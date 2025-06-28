## 🩺 MedSense AI - Intelligent Medical Assistant Bot

This AI powered medical assistant helps user analyze their symptoms and to get a pretty accurate diagnosis. It will also provide a list of nearby clinics and pharmacies if the user wants to share their location. This is built with Google's Gemini 2.5 Flash, and it gives personalized medical answers wihle maintaing the user's privacy and encouraging professional medical care.

### 🌟 What Makes MedSense Special?

MedSense isn't just a chatbot, it's a very well designed helath companion that understands your medical needs. Whether you're dealing with a weird rash, feeling a bit weird, or you need to find the nearest clinic in an unfamiliar city, MedSense has got your back. 

### ✨ Key Features

**🧠 Smart Medical Analysis**  
Analyzes both text symptoms and medical images with confidence scoring, provides dual diagnoses (with/without medical history), and works in 50+ languages automatically.

**👤 Personalized Experience**  
Collects a bit of user information (like age and gender) for accurate analysis, maintains medical history, and includes keywords for session management. 

**📍 Location-Aware Healthcare**  
Finds nearby hospitals and clinics worldwide, provides Google Maps links, and uses free OpenStreetMap data.

**💬 Multi-Platform Support**  
Full WhatsApp Business and Telegram integration with seamless cross-platform experience. Whatsapp may not be fully functional yet as it requires approval from Meta which might take a few weeks.

**📊 Quality & Safety**  
User feedback system, detailed medical disclaimers, emergency handling, and secure data storage.

## 🚀 Quick Start

### Prerequisites
- Python 3.8+
- Google Gemini API key
- WhatsApp Business API access (optional)
- Telegram Bot Token (optional)

### Installation

1. **Clone and install**
   ```bash
   git clone https://github.com/yourusername/medsense-ai.git
   cd medsense-ai
   pip install -r requirements.txt
   ```

2. **Configure environment**
   
   Create `.env` file:
   ```env
   # Required
   GEMINI_API_KEY=your_gemini_api_key_here
   
   # Optional - WhatsApp
   WHATSAPP_TOKEN=your_token
   PHONE_NUMBER_ID=your_phone_id
   VERIFY_TOKEN=your_verify_token
   
   # Optional - Telegram
   TELEGRAM_BOT_TOKEN=your_telegram_token
   
   # Location Services
   NOMINATIM_USER_AGENT=MedSenseAI/1.0 (your_email@domain.com)
   ```

3. **Run the bot**
   ```bash
   python app.py
   ```

## 🔑 API Setup

**Google Gemini (Required)**: Get your API key from [Google AI Studio](https://aistudio.google.com/)

**WhatsApp (Optional)**: Set up through [Meta for Developers](https://developers.facebook.com/) with webhook `https://yourdomain.com/webhook`

**Telegram (Optional)**: Create bot via [@BotFather](https://t.me/botfather) with webhook `https://yourdomain.com/webhook/telegram`

## 💡 How It Works

**For Users**: Start conversation → Share basic info → Describe symptoms → Upload photos (optional) → Get AI analysis → Find nearby clinics → Provide feedback

**For Developers**: Session-based approach with information gathering and natural conversation flow.

## 🛠️ Commands

**General**: `help`, `history`, `clear`, `proceed`, `emergency`, `good`/`bad`

**Telegram**: `/start`, `/help`, `/history`, `/clear`, `/emergency`

## 📁 Structure

```
medsense-ai/
├── app.py                 # Main Flask application
├── requirements.txt       # Dependencies
├── .env                  # Environment variables
├── medsense_history.db   # Auto-created database
└── README.md            # Documentation
```

## ⚠️ Important Disclaimers

- **This is NOT a replacement for professional medical advice**
- **Always consult healthcare professionals for serious symptoms**
- **Contact emergency services immediately in cases of emergencies**
- **Provides insights only, not official diagnoses**

## 🤝 Contributing

We welcome contributions! Fork the repo, create a feature branch, commit changes, and open a pull request.

**Help needed with**: Error handling, performance, and security.

## 🐛 Known Issues

- Image analysis works best with clear, well-lit photos
- Long descriptions may get truncated
- Location accuracy varies in rural areas
- Some medical terms may not translate perfectly

## 📋 Roadmap

More messaging platforms, prescription reminders, health tracking, voice support, wearable integration, and appointment scheduling.

## 📄 License

MIT License - see [LICENSE](LICENSE) file for details.

## 🙏 Support

- 🐛 **Bug Reports**: GitHub Issues
- 💡 **Feature Requests**: GitHub Discussions
- 📧 **Questions**: GitHub Discussions

---

**Remember**: MedSense AI provides helpful insights but isn't a substitute for professional medical care. Always consult healthcare providers for proper diagnosis and treatment. Stay healthy! 🌟 
