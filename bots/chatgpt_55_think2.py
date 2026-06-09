import sys
import json
from collections import deque

BOARD_SIZE = 9
INF = 10**9


def parse_pos(pos):
    if not isinstance(pos, str) or len(pos) < 2:
        return None

    c = pos[0].lower()

    if c < "a" or c > "i":
        return None

    try:
        y = int(pos[1:])
    except ValueError:
        return None

    x = ord(c) - ord("a") + 1

    if not (1 <= x <= BOARD_SIZE and 1 <= y <= BOARD_SIZE):
        return None

    return x, y


def opponent_of(player):
    if player == "P1":
        return "P2"
    return "P1"


def goal_reached(pos, player):
    if pos is None:
        return False

    if player == "P1":
        return pos[1] == BOARD_SIZE

    return pos[1] == 1


def get_pawn(state, player):
    pawns = state.get("pawns", {})

    if not isinstance(pawns, dict):
        return None

    return parse_pos(pawns.get(player))


def get_remaining_walls(state, player):
    remaining = state.get("remaining_walls", 0)

    if isinstance(remaining, dict):
        remaining = remaining.get(player, 0)

    try:
        return int(remaining)
    except Exception:
        return 0


def normalize_orientation(orientation):
    if not isinstance(orientation, str) or not orientation:
        return None

    orientation = orientation.lower()

    if orientation.startswith("h"):
        return "h"

    if orientation.startswith("v"):
        return "v"

    return None


def get_wall(action):
    if not isinstance(action, dict):
        return None

    at = action.get("at")
    orientation = normalize_orientation(action.get("orientation"))
    pos = parse_pos(at)

    if pos is None or orientation is None:
        return None

    x, y = pos

    if not (1 <= x <= BOARD_SIZE - 1 and 1 <= y <= BOARD_SIZE - 1):
        return None

    return at, orientation


def make_edge(a, b):
    return tuple(sorted((a, b)))


def wall_edges(wall):
    if wall is None:
        return []

    at, orientation = wall
    pos = parse_pos(at)

    if pos is None:
        return []

    x, y = pos
    edges = []

    if orientation == "h":
        edges.append(((x, y), (x, y + 1)))
        edges.append(((x + 1, y), (x + 1, y + 1)))
    else:
        edges.append(((x, y), (x + 1, y)))
        edges.append(((x, y + 1), (x + 1, y + 1)))

    return edges


def build_blocked_edges(walls):
    blocked = set()

    if not isinstance(walls, list):
        return blocked

    for wall_action in walls:
        wall = get_wall(wall_action)

        for a, b in wall_edges(wall):
            blocked.add(make_edge(a, b))

    return blocked


def add_wall_to_blocked(blocked, action):
    new_blocked = set(blocked)
    wall = get_wall(action)

    for a, b in wall_edges(wall):
        new_blocked.add(make_edge(a, b))

    return new_blocked


def neighbors(pos, player, blocked):
    x, y = pos

    if player == "P1":
        directions = [(0, 1), (-1, 0), (1, 0), (0, -1)]
    else:
        directions = [(0, -1), (-1, 0), (1, 0), (0, 1)]

    result = []

    for dx, dy in directions:
        nx = x + dx
        ny = y + dy

        if not (1 <= nx <= BOARD_SIZE and 1 <= ny <= BOARD_SIZE):
            continue

        nxt = (nx, ny)

        if make_edge(pos, nxt) in blocked:
            continue

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

        if goal_reached(cur, player):
            path = [cur]

            while cur in prev:
                cur = prev[cur]
                path.append(cur)

            path.reverse()
            return dist[path[-1]], path

        for nxt in neighbors(cur, player, blocked):
            if nxt in dist:
                continue

            dist[nxt] = dist[cur] + 1
            prev[nxt] = cur
            queue.append(nxt)

    return INF, []


def action_without_type(action):
    if not isinstance(action, dict):
        return {}

    return {
        key: value
        for key, value in action.items()
        if key != "type"
    }


def make_output_action(action):
    base = action_without_type(action)
    result = {"type": "action"}

    for key, value in base.items():
        result[key] = value

    return result


def action_kind(action):
    if not isinstance(action, dict):
        return None

    return action.get("action")


def legal_moves(legal_actions):
    if not isinstance(legal_actions, list):
        return []

    result = []

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
    if not isinstance(legal_actions, list):
        return []

    result = []

    for action in legal_actions:
        if not isinstance(action, dict):
            continue

        if action_kind(action) != "wall":
            continue

        if get_wall(action) is None:
            continue

        result.append(action)

    return result


def move_progress(old_pos, new_pos, player):
    if old_pos is None or new_pos is None:
        return 0

    if player == "P1":
        return new_pos[1] - old_pos[1]

    return old_pos[1] - new_pos[1]


def center_score(pos):
    if pos is None:
        return 0

    x, _ = pos
    return -abs(x - 5)


