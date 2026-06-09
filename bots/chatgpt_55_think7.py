import sys
import json
from collections import deque
from functools import lru_cache

N = 9
INF = 10**9
WIN = 10**8
MAX_DEPTH = 4


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


def opponent(player):
    return "P2" if player == "P1" else "P1"


def goal_row(player):
    return N if player == "P1" else 1


def is_goal(pos, player):
    return pos is not None and pos[1] == goal_row(player)


def normalize_orientation(o):
    if not isinstance(o, str) or not o:
        return None

    o = o.lower()

    if o.startswith("h"):
        return "h"

    if o.startswith("v"):
        return "v"

    return None


def wall_info(action):
    if isinstance(action, dict):
        at = action.get("at")
        orientation = action.get("orientation")
    elif isinstance(action, (list, tuple)) and len(action) >= 2:
        at = action[0]
        orientation = action[1]
    elif isinstance(action, str) and len(action) >= 3:
        at = action[:-1]
        orientation = action[-1]
    else:
        return None

    pos = parse_pos(at)
    orientation = normalize_orientation(orientation)

    if pos is None or orientation is None:
        return None

    x, y = pos

    if not (1 <= x <= N - 1 and 1 <= y <= N - 1):
        return None

    return x, y, orientation


def wall_action(w):
    x, y, orientation = w

    return {
        "action": "wall",
        "at": pos_to_str((x, y)),
        "orientation": orientation
    }


def action_kind(action):
    if not isinstance(action, dict):
        return None

    return action.get("action")


def make_edge(a, b):
    return tuple(sorted((a, b)))


def wall_edges(w):
    if w is None:
        return []

    x, y, orientation = w

    if orientation == "h":
        return [
            make_edge((x, y), (x, y + 1)),
            make_edge((x + 1, y), (x + 1, y + 1))
        ]

    return [
        make_edge((x, y), (x + 1, y)),
        make_edge((x, y + 1), (x + 1, y + 1))
    ]


def cross_wall(w):
    x, y, orientation = w

    return x, y, "v" if orientation == "h" else "h"


def get_pawn(raw, player):
    pawns = raw.get("pawns", {})

    if not isinstance(pawns, dict):
        return None

    return parse_pos(pawns.get(player))


def read_remaining(raw):
    remaining = raw.get("remaining_walls", 0)

    if isinstance(remaining, dict):
        result = {}

        for player in ("P1", "P2"):
            try:
                result[player] = int(remaining.get(player, 0))
            except Exception:
                result[player] = 0

        return result

    try:
        value = int(remaining)
    except Exception:
        value = 0

    return {
        "P1": value,
        "P2": value
    }


def read_walls(raw):
    walls = raw.get("walls", [])
    blocked = set()
    placed = set()

    if not isinstance(walls, list):
        return frozenset(), frozenset()

    for item in walls:
        w = wall_info(item)

        if w is None:
            continue

        placed.add(w)

        for e in wall_edges(w):
            blocked.add(e)

    return frozenset(blocked), frozenset(placed)


def make_state(raw):
    blocked, placed = read_walls(raw)

    return {
        "pos": {
            "P1": get_pawn(raw, "P1"),
            "P2": get_pawn(raw, "P2")
        },
        "rem": read_remaining(raw),
        "blocked": blocked,
        "placed": placed
    }


def in_board(pos):
    return pos is not None and 1 <= pos[0] <= N and 1 <= pos[1] <= N


def can_step(a, b, blocked):
    if not in_board(a) or not in_board(b):
        return False

    return make_edge(a, b) not in blocked


def dir_order(player):
    if player == "P1":
        return [(0, 1), (-1, 0), (1, 0), (0, -1)]

    return [(0, -1), (-1, 0), (1, 0), (0, 1)]


def basic_neighbors(pos, blocked, player=None):
    if pos is None:
        return []

    if player in ("P1", "P2"):
        directions = dir_order(player)
    else:
        directions = [(0, 1), (0, -1), (-1, 0), (1, 0)]

    result = []

    for dx, dy in directions:
        nxt = (pos[0] + dx, pos[1] + dy)

        if can_step(pos, nxt, blocked):
            result.append(nxt)

    return result


@lru_cache(maxsize=300000)
def shortest_path_cached(start, player, blocked):
    if start is None:
        return INF, ()

    queue = deque([start])
    dist = {start: 0}
    prev = {}

    while queue:
        cur = queue.popleft()

        if is_goal(cur, player):
            path = []
            p = cur

            while True:
                path.append(p)

                if p not in prev:
                    break

                p = prev[p]

            path.reverse()
            return dist[cur], tuple(path)

        for nxt in basic_neighbors(cur, blocked, player):
            if nxt in dist:
                continue

            dist[nxt] = dist[cur] + 1
            prev[nxt] = cur
            queue.append(nxt)

    return INF, ()


