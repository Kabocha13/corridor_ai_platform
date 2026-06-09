import json
import random
import sys
from collections import deque


BOARD_N = 9
INF = 999
RNG = random.Random()
_PATH_CACHE = {}
_CTX_CACHE = {}


def pos_to_rc(pos):
    return int(pos[1:]) - 1, ord(pos[0]) - 97


def rc_to_pos(r, c):
    return chr(97 + c) + str(r + 1)


def opponent(player):
    return "P2" if player == "P1" else "P1"


def goal_row(player):
    return 8 if player == "P1" else 0


def forward_dir(player):
    return 1 if player == "P1" else -1


def parse_walls(state):
    walls = []
    for wall in state.get("walls", []):
        try:
            r, c = pos_to_rc(wall["at"])
            o = wall["orientation"]
        except Exception:
            continue
        if 0 <= r < 8 and 0 <= c < 8 and o in ("h", "v"):
            walls.append((r, c, o))
    return tuple(walls)


def _normalize_wall(wall):
    if wall is None:
        return None
    if isinstance(wall, tuple):
        return wall
    r, c = pos_to_rc(wall["at"])
    return (r, c, wall["orientation"])


def blocked(r1, c1, r2, c2, walls):
    for wr, wc, orientation in walls:
        if orientation == "h":
            if r2 == r1 + 1 and r1 == wr and c1 in (wc, wc + 1):
                return True
            if r2 == r1 - 1 and r2 == wr and c1 in (wc, wc + 1):
                return True
        else:
            if c2 == c1 + 1 and c1 == wc and r1 in (wr, wr + 1):
                return True
            if c2 == c1 - 1 and c2 == wc and r1 in (wr, wr + 1):
                return True
    return False


def neighbors(pos, walls):
    r, c = pos_to_rc(pos)
    out = []
    for dr, dc in ((1, 0), (-1, 0), (0, -1), (0, 1)):
        nr, nc = r + dr, c + dc
        if 0 <= nr < BOARD_N and 0 <= nc < BOARD_N and not blocked(r, c, nr, nc, walls):
            out.append(rc_to_pos(nr, nc))
    return out


def _state_key(state):
    pawns = state.get("pawns", {})
    return (
        state.get("you", "P1"),
        pawns.get("P1", ""),
        pawns.get("P2", ""),
        parse_walls(state),
    )


def _ordered_dirs(player):
    if player == "P1":
        return ((1, 0), (0, -1), (0, 1), (-1, 0))
    return ((-1, 0), (0, -1), (0, 1), (1, 0))


def _path_data(state, player, start_pos=None, extra_wall=None, want_route=False):
    pawns = state.get("pawns", {})
    start_pos = start_pos or pawns.get(player)
    if not start_pos:
        return (INF, []) if want_route else (INF, None)

    extra = _normalize_wall(extra_wall)
    key = (_state_key(state), player, start_pos, extra, want_route)
    cached = _PATH_CACHE.get(key)
    if cached is not None:
        return cached

    if len(_PATH_CACHE) > 12000:
        _PATH_CACHE.clear()

    walls = parse_walls(state)
    if extra is not None:
        walls = walls + (extra,)

    sr, sc = pos_to_rc(start_pos)
    if not (0 <= sr < BOARD_N and 0 <= sc < BOARD_N):
        return (INF, []) if want_route else (INF, None)

    target = goal_row(player)
    start = sr * BOARD_N + sc
    q = deque([start])
    dist = [-1] * (BOARD_N * BOARD_N)
    parent = [-1] * (BOARD_N * BOARD_N) if want_route else None
    dist[start] = 0
    dirs = _ordered_dirs(player)

    while q:
        cur = q.popleft()
        r, c = divmod(cur, BOARD_N)
        d = dist[cur]
        if r == target:
            if not want_route:
                result = (d, None)
            else:
                route = []
                x = cur
                while x != -1:
                    rr, cc = divmod(x, BOARD_N)
                    route.append(rc_to_pos(rr, cc))
                    x = parent[x]
                route.reverse()
                result = (d, route)
            _PATH_CACHE[key] = result
            return result

        for dr, dc in dirs:
            nr, nc = r + dr, c + dc
            if not (0 <= nr < BOARD_N and 0 <= nc < BOARD_N):
                continue
            nxt = nr * BOARD_N + nc
            if dist[nxt] != -1 or blocked(r, c, nr, nc, walls):
                continue
            dist[nxt] = d + 1
            if want_route:
                parent[nxt] = cur
            q.append(nxt)

    result = (INF, []) if want_route else (INF, None)
    _PATH_CACHE[key] = result
    return result


