from flask import Blueprint, jsonify

try:
    from flask_jwt_extended import jwt_required
except ImportError:
    def jwt_required(**kwargs):
        def decorator(f):
            return f
        return decorator

posts_bp = Blueprint("posts", __name__)


@posts_bp.route("/")
@jwt_required()
def list_posts():
    return jsonify({"posts": []})


@posts_bp.route("/<int:post_id>")
@jwt_required()
def get_post(post_id):
    return jsonify({"id": post_id})


@posts_bp.route("/", methods=["POST"])
@jwt_required()
def create_post():
    return jsonify({}), 201


@posts_bp.route("/<int:post_id>", methods=["PUT"])
@jwt_required()
def update_post(post_id):
    return jsonify({"updated": post_id})


@posts_bp.route("/<int:post_id>", methods=["DELETE"])
@jwt_required()
def delete_post(post_id):
    return jsonify({"deleted": post_id})
