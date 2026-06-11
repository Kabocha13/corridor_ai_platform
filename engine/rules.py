from __future__ import annotations

from collections import deque
from typing import Iterable

from .action import GameAction, MoveAction, WallAction, action_key
from .pathfinding import has_path_to_goal
from .state import GameState, Player

BOARD_SIZE = 9
MAX_TURNS = 300
COLS = "abcdefghi"


def initial_state() -> GameState:
    return GameState()


def opponent(player: Player) -> Player:
    return "P2" if player == "P1" else "P1"


def coord_to_xy(coord: str) -> tuple[int, int]:
    if len(coord) != 2 or coord[0] not in COLS or not coord[1].isdigit():
        raise ValueError(f"Invalid coordinate: {coord}")
    x = COLS.index(coord[0]) + 1
    y = int(coord[1])
    if not (1 <= x <= BOARD_SIZE and 1 <= y <= BOARD_SIZE):
        raise ValueError(f"Invalid coordinate: {coord}")
    return x, y


def xy_to_coord(x: int, y: int) -> str:
    if not (1 <= x <= BOARD_SIZE and 1 <= y <= BOARD_SIZE):
        raise ValueError(f"Invalid xy: {(x, y)}")
    return f"{COLS[x - 1]}{y}"


def valid_wall_base(coord: str) -> bool:
    try:
        x, y = coord_to_xy(coord)
    except ValueError:
        return False
    return 1 <= x <= BOARD_SIZE - 1 and 1 <= y <= BOARD_SIZE - 1


def blocked_segments(wall: WallAction) -> set[tuple[tuple[int, int], tuple[int, int]]]:
    x, y = coord_to_xy(wall.at)
    if wall.orientation == "h":
        raw = [((x, y), (x, y + 1)), ((x + 1, y), (x + 1, y + 1))]
    else:
        raw = [((x, y), (x + 1, y)), ((x, y + 1), (x + 1, y + 1))]
    return {tuple(sorted(edge)) for edge in raw}  # type: ignore[arg-type]


def blocked_by_wall(state: GameState, from_coord: str, to_coord: str) -> bool:
    a = coord_to_xy(from_coord)
    b = coord_to_xy(to_coord)
    edge = tuple(sorted((a, b)))
    return any(edge in blocked_segments(wall) for wall in state.walls)


def wall_overlap_or_cross(state: GameState, wall: WallAction) -> bool:
    if not valid_wall_base(wall.at):
        return True
    new_segments = blocked_segments(wall)
    for existing in state.walls:
        if existing.at == wall.at and existing.orientation != wall.orientation:
            return True
        if new_segments & blocked_segments(existing):
            return True
    return False


def legal_pawn_moves(state: GameState) -> list[MoveAction]:
    current = state.pawns[state.turn]
    x, y = coord_to_xy(current)
    occupied = state.pawns[opponent(state.turn)]
    moves: list[MoveAction] = []
    for dx, dy in ((0, 1), (1, 0), (0, -1), (-1, 0)):
        nx, ny = x + dx, y + dy
        if not (1 <= nx <= BOARD_SIZE and 1 <= ny <= BOARD_SIZE):
            continue
        target = xy_to_coord(nx, ny)
        if blocked_by_wall(state, current, target):
            continue
        if target != occupied:
            moves.append(MoveAction(action="move", to=target))
            continue

        jump_x, jump_y = nx + dx, ny + dy
        if 1 <= jump_x <= BOARD_SIZE and 1 <= jump_y <= BOARD_SIZE:
            jump_target = xy_to_coord(jump_x, jump_y)
            if not blocked_by_wall(state, occupied, jump_target):
                moves.append(MoveAction(action="move", to=jump_target))
                continue

        for side_dx, side_dy in _perpendicular_directions(dx, dy):
            side_x, side_y = nx + side_dx, ny + side_dy
            if not (1 <= side_x <= BOARD_SIZE and 1 <= side_y <= BOARD_SIZE):
                continue
            side_target = xy_to_coord(side_x, side_y)
            if not blocked_by_wall(state, occupied, side_target):
                moves.append(MoveAction(action="move", to=side_target))
    return moves


