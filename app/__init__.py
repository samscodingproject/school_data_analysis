from flask import Flask
from config import Config

def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)  # Configure the app with the Config object

    # Import the Blueprint
    from .routes import main as main_blueprint

    # Register the Blueprint
    app.register_blueprint(main_blueprint)

    return app