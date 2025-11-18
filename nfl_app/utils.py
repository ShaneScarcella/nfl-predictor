import pandas as pd
from nfl_app.data_loader import games_df

def calculate_profit(odds, bet_amount):
    if odds < 0: return (100 / abs(odds)) * bet_amount
    else: return (odds / 100) * bet_amount

def get_opponent_record_entering_week(opponent, season, week):
    """
    Calculates the opponent's record (W-L-T) and winning percentage
    for all games played *before* the specified week in the given season.
    """
    if games_df.empty:
        return {'record': '0-0-0', 'win_pct': 0.5}

    opponent_games = games_df[
        (games_df['season'] == season) &
        (games_df['week'] < week) &
        ((games_df['home_team'] == opponent) | (games_df['away_team'] == opponent)) &
        (games_df['result'].notna())
    ].copy()

    if opponent_games.empty:
        return {'record': '0-0-0', 'win_pct': 0.5}

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