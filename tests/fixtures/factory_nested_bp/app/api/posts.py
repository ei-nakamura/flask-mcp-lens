from flask import Blueprint, jsonify

posts_api = Blueprint("posts_api", __name__)

@posts_api.route("/")
def list_posts():
    return jsonify([])

@posts_api.route("/<int:post_id>", methods=["GET"])
def post_detail(post_id):
    return jsonify({"id": post_id})
