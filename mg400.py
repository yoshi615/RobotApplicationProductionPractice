import serial
import time
import socket
from threading import Thread
import keyboard
from mg400_move import (
    move_to_nearest_and_stop as move_to_nearest_and_stop_fn,
    stop_mg400_movement as stop_mg400_movement_fn,
    return_to_center as return_to_center_fn,
)

# シリアル通信設定
ARDUINO_SERIAL_PORT = 'COM4'  # Arduinoが接続されているポート
BAUD_RATE = 9600
TRIGGER_SIGNAL = 'MG400_START'
STOP_SIGNAL = 'MG400_STOP'

# MG400設定
MG400_IP = "192.168.9.1"  # MG400のIPアドレス（環境に応じて変更）
SOCKET_TIMEOUT = 10  # Wi-Fi接続用タイムアウト（秒）

class MG400WiFiController:
    # 目標座標の定義（重複を避けるため）
    TARGET_POSITIONS = {
        "center": (250, 0, 0, 0),
        "positive": (250, 150, 0, -64),
        "negative": (250, -150, 0, -166)
    }
    
    def __init__(self):
        self.arduino_serial = None
        self.dashboard_socket = None
        self.move_socket = None
        self.stop_loop = False
        self.is_running = False  # 動作中フラグを追加
        self.stop_in_progress = False
        self.stop_handled_by_interrupt = False
        
    def set_safe_speed(self, speed=0.03, acc=0.03):
        """安全な速度・加速度を一括設定"""
        self.send_command(self.move_socket, f"Speed({speed})")
        self.send_command(self.move_socket, f"Acc({acc})")
        time.sleep(0.5)
    
    def move_to_position(self, target_name):
        """指定した座標に移動"""
        if target_name not in self.TARGET_POSITIONS:
            print(f"未知の目標座標: {target_name}")
            return False
        
        x, y, z, r = self.TARGET_POSITIONS[target_name]
        self.set_safe_speed()
        move_command = f"MovJ({x},{y},{z},{r})"
        print(f"{target_name}座標({x},{y},{z},{r})に移動中...")
        self.send_command(self.move_socket, move_command)
        return True
    
    def wait_for_movement_complete(self, timeout=15):
        """移動完了を待機（タイムアウト対応）"""
        print(f"移動完了を待機中（タイムアウト: {timeout}秒）...")
        time.sleep(timeout)  # 実装では単純な待機
        return True
    
    def print_current_position(self, label="現在位置"):
        """現在位置を取得して表示"""
        x, y = self.get_current_position()
        if x is not None and y is not None:
            print(f"{label}: X={x:.2f}, Y={y:.2f}")
            return x, y
        return None, None
        
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
                    print("✓ ロボットが有効化されました")

                    # ペイロード設定を追加
                    print("ペイロード設定中...")
                    self.send_command(self.dashboard_socket, "PayLoad(0.03,0.0001,0.0001,0.0015)")
                    time.sleep(1)
                    
                    # 中央へ移動
                    print("中央位置に移動中...")
                    self.move_to_position("center")
                    
                    return True
                elif mode_response2 and "4" in mode_response2:
                    print("ロボットは無効状態です。再度有効化を試みます...")
                    self.send_command(self.dashboard_socket, "EnableRobot()")
                    
            print("⚠ ロボット有効化の確認ができませんでした")
            return False
            
        except Exception as e:
            print(f"MG400有効化エラー: {e}")
            return False
        
    def get_current_position(self):
        """現在位置を取得してパースする"""
        try:
            pos_response = self.send_command(self.dashboard_socket, "GetPose()")
            if pos_response:
                # レスポンスから座標を抽出 (例: "{250.00,0.00,0.00,0.00}")
                pos_str = pos_response.strip('{}')
                coords = [float(x.strip()) for x in pos_str.split(',')]
                if len(coords) >= 2:
                    return coords[0], coords[1]  # X, Y座標を返す
            return None, None
        except Exception as e:
            print(f"現在位置取得エラー: {e}")
            return None, None

    def find_nearest_target_position(self, current_x, current_y):
        """現在位置から最も近い目標座標を見つける"""
        min_distance = float('inf')
        nearest_target = "center"
        nearest_coords = None
        
        for name, (target_x, target_y, _, _) in self.TARGET_POSITIONS.items():
            distance = ((current_x - target_x) ** 2 + (current_y - target_y) ** 2) ** 0.5
            print(f"目標座標 {name}({target_x}, {target_y}) までの距離: {distance:.2f}")
            
            if distance < min_distance:
                min_distance = distance
                nearest_target = name
                nearest_coords = (target_x, target_y)
        
        print(f"最も近い目標座標: {nearest_target} {nearest_coords}")
        return nearest_target, nearest_coords

    def move_to_nearest_and_stop(self):
        return move_to_nearest_and_stop_fn(self)

    def stop_mg400_movement(self):
        return stop_mg400_movement_fn(self)

    def return_to_center(self):
        return return_to_center_fn(self)

    def handle_stop_errors(self):
        try:
            err = self.send_command(self.dashboard_socket, "GetErrorID()")
            if err and "0" not in err:
                self.send_command(self.dashboard_socket, "ClearError()")
        except Exception as e:
            print(f"停止時エラーハンドリング失敗: {e}")

    def execute_mg400_sequence(self):
        """MG400の動作シーケンスを実行（改善版）"""
        try:
            print("MG400動作開始...")
            
            # 速度・加速度を低く設定（1回に統一）
            self.set_safe_speed()
            
            self.print_current_position("現在位置")
            
            loop_count = 0
            while not self.stop_loop:
                loop_count += 1
                print(f"\n--- ループ {loop_count} 回目 ---")
                
                # y軸正方向に移動
                if not self.move_to_position("positive"):
                    break
                if not self.wait_for_movement_complete(timeout=15):
                    print("⚠ 移動完了タイムアウト")
                    break
                print("✓ 正方向移動完了")
                
                if self.stop_loop:
                    break
                
                time.sleep(1)
                
                # y軸負方向に移動
                if not self.move_to_position("negative"):
                    break
                if not self.wait_for_movement_complete(timeout=15):
                    print("⚠ 移動完了タイムアウト")
                    break
                print("✓ 負方向移動完了")
                
                if self.stop_loop:
                    break
                
                time.sleep(2)
                
        except Exception as e:
            print(f"MG400動作シーケンスエラー: {e}")

    def keyboard_monitor(self):
        """キーボード監視（Escで停止）"""
        while not self.stop_loop:
            try:
                if keyboard.is_pressed('Esc'):
                    print("\nEscキーが押されました。割り込み停止を実行します...")
                    self.execute_stop_sequence()
                    break
                time.sleep(0.05)
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
                        
                        if self.is_running:
                            print("既に動作中です。現在の動作を停止して新しい動作を開始します...")
                            self.stop_loop = True
                            # 少し待機して停止処理を完了させる
                            time.sleep(2)
                        
                        # 新しい動作を開始
                        self.stop_loop = False  # ループフラグをリセット
                        self.is_running = True  # 動作中フラグをセット
                        print("新しい動作シーケンスを開始します...")
                        
                        # キーボード監視を開始
                        Thread(target=self.keyboard_monitor, daemon=True).start()
                        Thread(target=self.execute_mg400_sequence).start()
                    
                    elif received_data == STOP_SIGNAL:
                        print("停止信号を受信しました！割り込み停止を開始します...")
                        Thread(target=self.execute_stop_sequence, daemon=True).start()
                
                time.sleep(0.1)
                
            except Exception as e:
                print(f"Arduinoシリアル監視エラー: {e}")
                break

    def execute_stop_sequence(self):
        """停止処理を別スレッドで実行（Esc/STOP共通）"""
        if self.stop_in_progress:
            print("停止処理がすでに進行中です")
            return
        print("停止処理を開始します...")
        self.stop_in_progress = True
        self.stop_loop = True
        self.stop_handled_by_interrupt = True
        Thread(target=self._perform_stop_sequence, daemon=True).start()

    def _perform_stop_sequence(self):
        try:
            self.move_to_nearest_and_stop()
            self.handle_stop_errors()
            print("停止処理が完了しました")
        except Exception as e:
            print(f"停止処理エラー: {e}")
        finally:
            self.is_running = False
            self.stop_in_progress = False

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
        print(f"'{STOP_SIGNAL}'信号で動作を停止できます")
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