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
    team_logos = logos_df.set_index('team')['team_logo'].to_dict()
except FileNotFoundError as e:
    print(f"Error loading data files: {e}")
    games_df, team_avg_stats_df, team_logos = pd.DataFrame(), pd.DataFrame(), {}

@app.route('/custom_predict', methods=['POST'])
def custom_predict():
    # This function uses the proportional scoring algorithm
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

    # Offensive Yards (higher is better)
    h_stat, a_stat = home_stats['avg_off_yards'], away_stats['avg_off_yards']
    total = h_stat + a_stat
    if total > 0 and weights.get('offense', 0) > 0:
        h_share, a_share = h_stat / total, a_stat / total
        home_score += weights['offense'] * h_share
        away_score += weights['offense'] * a_share
        breakdown.append({'cat': 'Offense (Yds/G)', 'h_val': round(h_stat, 1), 'a_val': round(a_stat, 1), 'h_share': h_share, 'a_share': a_share})

    # Offensive TDs (higher is better)
    h_stat, a_stat = home_stats['avg_off_tds'], away_stats['avg_off_tds']
    total = h_stat + a_stat
    if total > 0 and weights.get('offense_td', 0) > 0:
        h_share, a_share = h_stat / total, a_stat / total
        home_score += weights['offense_td'] * h_share
        away_score += weights['offense_td'] * a_share
        breakdown.append({'cat': 'Offense (TDs/G)', 'h_val': round(h_stat, 2), 'a_val': round(a_stat, 2), 'h_share': h_share, 'a_share': a_share})

    # Defensive Yards (lower is better, so shares are inverted)
    h_stat, a_stat = home_stats['avg_def_yards_allowed'], away_stats['avg_def_yards_allowed']
    total = h_stat + a_stat
    if total > 0 and weights.get('defense', 0) > 0:
        h_share, a_share = a_stat / total, h_stat / total
        home_score += weights['defense'] * h_share
        away_score += weights['defense'] * a_share
        breakdown.append({'cat': 'Defense (Yds Allow/G)', 'h_val': round(h_stat, 1), 'a_val': round(a_stat, 1), 'h_share': h_share, 'a_share': a_share})

    # Defensive TDs (lower is better, so shares are inverted)
    h_stat, a_stat = home_stats['avg_def_tds_allowed'], away_stats['avg_def_tds_allowed']
    total = h_stat + a_stat
    if total > 0 and weights.get('defense_td', 0) > 0:
        h_share, a_share = a_stat / total, h_stat / total
        home_score += weights['defense_td'] * h_share
        away_score += weights['defense_td'] * a_share
        breakdown.append({'cat': 'Defense (TDs Allow/G)', 'h_val': round(h_stat, 2), 'a_val': round(a_stat, 2), 'h_share': h_share, 'a_share': a_share})

    # Turnovers (lower is better, so shares are inverted)
    h_stat, a_stat = home_stats['avg_turnovers'], away_stats['avg_turnovers']
    total = h_stat + a_stat
    if total > 0 and weights.get('turnovers', 0) > 0:
        h_share, a_share = a_stat / total, h_stat / total
        home_score += weights['turnovers'] * h_share
        away_score += weights['turnovers'] * a_share
        breakdown.append({'cat': 'Turnover Avoidance', 'h_val': round(h_stat, 2), 'a_val': round(a_stat, 2), 'h_share': h_share, 'a_share': a_share})

    # Defensive Turnovers Forced (higher is better)
    h_stat, a_stat = home_stats['avg_def_turnovers_forced'], away_stats['avg_def_turnovers_forced']
    total = h_stat + a_stat
    if total > 0 and weights.get('def_turnovers', 0) > 0:
        h_share, a_share = h_stat / total, a_stat / total
        home_score += weights['def_turnovers'] * h_share
        away_score += weights['def_turnovers'] * a_share
        breakdown.append({'cat': 'Defensive Playmaking', 'h_val': round(h_stat, 2), 'a_val': round(a_stat, 2), 'h_share': h_share, 'a_share': a_share})

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

@app.route('/get_current_week_info')
def get_current_week_info():
    try:
        current_season = nfl.get_current_season(); current_week = nfl.get_current_week()
        return jsonify({'season': current_season, 'week': current_week})
    except Exception as e:
        return jsonify({'error': f'Could not determine current week: {e}'})
    
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
        actual_winner = None
        if pd.notna(row['result']):
            actual_winner = row['home_team'] if row['result'] > 0 else row['away_team']
        output_data.append({ 'home_team': row['home_team'], 'away_team': row['away_team'], 'predicted_winner': predicted_winner, 'actual_winner': actual_winner, 'spread_line': row['spread_line'], 'confidence': row['win_probability'], 'home_logo': team_logos.get(row['home_team']), 'away_logo': team_logos.get(row['away_team']) })
    return jsonify({'predictions': output_data, 'weekly_stats': weekly_stats})

if __name__ == '__main__': app.run(debug=True)