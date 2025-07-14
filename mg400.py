import serial
import time
import socket
from threading import Thread
import keyboard

# シリアル通信設定
ARDUINO_SERIAL_PORT = 'COM4'  # Arduinoが接続されているポート
BAUD_RATE = 9600
TRIGGER_SIGNAL = 'MG400_START'

# MG400設定
MG400_IP = "192.168.9.1"  # MG400のIPアドレス（環境に応じて変更）
SOCKET_TIMEOUT = 10  # Wi-Fi接続用タイムアウト（秒）

class MG400WiFiController:
    def __init__(self):
        self.arduino_serial = None
        self.dashboard_socket = None
        self.move_socket = None
        self.stop_loop = False
        
    def send_command(self, socket_conn, command):
        """MG400にコマンドを送信し、応答を確認"""
        try:
            full_command = command + "\n"
            socket_conn.send(full_command.encode('utf-8'))
            response = socket_conn.recv(1024).decode('utf-8').strip()
            print(f"コマンド: {command} -> 応答: {response}")
            return response
        except socket.timeout:
            print(f"コマンドタイムアウト: {command}")
            return None
        except Exception as e:
            print(f"コマンド送信エラー: {e}")
            return None
    
    def connect_mg400_wifi(self):
        """MG400にWi-Fi接続"""
        try:
            print("MG400への接続を開始します...")
            
            # Dashboard接続（29999ポート）
            self.dashboard_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.dashboard_socket.settimeout(SOCKET_TIMEOUT)
            self.dashboard_socket.connect((MG400_IP, 29999))
            
            # Move接続（30003ポート）
            self.move_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.move_socket.settimeout(SOCKET_TIMEOUT)
            self.move_socket.connect((MG400_IP, 30003))
            
            print("MG400にWi-Fi接続しました")
            return True
        except Exception as e:
            print(f"MG400 Wi-Fi接続エラー: {e}")
            return False
    
    def enable_mg400(self):
        """MG400を有効化"""
        try:
            print("MG400初期化シーケンスを開始します...")
            
            # ロボット状態確認
            mode_response = self.send_command(self.dashboard_socket, "RobotMode()")
            print(f"RobotMode応答: {mode_response}")
            
            # 複数回エラークリアを試行
            for i in range(3):
                print(f"エラークリア試行 {i+1}/3...")
                clear_response = self.send_command(self.dashboard_socket, "ClearError()")
                if clear_response and "0" in clear_response:
                    print("エラークリア成功")
                    break
                time.sleep(1)
            
            # ロボット無効化→有効化
            print("ロボットを無効化...")
            self.send_command(self.dashboard_socket, "DisableRobot()")
            time.sleep(2)
            
            print("ロボットを有効化...")
            enable_response = self.send_command(self.dashboard_socket, "EnableRobot()")
            print(f"EnableRobot応答: {enable_response}")
            
            # 有効化の確認
            for i in range(5):
                time.sleep(2)
                mode_response2 = self.send_command(self.dashboard_socket, "RobotMode()")
                print(f"状態確認 {i+1}/5: {mode_response2}")
                
                if mode_response2 and "5" in mode_response2:
                    print("✓ ロボットが有効化されました（ライトが緑色になっているはずです）")
                    
                    # 有効化時の座標を表示
                    pos_response = self.send_command(self.dashboard_socket, "GetPose()")
                    print(f"有効化時の座標: {pos_response}")
                    
                    return True
                elif mode_response2 and "4" in mode_response2:
                    print("ロボットは無効状態です。再度有効化を試みます...")
                    self.send_command(self.dashboard_socket, "EnableRobot()")
                    
            print("⚠ ロボット有効化の確認ができませんでした")
            return False
            
        except Exception as e:
            print(f"MG400有効化エラー: {e}")
            return False
        
    def execute_mg400_sequence(self):
        """MG400の動作シーケンスを実行"""
        try:
            print("MG400動作開始...")
            print("Escキーでループを停止できます")
            
            # 現在位置確認
            pos_response = self.send_command(self.dashboard_socket, "GetPose()")
            print(f"現在位置: {pos_response}")
            
            # Z軸の繰り返し動作
            loop_count = 0
            while not self.stop_loop:
                loop_count += 1
                print(f"\n--- ループ {loop_count} 回目 ---")
                
                # Z軸下降
                print("Z軸下降中...")
                self.send_command(self.move_socket, "MovJ(250,0,30,0)")
                time.sleep(0.1)
                
                if self.stop_loop:
                    break
                    
                # 下降後の位置確認
                pos_response = self.send_command(self.dashboard_socket, "GetPose()")
                print(f"Z軸下降後の位置: {pos_response}")
                
                # Z軸上昇
                print("Z軸上昇中...")
                self.send_command(self.move_socket, "MovJ(250,0,100,0)")
                time.sleep(0.1)
                
                if self.stop_loop:
                    break
                    
                # 上昇後の位置確認
                pos_response = self.send_command(self.dashboard_socket, "GetPose()")
                print(f"Z軸上昇後の位置: {pos_response}")
                
                if self.stop_loop:
                    break
            
            print("MG400動作完了")
            
        except Exception as e:
            print(f"MG400動作エラー: {e}")
    
    def keyboard_monitor(self):
        """キーボード監視（Escで停止）"""
        while not self.stop_loop:
            try:
                if keyboard.is_pressed('Esc'):
                    print("\nEscキーが押されました。動作を停止します...")
                    self.stop_loop = True
                    break
                time.sleep(0.1)
            except:
                pass
    
    def connect_arduino_serial(self):
        """Arduinoシリアル接続（有線）"""
        try:
            self.arduino_serial = serial.Serial(ARDUINO_SERIAL_PORT, BAUD_RATE, timeout=1)
            print(f"Arduinoシリアルポート {ARDUINO_SERIAL_PORT} に接続しました（有線）")
            return True
        except Exception as e:
            print(f"Arduinoシリアル接続エラー: {e}")
            return False
    
    def monitor_arduino_serial(self):
        """Arduinoからの信号を監視（有線）"""
        while True:
            try:
                if self.arduino_serial and self.arduino_serial.in_waiting > 0:
                    received_data = self.arduino_serial.readline().decode('utf-8').strip()
                    print(f"Arduino受信データ（有線）: {received_data}")
                    
                    if received_data == TRIGGER_SIGNAL:
                        print("トリガー信号を受信しました！")
                        self.stop_loop = False  # ループフラグをリセット
                        # キーボード監視を開始
                        Thread(target=self.keyboard_monitor, daemon=True).start()
                        Thread(target=self.execute_mg400_sequence).start()
                
                time.sleep(0.1)
                
            except Exception as e:
                print(f"Arduinoシリアル監視エラー: {e}")
                break
    
    def run(self):
        """メイン実行関数"""
        print("MG400制御システムを開始します...")
        print("接続構成:")
        print("- Arduino <-> PC: 有線（USB/シリアル）")
        print("- PC <-> MG400: 無線（Wi-Fi）")
        
        # MG400にWi-Fi接続
        if not self.connect_mg400_wifi():
            print("MG400へのWi-Fi接続に失敗しました")
            return
        
        # MG400を有効化
        if not self.enable_mg400():
            print("MG400の有効化に失敗しました")
            return
        
        # Arduinoシリアル接続
        if not self.connect_arduino_serial():
            print("Arduinoへの有線接続に失敗しました")
            return
        
        print(f"'{TRIGGER_SIGNAL}'信号を待機中...")
        print("システムが正常に動作しています")
        
        try:
            self.monitor_arduino_serial()
        except KeyboardInterrupt:
            print("プログラムを終了します...")
        finally:
            if self.arduino_serial:
                self.arduino_serial.close()
            if self.dashboard_socket:
                self.dashboard_socket.close()
            if self.move_socket:
                self.move_socket.close()
            print("接続を閉じました")

if __name__ == "__main__":
    controller = MG400WiFiController()
    controller.run()