"""
engine.py —— 五子棋算法核心

只负责"给一个15x15的棋盘矩阵，算出下一步该走哪"，
不涉及摄像头、UI、语音，方便单独测试和复用。
"""

import numpy as np

BOARD_SIZE = 15

# ==========================================
# 棋形编码表（互不冲突，可安全用于 shape_counts 统计）
# ==========================================
PATTERN_FIVE = 5              # 连五
PATTERN_OPEN_FOUR = 42         # 活四（两端都空，必杀）
PATTERN_FOUR = 41              # 冲四（单端空，必须挡）
PATTERN_OPEN_THREE = 32        # 活三（两端都空）
PATTERN_BLOCKED_THREE = 31     # 眠三（单端空）
PATTERN_OPEN_TWO = 22
PATTERN_BLOCKED_TWO = 21
PATTERN_NONE = 0

_PATTERN_SCORE = {
    PATTERN_FIVE: 100000,
    PATTERN_OPEN_FOUR: 10000,
    PATTERN_FOUR: 1000,
    PATTERN_OPEN_THREE: 800,
    PATTERN_BLOCKED_THREE: 100,
    PATTERN_OPEN_TWO: 80,
    PATTERN_BLOCKED_TWO: 10,
    PATTERN_NONE: 0,
}

_DIRECTIONS = [(1, 0), (0, 1), (1, 1), (1, -1)]


def evaluate_line(board, r, c, dr, dc, player):
    """评估 (r, c) 沿 (dr, dc) 方向、假设落子为 player 的棋形，返回 (pattern_code, score)。"""
    count = 1
    i, j = r + dr, c + dc
    space1 = 0
    while 0 <= i < BOARD_SIZE and 0 <= j < BOARD_SIZE:
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
    while 0 <= i < BOARD_SIZE and 0 <= j < BOARD_SIZE:
        if board[i, j] == player:
            count += 1
        elif board[i, j] == 0:
            space2 = 1
            break
        else:
            break
        i, j = i - dr, j - dc

    spaces = space1 + space2

    if count >= 5:
        pattern = PATTERN_FIVE
    elif count == 4 and spaces == 2:
        pattern = PATTERN_OPEN_FOUR
    elif count == 4 and spaces == 1:
        pattern = PATTERN_FOUR
    elif count == 3 and spaces == 2:
        pattern = PATTERN_OPEN_THREE
    elif count == 3 and spaces == 1:
        pattern = PATTERN_BLOCKED_THREE
    elif count == 2 and spaces == 2:
        pattern = PATTERN_OPEN_TWO
    elif count == 2 and spaces == 1:
        pattern = PATTERN_BLOCKED_TWO
    else:
        pattern = PATTERN_NONE

    return pattern, _PATTERN_SCORE[pattern]


def evaluate_position(board, r, c, player):
    """评估某个空位对 player 的价值，含连环套(fork)识别。"""
    total_score = 0
    shape_counts = {
        PATTERN_FIVE: 0, PATTERN_OPEN_FOUR: 0, PATTERN_FOUR: 0,
        PATTERN_OPEN_THREE: 0, PATTERN_BLOCKED_THREE: 0,
        PATTERN_OPEN_TWO: 0, PATTERN_BLOCKED_TWO: 0,
        PATTERN_NONE: 0,
    }

    for dr, dc in _DIRECTIONS:
        pattern, score = evaluate_line(board, r, c, dr, dc, player)
        shape_counts[pattern] += 1
        total_score += score

    if shape_counts[PATTERN_FIVE] > 0:
        total_score += 1000000     # 连五，必胜/必防
    elif shape_counts[PATTERN_OPEN_FOUR] > 0:
        total_score += 500000      # 活四：对方挡不住
    elif shape_counts[PATTERN_FOUR] >= 2:
        total_score += 400000      # 双冲四
    elif shape_counts[PATTERN_FOUR] >= 1 and shape_counts[PATTERN_OPEN_THREE] >= 1:
        total_score += 300000      # 四三连环
    elif shape_counts[PATTERN_OPEN_THREE] >= 2:
        total_score += 150000      # 双活三
    elif shape_counts[PATTERN_FOUR] >= 1:
        total_score += 50000       # 单冲四

    return total_score


