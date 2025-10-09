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

    logos_df = pd.read_csv('data/team_logos.csv')
    # Convert logos into a dictionary (e.g., {'ARI': 'url_to_logo.png'}).
    team_logos = logos_df.set_index('team')['team_logo'].to_dict()

except FileNotFoundError as e:
    print(f"Error loading data files: {e}")
    games_df, team_avg_stats_df, team_logos = pd.DataFrame(), pd.DataFrame(), {}


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
    """
    Takes user-defined weights and predicts a winner using a
    proportional distribution scoring algorithm.
    """
    if team_avg_stats_df.empty:
        return jsonify({'error': 'Team average stats not loaded.'})

    data = request.get_json()
    home_team, away_team, season, week = data.get('home_team'), data.get('away_team'), data.get('season'), data.get('week')
    weights = data.get('weights')

    home_stats = team_avg_stats_df[(team_avg_stats_df['team'] == home_team) & (team_avg_stats_df['season'] == season) & (team_avg_stats_df['week'] == week)].iloc[0]
    away_stats = team_avg_stats_df[(team_avg_stats_df['team'] == away_team) & (team_avg_stats_df['season'] == season) & (team_avg_stats_df['week'] == week)].iloc[0]

    if pd.isna(home_stats['avg_off_yards']) or pd.isna(away_stats['avg_off_yards']):
        return jsonify({'error': 'Cannot generate predictions for Week 1 as there is no prior game data for this season. Please select Week 2 or later.'})

    home_score, away_score = 0.0, 0.0
    breakdown = []

    # 1. Offensive Yards (higher is better)
    total_off_yards = home_stats['avg_off_yards'] + away_stats['avg_off_yards']
    if total_off_yards > 0:
        home_off_share = home_stats['avg_off_yards'] / total_off_yards
        away_off_share = away_stats['avg_off_yards'] / total_off_yards
        home_score += weights['offense'] * home_off_share
        away_score += weights['offense'] * away_off_share
        breakdown.append(f"Offense: {home_team} gets {home_off_share:.1%} of points, {away_team} gets {away_off_share:.1%}")

    # 2. Defensive Yards (lower is better)
    total_def_yards = home_stats['avg_def_yards_allowed'] + away_stats['avg_def_yards_allowed']
    if total_def_yards > 0:
        # A team's "good" share is the inverse of their "bad" share (yards allowed).
        home_def_share = away_stats['avg_def_yards_allowed'] / total_def_yards
        away_def_share = home_stats['avg_def_yards_allowed'] / total_def_yards
        home_score += weights['defense'] * home_def_share
        away_score += weights['defense'] * away_def_share
        breakdown.append(f"Defense: {home_team} gets {home_def_share:.1%} of points, {away_team} gets {away_def_share:.1%}")

    # 3. Turnovers (lower is better)
    total_turnovers = home_stats['avg_turnovers'] + away_stats['avg_turnovers']
    if total_turnovers > 0:
        # Same inverse logic as defense.
        home_to_share = away_stats['avg_turnovers'] / total_turnovers
        away_to_share = home_stats['avg_turnovers'] / total_turnovers
        home_score += weights['turnovers'] * home_to_share
        away_score += weights['turnovers'] * away_to_share
        breakdown.append(f"Turnovers: {home_team} gets {home_to_share:.1%} of points, {away_team} gets {away_to_share:.1%}")

    # Determine winner and round scores for display.
    winner = home_team if home_score > away_score else away_team
    if home_score == away_score: winner = "It's a tie!"
    
    return jsonify({
        'winner': winner,
        'home_score': round(home_score, 1),
        'away_score': round(away_score, 1),
        'breakdown': breakdown
    })

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
        output_data.append({
            'home_team': row['home_team'],
            'away_team': row['away_team'],
            'predicted_winner': predicted_winner,
            'spread_line': row['spread_line'],
            'confidence': row['win_probability'],
            'home_logo': team_logos.get(row['home_team']),
            'away_logo': team_logos.get(row['away_team'])
        })
    return jsonify({'predictions': output_data, 'weekly_stats': weekly_stats})


if __name__ == '__main__': app.run(debug=True)

