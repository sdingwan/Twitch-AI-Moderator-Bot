import asyncio
import logging
import time
from typing import Optional, Dict, List
from datetime import datetime, timedelta
from ...core.config import Config
from ...core.command_processor import ModerationCommand
from .kick_api import KickAPI

logger = logging.getLogger(__name__)

class KickModeratorBot:
    def __init__(self, command_callback=None):
        """
        Initialize the Kick moderator bot using Kick API
        
        Args:
            command_callback: Callback function for when commands are executed
        """
        self.command_callback = command_callback
        self.api = KickAPI()
        self.is_connected = False
        
        # Track moderation actions for logging
        self.moderation_log = []
        
    async def initialize(self):
        """Initialize the bot and connect to Kick API"""
        try:
            success = await self.api.initialize()
            if success:
                self.is_connected = True
                logger.info(f'✅ Bot connected to Kick API for channel: {Config.KICK_CHANNEL}')
                return True
            else:
                logger.error('❌ Failed to connect to Kick API')
                await self.close()  # Clean up on failure
                return False
        except Exception as e:
            logger.error(f'Error initializing Kick bot: {e}')
            await self.close()  # Clean up on failure
            return False
    
    async def execute_moderation_command(self, cmd: ModerationCommand) -> bool:
        """
        Execute a moderation command using Kick API
        
        Args:
            cmd: ModerationCommand object containing the action details
            
        Returns:
            True if command was executed successfully, False otherwise
        """
        if not self.is_connected:
            logger.error("Bot is not connected to Kick API")
            return False
        
        try:
            success = False
            
            # Kick supports these core moderation actions
            if cmd.action == 'ban':
                success = await self.api.ban_user(cmd.username, cmd.reason)
            elif cmd.action == 'timeout':
                success = await self.api.ban_user(cmd.username, cmd.reason, cmd.duration)
            elif cmd.action == 'unban':
                success = await self.api.unban_user(cmd.username)
            elif cmd.action == 'untimeout':
                success = await self.api.unban_user(cmd.username)
            else:
                logger.warning(f"Unsupported action for Kick: {cmd.action}")
                # For unsupported actions, we'll send a chat message explaining
                await self.api.send_chat_message(f"⚠️ Action '{cmd.action}' not supported on Kick platform")
                return False
            
            if success:
                # Log the action
                self._log_moderation_action(cmd)
                
                # Call callback if provided
                if self.command_callback:
                    self.command_callback(cmd, success)
                
                logger.info(f"✅ Successfully executed Kick command: {cmd}")
            else:
                logger.error(f"❌ Failed to execute Kick command: {cmd}")
            
            return success
            
        except Exception as e:
            logger.error(f"Error executing Kick moderation command: {e}")
            return False
    
    async def close(self):
        """Close the bot and API connections"""
        if self.api:
            await self.api.close()
        self.is_connected = False
        logger.info("Kick moderator bot closed")
    
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
            'executor': 'voice_command',
            'platform': 'kick'
        }
        
        self.moderation_log.append(log_entry)
        
        # Keep only last 100 entries
        if len(self.moderation_log) > 100:
            self.moderation_log = self.moderation_log[-100:]
    
    def get_moderation_log(self, limit: int = 10) -> List[Dict]:
        """Get recent moderation actions"""
        return self.moderation_log[-limit:]
    
    async def send_status_message(self):
        """Send status message to chat as Briann-24"""
        try:
            await self.api.send_chat_message("🤖 AI Moderator is online on Kick!")
        except Exception as e:
            logger.error(f"Failed to send status message to Kick: {e}")
    
    async def send_username_not_found_message(self, spoken_username: str, action: str):
        """Send message to Kick chat when username cannot be found for moderation"""
        try:
            message = f"⚠️ Cannot {action} '{spoken_username}' - user not found in recent chat."
            await self.api.send_chat_message(message)
            logger.info(f"Sent username not found message to Kick chat: {message}")
        except Exception as e:
            logger.error(f"Failed to send username not found message to Kick: {e}") 