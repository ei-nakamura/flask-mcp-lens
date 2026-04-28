from flask import Blueprint

from app.api.posts import posts_api
from app.api.users import users_api

api_v1 = Blueprint("api_v1", __name__)
api_v1.register_blueprint(users_api, url_prefix="/users")
api_v1.register_blueprint(posts_api, url_prefix="/posts")
