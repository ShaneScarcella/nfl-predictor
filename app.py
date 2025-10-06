import pandas as pd
import joblib
from flask import Flask, render_template, jsonify
from sklearn.model_selection import train_test_split # Added for performance calculation

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

# --- NEW FEATURE: API Endpoint for Model Performance ---
@app.route('/get_performance_stats')
def get_performance_stats():
    """
    Calculates and returns the model's historical performance on the test set.
    """
    if games_df.empty:
        return jsonify({'error': 'Game data not loaded.'})

    # This logic mirrors the final steps of train_model.py to get the test set
    df = games_df[(games_df['game_type'] == 'REG') & (games_df['season'] >= 2006)].copy()
    cols_to_keep = ['result', 'spread_line', 'home_moneyline', 'away_moneyline']
    df = df[cols_to_keep].dropna()
    df['home_win'] = (df['result'] > 0).astype(int)

    X = df[['spread_line']]
    y = df['home_win']
    
    # Use the same random_state to get the exact same test set every time
    _, X_test, _, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
    
    # Make predictions and calculate accuracy
    predictions = model.predict(X_test)
    accuracy = model.score(X_test, y_test)

    # --- Run the profitability simulation ---
    test_df = df.loc[X_test.index]
    test_df['prediction'] = predictions
    total_profit = 0
    bet_amount = 100

    for _, row in test_df.iterrows():
        if row['prediction'] == row['home_win']: # Correct prediction
            if row['prediction'] == 1: # Bet on home team
                total_profit += calculate_profit(row['home_moneyline'], bet_amount)
            else: # Bet on away team
                total_profit += calculate_profit(row['away_moneyline'], bet_amount)
        else: # Incorrect prediction
            total_profit -= bet_amount
            
    roi = (total_profit / (len(test_df) * bet_amount)) * 100 if len(test_df) > 0 else 0

    return jsonify({
        'accuracy': f"{accuracy:.2%}",
        'total_games_tested': len(test_df),
        'simulated_roi': f"{roi:.2f}%"
    })

@app.route('/get_predictions')
def get_predictions():
    """Provides game predictions for the most recent week."""
    if games_df.empty:
        return jsonify({'error': 'Game data is not loaded.'})

    df = games_df[(games_df['game_type'] == 'REG') & (games_df['spread_line'].notna())].copy()
    latest_season = df['season'].max()
    latest_week = df[df['season'] == latest_season]['week'].max()
    upcoming_games = df[(df['season'] == latest_season) & (df['week'] == latest_week)]

    if upcoming_games.empty:
        return jsonify({'error': 'No upcoming games found.'})

    features = upcoming_games[['spread_line']]
    predictions = model.predict(features)
    probabilities = model.predict_proba(features)

    upcoming_games['prediction'] = predictions
    upcoming_games['win_probability'] = probabilities.max(axis=1)

    output_data = []
    for _, row in upcoming_games.iterrows():
        predicted_winner = row['home_team'] if row['prediction'] == 1 else row['away_team']
        output_data.append({
            'home_team': row['home_team'],
            'away_team': row['away_team'],
            'predicted_winner': predicted_winner,
            'spread_line': row['spread_line'],
            # MODIFIED: Send confidence as a raw number (e.g., 0.75)
            'confidence': row['win_probability']
        })
    return jsonify(output_data)

if __name__ == '__main__':
    app.run(debug=True)

