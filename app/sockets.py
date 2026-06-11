"""SocketIO event handlers."""
import time
from datetime import datetime

from flask import session
from flask_socketio import emit, join_room, leave_room

from . import db, socketio
from .models import Game, GamePlayer, User
from .game_logic import Outcome, evaluate_submission, cpu_pick
from .game_manager import (GAMES, assign_prompt, create_game, get_game,
                            get_player_index, lobby_sessions, start_turn_timer)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _current_user_id() -> int | None:
    return session.get('user_id')


def _sync_game_db(game, app):
    """Persist state_json snapshot and optionally mark finished."""
    with app.app_context():
        db_game = Game.query.filter_by(code=game.code).first()
        if not db_game:
            return
        db_game.state_json = game.to_dict()
        if game.status == 'finished':
            db_game.status = 'finished'
            db_game.finished_at = datetime.utcnow()
            if game.seats:
                winner_seat = next(
                    (i for i, s in enumerate(game.seats) if s.score <= 0), None
                )
                if winner_seat is not None:
                    db_game.winner_id = game.seats[winner_seat].user_id
        elif game.status == 'abandoned':
            db_game.status = 'abandoned'
            db_game.finished_at = datetime.utcnow()
        db.session.commit()


def _record_game_players(game, app):
    with app.app_context():
        db_game = Game.query.filter_by(code=game.code).first()
        if not db_game:
            return
        for i, seat in enumerate(game.seats):
            if seat.is_cpu:
                continue  # CPU has no DB user row
            gp = GamePlayer(
                game_id=db_game.id,
                user_id=seat.user_id,
                seat=i,
                final_score=seat.score,
                turns_taken=seat.turns_taken,
                won=seat.score <= 0,
                forfeit_count=seat.forfeit_count,
            )
            db.session.add(gp)
        try:
            db.session.commit()
        except Exception:
            db.session.rollback()


def _broadcast_lobby(app):
    with app.app_context():
        socketio.emit('lobby_update', {'sessions': lobby_sessions()}, room='lobby')


def _player_info_text(player: dict) -> str:
    pos_map = {'GK': 'Goalkeeper', 'DF': 'Defender', 'MF': 'Midfielder', 'FW': 'Forward'}
    pos_display = '/'.join(
        pos_map.get(p.strip(), p.strip())
        for p in player['positions'].split(',') if p.strip()
    )
    return (
        f"{player['name']} | {player.get('country','?')} | "
        f"{pos_display} | {player['clubs']} | {player['apps']} apps"
    )


# ---------------------------------------------------------------------------
# Connection / lobby
# ---------------------------------------------------------------------------

@socketio.on('connect')
def on_connect():
    uid = _current_user_id()
    if not uid:
        return False  # reject unauthenticated connections


@socketio.on('join_lobby')
def on_join_lobby():
    join_room('lobby')
    emit('lobby_update', {'sessions': lobby_sessions()})


@socketio.on('leave_lobby')
def on_leave_lobby():
    leave_room('lobby')


# ---------------------------------------------------------------------------
# Game events
# ---------------------------------------------------------------------------

@socketio.on('request_state')
def on_request_state(data):
    """Re-send the authoritative state to one client without reconnect side
    effects. Used by the client as a safety net when its turn timer hits 0."""
    uid = _current_user_id()
    if not uid:
        return
    code = data.get('code', '').upper()
    game = get_game(code)
    if game and game.seat_for_user(uid) is not None:
        emit('game_state', game.to_dict())


@socketio.on('join_game')
def on_join_game(data):
    from flask import current_app
    uid = _current_user_id()
    if not uid:
        return

    code = data.get('code', '').upper()
    game = get_game(code)
    if not game:
        emit('error', {'message': 'Game not found.'})
        return

    start_score = current_app.config['START_SCORE']
    user = db.session.get(User, uid)
    if not user:
        return

    existing_seat = game.seat_for_user(uid)

    if existing_seat is not None:
        # Re-attach (reconnect) — bump disconnect_seq to cancel any pending timeout
        game.seats[existing_seat].connected = True
        game.disconnect_seq[existing_seat] = game.disconnect_seq.get(existing_seat, 0) + 1
        join_room(code)
        emit('game_state', game.to_dict())
        socketio.emit('opponent_reconnected', {'seat': existing_seat},
                      room=code, include_self=False)
        return

    if len(game.seats) >= 2:
        emit('error', {'message': 'Game is full.'})
        return

    if game.status != 'waiting':
        emit('error', {'message': 'Game already started.'})
        return

    from .game_manager import Seat
    game.seats.append(Seat(
        user_id=uid,
        username=user.username,
        score=start_score,
    ))
    join_room(code)

    if len(game.seats) == 2:
        game.status = 'active'
        start_turn_timer(game)
        _sync_game_db_bg(game)
        socketio.start_background_task(_expire_turn, code, game.turn_seq,
                                       current_app._get_current_object())

    socketio.emit('game_state', game.to_dict(), room=code)
    _broadcast_lobby(current_app._get_current_object())


