"""
game.py —— 对局状态机

原版里 target_black / target_white / stable_frames / ai_planned_move /
last_calculated_board / fatal_warned / error_voice_played 这些变量
全是裸的全局变量，散落在主循环各处，谁改了谁没改很难一眼看清。

这里把它们收进 GomokuGame 一个类里，main.py 只需要调用方法、
读取返回值，不用再关心内部状态怎么互相影响。
"""

import numpy as np

from engine import check_winner, check_fatal_threat

STABLE_THRESHOLD = 15  # 连续多少帧识别结果不变，才认为"这一步真的落定了"


def check_pos(detected_pos, target_pos, error_voice_played):
    """校验物理落子是否与系统期望位置一致。"""
    if detected_pos is None or target_pos is None:
        return False, error_voice_played

    if detected_pos != target_pos:
        print(f"❌ 警告：识别落点 {detected_pos} 与目标 {target_pos} 不符！")
        return False, True

    print("✅ 确认落子位置完全一致！")
    return True, False


class GomokuGame:
    def __init__(self):
        self.target_black = 0
        self.target_white = 0
        self.stable_frames = 0

        self.ai_planned_move = None
        self.last_calculated_board = None

        self.game_over = False
        self.winner = 0
        self.fatal_warned = False
        self.error_voice_played = False

    def reset(self):
        self.__init__()

    # ---------- 稳定性判定 ----------

    def update_stability(self, current_black, current_white):
        """喂入当前识别到的黑/白棋子数，返回这一帧是否刚好达到"稳定"的判定点。"""
        if current_black != self.target_black or current_white != self.target_white:
            self.target_black = current_black
            self.target_white = current_white
            self.stable_frames = 1
        else:
            self.stable_frames += 1
        return self.stable_frames == STABLE_THRESHOLD

    @property
    def is_human_turn_settled(self):
        """黑白棋数相等：双方都已经各下了一手，回合记账是齐的。"""
        return self.target_black == self.target_white

    @property
    def is_ai_turn(self):
        """黑棋比白棋多一手：该 AI 落白棋了。"""
        return self.target_black == self.target_white + 1

    # ---------- 输赢 / 预警判定 ----------

    def check_game_over(self, board_state):
        winner = check_winner(board_state)
        if winner != 0:
            self.game_over = True
            self.ai_planned_move = None
            self.winner = winner
        return winner

    def check_fatal(self, board_state):
        """只在还没报警过的情况下检查一次冲四预警，避免反复刷屏喊话。"""
        if self.fatal_warned:
            return 0
        threat = check_fatal_threat(board_state)
        if threat != 0:
            self.fatal_warned = True
        return threat

    # ---------- AI 落子的提出与校验 ----------

    def needs_recalculation(self, board_state):
        """当前棋盘是不是一个 AI 还没算过的新局面。"""
        return (
            self.ai_planned_move is None
            or self.last_calculated_board is None
            or not np.array_equal(board_state, self.last_calculated_board)
        )

    def set_ai_move(self, board_state, move):
        self.ai_planned_move = move
        self.last_calculated_board = board_state.copy()

    def validate_ai_stone(self, board_state):
        """
        人类刚替 AI 把白棋放下去了，校验放的位置对不对。

        返回 (should_skip_frame, new_white_pos, should_speak_error):
            should_skip_frame=True 时，说明放错了，main.py 应该跳过本帧
            后续处理（计分板已经在内部回退）。
            should_speak_error=True 时，是"这次落错"的第一次报警，
            main.py 应该播报一次语音提示（避免每帧都重复喊）。
        """
        if self.ai_planned_move is None:
            return False, None, False

        new_white_pos = None
        if self.last_calculated_board is not None:
            diff = board_state - self.last_calculated_board
            new_y, new_x = np.where(diff == 2)
            if len(new_y) > 0:
                new_white_pos = (int(new_y[0]), int(new_x[0]))

        if new_white_pos is not None:
            was_already_warned = self.error_voice_played
            is_valid, self.error_voice_played = check_pos(
                new_white_pos, self.ai_planned_move, self.error_voice_played
            )
            if not is_valid:
                self.target_white -= 1
                self.stable_frames = 0
                should_speak_error = not was_already_warned
                return True, None, should_speak_error

        # 落子正确：清空"AI 还在等的那一步"的记忆
        self.ai_planned_move = None
        self.last_calculated_board = None
        return False, new_white_pos, False
