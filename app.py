"""
MedSense AI - Medical Chatbot Application
Refactored but maintains exact same functionality and launch behavior as original
"""
from flask import Flask, request, jsonify, current_app
import os
import threading
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

app = Flask(__name__)
app.config.from_object(Config)
init_database()

session_service = get_session_service()
message_processor = get_message_processor()

# Message deduplication for WhatsApp webhooks
processed_messages = {}

# Message deduplication for Telegram webhooks (NEW)
processed_telegram_messages = {}

def clean_old_messages():
    """Clean messages older than 5 minutes"""
    cutoff = datetime.now() - timedelta(minutes=5)
    # Clean WhatsApp messages
    to_remove = [msg_id for msg_id, timestamp in processed_messages.items() if timestamp < cutoff]
    for msg_id in to_remove:
        del processed_messages[msg_id]
    
    # Clean Telegram messages (NEW)
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

@app.route("/webhook", methods=["GET", "POST"])
def whatsapp_webhook():
    """WhatsApp webhook endpoint with enhanced debugging and performance optimizations"""
    start_time = datetime.now()
    session_service.clear_inactive_sessions()
    
    if request.method == "GET":
        challenge = request.args.get("hub.challenge")
        verify_token = app.config.get('VERIFY_TOKEN')
        if (request.args.get("hub.mode") == "subscribe" and 
            request.args.get("hub.verify_token") == verify_token):
            return challenge if challenge else "", 200
        return "Verification failed", 403
    
    try:
        data = request.get_json()
        entry = data['entry'][0]['changes'][0]['value']
        messages = entry.get('messages', [])
        if not messages:
            print(f"⚠️ WHATSAPP: No messages in data, returning OK")
            return "OK", 200
        
        msg = messages[0]
        sender = msg['from']
        
        print(f"📨 WHATSAPP: Received message from {sender} at {start_time.strftime('%H:%M:%S.%f')}")
        
        # Check for duplicate messages using WhatsApp message ID
        message_id = msg.get('id')
        if message_id and is_duplicate_message(message_id):
            print(f"⚠️ WHATSAPP: Skipping duplicate message {message_id} from {sender}")
            return "OK", 200
            
        session_service.update_session_activity(sender)
        print(f"🔄 WHATSAPP: Session updated for {sender} at {(datetime.now() - start_time).total_seconds():.3f}s")
        
        # OPTIMIZED: Quick check for profile setup (minimize blocking)
        should_send_processing_msg = True
        try:
            # Do a quick, non-blocking check first
            if session_service.is_in_profile_setup(sender):
                should_send_processing_msg = False
                print(f"👤 WHATSAPP: User {sender} is in profile setup")
            else:
                # Only check if new user if not already in setup
                # This will be double-checked in background thread
                print(f"✅ WHATSAPP: User {sender} not in profile setup, allowing processing message")
        except Exception as e:
            print(f"⚠️ WHATSAPP: Error checking profile setup: {e}")
            # Default to sending processing message if check fails
        
        print(f"🚀 WHATSAPP: Starting background processing for {sender} at {(datetime.now() - start_time).total_seconds():.3f}s")
        
        # Process message in background to prevent webhook timeout
        def process_message():
            bg_start = datetime.now()
            print(f"🔄 WHATSAPP BG: Background processing started for {sender}")
            try:
                if 'text' in msg:
                    body = msg['text']['body']
                    
                    print(f"📝 WHATSAPP BG: Processing text message: '{body[:50]}...'")
                    
                    # Send immediate processing message FIRST (before any blocking operations)
                    if should_send_processing_msg and not body.lower().startswith(('/start', 'start', 'history', 'clear', 'help')):
                        print(f"⚡ WHATSAPP BG: Sending immediate processing message to {sender}")
                        processing_sent = send_whatsapp_message(sender, PROCESSING_TEXT_MSG)
                        if processing_sent:
                            print(f"✅ WHATSAPP BG: Processing message sent successfully to {sender}")
                        else:
                            print(f"❌ WHATSAPP BG: Failed to send processing message to {sender}")
                    
                    # Now do the actual processing
                    response = message_processor.handle_text_message(sender, body, "whatsapp")
                    if response:
                        print(f"📤 WHATSAPP BG: Sending response to {sender} (length: {len(response)} chars)")
                        final_sent = send_whatsapp_message(sender, response)
                        if final_sent:
                            print(f"✅ WHATSAPP BG: Final response sent to {sender}")
                        else:
                            print(f"❌ WHATSAPP BG: Failed to send final response to {sender}")
                    else:
                        print(f"⚠️ WHATSAPP BG: No response generated for {sender}")
                        
                elif 'image' in msg:
                    media_id = msg['image']['id']
                    caption_text = msg['image'].get('caption', None)
                    
                    print(f"🖼️ WHATSAPP BG: Processing image message (media_id: {media_id[:20]}...)")
                    
                    # Send immediate processing message
                    if should_send_processing_msg:
                        print(f"⚡ WHATSAPP BG: Sending immediate image processing message to {sender}")
                        send_whatsapp_message(sender, PROCESSING_IMAGE_MSG)
                    
                    image_url = get_whatsapp_image_url(media_id)
                    if image_url:
                        image_base64 = download_and_encode_whatsapp_image(image_url)
                        if image_base64:
                            response = message_processor.handle_image_message(sender, image_base64, "whatsapp", caption_text)
                            if response:
                                send_whatsapp_message(sender, response)
                        else:
                            send_whatsapp_message(sender, IMAGE_ERROR_MSG)
                    else:
                        send_whatsapp_message(sender, IMAGE_ERROR_MSG)
                        
                elif 'location' in msg:
                    latitude = msg['location']['latitude']
                    longitude = msg['location']['longitude']
                    
                    print(f"📍 WHATSAPP BG: Processing location message (lat: {latitude}, lon: {longitude})")
                    
                    # Send immediate processing message
                    if should_send_processing_msg:
                        print(f"⚡ WHATSAPP BG: Sending immediate location processing message to {sender}")
                        send_whatsapp_message(sender, PROCESSING_LOCATION_MSG)
                    
                    response = message_processor.handle_location_message(sender, latitude, longitude, "whatsapp")
                    if response:
                        send_whatsapp_message(sender, response)
                        
                processing_time = (datetime.now() - bg_start).total_seconds()
                print(f"✅ WHATSAPP BG: Background processing completed for {sender} in {processing_time:.3f}s")
                
            except Exception as e:
                print(f"❌ WHATSAPP BG: Background processing error for {sender}: {e}")
                # Send error message to user
                try:
                    send_whatsapp_message(sender, "I encountered a technical issue. Please try again or consult a healthcare professional if urgent.")
                except:
                    pass
        
        # Start background processing
        threading.Thread(target=process_message, daemon=True).start()
        
        webhook_time = (datetime.now() - start_time).total_seconds()
        print(f"🏁 WHATSAPP: Webhook completed for {sender} in {webhook_time:.3f}s")
        
    except Exception as e:
        error_time = (datetime.now() - start_time).total_seconds()
        print(f"❌ WHATSAPP: Webhook error after {error_time:.3f}s: {e}")
    
    # Always return OK immediately to prevent retries
    return "OK", 200

