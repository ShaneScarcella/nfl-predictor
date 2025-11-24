from flask import Blueprint, jsonify, request
import pandas as pd
import os
from nfl_app.data_loader import games_df
from nfl_app.utils import calculate_profit

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
    # Cast season and week to integers ---
    try:
        season = int(data.get('season'))
        week = int(data.get('week'))
    except (ValueError, TypeError):
        return jsonify({'error': 'Invalid season or week format'}), 400
        
    home_team = data.get('home_team')
    away_team = data.get('away_team')
    pick = data.get('pick')

    if not user or not pick:
        return jsonify({'error': 'User and Pick are required.'})

    # Load existing picks
    df = pd.read_csv(PICKS_FILE)

    # Remove any existing pick for this specific game by this user
    # Now that season/week are ints, this comparison will work correctly
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
        # Filter for the specific user and week
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

    #  Fetch Result AND Moneyline odds
    cols_needed = ['season', 'week', 'home_team', 'away_team', 'result', 'home_moneyline', 'away_moneyline']
    results_df = games_df.dropna(subset=['result'])[cols_needed]

    #  Merge picks with game data
    merged_df = pd.merge(picks_df, results_df, on=['season', 'week', 'home_team', 'away_team'], how='inner')

    def calculate_pick_outcome(row):
        # Default values
        points = 0
        profit = 0
        bet_amount = 100

        # Check who won
        home_won = row['result'] > 0
        away_won = row['result'] < 0
        
        # Determine if the user was correct
        is_correct = False
        if (row['pick'] == row['home_team'] and home_won) or \
           (row['pick'] == row['away_team'] and away_won):
            is_correct = True

        # Calculate Profit/Loss
        if is_correct:
            points = 1
            # Get the odds for the team they picked
            odds = row['home_moneyline'] if row['pick'] == row['home_team'] else row['away_moneyline']
            
            # Handle missing odds data gracefully
            if pd.notna(odds):
                profit = calculate_profit(odds, bet_amount)
            else:
                profit = 0 # No profit calculated if odds are missing
        else:
            # If they lost, they lose the $100 bet
            # (If it was a tie, profit is 0, but we simplify here)
            if row['result'] != 0: 
                profit = -bet_amount

        return pd.Series([points, profit])

    # Apply the calculation
    merged_df[['points', 'profit']] = merged_df.apply(calculate_pick_outcome, axis=1)

    #  Aggregate by User
    leaderboard_data = []
    grouped = merged_df.groupby('user')
    
    for user, group in grouped:
        total_picks = len(group)
        wins = group['points'].sum()
        total_profit = group['profit'].sum()
        
        losses = total_picks - wins
        pct = (wins / total_picks * 100) if total_picks > 0 else 0
        
        # Format profit (e.g., "+$150.25" or "-$50.00")
        fmt_profit = f"${total_profit:,.2f}"
        if total_profit > 0:
            fmt_profit = f"+{fmt_profit}"

        leaderboard_data.append({
            'user': user,
            'record': f"{int(wins)}-{int(losses)}",
            'pct': f"{pct:.1f}%",
            'profit': fmt_profit,
            'raw_profit': total_profit # Keep raw number for sorting
        })

    # Sort by Profit first, then Win %
    leaderboard_data.sort(key=lambda x: (x['raw_profit'], float(x['pct'].strip('%'))), reverse=True)

    return jsonify(leaderboard_data)