from flask import Flask, render_template, request, jsonify, session, redirect, url_for
import json
import random
import time
import uuid
from typing import List, Dict, Set
from collections import Counter
from datetime import datetime, timedelta

app = Flask(__name__)
app.secret_key = 'your-secret-key-change-this-in-production'  # Change this in production

# Load players data
def load_players_data(file_path: str = "players_pl.json") -> List[Dict]:
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        return []

def get_all_prompt_options(players: List[Dict]) -> Dict[str, List[str]]:
    clubs, countries, positions = [], [], set()
    valid_positions = ['GK', 'DF', 'MF', 'FW']
    country_counter = Counter()
    club_counter = Counter()

    for player in players:
        club = player['clubs'].strip()
        clubs.append(club)
        club_counter[club] += 1

        # Extract country and count occurrences
        country = player['country'].strip()
        countries.append(country)
        country_counter[country] += 1

        # Extract positions (split by comma and filter valid ones)
        if player.get('position'):
            for pos in player['position'].split(','):
                pos = pos.strip()
                if pos in valid_positions:
                    positions.add(pos)

    # Get top 20 most common countries and clubs
    top_countries = [country for country, _ in country_counter.most_common(20)]
    top_clubs = [club for club, _ in club_counter.most_common(20)]

    return {
        'clubs': sorted(top_clubs),
        'countries': sorted(top_countries),
        'positions': sorted(list(positions))
    }

# Generate valid dart scores
def generate_valid_dart_scores() -> Set[int]:
    valid_scores = set()
    singles = list(range(21))
    doubles = [2 * n for n in singles]
    triples = [3 * n for n in singles]
    for a in singles + doubles + triples:
        for b in singles + doubles + triples:
            for c in singles + doubles + triples:
                total = a + b + c
                if total <= 180:
                    valid_scores.add(total)
    return valid_scores

VALID_SCORES = generate_valid_dart_scores()
players_data = load_players_data()
prompt_options = get_all_prompt_options(players_data)

# Global session storage (in production, use Redis or database)
game_sessions = {}

def create_new_session() -> str:
    """Create a new game session and return the session ID"""
    session_id = str(uuid.uuid4())[:8]  # Use first 8 characters for shorter IDs
    
    # Track selected players for this session
    selected_players = set()
    
    # Create game state for this session
    game_state = {
        'players': [{'name': 'Player 1', 'score': 501}, {'name': 'Player 2', 'score': 501}],
        'turn': 0,
        'prompt': None,
        'history': [[], []],
        'message': '',
        'turn_deadline': None,  # Timer starts when both players join
        'selected_players': selected_players,
        'created_at': datetime.now(),
        'last_activity': datetime.now(),
        'player_count': 0,
        'max_players': 2,
        'game_started': False  # Track if game has started
    }
    
    # Set initial prompt
    set_random_prompt_for_session(game_state)
    
    game_sessions[session_id] = game_state
    return session_id

def set_random_prompt_for_session(game_state):
    """Set a random prompt for a specific session"""
    use_club = random.random() < 0.5
    if use_club:
        position = random.choice(prompt_options['positions'])
        club = random.choice(prompt_options['clubs'])
        game_state['prompt'] = {'type': 'club', 'value': club, 'position': position}
    else:
        # Randomly decide between country+position or country+club
        if random.random() < 0.5:
            # country + position
            position = random.choice(prompt_options['positions'])
            country = random.choice(prompt_options['countries'])
            game_state['prompt'] = {'type': 'country', 'value': country, 'position': position}
        else:
            # country + club
            country = random.choice(prompt_options['countries'])
            club = random.choice(prompt_options['clubs'])
            game_state['prompt'] = {'type': 'country_club', 'value': country, 'club': club}

def reset_turn_timer_for_session(game_state):
    """Reset the turn timer for a specific session"""
    if game_state['game_started']:
        game_state['turn_deadline'] = time.time() + 60
    game_state['last_activity'] = datetime.now()

