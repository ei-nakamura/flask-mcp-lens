from flask import Blueprint, jsonify

main_bp = Blueprint("main_bp", __name__)

@main_bp.before_request
def bp_before():
    pass

@main_bp.route("/")
def main_index():
    return jsonify({"page": "main"})

@main_bp.route("/items", methods=["GET", "POST"])
def items():
    return jsonify([])

@main_bp.route("/items/<int:item_id>", methods=["GET", "PUT", "DELETE"])
def item_detail(item_id):
    return jsonify({"id": item_id})

@main_bp.route("/search")
def search():
    return jsonify([])

@main_bp.route("/about")
def about():
    return jsonify({"info": "about"})
