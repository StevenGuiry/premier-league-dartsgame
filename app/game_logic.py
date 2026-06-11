"""Pure game logic — no Flask or DB imports."""
import random
import unicodedata
import re
from dataclasses import dataclass, field
from typing import Optional


# ---------------------------------------------------------------------------
# Dart score validation
# ---------------------------------------------------------------------------

def _build_valid_dart_scores() -> frozenset:
    singles = list(range(21)) + [25]
    doubles = [2 * n for n in range(1, 21)] + [50]
    triples = [3 * n for n in range(1, 21)]
    all_values = singles + doubles + triples
    valid = set()
    for a in all_values:
        for b in all_values:
            for c in all_values:
                t = a + b + c
                if t <= 180:
                    valid.add(t)
    return frozenset(valid)


VALID_DART_SCORES: frozenset = _build_valid_dart_scores()

# ---------------------------------------------------------------------------
# Lookup tables
# ---------------------------------------------------------------------------

COUNTRY_NAMES = {
    'ENG': 'England', 'FRA': 'France', 'ESP': 'Spain', 'GER': 'Germany',
    'ITA': 'Italy', 'NED': 'Netherlands', 'BEL': 'Belgium', 'POR': 'Portugal',
    'BRA': 'Brazil', 'ARG': 'Argentina', 'IRL': 'Ireland', 'SCO': 'Scotland',
    'WAL': 'Wales', 'SWE': 'Sweden', 'NOR': 'Norway', 'DEN': 'Denmark',
    'AUT': 'Austria', 'SUI': 'Switzerland', 'CZE': 'Czech Republic', 'POL': 'Poland',
    'URU': 'Uruguay', 'COL': 'Colombia', 'CHI': 'Chile', 'MEX': 'Mexico',
    'USA': 'USA', 'JAM': 'Jamaica', 'NGA': 'Nigeria', 'GHA': 'Ghana',
    'CIV': 'Ivory Coast', 'CMR': 'Cameroon', 'SEN': 'Senegal', 'MAR': 'Morocco',
    'TUN': 'Tunisia', 'EGY': 'Egypt', 'ZAM': 'Zambia', 'RSA': 'South Africa',
    'AUS': 'Australia', 'JPN': 'Japan', 'KOR': 'South Korea', 'IRN': 'Iran',
    'RUS': 'Russia', 'UKR': 'Ukraine', 'CRO': 'Croatia', 'SRB': 'Serbia',
    'SVK': 'Slovakia', 'HUN': 'Hungary', 'ROM': 'Romania', 'TUR': 'Turkey',
    'GRE': 'Greece', 'ISL': 'Iceland', 'FIN': 'Finland', 'ALG': 'Algeria',
    'PAR': 'Paraguay', 'VEN': 'Venezuela', 'ECU': 'Ecuador', 'PER': 'Peru',
    'BOL': 'Bolivia', 'RSR': 'Serbia',
}

POSITION_NAMES = {
    'GK': 'Goalkeeper', 'DF': 'Defender', 'MF': 'Midfielder', 'FW': 'Forward',
}

VALID_POSITIONS = frozenset(POSITION_NAMES.keys())

# ---------------------------------------------------------------------------
# Name normalisation
# ---------------------------------------------------------------------------

def normalize_name_key(name: str) -> str:
    nfkd = unicodedata.normalize('NFKD', name)
    ascii_str = nfkd.encode('ASCII', 'ignore').decode('ASCII')
    return re.sub(r'\s+', ' ', ascii_str).strip().lower()


# ---------------------------------------------------------------------------
# Player record cleaning
# ---------------------------------------------------------------------------

