"""
vision.py —— 摄像头识别

负责"从一帧画面里找到棋盘、识别出每个交叉点是黑棋/白棋/空"，
以及鼠标拾色校准黑白棋的 HSV 阈值。所有识别相关的状态都收在
BoardVision 实例里，不再是裸的全局变量。
"""

import cv2
import numpy as np

from voice import speak_taunt

WARP_SIZE = 600  # 透视校正后的棋盘图像边长（像素）


def order_points(pts):
    """将检测到的棋盘四个角点按 左上/右上/右下/左下 排序。"""
    rect = np.zeros((4, 2), dtype="float32")
    s = pts.sum(axis=1)
    rect[0] = pts[np.argmin(s)]
    rect[2] = pts[np.argmax(s)]
    diff = np.diff(pts, axis=1)
    rect[1] = pts[np.argmin(diff)]
    rect[3] = pts[np.argmax(diff)]
    return rect


class BoardVision:
    """封装棋盘透视校正、黑白棋识别、颜色校准三件事。"""

    def __init__(self, board_size=15, warp_size=WARP_SIZE):
        self.board_size = board_size
        self.warp_size = warp_size
        self.step = (warp_size - 1) / (board_size - 1)

        self.last_valid_M = None  # 最近一次成功的透视变换矩阵

        # 默认黑/白棋 HSV 阈值，可通过 calibration 重新标定
        self.lower_black = np.array([0, 0, 0])
        self.upper_black = np.array([180, 255, 60])
        self.lower_white = np.array([0, 0, 200])
        self.upper_white = np.array([180, 40, 255])

        self.calibration_mode = 0       # 0: 关闭, 1: 采黑棋, 2: 采白棋
        self.hsv_frame_for_picker = None  # 供鼠标回调读取的当前帧 HSV

    # ---------- 棋盘定位 ----------

    def find_board(self, frame):
        """在原始帧里找棋盘的四个角，找到就更新 self.last_valid_M。"""
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        blurred = cv2.GaussianBlur(gray, (5, 5), 0)
        edges = cv2.Canny(blurred, 50, 150)
        contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        if not contours:
            return

        largest = max(contours, key=cv2.contourArea)
        if cv2.contourArea(largest) <= 20000:
            return

        epsilon = 0.02 * cv2.arcLength(largest, True)
        approx = cv2.approxPolyDP(largest, epsilon, True)
        if len(approx) != 4:
            return

        pts = approx.reshape(4, 2)
        rect = order_points(pts)
        dst = np.array(
            [[0, 0], [self.warp_size - 1, 0],
             [self.warp_size - 1, self.warp_size - 1], [0, self.warp_size - 1]],
            dtype="float32",
        )
        self.last_valid_M = cv2.getPerspectiveTransform(rect, dst)

    def has_board(self):
        return self.last_valid_M is not None

    def warp(self, frame):
        return cv2.warpPerspective(frame, self.last_valid_M, (self.warp_size, self.warp_size))

    # ---------- 黑白棋识别 ----------

    def read_board(self, warped):
        """
        识别棋盘上每个交叉点的黑/白棋子。

        返回：
            board_state: (board_size, board_size) 的 0/1/2 矩阵
            current_black, current_white: 当前黑/白棋子数
            human_latest_move: 最后一个识别到的黑棋坐标（用于嘲讽台词里提一下人类下哪了）
            annotated: 画好标记点的 warped 图像副本
        """
        hsv = cv2.cvtColor(warped, cv2.COLOR_BGR2HSV)
        self.hsv_frame_for_picker = hsv.copy()

        annotated = warped.copy()
        board_state = np.zeros((self.board_size, self.board_size), dtype=int)
        current_black = 0
        current_white = 0
        human_latest_move = None

        for row in range(self.board_size):
            for col in range(self.board_size):
                x, y = int(round(col * self.step)), int(round(row * self.step))
                y_s, y_e = max(0, y - 12), min(self.warp_size - 1, y + 12)
                x_s, x_e = max(0, x - 12), min(self.warp_size - 1, x + 12)
                roi = hsv[y_s:y_e, x_s:x_e]

                # 注意：576 = 24x24，跟原版保持一致的判定基准面积
                black_ratio = cv2.countNonZero(cv2.inRange(roi, self.lower_black, self.upper_black)) / 576
                white_ratio = cv2.countNonZero(cv2.inRange(roi, self.lower_white, self.upper_white)) / 576

                if black_ratio > 0.4:
                    board_state[row, col] = 1
                    cv2.circle(annotated, (x, y), 8, (0, 0, 0), 3)
                    current_black += 1
                    human_latest_move = (row, col)
                elif white_ratio > 0.4:
                    board_state[row, col] = 2
                    cv2.circle(annotated, (x, y), 8, (255, 255, 255), 3)
                    current_white += 1
                else:
                    cv2.circle(annotated, (x, y), 1, (255, 0, 0), -1)

        return board_state, current_black, current_white, human_latest_move, annotated

    def grid_to_pixel(self, row, col):
        return int(round(col * self.step)), int(round(row * self.step))

    # ---------- 颜色校准 ----------

    def start_calibration(self):
        self.calibration_mode = 1
        speak_taunt("想要帮我矫正视力吗？请用鼠标在画面上点击一颗黑棋。")

    def mouse_callback(self, event, x, y, flags, param):
        """绑定给 cv2.setMouseCallback，鼠标点击棋盘上的黑/白棋来标定阈值。"""
        if event != cv2.EVENT_LBUTTONDOWN or self.calibration_mode == 0:
            return
        if self.hsv_frame_for_picker is None or y >= self.warp_size or x >= self.warp_size:
            return

        h, s, v = self.hsv_frame_for_picker[y, x]
        print(f"[*] 鼠标拾取像素 HSV: ({h}, {s}, {v})")

        if self.calibration_mode == 1:
            # 黑棋核心特征是"亮度低(V小)"，色相H和饱和度S可放宽
            self.lower_black = np.array([0, 0, 0])
            self.upper_black = np.array([180, 255, min(255, int(v) + 40)])
            print(f"✅ 黑棋阈值更新: {self.lower_black} -> {self.upper_black}")
            self.calibration_mode = 2
            speak_taunt("黑棋记住了。现在请在画面上点击一颗白棋！")

        elif self.calibration_mode == 2:
            # 白棋核心特征是"亮度高(V大)，饱和度低(S小)"
            self.lower_white = np.array([0, 0, max(0, int(v) - 40)])
            self.upper_white = np.array([180, min(255, int(s) + 40), 255])
            print(f"✅ 白棋阈值更新: {self.lower_white} -> {self.upper_white}")
            self.calibration_mode = 0
            speak_taunt("色彩校准完成，本小姐的眼睛现在可是雪亮的！")
