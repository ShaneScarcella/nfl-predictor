from flask import Flask

def create_app():
    """
    Application Factory: Creates and configures the Flask app.
    """
    app = Flask(__name__) 

    # Import and register blueprints
    from nfl_app.main.routes import main
    from nfl_app.ai_predictor.routes import ai_predictor
    from nfl_app.custom_engine.routes import custom_engine
    from nfl_app.sos_analysis.routes import sos_analysis
    from nfl_app.user_picks.routes import user_picks
    from nfl_app.chat.routes import chat

    app.register_blueprint(main)
    app.register_blueprint(ai_predictor)
    app.register_blueprint(custom_engine)
    app.register_blueprint(sos_analysis)
    app.register_blueprint(user_picks)
    app.register_blueprint(chat, url_prefix='/chat')

    return app