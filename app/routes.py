import json
import os

from flask import (Blueprint, current_app, flash, jsonify, redirect,
                   render_template, request, session, url_for)

from . import db
from .models import Game, GamePlayer, Player, User
from .stats import ACHIEVEMENT_LABELS, compute_achievements, get_recent_games, get_user_stats
from .game_manager import (create_game, get_game, get_game_for_user,
                            assign_prompt, lobby_sessions, GAMES, Seat,
                            start_turn_timer)
from .game_logic import normalize_name_key

bp = Blueprint('main', __name__)


# ---------------------------------------------------------------------------
# Auth helpers
# ---------------------------------------------------------------------------

def current_user() -> User | None:
    uid = session.get('user_id')
    if uid:
        return db.session.get(User, uid)
    return None


def login_required(f):
    from functools import wraps

    @wraps(f)
    def decorated(*args, **kwargs):
        if not current_user():
            return redirect(url_for('main.login_page'))
        return f(*args, **kwargs)

    return decorated


# ---------------------------------------------------------------------------
# Auth routes
# ---------------------------------------------------------------------------

@bp.route('/')
def index():
    user = current_user()
    if not user:
        return redirect(url_for('main.login_page'))
    existing = get_game_for_user(user.id)
    if existing:
        return redirect(url_for('main.game_page', code=existing.code))
    return redirect(url_for('main.lobby'))


@bp.route('/login', methods=['GET'])
def login_page():
    if current_user():
        return redirect(url_for('main.lobby'))
    return render_template('login.html')


@bp.route('/login', methods=['POST'])
def login():
    username = request.form.get('username', '').strip()
    if not username or len(username) > 32:
        flash('Please enter a username (max 32 chars).')
        return redirect(url_for('main.login_page'))

    username_lower = username.lower()
    user = User.query.filter(db.func.lower(User.username) == username_lower).first()

    if not user:
        is_admin = (username == current_app.config.get('ADMIN_USERNAME', ''))
        user = User(username=username, is_admin=is_admin)
        db.session.add(user)
        db.session.commit()

    session['user_id'] = user.id
    return redirect(url_for('main.lobby'))


@bp.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('main.login_page'))


# ---------------------------------------------------------------------------
# Lobby
# ---------------------------------------------------------------------------

@bp.route('/lobby')
@login_required
def lobby():
    user = current_user()
    stats = get_user_stats(user.id)
    sessions = lobby_sessions()
    return render_template('lobby.html', user=user, stats=stats, sessions=sessions)


# ---------------------------------------------------------------------------
# Game
# ---------------------------------------------------------------------------

@bp.route('/game/create', methods=['POST'])
@login_required
def create_game_route():
    user = current_user()
    # Don't let a user create a second game while already in one
    existing = get_game_for_user(user.id)
    if existing:
        return redirect(url_for('main.game_page', code=existing.code))

    start_score = current_app.config['START_SCORE']
    game = create_game(start_score)
    assign_prompt(game)

    # Persist game row
    db_game = Game(code=game.code, status='waiting')
    db.session.add(db_game)
    db.session.commit()

    return redirect(url_for('main.game_page', code=game.code))


@bp.route('/game/<code>')
@login_required
def game_page(code):
    user = current_user()
    game = get_game(code)

    if not game or game.status in ('finished', 'abandoned'):
        flash('That game is no longer available.')
        return redirect(url_for('main.lobby'))

    start_score = current_app.config['START_SCORE']
    initial_state = json.dumps(game.to_dict())
    return render_template('game.html', user=user, code=code,
                           initial_state=initial_state, start_score=start_score)


# ---------------------------------------------------------------------------
# Profile
# ---------------------------------------------------------------------------

