import asyncio
import aiohttp
import logging
import time
import json
from typing import Optional, Dict, List, Any
from datetime import datetime, timedelta
from config import Config

logger = logging.getLogger(__name__)

class TwitchHelixAPI:
    """Twitch Helix API client for moderation actions"""
    
    def __init__(self):
        self.base_url = "https://api.twitch.tv/helix"
        self.session = None
        self.access_token = None
        self.broadcaster_id = None
        self.moderator_id = None
        self.rate_limiter = HelixRateLimiter()
        
    async def initialize(self):
        """Initialize the API client and get necessary tokens"""
        try:
            self.session = aiohttp.ClientSession()
            
            # Get access token
            await self._get_access_token()
            
            # Get broadcaster and moderator IDs
            await self._get_user_ids()
            
            logger.info("✅ Twitch Helix API initialized successfully")
            return True
            
        except Exception as e:
            logger.error(f"Failed to initialize Twitch API: {e}")
            return False
    
    async def _get_access_token(self):
        """Get OAuth access token using client credentials flow"""
        try:
            # For bot operations, we'll use the provided OAuth token
            # In production, you might want to implement token refresh
            self.access_token = Config.TWITCH_TOKEN.replace('oauth:', '')
            
            # Validate the token
            headers = {
                'Authorization': f'Bearer {self.access_token}',
                'Client-Id': Config.TWITCH_CLIENT_ID
            }
            
            async with self.session.get(
                'https://id.twitch.tv/oauth2/validate',
                headers=headers
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    logger.info(f"Token validated for user: {data.get('login')}")
                else:
                    raise Exception(f"Token validation failed: {response.status}")
                    
        except Exception as e:
            logger.error(f"Failed to get access token: {e}")
            raise
    
    async def _get_user_ids(self):
        """Get broadcaster and moderator user IDs"""
        try:
            headers = {
                'Authorization': f'Bearer {self.access_token}',
                'Client-Id': Config.TWITCH_CLIENT_ID
            }
            
            # Get broadcaster ID
            params = {'login': Config.TWITCH_CHANNEL}
            async with self.session.get(
                f'{self.base_url}/users',
                headers=headers,
                params=params
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    if data['data']:
                        self.broadcaster_id = data['data'][0]['id']
                        logger.info(f"Broadcaster ID: {self.broadcaster_id}")
                    else:
                        raise Exception(f"Broadcaster not found: {Config.TWITCH_CHANNEL}")
                else:
                    raise Exception(f"Failed to get broadcaster ID: {response.status}")
            
            # Get moderator ID (bot user)
            params = {'login': Config.TWITCH_BOT_USERNAME}
            async with self.session.get(
                f'{self.base_url}/users',
                headers=headers,
                params=params
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    if data['data']:
                        self.moderator_id = data['data'][0]['id']
                        logger.info(f"Moderator ID: {self.moderator_id}")
                    else:
                        raise Exception(f"Moderator not found: {Config.TWITCH_BOT_USERNAME}")
                else:
                    raise Exception(f"Failed to get moderator ID: {response.status}")
                    
        except Exception as e:
            logger.error(f"Failed to get user IDs: {e}")
            raise
    
    async def ban_user(self, username: str, reason: Optional[str] = None, duration: Optional[int] = None) -> bool:
        """Ban or timeout a user"""
        try:
            if not await self.rate_limiter.can_make_request():
                logger.warning("Rate limit exceeded for ban request")
                return False
            
            # Get user ID
            user_id = await self._get_user_id(username)
            if not user_id:
                logger.error(f"User not found: {username}")
                return False
            
            headers = {
                'Authorization': f'Bearer {self.access_token}',
                'Client-Id': Config.TWITCH_CLIENT_ID,
                'Content-Type': 'application/json'
            }
            
            # Prepare ban data
            ban_data = {
                'data': {
                    'user_id': user_id,
                    'reason': reason or 'Moderation action via voice command'
                }
            }
            
            # Add duration for timeout (if specified)
            if duration:
                ban_data['data']['duration'] = duration
            
            params = {
                'broadcaster_id': self.broadcaster_id,
                'moderator_id': self.moderator_id
            }
            
            async with self.session.post(
                f'{self.base_url}/moderation/bans',
                headers=headers,
                params=params,
                json=ban_data
            ) as response:
                if response.status == 200:
                    action_type = "timed out" if duration else "banned"
                    logger.info(f"✅ User {username} {action_type} successfully")
                    return True
                else:
                    error_text = await response.text()
                    logger.error(f"Failed to ban user {username}: {response.status} - {error_text}")
                    return False
                    
        except Exception as e:
            logger.error(f"Error banning user {username}: {e}")
            return False
    
    async def unban_user(self, username: str) -> bool:
        """Unban a user"""
        try:
            if not await self.rate_limiter.can_make_request():
                logger.warning("Rate limit exceeded for unban request")
                return False
            
            # Get user ID
            user_id = await self._get_user_id(username)
            if not user_id:
                logger.error(f"User not found: {username}")
                return False
            
            headers = {
                'Authorization': f'Bearer {self.access_token}',
                'Client-Id': Config.TWITCH_CLIENT_ID
            }
            
            params = {
                'broadcaster_id': self.broadcaster_id,
                'moderator_id': self.moderator_id,
                'user_id': user_id
            }
            
            async with self.session.delete(
                f'{self.base_url}/moderation/bans',
                headers=headers,
                params=params
            ) as response:
                if response.status == 204:
                    logger.info(f"✅ User {username} unbanned successfully")
                    return True
                else:
                    error_text = await response.text()
                    logger.error(f"Failed to unban user {username}: {response.status} - {error_text}")
                    return False
                    
        except Exception as e:
            logger.error(f"Error unbanning user {username}: {e}")
            return False
    
    async def clear_chat(self) -> bool:
        """Clear chat messages"""
        try:
            if not await self.rate_limiter.can_make_request():
                logger.warning("Rate limit exceeded for clear chat request")
                return False
            
            headers = {
                'Authorization': f'Bearer {self.access_token}',
                'Client-Id': Config.TWITCH_CLIENT_ID
            }
            
            params = {
                'broadcaster_id': self.broadcaster_id,
                'moderator_id': self.moderator_id
            }
            
            async with self.session.delete(
                f'{self.base_url}/moderation/chat',
                headers=headers,
                params=params
            ) as response:
                if response.status == 204:
                    logger.info("✅ Chat cleared successfully")
                    return True
                else:
                    error_text = await response.text()
                    logger.error(f"Failed to clear chat: {response.status} - {error_text}")
                    return False
                    
        except Exception as e:
            logger.error(f"Error clearing chat: {e}")
            return False
    
    async def update_chat_settings(self, slow_mode_duration: Optional[int] = None, 
                                 follower_only_duration: Optional[int] = None,
                                 subscriber_only: Optional[bool] = None,
                                 emote_only: Optional[bool] = None) -> bool:
        """Update chat settings (slow mode, follower-only mode, subscriber-only mode, emote-only mode, etc.)"""
        try:
            if not await self.rate_limiter.can_make_request():
                logger.warning("Rate limit exceeded for chat settings request")
                return False
            
            headers = {
                'Authorization': f'Bearer {self.access_token}',
                'Client-Id': Config.TWITCH_CLIENT_ID,
                'Content-Type': 'application/json'
            }
            
            # Prepare settings data
            settings_data = {}
            
            if slow_mode_duration is not None:
                if slow_mode_duration == 0:
                    settings_data['slow_mode'] = False
                else:
                    settings_data['slow_mode'] = True
                    settings_data['slow_mode_wait_time'] = slow_mode_duration
            
            if follower_only_duration is not None:
                if follower_only_duration == 0:
                    settings_data['follower_mode'] = False
                else:
                    settings_data['follower_mode'] = True
                    settings_data['follower_mode_duration'] = follower_only_duration // 60  # Convert to minutes
            
            if subscriber_only is not None:
                settings_data['subscriber_mode'] = subscriber_only
            
            if emote_only is not None:
                settings_data['emote_mode'] = emote_only
            
            params = {
                'broadcaster_id': self.broadcaster_id,
                'moderator_id': self.moderator_id
            }
            
            async with self.session.patch(
                f'{self.base_url}/chat/settings',
                headers=headers,
                params=params,
                json=settings_data
            ) as response:
                if response.status == 200:
                    logger.info("✅ Chat settings updated successfully")
                    return True
                else:
                    error_text = await response.text()
                    logger.error(f"Failed to update chat settings: {response.status} - {error_text}")
                    return False
                    
        except Exception as e:
            logger.error(f"Error updating chat settings: {e}")
            return False
    
    async def send_chat_message(self, message: str) -> bool:
        """Send a message to chat"""
        try:
            if not await self.rate_limiter.can_make_request():
                logger.warning("Rate limit exceeded for chat message")
                return False
            
            headers = {
                'Authorization': f'Bearer {self.access_token}',
                'Client-Id': Config.TWITCH_CLIENT_ID,
                'Content-Type': 'application/json'
            }
            
            message_data = {
                'broadcaster_id': self.broadcaster_id,
                'sender_id': self.moderator_id,
                'message': message
            }
            
            async with self.session.post(
                f'{self.base_url}/chat/messages',
                headers=headers,
                json=message_data
            ) as response:
                if response.status == 200:
                    logger.debug(f"Message sent: {message}")
                    return True
                else:
                    error_text = await response.text()
                    logger.error(f"Failed to send message: {response.status} - {error_text}")
                    return False
                    
        except Exception as e:
            logger.error(f"Error sending chat message: {e}")
            return False
    
    async def _get_user_id(self, username: str) -> Optional[str]:
        """Get user ID from username"""
        try:
            headers = {
                'Authorization': f'Bearer {self.access_token}',
                'Client-Id': Config.TWITCH_CLIENT_ID
            }
            
            params = {'login': username.lower()}
            async with self.session.get(
                f'{self.base_url}/users',
                headers=headers,
                params=params
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    if data['data']:
                        return data['data'][0]['id']
                    else:
                        return None
                else:
                    logger.error(f"Failed to get user ID for {username}: {response.status}")
                    return None
                    
        except Exception as e:
            logger.error(f"Error getting user ID for {username}: {e}")
            return None
    
    async def get_moderators(self) -> List[Dict[str, Any]]:
        """Get list of channel moderators"""
        try:
            headers = {
                'Authorization': f'Bearer {self.access_token}',
                'Client-Id': Config.TWITCH_CLIENT_ID
            }
            
            params = {'broadcaster_id': self.broadcaster_id}
            async with self.session.get(
                f'{self.base_url}/moderation/moderators',
                headers=headers,
                params=params
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    return data.get('data', [])
                else:
                    logger.error(f"Failed to get moderators: {response.status}")
                    return []
                    
        except Exception as e:
            logger.error(f"Error getting moderators: {e}")
            return []
    
    async def close(self):
        """Close the API client"""
        if self.session:
            await self.session.close()
            logger.info("Twitch API client closed")

class HelixRateLimiter:
    """Rate limiter for Twitch Helix API"""
    
    def __init__(self):
        self.requests = []
        self.max_requests = 800  # Helix API limit per minute
        self.time_window = 60  # seconds
    
    async def can_make_request(self) -> bool:
        """Check if we can make a request without exceeding rate limits"""
        now = time.time()
        
        # Remove requests older than the time window
        self.requests = [req_time for req_time in self.requests if now - req_time < self.time_window]
        
        # Check if we're under the limit
        if len(self.requests) < self.max_requests:
            self.requests.append(now)
            return True
        
        return False 