def shortest_path(start, player, blocked):
    return shortest_path_cached(start, player, frozenset(blocked))


def generate_moves(state, player):
    pos = state["pos"][player]
    enemy = opponent(player)
    enemy_pos = state["pos"][enemy]
    blocked = state["blocked"]

    if pos is None:
        return []

    result = []
    seen = set()

    for dx, dy in dir_order(player):
        nxt = (pos[0] + dx, pos[1] + dy)

        if not can_step(pos, nxt, blocked):
            continue

        if nxt != enemy_pos:
            if nxt not in seen:
                seen.add(nxt)
                result.append({
                    "action": "move",
                    "to": pos_to_str(nxt)
                })

            continue

        jump = (enemy_pos[0] + dx, enemy_pos[1] + dy)

        if can_step(enemy_pos, jump, blocked):
            if jump not in seen:
                seen.add(jump)
                result.append({
                    "action": "move",
                    "to": pos_to_str(jump)
                })

            continue

        if dx == 0:
            sides = [(-1, 0), (1, 0)]
        else:
            sides = [(0, -1), (0, 1)]

        for sx, sy in sides:
            diag = (enemy_pos[0] + sx, enemy_pos[1] + sy)

            if can_step(enemy_pos, diag, blocked):
                if diag not in seen:
                    seen.add(diag)
                    result.append({
                        "action": "move",
                        "to": pos_to_str(diag)
                    })

    return result


def apply_action(state, player, action):
    pos = {
        "P1": state["pos"]["P1"],
        "P2": state["pos"]["P2"]
    }

    rem = {
        "P1": state["rem"].get("P1", 0),
        "P2": state["rem"].get("P2", 0)
    }

    blocked = set(state["blocked"])
    placed = set(state["placed"])

    if action_kind(action) == "move":
        to = parse_pos(action.get("to"))

        if to is not None:
            pos[player] = to

    elif action_kind(action) == "wall":
        w = wall_info(action)

        if w is not None:
            placed.add(w)

            for e in wall_edges(w):
                blocked.add(e)

            rem[player] = max(0, rem.get(player, 0) - 1)

    return {
        "pos": pos,
        "rem": rem,
        "blocked": frozenset(blocked),
        "placed": frozenset(placed)
    }


def is_wall_legal(state, w):
    if w is None:
        return False

    if w in state["placed"]:
        return False

    if cross_wall(w) in state["placed"]:
        return False

    for e in wall_edges(w):
        if e in state["blocked"]:
            return False

    blocked = set(state["blocked"])

    for e in wall_edges(w):
        blocked.add(e)

    blocked = frozenset(blocked)

    d1, _ = shortest_path(state["pos"]["P1"], "P1", blocked)
    d2, _ = shortest_path(state["pos"]["P2"], "P2", blocked)

    return d1 < INF and d2 < INF


def all_wall_candidates(state):
    result = []

    for x in range(1, N):
        for y in range(1, N):
            for orientation in ("h", "v"):
                w = (x, y, orientation)

                if is_wall_legal(state, w):
                    result.append(wall_action(w))

    return result


def center_score(pos):
    if pos is None:
        return 0

    return -abs(pos[0] - 5)


def progress(old_pos, new_pos, player):
    if old_pos is None or new_pos is None:
        return 0

    if player == "P1":
        return new_pos[1] - old_pos[1]

    return old_pos[1] - new_pos[1]


def path_block_count(path, action):
    w = wall_info(action)

    if w is None or not path or len(path) < 2:
        return 0

    edges = set(wall_edges(w))
    count = 0

    for i in range(len(path) - 1):
        if make_edge(path[i], path[i + 1]) in edges:
            count += 1

    return count


def wall_near_path_score(path, action):
    w = wall_info(action)

    if w is None or not path:
        return 0

    x, y, _ = w

    cells = [
        (x, y),
        (x + 1, y),
        (x, y + 1),
        (x + 1, y + 1)
    ]

    best = 9999

    for c in cells:
        for i, p in enumerate(path):
            d = abs(c[0] - p[0]) + abs(c[1] - p[1])
            value = d * 12 + i

            if value < best:
                best = value

    return max(0, 160 - best * 3)


