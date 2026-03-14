from flask import Blueprint, render_template, jsonify
import nflreadpy as nfl
import json
import os

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
        return jsonify({'season': current_season, 'week': current_week})
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