const int sensorPin = A0;
const float baselineTemp = 22.0;

bool mg400Started = false;
unsigned long led5OnStartTime = 0;

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

    // 5本目のLED（ピン番号6）が点灯しているか確認
    bool isLed5On = (ledCount >= 5);

    if (isLed5On && !mg400Started) {
        // 点灯開始時間を記録（まだ記録されていない場合）
        if (led5OnStartTime == 0) {
            led5OnStartTime = millis();
        }

        // 3秒以上経過したらコマンド送信
        if (millis() - led5OnStartTime >= 3000) {
            Serial.println("MG400_START");
            mg400Started = true;  // 一度だけ送信
        }
    } else {
        // LEDがオフになったらタイマーをリセット
        led5OnStartTime = 0;
    }

    delay(500); // 適度に待機（デバッグしやすくするため）
}