def wall_shape_score(action, enemy_pos, enemy):
    w = wall_info(action)

    if w is None or enemy_pos is None:
        return 0

    x, y, orientation = w
    ex, ey = enemy_pos
    score = 0

    front_y = ey if enemy == "P1" else ey - 1

    if orientation == "h":
        if abs(y - front_y) <= 1:
            score += 260

        if abs(x - ex) <= 1:
            score += 180

        if abs(x - ex) == 2:
            score += 60

    else:
        if abs(x - ex) <= 1:
            score += 110

        if abs(y - ey) <= 2:
            score += 70

    score -= (abs(x - ex) + abs(y - ey)) * 18

    return score


def escape_width_score(pos, player, blocked):
    if pos is None:
        return 0

    d, path = shortest_path(pos, player, blocked)

    if d >= INF or not path:
        return -10000

    score = 0

    for p in path[:4]:
        score += len(basic_neighbors(p, blocked, None)) * 20

    return score


def evaluate_state(state, root):
    enemy = opponent(root)
    my = state["pos"][root]
    en = state["pos"][enemy]
    blocked = state["blocked"]

    my_dist, my_path = shortest_path(my, root, blocked)
    enemy_dist, enemy_path = shortest_path(en, enemy, blocked)

    if my_dist == 0:
        return WIN

    if enemy_dist == 0:
        return -WIN

    score = 0
    score += (enemy_dist - my_dist) * 15000
    score -= my_dist * 900
    score += enemy_dist * 700

    score += (state["rem"].get(root, 0) - state["rem"].get(enemy, 0)) * 260

    score += center_score(my) * 70
    score -= center_score(en) * 35

    score += escape_width_score(my, root, blocked)
    score -= escape_width_score(en, enemy, blocked) * 0.75

    if my_path and len(my_path) <= 5:
        score += (6 - len(my_path)) * 1800

    if enemy_path and len(enemy_path) <= 5:
        score -= (6 - len(enemy_path)) * 2200

    if my_path and len(my_path) >= 2:
        score += progress(my, my_path[1], root) * 300

    if enemy_path and len(enemy_path) >= 2:
        score -= progress(en, enemy_path[1], enemy) * 220

    if my is not None and en is not None:
        manhattan = abs(my[0] - en[0]) + abs(my[1] - en[1])

        if manhattan == 1:
            if my_dist <= enemy_dist:
                score += 400
            else:
                score -= 550

    return int(score)


def move_score(state, action, player):
    to = parse_pos(action.get("to"))

    if to is None:
        return -INF

    enemy = opponent(player)
    old = state["pos"][player]
    after = apply_action(state, player, action)

    my_dist, my_path = shortest_path(
        after["pos"][player],
        player,
        after["blocked"]
    )

    enemy_dist, enemy_path = shortest_path(
        after["pos"][enemy],
        enemy,
        after["blocked"]
    )

    score = 0
    score += (enemy_dist - my_dist) * 9000
    score -= my_dist * 850
    score += enemy_dist * 450

    score += progress(old, to, player) * 1300
    score += center_score(to) * 85

    if is_goal(to, player):
        score += WIN

    if my_path and len(my_path) <= 4:
        score += (5 - len(my_path)) * 1800

    if enemy_path and len(enemy_path) <= 3:
        score -= (4 - len(enemy_path)) * 2500

    return score


def wall_score(state, action, player):
    if state["rem"].get(player, 0) <= 0:
        return -INF, 0, 0

    enemy = opponent(player)
    my = state["pos"][player]
    en = state["pos"][enemy]
    blocked = state["blocked"]

    base_my_dist, base_my_path = shortest_path(my, player, blocked)
    base_enemy_dist, base_enemy_path = shortest_path(en, enemy, blocked)

    after = apply_action(state, player, action)

    my_dist, _ = shortest_path(my, player, after["blocked"])
    enemy_dist, _ = shortest_path(en, enemy, after["blocked"])

    if my_dist >= INF or enemy_dist >= INF:
        return -INF, 0, 0

    gain = enemy_dist - base_enemy_dist
    pain = my_dist - base_my_dist

    score = 0
    score += gain * 7200
    score -= pain * 5600
    score += (enemy_dist - my_dist) * 700

    score += path_block_count(base_enemy_path, action) * 3200
    score -= path_block_count(base_my_path, action) * 2400

    score += wall_near_path_score(base_enemy_path, action) * 13
    score += wall_shape_score(action, en, enemy)

    if base_enemy_dist <= base_my_dist:
        score += 2500

    if base_enemy_dist <= 5:
        score += 1700

    if base_enemy_dist <= 3:
        score += 4200

    if base_enemy_dist <= 2:
        score += 7500

    if gain <= 0:
        score -= 7000

    if pain > gain:
        score -= (pain - gain) * 5500

    if pain >= 3 and gain <= 2:
        score -= 4500

    if gain >= 2 and pain <= 1:
        score += 3000

    if gain >= 3 and pain <= 2:
        score += 5500

    if gain >= 4:
        score += 8500

    return score, gain, pain


