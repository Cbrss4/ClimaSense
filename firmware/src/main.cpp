#include <Arduino.h>
#include <Wire.h>
#include <WiFi.h>
#include <MQTT.h>
#include <Adafruit_Sensor.h>
#include <Adafruit_BME280.h>
#include <Adafruit_BMP280.h>
#include <math.h>
#include <string.h>
#include "secrets.h"

constexpr uint8_t SDA_PIN = 21;
constexpr uint8_t SCL_PIN = 22;
constexpr uint8_t LDR_PIN = 34;
constexpr uint8_t MQ135_PIN = 35;
constexpr uint8_t RAIN_PIN = 32;
constexpr int AMOSTRA_CHUVA_MOLHADO = 1911;
constexpr int AMOSTRA_CHUVA_SECO = 4095;
// Limiar inicial no ponto médio das amostras reais seco/molhado observadas.
constexpr int LIMITE_CHUVA =
    (AMOSTRA_CHUVA_MOLHADO + AMOSTRA_CHUVA_SECO) / 2;  // abaixo disso = molhado
constexpr unsigned long INTERVALO_LEITURA_MS = 500;
constexpr unsigned long PERIODO_SIMULACAO_MS = 600000;
constexpr unsigned long TEMPO_LIMITE_WIFI_MS = 20000;
constexpr unsigned long TEMPO_LIMITE_MQTT_MS = 10000;
constexpr char MQTT_TOPIC[] = "weather/station-01/readings";
constexpr char MQTT_CLIENT_ID[] = "station-01";

Adafruit_BME280 bme;
Adafruit_BMP280 bmp(&Wire);
WiFiClient wifiClient;
MQTTClient mqttClient(512);
bool bmeDisponivel = false;
bool bmpDisponivel = false;

void diagnosticarI2C() {
  Serial.println("Varredura I2C: procurando dispositivos...");
  bool dispositivoEncontrado = false;
  for (uint8_t endereco = 1; endereco < 127; ++endereco) {
    Wire.beginTransmission(endereco);
    if (Wire.endTransmission() == 0) {
      Serial.print("Dispositivo I2C encontrado em 0x");
      if (endereco < 16) {
        Serial.print("0");
      }
      Serial.println(endereco, HEX);
      dispositivoEncontrado = true;
    }
  }
  if (!dispositivoEncontrado) {
    Serial.println("Nenhum dispositivo respondeu no barramento I2C.");
  }
}

bool conectarWifi() {
  if (WiFi.status() == WL_CONNECTED) {
    return true;
  }

  WiFi.mode(WIFI_STA);
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
  Serial.print("Conectando ao Wi-Fi");

  const unsigned long inicio = millis();
  while (WiFi.status() != WL_CONNECTED &&
         millis() - inicio < TEMPO_LIMITE_WIFI_MS) {
    delay(500);
    Serial.print(".");
  }
  Serial.println();

  if (WiFi.status() != WL_CONNECTED) {
    Serial.println("Falha ao conectar ao Wi-Fi. Nova tentativa na próxima leitura.");
    return false;
  }

  Serial.println("Wi-Fi conectado!");
  Serial.print("IP do ESP32: ");
  Serial.println(WiFi.localIP());
  return true;
}

bool conectarMqtt() {
  if (mqttClient.connected()) {
    return true;
  }

  Serial.print("Conectando ao broker MQTT");
  const unsigned long inicio = millis();
  while (!mqttClient.connected() &&
         millis() - inicio < TEMPO_LIMITE_MQTT_MS) {
    if (mqttClient.connect(MQTT_CLIENT_ID)) {
      Serial.println("\nMQTT conectado!");
      return true;
    }
    Serial.print(".");
    delay(500);
  }

  Serial.println("\nFalha ao conectar ao MQTT. Nova tentativa na próxima leitura.");
  return false;
}

