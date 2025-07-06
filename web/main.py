#!/usr/bin/env python3
"""
Backend API for Twitch AI Moderator Bot
A FastAPI-based backend to control the bot
"""

import asyncio
import logging
import os
import sys
from typing import Optional, Dict, Any, Set, List
from datetime import datetime
import json
import threading
from threading import Timer
import time

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
import uvicorn

# Import bot components
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from src.core.config import Config
from src.voice.voice_recognition_hf import VoiceRecognitionHF
from src.core.command_processor import CommandProcessor, ModerationCommand
from src.core.multi_platform_manager import MultiPlatformManager, Platform
from src.platforms.twitch.twitch_bot import TwitchModeratorBot
from src.utils.username_logger import UsernameLogger, AIModerationHelper

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Pydantic models for API
class BotConfig(BaseModel):
    twitch_channel: Optional[str] = None
    kick_channel: Optional[str] = None
    platforms: List[str] = ['twitch']  # Default to Twitch only

class BotStatus(BaseModel):
    is_running: bool
    channel: Optional[str] = None  # For backward compatibility
    voice_active: bool = False
    last_command: Optional[str] = None
    last_command_time: Optional[str] = None
    enabled_platforms: List[str] = []
    current_channels: Dict[str, str] = {}
    platform_status: Dict[str, Dict] = {}

class CommandRequest(BaseModel):
    command: str

# Global bot instance
bot_instance = None
websocket_connections = []

app = FastAPI(title="Twitch AI Moderator Bot", description="Web interface for voice-controlled Twitch moderation")

