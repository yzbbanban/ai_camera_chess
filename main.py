import cv2
import numpy as np


# 辅助函数：将识别到的四个点按【左上, 右上, 右下, 左下】的顺序排列
def order_points(pts):
    rect = np.zeros((4, 2), dtype="float32")
    # 按行求和 (x+y)：最小的是左上角，最大的是右下角
    s = pts.sum(axis=1)
    rect[0] = pts[np.argmin(s)]
    rect[2] = pts[np.argmax(s)]
    # 按行求差 (y-x)：最小的是右上角，最大的是左下角
    diff = np.diff(pts, axis=1)
    rect[1] = pts[np.argmin(diff)]
    rect[3] = pts[np.argmax(diff)]
    return rect


cap = cv2.VideoCapture(0)

if not cap.isOpened():
    print("无法打开摄像头！")
    exit()

print("按下 'q' 键退出")

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
            # 画出边框和顶点
            cv2.drawContours(frame, [approx], -1, (0, 255, 0), 2)
            for point in approx:
                x, y = point[0]
                cv2.circle(frame, (x, y), 5, (0, 0, 255), -1)

            # --- 新增：透视变换 ---
            # 1. 提取四个顶点并排序
            pts = approx.reshape(4, 2)
            rect = order_points(pts)

            # 2. 设定目标画面的大小，五子棋通常是 15x15 线条，设个好除以 14 的数字，比如 600x600 像素
            dst = np.array([
                [0, 0],
                [599, 0],
                [599, 599],
                [0, 599]
            ], dtype="float32")

            # 3. 计算透视变换矩阵并生成新图像
            M = cv2.getPerspectiveTransform(rect, dst)
            warped = cv2.warpPerspective(frame, M, (600, 600))

            hsv_warped = cv2.cvtColor(warped, cv2.COLOR_BGR2HSV)

            # 建立 15x15 虚拟坐标网格 (已有的代码)
            grid_size = 15
            step = 599.0 / (grid_size - 1)

            # --- 新增：定义棋子HSV阈值 (需要根据你的光线调优) ---
            # 黑棋：低亮度 (V值是关键，V < 50)
            lower_black = np.array([0, 0, 0])
            upper_black = np.array([180, 255, 60])

            # 白棋：高亮度 (V > 180)，且低饱和度 (S < 40，过滤黄色的木头色)
            lower_white = np.array([0, 0, 200])
            upper_white = np.array([180, 40, 255])

            # 准备一个 15x15 的二维数组存棋局状态 (0:空, 1:黑, 2:白)
            # 你可以把它当成虚拟的五子棋程序
            board_state = np.zeros((15, 15), dtype=int)

            # 设定ROI（感兴趣区域）检测方块的大小 (在每个交叉点周围10x10像素)
            roi_size = 12

            # 核心检测循环
            for row in range(grid_size):
                for col in range(grid_size):
                    # 计算每个交叉点的 x 和 y 像素坐标 (已有的代码)
                    x = int(round(col * step))
                    y = int(round(row * step))

                    # 裁剪出该交叉点周围的一个小方块 (ROI)
                    y_start = max(0, y - roi_size)
                    y_end = min(599, y + roi_size)
                    x_start = max(0, x - roi_size)
                    x_end = min(599, x + roi_size)

                    # 裁剪出的HSV区域
                    roi_hsv = hsv_warped[y_start:y_end, x_start:x_end]

                    # 应用颜色阈值，生成掩膜 (符合颜色的像素为白，不符合为黑)
                    mask_black = cv2.inRange(roi_hsv, lower_black, upper_black)
                    mask_white = cv2.inRange(roi_hsv, lower_white, upper_white)

                    # 计算小区域内黑棋和白棋的像素数量
                    black_pixel_count = cv2.countNonZero(mask_black)
                    white_pixel_count = cv2.countNonZero(mask_white)

                    # 计算占比 (设定一个门限值，比如超过30%的面积是该颜色)
                    total_pixels = (roi_size * 2) ** 2
                    threshold_ratio = 0.4

                    # 判定棋子类型
                    if black_pixel_count / total_pixels > threshold_ratio:
                        board_state[row, col] = 1  # 黑
                        # 在拉平的棋盘上画一个粗黑圈
                        cv2.circle(warped, (x, y), 8, (0, 0, 0), 3)
                    elif white_pixel_count / total_pixels > threshold_ratio:
                        board_state[row, col] = 2  # 白
                        # 在拉平的棋盘上画一个粗白圈
                        cv2.circle(warped, (x, y), 8, (255, 255, 255), 3)
                    else:
                        board_state[row, col] = 0  # 空
                        # 保持小蓝点，画得更小一点
                        cv2.circle(warped, (x, y), 1, (255, 0, 0), -1)

                        # 可选：如果你想看到目前的HSV图像（比如白棋掩膜）可以取消注释
            # cv2.imshow("HSV White Mask (Debug)", mask_white)

            # --- 新增：全局颜色掩膜调试窗口 ---
            full_mask_white = cv2.inRange(hsv_warped, lower_white, upper_white)
            full_mask_black = cv2.inRange(hsv_warped, lower_black, upper_black)
            cv2.imshow("Debug: White Vision", full_mask_white)
            cv2.imshow("Debug: Black Vision", full_mask_black)

            # 显示结果
            cv2.imshow("Warped Board (Chess Recognition Enabled)", warped)

    if cv2.waitKey(1) == ord('q'):
        break

cap.release()
cv2.destroyAllWindows()