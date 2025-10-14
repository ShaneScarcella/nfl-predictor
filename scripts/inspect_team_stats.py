import pandas as pd
import os
import argparse

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.normpath(os.path.join(SCRIPT_DIR, '..'))
DATA_FILE_PATH = os.path.join(PROJECT_ROOT, "data", "team_weekly_averages.csv")

def inspect_stats(team_abbr, season):
    """
    Loads the processed weekly averages and displays the stats for a specific
    team and season, making it easy to verify the data.
    """
    print(f"\n--- Inspecting Season Averages for {team_abbr} in {season} ---")
    
    try:
        df = pd.read_csv(DATA_FILE_PATH)
    except FileNotFoundError:
        print(f"Error: '{DATA_FILE_PATH}' not found.")
        print("Please run 'python scripts/prepare_team_stats.py' first.")
        return

    # Filter the DataFrame for the specific team and season.
    team_df = df[(df['team'] == team_abbr) & (df['season'] == season)]

    if team_df.empty:
        print(f"No data found for team '{team_abbr}' in season {season}.")
        return

    # Print the week-by-week stats in a clean format.
    # The stats for 'Week N' represent the average *entering* that week.
    print(team_df.to_string(index=False))


if __name__ == "__main__":
    # This sets up the command-line arguments.
    parser = argparse.ArgumentParser(description="Inspect a team's weekly average stats for a given season.")
    parser.add_argument("team", type=str, help="The team's abbreviation (e.g., NYG).")
    parser.add_argument("season", type=int, help="The season to inspect (e.g., 2025).")
    
    args = parser.parse_args()
    
    inspect_stats(args.team, args.season)