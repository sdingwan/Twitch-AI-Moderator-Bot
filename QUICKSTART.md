# 🚀 Quick Start Guide

Get your Twitch AI Moderator Bot running in 5 minutes!

## 1. Install
```bash
git clone https://github.com/yourusername/Twitch-AI-Moderator-Bot.git
cd Twitch-AI-Moderator-Bot
pip install -r requirements.txt
```

## 2. Configure
```bash
cp env.example .env
# Edit .env with your credentials
```
```env
TWITCH_TOKEN=oauth:your_token_here
TWITCH_CLIENT_ID=your_client_id
TWITCH_CLIENT_SECRET=your_client_secret
TWITCH_CHANNEL=your_channel_name
TWITCH_BOT_USERNAME=your_bot_username
OPENAI_API_KEY=your_openai_api_key_here
HF_API_TOKEN=your_huggingface_token_here
HF_ENDPOINT_URL=https://your-endpoint.endpoints.huggingface.cloud
VOICE_ACTIVATION_KEYWORD=hey brian
```

## 3. Deploy Whisper to Cloud
1. Go to [Hugging Face Inference Endpoints](https://ui.endpoints.huggingface.co/)
2. Create endpoint with `openai/whisper-large-v3` 
3. Copy your API token and endpoint URL

## 4. Get Twitch Credentials
1. Go to [Twitch Developer Console](https://dev.twitch.tv/console)
2. Create new application → Get Client ID & Secret
3. Generate OAuth token with scopes: `channel:moderate`, `chat:edit`, `chat:read`

## 5. Test & Run
```bash
python main.py --test-mic    # Test microphone
python main.py              # Start bot
```

## 6. Use Voice Commands
Examples:
- `"Hey Brian, ban username123 for 10 minutes"`
- `"Hey Brian, unban username123"`
- `"Hey Brian, subscribers only mode"`
- `"Hey Brian, clear chat"`

That's it! 🎉 