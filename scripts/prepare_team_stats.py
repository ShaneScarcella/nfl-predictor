import pandas as pd
import os

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.normpath(os.path.join(SCRIPT_DIR, '..'))
DATA_DIR = os.path.join(PROJECT_ROOT, "data")

GAMES_PATH = os.path.join(DATA_DIR, "games.csv")
PLAYER_STATS_PATH = os.path.join(DATA_DIR, "player_stats.csv")
OUTPUT_PATH = os.path.join(DATA_DIR, "team_weekly_averages.csv")

def prepare_data():
    print("--- Starting Team Stat Preparation ---")

    try:
        player_stats_df = pd.read_csv(PLAYER_STATS_PATH, low_memory=False)
        games_df = pd.read_csv(GAMES_PATH)
        print("Successfully loaded raw data files.")
    except FileNotFoundError as e:
        print(f"Error: {e}")
        print("Please run 'python scripts/update_data.py' first.")
        return

    stats_to_aggregate = {
        'passing_yards': 'sum', 'rushing_yards': 'sum', 'passing_tds': 'sum',
        'rushing_tds': 'sum', 'passing_interceptions': 'sum', 'sack_fumbles_lost': 'sum',
        'rushing_fumbles_lost': 'sum', 'receiving_fumbles_lost': 'sum'
    }
    grouping_cols = ['team', 'opponent_team', 'season', 'week']
    df_subset = player_stats_df[grouping_cols + list(stats_to_aggregate.keys())]
    team_game_stats = df_subset.groupby(grouping_cols).agg(stats_to_aggregate).reset_index()

    team_game_stats['offensive_yards'] = team_game_stats['passing_yards'] + team_game_stats['rushing_yards']
    team_game_stats['offensive_tds'] = team_game_stats['passing_tds'] + team_game_stats['rushing_tds']
    team_game_stats['turnovers'] = team_game_stats['passing_interceptions'] + team_game_stats['sack_fumbles_lost'] + team_game_stats['rushing_fumbles_lost'] + team_game_stats['receiving_fumbles_lost']
    merged_df = pd.merge(team_game_stats, team_game_stats, left_on=['team', 'season', 'week'], right_on=['opponent_team', 'season', 'week'], suffixes=('', '_allowed'))

    cols_to_keep = ['team', 'season', 'week', 'offensive_yards', 'offensive_tds', 'turnovers', 'offensive_yards_allowed', 'offensive_tds_allowed', 'turnovers_allowed']
    processed_stats = merged_df[cols_to_keep]

    home_res = games_df[['season', 'week', 'home_team', 'result']].rename(columns={'home_team': 'team'})
    home_res['won'] = (home_res['result'] > 0).astype(int)
    home_res['lost'] = (home_res['result'] < 0).astype(int)
    home_res['tied'] = (home_res['result'] == 0).astype(int)

    away_res = games_df[['season', 'week', 'away_team', 'result']].rename(columns={'away_team': 'team'})
    away_res['won'] = (away_res['result'] < 0).astype(int)
    away_res['lost'] = (away_res['result'] > 0).astype(int)
    away_res['tied'] = (away_res['result'] == 0).astype(int)

    all_results = pd.concat([home_res, away_res]).dropna(subset=['result'])
    all_results = all_results[['team', 'season', 'week', 'won', 'lost', 'tied']]

    processed_stats = pd.merge(processed_stats, all_results, on=['team', 'season', 'week'], how='left')

    home_teams = games_df[['season', 'week', 'home_team']].rename(columns={'home_team': 'team'})
    away_teams = games_df[['season', 'week', 'away_team']].rename(columns={'away_team': 'team'})
    full_schedule = pd.concat([home_teams, away_teams]).drop_duplicates().sort_values(['team', 'season', 'week'])

    final_df = pd.merge(full_schedule, processed_stats, on=['team', 'season', 'week'], how='left')

    stats_to_average = ['offensive_yards', 'offensive_tds', 'turnovers', 'offensive_yards_allowed', 'offensive_tds_allowed', 'turnovers_allowed']
    record_stats = ['won', 'lost', 'tied']

    final_df = final_df.sort_values(by=['team', 'season', 'week'])

    rolling_averages = final_df.groupby(['team', 'season'], group_keys=False)[stats_to_average].apply(
        lambda x: x.expanding().mean().shift(1)
    )
    final_df[stats_to_average] = rolling_averages
    final_df[stats_to_average] = final_df.groupby(['team', 'season'], group_keys=False)[stats_to_average].ffill()

    final_df[record_stats] = final_df[record_stats].fillna(0)
    rolling_records = final_df.groupby(['team', 'season'], group_keys=False)[record_stats].apply(
        lambda x: x.expanding().sum().shift(1)
    )
    final_df[['entering_wins', 'entering_losses', 'entering_ties']] = rolling_records.fillna(0)

    total_games = final_df['entering_wins'] + final_df['entering_losses'] + final_df['entering_ties']
    final_df['entering_win_pct'] = (final_df['entering_wins'] + 0.5 * final_df['entering_ties']) / total_games
    final_df['entering_win_pct'] = final_df['entering_win_pct'].fillna(0.5)

    final_df.rename(columns={
        'offensive_yards': 'avg_off_yards', 'offensive_tds': 'avg_off_tds', 'turnovers': 'avg_turnovers',
        'offensive_yards_allowed': 'avg_def_yards_allowed', 'offensive_tds_allowed': 'avg_def_tds_allowed', 'turnovers_allowed': 'avg_def_turnovers_forced'
    }, inplace=True)

    final_cols = ['team', 'season', 'week', 'avg_off_yards', 'avg_off_tds', 'avg_turnovers',
                  'avg_def_yards_allowed', 'avg_def_tds_allowed', 'avg_def_turnovers_forced',
                  'entering_wins', 'entering_losses', 'entering_ties', 'entering_win_pct']

    final_df = final_df[final_cols]
    final_df.to_csv(OUTPUT_PATH, index=False)
    print(f"--- Successfully saved clean data to '{OUTPUT_PATH}' ---")

if __name__ == "__main__":
    prepare_data()