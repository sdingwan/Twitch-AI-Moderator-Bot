# 🚀 Multi-Platform AI Moderator Bot - Quick Start

## 🎯 What's New

Your AI Moderator Bot now supports **both Twitch and Kick.com** simultaneously! 

## ⚡ Quick Setup

### 1. Update Your .env File
```bash
# Add Kick credentials
KICK_CLIENT_ID=your_kick_client_id
KICK_CLIENT_SECRET=your_kick_client_secret

# Choose platforms: 'twitch', 'kick', or 'twitch,kick'
ENABLED_PLATFORMS=twitch,kick
```

### 2. Start the Bot
```bash
cd web && python main.py
```

### 3. Configure in Web Interface
```json
{
  "platforms": ["twitch", "kick"],
  "twitch_channel": "your_twitch_channel", 
  "kick_channel": "your_kick_channel"
}
```

## 🎤 Voice Commands (Work on Both Platforms!)
```
"Hey Brian, ban toxic_user"
"Hey Brian, timeout spammer for 600 seconds" 
"Hey Brian, unban reformed_user"
```

## 🔧 Supported Features

| Feature | Twitch | Kick |
|---------|--------|------|
| Ban/Unban | ✅ | ✅ |
| Timeout/Untimeout | ✅ | ✅ |
| Chat Settings | ✅ | ❌ |

## 📋 Platform Options

- **Twitch Only**: `"platforms": ["twitch"]`
- **Kick Only**: `"platforms": ["kick"]` 
- **Both**: `"platforms": ["twitch", "kick"]`

Commands execute on all enabled platforms simultaneously!

## 🔗 Get Kick API Keys
1. Visit [kick.com/settings/developer](https://kick.com/settings/developer)
2. Create new app with redirect: `http://localhost:8000/auth/kick/callback`
3. Copy Client ID & Secret

That's it! Your bot now moderates multiple platforms with unified voice commands! 🎉 