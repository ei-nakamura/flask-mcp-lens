from flask import Blueprint, jsonify

users_api = Blueprint("users_api", __name__)

@users_api.route("/")
def list_users():
    return jsonify([])

@users_api.route("/<int:user_id>", methods=["GET", "PUT", "DELETE"])
def user_detail(user_id):
    return jsonify({"id": user_id})
