from flask import Blueprint, jsonify

public_bp = Blueprint("public", __name__)


@public_bp.route("/health")
def health():
    return jsonify({"status": "ok"})


@public_bp.route("/")
def index():
    return jsonify({"message": "welcome"})


@public_bp.route("/about")
def about():
    return jsonify({"message": "about"})


@public_bp.route("/status")
def status():
    return jsonify({"status": "running"})


@public_bp.route("/version")
def version():
    return jsonify({"version": "0.2.0"})