class WebAIModeratorBot:
    def __init__(self):
        """Initialize the web-controlled Multi-Platform AI Moderator Bot"""
        self.current_channels = {}
        self.enabled_platforms = []
        self.is_running = False
        self.voice_active = False
        self.last_command = None
        self.last_command_time = None
        self.websockets = set()
        self.event_loop = None
        
        # Components
        self.multi_platform_manager = None
        self.voice_recognition = None
        self.command_processor = None
        
        # Sentence combining for split commands
        self.pending_command = None
        self.pending_command_time = None
        self.command_timeout = 15.0  # 15 seconds to wait for the next sentence
        self._cleanup_timer = None
        
    async def initialize(self, config: BotConfig):
        """Initialize all components for specified platforms and channels"""
        try:
            # Store reference to the current event loop
            self.event_loop = asyncio.get_running_loop()
            
            # Set channels for enabled platforms
            self.enabled_platforms = config.platforms
            self.current_channels = {}
            
            logger.info(f"🔧 Initializing bot with platforms: {config.platforms}")
            
            if 'twitch' in config.platforms and config.twitch_channel:
                Config.set_twitch_channel(config.twitch_channel)
                self.current_channels['twitch'] = config.twitch_channel
                logger.info(f"🔧 Twitch channel set to: {config.twitch_channel}")
            
            if 'kick' in config.platforms and config.kick_channel:
                Config.set_kick_channel(config.kick_channel)
                self.current_channels['kick'] = config.kick_channel
                logger.info(f"🔧 Kick channel set to: {config.kick_channel}")
            
            # Validate platform-specific configuration
            missing_vars = self._validate_platform_config(config.platforms)
            if missing_vars:
                raise ValueError(f"Missing required environment variables: {', '.join(missing_vars)}")
            
            # Initialize multi-platform manager
            self.multi_platform_manager = MultiPlatformManager(command_callback=self._on_command_executed)
            success = await self.multi_platform_manager.initialize(config.platforms)
            
            if not success:
                raise Exception("Failed to initialize multi-platform manager")
            
            # Initialize command processor with the multi-platform manager
            from src.core.command_processor import CommandProcessor
            self.command_processor = CommandProcessor()
            
            # Set up the multi-platform manager for cross-platform username resolution
            if self.multi_platform_manager:
                self.command_processor.set_phonetic_helper(self.multi_platform_manager)
            
            # Initialize voice recognition
            self.voice_recognition = VoiceRecognitionHF(command_callback=self._on_voice_command)
            
            await self.broadcast_status()
            return True
            
        except Exception as e:
            logger.error(f"Failed to initialize bot: {e}")
            await self.broadcast_message(f"❌ Failed to initialize: {e}")
            return False
    
    def _validate_platform_config(self, platforms: List[str]) -> List[str]:
        """Validate configuration for enabled platforms"""
        missing_vars = []
        
        if 'twitch' in platforms:
            twitch_vars = ['TWITCH_TOKEN', 'TWITCH_CLIENT_ID', 'TWITCH_CLIENT_SECRET', 'TWITCH_BOT_USERNAME']
            for var in twitch_vars:
                if not getattr(Config, var):
                    missing_vars.append(var)
        
        if 'kick' in platforms:
            kick_vars = ['KICK_CLIENT_ID', 'KICK_CLIENT_SECRET']
            for var in kick_vars:
                if not getattr(Config, var):
                    missing_vars.append(var)
        
        return missing_vars
    
    async def start(self):
        """Start the bot"""
        if not self.current_channels:
            raise ValueError("No channels configured")
            
        try:
            # Ensure we have the event loop reference
            if not self.event_loop:
                self.event_loop = asyncio.get_running_loop()
                
            self.is_running = True
            
            # Start multi-platform manager
            if self.multi_platform_manager:
                # Start platforms in background task
                asyncio.create_task(self.multi_platform_manager.start())
            
            # Automatically start voice recognition when bot starts
            if self.voice_recognition:
                self.voice_recognition.start_listening()
                self.voice_active = True
            
            # Single consolidated message
            platforms_str = ", ".join(self.enabled_platforms)
            channels_str = ", ".join([f"{p}: {c}" for p, c in self.current_channels.items()])
            await self.broadcast_message(f"✅ Bot started on {platforms_str} - Channels: {channels_str} (Voice recognition active)")
            await self.broadcast_status()
            return True
            
        except Exception as e:
            await self.broadcast_message(f"❌ Error starting bot: {e}")
            return False
    
    async def stop(self):
        """Stop the bot"""
        self.is_running = False
        self.voice_active = False
        
        # Clear any pending commands
        self._clear_pending_command()
        
        # Stop voice recognition first
        if self.voice_recognition:
            self.voice_recognition.stop_listening()
        
        # Stop multi-platform manager
        if self.multi_platform_manager:
            await self.multi_platform_manager.stop()
        
        # Single consolidated message
        await self.broadcast_message("✅ Bot stopped")
        await self.broadcast_status()
    
    def start_voice(self):
        """Start voice recognition"""
        if self.voice_recognition and self.is_running:
            self.voice_recognition.start_listening()
            self.voice_active = True
            self._schedule_coroutine(self.broadcast_message("🎤 Voice recognition started"))
            self._schedule_coroutine(self.broadcast_status())
    
    def stop_voice(self):
        """Stop voice recognition"""
        if self.voice_recognition:
            self.voice_recognition.stop_listening()
            self.voice_active = False
            self._schedule_coroutine(self.broadcast_message("🔇 Voice recognition stopped"))
            self._schedule_coroutine(self.broadcast_status())
    
    def _schedule_coroutine(self, coro):
        """Schedule a coroutine to run in the main event loop from any thread"""
        if self.event_loop and not self.event_loop.is_closed():
            try:
                asyncio.run_coroutine_threadsafe(coro, self.event_loop)
            except Exception as e:
                logger.error(f"Failed to schedule coroutine: {e}")

    def _clear_pending_command(self):
        """Clear the pending command and cancel any cleanup timer"""
        self.pending_command = None
        self.pending_command_time = None
        if self._cleanup_timer:
            self._cleanup_timer.cancel()
            self._cleanup_timer = None
    
    def _start_command_timeout(self):
        """Start a timer to clean up the pending command after timeout"""
        if self._cleanup_timer:
            self._cleanup_timer.cancel()
        
        def cleanup():
            logger.debug("Command timeout reached, clearing pending command")
            self._clear_pending_command()
        
        self._cleanup_timer = Timer(self.command_timeout, cleanup)
        self._cleanup_timer.start()
    
    def _store_pending_command(self, command_text: str):
        """Store a command that wasn't recognized, waiting for continuation"""
        self.pending_command = command_text
        self.pending_command_time = time.time()
        
        # Update last command since this contains the activation keyword
        self.last_command = command_text
        self.last_command_time = datetime.now().isoformat()
        
        self._start_command_timeout()
        logger.info(f"Stored incomplete command, waiting for continuation: {command_text}")
    
    def _combine_with_pending(self, new_text: str) -> str:
        """Combine the pending command with new text"""
        if not self.pending_command:
            return new_text
        
        # Combine the texts
        combined = f"{self.pending_command} {new_text}"
        logger.debug(f"Combined: '{self.pending_command}' + '{new_text}' = '{combined}'")
        return combined
    
    async def execute_text_command(self, command_text: str):
        """Execute a text command"""
        try:
            self.last_command = command_text
            self.last_command_time = datetime.now().isoformat()
            
            # Process the command
            moderation_cmd = self.command_processor.process_command(command_text)
            
            if moderation_cmd:
                # Show AI matching result if username was resolved
                if moderation_cmd.original_username and moderation_cmd.username != moderation_cmd.original_username:
                    await self.broadcast_message(f"🤖 AI match: '{moderation_cmd.original_username}' → '{moderation_cmd.username}'")
                
                # Validate the command
                is_valid, error_msg = self.command_processor.validate_command(moderation_cmd)
                
                if is_valid:
                    # Execute command using the multi-platform manager
                    if self.multi_platform_manager:
                        results = await self.multi_platform_manager.execute_command_on_enabled_platforms(moderation_cmd)
                        for platform, success in results.items():
                            platform_name = platform.value
                            if success:
                                await self.broadcast_message(f"✅ {platform_name}: {command_text}")
                            else:
                                await self.broadcast_message(f"❌ {platform_name}: {command_text}")
                    else:
                        await self.broadcast_message(f"❌ Multi-platform manager not initialized")
                else:
                    # If this is a username resolution failure for dangerous actions, notify chat on all relevant platforms
                    if ("username not found in recent chat" in error_msg and 
                        moderation_cmd.action in ['ban', 'timeout', 'restrict']):
                        original_username = moderation_cmd.original_username or moderation_cmd.username
                        # Notify all enabled platforms
                        if self.multi_platform_manager:
                            for platform, bot in self.multi_platform_manager.bots.items():
                                # Only notify platforms where the command would apply
                                if hasattr(bot, 'send_username_not_found_message'):
                                    # Schedule the coroutine for async method
                                    self._schedule_coroutine(bot.send_username_not_found_message(original_username, moderation_cmd.action))
                    await self.broadcast_message(f"❌ Invalid command: {error_msg}")
            else:
                await self.broadcast_message(f"❓ Could not understand command: {command_text}")
            
            await self.broadcast_status()
            
        except Exception as e:
            await self.broadcast_message(f"❌ Error executing command: {e}")
    
    def _on_voice_command(self, command_text: str):
        """Handle voice commands - called from voice recognition thread"""
        try:
            # Only log commands with activation keywords to reduce noise
            has_activation_keyword, _, _ = Config.find_activation_keyword(command_text)
            if has_activation_keyword:
                logger.info(f"🎤 Voice: '{command_text}'")
            
            # Check if we have a pending command to combine with
            if self.pending_command:
                if has_activation_keyword:
                    logger.debug("🔄 Replacing pending command with new one")
                    self._clear_pending_command()
                    self._process_single_command(command_text, is_combined=False)
                else:
                    # Combine with the pending command
                    logger.info(f"🔗 Combining commands")
                    combined_command = self._combine_with_pending(command_text)
                    self._clear_pending_command()
                    
                    # Process the combined command
                    self._process_single_command(combined_command, is_combined=True)
                return
            
            # Process as a single command
            self._process_single_command(command_text, is_combined=False)
            
        except Exception as e:
            logger.error(f"Error in voice command handler: {e}")
            self._schedule_coroutine(self.broadcast_message(f"❌ Error processing voice command: {e}"))
    
    def _process_single_command(self, command_text: str, is_combined: bool = False):
        """Process a single command, with logic for handling incomplete commands"""
        try:
            # Only process commands that contain activation keyword OR are combined commands
            has_activation_keyword, _, _ = Config.find_activation_keyword(command_text)
            
            if not has_activation_keyword and not is_combined:
                # Regular speech without activation keyword and not a combined command - ignore it
                return
            
            # Extract the actual command part after the activation keyword
            actual_command = command_text
            if has_activation_keyword:
                actual_command = Config.extract_command_after_keyword(command_text)
            else:
                # This is a combined command, extract command from the combined text
                actual_command = Config.extract_command_after_keyword(command_text)
                logger.info(f"🔗 Combined: '{actual_command}'")
            
            # Process the command with AI (only log if we have a command to process)
            if actual_command.strip():
                logger.info(f"🤖 Processing: '{actual_command}'")
            
            moderation_cmd = self.command_processor.process_command(actual_command)
            
            if moderation_cmd:
                # Clear any pending command since we got a valid result
                self._clear_pending_command()
                
                # Show AI matching result if username was resolved
                if moderation_cmd.original_username and moderation_cmd.username != moderation_cmd.original_username:
                    self._schedule_coroutine(self.broadcast_message(f"🤖 AI match: '{moderation_cmd.original_username}' → '{moderation_cmd.username}'"))
                
                # Validate the command
                is_valid, error_msg = self.command_processor.validate_command(moderation_cmd)
                
                if is_valid:
                    self._schedule_coroutine(self._execute_command_async(moderation_cmd, command_text))
                else:
                    # If this is a username resolution failure for dangerous actions, notify chat on all relevant platforms
                    if ("username not found in recent chat" in error_msg and 
                        moderation_cmd.action in ['ban', 'timeout', 'restrict']):
                        original_username = moderation_cmd.original_username or moderation_cmd.username
                        # Notify all enabled platforms
                        if self.multi_platform_manager:
                            for platform, bot in self.multi_platform_manager.bots.items():
                                # Only notify platforms where the command would apply
                                if hasattr(bot, 'send_username_not_found_message'):
                                    # Schedule the coroutine for async method
                                    self._schedule_coroutine(bot.send_username_not_found_message(original_username, moderation_cmd.action))
                    self._schedule_coroutine(self.broadcast_message(f"❌ Invalid command: {error_msg}"))
            else:
                # Command not recognized
                if is_combined:
                    # If this was a combined command and still failed, give up
                    self._schedule_coroutine(self.broadcast_message(f"❓ Could not understand combined command: {actual_command}"))
                elif has_activation_keyword:
                    # Store incomplete commands that contain the activation keyword
                    # This includes cases where someone just says "hey brian" with no command text
                    self._store_pending_command(command_text)
                    if actual_command.strip():
                        logger.info(f"⏳ Waiting for more: '{actual_command}'")
                    else:
                        logger.info(f"⏳ Activation keyword detected, waiting for command")
                    # Don't broadcast the "could not understand" message yet, wait for the next sentence
            
            # Update status but don't broadcast it to reduce noise
            self._schedule_coroutine(self.broadcast_status())
            
        except Exception as e:
            logger.error(f"Error processing command: {e}")
            self._schedule_coroutine(self.broadcast_message(f"❌ Error processing command: {e}"))
    
    async def _execute_command_async(self, cmd: ModerationCommand, original_command: str):
        """Execute a moderation command asynchronously"""
        try:
            # Update last command when we actually execute a valid command
            self.last_command = original_command
            self.last_command_time = datetime.now().isoformat()
            
            # Execute the command on all enabled platforms
            if self.multi_platform_manager:
                results = await self.multi_platform_manager.execute_command_on_enabled_platforms(cmd)
                
                # Show the actual command that was executed, not the full "Hey Brian" text
                actual_command = Config.extract_command_after_keyword(original_command)
                if not actual_command:  # Fallback to original if extraction fails
                    actual_command = original_command
                
                # Report results for each platform
                for platform, success in results.items():
                    platform_name = platform.value
                    if success:
                        await self.broadcast_message(f"✅ {platform_name}: {actual_command}")
                    else:
                        await self.broadcast_message(f"❌ {platform_name}: {actual_command}")
            else:
                await self.broadcast_message(f"❌ Multi-platform manager not initialized")
        except Exception as e:
            await self.broadcast_message(f"❌ Error executing command: {e}")
    
    def _on_command_executed(self, cmd: ModerationCommand, success: bool):
        """Callback for when a command is executed"""
        status = "✅ SUCCESS" if success else "❌ FAILED"
        logger.info(f"Command execution {status}: {cmd.action} on {cmd.username}")
    
    def get_status(self) -> BotStatus:
        """Get current bot status"""
        # Get platform status if multi-platform manager is available
        platform_status = {}
        if self.multi_platform_manager:
            platform_status = self.multi_platform_manager.get_platform_status()
        
        return BotStatus(
            is_running=self.is_running,
            channel=self.current_channels.get('twitch') or list(self.current_channels.values())[0] if self.current_channels else None,
            voice_active=self.voice_active,
            last_command=self.last_command,
            last_command_time=self.last_command_time,
            enabled_platforms=self.enabled_platforms,
            current_channels=self.current_channels,
            platform_status=platform_status
        )
    
    async def broadcast_status(self):
        """Broadcast status to all connected websockets"""
        status = self.get_status()
        await self.broadcast_data({"type": "status", "data": status.model_dump()})
    
    async def broadcast_message(self, message: str):
        """Broadcast a message to all connected websockets"""
        await self.broadcast_data({"type": "message", "data": message, "timestamp": datetime.now().isoformat()})
    
    async def broadcast_data(self, data: Dict[str, Any]):
        """Broadcast data to all connected websockets"""
        if websocket_connections:
            disconnected = []
            for websocket in websocket_connections:
                try:
                    await websocket.send_text(json.dumps(data))
                except:
                    disconnected.append(websocket)
            
            # Remove disconnected websockets
            for ws in disconnected:
                if ws in websocket_connections:
                    websocket_connections.remove(ws)

    async def stop_platform(self, platform: str):
        if self.multi_platform_manager:
            await self.multi_platform_manager.stop_platform(platform)
            
            # Update bot's enabled platforms and channels
            if platform in self.enabled_platforms:
                self.enabled_platforms.remove(platform)
            if platform in self.current_channels:
                del self.current_channels[platform]
                
            # If no platforms are left, mark bot as stopped
            if not self.enabled_platforms:
                self.is_running = False
                self.voice_active = False
                if self.voice_recognition:
                    self.voice_recognition.stop_listening()
                    
        await self.broadcast_message(f"✅ Stopped {platform} platform")
        await self.broadcast_status()

