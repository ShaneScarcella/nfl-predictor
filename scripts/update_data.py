import nflreadpy as nfl
import os
from datetime import datetime

# --- THIS IS THE FIX ---
# This block of code makes the script's paths robust.
# It finds the script's own location and builds paths from there.
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.normpath(os.path.join(SCRIPT_DIR, '..'))
DATA_DIR = os.path.join(PROJECT_ROOT, "data")

GAMES_FILE_PATH = os.path.join(DATA_DIR, "games.csv")
PLAYER_STATS_PATH = os.path.join(DATA_DIR, "player_stats.csv")

START_YEAR = 2006
CURRENT_YEAR = nfl.get_current_season()

def update_all_data():
    print("--- Starting Data Update Process using nflreadpy ---")
    os.makedirs(DATA_DIR, exist_ok=True)

    print(f"\n[1/2] Downloading schedule data ({START_YEAR}-{CURRENT_YEAR})...")
    try:
        schedules_df = nfl.load_schedules(range(START_YEAR, CURRENT_YEAR + 1))
        schedules_df.to_pandas().to_csv(GAMES_FILE_PATH, index=False)
        print("  - Success!")
    except Exception as e:
        print(f"  - CRITICAL: Failed to download schedule data. Error: {e}")
        return

    print(f"\n[2/2] Downloading weekly player stats ({START_YEAR}-{CURRENT_YEAR})...")
    try:
        player_stats_df = nfl.load_player_stats(seasons=range(START_YEAR, CURRENT_YEAR + 1))
        player_stats_df.to_pandas().to_csv(PLAYER_STATS_PATH, index=False)
        print(f"\nSuccessfully downloaded and saved player stats to '{PLAYER_STATS_PATH}'")
    except Exception as e:
        print(f"\nCRITICAL: Failed to download player stats. Error: {e}")

    print("\n--- Data Update Process Finished ---")

if __name__ == "__main__":
    update_all_data()

