"""Health check routes"""
from flask import Blueprint, jsonify
from services.session_service import get_session_service

health_bp = Blueprint('health', __name__)

@health_bp.route("/health", methods=["GET"])
def health_check():
    """Basic health check endpoint"""
    session_service = get_session_service()
    session_service.clear_inactive_sessions()
    return jsonify({
        "status": "healthy",
        "message": "MedSense AI Bot is running!"
    }), 200

@health_bp.route("/ping", methods=["GET"])
def ping():
    """Simple ping endpoint"""
    return "pong", 200 