@app.route("/webhook/telegram", methods=["POST"])
def telegram_webhook():
    """Telegram webhook endpoint with enhanced debugging and performance optimizations"""
    start_time = datetime.now()
    session_service.clear_inactive_sessions()
    
    try:
        data = request.get_json()
        if "message" not in data:
            print(f"⚠️ TELEGRAM: No message in data, returning OK")
            return "OK", 200
        
        msg = data["message"]
        chat_id = str(msg.get("chat", {}).get("id", ""))
        if not chat_id:
            print(f"❌ TELEGRAM: No chat_id found")
            return "No chat_id", 400
        
        print(f"📨 TELEGRAM: Received message from {chat_id} at {start_time.strftime('%H:%M:%S.%f')}")
        
        # Check for duplicate messages using Telegram message ID
        message_id = msg.get('message_id')
        if message_id and is_duplicate_telegram_message(f"{chat_id}_{message_id}"):
            print(f"⚠️ TELEGRAM: Skipping duplicate message {message_id} from {chat_id}")
            return "OK", 200
        
        session_service.update_session_activity(chat_id)
        print(f"🔄 TELEGRAM: Session updated for {chat_id} at {(datetime.now() - start_time).total_seconds():.3f}s")
        
        # OPTIMIZED: Quick check for profile setup (minimize blocking)
        should_send_processing_msg = True
        try:
            # Do a quick, non-blocking check first
            if session_service.is_in_profile_setup(chat_id):
                should_send_processing_msg = False
                print(f"👤 TELEGRAM: User {chat_id} is in profile setup")
            else:
                # Only check if new user if not already in setup
                # This will be double-checked in background thread
                print(f"✅ TELEGRAM: User {chat_id} not in profile setup, allowing processing message")
        except Exception as e:
            print(f"⚠️ TELEGRAM: Error checking profile setup: {e}")
            # Default to sending processing message if check fails
        
        print(f"🚀 TELEGRAM: Starting background processing for {chat_id} at {(datetime.now() - start_time).total_seconds():.3f}s")
        
        # Process message in background to prevent webhook timeout
        def process_message():
            bg_start = datetime.now()
            print(f"🔄 TELEGRAM BG: Background processing started for {chat_id}")
            try:
                if "text" in msg:
                    text = msg["text"]
                    if text.startswith("/start"):
                        text = "start"
                    elif text.startswith("/"):
                        text = text[1:]
                    
                    print(f"📝 TELEGRAM BG: Processing text message: '{text[:50]}...'")
                    
                    # Send immediate processing message FIRST (before any blocking operations)
                    if should_send_processing_msg and not text.lower().startswith(('start', 'history', 'clear', 'help')):
                        print(f"⚡ TELEGRAM BG: Sending immediate processing message to {chat_id}")
                        processing_sent = send_telegram_message(chat_id, PROCESSING_TEXT_MSG)
                        if processing_sent:
                            print(f"✅ TELEGRAM BG: Processing message sent successfully to {chat_id}")
                        else:
                            print(f"❌ TELEGRAM BG: Failed to send processing message to {chat_id}")
                    
                    # Now do the actual processing
                    response = message_processor.handle_text_message(chat_id, text, "telegram")
                    if response:
                        print(f"📤 TELEGRAM BG: Sending response to {chat_id} (length: {len(response)} chars)")
                        final_sent = send_telegram_message(chat_id, response)
                        if final_sent:
                            print(f"✅ TELEGRAM BG: Final response sent to {chat_id}")
                        else:
                            print(f"❌ TELEGRAM BG: Failed to send final response to {chat_id}")
                    else:
                        print(f"⚠️ TELEGRAM BG: No response generated for {chat_id}")
                        
                elif "photo" in msg:
                    photos = msg["photo"]
                    file_id = photos[-1]["file_id"]
                    caption_text = msg.get('caption', None)
                    
                    print(f"🖼️ TELEGRAM BG: Processing photo message (file_id: {file_id[:20]}...)")
                    
                    # Send immediate processing message
                    if should_send_processing_msg:
                        print(f"⚡ TELEGRAM BG: Sending immediate image processing message to {chat_id}")
                        send_telegram_message(chat_id, PROCESSING_IMAGE_MSG)
                    
                    file_path = get_telegram_file_path(file_id)
                    if file_path:
                        telegram_token = app.config.get('TELEGRAM_BOT_TOKEN')
                        file_url = f"https://api.telegram.org/file/bot{telegram_token}/{file_path}"
                        image_base64 = download_telegram_image(file_url)
                        if image_base64:
                            response = message_processor.handle_image_message(chat_id, image_base64, "telegram", caption_text)
                            if response:
                                send_telegram_message(chat_id, response)
                        else:
                            send_telegram_message(chat_id, IMAGE_ERROR_MSG)
                    else:
                        send_telegram_message(chat_id, IMAGE_ERROR_MSG)
                        
                elif "location" in msg:
                    latitude = msg["location"]["latitude"]
                    longitude = msg["location"]["longitude"]
                    
                    print(f"📍 TELEGRAM BG: Processing location message (lat: {latitude}, lon: {longitude})")
                    
                    # Send immediate processing message
                    if should_send_processing_msg:
                        print(f"⚡ TELEGRAM BG: Sending immediate location processing message to {chat_id}")
                        send_telegram_message(chat_id, PROCESSING_LOCATION_MSG)
                    
                    response = message_processor.handle_location_message(chat_id, latitude, longitude, "telegram")
                    if response:
                        send_telegram_message(chat_id, response)
                        
                processing_time = (datetime.now() - bg_start).total_seconds()
                print(f"✅ TELEGRAM BG: Background processing completed for {chat_id} in {processing_time:.3f}s")
                
            except Exception as e:
                print(f"❌ TELEGRAM BG: Background processing error for {chat_id}: {e}")
                # Send error message to user
                try:
                    send_telegram_message(chat_id, "I encountered a technical issue. Please try again or consult a healthcare professional if urgent.")
                except:
                    pass
        
        # Start background processing
        threading.Thread(target=process_message, daemon=True).start()
        
        webhook_time = (datetime.now() - start_time).total_seconds()
        print(f"🏁 TELEGRAM: Webhook completed for {chat_id} in {webhook_time:.3f}s")
        
        return "OK", 200
    except Exception as e:
        error_time = (datetime.now() - start_time).total_seconds()
        print(f"❌ TELEGRAM: Webhook error for {chat_id if 'chat_id' in locals() else 'unknown'} after {error_time:.3f}s: {e}")
        return "OK", 200  # Still return OK to prevent retries

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
    first_dup_check = processor._is_duplicate_request(test_user, "text", test_message)
    second_dup_check = processor._is_duplicate_request(test_user, "text", test_message)
    results["message_processor_deduplication"] = {
        "first_check": first_dup_check[0],  # is_duplicate
        "second_check": second_dup_check[0],  # is_duplicate  
        "working": not first_dup_check[0] and second_dup_check[0]
    }
    
    # Test message sending deduplication (would need actual tokens to test fully)
    results["message_sending_deduplication"] = {
        "info": "Message sending deduplication active - prevents identical messages within 2 minutes",
        "hash_system": "Uses MD5 hash of recipient + message content for deduplication"
    }
    
    return jsonify({
        "status": "Duplicate Prevention Test Results",
        "timestamp": datetime.now().isoformat(),
        "results": results,
        "summary": {
            "webhook_protection": results["webhook_deduplication"]["whatsapp"]["working"] and results["webhook_deduplication"]["telegram"]["working"],
            "processor_protection": results["message_processor_deduplication"]["working"],
            "all_systems_working": all([
                results["webhook_deduplication"]["whatsapp"]["working"],
                results["webhook_deduplication"]["telegram"]["working"], 
                results["message_processor_deduplication"]["working"]
            ])
        }
    })

