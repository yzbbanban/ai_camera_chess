import cv2
import numpy as np
import requests
import os
import threading
import subprocess
import sys

# 强制直连
os.environ['NO_PROXY'] = 'localhost,127.0.0.1,::1'

# ==========================================
# 🔊 异步后台发声器官 (Edge-TTS)
# ==========================================
def play_edge_tts_thread(text):
    try:
        # 已为你替换为云希（傲娇青年音），嘲讽效果绝佳
        voice = "zh-CN-YunxiNeural"
        output_file = "current_taunt.mp3"
        subprocess.run([
            sys.executable, '-m', 'edge_tts',
            '--voice', voice, '--rate=+15%', '--text', text, '--write-media', output_file
        ], check=True)
        subprocess.run(['afplay', output_file])
    except Exception as e:
        print(f"⚠️ 语音播报异常: {e}")

def speak_taunt(text):
    threading.Thread(target=play_edge_tts_thread, args=(text,), daemon=True).start()

# ==========================================
# 👁️ 视觉与几何底座
# ==========================================
def order_points(pts):
    rect = np.zeros((4, 2), dtype="float32")
    s = pts.sum(axis=1)
    rect[0] = pts[np.argmin(s)]
    rect[2] = pts[np.argmax(s)]
    diff = np.diff(pts, axis=1)
    rect[1] = pts[np.argmin(diff)]
    rect[3] = pts[np.argmax(diff)]
    return rect

# ==========================================
# 🧠 传统小脑：算力引擎与鹰眼
# ==========================================
def evaluate_line(board, r, c, dr, dc, player):
    count = 1
    i, j = r + dr, c + dc
    space1 = 0
    while 0 <= i < 15 and 0 <= j < 15:
        if board[i, j] == player: count += 1
        elif board[i, j] == 0: space1 = 1; break
        else: break
        i, j = i + dr, j + dc
    i, j = r - dr, c - dc
    space2 = 0
    while 0 <= i < 15 and 0 <= j < 15:
        if board[i, j] == player: count += 1
        elif board[i, j] == 0: space2 = 1; break
        else: break
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
                    if count >= 5: return player
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

# ==========================================
# 🗣️ 嘴替大脑：Qwen 生成引擎
# ==========================================
def call_ollama(prompt, model_name="qwen2.5:7b", fallback="哼。"):
    url = "http://127.0.0.1:11434/api/generate"
    try:
        response = requests.post(url, json={"model": model_name, "prompt": prompt, "stream": False}, timeout=5)
        if response.status_code == 200: return response.json().get("response", "").strip()
    except:
        pass
    return fallback

def generate_taunt(human_pos, ai_pos):
    return call_ollama(f"你是一个毒舌五子棋AI。人类下在{human_pos}，我极其轻蔑地下在{ai_pos}。请用15字以内嘲讽：", fallback="破绽百出！")

def generate_checkmate_taunt(is_human_threat):
    if is_human_threat: return call_ollama("人类刚走出必赢活四，请用15字以内找个极其荒谬的借口死不认输。", fallback="肯定是风把棋子吹跑了！")
    else: return call_ollama("你刚走出必赢活四。请用15字以内发表极其嚣张的宣告。", fallback="放弃挣扎吧！")

def generate_endgame_taunt(is_human_win):
    if is_human_win: return call_ollama("你彻底输给了人类。用15字找破防借口。", fallback="我的CPU刚才打喷嚏了！")
    else: return call_ollama("你连成5子碾压了人类。发表终极胜利宣言。", fallback="蝼蚁也敢与皓月争辉？")

# ================== 主程序启动 ==================
cap = cv2.VideoCapture(0)
print("==== 赛博五子棋大师已启动 ====")

lower_black, upper_black = np.array([0, 0, 0]), np.array([180, 255, 60])
lower_white, upper_white = np.array([0, 0, 200]), np.array([180, 40, 255])

target_black = 0
target_white = 0
stable_frames = 0
ai_planned_move = None
game_over = False
fatal_warned = False

# 🚀 核心修复：用于存储棋盘坐标的记忆矩阵
last_valid_M = None