def shortest_path(state, player, start_pos=None, extra_wall=None):
    return _path_data(state, player, start_pos, extra_wall, False)[0]


def shortest_path_route(state, player):
    return _path_data(state, player, None, None, True)[1]


def _wall_blocks_edge(wall_action, a, b):
    try:
        r1, c1 = pos_to_rc(a)
        r2, c2 = pos_to_rc(b)
        wall = (_normalize_wall(wall_action),)
    except Exception:
        return False
    return blocked(r1, c1, r2, c2, wall)


def _wall_route_bonus(action, route, op_pos):
    if not route or len(route) < 2:
        return 0

    bonus = 0
    for i in range(len(route) - 1):
        if _wall_blocks_edge(action, route[i], route[i + 1]):
            if i == 0:
                bonus += 70
            elif i <= 2:
                bonus += 45
            elif i <= 5:
                bonus += 25
            else:
                bonus += 10
            break

    wr, wc, orientation = _normalize_wall(action)
    pr, pc = pos_to_rc(op_pos)
    near = abs(wr - pr) + abs(wc - pc)
    if near <= 1:
        bonus += 18
    elif near == 2:
        bonus += 8

    if orientation == "h":
        if wr == pr or wr == pr - 1:
            bonus += 10
    else:
        if abs(wc - pc) <= 1 and abs(wr - pr) <= 2:
            bonus += 4

    return bonus


def _context(state):
    key = _state_key(state)
    cached = _CTX_CACHE.get(key)
    if cached is not None:
        return cached
    if len(_CTX_CACHE) > 256:
        _CTX_CACHE.clear()

    you = state.get("you", "P1")
    op = opponent(you)
    pawns = state.get("pawns", {})
    ctx = {
        "you": you,
        "op": op,
        "my_pos": pawns.get(you, "e1" if you == "P1" else "e9"),
        "op_pos": pawns.get(op, "e9" if op == "P2" else "e1"),
        "my_dist": shortest_path(state, you),
        "op_dist": shortest_path(state, op),
        "my_route": shortest_path_route(state, you),
        "op_route": shortest_path_route(state, op),
        "my_walls": state.get("remaining_walls", {}).get(you, 0),
        "op_walls": state.get("remaining_walls", {}).get(op, 0),
        "turn_index": state.get("turn_index", 0),
    }
    _CTX_CACHE[key] = ctx
    return ctx


def _center_score(pos):
    r, c = pos_to_rc(pos)
    return -abs(c - 4) * 1.3 - abs(r - 4) * 0.15


def evaluate_move(state, action):
    ctx = _context(state)
    you = ctx["you"]
    my_dist = ctx["my_dist"]
    op_dist = ctx["op_dist"]
    my_pos = ctx["my_pos"]
    to_pos = action.get("to", my_pos)
    new_my_dist = shortest_path(state, you, start_pos=to_pos)

    if new_my_dist <= 0:
        return 100000
    if my_dist >= INF or new_my_dist >= INF:
        return -100000

    old_r, old_c = pos_to_rc(my_pos)
    new_r, new_c = pos_to_rc(to_pos)
    signed_forward = (new_r - old_r) * forward_dir(you)
    dist_gain = my_dist - new_my_dist

    score = 0
    score += 116 * dist_gain
    score += 8 * (op_dist - new_my_dist)
    score -= 4.0 * new_my_dist
    score += 16 * signed_forward
    score += _center_score(to_pos)

    route = ctx["my_route"]
    if len(route) >= 2 and to_pos == route[1]:
        score += 42
    elif to_pos in route[1:4]:
        score += 22

    if dist_gain <= 0:
        score -= 38
    if signed_forward < 0:
        score -= 65
    if abs(new_c - old_c) > 0 and dist_gain <= 0:
        score -= 24
    if abs(new_c - old_c) > 0 and op_dist > new_my_dist + 1:
        score -= 8

    if new_my_dist <= 3:
        score += 35 * (4 - new_my_dist)
    if new_my_dist < op_dist:
        score += 24
    if new_my_dist + 2 < op_dist:
        score += 34
    if ctx["my_walls"] <= 2 or my_dist <= 4:
        score += 18
    if op_dist <= 2 and new_my_dist > 1:
        score -= 22

    return score


