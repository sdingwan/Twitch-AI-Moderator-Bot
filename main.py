#!/usr/bin/env python3
"""
AI Moderator Bot - Voice Command Twitch Moderation
A simple Twitch chat moderation bot that responds to voice commands using cloud-hosted Whisper Large V3
"""

import asyncio
import logging
import signal
import sys
import os
from typing import Optional

# Set up clean logging (suppress HTTP request spam)
os.environ['HTTPX_LOG_LEVEL'] = 'ERROR'
os.environ['HTTPCORE_LOG_LEVEL'] = 'ERROR'

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('moderator_bot.log'),
        logging.StreamHandler(sys.stdout)
    ]
)

# Disable noisy HTTP logs
logging.getLogger('httpx').disabled = True
logging.getLogger('httpcore').disabled = True
logging.getLogger('openai').setLevel(logging.WARNING)
logging.getLogger('urllib3').setLevel(logging.WARNING)

from config import Config
from voice_recognition_hf import VoiceRecognitionHF
from command_processor import CommandProcessor, ModerationCommand
from twitch_bot import TwitchModeratorBot

logger = logging.getLogger(__name__)

class AIModeratorBot:
    def __init__(self):
        """Initialize the AI Moderator Bot"""
        self.voice_recognition = None
        self.command_processor = None
        self.twitch_bot = None
        self.is_running = False
        self.bot_task = None
        self.event_loop = None  # Store reference to the main event loop
        
        # Setup signal handlers for graceful shutdown
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
    
    async def initialize(self):
        """Initialize all components"""
        try:
            # Validate configuration
            Config.validate()
            logger.info("Configuration validated successfully")
            
            # Initialize command processor
            self.command_processor = CommandProcessor()
            logger.info("Command processor initialized")
            
            # Initialize Twitch bot
            self.twitch_bot = TwitchModeratorBot(command_callback=self._on_command_executed)
            logger.info("Twitch bot initialized")
            
            # Initialize voice recognition with Hugging Face
            self.voice_recognition = VoiceRecognitionHF(command_callback=self._on_voice_command)
            logger.info("Voice recognition initialized")
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to initialize bot: {e}")
            return False
    
    async def start(self):
        """Start the AI Moderator Bot"""
        if not await self.initialize():
            logger.error("Failed to initialize bot components")
            return False
        
        try:
            logger.info("Starting AI Moderator Bot...")
            self.is_running = True
            
            # Store reference to the current event loop
            self.event_loop = asyncio.get_running_loop()
            
            # Initialize Twitch bot
            if not await self.twitch_bot.initialize():
                logger.error("Failed to connect to Twitch API")
                return False
            
            # Start voice recognition
            self.voice_recognition.start_listening()
            
            # Send startup message to chat
            await self.twitch_bot.send_status_message()
            
            logger.info("🎤 AI Moderator Bot is now running!")
            logger.info("🎯 Voice commands are active. Say 'Hey Brian' followed by your command.")
            logger.info("📝 Example: 'Hey Brian, ban username123 for 10 minutes'")
            logger.info("🔗 Using Twitch Helix API with cloud-hosted Whisper Large V3 for voice recognition")
            
            # Keep the main thread alive
            while self.is_running:
                await asyncio.sleep(1)
            
            return True
            
        except Exception as e:
            logger.error(f"Error starting bot: {e}")
            return False
    
    async def stop(self):
        """Stop the AI Moderator Bot"""
        logger.info("Stopping AI Moderator Bot...")
        self.is_running = False
        
        # Stop voice recognition
        if self.voice_recognition:
            self.voice_recognition.stop_listening()
        
        # Stop Twitch bot
        if self.twitch_bot:
            await self.twitch_bot.close()
        
        logger.info("AI Moderator Bot stopped")
    
    def _on_voice_command(self, command_text: str):
        """Handle voice commands"""
        logger.info(f"Processing voice command: {command_text}")
        
        # Process the command
        moderation_cmd = self.command_processor.process_command(command_text)
        
        if moderation_cmd:
            # Validate the command
            is_valid, error_msg = self.command_processor.validate_command(moderation_cmd)
            
            if is_valid:
                # Schedule the command execution in the main event loop
                if self.event_loop and not self.event_loop.is_closed():
                    try:
                        future = asyncio.run_coroutine_threadsafe(
                            self._execute_command_async(moderation_cmd), 
                            self.event_loop
                        )
                        logger.debug(f"Command scheduled for execution: {moderation_cmd.action}")
                    except Exception as e:
                        logger.error(f"Failed to schedule command execution: {e}")
                else:
                    logger.error("Event loop not available for command execution")
            else:
                logger.warning(f"Invalid command: {error_msg}")
        else:
            logger.warning(f"Could not understand command: {command_text}")
    
    async def _execute_command_async(self, cmd: ModerationCommand):
        """Execute a moderation command asynchronously"""
        try:
            success = await self.twitch_bot.execute_moderation_command(cmd)
            if success:
                logger.info(f"✅ Command executed successfully: {cmd.action}")
            else:
                logger.error(f"❌ Command execution failed: {cmd.action}")
        except Exception as e:
            logger.error(f"Error executing command: {e}")
    
    def _on_command_executed(self, cmd: ModerationCommand, success: bool):
        """Callback for when a command is executed"""
        status = "✅ SUCCESS" if success else "❌ FAILED"
        logger.info(f"Command execution {status}: {cmd.action} on {cmd.username}")
    
    def _signal_handler(self, signum, frame):
        """Handle shutdown signals"""
        logger.info(f"Received signal {signum}, shutting down...")
        self.is_running = False
    
    def test_microphone(self):
        """Test microphone functionality"""
        if not self.voice_recognition:
            self.voice_recognition = VoiceRecognitionHF(lambda x: None)
        
        return self.voice_recognition.test_microphone()
    
    def list_microphones(self):
        """List available microphones"""
        return VoiceRecognitionHF.list_microphones()

