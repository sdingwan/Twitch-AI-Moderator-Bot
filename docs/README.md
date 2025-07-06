# 🎤 Twitch AI Moderator Bot

A simple Twitch moderation bot that responds to voice commands using cloud-hosted Whisper Large V3.

## ✨ Features

- 🎤 **Voice Commands**: Say "Hey Brian" + your command
- 🚀 **Instant Moderation**: Ban, timeout, unban users with voice
- 🔍 **Smart Username Matching**: Phonetic matching for usernames with numbers/special characters
- 📝 **Chat Monitoring**: Automatically logs recent chat usernames for better matching
- ☁️ **Fast & Accurate**: Uses cloud-hosted Whisper Large V3 (no heavy local models)
- 📝 **Clean Logs**: No spam, just important information
- 🌐 **Web Interface**: Control the bot from your browser with a modern UI

## 🌐 Web Interface

The bot now includes a beautiful web interface that lets you control everything from your browser!


### Quick Start with Web Interface:
```bash
# Install dependencies (if not already done)
pip install -r requirements.txt

cd web && python3 main.py
```

Then open your browser to: **http://localhost:8000**

### Web Interface Usage:
1. **Configure**: Enter your Twitch channel name
2. **Start Bot**: Click "Start Bot" to connect to Twitch
3. **Voice Control**: Click "Start Voice Recognition" to enable voice commands
4. **Text Commands**: Use the text input to send commands without voice
5. **Monitor**: Watch the activity log for real-time feedback

**Both voice and text commands work simultaneously!**

## 🌤️ Weather Feature

The bot now includes a smart weather location feature that integrates with your existing `!weather` command:

- **Voice Control**: Say "Hey Brian, change weather to [location]" to update the weather location
- **Automatic Command**: The bot sends `!command edit !weather ${weather ${1:|"[location]"}}` to chat
- **Confirmation**: Shows a confirmation message when the location is updated
- **Seamless Integration**: Works with any existing weather bot setup

### Weather Commands:
- `"Hey Brian, change weather to Naples, Italy"`
- `"Hey Brian, set weather to Tokyo, Japan"`
- `"Hey Brian, weather location London, UK"`

## 🎯 Voice Commands

- `"Hey Brian, ban username123 for 10 minutes"`
- `"Hey Brian, timeout spammer for 5 minutes"`
- `"Hey Brian, unban username123"`
- `"Hey Brian, clear chat"`
- `"Hey Brian, slow mode 30"`
- `"Hey Brian, followers only mode"`
- `"Hey Brian, subscribers only mode"`
- `"Hey Brian, change weather to Naples, Italy"`
- `"Hey Brian, set weather to Tokyo, Japan"`

## 🤖 Smart AI Username Matching

The bot now includes advanced AI-powered matching to handle usernames with numbers and special characters:

**Examples:**
- Say `"Hey Brian, ban viking king"` → Matches `V1king_k1ng`
- Say `"Hey Brian, timeout roil navy"` → Matches `RoilNavy`
- Say `"Hey Brian, ban test user"` → Matches `TestUser123`

**How it works:**
- Monitors the last 50 chat messages automatically
- Uses OpenAI/ChatGPT to intelligently match spoken names to usernames
- Handles leet speak (1→i, 3→e, 4→a, etc.) and phonetic similarities
- Updates username log every 0.3 seconds
- Shows AI matches in real-time with 🤖 icon

## 🚀 Quick Start

### 1. Install
```bash
git clone https://github.com/yourusername/Twitch-AI-Moderator-Bot.git
cd Twitch-AI-Moderator-Bot
pip install -r requirements.txt
```

### 2. Configure
Copy the example configuration and edit it:
```bash
cp env.example .env
# Edit .env with your credentials
```