void adicionarNumeroOuNull(String& payload, float valor, float minimo,
                           float maximo) {
  if (isnan(valor) || valor < minimo || valor > maximo) {
    payload += "null";
    return;
  }
  payload += String(valor, 2);
}

String origemJson(const char* origem) {
  return String("\"") + origem + "\"";
}

String criarPayload(float temperatura, float umidade, float pressao,
                    const char* origemTemperatura,
                    const char* origemUmidade,
                    const char* origemPressao,
                    int qualidadeAr, int luminosidade, bool chuvaDetectada) {
  String payload;
  payload.reserve(384);
  payload += "{\"schema_version\":3";
  payload += ",\"device_id\":\"station-01\"";
  payload += ",\"captured_at\":null";
  payload += ",\"temperature_c\":";
  adicionarNumeroOuNull(payload, temperatura, -40.0F, 80.0F);
  payload += ",\"temperature_source\":";
  payload += origemJson(origemTemperatura);
  payload += ",\"humidity_pct\":";
  adicionarNumeroOuNull(payload, umidade, 0.0F, 100.0F);
  payload += ",\"humidity_source\":";
  payload += origemJson(origemUmidade);
  payload += ",\"pressure_hpa\":";
  adicionarNumeroOuNull(payload, pressao, 300.0F, 1100.0F);
  payload += ",\"pressure_source\":";
  payload += origemJson(origemPressao);
  payload += ",\"gas_raw\":";
  payload += String(qualidadeAr);
  payload += ",\"light_raw\":";
  payload += String(luminosidade);
  payload += ",\"light_detected\":null";
  payload += ",\"rain_detected\":";
  payload += chuvaDetectada ? "true" : "false";
  payload += "}";
  return payload;
}

void imprimirMedida(const char* rotulo, float valor, const char* unidade,
                    float minimo, float maximo, const char* origem) {
  Serial.print(rotulo);
  if (isnan(valor)) {
    Serial.println("INDISPONÍVEL");
    return;
  }
  if (valor < minimo || valor > maximo) {
    Serial.println("FORA DA FAIXA");
    return;
  }

  Serial.print(valor, 2);
  Serial.print(" ");
  Serial.print(unidade);
  if (strcmp(origem, "simulated") == 0) {
    Serial.print(" [SIMULADA]");
  } else {
    Serial.print(" [SENSOR]");
  }
  Serial.println();
}

float valorSimulado(float base, float amplitude, unsigned long agora,
                    unsigned long deslocamento) {
  const float fase = static_cast<float>((agora + deslocamento) %
                                        PERIODO_SIMULACAO_MS) /
                     static_cast<float>(PERIODO_SIMULACAO_MS);
  return base + amplitude * sinf(fase * 6.2831853F);
}

void setup() {
  Serial.begin(115200);
  delay(3000);
  Serial.println("Iniciando ClimaSense...");

  Wire.begin(SDA_PIN, SCL_PIN);

  // Tenta primeiro BME280 (temperatura, umidade e pressão).
  bmeDisponivel = bme.begin(0x76, &Wire);
  if (!bmeDisponivel) {
    bmeDisponivel = bme.begin(0x77, &Wire);
  }
  if (bmeDisponivel) {
    Serial.println("BME280 encontrado!");
  } else {
    // BMP280 mede temperatura e pressão; não possui sensor de umidade.
    bmpDisponivel = bmp.begin(0x76) || bmp.begin(0x77);
    if (bmpDisponivel) {
      Serial.println("BMP280 encontrado! Umidade não disponível neste modelo.");
    } else {
      Serial.println("Aviso: não encontrei BME280 nem BMP280 nos endereços 0x76/0x77. Confira SDA/SCL/VIN/GND.");
    }
  }

  pinMode(LDR_PIN, INPUT);
  pinMode(MQ135_PIN, INPUT);
  pinMode(RAIN_PIN, INPUT);

  Serial.println("Sensores prontos!");
  conectarWifi();
  mqttClient.begin(MQTT_HOST, MQTT_PORT, wifiClient);
  mqttClient.setKeepAlive(60);
  conectarMqtt();
}

