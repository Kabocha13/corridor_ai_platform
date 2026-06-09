import sys
import json
from collections import deque

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
    if player == "P1":
        return "P2"
    return "P1"


def goal_row(player):
    if player == "P1":
        return N
    return 1


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

    if orientation == "h":
        return x, y, "v"

    return x, y, "h"


def action_kind(action):
    if not isinstance(action, dict):
        return None

    return action.get("action")


def output_action(action):
    if not isinstance(action, dict):
        return {
            "type": "action",
            "action": "move",
            "to": "e1"
        }

    result = {"type": "action"}

    for key, value in action.items():
        if key != "type":
            result[key] = value

    return result


def get_pawn_from_input(state, player):
    pawns = state.get("pawns", {})

    if not isinstance(pawns, dict):
        return None

    return parse_pos(pawns.get(player))


def get_remaining_from_input(state):
    you = state.get("you")
    enemy = opponent(you)
    remaining = state.get("remaining_walls", {})

    if isinstance(remaining, dict):
        p1 = remaining.get("P1", 0)
        p2 = remaining.get("P2", 0)
    else:
        p1 = remaining
        p2 = remaining

    try:
        p1 = int(p1)
    except Exception:
        p1 = 0

    try:
        p2 = int(p2)
    except Exception:
        p2 = 0

    return {
        "P1": p1,
        "P2": p2,
        you: p1 if you == "P1" else p2,
        enemy: p2 if enemy == "P2" else p1
    }


def read_walls_from_input(state):
    walls = state.get("walls", [])
    blocked = set()
    placed = set()

    if not isinstance(walls, list):
        return blocked, placed

    for action in walls:
        w = wall_info(action)

        if w is None:
            continue

        placed.add(w)

        for e in wall_edges(w):
            blocked.add(e)

    return blocked, placed


def make_state(raw_state):
    you = raw_state.get("you")
    enemy = opponent(you)

    blocked, placed = read_walls_from_input(raw_state)

    return {
        "pos": {
            "P1": get_pawn_from_input(raw_state, "P1"),
            "P2": get_pawn_from_input(raw_state, "P2")
        },
        "rem": get_remaining_from_input(raw_state),
        "blocked": frozenset(blocked),
        "placed": frozenset(placed),
        "you": you,
        "enemy": enemy
    }


def in_board(pos):
    return 1 <= pos[0] <= N and 1 <= pos[1] <= N


def can_move_between(a, b, blocked):
    if not in_board(a) or not in_board(b):
        return False

    return make_edge(a, b) not in blocked


def basic_neighbors(pos, blocked, ordered_player=None):
    x, y = pos

    if ordered_player == "P1":
        directions = [(0, 1), (-1, 0), (1, 0), (0, -1)]
    elif ordered_player == "P2":
        directions = [(0, -1), (-1, 0), (1, 0), (0, 1)]
    else:
        directions = [(0, 1), (0, -1), (-1, 0), (1, 0)]

    result = []

    for dx, dy in directions:
        nxt = (x + dx, y + dy)

        if can_move_between(pos, nxt, blocked):
            result.append(nxt)

    return result


def shortest_path(start, player, blocked):
    if start is None:
        return INF, []

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
            return dist[cur], path

        for nxt in basic_neighbors(cur, blocked, player):
            if nxt in dist:
                continue

            dist[nxt] = dist[cur] + 1
            prev[nxt] = cur
            queue.append(nxt)

    return INF, []


def generate_moves(state, player):
    pos = state["pos"][player]
    enemy = opponent(player)
    enemy_pos = state["pos"][enemy]
    blocked = state["blocked"]

    if pos is None:
        return []

    result = []
    seen = set()

    if player == "P1":
        directions = [(0, 1), (-1, 0), (1, 0), (0, -1)]
    else:
        directions = [(0, -1), (-1, 0), (1, 0), (0, 1)]

    for dx, dy in directions:
        nxt = (pos[0] + dx, pos[1] + dy)

        if not can_move_between(pos, nxt, blocked):
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

        if can_move_between(enemy_pos, jump, blocked):
            if jump not in seen:
                seen.add(jump)
                result.append({
                    "action": "move",
                    "to": pos_to_str(jump)
                })
            continue

        if dx == 0:
            diagonals = [(-1, 0), (1, 0)]
        else:
            diagonals = [(0, -1), (0, 1)]

        for sx, sy in diagonals:
            diag = (enemy_pos[0] + sx, enemy_pos[1] + sy)

            if can_move_between(enemy_pos, diag, blocked):
                if diag not in seen:
                    seen.add(diag)
                    result.append({
                        "action": "move",
                        "to": pos_to_str(diag)
                    })

    return result


