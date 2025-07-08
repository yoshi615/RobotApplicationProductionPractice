import serial
import time
import socket
from threading import Thread

# シリアル通信設定
SERIAL_PORT = 'COM3'  # Arduinoが接続されているポート（環境に応じて変更）
BAUD_RATE = 9600
TRIGGER_SIGNAL = 'MG400_START'

# MG400設定
MG400_IP = "192.168.1.6"  # MG400のIPアドレス（環境に応じて変更）
SOCKET_TIMEOUT = 10  # Wi-Fi接続用タイムアウト（秒）

class MG400Controller:
    def __init__(self):
        self.dashboard_socket = None
        self.move_socket = None
        self.serial_conn = None
        
    def connect_mg400(self):
        """MG400に接続"""
        try:
            # Dashboard接続（29999ポート）
            self.dashboard_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.dashboard_socket.settimeout(SOCKET_TIMEOUT)  # Wi-Fi用タイムアウト設定
            self.dashboard_socket.connect((MG400_IP, 29999))
            
            # Move接続（30003ポート）
            self.move_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.move_socket.settimeout(SOCKET_TIMEOUT)  # Wi-Fi用タイムアウト設定
            self.move_socket.connect((MG400_IP, 30003))
            
            # ロボット有効化
            self.send_command(self.dashboard_socket, "EnableRobot()")
            
            print("MG400に接続しました")
            return True
        except Exception as e:
            print(f"MG400接続エラー: {e}")
            return False
    
    def send_command(self, socket_conn, command):
        """コマンドを送信"""
        try:
            socket_conn.send(command.encode('utf-8'))
            response = socket_conn.recv(1024).decode('utf-8')
            return response
        except socket.timeout:
            print(f"コマンドタイムアウト: {command}")
            return None
        except Exception as e:
            print(f"コマンド送信エラー: {e}")
            return None
    
    def check_connection(self):
        """接続状態を確認し、必要に応じて再接続"""
        try:
            # 簡単な状態確認コマンド
            response = self.send_command(self.dashboard_socket, "RobotMode()")
            if response is None:
                print("接続が切断されました。再接続を試みます...")
                return self.connect_mg400()
            return True
        except:
            print("接続が切断されました。再接続を試みます...")
            return self.connect_mg400()
    
    def connect_serial(self):
        """シリアル通信を開始"""
        try:
            self.serial_conn = serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=1)
            print(f"シリアルポート {SERIAL_PORT} に接続しました")
            return True
        except Exception as e:
            print(f"シリアル接続エラー: {e}")
            return False
    
    def execute_mg400_sequence(self):
        """MG400の動作シーケンスを実行"""
        try:
            # 接続状態を確認
            if not self.check_connection():
                print("接続の復旧に失敗しました")
                return
                
            print("MG400動作開始...")
            
            # ホームポジションに移動
            self.send_command(self.move_socket, "MovJ(250,0,50,0)")
            time.sleep(3)  # Wi-Fi接続のため待機時間を延長
            
            # 任意の動作パターン（例：ピック&プレース）
            # ポイント1に移動
            self.send_command(self.move_socket, "MovJ(200,100,100,0)")
            time.sleep(2)  # Wi-Fi接続のため待機時間を延長
            
            # Z軸を下降
            self.send_command(self.move_socket, "MovJ(200,100,30,0)")
            time.sleep(2)  # Wi-Fi接続のため待機時間を延長
            
            # Z軸を上昇
            self.send_command(self.move_socket, "MovJ(200,100,100,0)")
            time.sleep(2)  # Wi-Fi接続のため待機時間を延長
            
            # ポイント2に移動
            self.send_command(self.move_socket, "MovJ(200,-100,100,0)")
            time.sleep(2)  # Wi-Fi接続のため待機時間を延長
            
            # Z軸を下降
            self.send_command(self.move_socket, "MovJ(200,-100,30,0)")
            time.sleep(2)  # Wi-Fi接続のため待機時間を延長
            
            # ホームポジションに戻る
            self.send_command(self.move_socket, "MovJ(250,0,50,0)")
            time.sleep(3)  # Wi-Fi接続のため待機時間を延長
            
            print("MG400動作完了")
            
        except Exception as e:
            print(f"MG400動作エラー: {e}")
    
    def monitor_serial(self):
        """シリアル信号を監視"""
        while True:
            try:
                if self.serial_conn and self.serial_conn.in_waiting > 0:
                    received_data = self.serial_conn.readline().decode('utf-8').strip()
                    print(f"受信データ: {received_data}")
                    
                    if received_data == TRIGGER_SIGNAL:
                        print("トリガー信号を受信しました！")
                        # 別スレッドでMG400動作を実行
                        Thread(target=self.execute_mg400_sequence).start()
                
                time.sleep(0.1)  # CPU負荷軽減
                
            except Exception as e:
                print(f"シリアル監視エラー: {e}")
                break
    
    def run(self):
        """メイン実行関数"""
        print("MG400制御システムを開始します...")
        
        # MG400に接続
        if not self.connect_mg400():
            return
        
        # シリアル通信を開始
        if not self.connect_serial():
            return
        
        print(f"'{TRIGGER_SIGNAL}'信号を待機中...")
        print("Wi-Fi接続のため、応答時間が長くなる場合があります")
        
        try:
            # シリアル監視開始
            self.monitor_serial()
        except KeyboardInterrupt:
            print("プログラムを終了します...")
        finally:
            if self.serial_conn:
                self.serial_conn.close()
            if self.dashboard_socket:
                self.dashboard_socket.close()
            if self.move_socket:
                self.move_socket.close()
            print("接続を閉じました")

if __name__ == "__main__":
    controller = MG400Controller()
    controller.run()