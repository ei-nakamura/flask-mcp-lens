from flask import Blueprint, jsonify

try:
    from flask_login import login_required
except ImportError:
    def login_required(f):
        return f

auth_bp = Blueprint("auth", __name__)


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    return jsonify({"message": "login endpoint"})


@auth_bp.route("/logout", methods=["POST"])
@login_required
def logout():
    return jsonify({"message": "logged out"})


@auth_bp.route("/profile")
@login_required
def profile():
    return jsonify({"user": "current_user"})


@auth_bp.route("/profile/edit", methods=["GET", "POST"])
@login_required
def edit_profile():
    return jsonify({"message": "edit profile"})


@auth_bp.route("/password/change", methods=["POST"])
@login_required
def change_password():
    return jsonify({"message": "password changed"})


@auth_bp.route("/sessions")
@login_required
def list_sessions():
    return jsonify({"sessions": []})
