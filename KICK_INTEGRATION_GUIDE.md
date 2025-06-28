# 🤖 Multi-Platform AI Moderator Bot - Kick.com Integration Guide

## 📋 Overview

Your AI Moderator Bot now supports both **Twitch** and **Kick.com** platforms! You can run the bot on one platform, both simultaneously, or switch between them as needed.

## 🚀 Supported Features

### ✅ Kick.com Features
- **Ban** users permanently
- **Timeout** users (with duration in seconds)
- **Unban** users (removes permanent bans)
- **Untimeout** users (removes timeouts)
- **Real-time chat monitoring** via Pusher WebSocket
- **OAuth 2.1 authentication** with automatic token refresh
- **Cross-platform username resolution**

### ⚠️ Platform Limitations
| Feature | Twitch | Kick |
|---------|--------|------|
| Ban/Unban | ✅ | ✅ |
| Timeout/Untimeout | ✅ | ✅ |
| Slow Mode | ✅ | ❌ |
| Follower-only Mode | ✅ | ❌ |
| Subscriber-only Mode | ✅ | ❌ |
| Emote-only Mode | ✅ | ❌ |
| Clear Chat | ✅ | ❌ |

## 🔧 Setup Instructions

### 1. Get Kick.com API Credentials

1. Go to [kick.com/settings/developer](https://kick.com/settings/developer)
2. Create a new application
3. Set the redirect URI to: `http://localhost:8000/auth/kick/callback`
4. Copy your **Client ID** and **Client Secret**

### 2. Update Environment Variables

Add these to your `.env` file:

```bash
# Kick.com Configuration
KICK_CLIENT_ID=your_kick_client_id_here
KICK_CLIENT_SECRET=your_kick_client_secret_here
KICK_REDIRECT_URI=http://localhost:8000/auth/kick/callback

# Multi-Platform Configuration
ENABLED_PLATFORMS=twitch,kick  # or just 'kick' or 'twitch'
```

### 3. OAuth Authentication

The bot uses **OAuth 2.1** for secure authentication:

1. Start the bot web interface
2. Configure Kick channel in the web interface
3. The system will guide you through OAuth authentication
4. Access tokens are automatically refreshed

## 🎮 Usage Examples

### Option A: Twitch Only
```json
{
  "platforms": ["twitch"],
  "twitch_channel": "your_twitch_channel"
}
```

### Option B: Kick Only
```json
{
  "platforms": ["kick"],
  "kick_channel": "your_kick_channel"
}
```

### Option C: Both Platforms
```json
{
  "platforms": ["twitch", "kick"],
  "twitch_channel": "your_twitch_channel",
  "kick_channel": "your_kick_channel"
}
```

## 🎤 Voice Commands

All voice commands work across both platforms:

```
"Hey Brian, ban toxic_user for spamming"
"Hey Brian, timeout annoying_chatter for 600 seconds"
"Hey Brian, unban reformed_user"
```

When running on multiple platforms, commands execute on **all enabled platforms** simultaneously.

## 🔧 Technical Architecture

### Multi-Platform Manager
- Coordinates between Twitch and Kick platforms
- Unified command processing
- Cross-platform username resolution
- Independent platform operation

### Kick Integration Components
```
src/platforms/kick/
├── kick_api.py          # OAuth 2.1 & API client
├── kick_bot.py          # Moderation logic
├── kick_chat_monitor.py # Pusher WebSocket chat monitoring
└── __init__.py
```

### Configuration Management
- Platform-specific credential validation
- Dynamic channel assignment
- Automatic token refresh for Kick
- Fallback mechanisms

## 🚨 Important Notes

### Rate Limiting
- **Kick API**: Conservative 100 requests/minute
- **Twitch API**: 800 requests/minute (Helix limit)

### Authentication
- **Kick**: OAuth 2.1 with PKCE (more secure)
- **Twitch**: OAuth 2.0 (existing system)

### Username Resolution
- Cross-platform username matching
- AI-powered phonetic matching for Twitch
- Simple fuzzy matching for Kick
- Recent chat history tracking

## 🐛 Troubleshooting

### Common Issues

**1. Kick OAuth fails**
- Check redirect URI matches exactly: `http://localhost:8000/auth/kick/callback`
- Verify Client ID and Client Secret
- Ensure Kick app is active

**2. Commands not executing on Kick**
- Verify bot has moderation permissions in Kick channel
- Check OAuth token is valid
- Confirm channel name is correct (lowercase)

**3. Chat monitoring not working**
- Pusher connection uses public keys (no auth required)
- Check network connectivity
- Verify channel name format

### Debug Logs
Enable debug logging to see detailed platform status:
```python
import logging
logging.getLogger().setLevel(logging.DEBUG)
```

## 🔮 Future Enhancements

Planned features for future updates:
- Kick-specific chat settings management
- Enhanced cross-platform user tracking
- Platform-specific command routing
- Advanced moderation analytics
- Custom platform-specific actions

## 📖 API Reference

### Configuration Schema
```typescript
interface BotConfig {
  platforms: ('twitch' | 'kick')[]
  twitch_channel?: string
  kick_channel?: string
}
```

### Platform Status
```typescript
interface PlatformStatus {
  [platform: string]: {
    enabled: boolean
    connected: boolean
    bot_available: boolean
  }
}
```

---

## 🎉 Ready to Moderate!

Your AI Moderator Bot is now equipped to handle both Twitch and Kick.com! Start with one platform to test, then expand to multi-platform moderation as needed.

**Happy Streaming! 🚀** 