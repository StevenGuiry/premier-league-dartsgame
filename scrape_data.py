import soccerdata as sd
import pandas as pd
from normalize_names_final import normalize_name
from convert_to_english import convert_to_english

# Generate a list of all Premier League seasons from 1992-93 to 2024-25
start_year = 1992
end_year = 2024  # Adjust to the latest available season (e.g., 2024 for 2024-25)
seasons = [f"{year}-{year+1}" for year in range(start_year, end_year + 1)]

# Initialize FBref scraper for Premier League, all seasons
fbref = sd.FBref(leagues='ENG-Premier League', seasons=seasons)

# Fetch standard player season stats
try:
    player_stats = fbref.read_player_season_stats(stat_type='standard')
except Exception as e:
    print(f"Error fetching data: {e}")
    print("Some seasons may not have data. Check FBref for availability.")
    exit()

# Print column names in original DataFrame
print("Column Names in player_stats:")
print(player_stats.columns.tolist())

# Reset the index to make 'player', 'team', 'season', 'league' regular columns
player_stats_flat = player_stats.reset_index()

# Print column names after resetting index
print("\nColumn Names in player_stats_flat:")
print(player_stats_flat.columns.tolist())

# Define desired columns, including position
desired_columns = [('player', ''), ('nation', ''), ('team', ''), ('Playing Time', 'MP'), ('pos', '')]

# Verify if all desired columns exist
missing_cols = [col for col in desired_columns if col not in player_stats_flat.columns]
if missing_cols:
    print(f"\nError: The following columns are missing: {missing_cols}")
    print("Available columns:", player_stats_flat.columns.tolist())
else:
    # Select the desired columns
    result = player_stats_flat[desired_columns]

    # Handle missing values in 'pos' by converting to string and replacing NaN with empty string
    result[('pos', '')] = result[('pos', '')].astype(str).replace('nan', '')

    # Group by player and nation, summing appearances, listing unique teams and positions
    aggregated = result.groupby([('player', ''), ('nation', '')]).agg({
        ('Playing Time', 'MP'): 'sum',  # Sum appearances
        ('team', ''): lambda x: ', '.join(x.unique()),  # Join unique teams
        ('pos', ''): lambda x: ', '.join([p for p in x.unique() if p])  # Join non-empty unique positions
    }).reset_index()

    # Rename columns for clarity
    aggregated.columns = ['name', 'country', 'apps', 'clubs', 'position']

    # Reorder columns
    aggregated = aggregated[['name', 'country', 'clubs', 'position', 'apps']]

    # Apply normalization and conversion to English for the 'name' field
    aggregated['name'] = aggregated['name'].apply(lambda n: convert_to_english(normalize_name(n)))

    # Sort by appearances (descending) for better readability
    aggregated = aggregated.sort_values(by='apps', ascending=False)

    # Display the first few rows
    print("\nAggregated DataFrame (Total Appearances Across All Seasons):")
    print(aggregated.head())

    # Save to JSON as a proper array
    aggregated.to_json('players_pl.json', orient='records', indent=4)