@socketio.on('submit_player')
def on_submit_player(data):
    from flask import current_app
    uid = _current_user_id()
    if not uid:
        return

    code = data.get('code', '').upper()
    name = data.get('name', '').strip()
    game = get_game(code)

    if not game or game.status != 'active':
        emit('error', {'message': 'Game not active.'})
        return

    seat_idx = game.seat_for_user(uid)
    if seat_idx is None:
        emit('error', {'message': 'You are not in this game.'})
        return

    if seat_idx != game.current_turn:
        emit('error', {'message': "It's not your turn."})
        return

    idx = get_player_index()
    seat = game.seats[seat_idx]
    outcome, points, player = evaluate_submission(
        seat.score, name, game.used_players, game.prompt, idx
    )

    seat.turns_taken += 1

    if outcome in (Outcome.NOT_FOUND, Outcome.NOT_MATCHING,
                   Outcome.OVER_180, Outcome.INVALID_DART_SCORE,
                   Outcome.ALREADY_USED):
        seat.forfeit_count += 1
        seat.history.append({'name': name, 'result': 'X'})
        messages = {
            Outcome.NOT_FOUND: f'"{name}" not found in the database.',
            Outcome.NOT_MATCHING: f'"{name}" does not match the prompt.',
            Outcome.OVER_180: f'"{name}" has more than 180 appearances.',
            Outcome.INVALID_DART_SCORE: f'"{name}"\'s apps is not a valid dart score.',
            Outcome.ALREADY_USED: f'"{name}" has already been used this game.',
        }
        msg = messages[outcome]
        if player:
            msg += '\n' + _player_info_text(player)
        app = current_app._get_current_object()
        _advance_turn(game)
        _maybe_trigger_cpu(game, app)
        socketio.emit('turn_result', {'outcome': outcome, 'message': msg,
                                      'forfeited': True}, room=code)
        socketio.emit('game_state', game.to_dict(), room=code)
        return

    if outcome == Outcome.BUST:
        seat.forfeit_count += 1
        seat.history.append({'name': player['name'], 'result': 'BUST'})
        msg = f'BUST! Score would go below −20. Turn forfeited.\n{_player_info_text(player)}'
        app = current_app._get_current_object()
        _advance_turn(game)
        _maybe_trigger_cpu(game, app)
        socketio.emit('turn_result', {'outcome': outcome, 'message': msg,
                                      'forfeited': True}, room=code)
        socketio.emit('game_state', game.to_dict(), room=code)
        return

    # Valid score
    game.used_players.add(player['name_key'])
    seat.score -= points
    seat.history.append({'name': player['name'], 'result': points})
    msg = f"{player['name']} accepted: −{points}\n{_player_info_text(player)}"

    if outcome == Outcome.WIN:
        game.status = 'finished'
        game.deadline_epoch = 0.0
        socketio.emit('turn_result', {'outcome': outcome, 'message': msg,
                                      'forfeited': False}, room=code)
        socketio.emit('game_over', {
            'winner_seat': seat_idx,
            'winner_username': seat.username,
            'final_scores': [s.score for s in game.seats],
        }, room=code)
        socketio.emit('game_state', game.to_dict(), room=code)
        app = current_app._get_current_object()
        _record_game_players(game, app)
        _sync_game_db_bg(game)
        _broadcast_lobby(app)
        socketio.start_background_task(_cleanup_game, code, app)
    else:
        app = current_app._get_current_object()
        _advance_turn(game)
        _maybe_trigger_cpu(game, app)
        socketio.emit('turn_result', {'outcome': outcome, 'message': msg,
                                      'forfeited': False}, room=code)
        socketio.emit('game_state', game.to_dict(), room=code)


