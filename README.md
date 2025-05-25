# 🎤 AI Moderator Bot

A simple Twitch moderation bot that responds to voice commands using OpenAI Whisper API.

## ✨ Features

- 🎤 **Voice Commands**: Say "Hey Brian" + your command
- 🚀 **Instant Moderation**: Ban, timeout, unban users with voice
- ☁️ **Fast & Accurate**: Uses OpenAI Whisper API (no heavy local models)
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

# OpenAI Settings (required)
OPENAI_API_KEY=your_openai_api_key_here

# Voice Settings
VOICE_ACTIVATION_KEYWORD=hey brian
MICROPHONE_INDEX=-1
```

### 3. Get Your Twitch Credentials
1. Go to [Twitch Developer Console](https://dev.twitch.tv/console)
2. Create a new application
3. Get your Client ID and Client Secret
4. Generate an OAuth token with these scopes:
   - `channel:moderate`
   - `chat:edit`
   - `chat:read`

### 4. Run
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
├── voice_recognition.py # Voice processing with OpenAI Whisper
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

- The bot uses OpenAI's Whisper API for fast, accurate voice recognition
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
- Check your OpenAI API key
- Test with: `python main.py --test-mic`
- Speak clearly and include "Hey Brian" before commands

**Twitch commands failing?**
- Verify your OAuth token has the correct scopes
- Make sure the bot account has moderator permissions in your channel 