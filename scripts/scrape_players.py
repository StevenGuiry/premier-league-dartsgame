"""
Scrape Premier League player appearance data from FBref via soccerdata.
Run locally (not on cloud — FBref blocks/rate-limits cloud IPs).

Output: data/players_pl.json

Usage:
    cd /path/to/repo
    python scripts/scrape_players.py
"""

import json
import os
import unicodedata

import soccerdata as sd


def normalize_name(name: str) -> str:
    nfkd = unicodedata.normalize('NFKD', str(name))
    return ''.join(c for c in nfkd if not unicodedata.combining(c))


def clean_position(pos_str: str) -> str:
    """Dedup and sort position codes, e.g. 'MF,DF,MF' -> 'DF,MF'."""
    parts = {p.strip()[:2].upper() for p in str(pos_str).split(',') if p.strip() and p.strip() != 'nan'}
    valid = {'GK', 'DF', 'MF', 'FW'}
    kept = sorted(parts & valid)
    return ','.join(kept)


def clean_country(nat: str) -> str:
    parts = str(nat).split(' ')
    return parts[-1].upper() if parts else ''


def main():
    start_year = 1992
    end_year = 2025  # covers through 2025-26
    seasons = [f"{y}-{y+1}" for y in range(start_year, end_year + 1)]

    print(f"Fetching {len(seasons)} seasons from FBref…")
    fbref = sd.FBref(leagues='ENG-Premier League', seasons=seasons)

    try:
        stats = fbref.read_player_season_stats(stat_type='standard')
    except Exception as e:
        print(f"Error: {e}")
        return

    flat = stats.reset_index()

    desired = [('player', ''), ('nation', ''), ('team', ''), ('Playing Time', 'MP'), ('pos', '')]
    missing = [c for c in desired if c not in flat.columns]
    if missing:
        print(f"Missing columns: {missing}")
        print("Available:", flat.columns.tolist())
        return

    data = flat[desired].copy()
    data.columns = ['player', 'nation', 'team', 'apps', 'pos']
    data = data.dropna(subset=['player'])
    data['apps'] = data['apps'].fillna(0).astype(int)
    data['pos'] = data['pos'].fillna('').astype(str)
    data['nation'] = data['nation'].fillna('').astype(str)
    data['team'] = data['team'].fillna('').astype(str)

    grouped = data.groupby(['player', 'nation']).agg(
        apps=('apps', 'sum'),
        clubs=('team', lambda x: ','.join(sorted(set(str(t) for t in x if str(t) != 'nan')))),
        positions=('pos', lambda x: clean_position(','.join(str(p) for p in x))),
    ).reset_index()

    players = []
    for _, row in grouped.iterrows():
        name = normalize_name(row['player'])
        country = clean_country(row['nation'])
        clubs = row['clubs']
        positions = row['positions']
        apps = int(row['apps'])

        if not name or apps == 0:
            continue

        name_key = name.lower()

        players.append({
            'name': name,
            'name_key': name_key,
            'country': country,
            'positions': positions,
            'clubs': clubs,
            'apps': apps,
        })

    players.sort(key=lambda p: p['name'])
    print(f"Total players: {len(players)}")

    out_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data', 'players_pl.json')
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, 'w', encoding='utf-8') as f:
        json.dump(players, f, ensure_ascii=False, indent=2)
    print(f"Saved to {out_path}")


if __name__ == '__main__':
    main()
