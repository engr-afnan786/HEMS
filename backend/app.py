"""
HEMS Flask Application Factory — UPDATED v5.0
Added: Solar Advisor blueprint
"""

from flask import Flask, send_from_directory
from flask_cors import CORS
import os, sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import Config
from backend.routes.optimization import opt_bp
from backend.routes.parameters import params_bp
from backend.routes.data import data_bp
from backend.routes.advisor import advisor_bp   # ← NEW


def create_app():
    BASE     = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    FRONTEND = os.path.join(BASE, 'frontend')

    app = Flask(__name__)
    app.config.from_object(Config)
    CORS(app)

    app.register_blueprint(opt_bp,     url_prefix='/api')
    app.register_blueprint(params_bp,  url_prefix='/api')
    app.register_blueprint(data_bp,    url_prefix='/api')
    app.register_blueprint(advisor_bp, url_prefix='/api')    # ← NEW

    @app.route('/')
    def index():
        return send_from_directory(FRONTEND, 'index.html')

    @app.route('/js/<path:f>')
    def js(f):
        return send_from_directory(os.path.join(FRONTEND, 'js'), f)

    @app.route('/css/<path:f>')
    def css(f):
        return send_from_directory(os.path.join(FRONTEND, 'css'), f)

    return app
