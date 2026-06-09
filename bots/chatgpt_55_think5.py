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


def action_kind(action):
    if not isinstance(action, dict):
        return None

    return action.get("action")


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
    if not isinstance(action, dict):
        return None

    at = action.get("at")
    orientation = normalize_orientation(action.get("orientation"))
    pos = parse_pos(at)

    if pos is None or orientation is None:
        return None

    x, y = pos

    if not (1 <= x <= N - 1 and 1 <= y <= N - 1):
        return None

    return x, y, orientation


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


def get_pawn(state, player):
    pawns = state.get("pawns", {})

    if not isinstance(pawns, dict):
        return None

    return parse_pos(pawns.get(player))


def get_remaining(state, player):
    remaining = state.get("remaining_walls", 0)

    if isinstance(remaining, dict):
        remaining = remaining.get(player, 0)

    try:
        return int(remaining)
    except Exception:
        return 0


def read_blocked_edges(state):
    walls = state.get("walls", [])
    blocked = set()

    if not isinstance(walls, list):
        return blocked

    for wall_action in walls:
        w = wall_info(wall_action)

        if w is None:
            continue

        for e in wall_edges(w):
            blocked.add(e)

    return blocked


def can_move(a, b, blocked):
    if a is None or b is None:
        return False

    if not (1 <= b[0] <= N and 1 <= b[1] <= N):
        return False

    return make_edge(a, b) not in blocked


def basic_neighbors(pos, blocked, player=None):
    if pos is None:
        return []

    x, y = pos

    if player == "P1":
        directions = [(0, 1), (-1, 0), (1, 0), (0, -1)]
    elif player == "P2":
        directions = [(0, -1), (-1, 0), (1, 0), (0, 1)]
    else:
        directions = [(0, 1), (0, -1), (-1, 0), (1, 0)]

    result = []

    for dx, dy in directions:
        nxt = (x + dx, y + dy)

        if can_move(pos, nxt, blocked):
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


def add_wall(blocked, action):
    new_blocked = set(blocked)
    w = wall_info(action)

    if w is None:
        return new_blocked

    for e in wall_edges(w):
        new_blocked.add(e)

    return new_blocked


def action_signature(action):
    if not isinstance(action, dict):
        return None

    kind = action.get("action")

    if kind == "move":
        return ("move", action.get("to"))

    if kind == "wall":
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


def force_legal_action(chosen, legal_actions):
    if not isinstance(legal_actions, list) or not legal_actions:
        return {
            "type": "action",
            "action": "move",
            "to": "e1"
        }

    chosen_sig = action_signature(chosen)

    for legal in legal_actions:
        if action_signature(legal) == chosen_sig:
            return output_action(legal)

    return output_action(legal_actions[0])


def legal_moves(legal_actions):
    result = []

    if not isinstance(legal_actions, list):
        return result

    for action in legal_actions:
        if not isinstance(action, dict):
            continue

        if action_kind(action) != "move":
            continue

        if parse_pos(action.get("to")) is None:
            continue

        result.append(action)

    return result


def legal_walls(legal_actions):
    result = []

    if not isinstance(legal_actions, list):
        return result

    for action in legal_actions:
        if not isinstance(action, dict):
            continue

        if action_kind(action) != "wall":
            continue

        if wall_info(action) is None:
            continue

        result.append(action)

    return result


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


def path_block_count(path, action):
    w = wall_info(action)

    if w is None or not path or len(path) < 2:
        return 0

    blocked_edges = set(wall_edges(w))
    count = 0

    for i in range(len(path) - 1):
        if make_edge(path[i], path[i + 1]) in blocked_edges:
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

    best = 999

    for c in cells:
        for i, p in enumerate(path):
            d = abs(c[0] - p[0]) + abs(c[1] - p[1])
            value = d * 10 + i

            if value < best:
                best = value

    return max(0, 120 - best * 3)


def evaluate_move(state, action, blocked):
    you = state.get("you")
    enemy = opponent(you)

    my_pos = get_pawn(state, you)
    enemy_pos = get_pawn(state, enemy)
    to_pos = parse_pos(action.get("to"))

    if to_pos is None:
        return -INF

    my_dist, my_path = shortest_path(to_pos, you, blocked)
    enemy_dist, enemy_path = shortest_path(enemy_pos, enemy, blocked)

    score = 0
    score += (enemy_dist - my_dist) * 12000
    score -= my_dist * 700
    score += enemy_dist * 500
    score += progress_score(my_pos, to_pos, you) * 1000
    score += center_score(to_pos) * 80

    if is_goal(to_pos, you):
        score += WIN

    if enemy_path and len(enemy_path) <= 3:
        score -= (4 - len(enemy_path)) * 2000

    if my_path and len(my_path) <= 3:
        score += (4 - len(my_path)) * 1800

    return score


