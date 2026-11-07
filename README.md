# ClimaSense — Estação Meteorológica Inteligente

Protótipo acadêmico de uma estação meteorológica com ESP32. O repositório reúne, em projetos independentes, o software de integração, o firmware dos sensores físicos e a simulação Wokwi.

## Estrutura

```text
├── software/                 # MQTT, validação, SQLite, API FastAPI e testes
├── firmware/                 # ESP32 físico com BME280, entradas analógicas e MQTT
│   ├── include/
│   ├── src/
│   └── platformio.ini
├── simulador/                # Projeto PlatformIO independente para o Wokwi
│   ├── src/
│   ├── diagram.json
│   ├── platformio.ini
│   └── wokwi.toml
├── evidencias/
├── ENTREGA_S1.md
├── diagrama-fluxo-codigo.svg
└── diagrama-ligacao.svg
```

Cada pasta principal deve ser aberta ou executada separadamente. Os projetos `firmware/` e `simulador/` possuem dependências e componentes diferentes e não compartilham o mesmo `src/main.cpp`.

## Fluxo do protótipo físico

```text
ESP32 → MQTT → validação Python → SQLite → API FastAPI → dashboard
```

As leituras brutas dos sensores não são apresentadas como unidades físicas sem método de calibração comprovado.

## Software

Entre na pasta antes de executar os comandos:

```powershell
cd software
uv sync
uv run pytest -q
```

As instruções de configuração, execução do broker, assinante MQTT, API e teste integrado estão em [`software/README.md`](software/README.md).

Para iniciar o painel local, consulte o [Manual de acesso ao dashboard](MANUAL-DASHBOARD.md).

## Firmware físico

O firmware utiliza um arquivo local para a configuração da rede e do broker. Crie-o a partir do exemplo e não o adicione ao Git:

```powershell
cd firmware
Copy-Item include/secrets.example.h include/secrets.h
pio run
```

O arquivo `firmware/include/secrets.h` é ignorado pelo Git. O arquivo versionado `secrets.example.h` contém somente valores fictícios.

## Simulador Wokwi

O simulador preserva os componentes equivalentes utilizados na primeira sprint:

| Variável | Protótipo físico | Simulação Wokwi |
|---|---|---|
| Temperatura e umidade | BME280 | DHT22 |
| Pressão atmosférica | BME280 | BMP180 |
| Luminosidade | Módulo LDR | Módulo LDR |
| Qualidade do ar | MQ-135 | Potenciômetro |
| Presença de chuva | Módulo de chuva | Chave deslizante |

Essas equivalências validam o fluxo do programa, mas não substituem testes elétricos, calibração ou avaliação de precisão com o hardware real.

Para compilar a cópia local:

```powershell
cd simulador
pio run
```

Depois da compilação, abra especificamente a pasta `simulador/` no VS Code e execute `Wokwi: Start Simulator`. Os caminhos de `wokwi.toml` são relativos a essa pasta.

Também é possível abrir a [simulação da S1 no navegador](https://wokwi.com/projects/474895435837456385). Consulte [`ENTREGA_S1.md`](ENTREGA_S1.md) para o resultado e as limitações dessa etapa.

## Verificação após mudanças de estrutura

Execute cada validação a partir da respectiva pasta:

```powershell
cd software
uv run pytest -q

cd ..\firmware
pio run

cd ..\simulador
pio run
```

Uma alteração só deve ser integrada depois que os caminhos documentados e as três verificações continuarem funcionando.


## Dashboard ClimaSense

Interface integrada com modos claro e escuro. Consulte o [guia de execução e integração](INTEGRACAO-DASHBOARD.md).
