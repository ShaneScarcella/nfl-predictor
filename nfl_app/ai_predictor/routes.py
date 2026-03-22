from flask import Blueprint, jsonify, request
from nfl_app.data_loader import games_df, team_logos, model
from nfl_app.utils import calculate_profit
import pandas as pd

# Create a Blueprint named 'ai_predictor'
ai_predictor = Blueprint('ai_predictor', __name__)

@ai_predictor.route('/get_seasons_weeks')
def get_seasons_weeks():
    if games_df.empty: return jsonify({'error': 'Game data not loaded.'})
    df = games_df[games_df['game_type'] == 'REG'].copy()
    seasons = sorted(df['season'].unique(), reverse=True)
    weeks_by_season = { int(season): [int(week) for week in sorted(df[df['season'] == season]['week'].unique())] for season in seasons }
    return jsonify(weeks_by_season)

@ai_predictor.route('/get_predictions')
def get_predictions():
    if games_df.empty: return jsonify({'error': 'Game data is not loaded.'})
    
    season = request.args.get('season', type=int)
    week = request.args.get('week', type=int)
    
    if not season or not week: return jsonify({'error': 'Please select a season and week.'})
    
    df = games_df[(games_df['game_type'] == 'REG') & (games_df['spread_line'].notna())].copy()
    target_games = df[(df['season'] == season) & (df['week'] == week)].copy()
    
    if target_games.empty: return jsonify({'predictions': [], 'weekly_stats': {}})
    
    # Calculate stats for games already played
    played_games = target_games.dropna(subset=['result']).copy()
    weekly_stats = {}
    
    if not played_games.empty:
        played_games['home_win'] = (played_games['result'] > 0).astype(int)
        features = played_games[['spread_line']]
        if model:
            predictions = model.predict(features)
            played_games['prediction'] = predictions
            
            weekly_wins = (played_games['prediction'] == played_games['home_win']).sum()
            total_played = len(played_games)
            
            weekly_profit = 0
            bet_amount = 100
            
            for _, row in played_games.iterrows():
                if row['prediction'] == row['home_win']:
                    if row['prediction'] == 1: weekly_profit += calculate_profit(row['home_moneyline'], bet_amount)
                    else: weekly_profit += calculate_profit(row['away_moneyline'], bet_amount)
                else: weekly_profit -= bet_amount
            
            weekly_accuracy = (weekly_wins / total_played) * 100 if total_played > 0 else 0
            weekly_roi = (weekly_profit / (total_played * bet_amount)) * 100 if total_played > 0 else 0
            
            weekly_stats = { 
                'record': f"{weekly_wins}-{total_played - weekly_wins}", 
                'accuracy': f"{weekly_accuracy:.2f}%", 
                'roi': f"{weekly_roi:.2f}%" 
            }

    # Make predictions for all games (played and unplayed)
    features = target_games[['spread_line']]
    output_data = []
    
    if model:
        predictions = model.predict(features)
        probabilities = model.predict_proba(features)
        target_games['prediction'] = predictions
        target_games['win_probability'] = probabilities.max(axis=1)
        
        for _, row in target_games.iterrows():
            predicted_winner = row['home_team'] if row['prediction'] == 1 else row['away_team']
            
            actual_winner = None
            if pd.notna(row['result']):
                actual_winner = row['home_team'] if row['result'] > 0 else row['away_team']
                
            hm = row['home_moneyline'] if pd.notna(row.get('home_moneyline')) else None
            am = row['away_moneyline'] if pd.notna(row.get('away_moneyline')) else None
            output_data.append({
                'season': int(season),
                'week': int(row['week']),
                'home_team': row['home_team'],
                'away_team': row['away_team'],
                'predicted_winner': predicted_winner,
                'actual_winner': actual_winner,
                'spread_line': row['spread_line'],
                'confidence': row['win_probability'],
                'home_logo': team_logos.get(row['home_team']),
                'away_logo': team_logos.get(row['away_team']),
                'home_moneyline': float(hm) if hm is not None else None,
                'away_moneyline': float(am) if am is not None else None,
            })
            
    return jsonify({'predictions': output_data, 'weekly_stats': weekly_stats})