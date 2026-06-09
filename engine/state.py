from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

from .action import WallAction


Player = Literal["P1", "P2"]
Winner = Literal["P1", "P2", "DRAW"]
Reason = Literal["goal", "max_turn_draw", "engine_error"]


@dataclass
class GameState:
    turn: Player = "P1"
    turn_index: int = 0
    pawns: dict[Player, str] = field(default_factory=lambda: {"P1": "e1", "P2": "e9"})
    walls: list[WallAction] = field(default_factory=list)
    remaining_walls: dict[Player, int] = field(default_factory=lambda: {"P1": 10, "P2": 10})
    winner: Winner | None = None
    reason: Reason | None = None

    def copy(self) -> "GameState":
        return GameState(
            turn=self.turn,
            turn_index=self.turn_index,
            pawns=dict(self.pawns),
            walls=list(self.walls),
            remaining_walls=dict(self.remaining_walls),
            winner=self.winner,
            reason=self.reason,
        )

