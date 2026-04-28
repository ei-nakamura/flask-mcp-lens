from flask import Blueprint, abort, request

api_bp = Blueprint("api", __name__)


@api_bp.before_request
def require_api_token():
    token = request.headers.get("Authorization")
    if not token:
        abort(401)


from app.api.posts import posts_bp  # noqa: E402
from app.api.users import users_bp  # noqa: E402

api_bp.register_blueprint(users_bp, url_prefix="/users")
api_bp.register_blueprint(posts_bp, url_prefix="/posts")
