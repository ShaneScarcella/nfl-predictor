import pandas as pd
import joblib
from flask import Flask, render_template, jsonify, request

# Initialize the Flask application
app = Flask(__name__)

# Load the trained machine learning model and the full dataset
model = joblib.load('model.pkl')
try:
    games_df = pd.read_csv('data/games.csv')
except FileNotFoundError:
    print("Error: 'data/games.csv' not found. Make sure the dataset is in the 'data' directory.")
    games_df = pd.DataFrame()

# --- Helper function for moneyline profit calculation ---
def calculate_profit(odds, bet_amount):
    if odds < 0: return (100 / abs(odds)) * bet_amount
    else: return (odds / 100) * bet_amount

@app.route('/')
def home():
    """Renders the main HTML page for the web application."""
    return render_template('index.html')

@app.route('/get_performance_stats')
def get_performance_stats():
    # This logic remains unchanged
    if games_df.empty: return jsonify({'error': 'Game data not loaded.'})
    df = games_df[(games_df['game_type'] == 'REG') & (games_df['season'] >= 2006)].copy()
    cols_to_keep = ['result', 'spread_line', 'home_moneyline', 'away_moneyline']
    df = df[cols_to_keep].dropna()
    df['home_win'] = (df['result'] > 0).astype(int)
    X = df[['spread_line']]
    y = df['home_win']
    from sklearn.model_selection import train_test_split
    _, X_test, _, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
    predictions = model.predict(X_test)
    accuracy = model.score(X_test, y_test)
    test_df = df.loc[X_test.index]
    test_df['prediction'] = predictions
    total_profit = 0; bet_amount = 100
    for _, row in test_df.iterrows():
        if row['prediction'] == row['home_win']:
            if row['prediction'] == 1: total_profit += calculate_profit(row['home_moneyline'], bet_amount)
            else: total_profit += calculate_profit(row['away_moneyline'], bet_amount)
        else: total_profit -= bet_amount
    roi = (total_profit / (len(test_df) * bet_amount)) * 100 if len(test_df) > 0 else 0
    return jsonify({'accuracy': f"{accuracy:.2%}", 'total_games_tested': len(test_df), 'simulated_roi': f"{roi:.2f}%"})

# --- FINAL FIX: Convert both seasons (keys) and weeks (values) to standard ints ---
@app.route('/get_seasons_weeks')
def get_seasons_weeks():
    """Scans the dataset and returns all unique seasons and their corresponding weeks."""
    if games_df.empty:
        return jsonify({'error': 'Game data not loaded.'})
    
    df = games_df[games_df['game_type'] == 'REG'].copy()
    seasons = sorted(df['season'].unique(), reverse=True)
    
    weeks_by_season = {
        int(season): [int(week) for week in sorted(df[df['season'] == season]['week'].unique())]
        for season in seasons
    }
    return jsonify(weeks_by_season)

@app.route('/get_predictions')
def get_predictions():
    """Provides game predictions for a user-selected week."""
    if games_df.empty: return jsonify({'error': 'Game data is not loaded.'})

    season = request.args.get('season', type=int)
    week = request.args.get('week', type=int)

    if not season or not week:
        return jsonify({'error': 'Please select a season and week.'})

    df = games_df[(games_df['game_type'] == 'REG') & (games_df['spread_line'].notna())].copy()
    
    target_games = df[(df['season'] == season) & (df['week'] == week)]

    if target_games.empty:
        return jsonify([])

    features = target_games[['spread_line']]
    predictions = model.predict(features)
    probabilities = model.predict_proba(features)

    target_games['prediction'] = predictions
    target_games['win_probability'] = probabilities.max(axis=1)

    output_data = []
    for _, row in target_games.iterrows():
        predicted_winner = row['home_team'] if row['prediction'] == 1 else row['away_team']
        output_data.append({
            'home_team': row['home_team'], 'away_team': row['away_team'],
            'predicted_winner': predicted_winner, 'spread_line': row['spread_line'],
            'confidence': row['win_probability']
        })
    return jsonify(output_data)

if __name__ == '__main__':
    app.run(debug=True)