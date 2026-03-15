import pandas as pd
import joblib
import os

def load_data():
    base_dir = os.path.normpath(os.path.join(os.path.dirname(__file__), '..'))
    
    games_path = os.path.join(base_dir, 'data/games.csv')
    games_df = pd.read_csv(games_path, sep=r'\s*,\s*', engine='python')
    games_df.columns = games_df.columns.str.strip()
    games_df['gameday'] = pd.to_datetime(games_df['gameday'])
        
    stats_path = os.path.join(base_dir, 'data/team_weekly_averages.csv')
    team_avg_stats_df = pd.read_csv(stats_path)
        
    logos_path = os.path.join(base_dir, 'data/team_logos.csv')
    logos_df = pd.read_csv(logos_path)
    team_logos = logos_df.set_index('team')['team_logo'].to_dict()
        
    model_path = os.path.join(base_dir, 'models/model.pkl')
    model = joblib.load(model_path)

    return games_df, team_avg_stats_df, team_logos, model

games_df, team_avg_stats_df, team_logos, model = load_data()