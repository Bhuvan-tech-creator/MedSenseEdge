"""
MedSense AI - Medical Chatbot Application
Refactored but maintains exact same functionality and launch behavior as original
"""
from flask import Flask, request, jsonify, current_app
import os
import threading
import time
from datetime import datetime, timedelta
from config import Config
from models.database import init_database
from services.session_service import get_session_service
from services.message_service import (
    send_whatsapp_message, send_telegram_message, 
    get_whatsapp_image_url, download_and_encode_whatsapp_image,
    get_telegram_file_path, download_telegram_image,
    test_telegram_token, get_telegram_webhook_info, set_telegram_webhook, get_telegram_bot_info
)
from services.message_processor import get_message_processor
from services.followup_service import get_followup_service
from utils.constants import WELCOME_MSG, IMAGE_ERROR_MSG, PROCESSING_TEXT_MSG, PROCESSING_IMAGE_MSG, PROCESSING_LOCATION_MSG

# Import blueprints
from routes.whatsapp import whatsapp_bp
from routes.telegram import telegram_bp
from routes.health import health_bp

app = Flask(__name__)
app.config.from_object(Config)
init_database()

# Register blueprints
app.register_blueprint(whatsapp_bp)
app.register_blueprint(telegram_bp)
app.register_blueprint(health_bp)

session_service = get_session_service()
message_processor = get_message_processor()

# Message deduplication for WhatsApp webhooks
processed_messages = {}

# Message deduplication for Telegram webhooks
processed_telegram_messages = {}

def clean_old_messages():
    """Clean messages older than 5 minutes"""
    cutoff = datetime.now() - timedelta(minutes=5)
    # Clean WhatsApp messages
    to_remove = [msg_id for msg_id, timestamp in processed_messages.items() if timestamp < cutoff]
    for msg_id in to_remove:
        del processed_messages[msg_id]
    
    # Clean Telegram messages
    to_remove_telegram = [msg_id for msg_id, timestamp in processed_telegram_messages.items() if timestamp < cutoff]
    for msg_id in to_remove_telegram:
        del processed_telegram_messages[msg_id]

def is_duplicate_message(message_id):
    """Check if we've already processed this message"""
    clean_old_messages()
    if message_id in processed_messages:
        return True
    processed_messages[message_id] = datetime.now()
    return False

def is_duplicate_telegram_message(message_id):
    """Check if we've already processed this Telegram message"""
    clean_old_messages()
    if message_id in processed_telegram_messages:
        return True
    processed_telegram_messages[message_id] = datetime.now()
    return False

@app.route("/", methods=["GET"])
def health_check():
    session_service.clear_inactive_sessions()
    return "MedSense AI Bot is running!", 200

@app.route("/test-telegram", methods=["GET"])
def test_telegram_endpoint():
    token_works = test_telegram_token()
    webhook_info = get_telegram_webhook_info()
    return jsonify({
        "telegram_token_valid": token_works,
        "webhook_info": webhook_info
    })

@app.route("/bot-info", methods=["GET"])
def get_bot_info():
    """Get Telegram bot information"""
    bot_info = get_telegram_bot_info()
    return jsonify({
        "bot_info": bot_info
    })

@app.route("/test-followup", methods=["GET"])
def test_followup_system():
    """Test follow-up system status"""
    from models.user import get_pending_followups
    from services.followup_service import get_followup_service
    followup_service = get_followup_service()
    pending_followups = get_pending_followups()
    return jsonify({
        "followup_scheduler_running": followup_service.running,
        "pending_followups_count": len(pending_followups),
        "pending_followups": pending_followups[:5],
        "check_interval_seconds": followup_service.check_interval
    })

@app.route("/trigger-followup/<user_id>", methods=["GET"])
def trigger_followup_test(user_id):
    """Manually trigger a follow-up for testing purposes"""
    from services.followup_service import get_followup_service
    try:
        followup_service = get_followup_service()
        followup_service._process_pending_followups()
        return jsonify({
            "status": "follow-up check triggered",
            "user_id": user_id,
            "message": "Check the logs to see if any follow-ups were sent"
        })
    except Exception as e:
        return jsonify({
            "status": "error",
            "error": str(e)
        })

@app.route("/set-webhook/<path:webhook_url>", methods=["GET"])
def manual_set_webhook(webhook_url):
    if not webhook_url.startswith(('http://', 'https://')):
        webhook_url = f"https://{webhook_url}"
    success = set_telegram_webhook(webhook_url)
    webhook_info = get_telegram_webhook_info()
    return jsonify({
        "webhook_set": success,
        "webhook_url": f"{webhook_url}/webhook/telegram",
        "current_webhook_info": webhook_info
    })

