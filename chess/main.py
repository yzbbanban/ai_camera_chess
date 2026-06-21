"""
main.py —— 赛博五子棋少女 主程序

只负责"串流程"：读摄像头 -> 识别棋盘 -> 喂给对局状态机判断该谁走 ->
该 AI 走时调用 engine 算一步 -> 画面上标红圈 -> 该说话时调用 voice。

具体怎么识别棋盘看 vision.py，怎么算棋看 engine.py，
对局状态怎么流转看 game.py。
"""

import cv2

from engine import get_best_move
from game import GomokuGame
from vision import BoardVision
from voice import (
    speak_taunt,
    generate_taunt,
    generate_checkmate_taunt,
    generate_endgame_taunt,
)

WINDOW_NAME = "Cyber Gomoku Master"


def draw_ai_target(display_img, vision, move):
    """在棋盘上画出 AI 让人类帮忙落子的位置（红圈+十字）。"""
    r, c = move
    x, y = vision.grid_to_pixel(r, c)
    cv2.circle(display_img, (x, y), 14, (0, 0, 255), 2)
    cv2.line(display_img, (x - 10, y), (x + 10, y), (0, 0, 255), 2)
    cv2.line(display_img, (x, y - 10), (x, y + 10), (0, 0, 255), 2)
    cv2.putText(display_img, "PLACE WHITE", (x + 15, y - 15),
                cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 255), 2)


def draw_dashboard(warped, vision, game):
    """底部状态栏：当前轮到谁、识别是否稳定、校准提示等。"""
    display_img = cv2.copyMakeBorder(warped, 0, 60, 0, 0, cv2.BORDER_CONSTANT, value=(30, 30, 30))

    if vision.calibration_mode == 1:
        cv2.putText(display_img, "CALIBRATION: Click a BLACK stone", (15, 635),
                    cv2.FONT_HERSHEY_DUPLEX, 0.7, (0, 255, 255), 2)
    elif vision.calibration_mode == 2:
        cv2.putText(display_img, "CALIBRATION: Click a WHITE stone", (15, 635),
                    cv2.FONT_HERSHEY_DUPLEX, 0.7, (0, 255, 255), 2)
    elif game.game_over:
        if game.winner == 2:
            cv2.putText(display_img, "GAME OVER! AI WINS!", (15, 635), cv2.FONT_HERSHEY_DUPLEX, 0.7, (0, 0, 255), 2)
        elif game.winner == 1:
            cv2.putText(display_img, "GAME OVER! YOU WIN!", (15, 635), cv2.FONT_HERSHEY_DUPLEX, 0.7, (0, 255, 0), 2)
        else:
            cv2.putText(display_img, "GAME OVER! DRAW!", (15, 635), cv2.FONT_HERSHEY_DUPLEX, 0.7, (0, 255, 255), 2)
    elif game.is_human_turn_settled:
        cv2.putText(display_img, "YOUR TURN: Place Black", (15, 635), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)
    elif game.is_ai_turn:
        cv2.putText(display_img, "AI TURN: Place White", (15, 635), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 165, 255), 2)
    else:
        cv2.putText(display_img, "ERROR: Pieces Mismatch!", (15, 635), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 255), 2)

    if game.game_over:
        cv2.putText(display_img, "FINISHED", (480, 635), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)
    elif vision.calibration_mode > 0:
        cv2.putText(display_img, "LOCKED", (480, 635), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 255), 2)
    elif game.stable_frames < 15:
        cv2.putText(display_img, f"Wait... {game.stable_frames}/15", (420, 635),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 165, 255), 2)
    else:
        cv2.putText(display_img, "READY", (480, 635), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)

    return display_img


