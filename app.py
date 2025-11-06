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
    games_df['gameday'] = pd.to_datetime(games_df['gameday'])
    team_avg_stats_df = pd.read_csv('data/team_weekly_averages.csv')
    logos_df = pd.read_csv('data/team_logos.csv')
    team_logos = logos_df.set_index('team')['team_logo'].to_dict()
except FileNotFoundError as e:
    print(f"Error loading data files: {e}")
    games_df, team_avg_stats_df, team_logos = pd.DataFrame(), pd.DataFrame(), {}

# --- Helper function to calculate opponent record ---
def get_opponent_record_entering_week(opponent, season, week, all_games_df):
    """
    Calculates the opponent's record (W-L-T) and winning percentage
    for all games played *before* the specified week in the given season.
    """
    # Filter for games involving the opponent in the specified season BEFORE the given week
    opponent_games = all_games_df[
        (all_games_df['season'] == season) &
        (all_games_df['week'] < week) &
        ((all_games_df['home_team'] == opponent) | (all_games_df['away_team'] == opponent)) &
        (all_games_df['result'].notna()) # Only count games that have been played
    ].copy()

    if opponent_games.empty:
        return {'record': '0-0-0', 'win_pct': 0.5} # Default for teams before they play

    wins, losses, ties = 0, 0, 0
    for _, game in opponent_games.iterrows():
        if game['result'] == 0:
            ties += 1
        elif game['home_team'] == opponent and game['result'] > 0:
            wins += 1
        elif game['away_team'] == opponent and game['result'] < 0:
            wins += 1
        else:
            losses += 1
            
    total_games = wins + losses + ties
    win_pct = (wins + 0.5 * ties) / total_games if total_games > 0 else 0.5
    
    return {'record': f"{wins}-{losses}-{ties}", 'win_pct': win_pct}


# --- Strength of Schedule Analysis Endpoint ---
@app.route('/get_sos_analysis', methods=['GET'])
def get_sos_analysis():
    """
    Calculates a Strength of Schedule score based on past performance
    against opponents, weighted by opponent quality and margin of victory.
    """
    if games_df.empty:
        return jsonify({'error': 'Game data not loaded.'})

    team = request.args.get('team')
    season = request.args.get('season', type=int)
    week = request.args.get('week', type=int)
    filter_option = request.args.get('filter', 'all') # 'all', 'last3', 'last5'

    if not team or not season or not week:
        return jsonify({'error': 'Missing required parameters: team, season, week.'})

    # Find all games played by this team in this season before the selected week
    team_games = games_df[
        (games_df['season'] == season) &
        (games_df['week'] < week) &
        ((games_df['home_team'] == team) | (games_df['away_team'] == team)) &
        (games_df['result'].notna()) # Only consider played games
    ].sort_values(by='week', ascending=False).copy() # Sort descending to easily grab 'last N'

    if team_games.empty:
        return jsonify({'total_score': 0, 'breakdown': [], 'message': 'No past games found for this period.'})

    # Apply time filter
    if filter_option == 'last3':
        team_games = team_games.head(3)
    elif filter_option == 'last5':
        team_games = team_games.head(5)
    # 'all' uses the full filtered list

    game_breakdown = []
    total_sos_score = 0

    for _, game in team_games.iterrows():
        is_home_game = (game['home_team'] == team)
        opponent = game['away_team'] if is_home_game else game['home_team']
        margin = game['result'] if is_home_game else -game['result']
        result_flag = 1 if margin > 0 else (-1 if margin < 0 else 0) # 1=Win, -1=Loss, 0=Tie

        # Get the opponent's record *before* this specific game
        opp_record_info = get_opponent_record_entering_week(opponent, season, game['week'], games_df)
        opp_win_pct = opp_record_info['win_pct']
        opp_record_str = opp_record_info['record']

        # --- Define the "Game Value" Formula ---
        # Value = (Win/Loss * Opponent Strength) + (Margin Scaled)
        # We give more points for beating good teams or losing to bad teams.
        # Margin adds/subtracts a smaller amount based on blowout factor.
        game_value = (result_flag * (opp_win_pct * 10)) + (margin / 10.0)
        total_sos_score += game_value

        game_breakdown.append({
            'week': game['week'],
            'opponent': opponent,
            'result': 'W' if result_flag == 1 else ('L' if result_flag == -1 else 'T'),
            'margin': margin,
            'opp_record': opp_record_str,
            'opp_win_pct': f"{opp_win_pct:.3f}",
            'game_value': round(game_value, 2)
        })

    # Sort the breakdown chronologically for display
    game_breakdown.sort(key=lambda x: x['week'])

    return jsonify({
        'total_score': round(total_sos_score, 2),
        'breakdown': game_breakdown
    })


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
    if total > 0 and weights.get('offense_yards', 0) > 0:
        h_share, a_share = h_stat / total, a_stat / total
        home_score += weights['offense_yards'] * h_share
        away_score += weights['offense_yards'] * a_share
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
    if total > 0 and weights.get('defense_yards', 0) > 0:
        h_share, a_share = a_stat / total, h_stat / total
        home_score += weights['defense_yards'] * h_share
        away_score += weights['defense_yards'] * a_share
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