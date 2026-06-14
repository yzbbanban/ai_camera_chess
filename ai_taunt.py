import cv2
import numpy as np
import requests
import os
import threading
import subprocess  # ⬅️ 新增：用于调用系统语音引擎
import sys

# 强制直连，绕过系统网络代理，防止请求 Ollama 失败
os.environ['NO_PROXY'] = 'localhost,127.0.0.1,::1'


def play_edge_tts_thread(text):
    """真正在后台执行合成和播放的任务"""
    try:
        voice = "zh-CN-XiaoyiNeural"
        output_file = "current_taunt.mp3"

        # 1. 核心修复：用 sys.executable 和 -m 直接从当前 Python 环境里揪出 edge_tts 模块！
        # 注意模块名是下划线 edge_tts
        subprocess.run([
            sys.executable, '-m', 'edge_tts',
            '--voice', voice,
            '--rate=+15%',
            '--text', text,
            '--write-media', output_file
        ], check=True)

        # 2. 调用 macOS 原生播放器后台播放
        subprocess.run(['afplay', output_file])

    except Exception as e:
        print(f"⚠️ edge-tts 播报异常: {e}")


def speak_taunt(text):
    """
    异步触发器：每次被调用时，开一个新的幽灵线程去执行语音。
    主程序（OpenCV画面）不需要等它说完，直接继续往下跑。
    """
    # daemon=True 保证如果你关掉主程序，语音也会立刻跟着停掉，不会变成幽灵声音
    threading.Thread(target=play_edge_tts_thread, args=(text,), daemon=True).start()

def order_points(pts):
    """辅助函数：将识别到的棋盘四个顶点按【左上, 右上, 右下, 左下】顺序排列"""
    rect = np.zeros((4, 2), dtype="float32")
    s = pts.sum(axis=1)
    rect[0] = pts[np.argmin(s)]
    rect[2] = pts[np.argmax(s)]
    diff = np.diff(pts, axis=1)
    rect[1] = pts[np.argmin(diff)]
    rect[3] = pts[np.argmax(diff)]
    return rect


# ==========================================
# 🧠 传统小脑：无视空间路痴，硬核计算五子棋得分
# ==========================================
def evaluate_line(board, r, c, dr, dc, player):
    """评估某个方向上的连续棋子得分"""
    count = 1
    # 正向扫描
    i, j = r + dr, c + dc
    space1 = 0
    while 0 <= i < 15 and 0 <= j < 15:
        if board[i, j] == player:
            count += 1
        elif board[i, j] == 0:
            space1 = 1;
            break
        else:
            break
        i, j = i + dr, j + dc

    # 反向扫描
    i, j = r - dr, c - dc
    space2 = 0
    while 0 <= i < 15 and 0 <= j < 15:
        if board[i, j] == player:
            count += 1
        elif board[i, j] == 0:
            space2 = 1;
            break
        else:
            break
        i, j = i - dr, j - dc

    spaces = space1 + space2
    if count >= 5: return 100000  # 连五必赢
    if count == 4 and spaces == 2: return 10000  # 活四必赢/必挡
    if count == 4 and spaces == 1: return 1000  # 冲四
    if count == 3 and spaces == 2: return 1000  # 活三
    if count == 3 and spaces == 1: return 100  # 眠三
    if count == 2 and spaces == 2: return 100  # 活二
    if count == 2 and spaces == 1: return 10  # 眠二
    return 0


def get_best_move(board_state):
    """全盘扫描，找出防守和攻击得分最高的绝对理性落子点"""
    best_score = -1
    best_move = (7, 7)  # 默认起手天元

    # 遍历所有空位寻找最佳落子点
    directions = [(1, 0), (0, 1), (1, 1), (1, -1)]
    for r in range(15):
        for c in range(15):
            if board_state[r, c] == 0:
                score = 0
                for dr, dc in directions:
                    # 进攻得分 (白棋)
                    score += evaluate_line(board_state, r, c, dr, dc, 2) * 1.1
                    # 防守得分 (黑棋，拉高权重，优先死堵人类活三活四)
                    score += evaluate_line(board_state, r, c, dr, dc, 1) * 1.5

                # 增加一点趋中性，让开局显得更自然
                score += (7 - abs(7 - r)) + (7 - abs(7 - c))

                if score > best_score:
                    best_score = score
                    best_move = (r, c)
    return best_move


# ==========================================
# 🏆 裁判系统：全盘胜负判定
# ==========================================
def check_winner(board):
    """扫描全盘，看是否有人连成5子"""
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
                        return player  # 返回 1 (黑赢) 或 2 (白赢)
    return 0