def clean_player_record(raw: dict) -> dict:
    name = raw.get('name', '').strip()
    country = raw.get('country', '').strip()
    clubs_raw = raw.get('clubs', '')
    positions_raw = raw.get('position', raw.get('positions', ''))
    apps = int(raw.get('apps', 0))

    positions = ','.join(sorted({
        p.strip() for p in positions_raw.split(',')
        if p.strip() in VALID_POSITIONS
    }))

    clubs = ','.join(dict.fromkeys(
        c.strip() for c in clubs_raw.split(',') if c.strip()
    ))

    return {
        'name': name,
        'name_key': normalize_name_key(name),
        'country': country,
        'positions': positions,
        'clubs': clubs,
        'apps': apps,
    }


# ---------------------------------------------------------------------------
# Indexes
# ---------------------------------------------------------------------------

@dataclass
class PlayerIndex:
    by_name_key: dict
    by_club: dict        # club_lower -> set of name_keys
    by_country: dict     # country_code -> set of name_keys
    by_position: dict    # position -> set of name_keys
    playable: frozenset  # name_keys with apps<=180 and in VALID_DART_SCORES
    club_display: dict   # club_lower -> display name


def build_indexes(players: list) -> PlayerIndex:
    by_name_key: dict = {}
    by_club: dict = {}
    by_country: dict = {}
    by_position: dict = {}
    playable: set = set()
    club_display: dict = {}

    for p in players:
        nk = p['name_key']
        by_name_key[nk] = p

        for club in p['clubs'].split(','):
            club_stripped = club.strip()
            if club_stripped:
                club_key = club_stripped.lower()
                by_club.setdefault(club_key, set()).add(nk)
                if club_key not in club_display:
                    club_display[club_key] = club_stripped

        if p.get('country'):
            by_country.setdefault(p['country'], set()).add(nk)

        for pos in p['positions'].split(','):
            pos = pos.strip()
            if pos:
                by_position.setdefault(pos, set()).add(nk)

        if p['apps'] <= 180 and p['apps'] in VALID_DART_SCORES:
            playable.add(nk)

    return PlayerIndex(by_name_key, by_club, by_country, by_position,
                       frozenset(playable), club_display)


# ---------------------------------------------------------------------------
# Prompt pool
# ---------------------------------------------------------------------------

@dataclass
class Prompt:
    type: str        # club_position | country_position | country_club
    club: str        # display name
    club_key: str    # lowercased
    country: str     # 3-letter code
    position: str    # GK/DF/MF/FW or ''
    text: str        # human-readable prompt text
    answer_count: int


def _valid_answer_count(index: PlayerIndex, ptype: str, club_key: str,
                        country: str, position: str) -> int:
    if ptype == 'club_position':
        candidates = (index.by_club.get(club_key, set())
                      & index.by_position.get(position, set()))
    elif ptype == 'country_position':
        candidates = (index.by_country.get(country, set())
                      & index.by_position.get(position, set()))
    else:  # country_club
        candidates = (index.by_country.get(country, set())
                      & index.by_club.get(club_key, set()))
    return len(candidates & index.playable)


def build_prompt_pool(index: PlayerIndex, min_answers: int = 30) -> list:
    club_counts = {k: len(v & index.playable) for k, v in index.by_club.items()}
    country_counts = {k: len(v & index.playable) for k, v in index.by_country.items()}

    top_club_keys = sorted(club_counts, key=club_counts.get, reverse=True)[:20]
    top_countries = sorted(country_counts, key=country_counts.get, reverse=True)[:20]

    pool = []

    for ck in top_club_keys:
        club_name = index.club_display.get(ck, ck.title())
        for pos in VALID_POSITIONS:
            count = _valid_answer_count(index, 'club_position', ck, '', pos)
            if count >= min_answers:
                pool.append(Prompt(
                    type='club_position', club=club_name, club_key=ck,
                    country='', position=pos,
                    text=f'Name a {POSITION_NAMES[pos]} who played for {club_name}',
                    answer_count=count,
                ))

    for country in top_countries:
        cname = COUNTRY_NAMES.get(country, country)
        for pos in VALID_POSITIONS:
            count = _valid_answer_count(index, 'country_position', '', country, pos)
            if count >= min_answers:
                pool.append(Prompt(
                    type='country_position', club='', club_key='',
                    country=country, position=pos,
                    text=f'Name a {POSITION_NAMES[pos]} from {cname}',
                    answer_count=count,
                ))

    for country in top_countries:
        cname = COUNTRY_NAMES.get(country, country)
        for ck in top_club_keys:
            club_name = index.club_display.get(ck, ck.title())
            count = _valid_answer_count(index, 'country_club', ck, country, '')
            if count >= min_answers:
                pool.append(Prompt(
                    type='country_club', club=club_name, club_key=ck,
                    country=country, position='',
                    text=f'Name a player from {cname} who played for {club_name}',
                    answer_count=count,
                ))

    return pool


