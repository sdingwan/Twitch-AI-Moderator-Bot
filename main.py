#!/usr/bin/env python3
"""
Twitch AI Moderator Bot - Voice Command Twitch Moderation
A simple Twitch chat moderation bot that responds to voice commands using cloud-hosted Whisper Large V3
"""

import sys
import os

def print_help():
    """Print help information"""
    print("🎤 Twitch AI Moderator Bot")
    print("Voice-controlled Twitch moderation with cloud-hosted Whisper Large V3")
    print("\n" + "="*60)
    print("USAGE:")
    print("  python web_interface.py         - Start the web interface (RECOMMENDED)")
    print("  python main.py --test-mic       - Test microphone")
    print("  python main.py --list-mics      - List available microphones")
    print("  python main.py --help           - Show this help")
    print("\n" + "="*60)
    print("WEB INTERFACE (Recommended):")
    print("  1. Run: python web_interface.py")
    print("  2. Open: http://localhost:8000")
    print("  3. Enter your Twitch channel")
    print("  4. Click 'Start Bot'")
    print("  5. Say 'Hey Brian, [command]'")
    print("\n" + "="*60)
    print("VOICE COMMANDS:")
    print("  • 'Hey Brian, ban username123'")
    print("  • 'Hey Brian, timeout spammer for 10 minutes'")
    print("  • 'Hey Brian, clear chat'")
    print("  • 'Hey Brian, slow mode 30 seconds'")
    print("  • 'Hey Brian, followers only mode'")
    print("  • 'Hey Brian, subscribers only mode'")
    print("\n" + "="*60)
    print("FEATURES:")
    print("  🌐 Modern web interface")
    print("  🎤 Cloud-hosted Whisper Large V3 voice recognition")
    print("  🚀 Twitch Helix API integration")
    print("  🔍 Smart phonetic username matching")
    print("  📱 Mobile-friendly responsive design")

def test_microphone():
    """Test microphone functionality"""
    try:
        from voice_recognition_hf import VoiceRecognitionHF
        print("🎤 Testing microphone...")
        voice_recognition = VoiceRecognitionHF(lambda x: None)
        voice_recognition.test_microphone()
    except ImportError as e:
        print(f"❌ Missing dependencies: {e}")
        print("Please install requirements: pip install -r requirements.txt")
    except Exception as e:
        print(f"❌ Error testing microphone: {e}")

def list_microphones():
    """List available microphones"""
    try:
        from voice_recognition_hf import VoiceRecognitionHF
        print("🎤 Available microphones:")
        VoiceRecognitionHF.list_microphones()
    except ImportError as e:
        print(f"❌ Missing dependencies: {e}")
        print("Please install requirements: pip install -r requirements.txt")
    except Exception as e:
        print(f"❌ Error listing microphones: {e}")

def main():
    """Main entry point"""
    # Check command line arguments
    if len(sys.argv) > 1:
        if sys.argv[1] == '--test-mic':
            test_microphone()
            return
        elif sys.argv[1] == '--list-mics':
            list_microphones()
            return
        elif sys.argv[1] == '--help':
            print_help()
            return
        else:
            print(f"❌ Unknown argument: {sys.argv[1]}")
            print("Use --help for usage information")
            return
    
    # No arguments - direct user to web interface
    print("\n" + "="*60)
    print("🎤 TWITCH AI MODERATOR BOT")
    print("="*60)
    print("📌 The bot now uses a modern web interface!")
    print("\nTo start the bot:")
    print("  1. Run: python web_interface.py")
    print("  2. Open your browser to: http://localhost:8000")
    print("  3. Enter your Twitch channel and click 'Start Bot'")
    print("\nFor other options:")
    print("  python main.py --help      - Show all commands")
    print("  python main.py --test-mic  - Test your microphone")
    print("=" * 60)

if __name__ == "__main__":
    main() 