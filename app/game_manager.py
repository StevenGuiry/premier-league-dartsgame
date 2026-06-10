"""In-memory game session management. Single-worker safe."""
import random
import time
import uuid
from dataclasses import dataclass, field
from typing import Dict, List, Optional

_player_index = None
_prompt_pool: list = []


def set_player_index(index, pool: list) -> None:
    global _player_index, _prompt_pool
    _player_index = index
    _prompt_pool = pool


def get_player_index():
    return _player_index


def get_prompt_pool() -> list:
    return _prompt_pool


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class Seat:
    user_id: int
    username: str
    score: int
    turns_taken: int = 0
    forfeit_count: int = 0
    connected: bool = True
    history: list = field(default_factory=list)


@dataclass
class GameSession:
    code: str
    seats: List[Seat] = field(default_factory=list)
    current_turn: int = 0
    status: str = 'waiting'   # waiting | active | finished | abandoned
    prompt = None
    used_players: set = field(default_factory=set)
    turn_seq: int = 0
    deadline_epoch: float = 0.0
    disconnect_seq: Dict[int, int] = field(default_factory=dict)  # seat -> seq

    def to_dict(self) -> dict:
        return {
            'code': self.code,
            'status': self.status,
            'players': [
                {
                    'username': s.username,
                    'seat': i,
                    'score': s.score,
                    'connected': s.connected,
                    'history': list(s.history),
                }
                for i, s in enumerate(self.seats)
            ],
            'turn_seat': self.current_turn,
            'prompt': {
                'type': self.prompt.type,
                'text': self.prompt.text,
                'club': self.prompt.club,
                'country': self.prompt.country,
                'position': self.prompt.position,
            } if self.prompt else None,
            'deadline_epoch': self.deadline_epoch,
            'turn_seq': self.turn_seq,
        }

    def seat_for_user(self, user_id: int) -> Optional[int]:
        for i, s in enumerate(self.seats):
            if s.user_id == user_id:
                return i
        return None


# ---------------------------------------------------------------------------
# Global store
# ---------------------------------------------------------------------------

GAMES: Dict[str, GameSession] = {}


def create_game(start_score: int = 501) -> GameSession:
    code = uuid.uuid4().hex[:8].upper()
    game = GameSession(code=code)
    GAMES[code] = game
    return game


def get_game(code: str) -> Optional[GameSession]:
    return GAMES.get(code)


def get_game_for_user(user_id: int) -> Optional[GameSession]:
    for game in GAMES.values():
        if game.status in ('waiting', 'active'):
            seat_idx = game.seat_for_user(user_id)
            if seat_idx is not None:
                return game
    return None


def assign_prompt(game: GameSession) -> None:
    pool = get_prompt_pool()
    if pool:
        game.prompt = random.choice(pool)


def start_turn_timer(game: GameSession) -> None:
    game.turn_seq += 1
    game.deadline_epoch = time.time() + 60


def lobby_sessions() -> list:
    return [
        {
            'code': g.code,
            'host': g.seats[0].username if g.seats else '?',
            'player_count': len(g.seats),
            'status': g.status,
        }
        for g in GAMES.values()
        if g.status in ('waiting', 'active')
    ]
