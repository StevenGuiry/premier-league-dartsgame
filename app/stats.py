"""Compute user stats and achievements from DB — no denormalized counters."""
from sqlalchemy import func
from . import db
from .models import User, Game, GamePlayer


def get_user_stats(user_id: int) -> dict:
    row = db.session.query(
        func.count(GamePlayer.id).label('games_played'),
        func.sum(func.cast(GamePlayer.won, db.Integer)).label('games_won'),
        func.min(GamePlayer.final_score).label('best_score'),
        func.avg(GamePlayer.final_score).label('avg_score'),
        func.sum(GamePlayer.turns_taken).label('total_turns'),
        func.sum(GamePlayer.forfeit_count).label('total_forfeits'),
        func.sum(
            func.cast(
                db.and_(GamePlayer.won, GamePlayer.final_score == 0),
                db.Integer,
            )
        ).label('perfect_games'),
    ).filter(GamePlayer.user_id == user_id).one()

    games_played = row.games_played or 0
    games_won = int(row.games_won or 0)
    return {
        'games_played': games_played,
        'games_won': games_won,
        'games_lost': games_played - games_won,
        'best_score': row.best_score if row.best_score is not None else 501,
        'average_score': round(float(row.avg_score or 0), 1),
        'total_turns': int(row.total_turns or 0),
        'total_forfeits': int(row.total_forfeits or 0),
        'perfect_games': int(row.perfect_games or 0),
    }


def get_recent_games(user_id: int, limit: int = 10) -> list:
    # Join game_players with games and get opponent's username
    my_gp = db.aliased(GamePlayer)
    opp_gp = db.aliased(GamePlayer)
    opp_user = db.aliased(User)

    rows = (
        db.session.query(
            Game.code,
            Game.finished_at,
            my_gp.won,
            my_gp.final_score,
            my_gp.turns_taken,
            opp_user.username.label('opponent'),
        )
        .join(my_gp, my_gp.game_id == Game.id)
        .outerjoin(opp_gp, db.and_(opp_gp.game_id == Game.id, opp_gp.user_id != user_id))
        .outerjoin(opp_user, opp_user.id == opp_gp.user_id)
        .filter(my_gp.user_id == user_id)
        .filter(Game.status == 'finished')
        .order_by(Game.finished_at.desc())
        .limit(limit)
        .all()
    )

    return [
        {
            'code': r.code,
            'date': r.finished_at.strftime('%d %b %Y %H:%M') if r.finished_at else '—',
            'won': r.won,
            'final_score': r.final_score,
            'turns_taken': r.turns_taken,
            'opponent': r.opponent or '—',
        }
        for r in rows
    ]


def compute_achievements(stats: dict) -> list:
    achievements = []
    if stats['games_won'] >= 1:
        achievements.append('first_win')
    if stats['games_played'] >= 10:
        achievements.append('dedicated_player')
    if stats['perfect_games'] >= 1:
        achievements.append('perfect_game')
    if stats['games_won'] >= 5:
        achievements.append('consistent_winner')
    if stats['average_score'] <= 100 and stats['games_played'] >= 5:
        achievements.append('sharp_shooter')
    return achievements


ACHIEVEMENT_LABELS = {
    'first_win': ('First Win', 'Win your first game'),
    'dedicated_player': ('Dedicated Player', 'Play 10 games'),
    'perfect_game': ('Perfect Game', 'Win with exactly 0 points'),
    'consistent_winner': ('Consistent Winner', 'Win 5 games'),
    'sharp_shooter': ('Sharp Shooter', 'Average score ≤ 100 over 5+ games'),
}