def handle_settled_frame(board_state, vision, game, human_latest_move, warped):
    """棋子数量已经稳定满 15 帧时，真正做一次判定 + 决策。"""

    # 🔍 调试：打印算法实际看到的棋盘，跟实拍照片核对
    print("==== 当前算法看到的棋盘 ====")
    for row in board_state:
        print("".join("." if v == 0 else ("●" if v == 1 else "○") for v in row))

    winner = game.check_game_over(board_state)
    if winner != 0:
        taunt = generate_endgame_taunt(winner == 1)
        print(f"\n🎉 比赛结束！\n🤖 少女AI: {taunt}")
        speak_taunt(taunt)
        return

    threat = game.check_fatal(board_state)
    if threat != 0:
        taunt = generate_checkmate_taunt(threat == 1)
        print(f"\n🚨 活四预警！\n🤖 少女AI: {taunt}")
        speak_taunt(taunt)
        cv2.putText(warped, "CHECKMATE!", (150, 250), cv2.FONT_HERSHEY_DUPLEX, 1.5, (0, 0, 255), 3)
        temp_disp = cv2.copyMakeBorder(warped, 0, 60, 0, 0, cv2.BORDER_CONSTANT, value=(30, 30, 30))
        cv2.imshow(WINDOW_NAME, temp_disp)
        cv2.waitKey(1)

    if game.is_human_turn_settled:
        if game.ai_planned_move is not None:
            should_skip, _, should_speak_error = game.validate_ai_stone(board_state)
            if should_skip:
                if should_speak_error:
                    error_text = "喂！你是不是眼花啦？我让你下在红圈那里，你放哪去了！赶紧给我拿开重新放！"
                    print(f"🤖 少女AI: {error_text}")
                    speak_taunt(error_text)
                return
            print("\n[系统] ✅ 确认白棋落子！红圈清除。")

    elif game.is_ai_turn:
        if game.needs_recalculation(board_state):
            print("\n[系统] 🎯 检测到全新盘面！AI开始思考...")
            cv2.putText(warped, "AI THINKING...", (120, 300), cv2.FONT_HERSHEY_DUPLEX, 1.5, (0, 0, 255), 3)
            temp_disp = cv2.copyMakeBorder(warped, 0, 60, 0, 0, cv2.BORDER_CONSTANT, value=(30, 30, 30))
            cv2.imshow(WINDOW_NAME, temp_disp)
            cv2.waitKey(1)

            move = get_best_move(board_state)
            game.set_ai_move(board_state, move)

            from engine import evaluate_position
            print(f"🔍 AI选点 {move} | 对AI价值: {evaluate_position(board_state, move[0], move[1], 2)} "
                  f"| 对人类价值: {evaluate_position(board_state, move[0], move[1], 1)}")

            taunt = generate_taunt(human_latest_move, move)
            print(f"♟️ AI指令: 将白棋放在 {move}\n🤖: {taunt}")
            speak_taunt(taunt)


def main():
    cap = cv2.VideoCapture(0)
    print("==== 赛博五子棋少女 已启动 ====")

    vision = BoardVision(board_size=15)
    game = GomokuGame()

    cv2.namedWindow(WINDOW_NAME)
    cv2.setMouseCallback(WINDOW_NAME, vision.mouse_callback)

    while True:
        ret, frame = cap.read()
        if not ret:
            break

        vision.find_board(frame)
        if not vision.has_board():
            cv2.putText(frame, "Looking for Gomoku Board...", (50, 50),
                        cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 2)
            cv2.imshow(WINDOW_NAME, frame)
            if cv2.waitKey(1) == ord('q'):
                break
            continue

        warped = vision.warp(frame)
        board_state, current_black, current_white, human_latest_move, warped = vision.read_board(warped)

        if not game.game_over and vision.calibration_mode == 0:
            just_settled = game.update_stability(current_black, current_white)
            if just_settled:
                handle_settled_frame(board_state, vision, game, human_latest_move, warped)

        if game.ai_planned_move is not None:
            draw_ai_target(warped, vision, game.ai_planned_move)

        display_img = draw_dashboard(warped, vision, game)
        cv2.imshow(WINDOW_NAME, display_img)

        key = cv2.waitKey(1) & 0xFF
        if key == ord('q'):
            break
        elif key == ord('r'):
            print("=== 🔄 收到重置指令，棋局已重置！ ===")
            restart_text = "哼，这就急着重新开始啦？本小姐就大发慈悲再给你一次机会，准备好再被我虐一次了吗？"
            print(f"🤖 少女AI: {restart_text}")
            speak_taunt(restart_text)
            game.reset()
        elif key == ord('c'):
            print("=== 🖱️ 进入色彩校准模式 ===")
            vision.start_calibration()

    cap.release()
    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