def cleanup_old_sessions():
    """Remove sessions older than 2 hours"""
    cutoff_time = datetime.now() - timedelta(hours=2)
    expired_sessions = [
        session_id for session_id, game_state in game_sessions.items()
        if game_state['last_activity'] < cutoff_time
    ]
    for session_id in expired_sessions:
        del game_sessions[session_id]

@app.route('/')
def index():
    """Main page - redirect to session creation or show session list"""
    cleanup_old_sessions()
    
    # If user has a session, redirect to it
    if 'session_id' in session and session['session_id'] in game_sessions:
        return redirect(url_for('game', session_id=session['session_id']))
    
    # Show session creation/joining page
    return render_template('lobby.html', sessions=game_sessions)

@app.route('/lobby')
def lobby():
    """Clear session and return to lobby"""
    # Clear the user's session
    session.pop('session_id', None)
    session.pop('player_number', None)
    
    cleanup_old_sessions()
    return render_template('lobby.html', sessions=game_sessions)

@app.route('/create_session', methods=['POST'])
def create_session():
    """Create a new game session"""
    session_id = create_new_session()
    session['session_id'] = session_id
    session['player_number'] = 1  # First player to join
    
    # Increment player count
    game_sessions[session_id]['player_count'] += 1
    
    return redirect(url_for('game', session_id=session_id))

@app.route('/join_session/<session_id>')
def join_session(session_id):
    """Join an existing game session"""
    if session_id not in game_sessions:
        return redirect(url_for('index'))
    
    game_state = game_sessions[session_id]
    
    # Check if session is full
    if game_state['player_count'] >= game_state['max_players']:
        return redirect(url_for('index'))
    
    session['session_id'] = session_id
    session['player_number'] = game_state['player_count'] + 1
    
    # Increment player count
    game_state['player_count'] += 1
    game_state['last_activity'] = datetime.now()
    
    # Start the game timer when both players have joined
    if game_state['player_count'] == game_state['max_players'] and not game_state['game_started']:
        game_state['game_started'] = True
        game_state['turn_deadline'] = time.time() + 60
        game_state['message'] = "Game started! Player 1's turn."
    
    return redirect(url_for('game', session_id=session_id))

@app.route('/game/<session_id>')
def game(session_id):
    """Game page for a specific session"""
    if session_id not in game_sessions:
        return redirect(url_for('index'))
    
    game_state = game_sessions[session_id]
    game_state['last_activity'] = datetime.now()
    
    # Check if user is part of this session
    if 'session_id' not in session or session['session_id'] != session_id:
        return redirect(url_for('index'))
    
    return render_template('index.html', 
                         session_id=session_id,
                         players=game_state['players'], 
                         prompt=game_state['prompt'],
                         history=game_state['history'], 
                         message=game_state['message'], 
                         turn=game_state['turn'],
                         player_number=session.get('player_number', 1))

