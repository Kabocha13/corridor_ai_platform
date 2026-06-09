import sys
import json

BOARD_SIZE = 9


def parse_pos(pos):
    if not isinstance(pos, str) or len(pos) < 2:
        return None
    x = ord(pos[0].lower()) - ord("a") + 1
    try:
        y = int(pos[1:])
    except ValueError:
        return None
    if x < 1 or x > BOARD_SIZE or y < 1 or y > BOARD_SIZE:
        return None
    return x, y


def action_without_type(action):
    if not isinstance(action, dict):
        return {}
    return {k: v for k, v in action.items() if k != "type"}


def make_output_action(action):
    a = action_without_type(action)
    a["type"] = "action"
    return a


def get_action_kind(action):
    if not isinstance(action, dict):
        return None
    return action.get("action")


def get_my_pos(state):
    you = state.get("you")
    pawns = state.get("pawns", {})
    return parse_pos(pawns.get(you))


def move_score(state, action):
    you = state.get("you")
    my_pos = get_my_pos(state)
    to_pos = parse_pos(action.get("to"))

    if my_pos is None or to_pos is None:
        return -10**9

    x, y = to_pos
    old_x, old_y = my_pos

    if you == "P1":
        progress = y - old_y
        distance = BOARD_SIZE - y
    else:
        progress = old_y - y
        distance = y - 1

    center_bonus = -abs(x - 5)
    forward_bonus = progress * 100
    distance_bonus = -distance * 10
    side_penalty = -abs(x - old_x)

    return forward_bonus + distance_bonus + center_bonus + side_penalty


def choose_action(state):
    legal_actions = state.get("legal_actions", [])

    if not isinstance(legal_actions, list) or len(legal_actions) == 0:
        return {"type": "action", "action": "move", "to": "e1"}

    moves = [
        a for a in legal_actions
        if isinstance(a, dict) and get_action_kind(a) == "move" and "to" in a
    ]

    if moves:
        best = max(moves, key=lambda a: move_score(state, a))
        return make_output_action(best)

    walls = [
        a for a in legal_actions
        if isinstance(a, dict) and get_action_kind(a) == "wall"
    ]

    if walls:
        return make_output_action(walls[0])

    return make_output_action(legal_actions[0])


def main():
    for line in sys.stdin:
        line = line.strip()

        if not line:
            continue

        try:
            state = json.loads(line)
            action = choose_action(state)
            print(json.dumps(action, ensure_ascii=False, separators=(",", ":")), flush=True)
        except Exception as e:
            print(f"error: {e}", file=sys.stderr, flush=True)


if __name__ == "__main__":
    main()