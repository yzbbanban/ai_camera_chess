import cv2
import numpy as np
import requests
import os
import threading
import subprocess
import sys

os.environ['NO_PROXY'] = 'localhost,127.0.0.1,::1'


def play_edge_tts_thread(text):
    try:
        voice = "zh-CN-XiaoyiNeural"
        output_file = "current_taunt.mp3"
        subprocess.run([
            sys.executable, '-m', 'edge_tts',
            '--voice', voice,
            '--rate=+15%',
            '--text', text,
            '--write-media', output_file
        ], check=True)
        subprocess.run(['afplay', output_file])
    except Exception as e:
        print(f"⚠️ edge-tts 播报异常: {e}")


def speak_taunt(text):
    threading.Thread(target=play_edge_tts_thread, args=(text,), daemon=True).start()


def order_points(pts):
    rect = np.zeros((4, 2), dtype="float32")
    s = pts.sum(axis=1)
    rect[0] = pts[np.argmin(s)]
    rect[2] = pts[np.argmax(s)]
    diff = np.diff(pts, axis=1)
    rect[1] = pts[np.argmin(diff)]
    rect[3] = pts[np.argmax(diff)]
    return rect


def evaluate_line(board, r, c, dr, dc, player):
    count = 1
    i, j = r + dr, c + dc
    space1 = 0
    while 0 <= i < 15 and 0 <= j < 15:
        if board[i, j] == player:
            count += 1
        elif board[i, j] == 0:
            space1 = 1
            break
        else:
            break
        i, j = i + dr, j + dc

    i, j = r - dr, c - dc
    space2 = 0
    while 0 <= i < 15 and 0 <= j < 15:
        if board[i, j] == player:
            count += 1
        elif board[i, j] == 0:
            space2 = 1
            break
        else:
            break
        i, j = i - dr, j - dc

    spaces = space1 + space2
    if count >= 5: return 100000
    if count == 4 and spaces == 2: return 10000
    if count == 4 and spaces == 1: return 1000
    if count == 3 and spaces == 2: return 1000
    if count == 3 and spaces == 1: return 100
    if count == 2 and spaces == 2: return 100
    if count == 2 and spaces == 1: return 10
    return 0


def get_best_move(board_state):
    best_score = -1
    best_move = (7, 7)
    directions = [(1, 0), (0, 1), (1, 1), (1, -1)]
    for r in range(15):
        for c in range(15):
            if board_state[r, c] == 0:
                score = 0
                for dr, dc in directions:
                    score += evaluate_line(board_state, r, c, dr, dc, 2) * 1.1
                    score += evaluate_line(board_state, r, c, dr, dc, 1) * 1.5
                score += (7 - abs(7 - r)) + (7 - abs(7 - c))
                if score > best_score:
                    best_score = score
                    best_move = (r, c)
    return best_move


def check_winner(board):
    directions = [(0, 1), (1, 0), (1, 1), (1, -1)]
    for r in range(15):
        for c in range(15):
            player = board[r, c]
            if player != 0:
                for dr, dc in directions:
                    count = 1
                    nr, nc = r + dr, c + dc
                    while 0 <= nr < 15 and 0 <= nc < 15 and board[nr, nc] == player:
                        count += 1
                        nr += dr
                        nc += dc
                    if count >= 5:
                        return player
    return 0


def check_fatal_threat(board):
    directions = [(0, 1), (1, 0), (1, 1), (1, -1)]
    for r in range(15):
        for c in range(15):
            player = board[r, c]
            if player != 0:
                for dr, dc in directions:
                    count = 1
                    nr, nc = r + dr, c + dc
                    while 0 <= nr < 15 and 0 <= nc < 15 and board[nr, nc] == player:
                        count += 1
                        nr += dr
                        nc += dc
                    if count == 4:
                        before_r, before_c = r - dr, c - dc
                        after_r, after_c = nr, nc
                        if (0 <= before_r < 15 and 0 <= before_c < 15 and board[before_r, before_c] == 0) and \
                                (0 <= after_r < 15 and 0 <= after_c < 15 and board[after_r, after_c] == 0):
                            return player
    return 0


def generate_checkmate_taunt(is_human_threat, model_name="qwen2.5:7b"):
    if is_human_threat:
        prompt = "你是一个狂妄的五子棋AI，人类刚刚走出了'活四'（必赢棋型）。你即将输掉比赛，请用15个字以内找个极其荒谬的借口，死不承认自己被看穿。"
    else:
        prompt = "你是一个狂妄的五子棋AI，你刚刚走出了'活四'（必赢棋型）。请用15个字以内极其嚣张地让对方立刻投降。"

    url = "http://127.0.0.1:11434/api/generate"
    payload = {"model": model_name, "prompt": prompt, "stream": False}
    try:
        response = requests.post(url, json=payload, timeout=5)
        if response.status_code == 200:
            return response.json().get("response", "").strip()
    except:
        pass
    return "算你狠，我的主板刚刚进水了！" if is_human_threat else "放弃挣扎吧，你已经是一具尸体了！"