# API Routes
@app.post("/api/start")
async def start_bot(config: BotConfig):
    """Configure and start the bot in one operation"""
    global bot_instance
    
    try:
        # Create or reset bot instance
        if not bot_instance:
            bot_instance = WebAIModeratorBot()
        
        # Stop if already running
        if bot_instance.is_running:
            await bot_instance.stop()
        
        # Initialize with the multi-platform configuration
        success = await bot_instance.initialize(config)
        if not success:
            return {"success": False, "message": "Failed to configure bot"}
        
        # Start the bot (which will also start voice recognition)
        success = await bot_instance.start()
        if success:
            return {"success": True, "message": ""}  # Empty message to avoid duplicate
        else:
            return {"success": False, "message": "Failed to start bot"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/api/stop")
async def stop_bot():
    """Stop the bot"""
    global bot_instance
    
    if not bot_instance:
        raise HTTPException(status_code=400, detail="Bot not configured")
    
    try:
        await bot_instance.stop()
        return {"success": True, "message": ""}  # Empty message to avoid duplicate
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/status")
async def get_status():
    """Get current bot status"""
    global bot_instance
    
    if not bot_instance:
        return BotStatus(is_running=False, channel=None, voice_active=False, last_command=None, last_command_time=None,
                        enabled_platforms=[], current_channels={}, platform_status={}).model_dump()
    
    return bot_instance.get_status().model_dump()

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket endpoint for real-time communication"""
    await websocket.accept()
    websocket_connections.append(websocket)
    
    # Send initial status
    if bot_instance:
        await bot_instance.broadcast_status()
    
    try:
        while True:
            await websocket.receive_text()  # Keep connection alive
    except WebSocketDisconnect:
        if websocket in websocket_connections:
            websocket_connections.remove(websocket)

@app.get("/", response_class=FileResponse)
async def get_index():
    """Serve the main web interface"""
    import os
    # Get the absolute path to frontend.html
    frontend_path = os.path.join(os.path.dirname(__file__), "frontend.html")
    return FileResponse(frontend_path)

@app.post("/api/stop_platform")
async def stop_platform(request: Dict[str, str]):
    """Stop a specific platform (twitch or kick)"""
    global bot_instance
    if not bot_instance or not bot_instance.is_running:
        raise HTTPException(status_code=400, detail="Bot not running")
    platform = request.get("platform")
    if platform not in ["twitch", "kick"]:
        raise HTTPException(status_code=400, detail="Invalid platform")
    try:
        await bot_instance.stop_platform(platform)
        return {"success": True, "message": f"Stopped {platform}"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    print("🌐 Starting Multi-Platform AI Moderator Bot Web Interface...")
    print("📱 Open your browser to: http://localhost:8000")
    print("🎤 Configure your platforms and channels to start moderating!")
    print("🤖 Supports Twitch and Kick.com!")
    
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info") 