void loop() {
  const unsigned long inicioCiclo = millis();
  static unsigned long ultimaVarreduraI2C = 0;

  if (!bmeDisponivel && !bmpDisponivel &&
      millis() - ultimaVarreduraI2C >= 5000) {
    ultimaVarreduraI2C = millis();
    diagnosticarI2C();
  }

  if (WiFi.status() != WL_CONNECTED) {
    conectarWifi();
  }
  if (WiFi.status() == WL_CONNECTED && !mqttClient.connected()) {
    conectarMqtt();
  }
  mqttClient.loop();

  float temperatura = NAN;
  float umidade = NAN;
  float pressao = NAN;
  const char* origemTemperatura = "unavailable";
  const char* origemUmidade = "unavailable";
  const char* origemPressao = "unavailable";
  if (bmeDisponivel) {
    temperatura = bme.readTemperature();
    umidade = bme.readHumidity();
    pressao = bme.readPressure() / 100.0F;
    origemTemperatura = "sensor";
    origemUmidade = "sensor";
    origemPressao = "sensor";
  } else if (bmpDisponivel) {
    temperatura = bmp.readTemperature();
    pressao = bmp.readPressure() / 100.0F;
    origemTemperatura = "sensor";
    origemPressao = "sensor";
  }

  // Valores de demonstração preenchem somente campos sem leitura física.
  const unsigned long tempoSimulacao = millis();
  if (!isfinite(temperatura) || temperatura < -40.0F || temperatura > 80.0F) {
    temperatura = valorSimulado(24.0F, 2.5F, tempoSimulacao, 0);
    origemTemperatura = "simulated";
  }
  if (!isfinite(umidade) || umidade < 0.0F || umidade > 100.0F) {
    umidade = valorSimulado(62.0F, 8.0F, tempoSimulacao, 170000);
    origemUmidade = "simulated";
  }
  if (!isfinite(pressao) || pressao < 300.0F || pressao > 1100.0F) {
    pressao = valorSimulado(1013.0F, 4.0F, tempoSimulacao, 330000);
    origemPressao = "simulated";
  }

  int luminosidade = analogRead(LDR_PIN);
  int qualidadeAr = analogRead(MQ135_PIN);
  int chuvaBruta = analogRead(RAIN_PIN);
  bool chuvaDetectada = chuvaBruta < LIMITE_CHUVA;

  Serial.println("---- Leitura da Estação ----");
  imprimirMedida("Temperatura: ", temperatura, "°C", -40.0F, 80.0F,
                 origemTemperatura);
  imprimirMedida("Umidade: ", umidade, "%", 0.0F, 100.0F,
                 origemUmidade);
  imprimirMedida("Pressão: ", pressao, "hPa", 300.0F, 1100.0F,
                 origemPressao);
  Serial.print("Luminosidade (LDR, leitura bruta): ");
  Serial.println(luminosidade);
  Serial.print("Qualidade do ar (MQ-135, leitura bruta): ");
  Serial.println(qualidadeAr);
  Serial.print("Chuva (leitura bruta): ");
  Serial.println(chuvaBruta);
  Serial.print("Chuva detectada: ");
  Serial.println(chuvaDetectada ? "SIM" : "NÃO");
  Serial.println("-----------------------------");

  const String payload = criarPayload(
      temperatura, umidade, pressao, origemTemperatura, origemUmidade,
      origemPressao, qualidadeAr, luminosidade,
      chuvaDetectada);
  if (mqttClient.connected()) {
    const bool publicado = mqttClient.publish(
        MQTT_TOPIC, payload, false, 1);
    Serial.println(publicado ? "Leitura publicada no MQTT."
                             : "Falha ao publicar leitura no MQTT.");
  }

  while (millis() - inicioCiclo < INTERVALO_LEITURA_MS) {
    mqttClient.loop();
    delay(10);
  }
}
