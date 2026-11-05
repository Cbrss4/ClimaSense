# Como abrir o dashboard

O dashboard roda no computador e abre no navegador. Ele não está publicado na Internet.

## Abrir o painel — Linux Mint ou Windows

Você precisa ter Python 3.12 e [`uv`](https://docs.astral.sh/uv/getting-started/installation/) instalados.

**1. Abra um terminal** (no VS Code, pressione Ctrl e a tecla de acento grave, abaixo de Esc) e entre na pasta `software` do repositório. Se o terminal já estiver na raiz do projeto — a pasta que contém `software`, `firmware` e `simulador` — digite:

```bash
cd software
```

**2. Na primeira vez, instale as dependências:**

```bash
uv sync
```

**3. Inicie o dashboard:**

```bash
uv run uvicorn app.main:app --reload
```

Deixe o terminal aberto enquanto estiver usando o painel. Isso é normal: o servidor precisa continuar rodando.

**4. Abra este endereço no navegador do mesmo computador:**

```text
http://127.0.0.1:8000/
```

Para encerrar, volte ao terminal e pressione `Ctrl+C`.

Sem conexão com o ESP32, o painel mostra dados de demonstração. Isso confirma que a interface abriu, mas os valores não vêm dos sensores.

## Mostrar leituras reais do ESP32

Para receber dados reais, também é necessário instalar e iniciar o Mosquitto, configurar o firmware e iniciar o assinante MQTT.

1. Instale e inicie o Mosquitto:

   Linux Mint — execute na raiz do repositório:

   ```bash
   sudo apt update
   sudo apt install mosquitto mosquitto-clients
   sudo install -m 0644 software/config/mosquitto-lan.conf /etc/mosquitto/conf.d/estacao.conf
   sudo systemctl enable --now mosquitto
   sudo systemctl restart mosquitto
   ```

   Windows — instale pelo WinGet:

   ```powershell
   winget install --id EclipseFoundation.Mosquitto -e
   ```

   Confira se o serviço Mosquitto está rodando:

   ```powershell
   Get-Service mosquitto
   ```

   Se o estado for `Running`, pare-o em um PowerShell como administrador:

   ```powershell
   Stop-Service mosquitto
   ```

   Depois, em um PowerShell na raiz do repositório, inicie o broker com a configuração do projeto:

   ```powershell
   & 'C:\Program Files\mosquitto\mosquitto.exe' -c '.\software\config\mosquitto-lan.conf' -v
   ```

   Deixe esse terminal do broker aberto. Se o Firewall perguntar, permita conexões somente em redes privadas. A configuração aceita conexões anônimas; use-a apenas numa rede local confiável.
2. Conecte o computador e o ESP32 à mesma rede Wi-Fi.
3. Na raiz do projeto, crie `firmware/include/secrets.h` a partir do exemplo, se esse arquivo ainda não existir.

   Linux Mint:

   ```bash
   cp firmware/include/secrets.example.h firmware/include/secrets.h
   ```

   Windows PowerShell:

   ```powershell
   Copy-Item .\firmware\include\secrets.example.h .\firmware\include\secrets.h
   ```

4. Edite `firmware/include/secrets.h`: preencha o nome e a senha do Wi-Fi e coloque em `MQTT_HOST` o IPv4 do computador que executa o Mosquitto. No Linux, consulte com `ip -4 addr`; no Windows, com `ipconfig`. **Não use `127.0.0.1` em `MQTT_HOST`.**
5. Grave o firmware na placa. No terminal, entre em `firmware`, rode `pio device list` para descobrir a porta e use-a no comando de upload.

   Linux Mint, exemplo:

   ```bash
   pio run
   pio run -t upload --upload-port /dev/ttyUSB0
   ```

   Windows PowerShell, exemplo:

   ```powershell
   pio run
   pio run -t upload --upload-port COM3
   ```

   Troque `/dev/ttyUSB0` ou `COM3` pela porta mostrada no seu computador.

6. Em outro terminal, na pasta `software`, inicie o assinante:

   ```bash
   uv run python -m app.mqtt_subscriber
   ```

   Deixe esse terminal e o terminal do dashboard abertos. O Mosquitto também deve continuar ativo.

O dashboard atualiza aproximadamente a cada dez segundos. Se continuar mostrando demonstração, confira no monitor serial se o ESP32 informa `MQTT conectado!` e `Leitura publicada no MQTT.`

**Atenção aos sensores:** BMP280 mede temperatura e pressão, mas não umidade. Para medir umidade, use um BME280. O arquivo `secrets.h` contém a senha do Wi-Fi; nunca o envie ao GitHub. A configuração MQTT incluída permite conexões anônimas, portanto use-a somente numa rede local confiável.
