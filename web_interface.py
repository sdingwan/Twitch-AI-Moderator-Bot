#!/usr/bin/env python3
"""
Web Interface for Twitch AI Moderator Bot
A FastAPI-based web interface to control the bot
"""

import asyncio
import logging
import os
import sys
from typing import Optional, Dict, Any, Set
from datetime import datetime
import json
import threading
from threading import Timer
import time

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
import uvicorn

# Import bot components
from config import Config
from voice_recognition_hf import VoiceRecognitionHF
from command_processor import CommandProcessor, ModerationCommand
from twitch_bot import TwitchModeratorBot
from username_logger import UsernameLogger, AIModerationHelper

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Pydantic models for API
class BotConfig(BaseModel):
    channel: str

class BotStatus(BaseModel):
    is_running: bool
    channel: Optional[str] = None
    voice_active: bool = False
    last_command: Optional[str] = None
    last_command_time: Optional[str] = None

class CommandRequest(BaseModel):
    command: str

# Global bot instance
bot_instance = None
websocket_connections = []

app = FastAPI(title="Twitch AI Moderator Bot", description="Web interface for voice-controlled Twitch moderation")

class WebAIModeratorBot:
    def __init__(self):
        """Initialize the web-controlled Twitch AI Moderator Bot"""
        self.current_channel = None
        self.is_running = False
        self.voice_active = False
        self.last_command = None
        self.last_command_time = None
        self.websockets = set()
        self.event_loop = None
        
        # Components
        self.twitch_bot = None
        self.voice_recognition = None
        self.command_processor = None
        self.username_logger = None
        self.ai_helper = None
        
        # Sentence combining for split commands
        self.pending_command = None
        self.pending_command_time = None
        self.command_timeout = 15.0  # 15 seconds to wait for the next sentence
        self._cleanup_timer = None
        
    async def initialize(self, channel: str):
        """Initialize all components for a specific channel"""
        try:
            # Store reference to the current event loop
            self.event_loop = asyncio.get_running_loop()
            
            # Set the channel
            Config.set_twitch_channel(channel)
            self.current_channel = channel
            
            # Basic validation
            required_vars = ['TWITCH_TOKEN', 'TWITCH_CLIENT_ID', 'TWITCH_CLIENT_SECRET', 'TWITCH_BOT_USERNAME']
            missing_vars = []
            for var in required_vars:
                if not getattr(Config, var):
                    missing_vars.append(var)
            
            if missing_vars:
                raise ValueError(f"Missing required environment variables: {', '.join(missing_vars)}")
            
            # Initialize components
            self.username_logger = UsernameLogger(max_usernames=50, update_interval=0.5)
            self.ai_helper = AIModerationHelper(self.username_logger)
            self.command_processor = CommandProcessor(phonetic_helper=self.ai_helper)
            self.twitch_bot = TwitchModeratorBot(command_callback=self._on_command_executed)
            
            # Initialize voice recognition
            self.voice_recognition = VoiceRecognitionHF(command_callback=self._on_voice_command)
            
            await self.broadcast_status()
            return True
            
        except Exception as e:
            logger.error(f"Failed to initialize bot: {e}")
            await self.broadcast_message(f"❌ Failed to initialize: {e}")
            return False
    
    async def start(self):
        """Start the bot"""
        if not self.current_channel:
            raise ValueError("No channel configured")
            
        try:
            # Ensure we have the event loop reference
            if not self.event_loop:
                self.event_loop = asyncio.get_running_loop()
                
            Config.validate()
            self.is_running = True
            
            # Initialize Twitch bot
            if not await self.twitch_bot.initialize():
                await self.broadcast_message("❌ Failed to connect to Twitch API")
                return False
            
            # Start username logger
            if self.username_logger:
                self.username_logger_task = asyncio.create_task(self.username_logger.start_monitoring())
            
            # Send startup message to chat
            await self.twitch_bot.send_status_message()
            
            # Automatically start voice recognition when bot starts
            if self.voice_recognition:
                self.voice_recognition.start_listening()
                self.voice_active = True
            
            # Single consolidated message
            await self.broadcast_message(f"✅ Bot started for channel: {self.current_channel} (Voice recognition active)")
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
        
        # Stop components
        if self.username_logger:
            self.username_logger.stop_monitoring()
            if self.username_logger_task:
                self.username_logger_task.cancel()
                try:
                    await self.username_logger_task
                except asyncio.CancelledError:
                    pass
        
        if self.twitch_bot:
            await self.twitch_bot.close()
        
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
                    success = await self.twitch_bot.execute_moderation_command(moderation_cmd)
                    if success:
                        await self.broadcast_message(f"✅ Executed: {command_text}")
                    else:
                        await self.broadcast_message(f"❌ Execution failed: {command_text}")
                else:
                    # Check if this is a username resolution failure for dangerous actions
                    if ("username not found in recent chat" in error_msg and 
                        moderation_cmd.action in ['ban', 'timeout', 'restrict']):
                        # Send message to Twitch chat about the failed resolution
                        original_username = moderation_cmd.original_username or moderation_cmd.username
                        await self.twitch_bot.send_username_not_found_message(original_username, moderation_cmd.action)
                    
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
                    # Check if this is a username resolution failure for dangerous actions
                    if ("username not found in recent chat" in error_msg and 
                        moderation_cmd.action in ['ban', 'timeout', 'restrict']):
                        # Send message to Twitch chat about the failed resolution
                        original_username = moderation_cmd.original_username or moderation_cmd.username
                        self._schedule_coroutine(
                            self.twitch_bot.send_username_not_found_message(original_username, moderation_cmd.action)
                        )
                    
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
            
            success = await self.twitch_bot.execute_moderation_command(cmd)
            if success:
                # Show the actual command that was executed, not the full "Hey Brian" text
                actual_command = Config.extract_command_after_keyword(original_command)
                if not actual_command:  # Fallback to original if extraction fails
                    actual_command = original_command
                
                await self.broadcast_message(f"✅ Executed: {actual_command}")
            else:
                await self.broadcast_message(f"❌ Command failed")
        except Exception as e:
            await self.broadcast_message(f"❌ Error executing command: {e}")
    
    def _on_command_executed(self, cmd: ModerationCommand, success: bool):
        """Callback for when a command is executed"""
        status = "✅ SUCCESS" if success else "❌ FAILED"
        logger.info(f"Command execution {status}: {cmd.action} on {cmd.username}")
    
    def get_status(self) -> BotStatus:
        """Get current bot status"""
        return BotStatus(
            is_running=self.is_running,
            channel=self.current_channel,
            voice_active=self.voice_active,
            last_command=self.last_command,
            last_command_time=self.last_command_time
        )
    
    async def broadcast_status(self):
        """Broadcast status to all connected websockets"""
        status = self.get_status()
        await self.broadcast_data({"type": "status", "data": status.dict()})
    
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
        
        # Initialize with the channel
        success = await bot_instance.initialize(config.channel)
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
        raise HTTPException(status_code=400, detail=str(e))