# ---------------------------------------------------------------------------
# Submission evaluation
# ---------------------------------------------------------------------------

class Outcome:
    NOT_FOUND = 'not_found'
    ALREADY_USED = 'already_used'
    NOT_MATCHING = 'not_matching'
    OVER_180 = 'over_180'
    INVALID_DART_SCORE = 'invalid_dart_score'
    BUST = 'bust'
    SCORED = 'scored'
    WIN = 'win'


def matches_prompt(player: dict, prompt: Prompt) -> bool:
    positions_set = {p.strip() for p in player['positions'].split(',') if p.strip()}
    clubs_set = {c.strip().lower() for c in player['clubs'].split(',') if c.strip()}

    if prompt.type == 'club_position':
        return prompt.club_key in clubs_set and prompt.position in positions_set
    elif prompt.type == 'country_position':
        return player['country'] == prompt.country and prompt.position in positions_set
    else:  # country_club — no position requirement (fixes the bug)
        return player['country'] == prompt.country and prompt.club_key in clubs_set


def evaluate_submission(current_score: int, name: str, used: set,
                        prompt: Prompt, index: PlayerIndex):
    """Returns (outcome, points, player_dict_or_None)."""
    name_key = normalize_name_key(name)
    player = index.by_name_key.get(name_key)

    if player is None:
        return Outcome.NOT_FOUND, 0, None

    if name_key in used:
        return Outcome.ALREADY_USED, 0, player

    if not matches_prompt(player, prompt):
        return Outcome.NOT_MATCHING, 0, player

    apps = player['apps']
    if apps > 180:
        return Outcome.OVER_180, 0, player

    if apps not in VALID_DART_SCORES:
        return Outcome.INVALID_DART_SCORE, 0, player

    new_score = current_score - apps
    if new_score < -20:
        return Outcome.BUST, 0, player

    if new_score <= 0:
        return Outcome.WIN, apps, player

    return Outcome.SCORED, apps, player


# ---------------------------------------------------------------------------
# CPU opponent
# ---------------------------------------------------------------------------

def cpu_pick(current_score: int, used: set, prompt: Prompt,
             index: PlayerIndex, difficulty: str):
    """Pick a valid player for the CPU. Returns player dict or None (no valid pick)."""
    candidates = []
    for player in index.by_name_key.values():
        if player['name_key'] in used:
            continue
        if player['apps'] > 180 or player['apps'] not in VALID_DART_SCORES:
            continue
        if not matches_prompt(player, prompt):
            continue
        if current_score - player['apps'] < -20:
            continue  # would bust
        candidates.append(player)

    if not candidates:
        return None

    if difficulty == 'easy':
        # Pick randomly from the lower-apps half — slow, beatable progress
        candidates.sort(key=lambda p: p['apps'])
        pool = candidates[:max(1, len(candidates) // 2)]
        return random.choice(pool)

    # hard: win immediately if possible, otherwise take the biggest chunk
    winning = [p for p in candidates if -20 <= current_score - p['apps'] <= 0]
    if winning:
        return min(winning, key=lambda p: abs(current_score - p['apps']))
    return max(candidates, key=lambda p: p['apps'])