@app.route('/submit', methods=['POST'])
def handle_pick():
    """Handle player submission for a specific session"""
    session_id = request.form.get('session_id')
    if not session_id or session_id not in game_sessions:
        return jsonify({'error': 'Invalid session'})
    
    game_state = game_sessions[session_id]
    game_state['last_activity'] = datetime.now()
    
    input_name = request.form.get('player_name').strip()
    if not input_name:
        game_state['message'] = "Please enter a player name."
        return jsonify({'message': game_state['message'], 'players': game_state['players'], 'history': game_state['history']})

    # Prevent picking a player already selected (case-insensitive check)
    if any(player.lower() == input_name.lower() for player in game_state['selected_players']):
        game_state['message'] = "Player has already been picked. Turn forfeited."
        game_state['history'][game_state['turn']].append({'name': input_name, 'result': 'X'})
        game_state['turn'] = (game_state['turn'] + 1) % 2
        reset_turn_timer_for_session(game_state)
        return jsonify({'message': game_state['message'], 'players': game_state['players'], 'history': game_state['history']})

    # Find player matching the input name, position, and club/country
    player_entry = next(
        (
            p for p in players_data
            if p['name'].lower() == input_name.lower()
            and game_state['prompt'].get('position', '').lower() in [pos.strip().lower() for pos in p.get('position', '').split(',')]
            and (
                (game_state['prompt']['type'] == 'club'
                 and any(
                     club.strip().lower() == game_state['prompt']['value'].lower()
                     for club in p['clubs'].split(',')
                 )) or
                (game_state['prompt']['type'] == 'country' and p['country'].lower() == game_state['prompt']['value'].lower())
            )
        ),
        None
    )

    if not player_entry:
        # Try to find the player in the data to show their info
        player_info = next((p for p in players_data if p['name'].lower() == input_name.lower()), None)
        if player_info:
            info_str = f"Name: {player_info['name']}\nCountry: {player_info.get('country','')}\nClubs: {player_info.get('clubs','')}\nPosition: {player_info.get('position','')}\nApps: {player_info.get('apps','')}"
            game_state['message'] = f"Player not valid for this prompt. Turn forfeited.\n\n {info_str}"
        else:
            game_state['message'] = "Player not valid for this prompt. Turn forfeited."
        game_state['history'][game_state['turn']].append({'name': input_name, 'result': 'X'})
        game_state['turn'] = (game_state['turn'] + 1) % 2
        reset_turn_timer_for_session(game_state)
        return jsonify({'message': game_state['message'], 'players': game_state['players'], 'history': game_state['history']})

    if player_entry['apps'] > 180:
        info_str = f"Name: {player_entry['name']}\nCountry: {player_entry.get('country','')}\nClubs: {player_entry.get('clubs','')}\nPosition: {player_entry.get('position','')}\nApps: {player_entry.get('apps','')}"
        game_state['message'] = f"More than 180 appearances. Turn forfeited.\n\n {info_str}"
        game_state['history'][game_state['turn']].append({'name': player_entry['name'], 'result': 'X'})
        game_state['turn'] = (game_state['turn'] + 1) % 2
        reset_turn_timer_for_session(game_state)
        return jsonify({'message': game_state['message'], 'players': game_state['players'], 'history': game_state['history']})

    if player_entry['apps'] not in VALID_SCORES:
        info_str = f"Name: {player_entry['name']}\nCountry: {player_entry.get('country','')}\nClubs: {player_entry.get('clubs','')}\nPosition: {player_entry.get('position','')}\nApps: {player_entry.get('apps','')}"
        game_state['message'] = f"Invalid darts score. Turn forfeited.\n\n {info_str}"
        game_state['history'][game_state['turn']].append({'name': player_entry['name'], 'result': 'X'})
        game_state['turn'] = (game_state['turn'] + 1) % 2
        reset_turn_timer_for_session(game_state)
        return jsonify({'message': game_state['message'], 'players': game_state['players'], 'history': game_state['history']})

    # Mark player as selected so they can't be picked again
    game_state['selected_players'].add(player_entry['name'])

    game_state['history'][game_state['turn']].append({'name': player_entry['name'], 'result': player_entry['apps']})
    new_score = game_state['players'][game_state['turn']]['score'] - player_entry['apps']

    if new_score < -20:
        game_state['message'] = "Score would go below -20. Turn forfeited."
        game_state['history'][game_state['turn']].append({'name': player_entry['name'], 'result': 'X'})
        game_state['turn'] = (game_state['turn'] + 1) % 2
        reset_turn_timer_for_session(game_state)
        return jsonify({'message': game_state['message'], 'players': game_state['players'], 'history': game_state['history']})

    game_state['players'][game_state['turn']]['score'] = new_score
    won = new_score <= 0 and new_score >= -20

    info_str = f"Name: {player_entry['name']}\nCountry: {player_entry.get('country','')}\nClubs: {player_entry.get('clubs','')}\nPosition: {player_entry.get('position','')}\nApps: {player_entry.get('apps','')}"
    
    if won:
        game_state['message'] = f"{game_state['players'][game_state['turn']]['name']} wins!\n\n {info_str}"
    else:
        game_state['message'] = f"{player_entry['name']} accepted: -{player_entry['apps']}\n\n {info_str}"

    if not won:
        game_state['turn'] = (game_state['turn'] + 1) % 2
    else:
        # Reset game after a win
        game_state['players'] = [{'name': 'Player 1', 'score': 501}, {'name': 'Player 2', 'score': 501}]
        game_state['turn'] = 0
        game_state['history'] = [[], []]
        game_state['selected_players'].clear()
        set_random_prompt_for_session(game_state)

    return jsonify({
        'message': game_state['message'],
        'players': game_state['players'],
        'history': game_state['history'],
        'prompt': game_state['prompt'],
        'turn': game_state['turn']
    })

