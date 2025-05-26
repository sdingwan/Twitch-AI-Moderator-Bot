# 🎤 AI Moderator Bot

A simple Twitch moderation bot that responds to voice commands using cloud-hosted Whisper Large V3.

## ✨ Features

- 🎤 **Voice Commands**: Say "Hey Brian" + your command
- 🚀 **Instant Moderation**: Ban, timeout, unban users with voice
- ☁️ **Fast & Accurate**: Uses cloud-hosted Whisper Large V3 (no heavy local models)
- 📝 **Clean Logs**: No spam, just important information

## 🎯 Voice Commands

- `"Hey Brian, ban username123 for 10 minutes"`
- `"Hey Brian, timeout spammer for 5 minutes"`
- `"Hey Brian, unban username123"`
- `"Hey Brian, clear chat"`
- `"Hey Brian, slow mode 30"`

## 🚀 Quick Start

### 1. Install
```bash
git clone https://github.com/yourusername/AI-Moderator-Bot.git
cd AI-Moderator-Bot
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
TWITCH_TOKEN=oauth:your_token_here
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
MICROPHONE_INDEX=-1
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
python main.py
```

## 🛠️ Commands

```bash
python main.py              # Start the bot
python main.py --test-mic   # Test your microphone
python main.py --list-mics  # List available microphones
python main.py --help       # Show help
```

## 📁 Project Structure

```
AI-Moderator-Bot/
├── main.py              # Main bot application
├── voice_recognition_hf.py # Voice processing with cloud-hosted Whisper Large V3
├── command_processor.py # Command parsing and validation
├── twitch_api.py        # Twitch Helix API client
├── twitch_bot.py        # Twitch moderation logic
├── config.py            # Configuration management
└── requirements.txt     # Dependencies
```

## 🔧 Requirements

- Python 3.8+
- Microphone
- OpenAI API Key
- Twitch Developer Account

## 📝 Notes

- The bot uses cloud-hosted Whisper Large V3 for fast, accurate voice recognition
- All moderation actions are logged to `moderator_bot.log`
- HTTP request logs are automatically suppressed for clean output
- Voice activation keyword can be customized in the `.env` file

## 🆘 Troubleshooting

**Microphone not working?**
```bash
python main.py --list-mics  # Find your microphone index
# Update MICROPHONE_INDEX in .env file
```

**Bot not responding to voice?**
- Check your Hugging Face API token and endpoint URL
- Test with: `python main.py --test-mic`
- Speak clearly and include "Hey Brian" before commands

**Twitch commands failing?**
- Verify your OAuth token has the correct scopes
- Make sure the bot account has moderator permissions in your channel 