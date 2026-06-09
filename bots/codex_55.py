import json
import sys
from collections import deque


N = 9
COLS = "abcdefghi"
INF = 10**9
WIN = 10**8


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


def advancement(player, cell):
    if cell is None:
        return 0
    return cell[1] if player == "P1" else N - 1 - cell[1]


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


def wall_signature(action):
    if not isinstance(action, dict) or action.get("action") != "wall":
        return None
    parsed = parse_wall(action)
    if parsed is None:
        return None
    x, y, orientation = parsed
    return xy_to_pos(x, y), orientation


def action_signature(action):
    if not isinstance(action, dict):
        return None
    if action.get("action") == "move":
        return "move", action.get("to")
    if action.get("action") == "wall":
        sig = wall_signature(action)
        if sig is None:
            return None
        return "wall", sig[0], sig[1]
    return None


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


def move_neighbors(cell, blocked, player=None):
    if cell is None:
        return []
    if player == "P1":
        dirs = ((0, 1), (-1, 0), (1, 0), (0, -1))
    elif player == "P2":
        dirs = ((0, -1), (-1, 0), (1, 0), (0, 1))
    else:
        dirs = ((0, 1), (1, 0), (0, -1), (-1, 0))
    x, y = cell
    result = []
    for dx, dy in dirs:
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


def has_path(start, player, blocked):
    return distance_to_goal(start, player, blocked) < 99


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


def wall_overlaps(walls, action):
    sig = wall_signature(action)
    if sig is None:
        return True
    at, orientation = sig
    new_edges = set(wall_edges({"at": at, "orientation": orientation}))
    for wall in walls:
        other = wall_signature(wall)
        if other is None:
            continue
        if other[0] == at and other[1] != orientation:
            return True
        if new_edges & set(wall_edges(wall)):
            return True
    return False


def legal_sim_actions(sim_state):
    player = sim_state.get("turn", sim_state.get("you", "P1"))
    opp = opponent(player)
    pawns = sim_state.get("pawns", {})
    walls = sim_state.get("walls", [])
    blocked = build_blocks(walls)
    here = pos_to_xy(pawns.get(player)) if isinstance(pawns, dict) else None
    occupied = pos_to_xy(pawns.get(opp)) if isinstance(pawns, dict) else None

    actions = []
    for nxt in move_neighbors(here, blocked, player):
        if nxt != occupied:
            actions.append({"action": "move", "to": xy_to_pos(nxt[0], nxt[1])})

    if remaining_walls(sim_state, player) <= 0:
        return actions

    my_pos = here
    opp_pos = occupied
    for x in range(N - 1):
        for y in range(N - 1):
            at = xy_to_pos(x, y)
            for orientation in ("h", "v"):
                action = {"action": "wall", "at": at, "orientation": orientation}
                if wall_overlaps(walls, action):
                    continue
                next_blocked = blocks_with(walls, action)
                if has_path(my_pos, player, next_blocked) and has_path(opp_pos, opp, next_blocked):
                    actions.append(action)
    return actions


def apply_sim_action(sim_state, action):
    player = sim_state.get("turn", sim_state.get("you", "P1"))
    next_state = {
        "you": sim_state.get("you", player),
        "turn": opponent(player),
        "pawns": dict(sim_state.get("pawns", {})),
        "walls": list(sim_state.get("walls", [])),
        "remaining_walls": dict(sim_state.get("remaining_walls", {})),
    }
    if action_kind(action) == "move":
        next_state["pawns"][player] = action.get("to")
    elif action_kind(action) == "wall":
        sig = wall_signature(action)
        if sig is not None:
            next_state["walls"].append({"action": "wall", "at": sig[0], "orientation": sig[1]})
            next_state["remaining_walls"][player] = max(0, remaining_walls(next_state, player) - 1)
    return next_state


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


def wall_near_path_score(action, path):
    parsed = parse_wall(action)
    if parsed is None or not path:
        return 0
    x, y, _ = parsed
    cells = ((x, y), (x + 1, y), (x, y + 1), (x + 1, y + 1))
    best = 999
    for cell in cells:
        for idx, path_cell in enumerate(path):
            dist = abs(cell[0] - path_cell[0]) + abs(cell[1] - path_cell[1])
            best = min(best, dist * 10 + idx)
    return max(0, 120 - best * 3)


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


