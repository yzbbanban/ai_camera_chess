import cv2
import numpy as np

def order_points(pts):
    rect = np.zeros((4, 2), dtype="float32")
    s = pts.sum(axis=1)
    rect[0] = pts[np.argmin(s)]
    rect[2] = pts[np.argmax(s)]
    diff = np.diff(pts, axis=1)
    rect[1] = pts[np.argmin(diff)]
    rect[3] = pts[np.argmax(diff)]
    return rect

cap = cv2.VideoCapture(0) # 确保摄像头编号正确

print("=== 降维打击：局部对比度视觉引擎 ===")
print("按下 'q' 键退出")

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

            # 🚀 抛弃 HSV，直接使用灰度图进行相对明暗计算
            gray_warped = cv2.cvtColor(warped, cv2.COLOR_BGR2GRAY)

            grid_size = 15
            step = 599.0 / (grid_size - 1)
            roi_radius = 12  # ⬅️ 核心修复：把检测半径从 5 扩大到 12

            for row in range(grid_size):
                for col in range(grid_size):
                    x = int(round(col * step))
                    y = int(round(row * step))

                    # 1. 获取当前交叉点的平均亮度 (扩大到 24x24 像素区域)
                    y_start, y_end = max(0, y - roi_radius), min(599, y + roi_radius)
                    x_start, x_end = max(0, x - roi_radius), min(599, x + roi_radius)
                    center_brightness = np.mean(gray_warped[y_start:y_end, x_start:x_end])

                    # 2. 寻找参照物：当前交叉点旁边的“网格正中心” (纯木头)
                    ref_x_offset = step / 2 if col < 7 else -step / 2
                    ref_y_offset = step / 2 if row < 7 else -step / 2
                    ref_x = int(round(x + ref_x_offset))
                    ref_y = int(round(y + ref_y_offset))

                    # 参照框也要同样大
                    ref_y_start, ref_y_end = max(0, ref_y - roi_radius), min(599, ref_y + roi_radius)
                    ref_x_start, ref_x_end = max(0, ref_x - roi_radius), min(599, ref_x + roi_radius)
                    wood_brightness = np.mean(gray_warped[ref_y_start:ref_y_end, ref_x_start:ref_x_end])

                    # 3. 核心计算：计算局部的亮度差
                    diff = center_brightness - wood_brightness

                    # 4. 判定规则 (放宽一点黑棋的要求)
                    if diff < -40:
                        # 比木头暗40以上，是黑棋
                        cv2.circle(warped, (x, y), 10, (0, 255, 0), 3)
                    elif diff > 20:
                        # 比木头亮20以上，是白棋
                        cv2.circle(warped, (x, y), 10, (0, 0, 255), 3)
                    else:
                        # 亮度差不多，是空位
                        cv2.circle(warped, (x, y), 2, (255, 0, 0), -1)

            # 显示最终画面
            cv2.imshow("Robust Vision Engine", warped)

    if cv2.waitKey(1) == ord('q'): break

cap.release()
cv2.destroyAllWindows()