def generate_taunt(human_pos, ai_pos, model_name="qwen2.5:7b"):
    system_prompt = (
        "你是一个五子棋绝顶高手，性格狂妄、毒舌。你正在和人类下棋。"
        "任务：根据人类和你的落子，用一句话（15字以内）狠狠地嘲讽人类的棋技。"
        "语气要极度嚣张，像武侠小说里的反派大魔王，充满压迫感。"
    )
    user_prompt = f"人类下在了 {human_pos}，我极其轻蔑地下在了 {ai_pos}。请对人类发出一句无情的嘲讽："

    url = "http://127.0.0.1:11434/api/generate"
    payload = {"model": model_name, "prompt": f"{system_prompt}\n{user_prompt}", "stream": False}

    try:
        response = requests.post(url, json=payload, timeout=5)
        if response.status_code == 200:
            return response.json().get("response", "").strip()
    except:
        pass
    return "哼，破绽百出，你也配跟我对弈？"


def generate_endgame_taunt(is_human_win, model_name="qwen2.5:7b"):
    if is_human_win:
        prompt = "你是一个狂妄的五子棋AI，但你刚刚输给了人类。请用15个字以内找一个极其荒谬、死鸭子嘴硬的借口，绝对不承认是自己智商低。"
    else:
        prompt = "你是一个狂妄的五子棋AI，你刚刚彻底碾压了人类。请用15个字以内发表一句极度嚣张、充满压迫感的终极胜利宣言。"

    url = "http://127.0.0.1:11434/api/generate"
    payload = {"model": model_name, "prompt": prompt, "stream": False}
    try:
        response = requests.post(url, json=payload, timeout=5)
        if response.status_code == 200:
            return response.json().get("response", "").strip()
    except:
        pass
    return "哼，这次算你走运，我的 CPU 刚才打了个喷嚏！" if is_human_win else "蝼蚁也敢与皓月争辉？"


# ================== 主程序初始化 ==================
cap = cv2.VideoCapture(0)

if not cap.isOpened():
    print("无法打开摄像头！")
    exit()

print("==== 赛博五子棋大师已启动 ====")
print("按下 'q' 键退出")

last_black_count = 0
target_count = 0
stable_frames = 0
ai_planned_move = None
is_initialized = False
game_over = False
fatal_warned = False

# ✅ 修复3：新增上一帧棋盘快照，用于精准找到本轮新落的黑子
prev_board_state = np.zeros((15, 15), dtype=int)

# ✅ 新增：触发标志位，防止 stable_frames 持续累加导致重复触发
just_triggered = False

lower_black = np.array([0, 0, 0])
upper_black = np.array([180, 255, 60])
lower_white = np.array([0, 0, 200])
upper_white = np.array([180, 40, 255])
threshold_ratio = 0.4

