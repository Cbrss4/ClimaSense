#!/usr/bin/env bash
set -Eeuo pipefail

software_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
repo_dir="$(cd -- "$software_dir/.." && pwd)"
session_dir="$(mktemp -d "${TMPDIR:-/tmp}/estacao-meteorologica.XXXXXX")"
broker_pid=""
subscriber_pid=""
api_pid=""

cleanup() {
  local pid
  for pid in "$api_pid" "$subscriber_pid" "$broker_pid"; do
    if [[ -n "$pid" ]] && kill -0 "$pid" 2>/dev/null; then
      kill "$pid" 2>/dev/null || true
    fi
  done
  wait 2>/dev/null || true
  rm -rf -- "$session_dir"
}
trap cleanup EXIT INT TERM

for command in mosquitto; do
  if ! command -v "$command" >/dev/null 2>&1; then
    printf 'Comando ausente: %s. Instale-o antes de executar este script.\n' "$command" >&2
    exit 1
  fi
done

if [[ ! -x "$software_dir/.venv/bin/python" ]]; then
  if ! command -v uv >/dev/null 2>&1; then
    printf 'Comando ausente: uv. Instale o uv e execute "uv sync" na pasta software.\n' >&2
    exit 1
  fi
  printf 'Ambiente Python ausente. Execute "uv sync" na pasta software.\n' >&2
  exit 1
fi

export WEATHER_DATABASE_PATH="$session_dir/leituras.db"
export MQTT_HOST=127.0.0.1
export MQTT_PORT=1883
export MQTT_TOPIC=weather/station-01/readings
export MQTT_QOS=1

if (echo >/dev/tcp/127.0.0.1/1883) >/dev/null 2>&1; then
  printf 'Usando o Mosquitto já ativo em 127.0.0.1:1883.\n'
else
  mosquitto -c "$software_dir/config/mosquitto-lan.conf" -v >"$session_dir/broker.log" 2>&1 &
  broker_pid=$!
  for _ in {1..40}; do
    if ! kill -0 "$broker_pid" 2>/dev/null; then
      cat "$session_dir/broker.log" >&2
      printf 'O Mosquitto encerrou durante a inicialização.\n' >&2
      exit 1
    fi
    if (echo >/dev/tcp/127.0.0.1/1883) >/dev/null 2>&1; then
      break
    fi
    sleep 0.25
  done
  if ! (echo >/dev/tcp/127.0.0.1/1883) >/dev/null 2>&1; then
    cat "$session_dir/broker.log" >&2
    printf 'O Mosquitto não abriu a porta 1883.\n' >&2
    exit 1
  fi
fi

cd "$software_dir"
"$software_dir/.venv/bin/python" -m app.mqtt_subscriber >"$session_dir/subscriber.log" 2>&1 &
subscriber_pid=$!
"$software_dir/.venv/bin/uvicorn" app.main:app --host 127.0.0.1 --port 8000 >"$session_dir/api.log" 2>&1 &
api_pid=$!

ready=false
for _ in {1..80}; do
  if ! kill -0 "$api_pid" 2>/dev/null; then
    cat "$session_dir/api.log" >&2
    exit 1
  fi
  if curl --fail --silent http://127.0.0.1:8000/health >/dev/null; then
    ready=true
    break
  fi
  sleep 0.25
done
if [[ "$ready" != true ]]; then
  cat "$session_dir/api.log" >&2
  printf 'A API não ficou disponível em 20 segundos.\n' >&2
  exit 1
fi

printf 'Estação em execução. Pressione Ctrl+C para encerrar.\n'
printf 'Broker MQTT: 127.0.0.1:1883 | API: http://127.0.0.1:8000\n'
printf 'Aguardando leituras do ESP32...\n'
while kill -0 "$subscriber_pid" 2>/dev/null && kill -0 "$api_pid" 2>/dev/null; do
  curl --fail --silent http://127.0.0.1:8000/api/v1/readings/latest || true
  sleep 1
done
printf '\nUm processo da estação encerrou. Consulte os logs temporários em %s\n' "$session_dir" >&2
