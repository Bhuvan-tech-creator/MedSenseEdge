# MedSense AI - Refactored Application Structure

## Overview

This is a production-ready refactored version of the MedSense AI medical chatbot application. The original monolithic structure has been broken down into a modular, maintainable Flask application with proper separation of concerns.

## Project Structure

```
app/
├── __init__.py              # Flask app factory
├── config.py                # Configuration settings
├── models/                  # Database models and operations
│   ├── __init__.py
│   ├── database.py         # Database initialization
│   └── user.py             # User-related database operations
├── services/                # Business logic services
│   ├── __init__.py
│   ├── medical_analysis.py # Gemini AI medical analysis
│   ├── external_apis.py    # External API integrations
│   ├── message_service.py  # WhatsApp/Telegram messaging
│   ├── message_processor.py # Message processing orchestration
│   └── session_service.py  # User session management
├── routes/                  # Flask route blueprints
│   ├── __init__.py
│   ├── health.py           # Health check routes
│   ├── whatsapp.py         # WhatsApp webhook routes
│   └── telegram.py         # Telegram webhook routes
└── utils/                   # Utility functions
    ├── __init__.py
    ├── constants.py        # Constants and messages
    └── helpers.py          # Helper utility functions
main.py                     # Application entry point
```

## Key Features

### Architecture Benefits
- **Modular Design**: Clear separation of concerns with dedicated modules
- **Service Layer**: Business logic isolated in service classes
- **Blueprint Structure**: Routes organized by functionality
- **Configuration Management**: Centralized configuration handling
- **Error Handling**: Improved error handling and logging

### Medical Analysis Pipeline
1. **Multi-modal Input**: Text, images, and location data
2. **Gemini AI Integration**: Advanced medical analysis using Google's Gemini 2.5 Flash
3. **EndlessMedical Validation**: Secondary validation using medical database
4. **Profile-Aware Analysis**: Age and gender considerations
5. **Medical History**: Context from previous consultations
6. **Language Detection**: Responds in user's native language

### Platform Support
- **WhatsApp Business API**: Complete webhook integration
- **Telegram Bot API**: Full bot functionality
- **Cross-platform Sessions**: Unified user experience

### Additional Services
- **Disease Outbreak Alerts**: WHO API integration
- **Clinic Finder**: OpenStreetMap integration for nearby medical facilities
- **User Profiles**: Age, gender, and medical history tracking
- **Feedback System**: Diagnosis quality tracking

## Installation

1. **Clone the repository**
   ```bash
   git clone <repository-url>
   cd MedSenseEdge
   ```

2. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

3. **Environment Variables**
   Create a `.env` file with:
   ```env
   # WhatsApp API
   WHATSAPP_TOKEN=your_whatsapp_token
   PHONE_NUMBER_ID=your_phone_number_id
   VERIFY_TOKEN=your_verify_token
   
   # Telegram API
   TELEGRAM_BOT_TOKEN=your_telegram_bot_token
   
   # Google Gemini API
   GEMINI_API_KEY=your_gemini_api_key
   
   # Optional configurations
   NOMINATIM_USER_AGENT=MedSenseAI/1.0
   SECRET_KEY=your-secret-key-here
   ```

## Running the Application

### Local Development
```bash
python main.py
```

### Production Deployment
The application is configured for deployment on platforms like Render, Heroku, etc.

```bash
# Production configuration is handled via environment variables
# Set PORT environment variable for cloud platforms
export PORT=5000
python main.py
```

## API Endpoints

### Health Checks
- `GET /` - Main health check
- `GET /test-telegram` - Test Telegram configuration
- `GET /set-webhook/<webhook_url>` - Set Telegram webhook

### Webhooks
- `POST /webhook` - WhatsApp webhook
- `POST /webhook/telegram` - Telegram webhook

## Usage

### WhatsApp Integration
1. Configure WhatsApp Business API credentials
2. Set webhook URL to `https://your-domain.com/webhook`
3. Users can start chatting by sending messages

### Telegram Integration
1. Create a Telegram bot via @BotFather
2. Set webhook URL to `https://your-domain.com/webhook/telegram`
3. Users start with `/start` command

### User Commands
- `help` - Show help message
- `history` - View medical history
- `clear` - Clear current session
- `proceed` - Process current symptoms
- `emergency` - Emergency message
- `good`/`bad` - Provide feedback on diagnosis

## Development

### Adding New Features
1. **New Service**: Add to `app/services/`
2. **New Route**: Add blueprint to `app/routes/`
3. **New Model**: Add to `app/models/`
4. **Configuration**: Update `app/config.py`

### Database Schema
The application uses SQLite with the following tables:
- `user_profiles` - User age, gender, platform
- `symptom_history` - Medical consultations and diagnoses
- `user_locations` - Location data for clinic recommendations
- `user_countries` - Country data for disease outbreak alerts
- `diagnosis_feedback` - User feedback on diagnoses
- `disease_notifications` - Disease outbreak notifications

### Testing
```bash
# Test Telegram integration
curl https://your-domain.com/test-telegram

# Test health check
curl https://your-domain.com/
```

## Migration from Original Structure

The original `app.py` (675 lines) and `medical_services.py` (875 lines) have been refactored into:
- 13 focused modules
- Clear separation of concerns
- Improved testability
- Better error handling
- Enhanced maintainability

## Performance Considerations

- **Lazy Loading**: Services are loaded on-demand
- **Session Management**: Automatic cleanup of inactive sessions
- **Connection Pooling**: Efficient database connection handling
- **Caching**: User sessions cached in memory
- **Rate Limiting**: Built-in rate limiting for external APIs

## Security Features

- **Input Validation**: All user inputs validated
- **SSL Verification**: Configurable SSL settings
- **Token Management**: Secure API token handling
- **Error Masking**: Sensitive errors not exposed to users

## Monitoring and Logging

- **Startup Diagnostics**: Configuration validation on startup
- **Error Logging**: Comprehensive error logging
- **Health Checks**: Multiple health check endpoints
- **API Status**: External API connectivity monitoring

This refactored structure provides a solid foundation for future development while maintaining all existing functionality from the original monolithic application. 