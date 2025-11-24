from flask import Blueprint, jsonify, request
import pandas as pd
import os
from nfl_app.data_loader import games_df

user_picks = Blueprint('user_picks', __name__)

# Path to our simple storage file
PICKS_FILE = os.path.join(os.path.dirname(__file__), '../../data/user_picks.csv')

def ensure_picks_file_exists():
    if not os.path.exists(PICKS_FILE):
        df = pd.DataFrame(columns=['user', 'season', 'week', 'home_team', 'away_team', 'pick'])
        df.to_csv(PICKS_FILE, index=False)

@user_picks.route('/save_pick', methods=['POST'])
def save_pick():
    ensure_picks_file_exists()
    data = request.get_json()
    
    user = data.get('user')
    season = data.get('season')
    week = data.get('week')
    home_team = data.get('home_team')
    away_team = data.get('away_team')
    pick = data.get('pick')

    if not user or not pick:
        return jsonify({'error': 'User and Pick are required.'})

    # Load existing picks
    df = pd.read_csv(PICKS_FILE)

    # Remove any existing pick for this specific game by this user to allow "switching" sides
    mask = (
        (df['user'] == user) & 
        (df['season'] == season) & 
        (df['week'] == week) & 
        (df['home_team'] == home_team) & 
        (df['away_team'] == away_team)
    )
    df = df[~mask]

    # Add the new pick
    new_row = {
        'user': user, 'season': season, 'week': week, 
        'home_team': home_team, 'away_team': away_team, 'pick': pick
    }
    df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)
    
    df.to_csv(PICKS_FILE, index=False)
    
    return jsonify({'message': 'Pick saved!'})

@user_picks.route('/get_user_picks')
def get_user_picks():
    ensure_picks_file_exists()
    user = request.args.get('user')
    season = request.args.get('season', type=int)
    week = request.args.get('week', type=int)

    if not user:
        return jsonify([])

    try:
        df = pd.read_csv(PICKS_FILE)
        user_picks_df = df[
            (df['user'] == user) & 
            (df['season'] == season) & 
            (df['week'] == week)
        ]
        return jsonify(user_picks_df.to_dict(orient='records'))
    except pd.errors.EmptyDataError:
        return jsonify([])

@user_picks.route('/leaderboard')
def leaderboard():
    ensure_picks_file_exists()
    try:
        picks_df = pd.read_csv(PICKS_FILE)
    except pd.errors.EmptyDataError:
        return jsonify([])

    if picks_df.empty:
        return jsonify([])

    results_df = games_df.dropna(subset=['result'])[['season', 'week', 'home_team', 'away_team', 'result']]
    merged_df = pd.merge(picks_df, results_df, on=['season', 'week', 'home_team', 'away_team'], how='inner')

    def check_win(row):
        if row['result'] > 0 and row['pick'] == row['home_team']: return 1
        elif row['result'] < 0 and row['pick'] == row['away_team']: return 1
        return 0

    merged_df['is_correct'] = merged_df.apply(check_win, axis=1)

    leaderboard_data = []
    grouped = merged_df.groupby('user')
    
    for user, group in grouped:
        total_picks = len(group)
        wins = group['is_correct'].sum()
        losses = total_picks - wins
        pct = (wins / total_picks * 100) if total_picks > 0 else 0
        
        leaderboard_data.append({
            'user': user,
            'record': f"{wins}-{losses}",
            'pct': f"{pct:.1f}%"
        })

    leaderboard_data.sort(key=lambda x: float(x['pct'].strip('%')), reverse=True)
    return jsonify(leaderboard_data)