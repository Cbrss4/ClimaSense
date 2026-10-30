# Estação meteorológica — software

Este repositório contém o backend da estação meteorológica. Ele recebe leituras por MQTT, valida o JSON, salva os dados em SQLite e permite consultá-los por uma API FastAPI.

```text
ESP32 → Mosquitto → assinante Python → SQLite → API → dashboard
```

O fluxo foi testado com o ESP32 físico e também pode ser reproduzido sem hardware por meio de uma publicação manual com `mosquitto_pub`.

## Estado atual

Já funcionam localmente:

- recebimento de mensagens pelo Mosquitto;
- validação do payload com Pydantic;
- armazenamento de leituras válidas e parciais;
- rejeição de mensagens inválidas sem interromper o serviço;
- consulta da leitura atual e do histórico pela API;
- testes automatizados com bancos descartáveis.
- publicação do ESP32 físico por Wi-Fi e MQTT no tópico contratado.

A integração foi validada na rede Wi-Fi usada no desenvolvimento e em um hotspot de celular, incluindo uma janela contínua de dois minutos e a retomada após queda da rede. O funcionamento com os dados móveis desativados ainda não foi testado.

## Requisitos

- Python 3.12;
- `uv`;
- Eclipse Mosquitto.

Na pasta `software`, instale as dependências e crie a configuração local:

```bash
uv sync
cp .env.example .env
```

O arquivo `.env` guarda a configuração local e já está incluído no `.gitignore`.

## Como executar

### Linux Mint

Instale o Mosquitto e os clientes MQTT pelo gerenciador de pacotes:

```bash
sudo apt update
sudo apt install mosquitto mosquitto-clients
```

Configure o serviço para aceitar conexões da rede local usando a configuração do repositório:

```bash
sudo install -m 0644 "$(git rev-parse --show-toplevel)/software/config/mosquitto-lan.conf" /etc/mosquitto/conf.d/estacao.conf
sudo systemctl restart mosquitto
```

Na raiz do repositório, ajuste `firmware/include/secrets.h` para o IPv4 da interface Wi-Fi do seu PC. Consulte-o com `ip -4 addr`; o ESP32 e o PC precisam estar na mesma rede. O assinante local conecta ao broker em `127.0.0.1`, enquanto o ESP32 conecta ao IPv4 do PC.

O broker de demonstração permite MQTT anônimo e escuta em todas as interfaces IPv4. Restrinja a porta 1883 à sub-rede confiável no firewall. Com UFW ativo, confira a sub-rede com `ip -4 addr` e crie uma regra para o CIDR correto; por exemplo, para `192.168.1.0/24`:

```bash
sudo ufw allow from 192.168.1.0/24 to any port 1883 proto tcp
```

O limiar inicial do sensor de chuva usa o ponto médio das amostras físicas observadas: 1911 no molhado e 4095 no seco. Recalibre se as leituras do seu sensor forem diferentes.

Instale as dependências Python uma vez e inicie o fluxo completo:

```bash
cd software
uv sync
./scripts/testar-estacao.sh
```

O script confirma que o Mosquitto atende tanto em `127.0.0.1` quanto no IPv4 local do PC. Se o broker existente estiver limitado ao loopback, ele exibe o comando para reconfigurar o serviço. Caso não haja broker ativo, inicia um broker local com `config/mosquitto-lan.conf`. O script também inicia o assinante MQTT e a API. Pressione `Ctrl+C` para encerrar.

### Windows

### Teste automático com o ESP32

Com o ESP32 ligado e na mesma rede do notebook, execute apenas:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\testar-estacao.ps1
```

O script verifica o Mosquitto, inicia o assinante e a API em segundo plano e mostra as leituras atualizadas aproximadamente a cada 500 ms. Pressione `Ctrl+C` para encerrar; o banco, os logs e os processos temporários são removidos automaticamente.

No Windows, também é possível abrir a pasta `software` e dar duplo clique em `TESTAR_ESTACAO.cmd`.

### Execução manual no Windows

Confirme que o Mosquitto está ativo:

```powershell
Get-Service mosquitto
```

Para receber o ESP32, o serviço deve carregar `config/mosquitto-lan.conf` e o Firewall do Windows deve permitir o executável do Mosquitto na porta TCP 1883 somente para a sub-rede local. A configuração é anônima e foi escolhida apenas para o protótipo acadêmico em rede isolada.

Abra dois terminais na pasta `software`.

No primeiro, inicie o assinante MQTT:

```powershell
uv run python -m app.mqtt_subscriber
```

No segundo, inicie a API:

```powershell
uv run uvicorn app.main:app --reload
```

## Teste rápido

Com o assinante e a API em execução, abra um terceiro PowerShell e publique uma leitura:

```powershell
$payload = '{"schema_version":2,"device_id":"station-01","captured_at":null,"temperature_c":26.1,"humidity_pct":58.4,"pressure_hpa":1011.7,"gas_raw":812,"light_raw":4095,"light_detected":null,"rain_detected":false}'
$payload | & 'C:\Program Files\mosquitto\mosquitto_pub.exe' -h 127.0.0.1 -p 1883 -t 'weather/station-01/readings' -q 1 -s
```

O uso de `-s` preserva as aspas do JSON no Windows PowerShell.

Consulte a leitura recebida:

```powershell
Invoke-RestMethod 'http://127.0.0.1:8000/api/v1/readings/latest' | Format-List
```

## Endpoints

| Rota | Função |
|---|---|
| `GET /health` | Verifica se a API está ativa |
| `GET /api/v1/readings/latest` | Retorna a leitura mais recente |
| `GET /api/v1/readings?limit=100` | Retorna o histórico |
| `GET /api/v1/readings/{id}` | Busca uma leitura pelo ID |

## Testes automatizados

```powershell
uv run pytest -q
```

Os testes usam bancos temporários e não alteram `data/station.db`.

## Documentação

- [Evidências da S2](docs/evidencias-s2.md)

`gas_raw` é um valor bruto, não ppm. `light_raw` também é bruto e não representa lux. O estado de chuva não representa milímetros.
