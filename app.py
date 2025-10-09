import pandas as pd
import joblib
import nflreadpy as nfl
from flask import Flask, render_template, jsonify, request
from sklearn.model_selection import train_test_split

app = Flask(__name__)

model = joblib.load('models/model.pkl')
try:
    games_df = pd.read_csv('data/games.csv', sep=r'\s*,\s*', engine='python')
    games_df.columns = games_df.columns.str.strip()
    team_avg_stats_df = pd.read_csv('data/team_weekly_averages.csv')
except FileNotFoundError as e:
    print(f"Error loading data files: {e}")
    print("Please make sure you have run both 'scripts/update_data.py' and 'scripts/prepare_team_stats.py'")
    games_df = pd.DataFrame()
    team_avg_stats_df = pd.DataFrame()


@app.route('/get_current_week_info')
def get_current_week_info():
    try:
        current_season = nfl.get_current_season()
        current_week = nfl.get_current_week()
        return jsonify({'season': current_season, 'week': current_week})
    except Exception as e:
        print(f"Could not determine current week automatically: {e}")
        return jsonify({'error': 'Could not determine current week.'})

@app.route('/custom_predict', methods=['POST'])
def custom_predict():
    if team_avg_stats_df.empty:
        return jsonify({'error': 'Team average stats not loaded.'})

    data = request.get_json()
    home_team, away_team, season, week = data.get('home_team'), data.get('away_team'), data.get('season'), data.get('week')
    weights = data.get('weights')

    home_stats = team_avg_stats_df[(team_avg_stats_df['team'] == home_team) & (team_avg_stats_df['season'] == season) & (team_avg_stats_df['week'] == week)]
    away_stats = team_avg_stats_df[(team_avg_stats_df['team'] == away_team) & (team_avg_stats_df['season'] == season) & (team_avg_stats_df['week'] == week)]

    if home_stats.empty or away_stats.empty or home_stats.isnull().values.any() or away_stats.isnull().values.any():
        return jsonify({'error': 'Cannot generate predictions for Week 1 as there is no prior game data for this season. Please select Week 2 or later.'})

    home_score, away_score = 0, 0
    breakdown = []

    if home_stats['avg_off_yards'].iloc[0] > away_stats['avg_off_yards'].iloc[0]:
        home_score += weights['offense']; breakdown.append(f"+{weights['offense']} to {home_team} for more yards/game")
    else:
        away_score += weights['offense']; breakdown.append(f"+{weights['offense']} to {away_team} for more yards/game")
    if home_stats['avg_def_yards_allowed'].iloc[0] < away_stats['avg_def_yards_allowed'].iloc[0]:
        home_score += weights['defense']; breakdown.append(f"+{weights['defense']} to {home_team} for fewer yards allowed/game")
    else:
        away_score += weights['defense']; breakdown.append(f"+{weights['defense']} to {away_team} for fewer yards allowed/game")
    if home_stats['avg_turnovers'].iloc[0] < away_stats['avg_turnovers'].iloc[0]:
        home_score += weights['turnovers']; breakdown.append(f"+{weights['turnovers']} to {home_team} for fewer turnovers/game")
    else:
        away_score += weights['turnovers']; breakdown.append(f"+{weights['turnovers']} to {away_team} for fewer turnovers/game")

    winner = home_team if home_score > away_score else away_team
    if home_score == away_score: winner = "It's a tie!"
    return jsonify({'winner': winner, 'home_score': home_score, 'away_score': away_score, 'breakdown': breakdown})

@app.route('/')
def home(): return render_template('index.html')
def calculate_profit(odds, bet_amount):
    if odds < 0: return (100 / abs(odds)) * bet_amount
    else: return (odds / 100) * bet_amount
    
