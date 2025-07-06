import asyncio
import logging
from typing import Dict, List, Optional, Set
from enum import Enum
from datetime import datetime

from .config import Config
from .command_processor import ModerationCommand
from ..platforms.twitch.twitch_bot import TwitchModeratorBot
from ..platforms.kick.kick_bot import KickModeratorBot
from ..platforms.kick.kick_username_logger import KickUsernameLogger, KickAIModerationHelper
from ..utils.username_logger import UsernameLogger, AIModerationHelper

logger = logging.getLogger(__name__)

class Platform(Enum):
    TWITCH = "twitch"
    KICK = "kick"

class MultiPlatformManager:
    """
    Manages multiple streaming platforms (Twitch, Kick) for the AI Moderator Bot
    Allows running on one or multiple platforms simultaneously
    """
    
    def __init__(self, command_callback=None):
        """
        Initialize the multi-platform manager
        
        Args:
            command_callback: Callback function for when commands are executed
        """
        self.command_callback = command_callback
        self.enabled_platforms: Set[Platform] = set()
        self.bots: Dict[Platform, object] = {}
        self.username_loggers: Dict[Platform, object] = {}
        self.ai_helpers: Dict[Platform, object] = {}
        self.is_running = False
        
        # Cross-platform username resolution
        self.unified_usernames = set()
        
    async def initialize(self, platforms: List[str]):
        """
        Initialize the specified platforms
        
        Args:
            platforms: List of platform names to enable ['twitch', 'kick']
        """
        self.enabled_platforms.clear()
        successfully_initialized = []
        failed_platforms = []
        
        for platform_name in platforms:
            try:
                platform = Platform(platform_name.lower())
                
                if platform == Platform.TWITCH:
                    await self._initialize_twitch()
                    self.enabled_platforms.add(platform)
                    successfully_initialized.append(platform.value)
                elif platform == Platform.KICK:
                    await self._initialize_kick()
                    self.enabled_platforms.add(platform)
                    successfully_initialized.append(platform.value)
                    
            except Exception as e:
                logger.error(f"Failed to initialize {platform_name}: {e}")
                failed_platforms.append(platform_name)
                continue
        
        if successfully_initialized:
            logger.info(f"✅ Multi-platform manager initialized for: {successfully_initialized}")
            if failed_platforms:
                logger.warning(f"⚠️ Failed to initialize: {failed_platforms}")
            return True
        else:
            logger.error("❌ Failed to initialize any platforms")
            return False
    
    async def _initialize_twitch(self):
        """Initialize Twitch platform"""
        # Validate Twitch configuration
        if not all([Config.TWITCH_TOKEN, Config.TWITCH_CLIENT_ID, Config.TWITCH_CHANNEL]):
            raise ValueError("Missing Twitch configuration")
        
        # Initialize Twitch bot
        twitch_bot = TwitchModeratorBot(command_callback=self._on_command_executed)
        success = await twitch_bot.initialize()
        
        if success:
            self.bots[Platform.TWITCH] = twitch_bot
            
            # Initialize username logger for Twitch
            twitch_logger = UsernameLogger(max_usernames=50, update_interval=0.5)
            self.username_loggers[Platform.TWITCH] = twitch_logger
            
            # Initialize AI helper for Twitch
            twitch_ai_helper = AIModerationHelper(twitch_logger)
            self.ai_helpers[Platform.TWITCH] = twitch_ai_helper
            
            logger.info("✅ Twitch platform initialized")
        else:
            raise Exception("Failed to initialize Twitch bot")
    
    async def _initialize_kick(self):
        """Initialize Kick platform"""
        # Validate Kick configuration
        if not all([Config.KICK_CLIENT_ID, Config.KICK_CLIENT_SECRET, Config.KICK_CHANNEL]):
            raise ValueError("Missing Kick configuration")
        
        # Initialize Kick bot
        kick_bot = KickModeratorBot(command_callback=self._on_command_executed)
        success = await kick_bot.initialize()
        
        if success:
            self.bots[Platform.KICK] = kick_bot
            
            # Initialize Kick username logger (which includes chat monitoring)
            # Pass the authenticated API instance from the bot
            kick_logger = KickUsernameLogger(max_usernames=50, update_interval=0.5, username_callback=self._on_kick_username, kick_api=kick_bot.api)
            await kick_logger.initialize()
            self.username_loggers[Platform.KICK] = kick_logger
            
            # Initialize AI helper for Kick
            kick_ai_helper = KickAIModerationHelper(kick_logger)
            self.ai_helpers[Platform.KICK] = kick_ai_helper
            
            logger.info("✅ Kick platform initialized")
        else:
            raise Exception("Failed to initialize Kick bot")
    
    async def start(self):
        """Start all enabled platforms"""
        try:
            self.is_running = True
            
            # Start platform-specific services
            tasks = []
            
            if Platform.TWITCH in self.enabled_platforms:
                # Start Twitch username monitoring
                twitch_logger = self.username_loggers[Platform.TWITCH]
                tasks.append(asyncio.create_task(twitch_logger.start_monitoring()))
            
            if Platform.KICK in self.enabled_platforms:
                # Start Kick username monitoring (which includes chat monitoring)
                kick_logger = self.username_loggers[Platform.KICK]
                tasks.append(asyncio.create_task(kick_logger.start_monitoring()))
            
            # Send status messages to all platforms
            await self._send_status_messages()
            
            logger.info(f"✅ Multi-platform bot started on: {[p.value for p in self.enabled_platforms]}")
            
            # Wait for all monitoring tasks
            if tasks:
                await asyncio.gather(*tasks, return_exceptions=True)
                
        except Exception as e:
            logger.error(f"Error starting multi-platform manager: {e}")
            raise
    
    async def stop(self):
        """Stop all platforms"""
        try:
            self.is_running = False
            
            # Stop all bots
            for platform, bot in self.bots.items():
                try:
                    await bot.close()
                    logger.info(f"Stopped {platform.value} bot")
                except Exception as e:
                    logger.error(f"Error stopping {platform.value} bot: {e}")
            
            # Chat monitoring is now handled by username loggers, so no separate chat monitors to stop
            
            # Stop username loggers
            for platform, logger_instance in self.username_loggers.items():
                try:
                    if platform == Platform.KICK and hasattr(logger_instance, 'stop_monitoring'):
                        # Kick logger has async stop_monitoring
                        await logger_instance.stop_monitoring()
                    elif hasattr(logger_instance, 'is_running'):
                        # Twitch logger just needs is_running set to False
                        logger_instance.is_running = False
                    logger.info(f"Stopped {platform.value} username logger")
                except Exception as e:
                    logger.error(f"Error stopping {platform.value} logger: {e}")
            
            logger.info("✅ Multi-platform manager stopped")
            
        except Exception as e:
            logger.error(f"Error stopping multi-platform manager: {e}")
    
    async def execute_command_on_platform(self, cmd: ModerationCommand, platform: Platform) -> bool:
        """Execute a moderation command on a specific platform"""
        logger.info(f"🎯 Executing command '{cmd.action}' on platform: {platform.value}")
        try:
            if platform not in self.enabled_platforms:
                logger.warning(f"Platform {platform.value} is not enabled")
                return False
            
            bot = self.bots.get(platform)
            if not bot:
                logger.error(f"No bot available for platform {platform.value}")
                return False
            
            logger.info(f"🤖 Calling bot.execute_moderation_command for {platform.value}")
            success = await bot.execute_moderation_command(cmd)
            logger.info(f"Command executed on {platform.value}: {success}")
            return success
            
        except Exception as e:
            logger.error(f"Error executing command on {platform.value}: {e}")
            return False
    
    async def execute_command_on_all_platforms(self, cmd: ModerationCommand) -> Dict[Platform, bool]:
        """Execute a moderation command on all enabled platforms"""
        results = {}
        
        for platform in self.enabled_platforms:
            results[platform] = await self.execute_command_on_platform(cmd, platform)
        
        return results
    
    async def execute_command_on_enabled_platforms(self, cmd: ModerationCommand) -> Dict[Platform, bool]:
        """Execute command based on enabled platforms"""
        logger.info(f"🚀 Multi-platform manager executing command '{cmd.action}' on enabled platforms: {[p.value for p in self.enabled_platforms]}")
        
        # Execute on all enabled platforms (not based on environment variable)
        if self.enabled_platforms:
            logger.info(f"📡 Executing on ALL enabled platforms: {[p.value for p in self.enabled_platforms]}")
            return await self.execute_command_on_all_platforms(cmd)
        else:
            logger.warning("No platforms are enabled")
            return {}
    
    def resolve_username_across_platforms(self, partial_username: str) -> Optional[str]:
        """
        Try to resolve username across all enabled platforms.
        Returns the first successful match found.
        """
        logger.debug(f"🔍 Resolving username '{partial_username}' across platforms: {[p.value for p in self.enabled_platforms]}")
        
        for platform in self.enabled_platforms:
            ai_helper = self.ai_helpers.get(platform)
            if ai_helper:
                try:
                    resolved = ai_helper.resolve_username(partial_username)
                    if resolved:
                        logger.info(f"✅ Username '{partial_username}' resolved to '{resolved}' via {platform.value}")
                        return resolved
                    else:
                        logger.debug(f"❌ No match found on {platform.value} for '{partial_username}'")
                except Exception as e:
                    logger.error(f"Error resolving username on {platform.value}: {e}")
        
        logger.warning(f"❌ No username match found across any platform for: '{partial_username}'")
        return None
    
    def resolve_username(self, partial_username: str) -> Optional[str]:
        """Fallback method for single platform resolution (for compatibility)"""
        return self.resolve_username_across_platforms(partial_username)
    
    async def _on_command_executed(self, cmd: ModerationCommand, success: bool):
        """Callback when a command is executed on any platform"""
        if self.command_callback:
            try:
                await self.command_callback(cmd, success)
            except Exception as e:
                logger.error(f"Error in command callback: {e}")
    
    async def _on_kick_username(self, username: str, platform: str):
        """Callback when a username is detected in Kick chat"""
        try:
            # Add to unified username set for cross-platform resolution
            self.unified_usernames.add(username.lower())
            
            # Keep only recent usernames (last 100)
            if len(self.unified_usernames) > 100:
                # Convert to list, keep last 100, convert back to set
                username_list = list(self.unified_usernames)
                self.unified_usernames = set(username_list[-100:])
                
        except Exception as e:
            logger.error(f"Error processing Kick username: {e}")
    
    async def _send_status_messages(self):
        """Send status messages to all platforms"""
        for platform, bot in self.bots.items():
            try:
                await bot.send_status_message()
            except Exception as e:
                logger.error(f"Failed to send status message to {platform.value}: {e}")
    
    def get_platform_status(self) -> Dict[str, Dict]:
        """Get status of all platforms"""
        status = {}
        
        for platform in self.enabled_platforms:
            bot = self.bots.get(platform)
            status[platform.value] = {
                'enabled': True,
                'connected': getattr(bot, 'is_connected', False) if bot else False,
                'bot_available': bot is not None
            }
        
        return status
    
    def get_supported_platforms(self) -> List[str]:
        """Get list of supported platform names"""
        return [platform.value for platform in Platform]
    
    def get_ai_helper_for_platform(self, platform: Platform) -> Optional[object]:
        """Get the AI helper for a specific platform"""
        return self.ai_helpers.get(platform)
    
    def get_primary_ai_helper(self) -> Optional[object]:
        """
        Get the primary AI helper for username resolution.
        If both platforms are enabled, prefer Twitch. Otherwise, return the available one.
        """
        if Platform.TWITCH in self.enabled_platforms:
            return self.ai_helpers.get(Platform.TWITCH)
        elif Platform.KICK in self.enabled_platforms:
            return self.ai_helpers.get(Platform.KICK)
        return None
    
    async def stop_platform(self, platform: str):
        """Stop a single platform (twitch or kick)"""
        plat_enum = Platform.TWITCH if platform == "twitch" else Platform.KICK
        
        # Stop the bot
        bot = self.bots.get(plat_enum)
        if bot:
            await bot.close()
            del self.bots[plat_enum]
            logger.info(f"Stopped {platform} bot")
        
        # Stop the username logger
        logger_instance = self.username_loggers.get(plat_enum)
        if logger_instance:
            try:
                if hasattr(logger_instance, 'stop_monitoring'):
                    # Kick logger has async stop_monitoring
                    await logger_instance.stop_monitoring()
                elif hasattr(logger_instance, 'is_running'):
                    # Twitch logger just needs is_running set to False
                    logger_instance.is_running = False
                logger.info(f"Stopped {platform} username logger")
            except Exception as e:
                logger.error(f"Error stopping {platform} logger: {e}")
            del self.username_loggers[plat_enum]
        
        # Remove from enabled platforms
        if plat_enum in self.enabled_platforms:
            self.enabled_platforms.remove(plat_enum)
        
        # Remove AI helper
        if plat_enum in self.ai_helpers:
            del self.ai_helpers[plat_enum]
        
        logger.info(f"✅ Stopped {platform} platform") 