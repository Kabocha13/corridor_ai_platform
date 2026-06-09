import sys
import json
from collections import deque

N = 9
INF = 10**9


def parse_pos(s):
    if not isinstance(s, str) or len(s) < 2:
        return None
    c = s[0].lower()
    if c < "a" or c > "i":
        return None
    try:
        y = int(s[1:])
    except Exception:
        return None
    x = ord(c) - ord("a") + 1
    if 1 <= x <= N and 1 <= y <= N:
        return x, y
    return None


def pos_to_str(p):
    return chr(ord("a") + p[0] - 1) + str(p[1])


def opponent(p):
    if p == "P1":
        return "P2"
    return "P1"


def goal_row(player):
    if player == "P1":
        return N
    return 1


def is_goal(pos, player):
    return pos is not None and pos[1] == goal_row(player)


def pawn(state, player):
    ps = state.get("pawns", {})
    if not isinstance(ps, dict):
        return None
    return parse_pos(ps.get(player))


def remaining_walls(state, player):
    r = state.get("remaining_walls", 0)
    if isinstance(r, dict):
        r = r.get(player, 0)
    try:
        return int(r)
    except Exception:
        return 0


def norm_ori(o):
    if not isinstance(o, str) or not o:
        return None
    o = o.lower()
    if o.startswith("h"):
        return "h"
    if o.startswith("v"):
        return "v"
    return None


def wall_info(a):
    if not isinstance(a, dict):
        return None
    p = parse_pos(a.get("at"))
    o = norm_ori(a.get("orientation"))
    if p is None or o is None:
        return None
    x, y = p
    if not (1 <= x <= N - 1 and 1 <= y <= N - 1):
        return None
    return x, y, o


def edge(a, b):
    return tuple(sorted((a, b)))


def wall_edges_from_info(w):
    if w is None:
        return []
    x, y, o = w
    if o == "h":
        return [
            edge((x, y), (x, y + 1)),
            edge((x + 1, y), (x + 1, y + 1))
        ]
    return [
        edge((x, y), (x + 1, y)),
        edge((x, y + 1), (x + 1, y + 1))
    ]


def wall_key_from_info(w):
    if w is None:
        return None
    x, y, o = w
    return x, y, o


def wall_cross_key_from_info(w):
    if w is None:
        return None
    x, y, o = w
    if o == "h":
        return x, y, "v"
    return x, y, "h"


def read_walls(state):
    ws = state.get("walls", [])
    blocked = set()
    placed = set()

    if not isinstance(ws, list):
        return blocked, placed

    for a in ws:
        w = wall_info(a)
        if w is None:
            continue
        placed.add(wall_key_from_info(w))
        for e in wall_edges_from_info(w):
            blocked.add(e)

    return blocked, placed


def add_wall(blocked, placed, a):
    w = wall_info(a)
    nb = set(blocked)
    np = set(placed)

    if w is None:
        return nb, np

    np.add(wall_key_from_info(w))
    for e in wall_edges_from_info(w):
        nb.add(e)

    return nb, np


def basic_neighbors(pos, blocked, player=None):
    x, y = pos

    if player == "P1":
        dirs = [(0, 1), (-1, 0), (1, 0), (0, -1)]
    elif player == "P2":
        dirs = [(0, -1), (-1, 0), (1, 0), (0, 1)]
    else:
        dirs = [(0, 1), (0, -1), (-1, 0), (1, 0)]

    res = []

    for dx, dy in dirs:
        np = (x + dx, y + dy)
        if not (1 <= np[0] <= N and 1 <= np[1] <= N):
            continue
        if edge(pos, np) in blocked:
            continue
        res.append(np)

    return res


def shortest_path(start, player, blocked):
    if start is None:
        return INF, []

    q = deque([start])
    dist = {start: 0}
    prev = {}

    while q:
        cur = q.popleft()

        if is_goal(cur, player):
            path = []
            p = cur
            while True:
                path.append(p)
                if p not in prev:
                    break
                p = prev[p]
            path.reverse()
            return dist[cur], path

        for nxt in basic_neighbors(cur, blocked, player):
            if nxt in dist:
                continue
            dist[nxt] = dist[cur] + 1
            prev[nxt] = cur
            q.append(nxt)

    return INF, []


def all_distances_to_goal(player, blocked):
    q = deque()
    dist = {}

    gy = goal_row(player)

    for x in range(1, N + 1):
        p = (x, gy)
        dist[p] = 0
        q.append(p)

    while q:
        cur = q.popleft()
        for nxt in basic_neighbors(cur, blocked, None):
            if nxt in dist:
                continue
            dist[nxt] = dist[cur] + 1
            q.append(nxt)

    return dist