@app.route("/test-duplicate-prevention", methods=["GET"])
def test_duplicate_prevention():
    """Test endpoint to verify duplicate prevention systems"""
    from services.message_processor import get_message_processor
    from services.message_service import send_whatsapp_message, send_telegram_message
    import time
    
    test_user = "test_user_123"
    test_message = "I have a headache and fever"
    
    results = {
        "webhook_deduplication": {
            "whatsapp": {},
            "telegram": {}
        },
        "message_processor_deduplication": {},
        "message_sending_deduplication": {}
    }
    
    # Test webhook deduplication
    msg_id = "test_msg_001"
    first_check = is_duplicate_message(msg_id)
    second_check = is_duplicate_message(msg_id)
    results["webhook_deduplication"]["whatsapp"] = {
        "first_check": first_check,
        "second_check": second_check,
        "working": not first_check and second_check
    }
    
    telegram_msg_id = f"{test_user}_test_msg_001"
    first_tg_check = is_duplicate_telegram_message(telegram_msg_id)
    second_tg_check = is_duplicate_telegram_message(telegram_msg_id)
    results["webhook_deduplication"]["telegram"] = {
        "first_check": first_tg_check,
        "second_check": second_tg_check,
        "working": not first_tg_check and second_tg_check
    }
    
    # Test message processor deduplication
    processor = get_message_processor()
    
    # First call - should not be duplicate
    start_time = time.time()
    first_response = processor.handle_text_message(test_user, test_message, "test")
    first_time = time.time() - start_time
    
    # Second call - should be duplicate or cached
    start_time = time.time()
    second_response = processor.handle_text_message(test_user, test_message, "test")
    second_time = time.time() - start_time
    
    results["message_processor_deduplication"] = {
        "first_response_time": first_time,
        "second_response_time": second_time,
        "responses_match": first_response == second_response,
        "second_faster": second_time < first_time,
        "working": second_time < first_time * 0.5  # Should be much faster if cached
    }
    
    # Test message sending deduplication
    test_recipient = "test_recipient_123"
    test_send_message = "Test message for deduplication"
    
    # First send - should work
    start_time = time.time()
    first_send = send_whatsapp_message(test_recipient, test_send_message)
    first_send_time = time.time() - start_time
    
    # Second send - should be duplicate prevented
    start_time = time.time()
    second_send = send_whatsapp_message(test_recipient, test_send_message)
    second_send_time = time.time() - start_time
    
    results["message_sending_deduplication"] = {
        "first_send_time": first_send_time,
        "second_send_time": second_send_time,
        "both_returned_true": first_send and second_send,
        "second_faster": second_send_time < first_send_time,
        "working": second_send_time < first_send_time * 0.5  # Should be much faster if duplicate
    }
    
    return jsonify(results)