def evaluate_wall(state, action):
    ctx = _context(state)
    you = ctx["you"]
    op = ctx["op"]
    my_dist = ctx["my_dist"]
    op_dist = ctx["op_dist"]
    my_walls = ctx["my_walls"]

    if my_walls <= 0:
        return -100000
    if my_dist <= 1:
        return -100000

    new_my_dist = shortest_path(state, you, extra_wall=action)
    new_op_dist = shortest_path(state, op, extra_wall=action)
    if new_my_dist >= INF or new_op_dist >= INF:
        return -100000

    op_delta = new_op_dist - op_dist
    my_delta = new_my_dist - my_dist

    score = 0
    score += 150 * op_delta
    score -= 95 * max(0, my_delta)
    score += _wall_route_bonus(action, ctx["op_route"], ctx["op_pos"])

    if op_delta <= 0:
        score -= 155
    elif op_delta == 1:
        score += 18
    else:
        score += 38 * (op_delta - 1)

    if my_delta >= 2:
        score -= 150 + 70 * (my_delta - 2)
    elif my_delta < 0:
        score += 28

    if op_dist <= 3 and op_delta > 0:
        score += 115 + 65 * (4 - op_dist) + 28 * op_delta
    elif op_dist <= 4 and op_delta > 0:
        score += 55

    if op_dist <= my_dist and op_delta > 0:
        score += 75 + 16 * (my_dist - op_dist)
    if op_dist > my_dist + 2:
        score -= 60
    if my_dist <= 3:
        score -= 150
    elif my_dist <= 4:
        score -= 70

    if my_walls <= 1:
        score -= 120
    elif my_walls <= 3:
        score -= 38

    turn_index = ctx["turn_index"]
    if turn_index >= 110:
        score -= 70
    elif turn_index >= 70:
        score -= 30

    if ctx["op_walls"] == 0 and my_dist < op_dist:
        score -= 45
    if my_dist + 3 <= op_dist and my_dist <= 6:
        score -= 95

    wr, wc, orientation = _normalize_wall(action)
    op_r, op_c = pos_to_rc(ctx["op_pos"])
    direction = forward_dir(op)
    if orientation == "h":
        if (wr - op_r) * direction >= 0:
            score += 10
        else:
            score -= 18
    else:
        if abs(wc - op_c) > 2:
            score -= 12

    return score


def choose_action(state):
    legal = state.get("legal_actions", [])
    if not legal:
        you = state.get("you", "P1")
        pos = state.get("pawns", {}).get(you, "e1" if you == "P1" else "e9")
        return {"action": "move", "to": pos}

    ctx = _context(state)
    best_score = None
    best_actions = []
    best_move_score = None
    best_move = None

    for action in legal:
        try:
            if action.get("action") == "move":
                score = evaluate_move(state, action)
                if best_move_score is None or score > best_move_score:
                    best_move_score = score
                    best_move = action
            elif action.get("action") == "wall":
                score = evaluate_wall(state, action)
            else:
                score = -100000
        except Exception as e:
            print("eval error:", e, file=sys.stderr, flush=True)
            score = -100000

        if best_score is None or score > best_score + 1e-9:
            best_score = score
            best_actions = [action]
        elif abs(score - best_score) <= 1e-9:
            best_actions.append(action)

    if best_move is not None:
        my_dist = ctx["my_dist"]
        op_dist = ctx["op_dist"]
        if my_dist <= 4 and best_score is not None and best_score < best_move_score + 85:
            return best_move
        if op_dist > my_dist + 2 and best_score is not None and best_score < best_move_score + 70:
            return best_move
        if ctx["my_walls"] <= 1 and best_score is not None and best_score < best_move_score + 55:
            return best_move

    return RNG.choice(best_actions) if best_actions else legal[0]


def with_type(action):
    out = {"type": "action"}
    if isinstance(action, dict):
        out.update(action)
    out["type"] = "action"
    return out


def _fallback_action_from_line(line):
    try:
        state = json.loads(line)
        legal = state.get("legal_actions", [])
        if legal:
            return with_type(legal[0])
        you = state.get("you", "P1")
        pos = state.get("pawns", {}).get(you, "e1" if you == "P1" else "e9")
        return {"type": "action", "action": "move", "to": pos}
    except Exception:
        return {"type": "action", "action": "move", "to": "e1"}


def main():
    for line in sys.stdin:
        try:
            state = json.loads(line)
            action = choose_action(state)
            print(json.dumps(with_type(action), separators=(",", ":")), flush=True)
        except Exception as e:
            print("error:", e, file=sys.stderr, flush=True)
            print(json.dumps(_fallback_action_from_line(line), separators=(",", ":")), flush=True)


if __name__ == "__main__":
    main()