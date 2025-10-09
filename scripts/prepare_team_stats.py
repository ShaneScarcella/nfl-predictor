import pandas as pd
import os

# This block makes file paths work correctly from the scripts folder.
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.normpath(os.path.join(SCRIPT_DIR, '..'))
DATA_DIR = os.path.join(PROJECT_ROOT, "data")

WEEKLY_DATA_PATH = os.path.join(DATA_DIR, "player_stats.csv")
OUTPUT_PATH = os.path.join(DATA_DIR, "team_weekly_averages.csv")

def prepare_data():
    """
    Reads the raw weekly player data and transforms it into clean,
    season-to-date weekly averages for each team.
    """
    print("--- Starting Team Stat Preparation ---")

    try:
        # Load the file, using low_memory=False to prevent data type warnings.
        df = pd.read_csv(WEEKLY_DATA_PATH, low_memory=False)
        print("Successfully loaded raw player_stats.csv")
    except FileNotFoundError:
        print(f"Error: '{WEEKLY_DATA_PATH}' not found.")
        print("Please run 'python scripts/update_data.py' first.")
        return

    # Define the raw player stats we need to aggregate.
    stats_to_aggregate = {
        'passing_yards': 'sum',
        'rushing_yards': 'sum',
        'passing_tds': 'sum',
        'rushing_tds': 'sum',
        'passing_interceptions': 'sum', # Corrected name
        'sack_fumbles_lost': 'sum',
        'rushing_fumbles_lost': 'sum',
        'receiving_fumbles_lost': 'sum'
    }
    
    # Use the correct column names for team and opponent from the new dataset.
    grouping_cols = ['team', 'opponent_team', 'season', 'week']
    
    # Select only the columns we need to make the process faster.
    df_subset = df[grouping_cols + list(stats_to_aggregate.keys())]

    # Aggregate player stats up to the team-game level.
    team_game_stats = df_subset.groupby(grouping_cols).agg(stats_to_aggregate).reset_index()
    print("Aggregated player stats to team-per-game stats.")

    # Calculate combined offensive and defensive metrics for each game.
    team_game_stats['offensive_yards'] = team_game_stats['passing_yards'] + team_game_stats['rushing_yards']
    team_game_stats['offensive_tds'] = team_game_stats['passing_tds'] + team_game_stats['rushing_tds']
    # Combine all relevant turnover stats.
    team_game_stats['turnovers'] = team_game_stats['passing_interceptions'] + team_game_stats['sack_fumbles_lost'] + team_game_stats['rushing_fumbles_lost'] + team_game_stats['receiving_fumbles_lost']
    
    # To get defensive stats (e.g., yards ALLOWED), we merge the data with itself.
    merged_df = pd.merge(
        team_game_stats,
        team_game_stats,
        left_on=['team', 'season', 'week'],
        right_on=['opponent_team', 'season', 'week'],
        suffixes=('', '_allowed')
    )
    
    final_cols = [
        'team', 'season', 'week',
        'offensive_yards', 'offensive_tds', 'turnovers',
        'offensive_yards_allowed', 'offensive_tds_allowed', 'turnovers_allowed'
    ]
    team_game_stats = merged_df[final_cols]
    print("Calculated offensive and defensive stats for each game.")

    # Calculate season-to-date rolling averages for each stat.
    team_game_stats = team_game_stats.sort_values(by=['team', 'season', 'week'])
    
    stats_to_average = [
        'offensive_yards', 'offensive_tds', 'turnovers',
        'offensive_yards_allowed', 'offensive_tds_allowed', 'turnovers_allowed'
    ]
    
    rolling_averages = team_game_stats.groupby(['team', 'season'])[stats_to_average].apply(
        # The shift(1) ensures we're calculating the average *before* the current week's game.
        lambda x: x.expanding().mean().shift(1)
    )
    
    final_df = pd.concat([team_game_stats[['team', 'season', 'week']], rolling_averages], axis=1)
    
    # Rename columns for our final, clean file.
    final_df.columns = [
        'team', 'season', 'week', 'avg_off_yards', 'avg_off_tds', 'avg_turnovers',
        'avg_def_yards_allowed', 'avg_def_tds_allowed', 'avg_def_turnovers_forced'
    ]
    print("Calculated season-to-date rolling averages.")
    
    # Save the final, processed data.
    final_df.to_csv(OUTPUT_PATH, index=False)
    print(f"--- Successfully saved clean data to '{OUTPUT_PATH}' ---")


if __name__ == "__main__":
    prepare_data()