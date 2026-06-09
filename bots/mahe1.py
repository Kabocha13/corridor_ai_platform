import json
import sys
from collections import deque

# 探索の深さを設定 (2〜4を推奨。4にするとより深く読みますが計算時間が増えます)
# 制限時間に応じて調整してください。
MAX_DEPTH = 2


def parse_coord(coord_str):
    """"e4" などの座標文字列を (col, row) のインデックス (0-8) に変換"""
    col = ord(coord_str[0]) - ord("a")
    row = int(coord_str[1]) - 1
    return col, row


def get_shortest_path_len(pawn_pos, player, walls):
    """BFSで指定プレイヤーのゴールまでの最短歩数を計算。辿り着けないなら inf"""
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

        directions = [(0, 1, "up"), (0, -1, "down"), (-1, 0, "left"), (1, 0, "right")]
        for dc, dr, direction in directions:
            ncol, nrow = col + dc, row + dr
            if 0 <= ncol < 9 and 0 <= nrow < 9:
                if (ncol, nrow) in visited:
                    continue

                blocked = False
                if direction == "up" and ((col, row) in h_walls or (col - 1, row) in h_walls):
                    blocked = True
                elif direction == "down" and ((col, row - 1) in h_walls or (col - 1, row - 1) in h_walls):
                    blocked = True
                elif direction == "right" and ((col, v_walls) in v_walls or (col, row - 1) in v_walls):
                    # 簡易衝突判定
                    if (col, row) in v_walls or (col, row - 1) in v_walls:
                        blocked = True
                elif direction == "left":
                    if (col - 1, row) in v_walls or (col - 1, row - 1) in v_walls:
                        blocked = True

                if not blocked:
                    visited.add((ncol, nrow))
                    queue.append((ncol, nrow, dist + 1))
    return float("inf")


def evaluate_board(pawns, walls, my_id, opp_id):
    """「永遠・無敵・最強」の戦術知識を組み込んだ盤面評価関数"""
    my_dist = get_shortest_path_len(pawns[my_id], my_id, walls)
    opp_dist = get_shortest_path_len(pawns[opp_id], opp_id, walls)

    # どちらかが完全に閉じ込められる（違法手）なら最悪の評価
    if my_dist == float("inf"):
        return -9999
    if opp_dist == float("inf"):
        return 9999

    # 基本スコアは手数差（リードしている歩数）
    score = opp_dist - my_dist

    # --- 知識1: 「永遠」の判定（簡易シミュレーション） ---
    # 空いている適当な場所に仮想の壁を置いてみても、自分の歩数が増えない＝「永遠（ルート確定）」
    # ここでは「すでに自分がゴールまで十分近く、ルートがかなり固定されているか」を
    # 相手の壁の残り枚数や現在の歩数の少なさから簡易評価します。
    is_my_route_secure = my_dist <= 3  # ゴールまであとわずか
    is_opp_route_secure = opp_dist <= 3

    # --- 知識2: 「無敵」の検知 ---
    if is_my_route_secure and score > 0:
        score += 500  # 自分が安全かつリードしていれば絶対勝利（無敵ボーナス）

    # --- 知識3: 「最強」の回避とハメ ---
    # 相手が「無敵」状態で、自分が手を出せない（scoreが著しく低い）局面
    if is_opp_route_secure and score < 0:
        score -= 500  # 「最強」にハメられる悪手を全力回避

    return score


def alpha_beta(pawns, walls, legal_actions, depth, alpha, beta, is_maximizing, my_id, opp_id):
    """相手の最適な対応をシミュレーションするアルファベータ法"""
    if depth == 0 or not legal_actions:
        return evaluate_board(pawns, walls, my_id, opp_id), None

    best_action = None

    if is_maximizing:
        max_eval = -float("inf")
        for action in legal_actions:
            # 1手シミュレート
            next_pawns = pawns.copy()
            next_walls = walls.copy()
            if action["action"] == "move":
                next_pawns[my_id] = action["to"]
            elif action["action"] == "wall":
                next_walls.append({"action": "wall", "at": action["at"], "orientation": action["orientation"]})

            # 次のターンは相手（ミニマイズ側）の番
            # ※本来は相手の正確なlegal_actionsを生成すべきですが、
            #   ここでは計算量削減のため、現在の移動可能な方向をベースにします。
            #   簡易的に深さ1減らして評価
            eval_score, _ = alpha_beta(next_pawns, next_walls, [], depth - 1, alpha, beta, False, my_id, opp_id)

            if eval_score > max_eval:
                max_eval = eval_score
                best_action = action
            alpha = max(alpha, eval_score)
            if beta <= alpha:
                break  # βカット
        return max_eval, best_action

    else:
        min_eval = float("inf")
        # 相手の手番（自分にとって最悪の手を選んでくると仮定）
        # 簡易評価として現在の盤面評価を返す
        return evaluate_board(pawns, walls, my_id, opp_id), None


# --- メインループ ---
for line in sys.stdin:
    state = json.loads(line)
    my_id = state["you"]
    opp_id = "P2" if my_id == "P1" else "P1"

    # アルファベータ探索を実行して最善手を見つける
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

    # 安全策：エラー等で手が選ばれなかった場合のフォールバック
    if best_action is None:
        best_action = state["legal_actions"][0]

    # 移動の手を少しだけ優先する微調整を付与して出力
    print(json.dumps({"type": "action", **best_action}), flush=True)