import json
import sys
from collections import deque

# 探索の深さ (制限時間オーバーを防ぐため、まずは2手読み(=2)を確実に動かします)
MAX_DEPTH = 2


def parse_coord(coord_str):
    """ "e4" などの座標文字列を (col, row) のインデックス (0-8) に変換 """
    col = ord(coord_str[0]) - ord("a")
    row = int(coord_str[1]) - 1
    return col, row


def get_shortest_path_len(pawn_pos, player, walls):
    """ BFSで指定プレイヤーのゴールまでの最短歩数を計算。辿り着けないなら inf """
    try:
        start_col, start_row = parse_coord(pawn_pos)
        is_goal = (lambda c, r: r == 8) if player == "P1" else (lambda c, r: r == 0)

        queue = deque([(start_col, start_row, 0)])
        visited = {(start_col, start_row)}

        h_walls = set()
        v_walls = set()
        for w in walls:
            c, r = parse_coord(w["at"])
            if w["orientation"] == "h":
                h_walls.add((c, r))
            elif w["orientation"] == "v":
                v_walls.add((c, r))

        while queue:
            col, row, dist = queue.popleft()
            if is_goal(col, row):
                return dist

            # 上下左右
            directions = [(0, 1, "up"), (0, -1, "down"), (-1, 0, "left"), (1, 0, "right")]
            for dc, dr, direction in directions:
                ncol, nrow = col + dc, row + dr
                if 0 <= ncol < 9 and 0 <= nrow < 9:
                    if (ncol, nrow) in visited:
                        continue

                    blocked = False
                    # 【修正済み】壁の衝突判定のタイポを修正
                    if direction == "up" and ((col, row) in h_walls or (col - 1, row) in h_walls):
                        blocked = True
                    elif direction == "down" and ((col, row - 1) in h_walls or (col - 1, row - 1) in h_walls):
                        blocked = True
                    elif direction == "right" and ((col, row) in v_walls or (col, row - 1) in v_walls):
                        blocked = True
                    elif direction == "left" and ((col - 1, row) in v_walls or (col - 1, row - 1) in v_walls):
                        blocked = True

                    if not blocked:
                        visited.add((ncol, nrow))
                        queue.append((ncol, nrow, dist + 1))
        return float("inf")
    except Exception as e:
        # 万が一エラーが起きてもシステムを止めないための安全弁
        print(f"Error in BFS: {e}", file=sys.stderr)
        return float("inf")


def evaluate_board(pawns, walls, my_id, opp_id):
    """ 「永遠・無敵・最強」の戦術知識を組み込んだ盤面評価関数 """
    my_dist = get_shortest_path_len(pawns[my_id], my_id, walls)
    opp_dist = get_shortest_path_len(pawns[opp_id], opp_id, walls)

    if my_dist == float("inf"): return -9999
    if opp_dist == float("inf"): return 9999

    # 基本スコア：手数リード差
    score = opp_dist - my_dist

    # 知識1&2: 「永遠」「無敵」の簡易検知（ゴールまで3歩以内でリードしていれば勝利確定ボーナス）
    if my_dist <= 3 and score > 0:
        score += 500  

    # 知識3: 「最強」の回避（相手のルートが確定し、自分が大幅に遅れている場合は大減点）
    if opp_dist <= 3 and score < 0:
        score -= 500  

    return score


def alpha_beta(pawns, walls, legal_actions, depth, alpha, beta, is_maximizing, my_id, opp_id):
    """ アルファベータ法による先読み """
    if depth == 0 or not legal_actions:
        return evaluate_board(pawns, walls, my_id, opp_id), None

    best_action = None

    if is_maximizing:
        max_eval = -float("inf")
        for action in legal_actions:
            next_pawns = pawns.copy()
            next_walls = walls.copy()
            if action["action"] == "move":
                next_pawns[my_id] = action["to"]
            elif action["action"] == "wall":
                next_walls.append({"action": "wall", "at": action["at"], "orientation": action["orientation"]})

            # 相手の手番（簡易的に深さを下げて評価）
            eval_score, _ = alpha_beta(next_pawns, next_walls, [], depth - 1, alpha, beta, False, my_id, opp_id)

            if eval_score > max_eval:
                max_eval = eval_score
                best_action = action
            alpha = max(alpha, eval_score)
            if beta <= alpha:
                break
        return max_eval, best_action
    else:
        return evaluate_board(pawns, walls, my_id, opp_id), None


# --- メインループ ---
for line in sys.stdin:
    try:
        state = json.loads(line)
        my_id = state["you"]
        opp_id = "P2" if my_id == "P1" else "P1"

        # アルファベータ探索を実行
        _, best_action = alpha_beta(
            state["pawns"],
            state["walls"],
            state["legal_actions"],
            depth=MAX_DEPTH,
            alpha=-float("inf"),
            beta=float("inf"),
            is_maximizing=True,
            my_id=my_id,
            opp_id=opp_id,
        )

        # 万が一、手が選ばれなかった場合は合法手の先頭をフォールバックに
        if best_action is None:
            best_action = state["legal_actions"][0]

        # 【超重要】フォーマットを合わせて標準出力へ
        print(json.dumps({"type": "action", **best_action}), flush=True)

    except Exception as global_error:
        # メインループ全体を保護：何があっても標準エラーにログを出し、ゲームエンジンには有効な手を返す
        print(f"Global Critical Error: {global_error}", file=sys.stderr, flush=True)
        # 最低限、受け取ったstateの最初の合法手を安全に返す
        try:
            fallback = state["legal_actions"][0]
            print(json.dumps({"type": "action", **fallback}), flush=True)
        except:
            pass