def action_kind(a):
    if not isinstance(a, dict):
        return None
    return a.get("action")


def legal_moves(actions):
    res = []
    if not isinstance(actions, list):
        return res
    for a in actions:
        if not isinstance(a, dict):
            continue
        if action_kind(a) != "move":
            continue
        if parse_pos(a.get("to")) is None:
            continue
        res.append(a)
    return res


def legal_walls(actions):
    res = []
    if not isinstance(actions, list):
        return res
    for a in actions:
        if not isinstance(a, dict):
            continue
        if action_kind(a) != "wall":
            continue
        if wall_info(a) is None:
            continue
        res.append(a)
    return res


def output_action(a):
    if not isinstance(a, dict):
        return {"type": "action", "action": "move", "to": "e1"}

    res = {"type": "action"}
    for k, v in a.items():
        if k != "type":
            res[k] = v
    return res


def progress(old, new, player):
    if old is None or new is None:
        return 0
    if player == "P1":
        return new[1] - old[1]
    return old[1] - new[1]


def side_center(p):
    if p is None:
        return 0
    return -abs(p[0] - 5)


def path_cells_score(path, pos):
    if not path or pos is None:
        return 0
    for i, p in enumerate(path):
        if p == pos:
            return 30 - i * 3
    return 0


def direction_to_goal(player):
    if player == "P1":
        return 1
    return -1


def move_after_state(state, move_action):
    you = state.get("you")
    ps = dict(state.get("pawns", {}))
    ps[you] = move_action.get("to")
    ns = dict(state)
    ns["pawns"] = ps
    return ns


def eval_position(my_pos, enemy_pos, you, blocked):
    enemy = opponent(you)

    my_d, my_path = shortest_path(my_pos, you, blocked)
    en_d, en_path = shortest_path(enemy_pos, enemy, blocked)

    score = 0
    score += (en_d - my_d) * 1000
    score += en_d * 90
    score -= my_d * 140
    score += side_center(my_pos) * 12
    score -= side_center(enemy_pos) * 4

    if my_d == 0:
        score += 10000000
    if en_d == 0:
        score -= 10000000

    if my_path and len(my_path) >= 2:
        score += path_cells_score(my_path, my_path[1])

    if en_path and len(en_path) <= 3:
        score -= 2500

    return score


def move_score(state, a, blocked):
    you = state.get("you")
    enemy = opponent(you)
    my = pawn(state, you)
    en = pawn(state, enemy)
    to = parse_pos(a.get("to"))

    if to is None:
        return -INF

    my_d, my_path = shortest_path(to, you, blocked)
    en_d, en_path = shortest_path(en, enemy, blocked)

    score = 0
    score += (en_d - my_d) * 1100
    score -= my_d * 170
    score += en_d * 80
    score += progress(my, to, you) * 260
    score += side_center(to) * 15

    if is_goal(to, you):
        score += 10000000

    if my_path and len(my_path) >= 1:
        score += path_cells_score(my_path, to)

    if en_path and len(en_path) <= 2:
        score -= 3000

    dx = abs(to[0] - en[0]) if en else 0
    dy = abs(to[1] - en[1]) if en else 0
    if dx + dy == 1:
        score += 80

    return score


def best_move(state, moves, blocked):
    best = None
    best_s = -INF
    for a in moves:
        s = move_score(state, a, blocked)
        if s > best_s:
            best_s = s
            best = a
    return best, best_s


def path_block_gain(path, w):
    if not path or len(path) < 2:
        return 0
    es = set(wall_edges_from_info(w))
    gain = 0
    for i in range(len(path) - 1):
        if edge(path[i], path[i + 1]) in es:
            gain += 1
    return gain


def wall_near_path_score(path, w):
    if not path:
        return 0

    x, y, o = w
    cells = []

    if o == "h":
        cells = [(x, y), (x + 1, y), (x, y + 1), (x + 1, y + 1)]
    else:
        cells = [(x, y), (x, y + 1), (x + 1, y), (x + 1, y + 1)]

    best = 99

    for c in cells:
        for i, p in enumerate(path):
            d = abs(c[0] - p[0]) + abs(c[1] - p[1])
            if d + i * 0.15 < best:
                best = d + i * 0.15

    return int(max(0, 40 - best * 12))


def wall_shape_score(w, enemy_pos, enemy_player):
    if w is None or enemy_pos is None:
        return 0

    x, y, o = w
    ex, ey = enemy_pos
    s = 0

    if enemy_player == "P1":
        front_y = ey
    else:
        front_y = ey - 1

    if o == "h":
        if abs(y - front_y) <= 1:
            s += 90
        if abs(x - ex) <= 1:
            s += 50
    else:
        if abs(x - ex) <= 1:
            s += 25
        if abs(y - ey) <= 2:
            s += 20

    s -= (abs(x - ex) + abs(y - ey)) * 8
    return s


