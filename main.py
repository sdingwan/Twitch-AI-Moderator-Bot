#!/usr/bin/env python3
"""
Twitch AI Moderator Bot - Voice Command Twitch Moderation
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

# Create file handler for detailed logging
file_handler = logging.FileHandler('moderator_bot.log')
file_handler.setLevel(logging.DEBUG)
file_formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
file_handler.setFormatter(file_formatter)

# Create console handler for essential messages only
console_handler = logging.StreamHandler(sys.stdout)
console_handler.setLevel(logging.WARNING)  # Only show warnings and errors in terminal
console_formatter = logging.Formatter('%(levelname)s: %(message)s')
console_handler.setFormatter(console_formatter)

# Configure root logger
logging.basicConfig(
    level=logging.DEBUG,
    handlers=[file_handler, console_handler]
)

# Disable noisy HTTP logs
logging.getLogger('httpx').disabled = True
logging.getLogger('httpcore').disabled = True
logging.getLogger('openai').setLevel(logging.WARNING)
logging.getLogger('urllib3').setLevel(logging.WARNING)
logging.getLogger('aiohttp').setLevel(logging.WARNING)

from config import Config
from voice_recognition_hf import VoiceRecognitionHF
from command_processor import CommandProcessor, ModerationCommand
from twitch_bot import TwitchModeratorBot

logger = logging.getLogger(__name__)

class AIModeratorBot:
    def __init__(self):
        """Initialize the Twitch AI Moderator Bot"""
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
            # Basic validation (without channel check)
            required_vars = ['TWITCH_TOKEN', 'TWITCH_CLIENT_ID', 'TWITCH_CLIENT_SECRET', 'TWITCH_BOT_USERNAME']
            missing_vars = []
            for var in required_vars:
                if not getattr(Config, var):
                    missing_vars.append(var)
            
            if missing_vars:
                raise ValueError(f"Missing required environment variables: {', '.join(missing_vars)}")
            
            logger.info("Basic configuration validated successfully")
            
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
        """Start the Twitch AI Moderator Bot"""
        if not await self.initialize():
            print("❌ Failed to initialize bot components")
            return False
        
        try:
            # Final configuration validation (now that channel is set)
            Config.validate()
            logger.info("Full configuration validated successfully")
            
            print("🚀 Starting Twitch AI Moderator Bot...")
            self.is_running = True
            
            # Store reference to the current event loop
            self.event_loop = asyncio.get_running_loop()
            
            # Initialize Twitch bot
            if not await self.twitch_bot.initialize():
                print("❌ Failed to connect to Twitch API")
                return False
            
            # Start voice recognition
            self.voice_recognition.start_listening()
            
            # Send startup message to chat
            await self.twitch_bot.send_status_message()
            
            print("🎤 Twitch AI Moderator Bot is now running!")
            print(f"🎯 Moderating channel: {Config.TWITCH_CHANNEL}")
            print("🎯 Voice commands are active. Say 'Hey Brian' followed by your command.")
            print("📝 Example: 'Hey Brian, ban username123 for 10 minutes'")
            
            # Keep the main thread alive
            while self.is_running:
                await asyncio.sleep(1)
            
            return True
            
        except Exception as e:
            print(f"❌ Error starting bot: {e}")
            logger.error(f"Error starting bot: {e}")
            return False
    
    async def stop(self):
        """Stop the Twitch AI Moderator Bot"""
        print("🛑 Stopping Twitch AI Moderator Bot...")
        logger.info("Stopping Twitch AI Moderator Bot...")
        self.is_running = False
        
        # Stop voice recognition
        if self.voice_recognition:
            self.voice_recognition.stop_listening()
        
        # Stop Twitch bot
        if self.twitch_bot:
            await self.twitch_bot.close()
        
        print("✅ Twitch AI Moderator Bot stopped")
        logger.info("Twitch AI Moderator Bot stopped")
    
    def _on_voice_command(self, command_text: str):
        """Handle voice commands"""
        logger.info(f"Processing voice command: {command_text}")
        
        # Process the command
        moderation_cmd = self.command_processor.process_command(command_text)
        
        if moderation_cmd:
            # Validate the command
            is_valid, error_msg = self.command_processor.validate_command(moderation_cmd)
            
            if is_valid:
                # Show command in terminal for user feedback
                print(f"🎯 Executing: {moderation_cmd.action}" + (f" on {moderation_cmd.username}" if moderation_cmd.username else ""))
                
                # Schedule the command execution in the main event loop
                if self.event_loop and not self.event_loop.is_closed():
                    try:
                        future = asyncio.run_coroutine_threadsafe(
                            self._execute_command_async(moderation_cmd), 
                            self.event_loop
                        )
                        logger.debug(f"Command scheduled for execution: {moderation_cmd.action}")
                    except Exception as e:
                        print(f"❌ Failed to schedule command: {e}")
                        logger.error(f"Failed to schedule command execution: {e}")
                else:
                    print("❌ Event loop not available")
                    logger.error("Event loop not available for command execution")
            else:
                print(f"❌ Invalid command: {error_msg}")
                logger.warning(f"Invalid command: {error_msg}")
        else:
            print(f"❓ Could not understand command: {command_text}")
            logger.warning(f"Could not understand command: {command_text}")
    
    async def _execute_command_async(self, cmd: ModerationCommand):
        """Execute a moderation command asynchronously"""
        try:
            success = await self.twitch_bot.execute_moderation_command(cmd)
            if success:
                print(f"✅ Command executed successfully: {cmd.action}")
                logger.info(f"✅ Command executed successfully: {cmd.action}")
            else:
                print(f"❌ Command execution failed: {cmd.action}")
                logger.error(f"❌ Command execution failed: {cmd.action}")
        except Exception as e:
            print(f"❌ Error executing command: {e}")
            logger.error(f"Error executing command: {e}")
    
    def _on_command_executed(self, cmd: ModerationCommand, success: bool):
        """Callback for when a command is executed"""
        status = "✅ SUCCESS" if success else "❌ FAILED"
        logger.info(f"Command execution {status}: {cmd.action} on {cmd.username}")
    
    def _signal_handler(self, signum, frame):
        """Handle shutdown signals"""
        print(f"\n🛑 Received shutdown signal, stopping...")
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

    def get_twitch_channel(self) -> str:
        """Prompt user for Twitch channel to moderate"""
        # Check if we're in an interactive environment
        if not sys.stdin.isatty():
            print("❌ Error: This bot requires an interactive terminal to select a channel.")
            print("Please run the bot in an interactive terminal (not piped or redirected).")
            sys.exit(1)
        
        print("\n" + "="*60)
        print("🎤 TWITCH AI MODERATOR BOT")
        print("="*60)
        print("Welcome! This bot will help you moderate a Twitch channel using voice commands.")
        print("You'll be able to use commands like:")
        print("  • 'Hey Brian, ban username123 for 10 minutes'")
        print("  • 'Hey Brian, timeout spammer for spam'")
        print("  • 'Hey Brian, clear chat'")
        print("  • 'Hey Brian, slow mode 30 seconds'")
        print("  • And many more!")
        print("\n" + "-"*60)
        
        max_attempts = 3
        attempts = 0
        
        while attempts < max_attempts:
            try:
                channel = input("Enter the Twitch channel you want to moderate (without #): ").strip()
                
                if not channel:
                    print("❌ Please enter a valid channel name.")
                    attempts += 1
                    continue
                
                # Clean the channel name
                if channel.startswith('#'):
                    channel = channel[1:]
                
                # Basic validation
                if not channel.replace('_', '').isalnum():
                    print("❌ Channel name should only contain letters, numbers, and underscores.")
                    attempts += 1
                    continue
                
                if len(channel) < 3 or len(channel) > 25:
                    print("❌ Channel name should be between 3 and 25 characters.")
                    attempts += 1
                    continue
                
                # Confirm the channel
                print(f"\n🎯 You want to moderate: {channel}")
                try:
                    confirm = input("Is this correct? (y/n): ").strip().lower()
                    
                    if confirm in ['y', 'yes']:
                        return channel
                    elif confirm in ['n', 'no']:
                        attempts += 1
                        continue
                    else:
                        print("Please enter 'y' for yes or 'n' for no.")
                        attempts += 1
                        continue
                except (EOFError, KeyboardInterrupt):
                    print("\n\nExiting...")
                    sys.exit(0)
                    
            except (EOFError, KeyboardInterrupt):
                print("\n\nExiting...")
                sys.exit(0)
            except Exception as e:
                print(f"❌ Error: {e}")
                attempts += 1
                continue
        
        print(f"\n❌ Too many invalid attempts ({max_attempts}). Exiting...")
        sys.exit(1)

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
            print("Twitch AI Moderator Bot - Voice Command Twitch Moderation")
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
        # Get Twitch channel from user
        channel = bot.get_twitch_channel()
        Config.set_twitch_channel(channel)
        
        print(f"\n✅ Channel set to: {Config.TWITCH_CHANNEL}")
        print("🚀 Starting bot initialization...")
        
        # Start the bot
        success = await bot.start()
        if not success:
            print("❌ Failed to start bot")
            logger.error("Failed to start bot")
            sys.exit(1)
    except KeyboardInterrupt:
        print("\n🛑 Received keyboard interrupt")
        logger.info("Received keyboard interrupt")
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        logger.error(f"Unexpected error: {e}")
    finally:
        await bot.stop()

if __name__ == "__main__":
    # Run the main function
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n✅ Shutdown complete.")
    except Exception as e:
        print(f"❌ Fatal error: {e}")
        logger.error(f"Fatal error: {e}")
        sys.exit(1) 