def _perpendicular_directions(dx: int, dy: int) -> tuple[tuple[int, int], tuple[int, int]]:
    if dx == 0:
        return ((1, 0), (-1, 0))
    return ((0, 1), (0, -1))


def legal_wall_actions(state: GameState) -> list[WallAction]:
    if state.remaining_walls[state.turn] <= 0:
        return []
    actions: list[WallAction] = []
    base_edges = _blocked_edge_set(state.walls)
    for x in range(1, BOARD_SIZE):
        for y in range(1, BOARD_SIZE):
            at = xy_to_coord(x, y)
            for orientation in ("h", "v"):
                wall = WallAction(action="wall", at=at, orientation=orientation)
                if wall_overlap_or_cross(state, wall):
                    continue
                edges = base_edges | blocked_segments(wall)
                if _has_path_with_edges(state, "P1", edges) and _has_path_with_edges(state, "P2", edges):
                    actions.append(wall)
    return actions


def legal_actions(state: GameState) -> list[GameAction]:
    return [*legal_pawn_moves(state), *legal_wall_actions(state)]


def is_legal_action(state: GameState, action: GameAction) -> bool:
    return action_key(action) in {action_key(candidate) for candidate in legal_actions(state)}


def apply_action(state: GameState, action: GameAction) -> GameState:
    if not is_legal_action(state, action):
        raise ValueError(f"Illegal action: {action}")
    next_state = state.copy()
    if isinstance(action, MoveAction):
        next_state.pawns[state.turn] = action.to
    else:
        next_state.walls.append(action)
        next_state.remaining_walls[state.turn] -= 1
    winner = check_winner(next_state)
    next_state.turn_index += 1
    if winner:
        next_state.winner = winner
        next_state.reason = "goal"
    elif next_state.turn_index >= MAX_TURNS:
        next_state.winner = "DRAW"
        next_state.reason = "max_turn_draw"
    else:
        next_state.turn = opponent(state.turn)
    return next_state


def check_winner(state: GameState) -> Player | None:
    if coord_to_xy(state.pawns["P1"])[1] == BOARD_SIZE:
        return "P1"
    if coord_to_xy(state.pawns["P2"])[1] == 1:
        return "P2"
    return None


def neighbors_without_pawns(state: GameState, coord: str) -> Iterable[str]:
    x, y = coord_to_xy(coord)
    for dx, dy in ((0, 1), (1, 0), (0, -1), (-1, 0)):
        nx, ny = x + dx, y + dy
        if 1 <= nx <= BOARD_SIZE and 1 <= ny <= BOARD_SIZE:
            target = xy_to_coord(nx, ny)
            if not blocked_by_wall(state, coord, target):
                yield target


def _blocked_edge_set(walls: list[WallAction]) -> set[tuple[tuple[int, int], tuple[int, int]]]:
    edges: set[tuple[tuple[int, int], tuple[int, int]]] = set()
    for wall in walls:
        edges.update(blocked_segments(wall))
    return edges


def _has_path_with_edges(
    state: GameState,
    player: Player,
    blocked_edges: set[tuple[tuple[int, int], tuple[int, int]]],
) -> bool:
    start = state.pawns[player]
    goal_y = BOARD_SIZE if player == "P1" else 1
    seen = {start}
    queue: deque[str] = deque([start])
    while queue:
        coord = queue.popleft()
        x, y = coord_to_xy(coord)
        if y == goal_y:
            return True
        for dx, dy in ((0, 1), (1, 0), (0, -1), (-1, 0)):
            nx, ny = x + dx, y + dy
            if not (1 <= nx <= BOARD_SIZE and 1 <= ny <= BOARD_SIZE):
                continue
            edge = tuple(sorted(((x, y), (nx, ny))))
            target = xy_to_coord(nx, ny)
            if edge not in blocked_edges and target not in seen:
                seen.add(target)
                queue.append(target)
    return False
