const int sensorPin = A0;
const float baselineTemp = 23.0;

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
    float voltage = (sensorVal / 1024.0) * 5.0;
    float temperature = (voltage - 0.5) * 100;
    
    // 1行でまとめて送信
    Serial.print("Sensor: ");
    Serial.print(sensorVal);
    Serial.print(" | Volts: ");
    Serial.print(voltage);
    Serial.print(" | Temp: ");
    Serial.print(temperature);
    Serial.println("℃");  // 最後に改行
    
    int ledCount = (temperature - baselineTemp > 0) ? (int)(temperature - baselineTemp) : 0;
    ledCount = constrain(ledCount, 0, 6);
    
    // LED制御
    for (int i = 2; i < 8; i++) {
        digitalWrite(i, (i - 2 < ledCount) ? HIGH : LOW);
    }
    
    bool isLed5On = (ledCount >= 5);
    
    if (isLed5On && !mg400Started) {
        if (temperature >= 27.0) {
            tempCount++;
            Serial.print("温度27℃以上観測回数: ");
            Serial.println(tempCount);
            
            if (tempCount >= 3) {
                Serial.println("MG400_START");  // ← トリガー信号
                mg400Started = true;
                mg400Stopped = false;
                tempCount = 0;
            }
        }
    }
    
    if (!isLed5On) {
        tempCount = 0;
        led5OnStartTime = 0;
    }
    
    if (ledCount <= 3 && mg400Started && !mg400Stopped) {
        Serial.println("MG400_STOP");  // ← 停止信号
        mg400Stopped = true;
        mg400Started = false;
    }
    
    delay(500);
}