@app.route("/test-async-fix", methods=["GET"])
def test_async_fix():
    """Test the async/threading fix for message processing"""
    import asyncio
    from services.medical_agent import get_medical_agent_system
    
    test_user = "test_user_async"
    test_message = "I have a headache and feel dizzy"
    
    results = {
        "direct_async_call": {},
        "threaded_async_call": {},
        "message_processor_call": {}
    }
    
    # Test 1: Direct async call (should work in main thread)
    try:
        start_time = time.time()
        agent_system = get_medical_agent_system()
        
        # Try to get existing loop
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # If loop is running, we can't use run_until_complete
                results["direct_async_call"] = {
                    "status": "loop_already_running",
                    "error": "Cannot run async in already running loop"
                }
            else:
                # Loop exists but not running
                result = loop.run_until_complete(
                    agent_system.analyze_medical_query(
                        user_id=test_user,
                        message=test_message,
                        image_data=None,
                        location=None,
                        emergency=False
                    )
                )
                results["direct_async_call"] = {
                    "status": "success",
                    "time_taken": time.time() - start_time,
                    "result_keys": list(result.keys()) if result else []
                }
        except RuntimeError as e:
            # No event loop in current thread
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            result = loop.run_until_complete(
                agent_system.analyze_medical_query(
                    user_id=test_user,
                    message=test_message,
                    image_data=None,
                    location=None,
                    emergency=False
                )
            )
            loop.close()
            results["direct_async_call"] = {
                "status": "success_new_loop",
                "time_taken": time.time() - start_time,
                "result_keys": list(result.keys()) if result else []
            }
    except Exception as e:
        results["direct_async_call"] = {
            "status": "error",
            "error": str(e)
        }
    
    # Test 2: Threaded async call (what we use in production)
    try:
        start_time = time.time()
        result_container = {}
        
        def test_context_in_thread():
            """Test async processing in a separate thread with Flask context"""
            # Get Flask app context
            app_context = current_app._get_current_object()
            
            try:
                # Create new event loop for this thread
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                
                # Run with Flask app context
                with app_context.app_context():
                    agent_system = get_medical_agent_system()
                    result = loop.run_until_complete(
                        agent_system.analyze_medical_query(
                            user_id=test_user,
                            message=test_message,
                            image_data=None,
                            location=None,
                            emergency=False
                        )
                    )
                    result_container["result"] = result
                    result_container["status"] = "success"
            except Exception as e:
                result_container["status"] = "error"
                result_container["error"] = str(e)
            finally:
                if loop:
                    loop.close()
        
        thread = threading.Thread(target=test_context_in_thread)
        thread.start()
        thread.join(timeout=30)  # Wait up to 30 seconds
        
        if thread.is_alive():
            results["threaded_async_call"] = {
                "status": "timeout",
                "error": "Thread took too long"
            }
        else:
            results["threaded_async_call"] = {
                "status": result_container.get("status", "unknown"),
                "time_taken": time.time() - start_time,
                "result_keys": list(result_container.get("result", {}).keys()) if result_container.get("result") else [],
                "error": result_container.get("error")
            }
    except Exception as e:
        results["threaded_async_call"] = {
            "status": "error",
            "error": str(e)
        }
    
    # Test 3: Message processor call (production path)
    try:
        start_time = time.time()
        processor = get_message_processor()
        response = processor.handle_text_message(test_user, test_message, "test")
        results["message_processor_call"] = {
            "status": "success",
            "time_taken": time.time() - start_time,
            "response_length": len(response) if response else 0,
            "has_response": bool(response)
        }
    except Exception as e:
        results["message_processor_call"] = {
            "status": "error",
            "error": str(e)
        }
    
    return jsonify(results)

@app.route("/test-webhook-performance", methods=["GET"])
def test_webhook_performance():
    """Test webhook performance and background processing"""
    import time
    import requests
    
    results = {
        "webhook_response_time": {},
        "background_processing_test": {}
    }
    
    # Test webhook response time
    start_time = time.time()
    
    # Simulate webhook data
    test_data = {
        "message": {
            "message_id": 999999,
            "chat": {"id": 999999},
            "text": "test performance message",
            "date": int(time.time())
        }
    }
    
    try:
        # Test webhook endpoint directly
        with app.test_client() as client:
            response = client.post(
                '/webhook/telegram',
                json=test_data,
                headers={'Content-Type': 'application/json'}
            )
            
            webhook_time = time.time() - start_time
            results["webhook_response_time"] = {
                "status_code": response.status_code,
                "response_time_ms": webhook_time * 1000,
                "response_data": response.get_data(as_text=True),
                "fast_response": webhook_time < 1.0  # Should be under 1 second
            }
    except Exception as e:
        results["webhook_response_time"] = {
            "status": "error",
            "error": str(e)
        }
    
    # Test background processing simulation
    try:
        processing_times = []
        
        for i in range(3):
            start_time = time.time()
            
            # Simulate background processing
            def background_task():
                time.sleep(0.1)  # Simulate processing time
                return "processed"
            
            thread = threading.Thread(target=background_task)
            thread.start()
            
            # Measure time to start thread (webhook response time)
            thread_start_time = time.time() - start_time
            processing_times.append(thread_start_time)
            
            thread.join()  # Wait for completion
        
        avg_start_time = sum(processing_times) / len(processing_times)
        results["background_processing_test"] = {
            "average_thread_start_time_ms": avg_start_time * 1000,
            "individual_times_ms": [t * 1000 for t in processing_times],
            "fast_startup": avg_start_time < 0.01  # Should be under 10ms
        }
    except Exception as e:
        results["background_processing_test"] = {
            "status": "error",
            "error": str(e)
        }
    
    return jsonify(results)

if __name__ == "__main__":
    print("🚀 Starting MedSense AI Bot...")
    print("🔧 Initializing services...")
    
    # Initialize services
    session_service = get_session_service()
    message_processor = get_message_processor()
    followup_service = get_followup_service()
    
    print("✅ Services initialized successfully")
    print("🌐 Bot is ready to receive messages")
    
    # Run the app
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
