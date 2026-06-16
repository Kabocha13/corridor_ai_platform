import json
import sys
from collections import deque

# 探索の深さ (2手先を完璧に読みます。タイムアウトを考慮し2を推奨)
MAX_DEPTH = 2

def parse_coord(coord_str):
    """ "e4" ➔ (col, row) のインデックス (0-8) への変換 """
    col = ord(coord_str[0]) - ord("a")
    row = int(coord_str[1]) - 1
    return col, row


def get_shortest_path_len(pawn_pos, player, walls):
    """ 正確な壁判定を用いたBFSによる最短歩数計算。到達不能なら inf """
    try:
        start_col, start_row = parse_coord(pawn_pos)
        is_goal = (lambda c, r: r == 8) if player == "P1" else (lambda c, r: r == 0)

        queue = deque([(start_col, start_row, 0)])
        visited = {(start_col, start_row)}

        # 壁データのセット化（正確な2マスブロック判定用）
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

            # 上・下・左・右 の移動制限チェック
            # コリドールの壁 (c, r) は、(c, r) と (c+1, r)[横壁] または (c, r+1)[縦壁] を塞ぐ
            moves = []
            
            # 1. 上へ移動 (row -> row + 1)
            if row < 8 and not ((col, row) in h_walls or (col - 1, row) in h_walls):
                moves.append((col, row + 1))
            # 2. 下へ移動 (row -> row - 1)
            if row > 0 and not ((col, row - 1) in h_walls or (col - 1, row - 1) in h_walls):
                moves.append((col, row - 1))
            # 3. 左へ移動 (col -> col - 1)
            if col > 0 and not ((col - 1, row) in v_walls or (col - 1, row - 1) in v_walls):
                moves.append((col - 1, row))
            # 4. 右へ移動 (col -> col + 1)
            if col < 8 and not ((col, row) in v_walls or (col, row - 1) in v_walls):
                moves.append((col + 1, row))

            for ncol, nrow in moves:
                if (ncol, nrow) not in visited:
                    visited.add((ncol, nrow))
                    queue.append((ncol, nrow, dist + 1))

        return float("inf")
    except Exception:
        return float("inf")


def evaluate_board(pawns, walls, my_id, opp_id):
    """ 「永遠・無敵・最強」を基盤とした盤面評価関数 """
    my_dist = get_shortest_path_len(pawns[my_id], my_id, walls)
    opp_dist = get_shortest_path_len(pawns[opp_id], opp_id, walls)

    # 相手を閉じ込める壁、または自分が閉じ込められる手は排除
    if my_dist == float("inf"): return -9999
    if opp_dist == float("inf"): return 9999

    # 基本スコア：手数リード差（相手の残り歩数 - 自分の残り歩数）
    score = opp_dist - my_dist

    # 戦術知識1＆2: 「永遠・無敵」
    # 自分がリードしており、かつゴールまで4歩以内（相手の無駄な動きの隙を突く）なら勝利確定ボーナス
    if my_dist <= 4 and score > 0:
        score += 1000  

    # 戦術知識3: 「最強」の回避
    # 相手にルートを固められ、自分が遅れている（＝最強の檻にハメられる）危険を察知したら大減点
    if opp_dist <= 4 and score < 0:
        score -= 1000  

    return score


def generate_pseudo_moves(pawn_pos, walls):
    """ 相手の手番シミュレーション用に、簡易的な移動候補（1歩）を生成する """
    col, row = parse_coord(pawn_pos)
    h_walls = {(parse_coord(w["at"])[0], parse_coord(w["at"])[1]) for w in walls if w["orientation"] == "h"}
    v_walls = {(parse_coord(w["at"])[0], parse_coord(w["at"])[1]) for w in walls if w["orientation"] == "v"}
    
    valid_tos = []
    cols = ["a", "b", "c", "d", "e", "f", "g", "h", "i"]
    
    if row < 8 and not ((col, row) in h_walls or (col - 1, row) in h_walls):
        valid_tos.append(f"{cols[col]}{row+2}")
    if row > 0 and not ((col, row - 1) in h_walls or (col - 1, row - 1) in h_walls):
        valid_tos.append(f"{cols[col]}{row}")
    if col > 0 and not ((col - 1, row) in v_walls or (col - 1, row - 1) in v_walls):
        valid_tos.append(f"{cols[col-1]}{row+1}")
    if col < 8 and not ((col, row) in v_walls or (col, row - 1) in v_walls):
        valid_tos.append(f"{cols[col+1]}{row+1}")
        
    return [{"action": "move", "to": to} for to in valid_tos]


def alpha_beta(pawns, walls, legal_actions, depth, alpha, beta, is_maximizing, my_id, opp_id):
    """ アルファベータ法による2手先読み """
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

            # 相手の「次の対応」をシミュレートするため、相手の移動候補を擬似生成
            opp_moves = generate_pseudo_moves(next_pawns[opp_id], next_walls)
            
            # 相手はこちらにとって「最悪の手（ミニマイズ）」を選んでくると仮定
            eval_score, _ = alpha_beta(next_pawns, next_walls, opp_moves, depth - 1, alpha, beta, False, my_id, opp_id)

            # 移動の手にはほんの少しだけボーナスを与えて、無駄な壁置きを抑制
            if action["action"] == "move":
                eval_score += 0.1

            if eval_score > max_eval:
                max_eval = eval_score
                best_action = action
            alpha = max(alpha, eval_score)
            if beta <= alpha:
                break
        return max_eval, best_action
    else:
        # ミニマイズ側（相手の手番）
        min_eval = float("inf")
        for action in legal_actions:
            next_pawns = pawns.copy()
            next_walls = walls.copy()
            if action["action"] == "move":
                next_pawns[opp_id] = action["to"]
            
            eval_score = evaluate_board(next_pawns, next_walls, my_id, opp_id)
            if eval_score < min_eval:
                min_eval = eval_score
        return min_eval, None


# --- メインループ ---
for line in sys.stdin:
    try:
        state = json.loads(line)
        my_id = state["you"]
        opp_id = "P2" if my_id == "P1" else "P1"

        # 最善手を探索
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

        # 念のための安全弁
        if best_action is None:
            best_action = state["legal_actions"][0]

        print(json.dumps({"type": "action", **best_action}), flush=True)

    except Exception as global_error:
        # 万が一のクラッシュ時も絶対に反則負けにせず、合法手を返して試合を継続する
        print(f"Critial Error: {global_error}", file=sys.stderr, flush=True)
        try:
            fallback = state["legal_actions"][0]
            print(json.dumps({"type": "action", **fallback}), flush=True)
        except:
            pass
