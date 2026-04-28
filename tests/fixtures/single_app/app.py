from flask import Flask, jsonify, request

app = Flask(__name__)

@app.before_request
def log_request():
    pass

@app.route("/")
def index():
    return jsonify({"message": "hello"})

@app.route("/users", methods=["GET", "POST"])
def users():
    if request.method == "POST":
        return jsonify({}), 201
    return jsonify([])

@app.route("/users/<int:user_id>", methods=["GET", "DELETE"])
def user_detail(user_id):
    return jsonify({"id": user_id})
