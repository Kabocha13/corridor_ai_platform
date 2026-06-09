import json
import sys
from collections import deque


N = 9
COLS = "abcdefghi"
INF = 10**9


def pos_to_xy(pos):
    if isinstance(pos, str):
        text = pos.strip().lower()
        if len(text) >= 2:
            x = COLS.find(text[0])
            try:
                y = int(text[1:]) - 1
            except ValueError:
                return None
            if 0 <= x < N and 0 <= y < N:
                return x, y
    return None


def xy_to_pos(x, y):
    return f"{COLS[x]}{y + 1}"


def opponent(player):
    return "P2" if player == "P1" else "P1"


def goal_y(player):
    return N - 1 if player == "P1" else 0


def forward_dir(player):
    return 1 if player == "P1" else -1


def action_kind(action):
    if isinstance(action, dict) and action.get("action") in ("move", "wall"):
        return action["action"]
    return None


def parse_wall(wall):
    if not isinstance(wall, dict):
        return None
    at = pos_to_xy(wall.get("at"))
    orientation = wall.get("orientation")
    if isinstance(orientation, str):
        orientation = orientation.lower()[:1]
    if at is None or orientation not in ("h", "v"):
        return None
    return at[0], at[1], orientation


def wall_edges(wall):
    parsed = parse_wall(wall)
    if parsed is None:
        return []
    x, y, orientation = parsed
    if not (0 <= x < N - 1 and 0 <= y < N - 1):
        return []
    if orientation == "h":
        return [((x, y), (x, y + 1)), ((x + 1, y), (x + 1, y + 1))]
    return [((x, y), (x + 1, y)), ((x, y + 1), (x + 1, y + 1))]


def build_blocks(walls):
    blocked = set()
    if not isinstance(walls, list):
        return blocked
    for wall in walls:
        for a, b in wall_edges(wall):
            blocked.add((a, b))
            blocked.add((b, a))
    return blocked


def blocks_with(walls, action):
    next_walls = list(walls) if isinstance(walls, list) else []
    next_walls.append({"at": action.get("at"), "orientation": action.get("orientation")})
    return build_blocks(next_walls)


def neighbors(cell, blocked):
    x, y = cell
    result = []
    for dx, dy in ((0, 1), (1, 0), (0, -1), (-1, 0)):
        nxt = (x + dx, y + dy)
        if 0 <= nxt[0] < N and 0 <= nxt[1] < N and (cell, nxt) not in blocked:
            result.append(nxt)
    return result


def shortest_path(start, player, blocked):
    if start is None:
        return []
    target_y = goal_y(player)
    queue = deque([start])
    prev = {start: None}
    while queue:
        cell = queue.popleft()
        if cell[1] == target_y:
            path = []
            while cell is not None:
                path.append(cell)
                cell = prev[cell]
            return list(reversed(path))
        choices = neighbors(cell, blocked)
        choices.sort(key=lambda p: (abs(p[0] - 4), -p[1] if player == "P1" else p[1]))
        for nxt in choices:
            if nxt not in prev:
                prev[nxt] = cell
                queue.append(nxt)
    return []


def distance_to_goal(start, player, blocked):
    path = shortest_path(start, player, blocked)
    return len(path) - 1 if path else 99


def shortest_path_count(start, player, blocked, cap=500):
    if start is None:
        return cap
    target_y = goal_y(player)
    queue = deque([start])
    dist = {start: 0}
    count = {start: 1}
    best = None
    total = 0
    while queue:
        cell = queue.popleft()
        if best is not None and dist[cell] > best:
            continue
        if cell[1] == target_y:
            best = dist[cell]
            total = min(cap, total + count[cell])
            continue
        for nxt in neighbors(cell, blocked):
            nd = dist[cell] + 1
            if best is not None and nd > best:
                continue
            if nxt not in dist:
                dist[nxt] = nd
                count[nxt] = count[cell]
                queue.append(nxt)
            elif dist[nxt] == nd:
                count[nxt] = min(cap, count[nxt] + count[cell])
    return max(1, total) if total else cap


def remaining_walls(state, player):
    value = state.get("remaining_walls", 0)
    if isinstance(value, dict):
        value = value.get(player, 0)
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def center_score(cell):
    if cell is None:
        return 0
    x, y = cell
    return 8 - abs(x - 4) - abs(y - 4)


def blocks_path_score(action, path):
    edges = wall_edges({"at": action.get("at"), "orientation": action.get("orientation")})
    if not edges or len(path) < 2:
        return 0
    edge_set = set(edges)
    score = 0
    for i in range(len(path) - 1):
        edge = (path[i], path[i + 1])
        if edge in edge_set or (edge[1], edge[0]) in edge_set:
            score += 1
    return score


def move_score(action, player, my_pos, opp_pos, blocked, my_dist, opp_dist):
    dest = pos_to_xy(action.get("to"))
    nd = distance_to_goal(dest, player, blocked)
    if nd >= 99:
        return -INF

    score = 0
    score += (my_dist - nd) * 2400
    score -= nd * 260
    score += center_score(dest) * 55
    if my_pos is not None and dest is not None:
        score += (dest[1] - my_pos[1]) * forward_dir(player) * 900
    if opp_pos is not None and dest is not None:
        touch = abs(dest[0] - opp_pos[0]) + abs(dest[1] - opp_pos[1])
        if touch == 1:
            score += 160
    if nd >= my_dist:
        score -= 750
    if nd == 0:
        score += 100000
    if opp_dist <= 2:
        score += 250
    return score


