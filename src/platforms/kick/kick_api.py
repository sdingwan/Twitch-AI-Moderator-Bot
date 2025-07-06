import asyncio
import aiohttp
import logging
import time
import json
from typing import Optional, Dict, List, Any
from datetime import datetime, timedelta
from ...core.config import Config

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

class KickAPI:
    """Kick.com API client with OAuth 2.1 authentication and moderation endpoints"""
    
    def __init__(self):
        self.base_url = "https://api.kick.com/public/v1"
        self.oauth_url = "https://id.kick.com"
        self.session = None
        self.access_token = None
        self.refresh_token = None
        # Always use Briann-24's user ID for all moderation and chat actions
        self.broadcaster_user_id = 4304921
        self.rate_limiter = KickRateLimiter()
        
    async def initialize(self):
        """Initialize the API client and authenticate"""
        try:
            self.session = aiohttp.ClientSession()
            
            # Debug: Log tokens at startup
            logger.debug(f"[DEBUG] Startup: access_token={Config.KICK_ACCESS_TOKEN[:10]}... refresh_token={Config.KICK_REFRESH_TOKEN[:10]}...")
            
            # If we have stored tokens, try to use them
            if Config.KICK_ACCESS_TOKEN:
                self.access_token = Config.KICK_ACCESS_TOKEN
                self.refresh_token = Config.KICK_REFRESH_TOKEN
                
                # Debug: Log before validation
                logger.debug(f"[DEBUG] Before validation: access_token={self.access_token[:10]}... refresh_token={self.refresh_token[:10]}...")
                
                # Validate current token
                if await self._validate_token():
                    await self._get_broadcaster_id()
                    logger.info("✅ Kick API initialized with existing token")
                    return True
                else:
                    # Debug: Log before refresh
                    logger.debug(f"[DEBUG] Token invalid, attempting refresh with refresh_token={self.refresh_token[:10]}...")
                    # Token invalid, try to refresh
                    if await self._refresh_access_token():
                        await self._get_broadcaster_id()
                        logger.info("✅ Kick API initialized with refreshed token")
                        return True
                    else:
                        logger.warning("Failed to refresh token, need new OAuth flow")
                        await self.close()  # Clean up session on failure
                        return False
            else:
                logger.warning("No Kick access token found. Please complete OAuth flow.")
                await self.close()  # Clean up session on failure
                return False
                
        except Exception as e:
            logger.error(f"Failed to initialize Kick API: {e}")
            await self.close()  # Clean up session on failure
            return False
    
    async def _validate_token(self) -> bool:
        """Validate current access token"""
        try:
            headers = {'Authorization': f'Bearer {self.access_token}'}
            
            # Use the public channels endpoint which we know works with our scopes
            async with self.session.get(
                f"{self.base_url}/public/v1/channels",
                headers=headers
            ) as response:
                if response.status == 200:
                    return True
                elif response.status == 401:
                    # Token is expired/invalid, try to refresh
                    logger.info("Token appears expired, attempting refresh...")
                    return await self._refresh_access_token()
                else:
                    logger.error(f"Token validation failed with status: {response.status}")
                    return False
                
        except Exception as e:
            logger.error(f"Token validation error: {e}")
            return False
    
    async def _refresh_access_token(self) -> bool:
        """Refresh access token using refresh token"""
        try:
            if not self.refresh_token:
                logger.debug("[DEBUG] No refresh token available for refresh.")
                return False
            
            data = {
                'grant_type': 'refresh_token',
                'client_id': Config.KICK_CLIENT_ID,
                'client_secret': Config.KICK_CLIENT_SECRET,
                'refresh_token': self.refresh_token
            }
            
            headers = {'Content-Type': 'application/x-www-form-urlencoded'}
            
            logger.debug(f"[DEBUG] Attempting token refresh with refresh_token={self.refresh_token[:10]}...")
            
            async with self.session.post(
                f"{self.oauth_url}/oauth/token",
                headers=headers,
                data=data
            ) as response:
                resp_text = await response.text()
                logger.debug(f"[DEBUG] Refresh response status: {response.status}, body: {resp_text}")
                if response.status == 200:
                    token_data = await response.json()
                    self.access_token = token_data['access_token']
                    self.refresh_token = token_data.get('refresh_token', self.refresh_token)
                    
                    # Save new tokens to .env file to persist across restarts
                    self._save_tokens_to_env(self.access_token, self.refresh_token)
                    
                    # Update Config class variables to keep them in sync
                    Config.update_kick_tokens(self.access_token, self.refresh_token)
                    
                    logger.info("✅ Access token refreshed and saved")
                    logger.debug(f"[DEBUG] New access_token={self.access_token[:10]}... refresh_token={self.refresh_token[:10]}...")
                    return True
                else:
                    logger.error(f"Token refresh failed: {response.status}")
                    return False
                    
        except Exception as e:
            logger.error(f"Error refreshing token: {e}")
            return False
    
    def _save_tokens_to_env(self, access_token: str, refresh_token: str):
        """Save tokens to .env file for persistence"""
        try:
            import os
            from pathlib import Path
            
            # Get the project root directory (where .env should be)
            # This file is in src/platforms/kick/, so go up 3 levels to reach project root
            current_file_dir = Path(__file__).parent
            project_root = current_file_dir.parent.parent.parent
            env_file = project_root / '.env'
            
            if not env_file.exists():
                logger.error(f".env file not found at {env_file}, cannot save tokens")
                return
            
            # Read current .env content
            with open(env_file, 'r') as f:
                lines = f.readlines()
            
            # Update or add token lines
            updated_lines = []
            access_updated = False
            refresh_updated = False
            
            for line in lines:
                if line.startswith('KICK_ACCESS_TOKEN='):
                    updated_lines.append(f'KICK_ACCESS_TOKEN={access_token}\n')
                    access_updated = True
                elif line.startswith('KICK_REFRESH_TOKEN='):
                    updated_lines.append(f'KICK_REFRESH_TOKEN={refresh_token}\n')
                    refresh_updated = True
                else:
                    updated_lines.append(line)
            
            # Add tokens if they weren't found
            if not access_updated:
                updated_lines.append(f'KICK_ACCESS_TOKEN={access_token}\n')
            if not refresh_updated:
                updated_lines.append(f'KICK_REFRESH_TOKEN={refresh_token}\n')
            
            # Write back to .env file
            with open(env_file, 'w') as f:
                f.writelines(updated_lines)
            
            logger.debug("Tokens saved to .env file")
            
        except Exception as e:
            logger.error(f"Failed to save tokens to .env: {e}")
    
    async def _get_broadcaster_id(self):
        """Get broadcaster user ID from channel slug using official Kick API"""
        try:
            headers = {'Authorization': f'Bearer {self.access_token}'}
            
            # Use official Kick API channels endpoint with channel slug
            async with self.session.get(
                f"{self.base_url}/channels",
                headers=headers,
                params={'slug': [Config.KICK_CHANNEL.lower()]}
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    if data.get('data') and len(data['data']) > 0:
                        self.broadcaster_user_id = data['data'][0]['broadcaster_user_id']
                        logger.info(f"Kick broadcaster ID: {self.broadcaster_user_id}")
                    else:
                        logger.error("No channel data returned from Kick API")
                else:
                    error_text = await response.text()
                    logger.error(f"Failed to get broadcaster ID: {response.status} - {error_text}")
                    
        except Exception as e:
            logger.error(f"Error getting broadcaster ID: {e}")
    
    async def ban_user(self, username: str, reason: Optional[str] = None, duration: Optional[int] = None) -> bool:
        """Ban or timeout a user on Kick as Briann-24 (user 4304921)"""
        try:
            if not await self.rate_limiter.can_make_request():
                logger.warning("Rate limit exceeded for ban request")
                return False
            
            # Get user ID from username
            user_id = await self._get_user_id(username)
            if not user_id:
                logger.error(f"User not found: {username}")
                return False
            
            headers = {
                'Authorization': f'Bearer {self.access_token}',
                'Content-Type': 'application/json'
            }
            
            # Prepare ban data according to official Kick API format
            ban_data = {
                'broadcaster_user_id': int(self.broadcaster_user_id),  # Ensure integer
                'user_id': int(user_id),  # Convert string to integer as required by API
                'reason': (reason or 'Moderation action via voice command')[:100]  # Limit to 100 chars
            }
            
            # Add duration for timeout (duration in minutes for Kick API)
            if duration:
                ban_data['duration'] = max(1, min(10080, duration // 60))  # Convert seconds to minutes, clamp to 1-10080
            
            logger.debug(f"Ban request data: {ban_data}")
            
            async with self.session.post(
                f"{self.base_url}/moderation/bans",
                headers=headers,
                json=ban_data
            ) as response:
                if response.status == 200:
                    action_type = "timed out" if duration else "banned"
                    logger.info(f"✅ User {username} {action_type} successfully on Kick")
                    return True
                else:
                    error_text = await response.text()
                    logger.error(f"Failed to ban user {username} on Kick: {response.status} - {error_text}")
                    return False
                    
        except Exception as e:
            logger.error(f"Error banning user {username} on Kick: {e}")
            return False
    
    async def unban_user(self, username: str) -> bool:
        """Unban/untimeout a user on Kick as Briann-24 (user 4304921)"""
        try:
            if not await self.rate_limiter.can_make_request():
                logger.warning("Rate limit exceeded for unban request")
                return False
            
            # Get user ID from username
            user_id = await self._get_user_id(username)
            if not user_id:
                logger.error(f"User not found: {username}")
                return False
            
            headers = {
                'Authorization': f'Bearer {self.access_token}',
                'Content-Type': 'application/json'
            }
            
            unban_data = {
                'broadcaster_user_id': int(self.broadcaster_user_id),  # Ensure integer
                'user_id': int(user_id)  # Convert string to integer as required by API
            }
            
            logger.debug(f"Unban request data: {unban_data}")
            
            async with self.session.delete(
                f"{self.base_url}/moderation/bans",
                headers=headers,
                json=unban_data
            ) as response:
                if response.status == 200:
                    logger.info(f"✅ User {username} unbanned successfully on Kick")
                    return True
                else:
                    error_text = await response.text()
                    logger.error(f"Failed to unban user {username} on Kick: {response.status} - {error_text}")
                    return False
                    
        except Exception as e:
            logger.error(f"Error unbanning user {username} on Kick: {e}")
            return False
    
    async def send_chat_message(self, message: str) -> bool:
        """Send a message to Kick chat as Briann-24 (always as user 4304921)"""
        try:
            if not await self.rate_limiter.can_make_request():
                logger.warning("Rate limit exceeded for chat message")
                return False

            headers = {
                'Authorization': f'Bearer {self.access_token}',
                'Content-Type': 'application/json'
            }

            message_data = {
                "content": message,
                "type": "user",
                "broadcaster_user_id": self.broadcaster_user_id
            }

            url = "https://api.kick.com/public/v1/chat"
            async with self.session.post(url, headers=headers, json=message_data) as response:
                if response.status == 200:
                    logger.debug(f"Message sent to Kick: {message}")
                    return True
                else:
                    error_text = await response.text()
                    logger.error(f"Failed to send message to Kick: {response.status} - {error_text}")
                    return False

        except Exception as e:
            logger.error(f"Error sending chat message to Kick: {e}")
            return False
    
    async def _get_user_id(self, username: str) -> Optional[str]:
        """Get user ID from username using Kick API with exact working headers"""
        try:
            import json
            
            # Use the exact same working approach as the user's script
            headers = {
                "User-Agent": "Mozilla/5.0 (compatible)",
                "Accept": "application/json",
                "Referer": "https://kick.com/",
                "Origin": "https://kick.com"
            }
            
            # Try to get user info through their channel (same as working script)
            channel_url = f"https://kick.com/api/v2/channels/{username.lower()}"
            async with self.session.get(channel_url, headers=headers, timeout=10) as response:
                if response.status == 200:
                    # Manually parse JSON to avoid content-type issues
                    try:
                        text = await response.text()
                        data = json.loads(text)
                        broadcaster_id = data.get("user", {}).get("id")
                        if broadcaster_id:
                            user_id = str(broadcaster_id)
                            logger.debug(f"✅ Got user ID for {username} via channel lookup: {user_id}")
                            return user_id
                    except Exception as e:
                        logger.error(f"JSON parsing error for {username}: {e}")
                        return None
                elif response.status == 403:
                    logger.error(f"Access forbidden for {username} - blocked by security policy")
                    return None
                elif response.status == 404:
                    logger.debug(f"Channel not found for {username}, trying direct user lookup...")
                else:
                    logger.warning(f"Channel lookup failed for {username}: {response.status}")
            
            # Fallback: Try direct user lookup (may not work for all users)
            user_url = f"https://kick.com/api/v2/users/{username.lower()}"
            async with self.session.get(user_url, headers=headers, timeout=10) as response:
                if response.status == 200:
                    try:
                        text = await response.text()
                        data = json.loads(text)
                        if 'id' in data:
                            user_id = str(data['id'])
                            logger.debug(f"✅ Got user ID for {username} via direct lookup: {user_id}")
                            return user_id
                    except Exception as e:
                        logger.error(f"JSON parsing error for {username}: {e}")
                        return None
                else:
                    logger.error(f"Failed to get user ID for {username}: {response.status}")
                    return None
                    
        except Exception as e:
            logger.error(f"Error getting user ID for {username}: {e}")
            return None
    
    async def get_channel_info(self, channel_slug: str) -> Optional[Dict]:
        """Get channel information using Kick's public API with working headers"""
        try:
            if not self.session:
                logger.error("No active session for Kick API")
                return None
                
            # Use the same working headers as the user's script
            headers = {
                "User-Agent": "Mozilla/5.0 (compatible)",
                "Accept": "application/json",
                "Referer": "https://kick.com/",
                "Origin": "https://kick.com"
            }
            
            async with self.session.get(
                f"https://kick.com/api/v2/channels/{channel_slug.lower()}",
                headers=headers
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    logger.debug(f"Successfully got channel info for {channel_slug}")
                    return data
                else:
                    error_text = await response.text()
                    logger.error(f"Failed to get channel info for {channel_slug}: {response.status} - {error_text}")
                    return None
                    
        except Exception as e:
            logger.error(f"Error getting channel info for {channel_slug}: {e}")
            return None
    
    async def _get_chatroom_id(self) -> Optional[str]:
        """Get chatroom ID for the current channel using aiohttp"""
        try:
            headers = {"User-Agent": "Mozilla/5.0 (compatible; TranslatorBot/1.0)"}
            async with self.session.get(f"https://kick.com/api/v2/channels/{Config.KICK_CHANNEL}", headers=headers) as response:
                if response.status == 200:
                    data = await response.json()
                    return str(data['chatroom']['id'])
                else:
                    error_text = await response.text()
                    logger.error(f"Failed to get chatroom ID: {response.status} - {error_text}")
                    return None
        except Exception as e:
            logger.error(f"Error getting chatroom ID: {e}")
            return None
    
    async def close(self):
        """Close the API client"""
        if self.session and not self.session.closed:
            await self.session.close()
            logger.debug("Kick API client closed")
        self.session = None

class KickRateLimiter:
    """Rate limiter for Kick API requests"""
    
    def __init__(self):
        self.requests = []
        self.max_requests = 100  # Conservative limit for Kick API
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