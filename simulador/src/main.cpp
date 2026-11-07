#include <Arduino.h>
#include <Wire.h>
#include <Adafruit_Sensor.h>
#include <Adafruit_BMP085.h>
#include <DHTesp.h>

constexpr uint8_t DHT_PIN = 15;
constexpr uint8_t LDR_PIN = 34;
constexpr uint8_t MQ135_PIN = 35;
constexpr uint8_t RAIN_PIN = 32;
constexpr unsigned long INTERVALO_LEITURA_MS = 2000;

Adafruit_BMP085 bmp;
DHTesp dht;
bool bmpDisponivel = false;

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
  delay(1000);
  Serial.println("Iniciando ClimaSense...");

  Wire.begin();
  dht.setup(DHT_PIN, DHTesp::DHT22);

  bmpDisponivel = bmp.begin();
  if (!bmpDisponivel) {
    Serial.println("Aviso: BMP180 não encontrado. As outras leituras continuarão normalmente.");
  }

  pinMode(LDR_PIN, INPUT);
  pinMode(MQ135_PIN, INPUT);
  pinMode(RAIN_PIN, INPUT);

  Serial.println("Sensores simulados prontos!");
  Serial.println("Nota: DHT22 e BMP180 representam as medições previstas para o BME280 físico.");
}

void loop() {
  TempAndHumidity ambiente = dht.getTempAndHumidity();
  float pressao = bmpDisponivel ? bmp.readPressure() / 100.0F : NAN;

  if (isnan(ambiente.temperature) || isnan(ambiente.humidity)) {
    Serial.print("Diagnóstico DHT22: ");
    Serial.println(dht.getStatusString());
  }

  int luminosidade = analogRead(LDR_PIN);
  int qualidadeAr = analogRead(MQ135_PIN);
  bool chuvaDetectada = digitalRead(RAIN_PIN) == LOW;

  Serial.println("---- Leitura da Estação ----");
  imprimirMedida("Temperatura: ", ambiente.temperature, "°C", -40.0F, 80.0F);
  imprimirMedida("Umidade: ", ambiente.humidity, "%", 0.0F, 100.0F);
  imprimirMedida("Pressão: ", pressao, "hPa", 300.0F, 1100.0F);
  Serial.print("Luminosidade simulada (LDR, leitura bruta): ");
  Serial.println(luminosidade);
  Serial.print("Qualidade do ar simulada (MQ-135, leitura bruta): ");
  Serial.println(qualidadeAr);
  Serial.print("Chuva detectada: ");
  Serial.println(chuvaDetectada ? "SIM" : "NÃO");
  Serial.println("-----------------------------");

  delay(INTERVALO_LEITURA_MS);
}