def is_wall_legal(state, w):
    if w is None:
        return False

    blocked = state["blocked"]
    placed = state["placed"]

    if w in placed:
        return False

    if cross_wall(w) in placed:
        return False

    edges = wall_edges(w)

    for e in edges:
        if e in blocked:
            return False

    new_blocked = set(blocked)

    for e in edges:
        new_blocked.add(e)

    new_blocked = frozenset(new_blocked)

    d1, _ = shortest_path(state["pos"]["P1"], "P1", new_blocked)
    d2, _ = shortest_path(state["pos"]["P2"], "P2", new_blocked)

    return d1 < INF and d2 < INF


def apply_action(state, player, action):
    new_pos = {
        "P1": state["pos"]["P1"],
        "P2": state["pos"]["P2"]
    }

    new_rem = {
        "P1": state["rem"].get("P1", 0),
        "P2": state["rem"].get("P2", 0)
    }

    blocked = set(state["blocked"])
    placed = set(state["placed"])

    if action_kind(action) == "move":
        to = parse_pos(action.get("to"))

        if to is not None:
            new_pos[player] = to

    elif action_kind(action) == "wall":
        w = wall_info(action)

        if w is not None:
            placed.add(w)

            for e in wall_edges(w):
                blocked.add(e)

            new_rem[player] = max(0, new_rem.get(player, 0) - 1)

    return {
        "pos": new_pos,
        "rem": new_rem,
        "blocked": frozenset(blocked),
        "placed": frozenset(placed)
    }


def center_score(pos):
    if pos is None:
        return 0

    return -abs(pos[0] - 5)


def progress_score(old_pos, new_pos, player):
    if old_pos is None or new_pos is None:
        return 0

    if player == "P1":
        return new_pos[1] - old_pos[1]

    return old_pos[1] - new_pos[1]


def path_block_count(path, w):
    if not path or len(path) < 2:
        return 0

    edges = set(wall_edges(w))
    count = 0

    for i in range(len(path) - 1):
        if make_edge(path[i], path[i + 1]) in edges:
            count += 1

    return count


def wall_near_path_score(path, w):
    if not path or w is None:
        return 0

    x, y, orientation = w

    cells = [
        (x, y),
        (x + 1, y),
        (x, y + 1),
        (x + 1, y + 1)
    ]

    best = 1000

    for c in cells:
        for i, p in enumerate(path):
            d = abs(c[0] - p[0]) + abs(c[1] - p[1])
            value = d * 10 + i

            if value < best:
                best = value

    return max(0, 120 - best * 3)


def wall_shape_score(w, enemy_pos, enemy):
    if w is None or enemy_pos is None:
        return 0

    x, y, orientation = w
    ex, ey = enemy_pos
    score = 0

    if enemy == "P1":
        front_y = ey
    else:
        front_y = ey - 1

    if orientation == "h":
        if abs(y - front_y) <= 1:
            score += 180

        if abs(x - ex) <= 1:
            score += 120

    else:
        if abs(x - ex) <= 1:
            score += 70

        if abs(y - ey) <= 2:
            score += 40

    score -= (abs(x - ex) + abs(y - ey)) * 12

    return score


def evaluate_state(state, root):
    enemy = opponent(root)

    my_pos = state["pos"][root]
    enemy_pos = state["pos"][enemy]
    blocked = state["blocked"]

    my_dist, my_path = shortest_path(my_pos, root, blocked)
    enemy_dist, enemy_path = shortest_path(enemy_pos, enemy, blocked)

    if my_dist == 0:
        return WIN

    if enemy_dist == 0:
        return -WIN

    score = 0
    score += (enemy_dist - my_dist) * 12000
    score -= my_dist * 700
    score += enemy_dist * 500

    score += (state["rem"].get(root, 0) - state["rem"].get(enemy, 0)) * 180

    score += center_score(my_pos) * 45
    score -= center_score(enemy_pos) * 20

    if my_path and len(my_path) >= 2:
        next_pos = my_path[1]
        score += progress_score(my_pos, next_pos, root) * 160

    if enemy_path and len(enemy_path) <= 4:
        score -= (5 - len(enemy_path)) * 1800

    if my_path and len(my_path) <= 4:
        score += (5 - len(my_path)) * 1600

    if my_pos is not None and enemy_pos is not None:
        manhattan = abs(my_pos[0] - enemy_pos[0]) + abs(my_pos[1] - enemy_pos[1])

        if manhattan == 1:
            if my_dist <= enemy_dist:
                score += 250
            else:
                score -= 250

    return score