def wall_score(state, a, blocked):
    you = state.get("you")
    enemy = opponent(you)

    my = pawn(state, you)
    en = pawn(state, enemy)

    base_my_d, base_my_path = shortest_path(my, you, blocked)
    base_en_d, base_en_path = shortest_path(en, enemy, blocked)

    nb, _ = add_wall(blocked, set(), a)

    my_d, my_path = shortest_path(my, you, nb)
    en_d, en_path = shortest_path(en, enemy, nb)

    if my_d >= INF or en_d >= INF:
        return -INF, 0, 0

    gain = en_d - base_en_d
    pain = my_d - base_my_d

    w = wall_info(a)

    s = 0
    s += gain * 2200
    s -= pain * 1700
    s += (en_d - my_d) * 160
    s += wall_shape_score(w, en, enemy)
    s += wall_near_path_score(base_en_path, w)
    s += path_block_gain(base_en_path, w) * 600
    s -= path_block_gain(base_my_path, w) * 450

    if base_en_d <= base_my_d:
        s += 600
    if base_en_d <= 5:
        s += 400
    if base_en_d <= 3:
        s += 900
    if base_en_d <= 2:
        s += 1600

    if gain <= 0:
        s -= 3000
    if pain > gain:
        s -= (pain - gain) * 1600
    if pain > 2:
        s -= 2000

    if gain >= 2 and pain <= 1:
        s += 900
    if gain >= 3:
        s += 1300
    if gain >= 4:
        s += 2000

    return s, gain, pain


def best_wall(state, walls, blocked):
    best = None
    best_s = -INF
    best_gain = 0
    best_pain = 0

    for a in walls:
        s, g, p = wall_score(state, a, blocked)
        if s > best_s:
            best_s = s
            best = a
            best_gain = g
            best_pain = p

    return best, best_s, best_gain, best_pain


def should_wall(state, wall_s, gain, pain, blocked):
    you = state.get("you")
    enemy = opponent(you)

    rw = remaining_walls(state, you)
    if rw <= 0:
        return False

    my = pawn(state, you)
    en = pawn(state, enemy)

    my_d, _ = shortest_path(my, you, blocked)
    en_d, _ = shortest_path(en, enemy, blocked)

    if my_d <= 1:
        return False

    if en_d <= 2 and gain >= 1 and pain <= 2:
        return True

    if en_d <= 3 and gain >= 1 and pain <= 1:
        return True

    if gain >= 4 and pain <= 2:
        return True

    if gain >= 3 and pain <= 1:
        return True

    if gain >= 2 and pain <= 0:
        return True

    if en_d <= my_d and gain >= 1 and pain <= 0:
        return True

    if en_d < my_d and gain >= 1 and pain <= 1:
        return True

    if rw >= 7 and gain >= 2 and pain <= 1:
        return True

    if wall_s >= 2500 and gain > pain:
        return True

    return False


def pseudo_legal_wall_infos(placed):
    res = []

    for x in range(1, N):
        for y in range(1, N):
            for o in ("h", "v"):
                w = (x, y, o)
                if w in placed:
                    continue
                if wall_cross_key_from_info(w) in placed:
                    continue
                res.append(w)

    return res


def wall_action_from_info(w):
    x, y, o = w
    return {
        "action": "wall",
        "at": pos_to_str((x, y)),
        "orientation": o
    }


def pseudo_move_actions(pos, player, blocked):
    res = []
    for p in basic_neighbors(pos, blocked, player):
        res.append({
            "action": "move",
            "to": pos_to_str(p)
        })
    return res


def opponent_best_reply_score_after_move(state, my_action, blocked, placed):
    you = state.get("you")
    enemy = opponent(you)

    my_old = pawn(state, you)
    enemy_pos = pawn(state, enemy)

    if action_kind(my_action) == "move":
        my_new = parse_pos(my_action.get("to"))
        nb = blocked
        np = placed
    else:
        my_new = my_old
        nb, np = add_wall(blocked, placed, my_action)

    if my_new is None or enemy_pos is None:
        return 0

    enemy_moves = pseudo_move_actions(enemy_pos, enemy, nb)
    enemy_walls = []

    if remaining_walls(state, enemy) > 0:
        base_en_d, base_en_path = shortest_path(enemy_pos, enemy, nb)
        candidates = []

        for w in pseudo_legal_wall_infos(np):
            wa = wall_action_from_info(w)
            ww = wall_info(wa)
            near = wall_near_path_score(base_en_path, ww)
            block = path_block_gain(base_en_path, ww)
            if near > 0 or block > 0:
                candidates.append(wa)

        enemy_walls = candidates[:80]

    best_for_enemy = -INF

    for ea in enemy_moves + enemy_walls:
        if action_kind(ea) == "move":
            e_to = parse_pos(ea.get("to"))
            s = eval_position(enemy_pos=e_to, my_pos=my_new, you=enemy, blocked=nb)
        else:
            nnb, _ = add_wall(nb, np, ea)
            s = eval_position(enemy_pos=enemy_pos, my_pos=my_new, you=enemy, blocked=nnb)

        if s > best_for_enemy:
            best_for_enemy = s

    if best_for_enemy == -INF:
        return 0

    return -best_for_enemy


