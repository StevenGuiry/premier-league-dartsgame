from datetime import datetime
from . import db


class User(db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(32), unique=True, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    is_admin = db.Column(db.Boolean, default=False)


class Player(db.Model):
    __tablename__ = 'players'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    name_key = db.Column(db.String(100), nullable=False, index=True)
    country = db.Column(db.String(3))
    positions = db.Column(db.String(20))
    clubs = db.Column(db.Text)
    apps = db.Column(db.Integer)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow)


class Game(db.Model):
    __tablename__ = 'games'
    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(8), unique=True, nullable=False, index=True)
    status = db.Column(db.String(12), nullable=False, default='waiting')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    finished_at = db.Column(db.DateTime, nullable=True)
    winner_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    state_json = db.Column(db.JSON, nullable=True)


class GamePlayer(db.Model):
    __tablename__ = 'game_players'
    id = db.Column(db.Integer, primary_key=True)
    game_id = db.Column(db.Integer, db.ForeignKey('games.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    seat = db.Column(db.SmallInteger, nullable=False)
    final_score = db.Column(db.Integer)
    turns_taken = db.Column(db.Integer, default=0)
    won = db.Column(db.Boolean, default=False)
    forfeit_count = db.Column(db.Integer, default=0)

    __table_args__ = (
        db.UniqueConstraint('game_id', 'seat', name='uq_game_seat'),
        db.Index('ix_gp_user_id', 'user_id', 'id'),
    )
