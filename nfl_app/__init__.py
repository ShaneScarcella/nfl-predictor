from flask import Flask

def create_app():
    """
    Application Factory: Creates and configures the Flask app.
    This follows the standard Flask application factory pattern.
    """
    app = Flask(__name__, template_folder='../templates')

    # Import and register our blueprints (the features of our app)
    from nfl_app.main.routes import main
    from nfl_app.ai_predictor.routes import ai_predictor
    from nfl_app.custom_engine.routes import custom_engine
    from nfl_app.sos_analysis.routes import sos_analysis

    app.register_blueprint(main)
    app.register_blueprint(ai_predictor)
    app.register_blueprint(custom_engine)
    app.register_blueprint(sos_analysis)

    return app