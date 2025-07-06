# Kick.com Integration Guide

This guide explains how to set up and use the AI Moderator Bot with Kick.com.

## Overview

The AI Moderator Bot supports Kick.com as a moderation platform alongside Twitch. The bot can run on both platforms simultaneously or individually, with unified voice commands and cross-platform username resolution.

## Features

### Supported Actions on Kick

**Direct API Support:**
- ✅ Ban users (permanent)
- ✅ Timeout users (with duration)
- ✅ Unban/untimeout users
- ✅ Send chat messages

**Chat Mode Commands (via chat messages):**
- ✅ Clear chat (`/clear`)
- ✅ Slow mode (`/slow on/off [seconds]`)
- ✅ Followers-only mode (`/followonly on/off [minutes]`)
- ✅ Emote-only mode (`/emoteonly on/off`)
- ✅ Subscribers-only mode (`/subonly on/off`)

> **Note:** Since Kick's API doesn't currently support chat mode commands directly, these commands are sent as regular chat messages that moderators can execute. The bot will send the command (e.g., `/slow on 30`) followed by a confirmation message.

### Voice Commands

All voice commands work the same way as on Twitch:
- "Hey Brian, ban username"
- "Hey Brian, timeout username for 10 minutes"
- "Hey Brian, clear chat"
- "Hey Brian, slow mode 30 seconds"
- "Hey Brian, followers only 5 minutes"
- "Hey Brian, emote only"
- "Hey Brian, subscribers only"

## How Chat Mode Commands Work

Since Kick's API doesn't support chat mode commands directly, the bot implements a clever workaround:

1. **Voice Command:** "Hey Brian, slow mode 30 seconds"
2. **Bot Processing:** Recognizes the command and formats it as `/slow on 30`
3. **Chat Message:** Bot sends `/slow on 30` to Kick chat
4. **Moderator Execution:** A moderator (or the streamer) can execute this command
5. **Confirmation:** Bot sends "🤖 Chat mode command sent: /slow on 30"

This approach allows the bot to support all chat mode features even without direct API support.

## Setup Instructions

### 1. OAuth 2.1 Application Setup

1. Go to [Kick.com Developer Portal](https://kick.com/developer)
2. Create a new OAuth application:
   - **Application Name:** AI Moderator Bot
   - **Redirect URI:** `http://localhost:8000/auth/kick/callback`
   - **Scopes:** Select all available scopes (chat, moderation, etc.)

3. Note down your `client_id` and `client_secret`

### 2. Environment Configuration

Add these variables to your `.env` file:

```env
# Kick Configuration
KICK_CLIENT_ID=your_client_id_here
KICK_CLIENT_SECRET=your_client_secret_here
KICK_CHANNEL=your_channel_name_here
KICK_REDIRECT_URI=http://localhost:8000/auth/kick/callback

# Multi-Platform Configuration
ENABLED_PLATFORMS=twitch,kick  # or just 'kick' for Kick only
```

### 3. OAuth Token Setup

Run the OAuth setup script:

```bash
python kick_oauth_setup.py
```

This will:
1. Open your browser to Kick's OAuth page
2. Ask you to authorize the application
3. Automatically save the access and refresh tokens to your `.env` file

### 4. Start the Bot

```bash
python web/main.py
```

The bot will automatically:
- Connect to Kick using your OAuth tokens
- Start monitoring chat for usernames
- Enable voice commands for moderation

## Troubleshooting

### Common Issues

1. **"Missing Kick configuration"**
   - Ensure all required environment variables are set
   - Check that `KICK_CLIENT_ID`, `KICK_CLIENT_SECRET`, and `KICK_CHANNEL` are configured

2. **"Failed to connect to Kick API"**
   - Verify your OAuth tokens are valid
   - Run `python kick_oauth_setup.py` to refresh tokens
   - Check that your channel name is correct

3. **"Chat mode commands not working"**
   - Ensure you have moderator permissions in the channel
   - Check that the bot account has permission to send chat messages
   - Verify the command format in the chat logs

### Token Refresh

If you encounter authentication errors, your tokens may have expired. Run:

```bash
python kick_oauth_setup.py
```

This will refresh your tokens automatically.

## Platform Comparison

| Feature | Twitch | Kick |
|---------|--------|------|
| Ban/Timeout | ✅ API | ✅ API |
| Unban/Untimeout | ✅ API | ✅ API |
| Clear Chat | ✅ API | ✅ Chat Message |
| Slow Mode | ✅ API | ✅ Chat Message |
| Followers Only | ✅ API | ✅ Chat Message |
| Emote Only | ✅ API | ✅ Chat Message |
| Subscribers Only | ✅ API | ✅ Chat Message |
| Voice Commands | ✅ | ✅ |
| Username Resolution | ✅ | ✅ |

## Security Notes

- OAuth tokens are stored securely in your `.env` file
- The bot only has the permissions you grant during OAuth setup
- All moderation actions are logged for audit purposes
- Username resolution uses AI to prevent targeting innocent users

## Support

For issues specific to Kick integration:
1. Check the troubleshooting section above
2. Verify your OAuth setup is correct
3. Ensure your channel permissions are properly configured
4. Check the bot logs for detailed error messages

Your AI Moderator Bot is now equipped to handle both Twitch and Kick.com! Start with one platform to test, then expand to multi-platform moderation as needed.

**Happy Streaming! 🚀** 