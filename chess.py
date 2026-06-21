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
        # 晓伊：可爱傲娇的少女音
        voice = "zh-CN-XiaoyiNeural"
        output_file = "current_taunt.mp3"

        # 强制清空缓存防幽灵音
        if os.path.exists(output_file):
            os.remove(output_file)

        subprocess.run([
            sys.executable, '-m', 'edge_tts',
            '--voice', voice,
            '--rate=+5%',
            '--pitch=+10Hz',
            '--text', text,
            '--write-media', output_file
        ], check=True)

        if os.path.exists(output_file):
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
        if board[i, j] == player:
            count += 1
        elif board[i, j] == 0:
            space1 = 1; break
        else:
            break
        i, j = i + dr, j + dc
    i, j = r - dr, c - dc
    space2 = 0
    while 0 <= i < 15 and 0 <= j < 15:
        if board[i, j] == player:
            count += 1
        elif board[i, j] == 0:
            space2 = 1; break
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

    # ==========================================
    # 🗡️ 第一段：自己能连成 5 子，瞬间绝杀！
    # ==========================================
    for r in range(15):
        for c in range(15):
            if board_state[r, c] == 0:
                for dr, dc in directions:
                    if evaluate_line(board_state, r, c, dr, dc, 2) >= 100000:
                        return (r, c)

    # ==========================================
    # 🛡️ 第二段：人类能连成 5 子，必须死堵！
    # ==========================================
    for r in range(15):
        for c in range(15):
            if board_state[r, c] == 0:
                for dr, dc in directions:
                    if evaluate_line(board_state, r, c, dr, dc, 1) >= 100000:
                        return (r, c)

    # ==========================================
    # 🗡️ 第三段：自己能造出“活四”，下回合必赢，果断进攻！(修复的就是这里)
    # ==========================================
    for r in range(15):
        for c in range(15):
            if board_state[r, c] == 0:
                for dr, dc in directions:
                    if evaluate_line(board_state, r, c, dr, dc, 2) >= 10000:
                        return (r, c)

    # ==========================================
    # 🛡️ 第四段：人类能造出“活四”，死堵！
    # ==========================================
    for r in range(15):
        for c in range(15):
            if board_state[r, c] == 0:
                for dr, dc in directions:
                    if evaluate_line(board_state, r, c, dr, dc, 1) >= 10000:
                        return (r, c)

    # ==========================================
    # ⚖️ 第五段：常规算分拉扯
    # ==========================================
    for r in range(15):
        for c in range(15):
            if board_state[r, c] == 0:
                score = 0
                for dr, dc in directions:
                    # 进攻与防守权重回归理性
                    score += evaluate_line(board_state, r, c, dr, dc, 2) * 1.0
                    score += evaluate_line(board_state, r, c, dr, dc, 1) * 1.2

                # 偏好棋盘中心
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
    return call_ollama(
        f"你是一个傲娇、毒舌的五子棋AI少女。人类下在{human_pos}，我极其轻蔑地下在{ai_pos}。请用15字以内嘲讽：",
        fallback="破绽百出，大笨蛋！")


def generate_checkmate_taunt(is_human_threat):
    if is_human_threat:
        return call_ollama("你是一个傲娇的五子棋少女，人类刚走出必赢活四，请用15字以内找个极其荒谬的借口死不认输。",
                           fallback="不公平，肯定是风把棋子吹跑了！")
    else:
        return call_ollama("你是一个傲娇的五子棋少女，你刚走出必赢活四。请用15字以内发表极其嚣张的宣告。",
                           fallback="放弃挣扎吧，本小姐赢定了！")


def generate_endgame_taunt(is_human_win):
    if is_human_win:
        return call_ollama("你是一个傲娇的五子棋少女，你彻底输给了人类。用15字找极其傲娇的破防借口。",
                           fallback="哼，这次只是本小姐让你而已！")
    else:
        return call_ollama("你是一个傲娇的五子棋少女，你连成5子碾压了人类。发表终极胜利宣言。",
                           fallback="这就是惹怒本小姐的下场！")