def wall_score_for_player(state, action, player):
    enemy = opponent(player)
    w = wall_info(action)

    if w is None:
        return -INF, 0, 0

    blocked = state["blocked"]

    my_pos = state["pos"][player]
    enemy_pos = state["pos"][enemy]

    base_my_dist, base_my_path = shortest_path(my_pos, player, blocked)
    base_enemy_dist, base_enemy_path = shortest_path(enemy_pos, enemy, blocked)

    after = apply_action(state, player, action)
    new_blocked = after["blocked"]

    my_dist, my_path = shortest_path(my_pos, player, new_blocked)
    enemy_dist, enemy_path = shortest_path(enemy_pos, enemy, new_blocked)

    if my_dist >= INF or enemy_dist >= INF:
        return -INF, 0, 0

    gain = enemy_dist - base_enemy_dist
    pain = my_dist - base_my_dist

    score = 0
    score += gain * 5000
    score -= pain * 4200
    score += (enemy_dist - my_dist) * 450

    score += path_block_count(base_enemy_path, w) * 1800
    score -= path_block_count(base_my_path, w) * 1400

    score += wall_near_path_score(base_enemy_path, w) * 8
    score += wall_shape_score(w, enemy_pos, enemy)

    if base_enemy_dist <= base_my_dist:
        score += 1300

    if base_enemy_dist <= 5:
        score += 1200

    if base_enemy_dist <= 3:
        score += 2500

    if base_enemy_dist <= 2:
        score += 5000

    if gain <= 0:
        score -= 4500

    if pain > gain:
        score -= (pain - gain) * 3500

    if gain >= 2 and pain <= 1:
        score += 1800

    if gain >= 3 and pain <= 2:
        score += 3500

    if gain >= 4:
        score += 5000

    return score, gain, pain


def move_score_for_player(state, action, player):
    pos = state["pos"][player]
    to = parse_pos(action.get("to"))

    if to is None:
        return -INF

    after = apply_action(state, player, action)
    enemy = opponent(player)

    my_dist, my_path = shortest_path(after["pos"][player], player, after["blocked"])
    enemy_dist, enemy_path = shortest_path(after["pos"][enemy], enemy, after["blocked"])

    score = 0
    score += (enemy_dist - my_dist) * 4000
    score -= my_dist * 600
    score += enemy_dist * 350
    score += progress_score(pos, to, player) * 800
    score += center_score(to) * 40

    if is_goal(to, player):
        score += WIN

    if my_path and len(my_path) >= 2:
        score += progress_score(to, my_path[1], player) * 180

    return score


def all_wall_candidates(state):
    result = []

    for x in range(1, N):
        for y in range(1, N):
            for orientation in ("h", "v"):
                w = (x, y, orientation)

                if is_wall_legal(state, w):
                    result.append(wall_action(w))

    return result


def candidate_walls(state, player, limit):
    if state["rem"].get(player, 0) <= 0:
        return []

    enemy = opponent(player)

    my_pos = state["pos"][player]
    enemy_pos = state["pos"][enemy]

    my_dist, my_path = shortest_path(my_pos, player, state["blocked"])
    enemy_dist, enemy_path = shortest_path(enemy_pos, enemy, state["blocked"])

    scored = []

    for action in all_wall_candidates(state):
        w = wall_info(action)

        enemy_block = path_block_count(enemy_path, w)
        my_block = path_block_count(my_path, w)
        near = wall_near_path_score(enemy_path, w)

        if enemy_block == 0 and near <= 0:
            if enemy_pos is not None:
                x, y, _ = w
                if abs(x - enemy_pos[0]) + abs(y - enemy_pos[1]) > 3:
                    continue

        score, gain, pain = wall_score_for_player(state, action, player)

        if gain <= 0 and enemy_dist > 3:
            continue

        if pain >= 4 and gain < 3:
            continue

        score += enemy_block * 1200
        score -= my_block * 900

        scored.append((score, action))

    scored.sort(reverse=True, key=lambda item: item[0])

    return [action for _, action in scored[:limit]]