def check_fatal_threat(board):
    """鹰眼扫描：寻找必死棋型（活四：两端皆空的四连子）"""
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
                    # 发现四连子，检查两端是否都没被堵死
                    if count == 4:
                        before_r, before_c = r - dr, c - dc
                        after_r, after_c = nr, nc
                        if (0 <= before_r < 15 and 0 <= before_c < 15 and board[before_r, before_c] == 0) and \
                                (0 <= after_r < 15 and 0 <= after_c < 15 and board[after_r, after_c] == 0):
                            return player  # 返回 1 (黑棋活四) 或 2 (白棋活四)
    return 0


def generate_checkmate_taunt(is_human_threat, model_name="qwen2.5:7b"):
    """大模型专属：绝杀前的提前嘲讽"""
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

# ==========================================
# 🗣️ 嘴替大脑：Qwen 本地大模型调用
# ==========================================
def generate_taunt(human_pos, ai_pos, model_name="qwen2.5:7b"):
    """对局中的实时嘲讽"""
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
    """终局时的胜利宣言或破防借口"""
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

# 核心状态变量锁
last_black_count = 0
target_count = 0
stable_frames = 0
ai_planned_move = None
is_initialized = False
game_over = False
fatal_warned = False    # ⬅️ 新增：赛点预警锁

# 完美打光下的终极 HSV 颜色阈值
lower_black = np.array([0, 0, 0])
upper_black = np.array([180, 255, 60])
lower_white = np.array([0, 0, 200])
upper_white = np.array([180, 40, 255])
threshold_ratio = 0.4

while True:
    ret, frame = cap.read()
    if not ret: break

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
            human_latest_move = None

            # ----------------------------------------
            # 👁️ 100% 精准的黑白双向视觉循环
            # ----------------------------------------
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
                        human_latest_move = (row, col)

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
                if current_black_count != target_count:
                    target_count = current_black_count
                    stable_frames = 1
                else:
                    stable_frames += 1

                # 必须连续 30 帧（约 1~1.5 秒）画面绝对静止，系统才开始判定
                if stable_frames == 30:

                    # 1. 开局防抢跑初始化
                    if not is_initialized:
                        last_black_count = target_count
                        is_initialized = True
                        print(f"\n[视觉系统] 🛡️ 棋盘初始化锁定！当前黑棋: {last_black_count} 颗。请人类落子...")

                    else:
                        print(f"==============")
                        # 2. 裁判吹哨：判定是否绝杀
                        winner = check_winner(board_state)
                        if winner != 0:
                            game_over = True
                            ai_planned_move = None
                            print("\n" + "=" * 40)
                            if winner == 1:
                                print("🎉 比赛结束！人类连成5子，完成绝杀！")
                                taunt = generate_endgame_taunt(is_human_win=True)
                                print(f"🤖 AI 破防遗言: {taunt}")
                                speak_taunt(taunt)  # ⬅️ 插入这一行：气急败坏地狡辩
                            elif winner == 2:
                                print("💀 比赛结束！AI 连成5子，人类被无情碾压！")
                                taunt = generate_endgame_taunt(is_human_win=False)
                                print(f"🤖 AI 胜利宣言: {taunt}")
                                speak_taunt(taunt)  # ⬅️ 插入这一行：嚣张宣判
                            print("=" * 40)

                        # 3. 严格校验：防手影，触发 AI 反击
                        elif target_count > last_black_count:
                            if target_count == last_black_count + 1:
                                print(f"\n[视觉系统] 🎯 确认人类有效落子！当前黑子总数: {target_count}")

                                # 核心修复：更新基准线
                                last_black_count = target_count

                                if human_latest_move:
                                    # 1. 小脑毫秒级算棋
                                    ai_planned_move = get_best_move(board_state)

                                    # ==========================================
                                    # 💡 核心视觉反馈：在画面正中央打出暴走提示，并强制刷新画面
                                    # ==========================================
                                    cv2.putText(warped, "AI THINKING...", (120, 300), cv2.FONT_HERSHEY_DUPLEX, 1.5,
                                                (0, 0, 255), 3)
                                    cv2.imshow("Cyber Gomoku Master", warped)
                                    cv2.waitKey(1)  # ⬅️ 极其关键的一行！强制 OpenCV 立刻把字画出来，再去等大模型

                                    # 2. 大模型秒级生成嘲讽（此时画面定格在 THINKING，压迫感拉满）
                                    print("[大模型] 正在酝酿无情的垃圾话...")
                                    taunt = generate_taunt(human_latest_move, ai_planned_move)

                                    print("-" * 40)
                                    print(f"♟️ 电脑绝对理性落子: {ai_planned_move}")
                                    print(f"🤖 嘲讽: {taunt}")
                                    speak_taunt(taunt)  # ⬅️ 插入这一行：实况播报
                                    print("-" * 40)
                            else:
                                print(f"\n[视觉系统] ⚠️ 忽略视觉干扰 (疑似手影遮挡)。")

                            # 动作结束，手拿开后，同步最新的真实棋盘基准线
                            last_black_count = target_count

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

    if cv2.waitKey(1) == ord('q'): break

cap.release()
cv2.destroyAllWindows()