# ==========================================
# 📍 核心新增：AI落点校验拦截器
# ==========================================
def check_pos(detected_pos, target_pos, error_voice_played):
    """
    校验物理落子是否与系统期望位置一致
    """
    if detected_pos is None or target_pos is None:
        return False, error_voice_played

    if detected_pos != target_pos:
        print(f"❌ 警告：识别落点 {detected_pos} 与目标 {target_pos} 不符！")
        if not error_voice_played:
            error_text = "喂！你是不是眼花啦？我让你下在红圈那里，你放哪去了！赶紧给我拿开重新放！"
            print(f"🤖 少女AI: {error_text}")
            speak_taunt(error_text)
        return False, True
    else:
        print("✅ 确认落子位置完全一致！")
        return True, False

# ==========================================
# 🖱️ 核心新增：动态拾色器 (鼠标回调状态机)
# ==========================================
def mouse_callback(event, x, y, flags, param):
    global calibration_mode, lower_black, upper_black, lower_white, upper_white, hsv_frame_for_picker

    # 只响应左键按下，并且处于校准模式，同时确保点击在棋盘有效区域内(600x600)
    if event == cv2.EVENT_LBUTTONDOWN and calibration_mode > 0:
        if hsv_frame_for_picker is not None and y < 600 and x < 600:
            h, s, v = hsv_frame_for_picker[y, x]
            print(f"[*] 鼠标拾取像素 HSV: ({h}, {s}, {v})")

            if calibration_mode == 1:
                # 智能黑棋阈值推算：黑棋核心特征是“亮度低(V小)”，色相H和饱和度S可放宽
                lower_black = np.array([0, 0, 0])
                upper_black = np.array([180, 255, min(255, int(v + 40))])
                print(f"✅ 黑棋阈值更新: {lower_black} -> {upper_black}")

                calibration_mode = 2
                speak_taunt("黑棋记住了。现在请在画面上点击一颗白棋！")

            elif calibration_mode == 2:
                # 智能白棋阈值推算：白棋核心特征是“亮度高(V大)，饱和度低(S小)”
                lower_white = np.array([0, 0, max(0, int(v - 40))])
                upper_white = np.array([180, min(255, int(s + 40)), 255])
                print(f"✅ 白棋阈值更新: {lower_white} -> {upper_white}")

                calibration_mode = 0
                speak_taunt("色彩校准完成，本小姐的眼睛现在可是雪亮的！")

# ================== 主程序启动 ==================
cap = cv2.VideoCapture(0)
print("==== 赛博五子棋少女 已启动 ====")

# 🚀 核心新增：提前创建窗口，并绑定鼠标回调钩子
cv2.namedWindow("Cyber Gomoku Master")
cv2.setMouseCallback("Cyber Gomoku Master", mouse_callback)

lower_black, upper_black = np.array([0, 0, 0]), np.array([180, 255, 60])
lower_white, upper_white = np.array([0, 0, 200]), np.array([180, 40, 255])

target_black = 0
target_white = 0
stable_frames = 0
ai_planned_move = None
game_over = False
fatal_warned = False
last_valid_M = None
winner = 0

# 新增的状态记忆变量
last_calculated_board = None
error_voice_played = False
calibration_mode = 0         # 🚀 0: 关闭, 1: 采黑棋, 2: 采白棋
hsv_frame_for_picker = None  # 🚀 用于存储当前帧的 HSV 图像供鼠标回调读取