def generated_actions(state, player, depth):
    moves = generate_moves(state, player)

    if depth >= 4:
        wall_limit = 16
    elif depth == 3:
        wall_limit = 22
    elif depth == 2:
        wall_limit = 28
    else:
        wall_limit = 36

    walls = candidate_walls(state, player, wall_limit)

    actions = []

    scored_moves = []

    for move in moves:
        scored_moves.append((move_score_for_player(state, move, player), move))

    scored_moves.sort(reverse=True, key=lambda item: item[0])

    for _, move in scored_moves:
        actions.append(move)

    scored_walls = []

    for wall in walls:
        score, _, _ = wall_score_for_player(state, wall, player)
        scored_walls.append((score, wall))

    scored_walls.sort(reverse=True, key=lambda item: item[0])

    for _, wall in scored_walls:
        actions.append(wall)

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

    root_enemy = opponent(root)

    root_dist, _ = shortest_path(state["pos"][root], root, state["blocked"])
    enemy_dist, _ = shortest_path(state["pos"][root_enemy], root_enemy, state["blocked"])

    if root_dist == 0:
        return WIN

    if enemy_dist == 0:
        return -WIN

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
            value = search(child, next_turn, root, depth - 1, alpha, beta, cache)

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
        value = search(child, next_turn, root, depth - 1, alpha, beta, cache)

        if value < best:
            best = value

        if best < beta:
            beta = best

        if alpha >= beta:
            break

    cache[key] = best
    return best


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


def should_consider_root_wall(state, action, player):
    score, gain, pain = wall_score_for_player(state, action, player)
    enemy = opponent(player)

    my_dist, _ = shortest_path(state["pos"][player], player, state["blocked"])
    enemy_dist, _ = shortest_path(state["pos"][enemy], enemy, state["blocked"])

    if gain >= 3 and pain <= 2:
        return True

    if gain >= 2 and pain <= 1:
        return True

    if gain >= 1 and pain <= 0 and enemy_dist <= my_dist:
        return True

    if enemy_dist <= 3 and gain >= 1 and pain <= 2:
        return True

    if score >= 2500 and gain > pain:
        return True

    return False


def root_candidates(raw_state, state):
    you = raw_state.get("you")
    actions = raw_state.get("legal_actions", [])

    moves = legal_moves_from_input(actions)
    walls = legal_walls_from_input(actions)

    result = []

    scored_moves = []

    for move in moves:
        scored_moves.append((move_score_for_player(state, move, you), move))

    scored_moves.sort(reverse=True, key=lambda item: item[0])

    for _, move in scored_moves:
        result.append(move)

    scored_walls = []

    if state["rem"].get(you, 0) > 0:
        for wall in walls:
            score, gain, pain = wall_score_for_player(state, wall, you)

            if should_consider_root_wall(state, wall, you):
                scored_walls.append((score, wall))
            elif gain > 0 and pain <= 2:
                scored_walls.append((score - 1500, wall))

    scored_walls.sort(reverse=True, key=lambda item: item[0])

    for _, wall in scored_walls[:45]:
        result.append(wall)

    seen = set()
    unique = []

    for action in result:
        key = json.dumps(action, sort_keys=True)

        if key in seen:
            continue

        seen.add(key)
        unique.append(action)

    if unique:
        return unique

    if moves:
        return moves

    if walls:
        return walls[:1]

    if isinstance(actions, list) and actions:
        return [actions[0]]

    return []


def choose_action(raw_state):
    legal_actions = raw_state.get("legal_actions", [])

    if not isinstance(legal_actions, list) or not legal_actions:
        return {
            "type": "action",
            "action": "move",
            "to": "e1"
        }

    you = raw_state.get("you")
    enemy = opponent(you)
    state = make_state(raw_state)

    moves = legal_moves_from_input(legal_actions)

    for move in moves:
        to = parse_pos(move.get("to"))

        if is_goal(to, you):
            return output_action(move)

    my_dist, _ = shortest_path(state["pos"][you], you, state["blocked"])
    enemy_dist, _ = shortest_path(state["pos"][enemy], enemy, state["blocked"])

    depth = MAX_DEPTH

    if my_dist <= 4 or enemy_dist <= 4:
        depth = 5

    if state["rem"].get("P1", 0) + state["rem"].get("P2", 0) <= 4:
        depth = 5

    candidates = root_candidates(raw_state, state)

    if not candidates:
        return output_action(legal_actions[0])

    cache = {}
    best_action = None
    best_score = -INF
    alpha = -INF
    beta = INF

    for action in candidates:
        child = apply_action(state, you, action)
        score = search(child, enemy, you, depth - 1, alpha, beta, cache)

        if score > best_score:
            best_score = score
            best_action = action

        if score > alpha:
            alpha = score

    if best_action is not None:
        return output_action(best_action)

    return output_action(legal_actions[0])


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
                "error:",
                error,
                file=sys.stderr,
                flush=True
            )


if __name__ == "__main__":
    main()