"""
HEMS Web Application Entry Point
Usage: python run.py
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from backend.app import create_app
from config import Config

if __name__ == '__main__':
    app = create_app()
    # Configure stdout to handle UTF-8 characters on Windows
    sys.stdout.reconfigure(encoding='utf-8')
    print("\n" + "="*65)
    print("  ⚡ HEMS Pakistan — Convex Optimization Dashboard v3.0")
    print("  NEPRA IESCO Feb 2026 | Budget 2024-25 | SOCP + Fallback")
    print(f"  → Open browser: http://localhost:{Config.PORT}")
    print("="*65 + "\n")
    app.run(host=Config.HOST, port=Config.PORT, debug=Config.DEBUG)