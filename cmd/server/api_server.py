"""
HTTP Server for Trading Bot API
Run: python cmd/server/api_server.py
"""

import logging
import sys
from pathlib import Path
import json

# Add parent folder to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from configs.config import load_config
from internal.services.trading_bot_api import TradingBotAPI

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def create_app():
    """Create Flask app"""
    try:
        from flask import Flask, request, jsonify
    except ImportError:
        logger.error("Flask not installed. Run: pip install flask")
        sys.exit(1)
    
    app = Flask(__name__)
    cfg = load_config()
    api = TradingBotAPI(cfg)
    
    @app.route('/health', methods=['GET'])
    def health():
        return jsonify({"status": "ok", "service": "trading-bot-api"})
    
    @app.route('/api/register', methods=['POST'])
    def register():
        data = request.get_json()
        result = api.register(
            username=data.get('username'),
            email=data.get('email'),
            password=data.get('password')
        )
        return jsonify(result)
    
    @app.route('/api/login', methods=['POST'])
    def login():
        data = request.get_json()
        result = api.login(
            username=data.get('username'),
            password=data.get('password')
        )
        return jsonify(result)
    
    @app.route('/api/user/<user_id>', methods=['GET'])
    def get_user(user_id):
        result = api.get_user_info(user_id)
        return jsonify(result)
    
    @app.route('/api/user/<user_id>/deposit-addresses', methods=['GET'])
    def get_deposits(user_id):
        result = api.get_deposit_addresses(user_id)
        return jsonify(result)
    
    @app.route('/api/user/<user_id>/deposit-status', methods=['GET'])
    def check_deposits(user_id):
        etherscan_key = request.args.get('etherscan_key')
        result = api.check_deposit_status(user_id, etherscan_key)
        return jsonify(result)
    
    @app.route('/api/trade', methods=['POST'])
    def place_trade():
        data = request.get_json()
        result = api.place_trade(
            user_id=data.get('user_id'),
            symbol=data.get('symbol'),
            position_type=data.get('position_type'),
            entry_price=float(data.get('entry_price', 0)),
            quantity=float(data.get('quantity', 0)),
            stop_loss=float(data.get('stop_loss')) if data.get('stop_loss') else None,
            take_profit=float(data.get('take_profit')) if data.get('take_profit') else None,
            leverage=float(data.get('leverage')) if data.get('leverage') else None
        )
        return jsonify(result)
    
    @app.errorhandler(404)
    def not_found(e):
        return jsonify({"status": "error", "message": "Endpoint not found"}), 404
    
    @app.errorhandler(500)
    def server_error(e):
        logger.error(f"Server error: {e}")
        return jsonify({"status": "error", "message": "Internal server error"}), 500
    
    return app


if __name__ == "__main__":
    try:
        app = create_app()
        logger.info("Starting Trading Bot API Server on http://0.0.0.0:5000")
        app.run(host="0.0.0.0", port=5000, debug=False)
    except Exception as e:
        logger.error(f"Failed to start server: {e}")
        sys.exit(1)
