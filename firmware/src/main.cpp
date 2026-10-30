#include <Arduino.h>
#include <Wire.h>
#include <WiFi.h>
#include <MQTT.h>
#include <Adafruit_Sensor.h>
#include <Adafruit_BME280.h>
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
constexpr unsigned long TEMPO_LIMITE_WIFI_MS = 20000;
constexpr unsigned long TEMPO_LIMITE_MQTT_MS = 10000;
constexpr char MQTT_TOPIC[] = "weather/station-01/readings";
constexpr char MQTT_CLIENT_ID[] = "station-01";

Adafruit_BME280 bme;
WiFiClient wifiClient;
MQTTClient mqttClient(512);
bool bmeDisponivel = false;

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

String criarPayload(float temperatura, float umidade, float pressao,
                    int qualidadeAr, int luminosidade, bool chuvaDetectada) {
  String payload;
  payload.reserve(256);
  payload += "{\"schema_version\":2";
  payload += ",\"device_id\":\"station-01\"";
  payload += ",\"captured_at\":null";
  payload += ",\"temperature_c\":";
  adicionarNumeroOuNull(payload, temperatura, -40.0F, 80.0F);
  payload += ",\"humidity_pct\":";
  adicionarNumeroOuNull(payload, umidade, 0.0F, 100.0F);
  payload += ",\"pressure_hpa\":";
  adicionarNumeroOuNull(payload, pressao, 300.0F, 1100.0F);
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
                    float minimo, float maximo) {
  Serial.print(rotulo);
  if (isnan(valor) || valor < minimo || valor > maximo) {
    Serial.println("LEITURA INVÁLIDA");
    return;
  }

  Serial.print(valor, 2);
  Serial.print(" ");
  Serial.println(unidade);
}

void setup() {
  Serial.begin(115200);
  delay(3000);
  Serial.println("Iniciando Estação Meteorológica...");

  Wire.begin(SDA_PIN, SCL_PIN);

  // O BME280 costuma usar o endereço 0x76 ou 0x77
  bmeDisponivel = bme.begin(0x76, &Wire);
  if (!bmeDisponivel) {
    bmeDisponivel = bme.begin(0x77, &Wire);
  }
  if (!bmeDisponivel) {
    Serial.println("Aviso: BME280 não encontrado (testei 0x76 e 0x77). Confira SDA/SCL/VIN/GND.");
  } else {
    Serial.println("BME280 encontrado!");
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

  if (WiFi.status() != WL_CONNECTED) {
    conectarWifi();
  }
  if (WiFi.status() == WL_CONNECTED && !mqttClient.connected()) {
    conectarMqtt();
  }
  mqttClient.loop();

  float temperatura = bmeDisponivel ? bme.readTemperature() : NAN;
  float umidade = bmeDisponivel ? bme.readHumidity() : NAN;
  float pressao = bmeDisponivel ? bme.readPressure() / 100.0F : NAN;

  int luminosidade = analogRead(LDR_PIN);
  int qualidadeAr = analogRead(MQ135_PIN);
  int chuvaBruta = analogRead(RAIN_PIN);
  bool chuvaDetectada = chuvaBruta < LIMITE_CHUVA;

  Serial.println("---- Leitura da Estação ----");
  imprimirMedida("Temperatura: ", temperatura, "°C", -40.0F, 80.0F);
  imprimirMedida("Umidade: ", umidade, "%", 0.0F, 100.0F);
  imprimirMedida("Pressão: ", pressao, "hPa", 300.0F, 1100.0F);
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
      temperatura, umidade, pressao, qualidadeAr, luminosidade,
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
