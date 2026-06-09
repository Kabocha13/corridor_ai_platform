from __future__ import annotations

from .action import GameAction
from .rules import legal_actions
from .state import GameState, Player


def action_to_json(action: GameAction) -> dict[str, str]:
    return action.to_json()


def state_for_ai(state: GameState, match_id: str, you: Player) -> dict:
    return {
        "type": "state",
        "match_id": match_id,
        "turn_index": state.turn_index,
        "you": you,
        "turn": state.turn,
        "board_size": 9,
        "pawns": dict(state.pawns),
        "walls": [wall.to_json() for wall in state.walls],
        "remaining_walls": dict(state.remaining_walls),
        "legal_actions": [action_to_json(action) for action in legal_actions(state)],
    }


def state_for_log(state: GameState) -> dict:
    return {
        "type": "state",
        "turn_index": state.turn_index,
        "turn": state.turn,
        "pawns": dict(state.pawns),
        "walls": [wall.to_json() for wall in state.walls],
        "remaining_walls": dict(state.remaining_walls),
    }

