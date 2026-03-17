from flask import Blueprint, render_template, jsonify
import nflreadpy as nfl
import json
import os
from nfl_app.data_loader import team_logos, games_df

main = Blueprint('main', __name__)

METRICS_FILE = os.path.join(os.path.dirname(__file__), '../../data/model_metrics.json')

@main.route('/')
def home():
    return render_template('index.html')

@main.route('/get_current_week_info')
def get_current_week_info():
    try:
        current_season = nfl.get_current_season()
        current_week = nfl.get_current_week()

        # Default to a week that exists in the UI (regular season only: 1-18).
        # During regular season use current week; in post-season/offseason use last regular-season week.
        if not games_df.empty:
            reg = games_df[games_df['game_type'] == 'REG']
            season_weeks = [int(w) for w in reg[reg['season'] == current_season]['week'].dropna().unique()]
            if season_weeks:
                valid_weeks = set(season_weeks)
                default_week = current_week if current_week in valid_weeks else max(season_weeks)
            else:
                default_week = min(current_week, 18)
        else:
            default_week = min(current_week, 18)

        return jsonify({'season': current_season, 'week': default_week})
    except Exception as e:
        return jsonify({'error': f'Could not determine current week: {e}'})

@main.route('/get_performance_stats')
def get_performance_stats():
    try:
        with open(METRICS_FILE, 'r') as f:
            metrics = json.load(f)
        return jsonify(metrics)
    except FileNotFoundError:
        return jsonify({'error': 'Model metrics not found. Run the training pipeline.'})

@main.route('/get_teams')
def get_teams():
    # Try getting teams from logos first
    teams = sorted(list(team_logos.keys()))
    # Fallback: scrape them from the schedule if logos are missing
    if not teams and not games_df.empty:
        teams = sorted(games_df['home_team'].dropna().unique().tolist())
    return jsonify(teams)