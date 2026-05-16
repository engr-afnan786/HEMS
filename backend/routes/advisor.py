"""
Solar Advisor API Route — NEW
Add to backend/routes/
"""

from flask import Blueprint, request, jsonify
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from src.solar_advisor import (
    recommend_systems, recommendation_to_dict,
    estimate_monthly_bill, size_system_from_load,
    SOLAR_PANELS, INVERTERS, BATTERIES
)

advisor_bp = Blueprint('advisor', __name__)


@advisor_bp.route('/advisor/recommend', methods=['POST'])
def recommend():
    """Generate solar system recommendations based on user input."""
    body = request.get_json(force=True) or {}
    try:
        monthly_units = float(body.get('monthly_units', 500))
        budget = float(body.get('budget', 1000000))
        has_loadshedding = body.get('has_loadshedding', True)
        wants_battery = body.get('wants_battery', None)
        location = body.get('location', 'Rawalpindi')

        current_bill = estimate_monthly_bill(monthly_units)
        ideal_kw = size_system_from_load(monthly_units)

        recs = recommend_systems(
            monthly_units=monthly_units,
            budget_pkr=budget,
            has_loadshedding=has_loadshedding,
            wants_battery=wants_battery,
            location=location
        )

        return jsonify({
            'input': {
                'monthly_units': monthly_units,
                'budget_pkr': budget,
                'current_bill_pkr': round(current_bill),
                'annual_bill_pkr': round(current_bill * 12),
                'ideal_system_kw': ideal_kw,
                'has_loadshedding': has_loadshedding,
                'location': location
            },
            'recommendations': [recommendation_to_dict(r) for r in recs],
            'total_options': len(recs)
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@advisor_bp.route('/advisor/catalog', methods=['GET'])
def catalog():
    """Return available equipment catalog."""
    return jsonify({
        'panels': SOLAR_PANELS,
        'inverters': INVERTERS,
        'batteries': BATTERIES
    })
