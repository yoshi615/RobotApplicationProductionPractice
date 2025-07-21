const int sensorPin = A0;
const float baselineTemp = 22.0;

bool mg400Started = false;
bool mg400Stopped = false;  // 停止信号送信フラグを追加
unsigned long led5OnStartTime = 0;
int tempCount = 0;  // 27℃以上を観測した回数（グローバル変数として宣言）

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

    // 27℃以上を3回観測したらSTARTコマンド送信
    if (isLed5On && !mg400Started) {
        // 27℃以上の場合カウントを増加
        if (temperature >= 27.0) {
            tempCount++;
            Serial.print("温度27℃以上観測回数: ");
            Serial.println(tempCount);
            
            // 3回観測したらコマンド送信
            if (tempCount >= 3) {
                Serial.println("MG400_START");
                mg400Started = true;  // 一度だけ送信
                mg400Stopped = false; // 停止フラグをリセット
                tempCount = 0;  // カウンターをリセット
            }
        }
    }

    // LED5が消灯した場合はカウンターとフラグをリセット
    if (!isLed5On) {
        tempCount = 0;
        mg400Started = false;
        mg400Stopped = false;
        led5OnStartTime = 0;
    }

    // LEDが3つに減った時の停止処理
    if (ledCount <= 3 && mg400Started && !mg400Stopped) {
        Serial.println("MG400_STOP");
        mg400Stopped = true;  // 一度だけ送信
        mg400Started = false; // 開始フラグをリセット（再開始可能にする）
    }

    delay(500); // 適度に待機（デバッグしやすくするため）
}