from flask import Blueprint, jsonify
data_bp = Blueprint('data', __name__)


@data_bp.route('/health', methods=['GET'])
def health():
    return jsonify({
        'status':  'ok',
        'version': '3.0.0',
        'project': 'HEMS Pakistan — Robust Convex Optimization',
        'features': [
            'LP + SOCP',
            'Load Shedding G_t Matrix',
            'Net/Gross/Capacity-Tax Billing',
            'Solver Fallback Cascade',
            'MQTT Hardware Control'
        ]
    })