# Estação Viva integrada ao projeto

## Executar
Na pasta `software`:

```bash
uv sync
uv run uvicorn app.main:app --reload
```

Abra http://127.0.0.1:8000/ (dashboard) ou http://127.0.0.1:8000/docs (API).
Para receber a estação física, mantenha também o Mosquitto e `uv run python -m app.mqtt_subscriber` em execução, conforme o README original. Os scripts existentes de teste da estação continuam iniciando a mesma aplicação e agora disponibilizam o dashboard em `/`.

## Integração implementada
- Front-end sem build em `software/frontend/`, servido pelo FastAPI em `/` e `/assets/`.
- Consome `/api/v1/readings/latest` sem alterar o contrato original do MQTT, firmware ou endpoints existentes.
- Novo `/api/v1/dashboard/history`: últimas 12 horas por `received_at`, uma leitura por janela de cinco minutos e por dispositivo. Retorna registros originais, sem inventar médias ou interpolar valores ausentes. O painel filtra o histórico pelo dispositivo da última leitura recebida. A consulta existente com `limit=500` é preservada.
- Atualização a cada dez segundos. “Dados recentes” significa recebimento no servidor há no máximo dois minutos, não confirmação de conexão física. A API não distingue o simulador de hardware físico; o painel deixa isso explícito. Horário exibido de recebimento (fuso America/Sao_Paulo), com captura indicada quando disponível.
- Campos parciais são `—`; série sem valores informa ausência de histórico. Sem leituras ou API indisponível, exemplos fixos e históricos ilustrativos aparecem como demonstração. Nenhum dado demonstrativo é gravado no SQLite ou enviado por MQTT pelo front-end.
- MQ-135: `gas_raw` em ADC bruto, sem classificação oficial, ppm ou IQA. LDR: `light_raw` em ADC, não lux. Pressão BME280 em hPa. Chuva: estado seco/molhado conforme `rain_detected`, não intensidade ou milímetros; não é previsão meteorológica.
- Temas Claro, Escuro e Sistema, com escolha salva em localStorage e operação por teclado.
- Localização permanece “a configurar” em `software/frontend/index.html`.

## Arquivos alterados
`software/app/main.py`, `software/app/repository.py`; adicionados `software/frontend/`, `software/tests/test_dashboard.py`, este guia e links nos READMEs. Não há alteração em firmware ou simulador.

## Validação
76 testes passaram (`uv run pytest -q`). Testes novos cobrem entrega de HTML/assets, preservação de leituras parciais, recorte temporal e histórico superior ao limite anterior de 500 mensagens. Navegador: banco vazio, leitura parcial via API em banco isolado de QA, ausência de série e alternância do gráfico. A comunicação com o ESP32 físico não foi testada nesta sessão.

## Aplicar ao seu checkout
Copie `software/frontend/`, os dois arquivos Python alterados e `software/tests/test_dashboard.py` para seu checkout atualizado. Alternativamente use este projeto completo. Preserve suas configurações `.env`, `secrets.h` e banco local; eles não estão no pacote. Reinicie o Uvicorn. Não é necessária migração do banco.

Este pacote é uma integração local FastAPI/Python. O endereço estático publicado anteriormente continua sendo a demonstração; não passa a acessar automaticamente seu broker MQTT ou banco local. Para disponibilizar a integração fora do computador, hospede o serviço FastAPI com acesso ao seu banco/assinante MQTT, usando infraestrutura apropriada ao back-end Python.