def tactical_score(state, action, blocked, placed):
    you = state.get("you")
    enemy = opponent(you)
    my = pawn(state, you)
    en = pawn(state, enemy)

    if action_kind(action) == "move":
        to = parse_pos(action.get("to"))
        nb = blocked
        np = placed
        base = move_score(state, action, blocked)
        if to is None:
            return -INF
        my_after = to
    else:
        nb, np = add_wall(blocked, placed, action)
        base, _, _ = wall_score(state, action, blocked)
        my_after = my

    my_d, _ = shortest_path(my_after, you, nb)
    en_d, _ = shortest_path(en, enemy, nb)

    score = base
    score += (en_d - my_d) * 500

    reply_score = opponent_best_reply_score_after_move(state, action, nb, np)
    score += reply_score * 0.20

    return score


def choose_action(state):
    actions = state.get("legal_actions", [])

    if not isinstance(actions, list) or not actions:
        return {
            "type": "action",
            "action": "move",
            "to": "e1"
        }

    you = state.get("you")
    enemy = opponent(you)

    blocked, placed = read_walls(state)
    moves = legal_moves(actions)
    walls = legal_walls(actions)

    for m in moves:
        to = parse_pos(m.get("to"))
        if is_goal(to, you):
            return output_action(m)

    enemy_pos = pawn(state, enemy)
    enemy_d, _ = shortest_path(enemy_pos, enemy, blocked)

    wall_a = None
    wall_s = -INF
    gain = 0
    pain = 0

    if walls and remaining_walls(state, you) > 0:
        wall_a, wall_s, gain, pain = best_wall(state, walls, blocked)

    move_a, move_s = best_move(state, moves, blocked)

    candidates = []

    if move_a is not None:
        candidates.append(move_a)

    if wall_a is not None and should_wall(state, wall_s, gain, pain, blocked):
        candidates.append(wall_a)

    if enemy_d <= 3 and walls and remaining_walls(state, you) > 0:
        scored_walls = []
        for w in walls:
            s, g, p = wall_score(state, w, blocked)
            if g >= 1 and p <= 2:
                scored_walls.append((s, w))
        scored_walls.sort(reverse=True, key=lambda x: x[0])
        for _, w in scored_walls[:8]:
            candidates.append(w)

    if moves:
        scored_moves = []
        for m in moves:
            scored_moves.append((move_score(state, m, blocked), m))
        scored_moves.sort(reverse=True, key=lambda x: x[0])
        for _, m in scored_moves[:6]:
            candidates.append(m)

    if walls and remaining_walls(state, you) > 0:
        scored_walls = []
        for w in walls:
            s, g, p = wall_score(state, w, blocked)
            if g > 0 and p <= 2:
                scored_walls.append((s, w))
        scored_walls.sort(reverse=True, key=lambda x: x[0])
        for _, w in scored_walls[:10]:
            candidates.append(w)

    seen = set()
    unique = []

    for c in candidates:
        k = json.dumps(c, sort_keys=True)
        if k in seen:
            continue
        seen.add(k)
        unique.append(c)

    if not unique:
        if move_a is not None:
            return output_action(move_a)
        return output_action(actions[0])

    best_a = None
    best_s = -INF

    for a in unique:
        s = tactical_score(state, a, blocked, placed)
        if s > best_s:
            best_s = s
            best_a = a

    if best_a is not None:
        return output_action(best_a)

    if move_a is not None:
        return output_action(move_a)

    return output_action(actions[0])


def main():
    for line in sys.stdin:
        line = line.strip()

        if not line:
            continue

        try:
            state = json.loads(line)
            action = choose_action(state)
            print(
                json.dumps(
                    action,
                    ensure_ascii=False,
                    separators=(",", ":")
                ),
                flush=True
            )
        except Exception as e:
            print("error:", e, file=sys.stderr, flush=True)


if __name__ == "__main__":
    main()