import pandas as pd
import joblib
from flask import Flask, render_template, jsonify

# Initialize the Flask application
app = Flask(__name__)

# Load the trained machine learning model
model = joblib.load('model.pkl')

# Load the game data
try:
    games_df = pd.read_csv('data/games.csv')
except FileNotFoundError:
    print("Error: 'data/games.csv' not found. Make sure the dataset is in the 'data' directory.")
    games_df = pd.DataFrame() # Create an empty DataFrame to avoid further errors

@app.route('/')
def home():
    """Renders the main HTML page for the web application."""
    return render_template('index.html')

@app.route('/get_predictions')
def get_predictions():
    """
    This is the API endpoint that provides game predictions.
    It finds the latest week of games and uses the model to predict the winner.
    """
    if games_df.empty:
        return jsonify({'error': 'Game data is not loaded.'})

    # --- Find the latest available games to use as a "mock" upcoming week ---
    # We only want regular season games with valid spread data
    df = games_df[(games_df['game_type'] == 'REG') & (games_df['spread_line'].notna())].copy()
    
    # Find the most recent season and week in the dataset
    latest_season = df['season'].max()
    latest_week = df[df['season'] == latest_season]['week'].max()

    # Filter for the games in that specific week
    upcoming_games = df[(df['season'] == latest_season) & (df['week'] == latest_week)]

    if upcoming_games.empty:
        return jsonify({'error': 'No upcoming games found for the latest week.'})

    # Use the model to make predictions on these games
    features = upcoming_games[['spread_line']]
    predictions = model.predict(features)
    probabilities = model.predict_proba(features)

    # Add prediction data to the DataFrame
    upcoming_games['prediction'] = predictions
    upcoming_games['win_probability'] = probabilities.max(axis=1)

    # Format the data into a JSON structure for the frontend
    output_data = []
    for index, row in upcoming_games.iterrows():
        if row['prediction'] == 1: # Home team is predicted to win
            predicted_winner = row['home_team']
            confidence = row['win_probability']
        else: # Away team is predicted to win
            predicted_winner = row['away_team']
            confidence = row['win_probability']

        output_data.append({
            'home_team': row['home_team'],
            'away_team': row['away_team'],
            'predicted_winner': predicted_winner,
            'spread_line': row['spread_line'],
            'confidence': f"{confidence:.0%}" # Format as a percentage string
        })

    return jsonify(output_data)

# This allows you to run the app directly from the command line
if __name__ == '__main__':
    app.run(debug=True)