async def main():
    """Main entry point"""
    bot = AIModeratorBot()
    
    # Check if user wants to test microphone
    if len(sys.argv) > 1:
        if sys.argv[1] == '--test-mic':
            print("Testing microphone...")
            bot.test_microphone()
            return
        elif sys.argv[1] == '--list-mics':
            print("Listing available microphones...")
            bot.list_microphones()
            return
        elif sys.argv[1] == '--help':
            print("AI Moderator Bot - Voice Command Twitch Moderation")
            print("Powered by cloud-hosted Whisper Large V3 + Twitch Helix API")
            print("\nUsage:")
            print("  python main.py              - Start the bot")
            print("  python main.py --test-mic   - Test microphone with cloud-hosted Whisper Large V3")
            print("  python main.py --list-mics  - List available microphones")
            print("  python main.py --help       - Show this help")
            print("\nVoice Commands:")
            print("  'Hey Brian, ban [username] for [duration]'")
            print("  'Hey Brian, timeout [username] for [duration]'")
            print("  'Hey Brian, unban [username]'")
            print("  'Hey Brian, clear chat'")
            print("  'Hey Brian, slow mode 30'")
            print("  'Hey Brian, followers only mode'")
            print("  'Hey Brian, subscribers only mode'")
            print("\nFeatures:")
            print("  🎤 Cloud-hosted Whisper Large V3 for fast and accurate voice recognition")
            print("  🚀 Twitch Helix API for reliable moderation")
            print("  🤖 OpenAI GPT for complex command understanding")
            print("  ☁️ Cloud-based processing with no heavy local models")
            return
    
    try:
        # Start the bot
        success = await bot.start()
        if not success:
            logger.error("Failed to start bot")
            sys.exit(1)
    except KeyboardInterrupt:
        logger.info("Received keyboard interrupt")
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
    finally:
        await bot.stop()

if __name__ == "__main__":
    # Run the main function
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nShutdown complete.")
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        sys.exit(1) 