@app.route("/test-async-fix", methods=["GET"])
def test_async_fix():
    """Test endpoint to verify async/sync fixes are working"""
    from services.message_processor import get_message_processor
    import time
    
    test_results = {
        "timestamp": datetime.now().isoformat(),
        "tests": {}
    }
    
    try:
        # Test 1: Simple message processor instantiation
        start_time = time.time()
        processor = get_message_processor()
        test_results["tests"]["processor_creation"] = {
            "status": "success",
            "time_ms": round((time.time() - start_time) * 1000, 2)
        }
    except Exception as e:
        test_results["tests"]["processor_creation"] = {
            "status": "failed",
            "error": str(e)
        }
    
    try:
        # Test 2: Medical agent system instantiation
        start_time = time.time()
        from services.medical_agent import get_medical_agent_system
        agent = get_medical_agent_system()
        test_results["tests"]["agent_creation"] = {
            "status": "success",
            "time_ms": round((time.time() - start_time) * 1000, 2)
        }
    except Exception as e:
        test_results["tests"]["agent_creation"] = {
            "status": "failed",
            "error": str(e)
        }
    
    try:
        # Test 3: Async analysis simulation (without actually running it)
        processor = get_message_processor()
        test_hash = processor._generate_request_hash("test_user", "text", "test message")
        test_results["tests"]["hash_generation"] = {
            "status": "success",
            "hash": test_hash[:8] + "...",
            "full_length": len(test_hash)
        }
    except Exception as e:
        test_results["tests"]["hash_generation"] = {
            "status": "failed",
            "error": str(e)
        }
    
    try:
        # Test 4: Flask app context availability - NEW TEST
        app_available = current_app is not None
        config_accessible = current_app.config.get('GEMINI_API_KEY') is not None if app_available else False
        test_results["tests"]["flask_context"] = {
            "status": "success",
            "app_available": app_available,
            "config_accessible": config_accessible,
            "context_type": str(type(current_app)) if app_available else "None"
        }
    except Exception as e:
        test_results["tests"]["flask_context"] = {
            "status": "failed",
            "error": str(e)
        }
    
    try:
        # Test 5: Background thread simulation - NEW TEST
        import threading
        context_test_result = {"success": False, "error": None}
        
        def test_context_in_thread():
            try:
                # Capture app context like message processor does
                app_context = current_app._get_current_object() if current_app else None
                if app_context:
                    with app_context.app_context():
                        # Test if we can access config
                        api_key = current_app.config.get('GEMINI_API_KEY')
                        context_test_result["success"] = True
                        context_test_result["api_key_accessible"] = api_key is not None
                else:
                    context_test_result["error"] = "No app context captured"
            except Exception as e:
                context_test_result["error"] = str(e)
        
        thread = threading.Thread(target=test_context_in_thread)
        thread.start()
        thread.join(timeout=5)  # Wait max 5 seconds
        
        test_results["tests"]["background_thread_context"] = {
            "status": "success" if context_test_result["success"] else "failed",
            "context_accessible": context_test_result["success"],
            "api_key_accessible": context_test_result.get("api_key_accessible", False),
            "error": context_test_result.get("error")
        }
    except Exception as e:
        test_results["tests"]["background_thread_context"] = {
            "status": "failed",
            "error": str(e)
        }
    
    # Overall status
    all_passed = all(test.get("status") == "success" for test in test_results["tests"].values())
    test_results["overall_status"] = "all_tests_passed" if all_passed else "some_tests_failed"
    test_results["message"] = "Flask context fixes working properly" if all_passed else "Some issues detected"
    test_results["flask_context_fix"] = "✅ Implemented" if test_results["tests"].get("background_thread_context", {}).get("context_accessible") else "❌ Issues detected"
    
    return jsonify(test_results)

