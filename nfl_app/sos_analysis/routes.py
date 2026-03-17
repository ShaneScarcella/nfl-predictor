from flask import Blueprint, jsonify, request
from nfl_app.data_loader import games_df, team_avg_stats_df

sos_analysis = Blueprint('sos_analysis', __name__)

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
        (games_df['week'] < week) & 
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
            opp_win_pct = opp_row['entering_win_pct']
            opp_record_str = f"{int(opp_row['entering_wins'])}-{int(opp_row['entering_losses'])}-{int(opp_row['entering_ties'])}"
        else:
            opp_win_pct = 0.5
            opp_record_str = "0-0-0"

        # Adjusted SoS: stronger margin impact (divisor 5), cap ±28 so huge games don't dominate, road-win bonus
        capped_margin = max(min(margin, 28), -28)
        margin_component = capped_margin / 5.0

        game_value = (result_flag * (opp_win_pct * 10)) + margin_component

        if result_flag == 1 and not is_home_game:
            game_value += 1.0  # small bonus for road wins

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