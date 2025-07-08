const int sensorPin = A0;
const float baselineTemp = 22.0;

void setup() {
    Serial.begin(9600);
    for (int pinNumber = 2; pinNumber < 8; pinNumber++) {
        pinMode(pinNumber, OUTPUT);
        digitalWrite(pinNumber, LOW);
    }
}

void loop() {
    int sensorVal = analogRead(sensorPin);
    Serial.print("sensor Value: ");
    Serial.print(sensorVal);

    float voltage = (sensorVal / 1024.0) * 5.0;
    Serial.print(", Volts: ");
    Serial.print(voltage);

    float temperature = (voltage - 0.5) * 100;
    Serial.print(", degrees C: ");
    Serial.println(temperature);

    int ledCount = (temperature - baselineTemp > 0) ? (int)(temperature - baselineTemp) : 0;
    ledCount = constrain(ledCount, 0, 6); // 最大6つのLEDを制御

    for (int i = 2; i < 8; i++) {
        digitalWrite(i, (i - 2 < ledCount) ? HIGH : LOW);
    }

    // 5個目のLEDが点灯したらシリアルでコマンド送信
    if (ledCount >= 5) {
        Serial.println("MG400_START");
    }

    delay(500); // 適度に待機（デバッグしやすくするため）
}
