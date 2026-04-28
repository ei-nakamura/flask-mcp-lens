from functools import wraps

from flask import Blueprint, jsonify


def require_admin(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        return f(*args, **kwargs)
    return decorated


admin_bp = Blueprint("admin", __name__)


@admin_bp.route("/dashboard")
@require_admin
def dashboard():
    return jsonify({"admin": "dashboard"})


@admin_bp.route("/users")
@require_admin
def list_users():
    return jsonify({"users": []})


@admin_bp.route("/users/<int:user_id>")
@require_admin
def get_user(user_id):
    return jsonify({"id": user_id})


@admin_bp.route("/users/<int:user_id>", methods=["DELETE"])
@require_admin
def delete_user(user_id):
    return jsonify({"deleted": user_id})


@admin_bp.route("/reports")
@require_admin
def reports():
    return jsonify({"reports": []})


@admin_bp.route("/settings")
@require_admin
def settings():
    return jsonify({"settings": {}})


@admin_bp.route("/settings", methods=["PUT"])
@require_admin
def update_settings():
    return jsonify({"updated": True})


@admin_bp.route("/logs")
@require_admin
def logs():
    return jsonify({"logs": []})