def evaluate_wall(state, action, blocked):
    you = state.get("you")
    enemy = opponent(you)

    my_pos = get_pawn(state, you)
    enemy_pos = get_pawn(state, enemy)

    base_my_dist, base_my_path = shortest_path(my_pos, you, blocked)
    base_enemy_dist, base_enemy_path = shortest_path(enemy_pos, enemy, blocked)

    new_blocked = add_wall(blocked, action)

    my_dist, _ = shortest_path(my_pos, you, new_blocked)
    enemy_dist, _ = shortest_path(enemy_pos, enemy, new_blocked)

    if my_dist >= INF or enemy_dist >= INF:
        return -INF

    gain = enemy_dist - base_enemy_dist
    pain = my_dist - base_my_dist

    score = 0
    score += gain * 5200
    score -= pain * 4300
    score += (enemy_dist - my_dist) * 600

    score += path_block_count(base_enemy_path, action) * 2500
    score -= path_block_count(base_my_path, action) * 1700
    score += wall_near_path_score(base_enemy_path, action) * 10

    if base_enemy_dist <= base_my_dist:
        score += 1800

    if base_enemy_dist <= 5:
        score += 1200

    if base_enemy_dist <= 3:
        score += 3000

    if base_enemy_dist <= 2:
        score += 6000

    if gain <= 0:
        score -= 5000

    if pain > gain:
        score -= (pain - gain) * 4000

    if gain >= 2 and pain <= 1:
        score += 2500

    if gain >= 3 and pain <= 2:
        score += 4000

    if gain >= 4:
        score += 6000

    return score


def simulate_after_action(state, action):
    you = state.get("you")
    enemy = opponent(you)

    new_state = dict(state)
    pawns = dict(state.get("pawns", {}))

    if action_kind(action) == "move":
        pawns[you] = action.get("to")
        new_state["pawns"] = pawns
        return new_state

    return new_state


def opponent_best_reply_penalty(state, action, blocked):
    you = state.get("you")
    enemy = opponent(you)

    after_state = simulate_after_action(state, action)

    my_pos = get_pawn(after_state, you)
    enemy_pos = get_pawn(after_state, enemy)

    if action_kind(action) == "wall":
        after_blocked = add_wall(blocked, action)
    else:
        after_blocked = blocked

    enemy_moves = []

    for nxt in basic_neighbors(enemy_pos, after_blocked, enemy):
        enemy_moves.append({
            "action": "move",
            "to": pos_to_str(nxt)
        })

    if not enemy_moves:
        return 0

    worst = -INF

    for enemy_move in enemy_moves:
        to_pos = parse_pos(enemy_move.get("to"))

        enemy_dist, _ = shortest_path(to_pos, enemy, after_blocked)
        my_dist, _ = shortest_path(my_pos, you, after_blocked)

        value = (my_dist - enemy_dist) * 5000

        if is_goal(to_pos, enemy):
            value += WIN

        if value > worst:
            worst = value

    return worst


def choose_action_inner(state):
    legal_actions = state.get("legal_actions", [])

    if not isinstance(legal_actions, list) or not legal_actions:
        return None

    you = state.get("you")
    blocked = read_blocked_edges(state)

    moves = legal_moves(legal_actions)
    walls = legal_walls(legal_actions)

    for move in moves:
        to_pos = parse_pos(move.get("to"))

        if is_goal(to_pos, you):
            return move

    candidates = []

    for move in moves:
        score = evaluate_move(state, move, blocked)
        score -= opponent_best_reply_penalty(state, move, blocked) * 0.20
        candidates.append((score, move))

    if get_remaining(state, you) > 0:
        for wall in walls:
            score = evaluate_wall(state, wall, blocked)
            score -= opponent_best_reply_penalty(state, wall, blocked) * 0.20
            candidates.append((score, wall))

    if not candidates:
        return legal_actions[0]

    candidates.sort(reverse=True, key=lambda item: item[0])

    return candidates[0][1]


def choose_action(state):
    legal_actions = state.get("legal_actions", [])

    try:
        chosen = choose_action_inner(state)
    except Exception as error:
        print(
            "choose_action_error:",
            error,
            file=sys.stderr,
            flush=True
        )
        chosen = None

    return force_legal_action(chosen, legal_actions)


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