@app.get("/api/status")
async def get_status():
    """Get bot status"""
    global bot_instance
    
    if not bot_instance:
        return BotStatus(is_running=False, channel=None, voice_active=False, last_command=None, last_command_time=None).dict()
    
    return bot_instance.get_status().dict()

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket endpoint for real-time updates"""
    await websocket.accept()
    websocket_connections.append(websocket)
    
    # Send initial status
    if bot_instance:
        await bot_instance.broadcast_status()
    
    try:
        while True:
            # Keep connection alive
            await websocket.receive_text()
    except WebSocketDisconnect:
        if websocket in websocket_connections:
            websocket_connections.remove(websocket)

@app.get("/", response_class=HTMLResponse)
async def get_index():
    """Serve the main web interface"""
    return """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Twitch AI Moderator Bot</title>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        
        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            color: #333;
        }
        
        .container {
            max-width: 1200px;
            margin: 0 auto;
            padding: 20px;
        }
        
        .header {
            text-align: center;
            color: white;
            margin-bottom: 30px;
        }
        
        .header h1 {
            font-size: 2.5em;
            margin-bottom: 10px;
        }
        
        .header p {
            font-size: 1.2em;
            opacity: 0.9;
        }
        
        .card {
            background: white;
            border-radius: 15px;
            padding: 25px;
            margin-bottom: 20px;
            box-shadow: 0 10px 30px rgba(0,0,0,0.1);
        }
        
        .status-card {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 20px;
        }
        
        .status-item {
            text-align: center;
            padding: 15px;
            border-radius: 10px;
            background: #f8f9fa;
        }
        
        .status-item.active {
            background: #d4edda;
            color: #155724;
        }
        
        .status-item.inactive {
            background: #f8d7da;
            color: #721c24;
        }
        
        .controls {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 20px;
        }
        
        @media (max-width: 768px) {
            .controls {
                grid-template-columns: 1fr;
            }
        }
        
        .control-group {
            background: #f8f9fa;
            padding: 20px;
            border-radius: 10px;
            height: 500px;
            display: flex;
            flex-direction: column;
        }
        
        .control-group h3 {
            margin-bottom: 15px;
            color: #495057;
        }
        
        .activity-section {
            background: #f8f9fa;
            padding: 20px;
            border-radius: 10px;
            height: 500px;
            display: flex;
            flex-direction: column;
        }
        
        .activity-section h3 {
            margin-bottom: 15px;
            color: #495057;
        }
        
        input, button, textarea {
            width: 100%;
            padding: 12px;
            border: 1px solid #ddd;
            border-radius: 8px;
            font-size: 14px;
            margin-bottom: 10px;
        }
        
        button {
            background: #007bff;
            color: white;
            border: none;
            cursor: pointer;
            transition: background 0.3s;
        }
        
        button:hover {
            background: #0056b3;
        }
        
        button:disabled {
            background: #6c757d;
            cursor: not-allowed;
        }
        
        .btn-success {
            background: #28a745;
        }
        
        .btn-success:hover {
            background: #1e7e34;
        }
        
        .btn-danger {
            background: #dc3545;
        }
        
        .btn-danger:hover {
            background: #c82333;
        }
        
        .btn-warning {
            background: #ffc107;
            color: #212529;
        }
        
        .btn-warning:hover {
            background: #e0a800;
        }
        
        .log {
            background: #1e1e1e;
            color: #fff;
            padding: 20px;
            border-radius: 10px;
            flex: 1;
            overflow-y: auto;
            font-family: 'Courier New', monospace;
            font-size: 13px;
            line-height: 1.4;
        }
        
        .log-entry {
            margin-bottom: 5px;
            padding: 5px;
            border-radius: 3px;
        }
        
        .log-entry.success {
            background: rgba(40, 167, 69, 0.2);
        }
        
        .log-entry.error {
            background: rgba(220, 53, 69, 0.2);
        }
        
        .log-entry.info {
            background: rgba(23, 162, 184, 0.2);
        }
        
        .timestamp {
            opacity: 0.7;
            font-size: 11px;
        }
        
        .examples {
            background: #e9ecef;
            padding: 15px;
            border-radius: 8px;
            margin-top: 10px;
        }
        
        .examples h4 {
            margin-bottom: 10px;
            color: #495057;
        }
        
        .examples ul {
            list-style: none;
            padding-left: 0;
        }
        
        .examples li {
            padding: 5px 0;
            color: #6c757d;
        }
        
        .examples li:before {
            content: "• ";
            color: #007bff;
            font-weight: bold;
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>Twitch AI Moderator Bot</h1>
            <p>Voice-controlled Twitch Moderation</p>
        </div>
        
        <div class="card">
            <h2>Bot Status</h2>
            <div class="status-card">
                <div class="status-item" id="bot-status">
                    <h3>Bot Status</h3>
                    <div id="bot-running">Stopped</div>
                </div>
                <div class="status-item" id="voice-status">
                    <h3>Voice Recognition</h3>
                    <div id="voice-active">Inactive</div>
                </div>
                <div class="status-item" id="channel-status">
                    <h3>Channel</h3>
                    <div id="current-channel">Not configured</div>
                </div>
                <div class="status-item" id="last-command-status">
                    <h3>Last Command</h3>
                    <div id="last-command">None</div>
                </div>
            </div>
        </div>
        
        <div class="card">
            <h2>Controls</h2>
            <div class="controls">
                <div class="control-group">
                    <h3>Bot Control</h3>
                    <input type="text" id="channel-input" placeholder="Enter Twitch channel">
                    <button onclick="startBot()" class="btn-success">Start Bot</button>
                    <button onclick="stopBot()" class="btn-danger">Stop Bot</button>
                    <div class="examples">
                        <h4>Voice Commands:</h4>
                        <ul>
                            <li>"Hey Brian, ban username123"</li>
                            <li>"Hey Brian, timeout spammer for 10 minutes"</li>
                            <li>"Hey Brian, clear chat"</li>
                            <li>"Hey Brian, slow mode 30 seconds"</li>
                            <li>"Hey Brian, followers only mode"</li>
                            <li>"Hey Brian, subscribers only mode"</li>
                            <li>"Hey Brian, change weather to Naples, Italy"</li>
                            <li>"Hey Brian, set weather to Tokyo, Japan"</li>
                        </ul>
                    </div>
                </div>
                
                <div class="activity-section">
                    <h3>Activity Log</h3>
                    <div class="log" id="activity-log">
                        <div class="log-entry info">
                            <span class="timestamp">[System]</span> Web interface loaded. Configure a channel to get started.
                        </div>
                    </div>
                </div>
            </div>
        </div>
    </div>

    <script>
        let ws = null;
        
        function connectWebSocket() {
            const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
            ws = new WebSocket(`${protocol}//${window.location.host}/ws`);
            
            ws.onopen = function() {
                addLogEntry('Connected to bot', 'info');
            };
            
            ws.onmessage = function(event) {
                const data = JSON.parse(event.data);
                
                if (data.type === 'status') {
                    updateStatus(data.data);
                } else if (data.type === 'message') {
                    addLogEntry(data.data, getLogType(data.data), data.timestamp);
                }
            };
            
            ws.onclose = function() {
                addLogEntry('Disconnected from bot', 'error');
                setTimeout(connectWebSocket, 3000);
            };
        }
        
        function updateStatus(status) {
            // Bot status
            const botStatus = document.getElementById('bot-status');
            const botRunning = document.getElementById('bot-running');
            botRunning.textContent = status.is_running ? 'Running' : 'Stopped';
            botStatus.className = 'status-item ' + (status.is_running ? 'active' : 'inactive');
            
            // Voice status
            const voiceStatus = document.getElementById('voice-status');
            const voiceActive = document.getElementById('voice-active');
            voiceActive.textContent = status.voice_active ? 'Active' : 'Inactive';
            voiceStatus.className = 'status-item ' + (status.voice_active ? 'active' : 'inactive');
            
            // Channel status
            const channelStatus = document.getElementById('channel-status');
            const currentChannel = document.getElementById('current-channel');
            currentChannel.textContent = status.channel || 'Not configured';
            channelStatus.className = 'status-item ' + (status.channel ? 'active' : 'inactive');
            
            // Last command
            const lastCommand = document.getElementById('last-command');
            if (status.last_command) {
                const time = status.last_command_time ? new Date(status.last_command_time).toLocaleTimeString() : '';
                lastCommand.textContent = `${status.last_command} (${time})`;
            } else {
                lastCommand.textContent = 'None';
            }
        }
        
        function getLogType(message) {
            if (message.includes('✅')) return 'success';
            if (message.includes('❌')) return 'error';
            return 'info';
        }
        
        function addLogEntry(message, type = 'info', timestamp = null) {
            const log = document.getElementById('activity-log');
            const entry = document.createElement('div');
            entry.className = `log-entry ${type}`;
            
            const time = timestamp ? new Date(timestamp).toLocaleTimeString() : new Date().toLocaleTimeString();
            entry.innerHTML = `<span class="timestamp">[${time}]</span> ${message}`;
            
            log.appendChild(entry);
            log.scrollTop = log.scrollHeight;
        }
        
        async function apiCall(endpoint, method = 'GET', data = null) {
            try {
                const options = {
                    method,
                    headers: {
                        'Content-Type': 'application/json',
                    },
                };
                
                if (data) {
                    options.body = JSON.stringify(data);
                }
                
                const response = await fetch(endpoint, options);
                const result = await response.json();
                
                if (!response.ok) {
                    throw new Error(result.detail || 'API call failed');
                }
                
                return result;
            } catch (error) {
                addLogEntry(`❌ ${error.message}`, 'error');
                throw error;
            }
        }
        
        async function startBot() {
            const channel = document.getElementById('channel-input').value.trim();
            if (!channel) {
                addLogEntry('❌ Please enter a channel name', 'error');
                return;
            }
            
            try {
                const result = await apiCall('/api/start', 'POST', { channel });
                // Only show message if it's not empty
                if (result.message) {
                    addLogEntry(result.message, 'success');
                }
            } catch (error) {
                // Error already logged in apiCall
            }
        }
        
        async function stopBot() {
            try {
                const result = await apiCall('/api/stop', 'POST');
                // Only show message if it's not empty
                if (result.message) {
                    addLogEntry(result.message, 'success');
                }
            } catch (error) {
                // Error already logged in apiCall
            }
        }
        
        // Initialize
        connectWebSocket();
        
        // Load initial status
        fetch('/api/status')
            .then(response => response.json())
            .then(status => updateStatus(status))
            .catch(error => addLogEntry('❌ Failed to load initial status', 'error'));
        
        // Allow Enter key to start bot
        document.getElementById('channel-input').addEventListener('keypress', function(e) {
            if (e.key === 'Enter') {
                e.preventDefault();
                startBot();
            }
        });
    </script>
</body>
</html>
    """

if __name__ == "__main__":
    print("🌐 Starting Twitch AI Moderator Bot Web Interface...")
    print("📱 Open your browser to: http://localhost:8000")
    print("🎤 Configure your channel and start moderating!")
    
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info") 