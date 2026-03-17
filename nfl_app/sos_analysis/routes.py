from flask import Blueprint, jsonify, request
from nfl_app.data_loader import games_df, team_avg_stats_df

sos_analysis = Blueprint('sos_analysis', __name__)

# Typical per-game ranges (rough league bounds) to normalize team stats into a 0-1 strength score
_STRENGTH = {
    'off_yards_lo': 200, 'off_yards_hi': 450,
    'off_tds_lo': 0.5, 'off_tds_hi': 4.0,
    'turnovers_hi': 3.0,
    'def_yards_lo': 200, 'def_yards_hi': 450,
    'def_tds_lo': 0.5, 'def_tds_hi': 4.0,
    'def_turnovers_hi': 3.0,
}


def _safe_float(val, default):
    """Return float(val) if val is present and not NaN, else default."""
    if val is None:
        return default
    try:
        v = float(val)
        return default if v != v else v  # NaN check
    except (TypeError, ValueError):
        return default


def _opponent_strength_from_stats(opp_row):
    """Compute a 0-1 strength score from rolling avg offense/defense stats (higher = stronger team)."""
    def _norm(val, lo, hi):
        v = _safe_float(val, None)
        if v is None:
            return 0.5
        return max(0.0, min(1.0, (v - lo) / (hi - lo) if hi != lo else 0.5))

    off_y = _norm(opp_row.get('avg_off_yards'), _STRENGTH['off_yards_lo'], _STRENGTH['off_yards_hi'])
    off_t = _norm(opp_row.get('avg_off_tds'), _STRENGTH['off_tds_lo'], _STRENGTH['off_tds_hi'])
    to = _safe_float(opp_row.get('avg_turnovers'), 1.5)
    off_to = 1.0 - max(0.0, min(1.0, to / _STRENGTH['turnovers_hi']))

    def_y = opp_row.get('avg_def_yards_allowed')
    def_y_norm = 1.0 - _norm(def_y, _STRENGTH['def_yards_lo'], _STRENGTH['def_yards_hi'])  # fewer allowed = better
    def_t = opp_row.get('avg_def_tds_allowed')
    def_t_norm = 1.0 - _norm(def_t, _STRENGTH['def_tds_lo'], _STRENGTH['def_tds_hi'])
    to_f = _safe_float(opp_row.get('avg_def_turnovers_forced'), 1.0)
    def_to = max(0.0, min(1.0, to_f / _STRENGTH['def_turnovers_hi']))

    strength = (off_y + off_t + off_to + def_y_norm + def_t_norm + def_to) / 6.0
    return max(0.0, min(1.0, strength))

@sos_analysis.route('/get_sos_analysis', methods=['GET'])
def get_sos_analysis():
    if games_df.empty or team_avg_stats_df.empty: 
        return jsonify({'error': 'Game or stats data not loaded.'})
    
    team, season, week = request.args.get('team'), request.args.get('season', type=int), request.args.get('week', type=int)
    filter_option = request.args.get('filter', 'all')
    
    if not team or not season or not week: 
        return jsonify({'error': 'Missing parameters.'})
    
    team_games = games_df[
        (games_df['season'] == season) & 
        (games_df['week'] <= week) & 
        ((games_df['home_team'] == team) | (games_df['away_team'] == team)) & 
        (games_df['result'].notna())
    ].sort_values(by='week', ascending=False).copy()
    
    if team_games.empty: 
        return jsonify({'total_score': 0, 'breakdown': [], 'message': 'No past games found for this period.'})
    
    if filter_option == 'last3': team_games = team_games.head(3)
    elif filter_option == 'last5': team_games = team_games.head(5)
    
    game_breakdown = []
    total_sos_score = 0.0

    for _, game in team_games.iterrows():
        is_home_game = (game['home_team'] == team)
        opponent = game['away_team'] if is_home_game else game['home_team']
        margin = game['result'] if is_home_game else -game['result']
        result_flag = 1 if margin > 0 else (-1 if margin < 0 else 0)

        opp_stats = team_avg_stats_df[
            (team_avg_stats_df['team'] == opponent) &
            (team_avg_stats_df['season'] == season) &
            (team_avg_stats_df['week'] == game['week'])
        ]

        if not opp_stats.empty:
            opp_row = opp_stats.iloc[0]
            opp_strength = _opponent_strength_from_stats(opp_row)
            opp_record_str = f"{int(opp_row['entering_wins'])}-{int(opp_row['entering_losses'])}-{int(opp_row['entering_ties'])}"
        else:
            opp_strength = 0.5
            opp_record_str = "0-0-0"

        # Quality component: beat good team = more credit; lose to bad team = more penalty (flipped from win%)
        if result_flag == 1:
            quality_component = 10.0 * opp_strength
        elif result_flag == -1:
            quality_component = -10.0 * (1.0 - opp_strength)  # losing to weak team hurts more
        else:
            quality_component = 0.0

        capped_margin = max(min(margin, 28), -28)
        margin_component = capped_margin / 5.0

        game_value = quality_component + margin_component

        if result_flag == 1 and not is_home_game:
            game_value += 1.0  # small bonus for road wins

        total_sos_score += game_value

        game_breakdown.append({
            'week': game['week'],
            'opponent': opponent,
            'result': 'W' if result_flag == 1 else ('L' if result_flag == -1 else 'T'),
            'margin': margin,
            'opp_record': opp_record_str,
            'opp_strength': f"{opp_strength:.3f}",
            'game_value': round(game_value, 2)
        })

    game_breakdown.sort(key=lambda x: x['week'])

    # Normalize to 0–100 scale from average game value (approx range [-16, 16])
    num_games = len(game_breakdown)
    avg_game_value = total_sos_score / num_games if num_games > 0 else 0.0
    min_val, max_val = -16.0, 16.0
    norm = (avg_game_value - min_val) / (max_val - min_val) * 100.0
    normalized_score = max(0.0, min(100.0, norm))

    return jsonify({
        'total_score': round(normalized_score, 2),
        'raw_total_score': round(total_sos_score, 2),
        'games_considered': num_games,
        'breakdown': game_breakdown
    })