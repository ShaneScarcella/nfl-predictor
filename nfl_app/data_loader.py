import pandas as pd
import joblib
import os

def load_data():
    """
    Loads all necessary data files and the ML model from disk.
    This is run once when the app starts.
    """
    base_dir = os.path.normpath(os.path.join(os.path.dirname(__file__), '..'))
    
    try:
        games_path = os.path.join(base_dir, 'data/games.csv')
        games_df = pd.read_csv(games_path, sep=r'\s*,\s*', engine='python')
        games_df.columns = games_df.columns.str.strip()
        games_df['gameday'] = pd.to_datetime(games_df['gameday'])
    except FileNotFoundError:
        print("Warning: data/games.csv not found.")
        games_df = pd.DataFrame()
        
    try:
        stats_path = os.path.join(base_dir, 'data/team_weekly_averages.csv')
        team_avg_stats_df = pd.read_csv(stats_path)
    except FileNotFoundError:
        print("Warning: data/team_weekly_averages.csv not found.")
        team_avg_stats_df = pd.DataFrame()
        
    try:
        logos_path = os.path.join(base_dir, 'data/team_logos.csv')
        logos_df = pd.read_csv(logos_path)
        team_logos = logos_df.set_index('team')['team_logo'].to_dict()
    except FileNotFoundError:
        print("Warning: data/team_logos.csv not found.")
        team_logos = {}
        
    try:
        model_path = os.path.join(base_dir, 'models/model.pkl')
        model = joblib.load(model_path)
    except FileNotFoundError:
        print("Warning: models/model.pkl not found.")
        model = None

    return games_df, team_avg_stats_df, team_logos, model

# Load all data once on import
games_df, team_avg_stats_df, team_logos, model = load_data()