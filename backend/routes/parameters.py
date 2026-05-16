from flask import Blueprint, jsonify
import json, os

params_bp = Blueprint('params', __name__)
BASE = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))


@params_bp.route('/tariffs', methods=['GET'])
def tariffs():
    with open(os.path.join(BASE, 'data', 'tariffs.json')) as f:
        return jsonify(json.load(f))


@params_bp.route('/loads', methods=['GET'])
def loads():
    with open(os.path.join(BASE, 'data', 'load_profiles.json')) as f:
        return jsonify(json.load(f))


@params_bp.route('/solar', methods=['GET'])
def solar():
    with open(os.path.join(BASE, 'data', 'solar_profiles.json')) as f:
        return jsonify(json.load(f))