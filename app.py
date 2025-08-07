from flask import Flask, render_template, request, jsonify
import json
import random
import time
from typing import List, Dict, Set
from collections import Counter

app = Flask(__name__)

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

# Track selected players so they can't be picked again
global selected_players
selected_players = set()

# Game state
game_state = {
    'players': [{'name': 'Player 1', 'score': 501}, {'name': 'Player 2', 'score': 501}],
    'turn': 0,
    'prompt': None,
    'history': [[], []],
    'message': '',
    'turn_deadline': time.time() + 60  # 60 seconds from now
}

def set_random_prompt():
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

set_random_prompt()

@app.route('/')
def index():
    return render_template('index.html', players=game_state['players'], prompt=game_state['prompt'],
                          history=game_state['history'], message=game_state['message'], turn=game_state['turn'])

@app.route('/submit', methods=['POST'])
def handle_pick():
    input_name = request.form.get('player_name').strip()
    if not input_name:
        game_state['message'] = "Please enter a player name."
        return jsonify({'message': game_state['message'], 'players': game_state['players'], 'history': game_state['history']})

    # Prevent picking a player already selected (case-insensitive check)
    if any(player.lower() == input_name.lower() for player in selected_players):
        game_state['message'] = "Player has already been picked. Turn forfeited."
        game_state['history'][game_state['turn']].append({'name': input_name, 'result': 'X'})
        game_state['turn'] = (game_state['turn'] + 1) % 2
        reset_turn_timer()
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
        reset_turn_timer()
        return jsonify({'message': game_state['message'], 'players': game_state['players'], 'history': game_state['history']})

    if player_entry['apps'] > 180:
        info_str = f"Name: {player_entry['name']}\nCountry: {player_entry.get('country','')}\nClubs: {player_entry.get('clubs','')}\nPosition: {player_entry.get('position','')}\nApps: {player_entry.get('apps','')}"
        game_state['message'] = f"More than 180 appearances. Turn forfeited.\n\n {info_str}"
        game_state['history'][game_state['turn']].append({'name': player_entry['name'], 'result': 'X'})
        game_state['turn'] = (game_state['turn'] + 1) % 2
        reset_turn_timer()
        return jsonify({'message': game_state['message'], 'players': game_state['players'], 'history': game_state['history']})

    if player_entry['apps'] not in VALID_SCORES:
        info_str = f"Name: {player_entry['name']}\nCountry: {player_entry.get('country','')}\nClubs: {player_entry.get('clubs','')}\nPosition: {player_entry.get('position','')}\nApps: {player_entry.get('apps','')}"
        game_state['message'] = f"Invalid darts score. Turn forfeited.\n\n {info_str}"
        game_state['history'][game_state['turn']].append({'name': player_entry['name'], 'result': 'X'})
        game_state['turn'] = (game_state['turn'] + 1) % 2
        reset_turn_timer()
        return jsonify({'message': game_state['message'], 'players': game_state['players'], 'history': game_state['history']})

    # Mark player as selected so they can't be picked again
    selected_players.add(player_entry['name'])

    game_state['history'][game_state['turn']].append({'name': player_entry['name'], 'result': player_entry['apps']})
    new_score = game_state['players'][game_state['turn']]['score'] - player_entry['apps']

    if new_score < -20:
        game_state['message'] = "Score would go below -20. Turn forfeited."
        game_state['history'][game_state['turn']].append({'name': player_entry['name'], 'result': 'X'})
        game_state['turn'] = (game_state['turn'] + 1) % 2
        reset_turn_timer()
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
        set_random_prompt()

    return jsonify({
        'message': game_state['message'],
        'players': game_state['players'],
        'history': game_state['history'],
        'prompt': game_state['prompt'],
        'turn': game_state['turn']
    })

@app.route('/reset', methods=['POST'])
def reset_game():
    game_state['players'] = [{'name': 'Player 1', 'score': 501}, {'name': 'Player 2', 'score': 501}]
    game_state['turn'] = 0
    game_state['history'] = [[], []]
    set_random_prompt()
    game_state['message'] = "Game has been reset!"
    reset_turn_timer()
    selected_players.clear()  # Clear selected players on reset
    return jsonify({
        'message': game_state['message'],
        'players': game_state['players'],
        'history': game_state['history'],
        'prompt': game_state['prompt'],
        'turn': game_state['turn'],
        'turn_deadline': game_state['turn_deadline']
    })

@app.route('/forfeit', methods=['POST'])
def forfeit_turn():
    current_turn = game_state['turn']
    game_state['message'] = "Time's up! Turn forfeited."
    game_state['history'][current_turn].append({'name': 'Timeout', 'result': 'X'})
    game_state['turn'] = (current_turn + 1) % 2
    reset_turn_timer()
    return jsonify({
        'message': game_state['message'],
        'players': game_state['players'],
        'history': game_state['history'],
        'prompt': game_state['prompt'],
        'turn': game_state['turn'],
        'turn_deadline': game_state['turn_deadline']
    })

def reset_turn_timer():
    game_state['turn_deadline'] = time.time() + 60

@app.route('/search_players')
def search_players():
    query = request.args.get('q', '').lower().strip()
    if not query:
        return jsonify([])
    
    # Filter players based on query only (not prompt criteria)
    matching_players = []
    
    for player in players_data:
        # Check if name matches query and is not already selected
        if query in player['name'].lower() and player['name'] not in selected_players:
            matching_players.append(player['name'])
    
    # Return top 3 matches
    return jsonify(matching_players[:3])

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)