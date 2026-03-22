from flask import Blueprint, jsonify, request
import pandas as pd
import sqlite3
import os
from nfl_app.data_loader import games_df
from nfl_app.utils import calculate_profit

user_picks = Blueprint('user_picks', __name__)

DB_FILE = os.path.join(os.path.dirname(__file__), '../../data/user_picks.db')

def get_db_connection():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    return conn

def ensure_picks_table_exists():
    conn = get_db_connection()
    conn.execute('''
        CREATE TABLE IF NOT EXISTS picks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user TEXT NOT NULL,
            season INTEGER NOT NULL,
            week INTEGER NOT NULL,
            home_team TEXT NOT NULL,
            away_team TEXT NOT NULL,
            pick TEXT NOT NULL,
            UNIQUE(user, season, week, home_team, away_team)
        )
    ''')
    conn.commit()
    _repair_misaligned_pick_weeks(conn)
    conn.close()


def _repair_misaligned_pick_weeks(conn):
    """Fix picks whose week does not match the REG schedule (e.g. race saved week 18 for a Week 1 game)."""
    rows = conn.execute(
        'SELECT id, user, season, week, home_team, away_team FROM picks'
    ).fetchall()
    for r in rows:
        rid, user, season, week, home_team, away_team = (
            r['id'],
            r['user'],
            r['season'],
            r['week'],
            r['home_team'],
            r['away_team'],
        )
        reg = games_df[
            (games_df['game_type'] == 'REG')
            & (games_df['season'] == season)
            & (games_df['home_team'] == home_team)
            & (games_df['away_team'] == away_team)
        ]
        if reg.empty or len(reg['week'].dropna().unique()) != 1:
            continue
        cw = int(reg['week'].iloc[0])
        if int(week) == cw:
            continue
        dup = conn.execute(
            'SELECT id FROM picks WHERE user = ? AND season = ? AND week = ? AND home_team = ? AND away_team = ?',
            (user, season, cw, home_team, away_team),
        ).fetchone()
        if dup:
            conn.execute('DELETE FROM picks WHERE id = ?', (rid,))
        else:
            conn.execute('UPDATE picks SET week = ? WHERE id = ?', (cw, rid))
    conn.commit()

BET_AMOUNT = 100

_REG_GAME_COLS = ['season', 'week', 'home_team', 'away_team', 'result', 'home_moneyline', 'away_moneyline']


def _fill_reg_game_fallback(merged_df):
    """When merge on (season, week, teams) misses, attach the single REG row for that season + matchup."""
    reg_games = games_df[games_df['game_type'] == 'REG'][_REG_GAME_COLS]
    for idx in merged_df.index:
        if pd.isna(merged_df.at[idx, 'result']):
            r = merged_df.loc[idx]
            alt = reg_games[
                (reg_games['season'] == r['season'])
                & (reg_games['home_team'] == r['home_team'])
                & (reg_games['away_team'] == r['away_team'])
            ]
            if len(alt) == 1:
                a = alt.iloc[0]
                merged_df.at[idx, 'result'] = a['result']
                merged_df.at[idx, 'home_moneyline'] = a['home_moneyline']
                merged_df.at[idx, 'away_moneyline'] = a['away_moneyline']
                merged_df.at[idx, 'week'] = int(a['week'])
    return merged_df


def determine_bet_outcome(pick, home_team, away_team, result, home_moneyline, away_moneyline, bet_amount=BET_AMOUNT):
    """
    Calculate bet outcome/profit for a single pick.
    Result is from games_df and represents the signed point differential (positive => home won, negative => away won).
    """
    # Future games (or missing data) -> pending.
    if pd.isna(result):
        return 'Pending', 0, 0.0

    # Ties
    if result == 0:
        return 'Push', 0, 0.0

    home_won = result > 0
    away_won = result < 0

    is_correct = (pick == home_team and home_won) or (pick == away_team and away_won)
    if is_correct:
        odds = home_moneyline if pick == home_team else away_moneyline
        profit = calculate_profit(odds, bet_amount) if pd.notna(odds) else 0.0
        return 'Win', 1, float(profit)

    # Incorrect pick
    return 'Loss', 0, float(-bet_amount)

@user_picks.route('/save_pick', methods=['POST'])
def save_pick():
    ensure_picks_table_exists()
    data = request.get_json()
    
    try:
        user = data.get('user')
        season = int(data.get('season'))
        week = int(data.get('week'))
        home_team = data.get('home_team')
        away_team = data.get('away_team')
        pick = data.get('pick')
    except (ValueError, TypeError):
        return jsonify({'error': 'Invalid season or week format'}), 400

    if not user or not pick:
        return jsonify({'error': 'User and Pick are required.'})

    reg_rows = games_df[
        (games_df['game_type'] == 'REG')
        & (games_df['season'] == season)
        & (games_df['home_team'] == home_team)
        & (games_df['away_team'] == away_team)
    ]
    if not reg_rows.empty:
        week = int(reg_rows['week'].min())

    conn = get_db_connection()
    try:
        if not reg_rows.empty:
            conn.execute(
                '''
                DELETE FROM picks
                WHERE user = ? AND season = ? AND home_team = ? AND away_team = ? AND week != ?
                ''',
                (user, season, home_team, away_team, week),
            )
        conn.execute('''
            INSERT INTO picks (user, season, week, home_team, away_team, pick)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(user, season, week, home_team, away_team)
            DO UPDATE SET pick=excluded.pick
        ''', (user, season, week, home_team, away_team, pick))
        conn.commit()
    finally:
        conn.close()
    
    return jsonify({'message': 'Pick saved!'})