def evaluate_move(state, action, blocked):
    you = state.get("you")
    enemy = opponent_of(you)

    my_pos = get_pawn(state, you)
    enemy_pos = get_pawn(state, enemy)
    to_pos = parse_pos(action.get("to"))

    if to_pos is None:
        return -INF

    my_dist, _ = shortest_path(to_pos, you, blocked)
    enemy_dist, _ = shortest_path(enemy_pos, enemy, blocked)

    score = 0
    score += (enemy_dist - my_dist) * 120
    score += move_progress(my_pos, to_pos, you) * 45
    score += center_score(to_pos) * 5

    if goal_reached(to_pos, you):
        score += 100000

    return score


def best_move(state, moves, blocked):
    best_action = None
    best_score = -INF

    for action in moves:
        score = evaluate_move(state, action, blocked)

        if score > best_score:
            best_score = score
            best_action = action

    return best_action, best_score


def wall_distance_from_enemy(action, enemy_pos):
    wall = get_wall(action)

    if wall is None or enemy_pos is None:
        return 0

    at, _ = wall
    pos = parse_pos(at)

    if pos is None:
        return 0

    wx, wy = pos
    ex, ey = enemy_pos

    return -(abs(wx - ex) + abs(wy - ey))


def evaluate_wall(state, action, blocked, base_my_dist, base_enemy_dist):
    you = state.get("you")
    enemy = opponent_of(you)

    my_pos = get_pawn(state, you)
    enemy_pos = get_pawn(state, enemy)

    new_blocked = add_wall_to_blocked(blocked, action)

    my_dist, _ = shortest_path(my_pos, you, new_blocked)
    enemy_dist, _ = shortest_path(enemy_pos, enemy, new_blocked)

    if my_dist >= INF or enemy_dist >= INF:
        return -INF, 0, 0

    gain = enemy_dist - base_enemy_dist
    pain = my_dist - base_my_dist

    if gain <= 0:
        return -5000 - pain * 300, gain, pain

    urgency = 0

    if base_enemy_dist <= base_my_dist:
        urgency += 200

    if base_enemy_dist <= 4:
        urgency += 160

    if base_enemy_dist <= 2:
        urgency += 400

    score = 0
    score += gain * 360
    score -= pain * 220
    score += urgency
    score += wall_distance_from_enemy(action, enemy_pos) * 4

    return score, gain, pain


def best_wall(state, walls, blocked):
    you = state.get("you")
    enemy = opponent_of(you)

    my_pos = get_pawn(state, you)
    enemy_pos = get_pawn(state, enemy)

    base_my_dist, _ = shortest_path(my_pos, you, blocked)
    base_enemy_dist, _ = shortest_path(enemy_pos, enemy, blocked)

    best_action = None
    best_score = -INF
    best_gain = 0
    best_pain = 0

    for action in walls:
        score, gain, pain = evaluate_wall(
            state,
            action,
            blocked,
            base_my_dist,
            base_enemy_dist
        )

        if score > best_score:
            best_score = score
            best_action = action
            best_gain = gain
            best_pain = pain

    return (
        best_action,
        best_score,
        best_gain,
        best_pain,
        base_my_dist,
        base_enemy_dist
    )


def should_place_wall(score, gain, pain, my_dist, enemy_dist, remaining):
    if remaining <= 0:
        return False

    if gain >= 3 and pain <= 2:
        return True

    if gain >= 2 and pain <= 1:
        return True

    if enemy_dist <= 3 and gain >= 1 and pain <= 2:
        return True

    if enemy_dist <= my_dist and gain >= 1 and pain <= 0:
        return True

    if enemy_dist <= my_dist + 1 and gain >= 2:
        return True

    if remaining >= 6 and score >= 700 and gain > pain:
        return True

    if remaining >= 3 and score >= 850 and gain > pain:
        return True

    return False


def choose_action(state):
    legal_actions = state.get("legal_actions", [])

    if not isinstance(legal_actions, list) or not legal_actions:
        return {
            "type": "action",
            "action": "move",
            "to": "e1"
        }

    you = state.get("you")
    blocked = build_blocked_edges(state.get("walls", []))

    moves = legal_moves(legal_actions)
    walls = legal_walls(legal_actions)

    move_action, _ = best_move(state, moves, blocked)

    wall_action = None
    wall_score = -INF
    gain = 0
    pain = 0
    my_dist = INF
    enemy_dist = INF

    if walls and get_remaining_walls(state, you) > 0:
        (
            wall_action,
            wall_score,
            gain,
            pain,
            my_dist,
            enemy_dist
        ) = best_wall(state, walls, blocked)

    if wall_action is not None:
        remaining = get_remaining_walls(state, you)

        if should_place_wall(
            wall_score,
            gain,
            pain,
            my_dist,
            enemy_dist,
            remaining
        ):
            return make_output_action(wall_action)

    if move_action is not None:
        return make_output_action(move_action)

    return make_output_action(legal_actions[0])


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