@app.route('/reset', methods=['POST'])
def reset_game():
    """Reset game for a specific session"""
    session_id = request.form.get('session_id')
    if not session_id or session_id not in game_sessions:
        return jsonify({'error': 'Invalid session'})
    
    game_state = game_sessions[session_id]
    game_state['last_activity'] = datetime.now()
    
    game_state['players'] = [{'name': 'Player 1', 'score': 501}, {'name': 'Player 2', 'score': 501}]
    game_state['turn'] = 0
    game_state['history'] = [[], []]
    set_random_prompt_for_session(game_state)
    game_state['message'] = "Game has been reset!"
    game_state['selected_players'].clear()  # Clear selected players on reset
    
    # Reset timer only if game was started
    if game_state['game_started']:
        reset_turn_timer_for_session(game_state)
    
    return jsonify({
        'message': game_state['message'],
        'players': game_state['players'],
        'history': game_state['history'],
        'prompt': game_state['prompt'],
        'turn': game_state['turn'],
        'turn_deadline': game_state['turn_deadline'],
        'game_started': game_state['game_started']
    })

@app.route('/forfeit', methods=['POST'])
def forfeit_turn():
    """Forfeit turn for a specific session"""
    session_id = request.form.get('session_id')
    if not session_id or session_id not in game_sessions:
        return jsonify({'error': 'Invalid session'})
    
    game_state = game_sessions[session_id]
    game_state['last_activity'] = datetime.now()
    
    # Only allow forfeit if game has started
    if not game_state['game_started']:
        return jsonify({'error': 'Game not started yet'})
    
    current_turn = game_state['turn']
    game_state['message'] = "Time's up! Turn forfeited."
    game_state['history'][current_turn].append({'name': 'Timeout', 'result': 'X'})
    game_state['turn'] = (current_turn + 1) % 2
    reset_turn_timer_for_session(game_state)
    
    return jsonify({
        'message': game_state['message'],
        'players': game_state['players'],
        'history': game_state['history'],
        'prompt': game_state['prompt'],
        'turn': game_state['turn'],
        'turn_deadline': game_state['turn_deadline'],
        'game_started': game_state['game_started']
    })

@app.route('/search_players')
def search_players():
    """Search players for a specific session"""
    session_id = request.args.get('session_id')
    query = request.args.get('q', '').lower().strip()
    
    if not query or not session_id or session_id not in game_sessions:
        return jsonify([])
    
    game_state = game_sessions[session_id]
    
    # Filter players based on query only (not prompt criteria)
    matching_players = []
    
    for player in players_data:
        # Check if name matches query and is not already selected
        if query in player['name'].lower() and player['name'] not in game_state['selected_players']:
            matching_players.append(player['name'])
    
    # Return top 3 matches
    return jsonify(matching_players[:3])

@app.route('/get_game_state/<session_id>')
def get_game_state(session_id):
    """Get current game state for polling updates"""
    if session_id not in game_sessions:
        return jsonify({'error': 'Session not found'})
    
    game_state = game_sessions[session_id]
    game_state['last_activity'] = datetime.now()
    
    return jsonify({
        'players': game_state['players'],
        'prompt': game_state['prompt'],
        'history': game_state['history'],
        'message': game_state['message'],
        'turn': game_state['turn'],
        'turn_deadline': game_state['turn_deadline'],
        'player_count': game_state['player_count'],
        'game_started': game_state['game_started']
    })

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)