@socketio.on('leave_game')
def on_leave_game(data):
    from flask import current_app
    uid = _current_user_id()
    if not uid:
        return

    code = data.get('code', '').upper()
    game = get_game(code)
    if not game:
        return

    seat_idx = game.seat_for_user(uid)
    if seat_idx is None:
        return

    leave_room(code)
    app = current_app._get_current_object()

    if game.status == 'active':
        if game.is_solo:
            # No CPU "win" for abandonment — just close the game
            game.status = 'abandoned'
        else:
            winner_seat = 1 - seat_idx
            if winner_seat < len(game.seats):
                game.status = 'finished'
                game.seats[winner_seat].score = 0
                socketio.emit('game_over', {
                    'winner_seat': winner_seat,
                    'winner_username': game.seats[winner_seat].username,
                    'final_scores': [s.score for s in game.seats],
                    'abandoned': True,
                }, room=code)
                _record_game_players(game, app)
        _sync_game_db_bg(game)
    elif game.status == 'waiting':
        game.status = 'abandoned'
        _sync_game_db_bg(game)

    socketio.start_background_task(_cleanup_game, code, app)
    _broadcast_lobby(app)


@socketio.on('rematch')
def on_rematch(data):
    from flask import current_app
    uid = _current_user_id()
    if not uid:
        return

    code = data.get('code', '').upper()
    old_game = get_game(code)
    if not old_game or old_game.status != 'finished':
        return

    seat_idx = old_game.seat_for_user(uid)
    if seat_idx is None:
        return

    app = current_app._get_current_object()
    start_score = current_app.config['START_SCORE']

    # Mark this seat as ready for rematch
    if not hasattr(old_game, 'rematch_ready'):
        old_game.rematch_ready = set()
    old_game.rematch_ready.add(seat_idx)

    # For solo games, only the human needs to accept; for multiplayer, both must.
    human_seat_count = sum(1 for s in old_game.seats if not s.is_cpu)
    if len(old_game.rematch_ready) < human_seat_count:
        emit('rematch_waiting', {'message': 'Waiting for opponent to accept rematch...'})
        return

    # Ready — create a new game preserving seat types
    from .game_manager import Seat
    new_game = create_game(start_score)
    new_game.is_solo = old_game.is_solo
    assign_prompt(new_game)

    for s in old_game.seats:
        new_game.seats.append(Seat(
            user_id=s.user_id, username=s.username, score=start_score,
            is_cpu=s.is_cpu, cpu_difficulty=s.cpu_difficulty,
        ))

    new_game.status = 'active'
    start_turn_timer(new_game)

    db_game = Game(code=new_game.code, status='active')
    db.session.add(db_game)
    db.session.commit()

    socketio.emit('rematch_start', {'code': new_game.code}, room=code)
    socketio.start_background_task(_expire_turn, new_game.code, new_game.turn_seq, app)
    _maybe_trigger_cpu(new_game, app)
    _broadcast_lobby(app)


@socketio.on('disconnect')
def on_disconnect():
    from flask import current_app
    uid = _current_user_id()
    if not uid:
        return

    app = current_app._get_current_object()

    for game in list(GAMES.values()):
        seat_idx = game.seat_for_user(uid)
        if seat_idx is not None and game.status == 'active':
            game.seats[seat_idx].connected = False
            seq = game.disconnect_seq.get(seat_idx, 0) + 1
            game.disconnect_seq[seat_idx] = seq
            if not game.is_solo:
                socketio.emit('opponent_disconnected', {'seat': seat_idx}, room=game.code)
            socketio.start_background_task(
                _handle_disconnect_timeout, game.code, seat_idx, seq, uid, app
            )
            break


# ---------------------------------------------------------------------------
# Background tasks
# ---------------------------------------------------------------------------

def _maybe_trigger_cpu(game, app) -> None:
    """Schedule a CPU turn if the current seat is a CPU."""
    if game.status != 'active':
        return
    seat = game.seats[game.current_turn]
    if seat.is_cpu:
        socketio.start_background_task(_cpu_take_turn, game.code, game.turn_seq, app)


def _advance_turn(game) -> None:
    start_turn_timer(game)
    game.current_turn = (game.current_turn + 1) % 2
    from flask import current_app
    socketio.start_background_task(
        _expire_turn, game.code, game.turn_seq,
        current_app._get_current_object()
    )


def _expire_turn(code: str, captured_seq: int, app) -> None:
    import gevent
    gevent.sleep(60)
    with app.app_context():
        game = get_game(code)
        if not game or game.status != 'active':
            return
        if game.turn_seq != captured_seq:
            return  # A newer turn is running; this task is stale

        seat = game.seats[game.current_turn]
        if seat.is_cpu:
            # CPU should never actually time out — stale guard covers this
            return

        seat.turns_taken += 1
        seat.forfeit_count += 1
        seat.history.append({'name': 'Timeout', 'result': 'X'})

        game.current_turn = (game.current_turn + 1) % 2
        start_turn_timer(game)

        socketio.emit('turn_result', {
            'outcome': 'timeout',
            'message': "Time's up! Turn forfeited.",
            'forfeited': True,
        }, room=code)
        socketio.emit('game_state', game.to_dict(), room=code)

        socketio.start_background_task(_expire_turn, code, game.turn_seq, app)
        _maybe_trigger_cpu(game, app)