def has_neighbor(board, r, c, radius=2):
    for dr in range(-radius, radius + 1):
        for dc in range(-radius, radius + 1):
            if dr == 0 and dc == 0:
                continue
            nr, nc = r + dr, c + dc
            if 0 <= nr < BOARD_SIZE and 0 <= nc < BOARD_SIZE and board[nr, nc] != 0:
                return True
    return False


def evaluate_board_total(board):
    ai_scores = []
    hu_scores = []
    for r in range(BOARD_SIZE):
        for c in range(BOARD_SIZE):
            if board[r, c] == 0 and has_neighbor(board, r, c, 1):
                ai_scores.append(evaluate_position(board, r, c, 2))
                hu_scores.append(evaluate_position(board, r, c, 1))

    ai_scores.sort(reverse=True)
    hu_scores.sort(reverse=True)

    ai_total = ai_scores[0] if ai_scores else 0
    if len(ai_scores) > 1:
        ai_total += ai_scores[1] * 0.6

    hu_total = hu_scores[0] if hu_scores else 0
    if len(hu_scores) > 1:
        hu_total += hu_scores[1] * 0.6

    return ai_total - hu_total * 1.5


def minimax(board, depth, alpha, beta, is_maximizing):
    if depth == 0:
        return evaluate_board_total(board)

    candidates = []
    for r in range(BOARD_SIZE):
        for c in range(BOARD_SIZE):
            if board[r, c] == 0 and has_neighbor(board, r, c, 2):
                ai_score = evaluate_position(board, r, c, 2)
                hu_score = evaluate_position(board, r, c, 1)

                # 💥 修复短路：在推演树里也要严格遵守绝对优先级！
                if is_maximizing:
                    if ai_score >= 1000000: return 100000000  # AI 连五
                    if hu_score >= 1000000:
                        score = 50000000  # 人类 连五，必须堵
                    elif ai_score >= 300000:
                        score = 10000000  # AI 活四/双杀
                    elif hu_score >= 300000:
                        score = 5000000   # 人类 活四/双杀
                    else:
                        score = ai_score + hu_score
                    candidates.append((score, (r, c)))
                else:
                    if hu_score >= 1000000: return -100000000 # 人类 连五
                    if ai_score >= 1000000:
                        score = 50000000  # AI 连五，人类必须堵
                    elif hu_score >= 300000:
                        score = 10000000
                    elif ai_score >= 300000:
                        score = 5000000
                    else:
                        score = hu_score + ai_score
                    candidates.append((score, (r, c)))

    candidates.sort(reverse=True, key=lambda x: x[0])
    top_candidates = [move for score, move in candidates[:8]]

    if not top_candidates:
        return evaluate_board_total(board)

    if is_maximizing:
        max_eval = -float('inf')
        for move in top_candidates:
            board[move[0], move[1]] = 2
            ev = minimax(board, depth - 1, alpha, beta, False)
            board[move[0], move[1]] = 0
            max_eval = max(max_eval, ev)
            alpha = max(alpha, ev)
            if beta <= alpha:
                break
        return max_eval
    else:
        min_eval = float('inf')
        for move in top_candidates:
            board[move[0], move[1]] = 1
            ev = minimax(board, depth - 1, alpha, beta, True)
            board[move[0], move[1]] = 0
            min_eval = min(min_eval, ev)
            beta = min(beta, ev)
            if beta <= alpha:
                break
        return min_eval