def wall_score(action, player, opp, my_pos, opp_pos, walls, blocked, my_dist, opp_dist):
    next_blocked = blocks_with(walls, action)
    next_my_dist = distance_to_goal(my_pos, player, next_blocked)
    next_opp_dist = distance_to_goal(opp_pos, opp, next_blocked)
    if next_my_dist >= 99 or next_opp_dist >= 99:
        return -INF

    my_loss = next_my_dist - my_dist
    opp_loss = next_opp_dist - opp_dist
    gain = opp_loss - my_loss
    opp_path = shortest_path(opp_pos, opp, blocked)
    my_paths_now = shortest_path_count(my_pos, player, blocked)
    opp_paths_now = shortest_path_count(opp_pos, opp, blocked)
    my_paths_next = shortest_path_count(my_pos, player, next_blocked)
    opp_paths_next = shortest_path_count(opp_pos, opp, next_blocked)
    wall_pos = pos_to_xy(action.get("at"))

    score = 0
    score += opp_loss * 6200
    score -= my_loss * 4300
    score += gain * 2800
    score += (next_opp_dist - next_my_dist) * 360
    score += blocks_path_score(action, opp_path) * 1700
    score += center_score(wall_pos) * 75
    score += (my_paths_now - my_paths_next) * 12
    score += (opp_paths_next - opp_paths_now) * 16

    if my_loss <= 0:
        score += 900
    if opp_loss >= 1:
        score += 1800
    if opp_loss >= 2:
        score += 2800
    if gain <= 0:
        score -= 2600
    if opp_dist <= 5:
        score += 2500
    if my_dist + 2 <= opp_dist:
        score -= 2200
    return score


def stable_tiebreak(action):
    text = json.dumps(action, sort_keys=True, separators=(",", ":"))
    return sum(ord(ch) for ch in text) % 97


def choose_action(state):
    legal = state.get("legal_actions", [])
    if not isinstance(legal, list) or not legal:
        return {"action": "move", "to": "e1"}

    legal = [a for a in legal if isinstance(a, dict) and action_kind(a)]
    if not legal:
        return {"action": "move", "to": "e1"}

    player = state.get("you", "P1")
    opp = opponent(player)
    pawns = state.get("pawns", {})
    my_pos = pos_to_xy(pawns.get(player)) if isinstance(pawns, dict) else None
    opp_pos = pos_to_xy(pawns.get(opp)) if isinstance(pawns, dict) else None
    walls = state.get("walls", [])
    blocked = build_blocks(walls)
    my_dist = distance_to_goal(my_pos, player, blocked)
    opp_dist = distance_to_goal(opp_pos, opp, blocked)
    rem = remaining_walls(state, player)

    moves = [a for a in legal if action_kind(a) == "move"]
    wall_actions = [a for a in legal if action_kind(a) == "wall"]

    best_move = None
    best_move_score = -INF
    for action in moves:
        score = move_score(action, player, my_pos, opp_pos, blocked, my_dist, opp_dist)
        score += stable_tiebreak(action)
        if score > best_move_score:
            best_move = action
            best_move_score = score

    best_wall = None
    best_wall_score = -INF
    if rem > 0:
        for action in wall_actions:
            score = wall_score(action, player, opp, my_pos, opp_pos, walls, blocked, my_dist, opp_dist)
            score += stable_tiebreak(action)
            if score > best_wall_score:
                best_wall = action
                best_wall_score = score

    if best_wall is not None:
        should_wall = False
        if opp_dist <= 5 and best_wall_score > best_move_score - 1600:
            should_wall = True
        if opp_dist <= my_dist + 1 and best_wall_score > best_move_score - 900:
            should_wall = True
        if best_wall_score > best_move_score + 1200:
            should_wall = True
        if my_dist <= 2 and best_move is not None:
            should_wall = False
        if should_wall:
            return best_wall

    return best_move or best_wall or legal[0]


def legal_output(action):
    if not isinstance(action, dict):
        return {"type": "action", "action": "move", "to": "e1"}
    if action.get("action") == "move":
        return {"type": "action", "action": "move", "to": action.get("to")}
    if action.get("action") == "wall":
        return {
            "type": "action",
            "action": "wall",
            "at": action.get("at"),
            "orientation": action.get("orientation"),
        }
    return {"type": "action", **action}


def main():
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        state = None
        try:
            state = json.loads(line)
            answer = legal_output(choose_action(state))
        except Exception as exc:
            print(f"codex_55 fallback: {exc}", file=sys.stderr, flush=True)
            legal = state.get("legal_actions", []) if isinstance(state, dict) else []
            if isinstance(legal, list) and legal and isinstance(legal[0], dict):
                answer = legal_output(legal[0])
            else:
                answer = {"type": "action", "action": "move", "to": "e1"}
        print(json.dumps(answer, ensure_ascii=False, separators=(",", ":")), flush=True)


if __name__ == "__main__":
    main()