def _cpu_take_turn(code: str, captured_seq: int, app) -> None:
    import gevent
    gevent.sleep(1.5)
    with app.app_context():
        game = get_game(code)
        if not game or game.status != 'active':
            return
        if game.turn_seq != captured_seq:
            return

        cpu_seat_idx = game.current_turn
        seat = game.seats[cpu_seat_idx]
        if not seat.is_cpu:
            return

        idx = get_player_index()
        player = cpu_pick(seat.score, game.used_players, game.prompt, idx, seat.cpu_difficulty)
        seat.turns_taken += 1

        if player is None:
            # No valid pick — CPU forfeits its turn
            seat.forfeit_count += 1
            seat.history.append({'name': '—', 'result': 'X'})
            game.current_turn = (game.current_turn + 1) % 2
            start_turn_timer(game)
            socketio.emit('turn_result', {
                'outcome': 'forfeit',
                'message': f'{seat.username} has no valid pick — turn skipped.',
                'forfeited': True,
            }, room=code)
            socketio.emit('game_state', game.to_dict(), room=code)
            socketio.start_background_task(_expire_turn, code, game.turn_seq, app)
            return

        apps = player['apps']
        new_score = seat.score - apps
        game.used_players.add(player['name_key'])
        seat.score = new_score
        seat.history.append({'name': player['name'], 'result': apps})
        msg = f"{seat.username} plays: {player['name']} (−{apps})"

        if -20 <= new_score <= 0:
            game.status = 'finished'
            game.deadline_epoch = 0.0
            socketio.emit('turn_result', {'outcome': Outcome.WIN, 'message': msg,
                                          'forfeited': False}, room=code)
            socketio.emit('game_over', {
                'winner_seat': cpu_seat_idx,
                'winner_username': seat.username,
                'final_scores': [s.score for s in game.seats],
            }, room=code)
            socketio.emit('game_state', game.to_dict(), room=code)
            _record_game_players(game, app)
            _sync_game_db_bg(game)
            _broadcast_lobby(app)
            socketio.start_background_task(_cleanup_game, code, app)
        else:
            game.current_turn = (game.current_turn + 1) % 2
            start_turn_timer(game)
            socketio.emit('turn_result', {'outcome': Outcome.SCORED, 'message': msg,
                                          'forfeited': False}, room=code)
            socketio.emit('game_state', game.to_dict(), room=code)
            socketio.start_background_task(_expire_turn, code, game.turn_seq, app)


def _handle_disconnect_timeout(code: str, seat_idx: int,
                                captured_seq: int, uid: int, app) -> None:
    import gevent
    gevent.sleep(60)
    with app.app_context():
        game = get_game(code)
        if not game or game.status != 'active':
            return
        if game.disconnect_seq.get(seat_idx) != captured_seq:
            return  # Player reconnected (seq was bumped in on_join_game)

        if game.is_solo:
            # Solo game — human left, just abandon; CPU cannot "win" by forfeit
            game.status = 'abandoned'
            _sync_game_db_bg(game)
            _broadcast_lobby(app)
            return

        # Multiplayer — opponent wins (mirror on_leave_game so the win is
        # actually credited: set winner score to 0 and mark finished, otherwise
        # _record_game_players records won=False for everyone).
        winner_seat = 1 - seat_idx
        if winner_seat < len(game.seats):
            game.status = 'finished'
            game.seats[winner_seat].score = 0
            socketio.emit('game_over', {
                'winner_seat': winner_seat,
                'winner_username': game.seats[winner_seat].username,
                'final_scores': [s.score for s in game.seats],
                'abandoned': True,
            }, room=code)
            _record_game_players(game, app)
            _sync_game_db_bg(game)
        _broadcast_lobby(app)


def _sync_game_db_bg(game) -> None:
    from flask import current_app
    socketio.start_background_task(_sync_game_db, game, current_app._get_current_object())


def _cleanup_game(code: str, app) -> None:
    import gevent
    gevent.sleep(30)
    with app.app_context():
        game = get_game(code)
        if game and game.status in ('finished', 'abandoned'):
            GAMES.pop(code, None)
