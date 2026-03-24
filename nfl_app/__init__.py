import os

from flask import Flask, jsonify, redirect, url_for, request

from nfl_app.extensions import db, login_manager


def create_app():
    """
    Application Factory: Creates and configures the Flask app.
    """
    app = Flask(__name__)

    basedir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
    data_dir = os.path.join(basedir, 'data')
    os.makedirs(data_dir, exist_ok=True)
    db_path = os.path.join(data_dir, 'app_users.db')

    app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-secret-change-for-production')
    app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{db_path}'
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

    db.init_app(app)
    login_manager.init_app(app)
    login_manager.login_view = 'auth.login'
    login_manager.login_message = None

    from nfl_app.models import User

    @login_manager.user_loader
    def load_user(user_id):
        return db.session.get(User, int(user_id))

    _JSON_AUTH_PATHS = frozenset({
        '/save_pick',
        '/get_user_picks',
        '/get_my_picks',
        '/get_my_bets',
    })

    @login_manager.unauthorized_handler
    def unauthorized():
        if request.path in _JSON_AUTH_PATHS or (
            request.path == '/chat/messages' and request.method == 'POST'
        ):
            return jsonify({'error': 'Authentication required.'}), 401
        return redirect(url_for('auth.login', next=request.url))

    # Import and register blueprints
    from nfl_app.auth.routes import auth
    from nfl_app.main.routes import main
    from nfl_app.ai_predictor.routes import ai_predictor
    from nfl_app.custom_engine.routes import custom_engine
    from nfl_app.sos_analysis.routes import sos_analysis
    from nfl_app.user_picks.routes import user_picks
    from nfl_app.chat.routes import chat

    app.register_blueprint(auth)
    app.register_blueprint(main)
    app.register_blueprint(ai_predictor)
    app.register_blueprint(custom_engine)
    app.register_blueprint(sos_analysis)
    app.register_blueprint(user_picks)
    app.register_blueprint(chat, url_prefix='/chat')

    with app.app_context():
        db.create_all()

    return app