def candidate_walls(state, player, limit):
    if state["rem"].get(player, 0) <= 0:
        return []

    enemy = opponent(player)

    my = state["pos"][player]
    en = state["pos"][enemy]

    _, my_path = shortest_path(my, player, state["blocked"])
    enemy_dist, enemy_path = shortest_path(en, enemy, state["blocked"])

    scored = []

    for action in all_wall_candidates(state):
        w = wall_info(action)

        near = wall_near_path_score(enemy_path, action)
        block_enemy = path_block_count(enemy_path, action)
        block_me = path_block_count(my_path, action)

        if block_enemy == 0 and near <= 0 and en is not None:
            x, y, _ = w

            if abs(x - en[0]) + abs(y - en[1]) > 4 and enemy_dist > 4:
                continue

        score, gain, pain = wall_score(state, action, player)

        if gain <= 0 and enemy_dist > 3:
            continue

        if pain >= 4 and gain < 4:
            continue

        score += block_enemy * 1800
        score -= block_me * 1200

        scored.append((score, action))

    scored.sort(reverse=True, key=lambda x: x[0])

    return [action for _, action in scored[:limit]]


def generated_actions(state, player, depth):
    moves = generate_moves(state, player)

    scored_moves = [
        (move_score(state, action, player), action)
        for action in moves
    ]

    scored_moves.sort(reverse=True, key=lambda x: x[0])

    if depth >= 4:
        wall_limit = 18
    elif depth == 3:
        wall_limit = 24
    elif depth == 2:
        wall_limit = 32
    else:
        wall_limit = 42

    walls = candidate_walls(state, player, wall_limit)

    scored_walls = []

    for action in walls:
        score, _, _ = wall_score(state, action, player)
        scored_walls.append((score, action))

    scored_walls.sort(reverse=True, key=lambda x: x[0])

    actions = []

    for _, action in scored_moves:
        actions.append(action)

    for _, action in scored_walls:
        actions.append(action)

    return actions


def state_key(state, turn, depth):
    return (
        turn,
        depth,
        state["pos"]["P1"],
        state["pos"]["P2"],
        state["rem"].get("P1", 0),
        state["rem"].get("P2", 0),
        tuple(sorted(state["placed"]))
    )


def search(state, turn, root, depth, alpha, beta, cache):
    key = state_key(state, turn, depth)

    if key in cache:
        return cache[key]

    enemy = opponent(root)

    root_dist, _ = shortest_path(
        state["pos"][root],
        root,
        state["blocked"]
    )

    enemy_dist, _ = shortest_path(
        state["pos"][enemy],
        enemy,
        state["blocked"]
    )

    if root_dist == 0:
        return WIN + depth

    if enemy_dist == 0:
        return -WIN - depth

    if depth <= 0:
        value = evaluate_state(state, root)
        cache[key] = value
        return value

    actions = generated_actions(state, turn, depth)

    if not actions:
        value = evaluate_state(state, root)
        cache[key] = value
        return value

    next_turn = opponent(turn)

    if turn == root:
        best = -INF

        for action in actions:
            child = apply_action(state, turn, action)

            value = search(
                child,
                next_turn,
                root,
                depth - 1,
                alpha,
                beta,
                cache
            )

            if value > best:
                best = value

            if best > alpha:
                alpha = best

            if alpha >= beta:
                break

        cache[key] = best
        return best

    best = INF

    for action in actions:
        child = apply_action(state, turn, action)

        value = search(
            child,
            next_turn,
            root,
            depth - 1,
            alpha,
            beta,
            cache
        )

        if value < best:
            best = value

        if best < beta:
            beta = best

        if alpha >= beta:
            break

    cache[key] = best
    return best


def signature(action):
    if not isinstance(action, dict):
        return None

    if action.get("action") == "move":
        return "move", action.get("to")

    if action.get("action") == "wall":
        return (
            "wall",
            action.get("at"),
            normalize_orientation(action.get("orientation"))
        )

    return None


def output_action(action):
    result = {"type": "action"}

    for key, value in action.items():
        if key != "type":
            result[key] = value

    return result