while True:
    ret, frame = cap.read()
    if not ret: break

    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    blurred = cv2.GaussianBlur(gray, (5, 5), 0)
    edges = cv2.Canny(blurred, 50, 150)
    contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    if contours:
        largest_contour = max(contours, key=cv2.contourArea)
        if cv2.contourArea(largest_contour) > 20000:
            epsilon = 0.02 * cv2.arcLength(largest_contour, True)
            approx = cv2.approxPolyDP(largest_contour, epsilon, True)
            if len(approx) == 4:
                pts = approx.reshape(4, 2)
                rect = order_points(pts)
                last_valid_M = cv2.getPerspectiveTransform(rect, np.array([[0, 0], [599, 0], [599, 599], [0, 599]],
                                                                          dtype="float32"))

    if last_valid_M is None:
        cv2.putText(frame, "Looking for Gomoku Board...", (50, 50), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 2)
        cv2.imshow("Cyber Gomoku Master", frame)
        if cv2.waitKey(1) == ord('q'): break
        continue

    warped = cv2.warpPerspective(frame, last_valid_M, (600, 600))
    hsv_warped = cv2.cvtColor(warped, cv2.COLOR_BGR2HSV)

    # 🚀 核心新增：实时更新供拾色器读取的 HSV 画面
    hsv_frame_for_picker = hsv_warped.copy()

    step = 599.0 / 14
    board_state = np.zeros((15, 15), dtype=int)
    current_black = 0
    current_white = 0
    human_latest_move = None

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

    # 🚀 核心修改：增加对 calibration_mode 的冻结判定。校准时大脑暂停思考！
    if not game_over and calibration_mode == 0:
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
                print(f"\n🎉 比赛结束！\n🤖 少女AI: {taunt}")
                speak_taunt(taunt)
            else:
                if not fatal_warned:
                    threat = check_fatal_threat(board_state)
                    if threat != 0:
                        fatal_warned = True
                        taunt = generate_checkmate_taunt(threat == 1)
                        print(f"\n🚨 活四预警！\n🤖 少女AI: {taunt}")
                        speak_taunt(taunt)
                        cv2.putText(warped, "CHECKMATE!", (150, 250), cv2.FONT_HERSHEY_DUPLEX, 1.5, (0, 0, 255), 3)
                        temp_disp = cv2.copyMakeBorder(warped, 0, 60, 0, 0, cv2.BORDER_CONSTANT, value=(30, 30, 30))
                        cv2.imshow("Cyber Gomoku Master", temp_disp)
                        cv2.waitKey(1)

                # ==========================================
                # 🚀 新增：拦截与重算逻辑
                # ==========================================
                if target_black == target_white:
                    if ai_planned_move is not None:
                        # 寻找新放下的白子坐标
                        new_white_pos = None
                        if last_calculated_board is not None:
                            diff = board_state - last_calculated_board
                            new_y, new_x = np.where(diff == 2)
                            if len(new_y) > 0:
                                new_white_pos = (new_y[0], new_x[0])

                        # 校验刚才下的这颗白棋是不是目标位置
                        if new_white_pos is not None:
                            is_valid, error_voice_played = check_pos(new_white_pos, ai_planned_move, error_voice_played)

                            if not is_valid:
                                # 🛑 拦截生效！把计分板退回去，假装没看见这颗错的棋子
                                target_white -= 1
                                stable_frames = 0
                                continue  # 跳过本帧后续处理

                        # 下对了，放行
                        print(f"\n[系统] ✅ 确认白棋落子！红圈清除。")
                        ai_planned_move = None
                        last_calculated_board = None  # 顺手把记忆也清了

                elif target_black == target_white + 1:
                    # 🚀 绝对防卡死：只要当前棋盘跟上次算出的不一样，强制重算！
                    if ai_planned_move is None or last_calculated_board is None or not np.array_equal(board_state,
                                                                                                      last_calculated_board):
                        print(f"\n[系统] 🎯 检测到全新盘面！AI开始思考...")

                        cv2.putText(warped, "AI THINKING...", (120, 300), cv2.FONT_HERSHEY_DUPLEX, 1.5, (0, 0, 255), 3)
                        temp_disp = cv2.copyMakeBorder(warped, 0, 60, 0, 0, cv2.BORDER_CONSTANT, value=(30, 30, 30))
                        cv2.imshow("Cyber Gomoku Master", temp_disp)
                        cv2.waitKey(1)

                        ai_planned_move = get_best_move(board_state)
                        last_calculated_board = board_state.copy()  # 死死记住这个盘面

                        taunt = generate_taunt(human_latest_move, ai_planned_move)
                        print(f"♟️ AI指令: 将白棋放在 {ai_planned_move}\n🤖: {taunt}")
                        speak_taunt(taunt)

    if ai_planned_move is not None:
        ai_r, ai_c = ai_planned_move
        ai_x, ai_y = int(round(ai_c * step)), int(round(ai_r * step))
        cv2.circle(warped, (ai_x, ai_y), 14, (0, 0, 255), 2)
        cv2.line(warped, (ai_x - 10, ai_y), (ai_x + 10, ai_y), (0, 0, 255), 2)
        cv2.line(warped, (ai_x, ai_y - 10), (ai_x, ai_y + 10), (0, 0, 255), 2)
        cv2.putText(warped, "PLACE WHITE", (ai_x + 15, ai_y - 15), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 255), 2)

    # ==========================================
    # 🖥️ 扩展底栏：完美显示仪表盘，绝不遮挡棋盘！
    # ==========================================
    display_img = cv2.copyMakeBorder(warped, 0, 60, 0, 0, cv2.BORDER_CONSTANT, value=(30, 30, 30))

    # 🚀 已修复：整合 UI 拦截，确保在同一坐标上只有一条判定生效
    if calibration_mode == 1:
        cv2.putText(display_img, "CALIBRATION: Click a BLACK stone", (15, 635), cv2.FONT_HERSHEY_DUPLEX, 0.7,
                    (0, 255, 255), 2)
    elif calibration_mode == 2:
        cv2.putText(display_img, "CALIBRATION: Click a WHITE stone", (15, 635), cv2.FONT_HERSHEY_DUPLEX, 0.7,
                    (0, 255, 255), 2)
    elif game_over:
        if winner == 2:
            cv2.putText(display_img, "GAME OVER! AI WINS!", (15, 635), cv2.FONT_HERSHEY_DUPLEX, 0.7, (0, 0, 255), 2)
        elif winner == 1:
            cv2.putText(display_img, "GAME OVER! YOU WIN!", (15, 635), cv2.FONT_HERSHEY_DUPLEX, 0.7, (0, 255, 0), 2)
        else:
            cv2.putText(display_img, "GAME OVER! DRAW!", (15, 635), cv2.FONT_HERSHEY_DUPLEX, 0.7, (0, 255, 255), 2)
    else:
        if target_black == target_white:
            cv2.putText(display_img, "YOUR TURN: Place Black", (15, 635), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)
        elif target_black == target_white + 1:
            cv2.putText(display_img, "AI TURN: Place White", (15, 635), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 165, 255), 2)
        else:
            cv2.putText(display_img, "ERROR: Pieces Mismatch!", (15, 635), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 255),
                        2)

    # 右下角的状态提示也同步修补
    if game_over:
        cv2.putText(display_img, "FINISHED", (480, 635), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)
    elif calibration_mode > 0:
        cv2.putText(display_img, "LOCKED", (480, 635), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 255), 2)
    elif stable_frames < 15:
        cv2.putText(display_img, f"Wait... {stable_frames}/15", (420, 635), cv2.FONT_HERSHEY_SIMPLEX, 0.6,
                    (0, 165, 255), 2)
    else:
        cv2.putText(display_img, "READY", (480, 635), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)

    cv2.imshow("Cyber Gomoku Master", display_img)

    key = cv2.waitKey(1) & 0xFF
    if key == ord('q'):
        break
    elif key == ord('r'):
        print("=== 🔄 收到重置指令，棋局已重置！ ===")
        restart_text = "哼，这就急着重新开始啦？本小姐就大发慈悲再给你一次机会，准备好再被我虐一次了吗？"
        print(f"🤖 少女AI: {restart_text}")
        speak_taunt(restart_text)

        game_over = False
        winner = 0
        board_state = np.zeros((15, 15), dtype=int)

        last_calculated_board = None
        ai_planned_move = None
        error_voice_played = False
    # 🚀 核心新增：按 'c' 键触发拾色器
    elif key == ord('c'):
        print("=== 🖱️ 进入色彩校准模式 ===")
        calibration_mode = 1
        calibration_text = "想要帮我矫正视力吗？请用鼠标在画面上点击一颗黑棋。"
        print(f"🤖 少女AI: {calibration_text}")
        speak_taunt(calibration_text)

cap.release()
cv2.destroyAllWindows()