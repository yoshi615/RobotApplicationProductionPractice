import time


def move_to_nearest_and_stop(controller):
    """現在位置から最も近い座標に移動してから停止"""
    try:
        print("現在位置から最も近い座標への移動を開始...")
        
        # 現在位置を取得
        current_x, current_y = controller.get_current_position()
        if current_x is None or current_y is None:
            print("現在位置の取得に失敗しました。中央位置に移動します...")
            controller.move_to_position("center")
            time.sleep(5)
            return
        
        print(f"現在位置: X={current_x:.2f}, Y={current_y:.2f}")
        
        # 最も近い目標座標を見つける
        nearest_name, (target_x, target_y) = controller.find_nearest_target_position(current_x, current_y)
        
        # 安全な速度で移動（1回に統一）
        controller.set_safe_speed()
        
        # 最も近い座標に移動
        controller.move_to_position(nearest_name)
        
        # 移動完了を待機
        print("移動完了を待機中...")
        time.sleep(6)  # 十分な待機時間
        
        # 移動後の位置確認
        controller.print_current_position("移動完了後の位置")
        
        # 動作停止コマンドを送信
        print("最寄り座標到達後、動作を停止します...")
        controller.send_command(controller.dashboard_socket, "StopRobot()")
        
    except Exception as e:
        print(f"最寄り座標への移動エラー: {e}")


def stop_mg400_movement(controller):
    """MG400の動作を強制停止"""
    try:
        print("MG400の動作を停止中...")
        
        # 1秒間その場で停止
        print("停止中...")
        time.sleep(1)  # 1秒間待機
        
        # 最寄りの座標まで移動してから停止
        move_to_nearest_and_stop(controller)
        
        print("MG400停止コマンドを送信しました")
        
        # 停止後のエラーチェックとクリア処理
        controller.handle_stop_errors()
        
        # 動作中フラグをリセット
        controller.is_running = False
        print("停止処理完了 - 新しいSTART信号を待機中...")
        
    except Exception as e:
        print(f"MG400停止エラー: {e}")
        controller.is_running = False

def return_to_center(controller):
    """確実に中央位置(250,0,0,0)に戻る処理"""
    try:
        print("中央位置復帰処理を開始...")
        
        # 現在位置を確認
        controller.print_current_position("初期位置")
        
        # 安全な速度に設定（1回に統一）
        controller.set_safe_speed()
        
        # 中央位置への移動を複数回試行
        for attempt in range(3):
            print(f"中央位置移動試行 {attempt+1}/3...")
            
            # MovJコマンドで中央に移動
            controller.move_to_position("center")
            
            # 移動完了を待機（十分な時間）
            print("移動完了を待機中...")
            time.sleep(8)  # より長い待機時間
            
            # 移動後の位置確認
            final_x, final_y = controller.print_current_position("移動後位置確認")
            
            # 位置が正しいかチェック（簡易的な確認）
            if final_x is not None and final_y is not None and abs(final_x - 250) < 10 and abs(final_y) < 10:
                print("✓ 中央位置への移動が完了しました")
                break
            else:
                print(f"移動未完了。再試行します... (試行 {attempt+1}/3)")
                if attempt < 2:  # 最後の試行でない場合
                    time.sleep(2)
        else:
            print("⚠ 中央位置への移動が完全には確認できませんでした")
            
    except Exception as e:
        print(f"中央位置復帰エラー: {e}")