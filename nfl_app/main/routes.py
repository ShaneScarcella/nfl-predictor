from flask import Blueprint, render_template, jsonify
from nfl_app.data_loader import games_df, model
from nfl_app.utils import calculate_profit
from sklearn.model_selection import train_test_split
import nflreadpy as nfl

main = Blueprint('main', __name__)

@main.route('/')
def home():
    return render_template('index.html')

@main.route('/get_current_week_info')
def get_current_week_info():
    try:
        current_season = nfl.get_current_season()
        current_week = nfl.get_current_week()
        return jsonify({'season': current_season, 'week': current_week})
    except Exception as e:
        return jsonify({'error': f'Could not determine current week: {e}'})

@main.route('/get_performance_stats')
def get_performance_stats():
    if games_df.empty: return jsonify({'error': 'Game data not loaded.'})
    
    # We replicate the model training logic here to get the test set stats
    df = games_df[(games_df['game_type'] == 'REG') & (games_df['season'] >= 2006)].copy()
    cols_to_keep = ['result', 'spread_line', 'home_moneyline', 'away_moneyline']
    df = df[cols_to_keep].dropna()
    
    df['home_win'] = (df['result'] > 0).astype(int)
    X = df[['spread_line']]
    y = df['home_win']
    
    if model:
        _, X_test, _, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
        predictions = model.predict(X_test)
        accuracy = model.score(X_test, y_test)
        
        test_df = df.loc[X_test.index]
        test_df['prediction'] = predictions
        
        total_profit = 0
        bet_amount = 100
        
        for _, row in test_df.iterrows():
            if row['prediction'] == row['home_win']:
                if row['prediction'] == 1: total_profit += calculate_profit(row['home_moneyline'], bet_amount)
                else: total_profit += calculate_profit(row['away_moneyline'], bet_amount)
            else: total_profit -= bet_amount
            
        roi = (total_profit / (len(test_df) * bet_amount)) * 100 if len(test_df) > 0 else 0
        return jsonify({'accuracy': f"{accuracy:.2%}", 'total_games_tested': len(test_df), 'simulated_roi': f"{roi:.2f}%"})
        
    return jsonify({'error': 'Model not loaded.'})