while True:
    ret, frame = cap.read()
    if not ret: break

    # --- 0. 棋盘轮廓提取与矩阵记忆 ---
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    blurred = cv2.GaussianBlur(gray, (5, 5), 0)
    edges = cv2.Canny(blurred, 50, 150)
    contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    if contours:
        largest_contour = max(contours, key=cv2.contourArea)
        # 确保它足够大，排除小杂物干扰
        if cv2.contourArea(largest_contour) > 20000:
            epsilon = 0.02 * cv2.arcLength(largest_contour, True)
            approx = cv2.approxPolyDP(largest_contour, epsilon, True)
            # 只有识别到完美四边形时，才更新记忆矩阵
            if len(approx) == 4:
                pts = approx.reshape(4, 2)
                rect = order_points(pts)
                last_valid_M = cv2.getPerspectiveTransform(rect, np.array([[0, 0], [599, 0], [599, 599], [0, 599]], dtype="float32"))

    # 如果刚开机还没找到棋盘，直接显示原始画面并提示
    if last_valid_M is None:
        cv2.putText(frame, "Looking for Gomoku Board...", (50, 50), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 2)
        cv2.imshow("Cyber Gomoku Master", frame)
        if cv2.waitKey(1) == ord('q'): break
        continue

    # --- 1. 使用“记忆矩阵”裁剪棋盘 (即使手挡住边缘也绝不闪烁) ---
    warped = cv2.warpPerspective(frame, last_valid_M, (600, 600))
    hsv_warped = cv2.cvtColor(warped, cv2.COLOR_BGR2HSV)

    step = 599.0 / 14
    board_state = np.zeros((15, 15), dtype=int)
    current_black = 0
    current_white = 0
    human_latest_move = None

    # --- 2. 双色精准视觉 ---
    for row in range(15):
        for col in range(15):
            x, y = int(round(col * step)), int(round(row * step))
            y_s, y_e = max(0, y - 12), min(599, y + 12)
            x_s, x_e = max(0, x - 12), min(599, x + 12)
            roi = hsv_warped[y_s:y_e, x_s:x_e]

            if cv2.countNonZero(cv2.inRange(roi, lower_black, upper_black)) / 576 > 0.4:
                board_state[row, col] = 1
                cv2.circle(warped, (x, y), 8, (0, 0, 0), 3)
                current_black += 1
                human_latest_move = (row, col)
            elif cv2.countNonZero(cv2.inRange(roi, lower_white, upper_white)) / 576 > 0.4:
                board_state[row, col] = 2
                cv2.circle(warped, (x, y), 8, (255, 255, 255), 3)
                current_white += 1
            else:
                cv2.circle(warped, (x, y), 1, (255, 0, 0), -1)

    # --- 3. 绝对物理真理大脑 ---
    if not game_over:
        if current_black != target_black or current_white != target_white:
            target_black = current_black
            target_white = current_white
            stable_frames = 1
        else:
            stable_frames += 1

        if stable_frames == 15:
            winner = check_winner(board_state)
            if winner != 0:
                game_over = True
                ai_planned_move = None
                taunt = generate_endgame_taunt(winner == 1)
                print(f"\n🎉 比赛结束！\n🤖 AI: {taunt}")
                speak_taunt(taunt)
            else:
                if not fatal_warned:
                    threat = check_fatal_threat(board_state)
                    if threat != 0:
                        fatal_warned = True
                        taunt = generate_checkmate_taunt(threat == 1)
                        print(f"\n🚨 活四预警！\n🤖 AI: {taunt}")
                        speak_taunt(taunt)
                        cv2.putText(warped, "CHECKMATE!", (150, 250), cv2.FONT_HERSHEY_DUPLEX, 1.5, (0, 0, 255), 3)
                        temp_disp = cv2.copyMakeBorder(warped, 0, 60, 0, 0, cv2.BORDER_CONSTANT, value=(30, 30, 30))
                        cv2.imshow("Cyber Gomoku Master", temp_disp)
                        cv2.waitKey(1)

                if target_black == target_white:
                    if ai_planned_move is not None:
                        print(f"\n[系统] ✅ 确认白棋落子！红圈清除。")
                        ai_planned_move = None

                elif target_black == target_white + 1:
                    if ai_planned_move is None:
                        print(f"\n[系统] 🎯 检测到黑棋！AI开始思考...")

                        cv2.putText(warped, "AI THINKING...", (120, 300), cv2.FONT_HERSHEY_DUPLEX, 1.5, (0, 0, 255), 3)
                        temp_disp = cv2.copyMakeBorder(warped, 0, 60, 0, 0, cv2.BORDER_CONSTANT, value=(30, 30, 30))
                        cv2.imshow("Cyber Gomoku Master", temp_disp)
                        cv2.waitKey(1)

                        ai_planned_move = get_best_move(board_state)
                        taunt = generate_taunt(human_latest_move, ai_planned_move)
                        print(f"♟️ AI指令: 将白棋放在 {ai_planned_move}\n🤖: {taunt}")
                        speak_taunt(taunt)

    # --- 4. UI 渲染 ---
    if ai_planned_move is not None:
        ai_r, ai_c = ai_planned_move
        ai_x, ai_y = int(round(ai_c * step)), int(round(ai_r * step))
        cv2.circle(warped, (ai_x, ai_y), 14, (0, 0, 255), 2)
        cv2.line(warped, (ai_x - 10, ai_y), (ai_x + 10, ai_y), (0, 0, 255), 2)
        cv2.line(warped, (ai_x, ai_y - 10), (ai_x, ai_y + 10), (0, 0, 255), 2)
        cv2.putText(warped, "PLACE WHITE", (ai_x + 15, ai_y - 15), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 255), 2)

    # 扩展底栏：完美显示仪表盘
    display_img = cv2.copyMakeBorder(warped, 0, 60, 0, 0, cv2.BORDER_CONSTANT, value=(30, 30, 30))

    if target_black == target_white:
        cv2.putText(display_img, "YOUR TURN: Place Black", (15, 635), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)
    elif target_black == target_white + 1:
        cv2.putText(display_img, "AI TURN: Place White", (15, 635), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 165, 255), 2)
    else:
        cv2.putText(display_img, "ERROR: Pieces Mismatch!", (15, 635), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 255), 2)

    if stable_frames < 15:
        cv2.putText(display_img, f"Wait... {stable_frames}/15", (420, 635), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 165, 255), 2)
    else:
        cv2.putText(display_img, "READY", (480, 635), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)

    cv2.imshow("Cyber Gomoku Master", display_img)

    if cv2.waitKey(1) == ord('q'): break

cap.release()
cv2.destroyAllWindows()