def get_best_move(board_state):
    """给定当前棋盘，返回 AI 应该落子的 (row, col)。"""
    candidates = []
    is_empty = True

    for r in range(BOARD_SIZE):
        for c in range(BOARD_SIZE):
            if board_state[r, c] != 0:
                is_empty = False
            elif has_neighbor(board_state, r, c, 2):
                ai_score = evaluate_position(board_state, r, c, 2)
                hu_score = evaluate_position(board_state, r, c, 1)

                # 💥 核心修复：建立不可逾越的绝对阶梯，彻底取代原有的短路 return
                if ai_score >= 1000000:
                    score = 100000000  # 1. AI 连五 (必杀)
                elif hu_score >= 1000000:
                    score = 50000000   # 2. 玩家 连五 (必防，必须放下手里的一切去堵)
                elif ai_score >= 300000:
                    score = 10000000   # 3. AI 成活四/双杀
                elif hu_score >= 300000:
                    score = 5000000    # 4. 玩家 成活四/双杀 (必防)
                else:
                    # 5. 常规评估，进攻兼顾防守
                    score = ai_score + hu_score * 1.2
                    score += (7 - abs(7 - r)) + (7 - abs(7 - c))  # 居中权重

                candidates.append((score, (r, c)))

    if is_empty:
        return (7, 7)  # 开局占天元

    candidates.sort(reverse=True, key=lambda x: x[0])
    if not candidates:
        return (7, 7)

    # 🚀 斩杀线：如果找到了生死攸关的点（自己能赢，或必须防守死亡），直接出手，跳过深推延！
    best_cand_score, best_cand_move = candidates[0]
    if best_cand_score >= 5000000:
        return best_cand_move

    top_candidates = [move for score, move in candidates[:10]]
    best_move = top_candidates[0]
    best_val = -float('inf')
    alpha = -float('inf')
    beta = float('inf')

    for move in top_candidates:
        board_state[move[0], move[1]] = 2
        val = minimax(board_state, depth=2, alpha=alpha, beta=beta, is_maximizing=False)
        board_state[move[0], move[1]] = 0

        if val > best_val:
            best_val = val
            best_move = move
        alpha = max(alpha, best_val)

    return best_move


def check_winner(board):
    """检查是否有人连成五子，返回 1(黑)/2(白)/0(无)。"""
    for r in range(BOARD_SIZE):
        for c in range(BOARD_SIZE):
            player = board[r, c]
            if player != 0:
                for dr, dc in [(0, 1), (1, 0), (1, 1), (1, -1)]:
                    count = 1
                    nr, nc = r + dr, c + dc
                    while 0 <= nr < BOARD_SIZE and 0 <= nc < BOARD_SIZE and board[nr, nc] == player:
                        count += 1
                        nr += dr
                        nc += dc
                    if count >= 5:
                        return player
    return 0


def check_fatal_threat(board):
    """
    检查是否有人已经走出"冲四"（四子连珠且至少一端开放）。
    只要有一端开放，对方下一步就能连五，必须立刻提示玩家去挡。
    """
    for r in range(BOARD_SIZE):
        for c in range(BOARD_SIZE):
            player = board[r, c]
            if player != 0:
                for dr, dc in [(0, 1), (1, 0), (1, 1), (1, -1)]:
                    count = 1
                    nr, nc = r + dr, c + dc
                    while 0 <= nr < BOARD_SIZE and 0 <= nc < BOARD_SIZE and board[nr, nc] == player:
                        count += 1
                        nr += dr
                        nc += dc
                    if count == 4:
                        before_r, before_c = r - dr, c - dc
                        after_r, after_c = nr, nc
                        before_open = (0 <= before_r < BOARD_SIZE and 0 <= before_c < BOARD_SIZE
                                       and board[before_r, before_c] == 0)
                        after_open = (0 <= after_r < BOARD_SIZE and 0 <= after_c < BOARD_SIZE
                                      and board[after_r, after_c] == 0)
                        if before_open or after_open:
                            return player
    return 0