def force_legal(chosen, legal_actions):
    if not isinstance(legal_actions, list) or not legal_actions:
        return {
            "type": "action",
            "action": "move",
            "to": "e1"
        }

    sig = signature(chosen)

    for action in legal_actions:
        if signature(action) == sig:
            return output_action(action)

    return output_action(legal_actions[0])


def legal_moves_from_input(actions):
    result = []

    if not isinstance(actions, list):
        return result

    for action in actions:
        if not isinstance(action, dict):
            continue

        if action_kind(action) != "move":
            continue

        if parse_pos(action.get("to")) is None:
            continue

        result.append(action)

    return result


def legal_walls_from_input(actions):
    result = []

    if not isinstance(actions, list):
        return result

    for action in actions:
        if not isinstance(action, dict):
            continue

        if action_kind(action) != "wall":
            continue

        if wall_info(action) is None:
            continue

        result.append(action)

    return result


def root_candidates(raw, state, player):
    actions = raw.get("legal_actions", [])

    moves = legal_moves_from_input(actions)
    walls = legal_walls_from_input(actions)

    result = []

    scored_moves = [
        (move_score(state, action, player), action)
        for action in moves
    ]

    scored_moves.sort(reverse=True, key=lambda x: x[0])

    for _, action in scored_moves:
        result.append(action)

    scored_walls = []

    if state["rem"].get(player, 0) > 0:
        enemy = opponent(player)

        my_dist, _ = shortest_path(
            state["pos"][player],
            player,
            state["blocked"]
        )

        enemy_dist, _ = shortest_path(
            state["pos"][enemy],
            enemy,
            state["blocked"]
        )

        for action in walls:
            score, gain, pain = wall_score(state, action, player)

            ok = False

            if gain >= 3 and pain <= 2:
                ok = True

            if gain >= 2 and pain <= 1:
                ok = True

            if gain >= 1 and pain <= 0 and enemy_dist <= my_dist:
                ok = True

            if enemy_dist <= 3 and gain >= 1 and pain <= 2:
                ok = True

            if score >= 3500 and gain > pain:
                ok = True

            if ok:
                scored_walls.append((score, action))

    scored_walls.sort(reverse=True, key=lambda x: x[0])

    for _, action in scored_walls[:70]:
        result.append(action)

    if not result:
        result = moves + walls[:1]

    seen = set()
    unique = []

    for action in result:
        key = json.dumps(action, sort_keys=True)

        if key in seen:
            continue

        seen.add(key)
        unique.append(action)

    return unique


def choose_action_inner(raw):
    actions = raw.get("legal_actions", [])

    if not isinstance(actions, list) or not actions:
        return None

    you = raw.get("you")
    enemy = opponent(you)

    state = make_state(raw)

    moves = legal_moves_from_input(actions)

    for action in moves:
        to = parse_pos(action.get("to"))

        if is_goal(to, you):
            return action

    my_dist, _ = shortest_path(
        state["pos"][you],
        you,
        state["blocked"]
    )

    enemy_dist, _ = shortest_path(
        state["pos"][enemy],
        enemy,
        state["blocked"]
    )

    depth = MAX_DEPTH

    if my_dist <= 4 or enemy_dist <= 4:
        depth = 5

    if state["rem"].get("P1", 0) + state["rem"].get("P2", 0) <= 5:
        depth = 5

    candidates = root_candidates(raw, state, you)

    if not candidates:
        return actions[0]

    cache = {}
    best_action = None
    best_score = -INF
    alpha = -INF
    beta = INF

    ordered = []

    for action in candidates:
        if action_kind(action) == "move":
            score = move_score(state, action, you)
        else:
            score, _, _ = wall_score(state, action, you)

        ordered.append((score, action))

    ordered.sort(reverse=True, key=lambda x: x[0])

    for _, action in ordered:
        child = apply_action(state, you, action)

        score = search(
            child,
            enemy,
            you,
            depth - 1,
            alpha,
            beta,
            cache
        )

        if score > best_score:
            best_score = score
            best_action = action

        if score > alpha:
            alpha = score

    return best_action


def choose_action(raw):
    legal_actions = raw.get("legal_actions", [])

    try:
        chosen = choose_action_inner(raw)
    except Exception as error:
        print(
            "error:",
            error,
            file=sys.stderr,
            flush=True
        )
        chosen = None

    return force_legal(chosen, legal_actions)


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

        except Exception as error:
            print(
                "main_error:",
                error,
                file=sys.stderr,
                flush=True
            )


if __name__ == "__main__":
    main()