def evaluate_position(sim_state, root_player):
    opp = opponent(root_player)
    pawns = sim_state.get("pawns", {})
    walls = sim_state.get("walls", [])
    blocked = build_blocks(walls)
    my_pos = pos_to_xy(pawns.get(root_player)) if isinstance(pawns, dict) else None
    opp_pos = pos_to_xy(pawns.get(opp)) if isinstance(pawns, dict) else None
    my_dist = distance_to_goal(my_pos, root_player, blocked)
    opp_dist = distance_to_goal(opp_pos, opp, blocked)

    if my_dist == 0:
        return WIN
    if opp_dist == 0:
        return -WIN

    my_path_count = shortest_path_count(my_pos, root_player, blocked)
    opp_path_count = shortest_path_count(opp_pos, opp, blocked)
    my_adv = my_pos[1] if root_player == "P1" and my_pos else N - 1 - my_pos[1] if my_pos else 0
    opp_adv = opp_pos[1] if opp == "P1" and opp_pos else N - 1 - opp_pos[1] if opp_pos else 0

    score = 0
    score += (opp_dist - my_dist) * 14500
    score -= my_dist * 650
    score += opp_dist * 450
    score += (my_adv - opp_adv) * 900
    score += center_score(my_pos) * 70
    score -= center_score(opp_pos) * 45
    score += (remaining_walls(sim_state, root_player) - remaining_walls(sim_state, opp)) * 260
    score += (opp_path_count - my_path_count) * 18
    if my_dist <= 2:
        score += (3 - my_dist) * 4500
    if opp_dist <= 2:
        score -= (3 - opp_dist) * 5200
    return score


def tactical_score(sim_state, action, player):
    opp = opponent(player)
    pawns = sim_state.get("pawns", {})
    walls = sim_state.get("walls", [])
    blocked = build_blocks(walls)
    my_pos = pos_to_xy(pawns.get(player)) if isinstance(pawns, dict) else None
    opp_pos = pos_to_xy(pawns.get(opp)) if isinstance(pawns, dict) else None
    my_dist = distance_to_goal(my_pos, player, blocked)
    opp_dist = distance_to_goal(opp_pos, opp, blocked)
    if action_kind(action) == "move":
        return move_score(action, player, my_pos, opp_pos, blocked, my_dist, opp_dist)
    score = wall_score(action, player, opp, my_pos, opp_pos, walls, blocked, my_dist, opp_dist)
    opp_path = shortest_path(opp_pos, opp, blocked)
    my_path = shortest_path(my_pos, player, blocked)
    score += blocks_path_score(action, opp_path) * 900
    score -= blocks_path_score(action, my_path) * 1600
    score += wall_near_path_score(action, opp_path) * 9
    return score


def ordered_candidates(sim_state, player, limit):
    actions = legal_sim_actions(sim_state)
    if not actions:
        return []
    for action in actions:
        if action_kind(action) == "move":
            to = pos_to_xy(action.get("to"))
            if to is not None and to[1] == goal_y(player):
                return [action]
    scored = []
    for action in actions:
        scored.append((tactical_score(sim_state, action, player) + stable_tiebreak(action), action))
    scored.sort(key=lambda item: item[0], reverse=True)
    return [action for _, action in scored[:limit]]


def search(sim_state, root_player, depth, alpha, beta):
    turn = sim_state.get("turn", root_player)
    base = evaluate_position(sim_state, root_player)
    if depth <= 0 or abs(base) >= WIN:
        return base

    maximizing = turn == root_player
    candidates = ordered_candidates(sim_state, turn, 8 if depth >= 2 else 6)
    if not candidates:
        return base

    if maximizing:
        value = -INF
        for action in candidates:
            value = max(value, search(apply_sim_action(sim_state, action), root_player, depth - 1, alpha, beta))
            alpha = max(alpha, value)
            if alpha >= beta:
                break
        return value

    value = INF
    for action in candidates:
        value = min(value, search(apply_sim_action(sim_state, action), root_player, depth - 1, alpha, beta))
        beta = min(beta, value)
        if alpha >= beta:
            break
    return value


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
        # Do not let early wall tactics pin us to our own back rank forever.
        my_adv = advancement(player, my_pos)
        if my_adv <= 2 and my_dist >= opp_dist:
            should_wall = False
        if my_dist <= opp_dist - 2 and opp_dist > 3:
            should_wall = False
        if should_wall:
            return best_wall

    tactical_choice = best_move or best_wall or legal[0]

    sim_state = {
        "you": player,
        "turn": player,
        "pawns": dict(state.get("pawns", {})),
        "walls": list(walls) if isinstance(walls, list) else [],
        "remaining_walls": dict(state.get("remaining_walls", {}))
        if isinstance(state.get("remaining_walls", {}), dict)
        else {player: rem, opp: 0},
    }
    root_candidates = ordered_candidates(sim_state, player, 12)
    legal_by_sig = {action_signature(a): a for a in legal}

    best_action = tactical_choice
    best_score = -INF
    for action in root_candidates:
        sig = action_signature(action)
        if sig not in legal_by_sig:
            continue
        score = search(apply_sim_action(sim_state, action), player, 1, -INF, INF)
        if action_kind(action) == "wall":
            my_adv = advancement(player, my_pos)
            if my_adv <= 2:
                score -= 14000
            if my_dist <= opp_dist - 2 and opp_dist > 3:
                score -= 10000
        score += tactical_score(sim_state, action, player) * 0.08
        score += stable_tiebreak(action)
        if score > best_score:
            best_score = score
            best_action = legal_by_sig[sig]

    return best_action


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