@app.route('/get_performance_stats')
def get_performance_stats():
    if games_df.empty: return jsonify({'error': 'Game data not loaded.'})
    df = games_df[(games_df['game_type'] == 'REG') & (games_df['season'] >= 2006)].copy()
    cols_to_keep = ['result', 'spread_line', 'home_moneyline', 'away_moneyline']
    df = df[cols_to_keep].dropna()
    df['home_win'] = (df['result'] > 0).astype(int)
    X = df[['spread_line']]; y = df['home_win']
    _, X_test, _, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
    predictions = model.predict(X_test); accuracy = model.score(X_test, y_test)
    test_df = df.loc[X_test.index]; test_df['prediction'] = predictions
    total_profit = 0; bet_amount = 100
    for _, row in test_df.iterrows():
        if row['prediction'] == row['home_win']:
            if row['prediction'] == 1: total_profit += calculate_profit(row['home_moneyline'], bet_amount)
            else: total_profit += calculate_profit(row['away_moneyline'], bet_amount)
        else: total_profit -= bet_amount
    roi = (total_profit / (len(test_df) * bet_amount)) * 100 if len(test_df) > 0 else 0
    return jsonify({'accuracy': f"{accuracy:.2%}", 'total_games_tested': len(test_df), 'simulated_roi': f"{roi:.2f}%"})

@app.route('/get_seasons_weeks')
def get_seasons_weeks():
    if games_df.empty: return jsonify({'error': 'Game data not loaded.'})
    df = games_df[games_df['game_type'] == 'REG'].copy()
    seasons = sorted(df['season'].unique(), reverse=True)
    weeks_by_season = { int(season): [int(week) for week in sorted(df[df['season'] == season]['week'].unique())] for season in seasons }
    return jsonify(weeks_by_season)

@app.route('/get_predictions')
def get_predictions():
    if games_df.empty: return jsonify({'error': 'Game data is not loaded.'})
    season = request.args.get('season', type=int); week = request.args.get('week', type=int)
    if not season or not week: return jsonify({'error': 'Please select a season and week.'})
    df = games_df[(games_df['game_type'] == 'REG') & (games_df['spread_line'].notna())].copy()
    target_games = df[(df['season'] == season) & (df['week'] == week)].copy()
    if target_games.empty: return jsonify({'predictions': [], 'weekly_stats': {}})
    played_games = target_games.dropna(subset=['result']).copy()
    weekly_stats = {}
    if not played_games.empty:
        played_games['home_win'] = (played_games['result'] > 0).astype(int)
        features = played_games[['spread_line']]; predictions = model.predict(features)
        played_games['prediction'] = predictions
        weekly_wins = (played_games['prediction'] == played_games['home_win']).sum()
        total_played = len(played_games); weekly_profit = 0; bet_amount = 100
        for _, row in played_games.iterrows():
            if row['prediction'] == row['home_win']:
                if row['prediction'] == 1: weekly_profit += calculate_profit(row['home_moneyline'], bet_amount)
                else: weekly_profit += calculate_profit(row['away_moneyline'], bet_amount)
            else: weekly_profit -= bet_amount
        weekly_accuracy = (weekly_wins / total_played) * 100 if total_played > 0 else 0
        weekly_roi = (weekly_profit / (total_played * bet_amount)) * 100 if total_played > 0 else 0
        weekly_stats = { 'record': f"{weekly_wins}-{total_played - weekly_wins}", 'accuracy': f"{weekly_accuracy:.2f}%", 'roi': f"{weekly_roi:.2f}%" }
    features = target_games[['spread_line']]; predictions = model.predict(features)
    probabilities = model.predict_proba(features)
    target_games['prediction'] = predictions; target_games['win_probability'] = probabilities.max(axis=1)
    output_data = []
    for _, row in target_games.iterrows():
        predicted_winner = row['home_team'] if row['prediction'] == 1 else row['away_team']
        output_data.append({ 'home_team': row['home_team'], 'away_team': row['away_team'], 'predicted_winner': predicted_winner, 'spread_line': row['spread_line'], 'confidence': row['win_probability'] })
    return jsonify({'predictions': output_data, 'weekly_stats': weekly_stats})
if __name__ == '__main__': app.run(debug=True)