@bp.route('/game/create-solo', methods=['POST'])
@login_required
def create_solo_game():
    user = current_user()
    difficulty = request.form.get('difficulty', 'easy')
    if difficulty not in ('easy', 'hard'):
        difficulty = 'easy'

    existing = get_game_for_user(user.id)
    if existing:
        return redirect(url_for('main.game_page', code=existing.code))

    start_score = current_app.config['START_SCORE']
    game = create_game(start_score)
    game.is_solo = True
    assign_prompt(game)

    game.seats.append(Seat(user_id=user.id, username=user.username, score=start_score))
    cpu_label = f'CPU ({difficulty.capitalize()})'
    game.seats.append(Seat(user_id=None, username=cpu_label, score=start_score,
                           is_cpu=True, cpu_difficulty=difficulty))

    game.status = 'active'
    start_turn_timer(game)

    db_game = Game(code=game.code, status='active')
    db.session.add(db_game)
    db.session.commit()

    # Schedule the opening-turn expiry (multiplayer does this in on_join_game,
    # rematch in on_rematch). Without it, the human's first solo turn has a
    # client countdown but no server forfeit, so it stalls at 0.
    from . import socketio
    from .sockets import _expire_turn
    socketio.start_background_task(_expire_turn, game.code, game.turn_seq,
                                   current_app._get_current_object())

    return redirect(url_for('main.game_page', code=game.code))


@bp.route('/profile')
@login_required
def profile():
    user = current_user()
    stats = get_user_stats(user.id)
    achievements = compute_achievements(stats)
    recent = get_recent_games(user.id)
    achievement_details = [
        {'key': k, 'label': ACHIEVEMENT_LABELS[k][0], 'desc': ACHIEVEMENT_LABELS[k][1],
         'earned': k in achievements}
        for k in ACHIEVEMENT_LABELS
    ]
    return render_template('profile.html', user=user, stats=stats,
                           achievements=achievement_details, recent_games=recent)


# ---------------------------------------------------------------------------
# API
# ---------------------------------------------------------------------------

@bp.route('/api/players/search')
@login_required
def search_players():
    q = request.args.get('q', '').strip().lower()
    code = request.args.get('code', '')
    if len(q) < 2:
        return jsonify([])

    game = get_game(code) if code else None
    used = game.used_players if game else set()

    from .game_manager import get_player_index
    idx = get_player_index()
    if not idx:
        return jsonify([])

    results = []
    for name_key, player in idx.by_name_key.items():
        if q in name_key and name_key not in used:
            results.append(player['name'])
            if len(results) == 5:
                break

    return jsonify(results)


@bp.route('/admin/refresh-players', methods=['GET'])
@login_required
def admin_refresh_page():
    user = current_user()
    if not user.is_admin:
        return redirect(url_for('main.lobby'))
    return render_template('admin_refresh.html', user=user)


@bp.route('/admin/refresh-players', methods=['POST'])
@login_required
def admin_refresh():
    from . import _rebuild_indexes
    from .game_logic import clean_player_record
    from .models import Player
    from datetime import datetime

    user = current_user()
    if not user.is_admin:
        return jsonify({'error': 'Unauthorized'}), 403

    f = request.files.get('players_json')
    if not f:
        flash('No file uploaded.')
        return redirect(url_for('main.admin_refresh_page'))

    try:
        raw_players = json.load(f)
        assert isinstance(raw_players, list)
    except Exception:
        flash('Invalid JSON file.')
        return redirect(url_for('main.admin_refresh_page'))

    now = datetime.utcnow()
    rows = []
    for raw in raw_players:
        c = clean_player_record(raw)
        rows.append(Player(
            name=c['name'], name_key=c['name_key'], country=c['country'],
            positions=c['positions'], clubs=c['clubs'], apps=c['apps'], updated_at=now,
        ))

    Player.query.delete()
    db.session.bulk_save_objects(rows)
    db.session.commit()

    _rebuild_indexes(current_app)
    flash(f'Player data refreshed: {len(rows)} players loaded.')
    return redirect(url_for('main.admin_refresh_page'))