while True:
    ret, frame = cap.read()
    if not ret:
        break

    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    blurred = cv2.GaussianBlur(gray, (5, 5), 0)
    edges = cv2.Canny(blurred, 50, 150)
    contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    if contours:
        largest_contour = max(contours, key=cv2.contourArea)
        epsilon = 0.02 * cv2.arcLength(largest_contour, True)
        approx = cv2.approxPolyDP(largest_contour, epsilon, True)

        if len(approx) == 4:
            pts = approx.reshape(4, 2)
            rect = order_points(pts)

            dst = np.array([[0, 0], [599, 0], [599, 599], [0, 599]], dtype="float32")
            M = cv2.getPerspectiveTransform(rect, dst)
            warped = cv2.warpPerspective(frame, M, (600, 600))
            hsv_warped = cv2.cvtColor(warped, cv2.COLOR_BGR2HSV)

            grid_size = 15
            step = 599.0 / (grid_size - 1)
            roi_size = 12

            board_state = np.zeros((15, 15), dtype=int)
            current_black_count = 0

            for row in range(grid_size):
                for col in range(grid_size):
                    x = int(round(col * step))
                    y = int(round(row * step))

                    y_start, y_end = max(0, y - roi_size), min(599, y + roi_size)
                    x_start, x_end = max(0, x - roi_size), min(599, x + roi_size)

                    roi_hsv = hsv_warped[y_start:y_end, x_start:x_end]
                    mask_black = cv2.inRange(roi_hsv, lower_black, upper_black)
                    mask_white = cv2.inRange(roi_hsv, lower_white, upper_white)

                    black_pixel_count = cv2.countNonZero(mask_black)
                    white_pixel_count = cv2.countNonZero(mask_white)
                    total_pixels = (roi_size * 2) ** 2

                    if black_pixel_count / total_pixels > threshold_ratio:
                        board_state[row, col] = 1
                        cv2.circle(warped, (x, y), 8, (0, 0, 0), 3)
                        current_black_count += 1
                    elif white_pixel_count / total_pixels > threshold_ratio:
                        board_state[row, col] = 2
                        cv2.circle(warped, (x, y), 8, (255, 255, 255), 3)
                    else:
                        board_state[row, col] = 0
                        cv2.circle(warped, (x, y), 1, (255, 0, 0), -1)

            # ==========================================
            # 🧠 终极大脑：防抖、裁判与反击逻辑
            # ==========================================
            if not game_over:

                # ✅ 修复1：画面变化时重置计数器和触发标志
                if current_black_count != target_count:
                    target_count = current_black_count
                    stable_frames = 1
                    just_triggered = False   # 画面变了，下次稳定时允许重新触发
                else:
                    stable_frames += 1

                # ✅ 修复2：用 >= 30 且 just_triggered=False 来防止重复触发
                # 只要画面稳定超过30帧，且本轮还没触发过，就执行一次判定
                if stable_frames >= 30 and not just_triggered:
                    just_triggered = True   # 立刻锁上，本轮画面稳定期内只触发一次

                    if not is_initialized:
                        last_black_count = target_count
                        is_initialized = True
                        prev_board_state = board_state.copy()
                        print(f"\n[视觉系统] 🛡️ 棋盘初始化锁定！当前黑棋: {last_black_count} 颗。请人类落子...")

                    else:
                        print("==============")
                        winner = check_winner(board_state)
                        if winner != 0:
                            game_over = True
                            ai_planned_move = None
                            print("\n" + "=" * 40)
                            if winner == 1:
                                print("🎉 比赛结束！人类连成5子，完成绝杀！")
                                taunt = generate_endgame_taunt(is_human_win=True)
                                print(f"🤖 AI 破防遗言: {taunt}")
                                speak_taunt(taunt)
                            elif winner == 2:
                                print("💀 比赛结束！AI 连成5子，人类被无情碾压！")
                                taunt = generate_endgame_taunt(is_human_win=False)
                                print(f"🤖 AI 胜利宣言: {taunt}")
                                speak_taunt(taunt)
                            print("=" * 40)

                        elif target_count == last_black_count + 1:
                            print(f"\n[视觉系统] 🎯 确认人类有效落子！当前黑子总数: {target_count}")

                            # ✅ 修复3：用棋盘差异精准找到本轮新落的黑子位置
                            human_latest_move = None
                            new_stones = []
                            for r in range(15):
                                for c in range(15):
                                    if board_state[r, c] == 1 and prev_board_state[r, c] == 0:
                                        new_stones.append((r, c))
                            if len(new_stones) == 1:
                                human_latest_move = new_stones[0]
                            elif len(new_stones) > 1:
                                # 多个差异点时取最后一个（兜底策略）
                                human_latest_move = new_stones[-1]

                            # 更新基准线和快照
                            last_black_count = target_count
                            prev_board_state = board_state.copy()

                            # AI 算棋 + 嘲讽
                            ai_planned_move = get_best_move(board_state)

                            cv2.putText(warped, "AI THINKING...", (120, 300), cv2.FONT_HERSHEY_DUPLEX, 1.5,
                                        (0, 0, 255), 3)
                            cv2.imshow("Cyber Gomoku Master", warped)
                            cv2.waitKey(1)

                            print("[大模型] 正在酝酿无情的垃圾话...")
                            taunt = generate_taunt(human_latest_move, ai_planned_move)

                            print("-" * 40)
                            print(f"♟️ 电脑绝对理性落子: {ai_planned_move}")
                            print(f"🤖 嘲讽: {taunt}")
                            speak_taunt(taunt)
                            print("-" * 40)

                        elif target_count > last_black_count + 1:
                            print(f"\n[视觉系统] ⚠️ 忽略视觉干扰 (疑似手影遮挡，黑子变化 +{target_count - last_black_count})。")

                        elif target_count == last_black_count:
                            # 黑子数量没变，画面稳定，不做任何处理（等待人类落子）
                            pass

            # ==========================================
            # 🎯 绘制 AI 的红色十字瞄准星
            # ==========================================
            if ai_planned_move is not None:
                ai_r, ai_c = ai_planned_move
                ai_x = int(round(ai_c * step))
                ai_y = int(round(ai_r * step))
                cv2.circle(warped, (ai_x, ai_y), 14, (0, 0, 255), 2)
                cv2.line(warped, (ai_x - 10, ai_y), (ai_x + 10, ai_y), (0, 0, 255), 2)
                cv2.line(warped, (ai_x, ai_y - 10), (ai_x, ai_y + 10), (0, 0, 255), 2)
                cv2.putText(warped, "AI", (ai_x + 15, ai_y - 15), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)

            cv2.imshow("Cyber Gomoku Master", warped)

    if cv2.waitKey(1) == ord('q'):
        break

cap.release()
cv2.destroyAllWindows()