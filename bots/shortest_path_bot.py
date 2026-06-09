import json
import sys
from collections import deque


COLS = "abcdefghi"


def coord_to_xy(coord):
    return COLS.index(coord[0]) + 1, int(coord[1])


def xy_to_coord(x, y):
    return f"{COLS[x - 1]}{y}"


def blocked_segments(wall):
    x, y = coord_to_xy(wall["at"])
    if wall["orientation"] == "h":
        raw = [((x, y), (x, y + 1)), ((x + 1, y), (x + 1, y + 1))]
    else:
        raw = [((x, y), (x + 1, y)), ((x, y + 1), (x + 1, y + 1))]
    return {tuple(sorted(edge)) for edge in raw}


def is_blocked(walls, a, b):
    edge = tuple(sorted((coord_to_xy(a), coord_to_xy(b))))
    return any(edge in blocked_segments(wall) for wall in walls)


def next_step(state):
    you = state["you"]
    goal_y = 9 if you == "P1" else 1
    start = state["pawns"][you]
    occupied = state["pawns"]["P2" if you == "P1" else "P1"]
    queue = deque([(start, [])])
    seen = {start}
    while queue:
        coord, path = queue.popleft()
        if coord_to_xy(coord)[1] == goal_y:
            return path[0] if path else coord
        x, y = coord_to_xy(coord)
        for dx, dy in ((0, 1), (1, 0), (0, -1), (-1, 0)):
            nx, ny = x + dx, y + dy
            if not (1 <= nx <= 9 and 1 <= ny <= 9):
                continue
            target = xy_to_coord(nx, ny)
            if target == occupied or target in seen or is_blocked(state["walls"], coord, target):
                continue
            seen.add(target)
            queue.append((target, [*path, target]))
    return None


def choose(state):
    step = next_step(state)
    for action in state["legal_actions"]:
        if action.get("action") == "move" and action.get("to") == step:
            return {"type": "action", **action}
    return {"type": "action", **state["legal_actions"][0]}


def main():
    for line in sys.stdin:
        print(json.dumps(choose(json.loads(line))), flush=True)


if __name__ == "__main__":
    main()
