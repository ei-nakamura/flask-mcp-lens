from flask import Blueprint, jsonify
from flask.views import MethodView

try:
    from flask_jwt_extended import jwt_required
except ImportError:
    def jwt_required(**kwargs):
        def decorator(f):
            return f
        return decorator

users_bp = Blueprint("users", __name__)


@users_bp.route("/")
@jwt_required()
def list_users():
    return jsonify({"users": []})


@users_bp.route("/<int:user_id>")
@jwt_required()
def get_user(user_id):
    return jsonify({"id": user_id})


@users_bp.route("/", methods=["POST"])
@jwt_required()
def create_user():
    return jsonify({}), 201


@users_bp.route("/<int:user_id>", methods=["DELETE"])
@jwt_required()
def delete_user(user_id):
    return jsonify({"deleted": user_id})


class UserView(MethodView):
    decorators = [jwt_required()]

    def get(self, user_id):
        return jsonify({"id": user_id, "detail": True})

    def put(self, user_id):
        return jsonify({"updated": user_id})


users_bp.add_url_rule(
    "/view/<int:user_id>",
    view_func=UserView.as_view("user_view"),
)
