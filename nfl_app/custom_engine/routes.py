from flask import Blueprint, jsonify, request
from nfl_app.data_loader import team_avg_stats_df
import pandas as pd

custom_engine = Blueprint('custom_engine', __name__)

@custom_engine.route('/custom_predict', methods=['POST'])
def custom_predict():
    if team_avg_stats_df.empty: return jsonify({'error': 'Team average stats not loaded.'})
    
    data = request.get_json()
    home_team, away_team, season, week = data.get('home_team'), data.get('away_team'), data.get('season'), data.get('week')
    weights = data.get('weights')

    # Get stats for the specific week
    home_stats_row = team_avg_stats_df[(team_avg_stats_df['team'] == home_team) & (team_avg_stats_df['season'] == season) & (team_avg_stats_df['week'] == week)]
    away_stats_row = team_avg_stats_df[(team_avg_stats_df['team'] == away_team) & (team_avg_stats_df['season'] == season) & (team_avg_stats_df['week'] == week)]

    if home_stats_row.empty or away_stats_row.empty:
        return jsonify({'error': 'Could not find stats for this matchup.'})

    home_stats = home_stats_row.iloc[0]
    away_stats = away_stats_row.iloc[0]

    if pd.isna(home_stats['avg_off_yards']) or pd.isna(away_stats['avg_off_yards']):
        return jsonify({'error': 'Cannot generate predictions for Week 1.'})

    home_score, away_score = 0.0, 0.0
    breakdown = []

    def add_score(cat_name, h_stat, a_stat, weight, higher_is_better):
        nonlocal home_score, away_score, breakdown
        total = h_stat + a_stat
        if total > 0:
            if higher_is_better:
                h_share, a_share = h_stat / total, a_stat / total
            else:
                h_share, a_share = a_stat / total, h_stat / total
                
            home_score += weight * h_share
            away_score += weight * a_share
            breakdown.append({'cat': cat_name, 'h_val': round(h_stat, 1), 'a_val': round(a_stat, 1), 'h_share': h_share, 'a_share': a_share})

    add_score('Offense (Yds/G)', home_stats['avg_off_yards'], away_stats['avg_off_yards'], weights['offense_yards'], True)
    add_score('Offense (TDs/G)', home_stats['avg_off_tds'], away_stats['avg_off_tds'], weights['offense_td'], True)
    add_score('Defense (Yds Allow/G)', home_stats['avg_def_yards_allowed'], away_stats['avg_def_yards_allowed'], weights['defense_yards'], False)
    add_score('Defense (TDs Allow/G)', home_stats['avg_def_tds_allowed'], away_stats['avg_def_tds_allowed'], weights['defense_td'], False)
    add_score('Turnovers Lost (Per G)', home_stats['avg_turnovers'], away_stats['avg_turnovers'], weights['turnovers'], False)
    add_score('Turnovers Forced (Per G)', home_stats['avg_def_turnovers_forced'], away_stats['avg_def_turnovers_forced'], weights['def_turnovers'], True)

    winner = home_team if home_score > away_score else away_team
    if home_score == away_score: winner = "It's a tie!"
    
    return jsonify({'winner': winner, 'home_score': round(home_score, 1), 'away_score': round(away_score, 1), 'breakdown': breakdown})