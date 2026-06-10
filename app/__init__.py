import json
import os

from flask import Flask
from flask_socketio import SocketIO
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()
socketio = SocketIO()


def create_app(config_overrides: dict = None):
    app = Flask(
        __name__,
        template_folder=os.path.join(os.path.dirname(os.path.dirname(__file__)), 'templates'),
        static_folder=os.path.join(os.path.dirname(os.path.dirname(__file__)), 'static'),
    )

    app.config.from_object('app.config.Config')
    if config_overrides:
        app.config.update(config_overrides)

    db.init_app(app)
    socketio.init_app(app, cors_allowed_origins='*', async_mode='gevent')

    with app.app_context():
        from .models import User, Player, Game, GamePlayer  # noqa
        db.create_all()

        # Mark stale games abandoned so the lobby starts clean
        Game.query.filter(Game.status.in_(['waiting', 'active'])).update(
            {'status': 'abandoned'}, synchronize_session=False
        )
        db.session.commit()

        # Seed players on first boot
        if Player.query.count() == 0:
            _seed_players()

        # Build in-memory indexes and prompt pool
        _rebuild_indexes(app)

        # Register routes and socket handlers
        from . import routes  # noqa
        from . import sockets  # noqa
        app.register_blueprint(routes.bp)

    return app


def _seed_players():
    from .models import Player
    from .game_logic import clean_player_record

    data_path = os.path.join(
        os.path.dirname(os.path.dirname(__file__)), 'data', 'players_pl.json'
    )
    if not os.path.exists(data_path):
        return

    with open(data_path, 'r', encoding='utf-8') as f:
        raw_players = json.load(f)

    rows = []
    for raw in raw_players:
        c = clean_player_record(raw)
        rows.append(Player(
            name=c['name'],
            name_key=c['name_key'],
            country=c['country'],
            positions=c['positions'],
            clubs=c['clubs'],
            apps=c['apps'],
        ))
    db.session.bulk_save_objects(rows)
    db.session.commit()


def _rebuild_indexes(app):
    from .models import Player
    from .game_logic import build_indexes, build_prompt_pool
    from .game_manager import set_player_index

    players = Player.query.all()
    player_dicts = [
        {
            'name': p.name,
            'name_key': p.name_key,
            'country': p.country or '',
            'positions': p.positions or '',
            'clubs': p.clubs or '',
            'apps': p.apps or 0,
        }
        for p in players
    ]

    idx = build_indexes(player_dicts)
    pool = build_prompt_pool(idx)
    set_player_index(idx, pool)

    app.logger.info(f'Player index built: {len(player_dicts)} players, {len(pool)} prompts in pool')
