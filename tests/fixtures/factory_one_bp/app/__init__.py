from flask import Flask

from app.views import main_bp


def create_app():
    app = Flask(__name__)

    @app.before_request
    def app_before():
        pass

    app.register_blueprint(main_bp, url_prefix="/main")
    return app