@app.route("/test-webhook-performance", methods=["GET"])
def test_webhook_performance():
    """Test webhook performance and deadlock fixes"""
    from services.session_service import get_session_service
    from models.user import is_new_user, get_user_profile, get_user_history
    import time
    
    test_results = {
        "timestamp": datetime.now().isoformat(),
        "deadlock_fix": {},
        "performance_tests": {},
        "database_operations": {}
    }
    
    test_user = "test_deadlock_user_123"
    
    try:
        # Test 1: Deadlock fix - nested lock calls
        start_time = time.time()
        session_service = get_session_service()
        
        # This previously caused deadlock
        result1 = session_service.should_start_profile_setup(test_user)
        result2 = session_service.is_in_profile_setup(test_user)
        
        test_results["deadlock_fix"] = {
            "status": "success",
            "should_start_profile_setup": result1,
            "is_in_profile_setup": result2,
            "time_ms": round((time.time() - start_time) * 1000, 2),
            "rlock_working": True
        }
    except Exception as e:
        test_results["deadlock_fix"] = {
            "status": "failed",
            "error": str(e),
            "rlock_working": False
        }
    
    try:
        # Test 2: Database operation performance
        start_time = time.time()
        
        # Test is_new_user function (which makes 2 DB calls)
        is_new = is_new_user(test_user)
        db_time = time.time() - start_time
        
        # Test individual operations
        start_time = time.time()
        profile = get_user_profile(test_user)
        profile_time = time.time() - start_time
        
        start_time = time.time()
        history = get_user_history(test_user)
        history_time = time.time() - start_time
        
        test_results["database_operations"] = {
            "status": "success",
            "is_new_user_time_ms": round(db_time * 1000, 2),
            "get_user_profile_time_ms": round(profile_time * 1000, 2),
            "get_user_history_time_ms": round(history_time * 1000, 2),
            "is_new_user_result": is_new,
            "profile_exists": profile is not None,
            "history_count": len(history) if history else 0
        }
    except Exception as e:
        test_results["database_operations"] = {
            "status": "failed",
            "error": str(e)
        }
    
    try:
        # Test 3: Webhook processing simulation
        start_time = time.time()
        
        # Simulate webhook processing steps
        step1_time = time.time()
        session_service.update_session_activity(test_user)
        step1_elapsed = time.time() - step1_time
        
        step2_time = time.time()
        should_send = not session_service.is_in_profile_setup(test_user)
        step2_elapsed = time.time() - step2_time
        
        total_webhook_time = time.time() - start_time
        
        test_results["performance_tests"] = {
            "status": "success",
            "session_update_time_ms": round(step1_elapsed * 1000, 2),
            "profile_check_time_ms": round(step2_elapsed * 1000, 2),
            "total_webhook_simulation_ms": round(total_webhook_time * 1000, 2),
            "should_send_processing_msg": should_send,
            "performance_acceptable": total_webhook_time < 0.1  # Should be under 100ms
        }
    except Exception as e:
        test_results["performance_tests"] = {
            "status": "failed",
            "error": str(e)
        }
    
    # Overall assessment
    all_passed = all(
        test.get("status") == "success" 
        for test in [
            test_results["deadlock_fix"], 
            test_results["database_operations"], 
            test_results["performance_tests"]
        ]
    )
    
    test_results["overall_status"] = "all_tests_passed" if all_passed else "some_tests_failed"
    test_results["deadlock_fixed"] = test_results["deadlock_fix"].get("rlock_working", False)
    test_results["performance_good"] = test_results["performance_tests"].get("performance_acceptable", False)
    test_results["summary"] = {
        "deadlock_issue": "✅ Fixed with RLock" if test_results["deadlock_fix"].get("rlock_working") else "❌ Still present",
        "webhook_performance": f"✅ Fast ({test_results['performance_tests'].get('total_webhook_simulation_ms', 0)}ms)" if test_results["performance_tests"].get("performance_acceptable") else "⚠️ Slow",
        "database_performance": f"✅ DB operations working" if test_results["database_operations"].get("status") == "success" else "❌ DB issues"
    }
    
    return jsonify(test_results)

if __name__ == "__main__":
    print("🚀 Starting MedSense AI Bot...")
    followup_service = get_followup_service()
    followup_service.start_scheduler()
    print("✅ 24-hour follow-up scheduler initialized")
    if app.config.get('TELEGRAM_BOT_TOKEN'):
        token_works = test_telegram_token()
        if token_works:
            print("✅ Telegram token is valid")
            webhook_info = get_telegram_webhook_info()
            if webhook_info and webhook_info.get('url'):
                print(f"✅ Telegram webhook configured: {webhook_info.get('url')}")
            else:
                print("⚠️ Telegram webhook not configured")
        else:
            print("❌ Telegram token is invalid or bot is not working")
    else:
        print("❌ TELEGRAM_BOT_TOKEN not found in environment variables")
    if app.config.get('WHATSAPP_TOKEN'):
        print("✅ WhatsApp token configured")
    else:
        print("⚠️ WhatsApp token not configured")
    if app.config.get('GEMINI_API_KEY'):
        print("✅ Gemini API key configured")
    else:
        print("❌ Gemini API key not configured")
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
