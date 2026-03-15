import nflreadpy as nfl
import pandas as pd
import os
from datetime import datetime

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.normpath(os.path.join(SCRIPT_DIR, '..'))
DATA_DIR = os.path.join(PROJECT_ROOT, "data")

GAMES_FILE_PATH = os.path.join(DATA_DIR, "games.csv")
PLAYER_STATS_PATH = os.path.join(DATA_DIR, "player_stats.csv")

START_YEAR = 2006
CURRENT_YEAR = nfl.get_current_season()

def update_dataset(file_path, fetch_func, name):
    """
    Checks for existing data. If found, only fetches the most recent season 
    (to get new weeks) and merges it. If not found, fetches full history.
    """
    if os.path.exists(file_path):
        print(f"  - Found existing {name} data. Checking for updates...")
        # Read existing data
        existing_df = pd.read_csv(file_path, low_memory=False)
        last_season = existing_df['season'].max()
        
        # We re-download the latest season we have on file to catch newly played weeks
        seasons_to_fetch = range(last_season, CURRENT_YEAR + 1)
        print(f"  - Fetching {name} for seasons: {list(seasons_to_fetch)}")
        
        new_data = fetch_func(seasons_to_fetch).to_pandas()
        
        # Remove the overlapping seasons from the old data so we don't duplicate games
        existing_df = existing_df[~existing_df['season'].isin(seasons_to_fetch)]
        
        # Combine the historical data with the fresh data and save
        updated_df = pd.concat([existing_df, new_data], ignore_index=True)
        updated_df.to_csv(file_path, index=False)
        print(f"  - Successfully updated {name}.")
    else:
        print(f"  - No existing data found. Downloading full history ({START_YEAR}-{CURRENT_YEAR})...")
        seasons_to_fetch = range(START_YEAR, CURRENT_YEAR + 1)
        full_data = fetch_func(seasons_to_fetch).to_pandas()
        full_data.to_csv(file_path, index=False)
        print(f"  - Successfully downloaded all {name}.")

def update_all_data():
    print("--- Starting Data Update Process using nflreadpy ---")
    os.makedirs(DATA_DIR, exist_ok=True)

    print("\n[1/2] Updating schedule data...")
    try:
        update_dataset(GAMES_FILE_PATH, nfl.load_schedules, "schedule")
    except Exception as e:
        print(f"  - CRITICAL: Failed to update schedule data. Error: {e}")
        return

    print("\n[2/2] Updating player stats data...")
    try:
        # nfl.load_player_stats specifically expects the kwarg 'seasons'
        update_dataset(PLAYER_STATS_PATH, lambda s: nfl.load_player_stats(seasons=s), "player stats")
    except Exception as e:
        print(f"  - CRITICAL: Failed to update player stats. Error: {e}")

    print("\n--- Data Update Process Finished ---")

if __name__ == "__main__":
    update_all_data()