@user_picks.route('/get_user_picks')
def get_user_picks():
    ensure_picks_table_exists()
    user = request.args.get('user')
    season = request.args.get('season', type=int)
    week = request.args.get('week', type=int)

    if not user:
        return jsonify([])

    conn = get_db_connection()
    picks = conn.execute(
        'SELECT * FROM picks WHERE user = ? AND season = ? AND week = ?',
        (user, season, week)
    ).fetchall()
    conn.close()

    return jsonify([dict(ix) for ix in picks])

@user_picks.route('/get_my_picks')
def get_my_picks():
    """Return all picks for a user, grouped by season and week (newest first)."""
    ensure_picks_table_exists()
    user = request.args.get('user')
    if not user:
        return jsonify([])

    conn = get_db_connection()
    rows = conn.execute(
        'SELECT season, week, home_team, away_team, pick FROM picks WHERE user = ? ORDER BY season DESC, week DESC',
        (user,)
    ).fetchall()
    conn.close()

    return jsonify([dict(ix) for ix in rows])

@user_picks.route('/get_my_bets', methods=['GET'])
def get_my_bets():
    """
    Return all bets for a user, optionally filtered by season/week.
    Each bet includes outcome (Win/Loss/Pending/Push) and profit assuming $100 per bet.
    """
    ensure_picks_table_exists()

    user = request.args.get('user')
    season = request.args.get('season', type=int)
    week = request.args.get('week', type=int)

    if not user:
        return jsonify([])

    conn = get_db_connection()
    try:
        query = 'SELECT season, week, home_team, away_team, pick FROM picks WHERE user = ?'
        params = [user]
        if season is not None:
            query += ' AND season = ?'
            params.append(season)
        if week is not None:
            query += ' AND week = ?'
            params.append(week)
        query += ' ORDER BY season DESC, week DESC'

        rows = conn.execute(query, params).fetchall()
    finally:
        conn.close()

    if not rows:
        return jsonify([])

    bets_df = pd.DataFrame([dict(ix) for ix in rows])
    games_needed = games_df[['season', 'week', 'home_team', 'away_team', 'result', 'home_moneyline', 'away_moneyline']]
    merged_df = pd.merge(
        bets_df,
        games_needed,
        on=['season', 'week', 'home_team', 'away_team'],
        how='left',
        validate='many_to_one'
    )

    merged_df = _fill_reg_game_fallback(merged_df)

    merged_df[['outcome', 'points', 'profit']] = merged_df.apply(
        lambda row: pd.Series(
            determine_bet_outcome(
                pick=row['pick'],
                home_team=row['home_team'],
                away_team=row['away_team'],
                result=row['result'],
                home_moneyline=row['home_moneyline'],
                away_moneyline=row['away_moneyline'],
            )
        ),
        axis=1
    )

    bets_list = []
    for _, row in merged_df.iterrows():
        bets_list.append({
            'season': int(row['season']),
            'week': int(row['week']),
            'away_team': row['away_team'],
            'home_team': row['home_team'],
            'pick': row['pick'],
            'outcome': row['outcome'],
            'points': int(row['points']),
            'profit': float(row['profit']),
            'result': None if pd.isna(row['result']) else float(row['result']),
            'home_moneyline': None if pd.isna(row['home_moneyline']) else float(row['home_moneyline']),
            'away_moneyline': None if pd.isna(row['away_moneyline']) else float(row['away_moneyline']),
        })

    return jsonify(bets_list)

@user_picks.route('/leaderboard')
def leaderboard():
    ensure_picks_table_exists()
    
    conn = get_db_connection()
    picks_df = pd.read_sql_query('SELECT * FROM picks', conn)
    conn.close()

    if picks_df.empty:
        return jsonify([])

    cols_needed = ['season', 'week', 'home_team', 'away_team', 'result', 'home_moneyline', 'away_moneyline']
    results_df = games_df[(games_df['game_type'] == 'REG')].dropna(subset=['result'])[cols_needed]

    merged_df = pd.merge(picks_df, results_df, on=['season', 'week', 'home_team', 'away_team'], how='left')
    merged_df = _fill_reg_game_fallback(merged_df)
    merged_df = merged_df.dropna(subset=['result'])

    def calculate_pick_outcome(row):
        points = 0
        profit = 0
        bet_amount = 100

        home_won = row['result'] > 0
        away_won = row['result'] < 0
        
        is_correct = False
        if (row['pick'] == row['home_team'] and home_won) or \
           (row['pick'] == row['away_team'] and away_won):
            is_correct = True

        if is_correct:
            points = 1
            odds = row['home_moneyline'] if row['pick'] == row['home_team'] else row['away_moneyline']
            
            if pd.notna(odds):
                profit = calculate_profit(odds, bet_amount)
            else:
                profit = 0 
        else:
            if row['result'] != 0: 
                profit = -bet_amount

        return pd.Series([points, profit])

    merged_df[['points', 'profit']] = merged_df.apply(calculate_pick_outcome, axis=1)

    leaderboard_data = []
    grouped = merged_df.groupby('user')
    
    for user, group in grouped:
        total_picks = len(group)
        wins = group['points'].sum()
        total_profit = group['profit'].sum()
        
        losses = total_picks - wins
        pct = (wins / total_picks * 100) if total_picks > 0 else 0
        
        fmt_profit = f"${total_profit:,.2f}"
        if total_profit > 0:
            fmt_profit = f"+{fmt_profit}"

        leaderboard_data.append({
            'user': user,
            'record': f"{int(wins)}-{int(losses)}",
            'pct': f"{pct:.1f}%",
            'profit': fmt_profit,
            'raw_profit': total_profit 
        })

    leaderboard_data.sort(key=lambda x: (x['raw_profit'], float(x['pct'].strip('%'))), reverse=True)

    return jsonify(leaderboard_data)