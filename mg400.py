import serial
import time
import socket
from threading import Thread
import keyboard

# シリアル通信設定
ARDUINO_SERIAL_PORT = 'COM4'  # Arduinoが接続されているポート
BAUD_RATE = 9600
TRIGGER_SIGNAL = 'MG400_START'
STOP_SIGNAL = 'MG400_STOP'

# MG400設定
MG400_IP = "192.168.9.1"  # MG400のIPアドレス（環境に応じて変更）
SOCKET_TIMEOUT = 10  # Wi-Fi接続用タイムアウト（秒）

class MG400WiFiController:
    def __init__(self):
        self.arduino_serial = None
        self.dashboard_socket = None
        self.move_socket = None
        self.stop_loop = False
        self.is_running = False  # 動作中フラグを追加
        
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
                    
                    # 中央へ移動
                    print("y軸負方向に150mm移動中...")
                    self.send_command(self.move_socket, "MovJ(250,0,0,0)")
                    
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
        # 目標座標の定義
        targets = {
            "center": (250, 0),
            "positive": (250, 150),
            "negative": (250, -150)
        }
        
        min_distance = float('inf')
        nearest_target = "center"
        nearest_coords = (250, 0)
        
        for name, (target_x, target_y) in targets.items():
            # ユークリッド距離を計算
            distance = ((current_x - target_x) ** 2 + (current_y - target_y) ** 2) ** 0.5
            print(f"目標座標 {name}({target_x}, {target_y}) までの距離: {distance:.2f}")
            
            if distance < min_distance:
                min_distance = distance
                nearest_target = name
                nearest_coords = (target_x, target_y)
        
        print(f"最も近い目標座標: {nearest_target} {nearest_coords}")
        return nearest_target, nearest_coords

    def move_to_nearest_and_stop(self):
        """現在位置から最も近い座標に移動してから停止"""
        try:
            print("現在位置から最も近い座標への移動を開始...")
            
            # 現在位置を取得
            current_x, current_y = self.get_current_position()
            if current_x is None or current_y is None:
                print("現在位置の取得に失敗しました。中央位置に移動します...")
                self.send_command(self.move_socket, "MovJ(250,0,0,0)")
                time.sleep(5)
                return
            
            print(f"現在位置: X={current_x:.2f}, Y={current_y:.2f}")
            
            # 最も近い目標座標を見つける
            nearest_name, (target_x, target_y) = self.find_nearest_target_position(current_x, current_y)
            
            # 安全な速度で移動
            self.send_command(self.move_socket, "Speed(15)")
            time.sleep(0.5)
            
            # 最も近い座標に移動
            if nearest_name == "positive":
                print("y軸正方向の座標(250,150,0,-64)に移動中...")
                self.send_command(self.move_socket, "MovJ(250,150,0,-64)")
            elif nearest_name == "negative":
                print("y軸負方向の座標(250,-150,0,-166)に移動中...")
                self.send_command(self.move_socket, "MovJ(250,-150,0,-166)")
            else:  # center
                print("中央座標(250,0,0,0)に移動中...")
                self.send_command(self.move_socket, "MovJ(250,0,0,0)")
            
            # 移動完了を待機
            print("移動完了を待機中...")
            time.sleep(6)  # 十分な待機時間
            
            # 移動後の位置確認
            final_x, final_y = self.get_current_position()
            if final_x is not None and final_y is not None:
                print(f"移動完了後の位置: X={final_x:.2f}, Y={final_y:.2f}")
            
            # 動作停止コマンドを送信
            print("最寄り座標到達後、動作を停止します...")
            self.send_command(self.dashboard_socket, "StopRobot()")
            
        except Exception as e:
            print(f"最寄り座標への移動エラー: {e}")

    def stop_mg400_movement(self):
        """MG400の動作を強制停止"""
        try:
            print("MG400の動作を停止中...")
            
            # 最寄りの座標まで移動してから停止
            self.move_to_nearest_and_stop()
            
            print("MG400停止コマンドを送信しました")
            
            # 停止後のエラーチェックとクリア処理
            self.handle_stop_errors()
            
            # 動作中フラグをリセット
            self.is_running = False
            print("停止処理完了 - 新しいSTART信号を待機中...")
            
        except Exception as e:
            print(f"MG400停止エラー: {e}")
            self.is_running = False

    def handle_stop_errors(self):
        """停止後のエラーハンドリング（ライトは緑色のまま）"""
        try:
            print("停止後エラーチェックを開始...")
            
            # 停止コマンド後の安定化待機
            time.sleep(3)
            
            # ロボット状態を確認
            mode_response = self.send_command(self.dashboard_socket, "RobotMode()")
            print(f"停止後のロボット状態: {mode_response}")
            
            # エラー情報を取得
            error_response = self.send_command(self.dashboard_socket, "GetErrorID()")
            print(f"エラー状態: {error_response}")
            
            # エラーがある場合は詳細処理
            if error_response and not ("0" in error_response and len(error_response.split(',')) == 1):
                print("エラーを検出しました。詳細クリア処理を開始...")
                
                # 緊急停止解除
                print("緊急停止を解除中...")
                self.send_command(self.dashboard_socket, "ResetRobot()")
                time.sleep(2)
                
                # 複数回エラークリアを試行（より長い待機時間）
                for i in range(5):
                    print(f"エラークリア試行 {i+1}/5...")
                    clear_response = self.send_command(self.dashboard_socket, "ClearError()")
                    if clear_response and "0" in clear_response:
                        print("✓ エラークリア成功")
                        break
                    time.sleep(2)  # より長い待機時間
                
                # エラークリア後の十分な待機
                time.sleep(3)
                
                # エラークリア後の状態確認
                error_check = self.send_command(self.dashboard_socket, "GetErrorID()")
                print(f"エラークリア後の状態: {error_check}")
                
                # ロボット状態を再確認
                mode_response_final = self.send_command(self.dashboard_socket, "RobotMode()")
                print(f"最終状態: {mode_response_final}")
                
                if mode_response_final and "5" in mode_response_final:
                    print("✓ ロボットは有効状態を維持しています（ライトは緑色のままです）")
                elif mode_response_final and "4" in mode_response_final:
                    print("ロボットが無効化されています。再有効化します...")
                    self.enable_robot_after_error()
                else:
                    print("⚠ ロボット状態の確認ができませんでした。強制再有効化を試みます...")
                    self.enable_robot_after_error()
            else:
                print("エラーは検出されませんでした。ロボット状態を確認します。")
                # ロボット状態を確認して必要に応じて有効化
                mode_check = self.send_command(self.dashboard_socket, "RobotMode()")
                if mode_check and "4" in mode_check:
                    print("ロボットが無効化されています。再有効化します...")
                    self.enable_robot_after_error()
                elif mode_check and "5" in mode_check:
                    print("✓ ロボットは有効状態を維持しています")
                else:
                    print("ロボット状態が不明です。再有効化を試みます...")
                    self.enable_robot_after_error()
            
            print("停止後処理が完了しました（ロボットは有効状態のままです）")
            
        except Exception as e:
            print(f"停止後エラーハンドリングエラー: {e}")

    def enable_robot_after_error(self):
        """エラー後のロボット再有効化処理"""
        try:
            print("ロボット再有効化処理を開始...")
            
            # まず無効化して状態をリセット
            self.send_command(self.dashboard_socket, "DisableRobot()")
            time.sleep(2)
            
            # 再度エラークリア
            for i in range(3):
                print(f"再エラークリア試行 {i+1}/3...")
                clear_response = self.send_command(self.dashboard_socket, "ClearError()")
                if clear_response and "0" in clear_response:
                    print("✓ 再エラークリア成功")
                    break
                time.sleep(1)
            
            # ロボット有効化
            print("ロボットを再有効化...")
            enable_response = self.send_command(self.dashboard_socket, "EnableRobot()")
            print(f"EnableRobot応答: {enable_response}")
            
            # 有効化の確認（より長い待機）
            for i in range(10):
                time.sleep(3)
                mode_response = self.send_command(self.dashboard_socket, "RobotMode()")
                print(f"再有効化状態確認 {i+1}/10: {mode_response}")
                
                if mode_response and "5" in mode_response:
                    print("✓ ロボットが正常に再有効化されました")
                    return True
                elif mode_response and "4" in mode_response:
                    print("ロボットはまだ無効状態です。再度有効化を試みます...")
                    self.send_command(self.dashboard_socket, "EnableRobot()")
            
            print("⚠ ロボット再有効化の確認ができませんでした")
            return False
            
        except Exception as e:
            print(f"ロボット再有効化エラー: {e}")
            return False

    def return_to_center(self):
        """確実に中央位置(250,0,0,0)に戻る処理"""
        try:
            print("中央位置復帰処理を開始...")
            
            # 現在位置を確認
            pos_response = self.send_command(self.dashboard_socket, "GetPose()")
            print(f"現在位置: {pos_response}")
            
            # 安全な速度に設定
            self.send_command(self.move_socket, "Speed(10)")  # より安全な速度
            time.sleep(1)
            
            # 中央位置への移動を複数回試行
            for attempt in range(3):
                print(f"中央位置移動試行 {attempt+1}/3...")
                
                # MovJコマンドで中央に移動
                move_response = self.send_command(self.move_socket, "MovJ(250,0,0,0)")
                print(f"MovJコマンド応答: {move_response}")
                
                # 移動完了を待機（十分な時間）
                print("移動完了を待機中...")
                time.sleep(8)  # より長い待機時間
                
                # 移動後の位置確認
                final_pos = self.send_command(self.dashboard_socket, "GetPose()")
                print(f"移動後位置確認: {final_pos}")
                
                # 位置が正しいかチェック（簡易的な確認）
                if final_pos and "250" in final_pos and ",0," in final_pos:
                    print("✓ 中央位置への移動が完了しました")
                    break
                else:
                    print(f"移動未完了。再試行します... (試行 {attempt+1}/3)")
                    if attempt < 2:  # 最後の試行でない場合
                        time.sleep(2)
            else:
                print("⚠ 中央位置への移動が完全には確認できませんでした")
            
            # 速度を元に戻す
            self.send_command(self.move_socket, "Speed(20)")
            
        except Exception as e:
            print(f"中央位置復帰エラー: {e}")

    def execute_mg400_sequence(self):
        """MG400の動作シーケンスを実行"""
        try:
            print("MG400動作開始...")
            print("Escキーでループを停止できます")
            
            # 速度設定（遅くする）
            print("速度を設定中...")
            self.send_command(self.move_socket, "Speed(20)")  # 20%の速度に設定
            
            # 現在位置確認
            pos_response = self.send_command(self.dashboard_socket, "GetPose()")
            print(f"現在位置: {pos_response}")
            
            # y軸の繰り返し動作
            loop_count = 0
            while not self.stop_loop:
                loop_count += 1
                print(f"\n--- ループ {loop_count} 回目 ---")
                
                # 停止フラグチェック
                if self.stop_loop:
                    break
                
                # y軸正方向に移動
                print("y軸正方向に移動中...")
                self.send_command(self.move_socket, "MovJ(250,150,0,-64)")
                
                # 動作完了を待つ間も停止フラグをチェック
                for i in range(30):  # 待機時間を3秒に延長（遅い速度に対応）
                    if self.stop_loop:
                        break
                    time.sleep(0.1)
                
                if self.stop_loop:
                    break

                # y軸移動後の位置確認
                pos_response = self.send_command(self.dashboard_socket, "GetPose()")
                print(f"y軸正方向移動後の位置: {pos_response}")
                
                # 停止フラグチェック
                if self.stop_loop:
                    break

                # y軸負方向に移動
                print("y軸負方向に移動中...")
                self.send_command(self.move_socket, "MovJ(250,-150,0,-166)")
                
                # 動作完了を待つ間も停止フラグをチェック
                for i in range(30):  # 待機時間を3秒に延長（遅い速度に対応）
                    if self.stop_loop:
                        break
                    time.sleep(0.1)
                
                if self.stop_loop:
                    break
                    
                # 移動後の位置確認
                pos_response = self.send_command(self.dashboard_socket, "GetPose()")
                print(f"y軸負方向移動後の位置: {pos_response}")
                
                # 停止フラグチェック
                if self.stop_loop:
                    break
                
                
                # 動作完了を待つ間も停止フラグをチェック
                for i in range(30):
                    if self.stop_loop:
                        break
                    time.sleep(0.1)
            
            # 停止処理
            if self.stop_loop:
                self.stop_mg400_movement()
            
            print("MG400動作完了")
            
        except Exception as e:
            print(f"MG400動作エラー: {e}")
            # エラー時も停止処理を実行
            self.stop_mg400_movement()
        finally:
            # 動作終了時に必ずフラグをリセット
            self.is_running = False
            print("動作シーケンス終了 - 新しいSTART信号を待機中...")

    def keyboard_monitor(self):
        """キーボード監視（Escで停止）"""
        while not self.stop_loop:
            try:
                if keyboard.is_pressed('Esc'):
                    print("\nEscキーが押されました。現在位置から最も近い座標まで移動後に停止します...")
                    self.stop_loop = True
                    # 最寄り座標への移動処理
                    self.move_to_nearest_and_stop()
                    # エラーハンドリング
                    self.handle_stop_errors()
                    # フラグリセット
                    self.is_running = False
                    print("Escキーによる停止処理完了")
                    break
                time.sleep(0.05)  # より頻繁にチェック
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
                        print("停止信号を受信しました！現在位置から最も近い座標まで移動後に停止します...")
                        if self.is_running:
                            self.stop_loop = True
                            # 最寄り座標への移動処理
                            self.move_to_nearest_and_stop()
                            # エラーハンドリング
                            self.handle_stop_errors()
                            # フラグリセット
                            self.is_running = False
                            print("STOP信号による停止処理完了")
                        else:
                            print("現在動作していません")
                
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