Your `.env` file should contain:
```env
# Twitch Settings
TWITCH_TOKEN=your_token_here
TWITCH_CLIENT_ID=your_client_id
TWITCH_CLIENT_SECRET=your_client_secret
TWITCH_CHANNEL=your_channel_name
TWITCH_BOT_USERNAME=your_bot_username

# OpenAI Settings (for command processing)
OPENAI_API_KEY=your_openai_api_key_here

# Hugging Face Settings (for voice recognition)
HF_API_TOKEN=your_huggingface_token_here
HF_ENDPOINT_URL=https://your-endpoint.endpoints.huggingface.cloud

# Voice Settings
VOICE_ACTIVATION_KEYWORD=hey brian
```

### 3. Deploy Whisper to the Cloud
**Option A: Hugging Face Inference Endpoints (Recommended)**
1. Go to [Hugging Face Inference Endpoints](https://ui.endpoints.huggingface.co/)
2. Create endpoint with `openai/whisper-large-v3`
3. Copy your endpoint URL and API token

**Option B: Other cloud providers**
See [DEPLOYMENT_GUIDE.md](DEPLOYMENT_GUIDE.md) for RunPod, Google Colab, and other options.

### 4. Get Your Twitch Credentials
1. Go to [Twitch Developer Console](https://dev.twitch.tv/console)
2. Create a new application
3. Get your Client ID and Client Secret
4. Generate an OAuth token with these scopes:
   - `channel:moderate`
   - `chat:edit`
   - `chat:read`

### 5. Run
```bash
cd web && python3 main.py
```

Then open your browser to: **http://localhost:8000**

## 📁 Project Structure

```
Twitch-AI-Moderator-Bot/
├── src/                    # Source code directory
│   ├── core/               # Core bot functionality
│   │   ├── config.py       # Configuration management
│   │   └── command_processor.py # Command parsing and validation
│   ├── platforms/          # Platform-specific integrations
│   │   └── twitch/         # Twitch-specific code
│   │       ├── twitch_api.py   # Twitch Helix API client
│   │       └── twitch_bot.py   # Twitch moderation logic
│   ├── voice/              # Voice recognition components
│   │   └── voice_recognition_hf.py # Voice processing with cloud-hosted Whisper Large V3
│   └── utils/              # Utility modules
│       └── twitch_username_logger.py # Twitch chat monitoring and phonetic username matching
├── web/                    # Web interface directory
│   ├── main.py            # Web application backend
│   └── frontend.html      # Static HTML frontend
├── docs/                   # Documentation
│   ├── README.md          # This file
│   └── QUICKSTART.md      # Quick start guide
├── chat_usernames.log      # Recent chat usernames (auto-generated)
└── requirements.txt        # Dependencies
```

## 🔧 Requirements

- Python 3.8+
- Microphone
- OpenAI API Key
- Twitch Developer Account

## 📝 Notes

- The bot uses cloud-hosted Whisper Large V3 for fast, accurate voice recognition
- Chat usernames are automatically monitored and logged for phonetic matching
- All moderation actions are logged to `moderator_bot.log`
- HTTP request logs are automatically suppressed for clean output
- Voice activation keyword can be customized in the `.env` file
- AI matching provides intelligent username resolution using ChatGPT
- Web interface provides both voice and text command options

## 🆘 Troubleshooting

**Bot not responding to voice?**
- Check your Hugging Face API token and endpoint URL
- Make sure your Twitch channel is live (the bot captures stream audio)
- Speak clearly and include "Hey Brian" before commands

**Username not being matched?**
- Make sure the user has chatted recently (last 50 messages)
- Try speaking the username more clearly
- Check `chat_usernames.log` to see logged usernames
- The bot shows AI matches in real-time with 🤖 icon
- AI matching is more flexible than phonetic algorithms

**Twitch commands failing?**
- Verify your OAuth token has the correct scopes
- Make sure the bot account has moderator permissions in your channel

**Web interface not loading?**
- Make sure you installed FastAPI: `pip install -r requirements.txt`
- Check if port 8000 is available
- Try accessing `http://127.0.0.1:8000` instead of localhost