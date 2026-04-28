from flask import Flask

try:
    from flask_login import LoginManager
    _login_manager = LoginManager()
except ImportError:
    _login_manager = None

try:
    from flask_jwt_extended import JWTManager
    _jwt = JWTManager()
except ImportError:
    _jwt = None


def create_app():
    app = Flask(__name__)
    app.config["SECRET_KEY"] = "test-secret"
    app.config["JWT_SECRET_KEY"] = "test-jwt-secret"

    if _login_manager is not None:
        _login_manager.init_app(app)
    if _jwt is not None:
        _jwt.init_app(app)

    from app.api import api_bp
    from app.auth import auth_bp
    from app.public import public_bp
    # admin_bp is intentionally not registered (unregistered-blueprint test fixture)

    app.register_blueprint(auth_bp, url_prefix="/auth")
    app.register_blueprint(api_bp, url_prefix="/api/v1")
    app.register_blueprint(public_bp)

    return app
