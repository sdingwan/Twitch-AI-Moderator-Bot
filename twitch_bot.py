import asyncio
import logging
import time
from typing import Optional, Dict, List
from datetime import datetime, timedelta
from config import Config
from command_processor import ModerationCommand
from twitch_api import TwitchHelixAPI

logger = logging.getLogger(__name__)

class TwitchModeratorBot:
    def __init__(self, command_callback=None):
        """
        Initialize the Twitch moderator bot using Helix API
        
        Args:
            command_callback: Callback function for when commands are executed
        """
        self.command_callback = command_callback
        self.api = TwitchHelixAPI()
        self.is_connected = False
        
        # Track moderation actions for logging
        self.moderation_log = []
        
    async def initialize(self):
        """Initialize the bot and connect to Twitch API"""
        try:
            success = await self.api.initialize()
            if success:
                self.is_connected = True
                logger.info(f'✅ Bot connected to Twitch Helix API for channel: {Config.TWITCH_CHANNEL}')
                return True
            else:
                logger.error('❌ Failed to connect to Twitch API')
                return False
        except Exception as e:
            logger.error(f'Error initializing bot: {e}')
            return False
    
    async def execute_moderation_command(self, cmd: ModerationCommand) -> bool:
        """
        Execute a moderation command using Helix API
        
        Args:
            cmd: ModerationCommand object containing the action details
            
        Returns:
            True if command was executed successfully, False otherwise
        """
        if not self.is_connected:
            logger.error("Bot is not connected to Twitch API")
            return False
        
        try:
            success = False
            
            if cmd.action == 'ban':
                success = await self.api.ban_user(cmd.username, cmd.reason)
                if success:
                    await self.api.send_chat_message(f"🔨 {cmd.username} has been banned" + 
                                                   (f" (Reason: {cmd.reason})" if cmd.reason else ""))
            elif cmd.action == 'timeout':
                success = await self.api.ban_user(cmd.username, cmd.reason, cmd.duration)
                if success:
                    duration_text = self._format_duration(cmd.duration)
                    await self.api.send_chat_message(f"⏰ {cmd.username} has been timed out for {duration_text}" + 
                                                   (f" (Reason: {cmd.reason})" if cmd.reason else ""))
            elif cmd.action == 'unban':
                success = await self.api.unban_user(cmd.username)
                if success:
                    await self.api.send_chat_message(f"✅ {cmd.username} has been unbanned")
            elif cmd.action == 'clear':
                success = await self.api.clear_chat()
                if success:
                    await self.api.send_chat_message("🧹 Chat has been cleared")
            elif cmd.action == 'slow':
                success = await self.api.update_chat_settings(slow_mode_duration=cmd.duration)
                if success:
                    await self.api.send_chat_message(f"🐌 Slow mode enabled: {cmd.duration} seconds between messages")
            elif cmd.action == 'followers_only':
                success = await self.api.update_chat_settings(follower_only_duration=cmd.duration)
                if success:
                    duration_text = f"{cmd.duration // 60} minutes minimum follow time" if cmd.duration else "enabled"
                    await self.api.send_chat_message(f"👥 Followers-only mode {duration_text}")
            else:
                logger.error(f"Unknown moderation action: {cmd.action}")
                return False
            
            if success:
                # Log the action
                self._log_moderation_action(cmd)
                
                # Call callback if provided
                if self.command_callback:
                    self.command_callback(cmd, success)
                
                logger.info(f"✅ Successfully executed command: {cmd}")
            else:
                logger.error(f"❌ Failed to execute command: {cmd}")
            
            return success
            
        except Exception as e:
            logger.error(f"Error executing moderation command: {e}")
            return False
    
    async def close(self):
        """Close the bot and API connections"""
        if self.api:
            await self.api.close()
        self.is_connected = False
        logger.info("Twitch moderator bot closed")
    
    def _format_duration(self, seconds: int) -> str:
        """Format duration in seconds to human readable string"""
        if seconds < 60:
            return f"{seconds} seconds"
        elif seconds < 3600:
            minutes = seconds // 60
            return f"{minutes} minutes"
        else:
            hours = seconds // 3600
            minutes = (seconds % 3600) // 60
            if minutes > 0:
                return f"{hours} hours {minutes} minutes"
            else:
                return f"{hours} hours"
    
    def _log_moderation_action(self, cmd: ModerationCommand):
        """Log moderation action for record keeping"""
        log_entry = {
            'timestamp': datetime.now(),
            'action': cmd.action,
            'username': cmd.username,
            'duration': cmd.duration,
            'reason': cmd.reason,
            'executor': 'voice_command'
        }
        
        self.moderation_log.append(log_entry)
        
        # Keep only last 100 entries
        if len(self.moderation_log) > 100:
            self.moderation_log = self.moderation_log[-100:]
    
    def get_moderation_log(self, limit: int = 10) -> List[Dict]:
        """Get recent moderation actions"""
        return self.moderation_log[-limit:]
    
    async def send_status_message(self):
        """Send status message to chat"""
        try:
            await self.api.send_chat_message("🤖 AI Moderator Bot is online and listening for voice commands!")
        except Exception as e:
            logger.error(f"Failed to send status message: {e}")
    
    async def get_moderators(self) -> List[Dict]:
        """Get list of channel moderators"""
        try:
            return await self.api.get_moderators()
        except Exception as e:
            logger.error(f"Failed to get moderators: {e}")
            return [] 