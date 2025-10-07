import pandas as pd
import joblib
from flask import Flask, render_template, jsonify, request
from sklearn.model_selection import train_test_split

app = Flask(__name__)

# Load our pre-trained model and the big dataset once, right when the app starts.
model = joblib.load('model.pkl')
try:
    # Use a more robust CSV reader to handle messy formatting.
    games_df = pd.read_csv('data/games.csv', sep=r'\s*,\s*', engine='python')
    # Clean up column names just in case there are extra spaces.
    games_df.columns = games_df.columns.str.strip()

except FileNotFoundError:
    print("Error: 'data/games.csv' not found. Make sure the dataset is in the 'data' directory.")
    games_df = pd.DataFrame()

# A simple helper for calculating profit from American odds.
def calculate_profit(odds, bet_amount):
    if odds < 0: return (100 / abs(odds)) * bet_amount
    else: return (odds / 100) * bet_amount

# This is our main page. Just send back the HTML file.
@app.route('/')
def home():
    return render_template('index.html')

# This endpoint calculates the model's overall historical stats for the main dashboard.
@app.route('/get_performance_stats')
def get_performance_stats():
    if games_df.empty: return jsonify({'error': 'Game data not loaded.'})
    df = games_df[(games_df['game_type'] == 'REG') & (games_df['season'] >= 2006)].copy()
    cols_to_keep = ['result', 'spread_line', 'home_moneyline', 'away_moneyline']
    df = df[cols_to_keep].dropna()
    df['home_win'] = (df['result'] > 0).astype(int)
    X = df[['spread_line']]
    y = df['home_win']
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

# This endpoint just feeds the season/week dropdowns on the frontend.
@app.route('/get_seasons_weeks')
def get_seasons_weeks():
    # This logic remains unchanged.
    if games_df.empty: return jsonify({'error': 'Game data not loaded.'})
    df = games_df[games_df['game_type'] == 'REG'].copy()
    seasons = sorted(df['season'].unique(), reverse=True)
    weeks_by_season = {
        int(season): [int(week) for week in sorted(df[df['season'] == season]['week'].unique())]
        for season in seasons
    }
    return jsonify(weeks_by_season)

# The main prediction endpoint.
@app.route('/get_predictions')
def get_predictions():
    if games_df.empty: return jsonify({'error': 'Game data is not loaded.'})
    season = request.args.get('season', type=int)
    week = request.args.get('week', type=int)
    if not season or not week: return jsonify({'error': 'Please select a season and week.'})

    df = games_df[(games_df['game_type'] == 'REG') & (games_df['spread_line'].notna())].copy()
    target_games = df[(df['season'] == season) & (df['week'] == week)].copy()

    if target_games.empty:
        return jsonify({'predictions': [], 'weekly_stats': {}})

    # Get predictions for all games this week, played or not.
    features = target_games[['spread_line']]
    predictions = model.predict(features)
    probabilities = model.predict_proba(features)
    target_games['prediction'] = predictions
    target_games['win_probability'] = probabilities.max(axis=1)

    # Create a new, smaller dataframe containing ONLY the games that have a result.
    played_games = target_games.dropna(subset=['result']).copy()
    
    weekly_stats = {}
    if not played_games.empty:
        # If there's at least one finished game, calculate stats on that subset.
        played_games['home_win'] = (played_games['result'] > 0).astype(int)
        weekly_wins = (played_games['prediction'] == played_games['home_win']).sum()
        total_played = len(played_games)
        
        weekly_profit = 0
        bet_amount = 100
        for _, row in played_games.iterrows():
            if row['prediction'] == row['home_win']:
                if row['prediction'] == 1: weekly_profit += calculate_profit(row['home_moneyline'], bet_amount)
                else: weekly_profit += calculate_profit(row['away_moneyline'], bet_amount)
            else:
                weekly_profit -= bet_amount
        
        weekly_accuracy = (weekly_wins / total_played) * 100 if total_played > 0 else 0
        weekly_roi = (weekly_profit / (total_played * bet_amount)) * 100 if total_played > 0 else 0
        weekly_stats = {
            'record': f"{weekly_wins}-{total_played - weekly_wins}",
            'accuracy': f"{weekly_accuracy:.2f}%",
            'roi': f"{weekly_roi:.2f}%"
        }

    # Format the game-by-game predictions for the UI.
    output_data = []
    for _, row in target_games.iterrows():
        predicted_winner = row['home_team'] if row['prediction'] == 1 else row['away_team']
        output_data.append({
            'home_team': row['home_team'], 'away_team': row['away_team'],
            'predicted_winner': predicted_winner, 'spread_line': row['spread_line'],
            'confidence': row['win_probability']
        })
    
    return jsonify({'predictions': output_data, 'weekly_stats': weekly_stats})

if __name__ == '__main__':
    app.run(debug=True)

