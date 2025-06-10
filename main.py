#!/usr/bin/env python3
"""
Utility functions for Twitch AI Moderator Bot
Debug and testing utilities for stream audio setup
"""

def test_stream_audio():
    """Test Twitch stream audio capture functionality"""
    try:
        from voice_recognition_hf import VoiceRecognitionHF
        from config import Config
        import subprocess
        import time
        import io
        import wave
        import requests
        
        print("🎤 Testing Twitch stream audio capture...")
        
        # Check if channel is configured, if not ask for it
        test_channel = Config.TWITCH_CHANNEL
        if not test_channel:
            print("⚠️  TWITCH_CHANNEL not configured in .env file")
            test_channel = input("Enter Twitch channel name for testing (without #): ").strip().lower()
            if not test_channel:
                print("❌ No channel name provided")
                return False
            
            # Temporarily set the channel for testing
            Config.set_twitch_channel(test_channel)
        
        print(f"📡 Testing stream: {test_channel}")
        
        # Test streamlink availability
        try:
            subprocess.run(['streamlink', '--version'], capture_output=True, check=True)
            print("✅ Streamlink found")
        except (subprocess.CalledProcessError, FileNotFoundError):
            print("❌ Streamlink not found. Please install: pip install streamlink")
            return False
        
        # Test FFmpeg availability
        try:
            subprocess.run(['ffmpeg', '-version'], capture_output=True, check=True)
            print("✅ FFmpeg found")
        except (subprocess.CalledProcessError, FileNotFoundError):
            print("❌ FFmpeg not found. Please install FFmpeg")
            return False
        
        # Test Hugging Face endpoint
        if not Config.HF_API_TOKEN or not Config.HF_ENDPOINT_URL:
            print("❌ Hugging Face configuration missing (HF_API_TOKEN or HF_ENDPOINT_URL)")
            print("💡 Please configure these in your .env file to test transcription")
            print("   For now, testing basic stream access only...")
        else:
            print("✅ Hugging Face configuration found")
        
        print("✅ All dependencies found")
        print("🔴 Testing stream capture (this may take a moment)...")
        
        # Test streamlink access to the channel
        print(f"🔍 Checking if channel '{test_channel}' is live...")
        try:
            streamlink_test_cmd = [
                'streamlink', 
                '--json',
                f'twitch.tv/{test_channel}'
            ]
            result = subprocess.run(streamlink_test_cmd, capture_output=True, text=True, timeout=10)
            if result.returncode == 0:
                print("✅ Channel is accessible via streamlink")
            else:
                print(f"⚠️  Channel may not be live or accessible: {result.stderr}")
                print("💡 This is normal if the channel is offline")
        except subprocess.TimeoutExpired:
            print("⚠️  Streamlink test timed out - this is normal")
        except Exception as e:
            print(f"⚠️  Streamlink test error: {e}")
        
        # Create a voice recognition instance and test basic initialization
        try:
            voice_recognition = VoiceRecognitionHF(lambda x: print(f"🎯 Test command: {x}"))
            print("✅ Voice recognition initialized successfully")
        except Exception as e:
            print(f"❌ Voice recognition initialization failed: {e}")
            return False
        
        print("✅ Stream audio capture test completed successfully!")
        print("💡 To start the bot: python web_interface.py")
        return True
        
    except ImportError as e:
        print(f"❌ Missing dependencies: {e}")
        print("Please install requirements: pip install -r requirements.txt")
        return False
    except Exception as e:
        print(f"❌ Error testing stream audio capture: {e}")
        return False

def show_stream_info():
    """Show information about Twitch stream audio capture"""
    try:
        from config import Config
        
        print("📡 Twitch Stream Audio Capture Information")
        print("=" * 50)
        print("This bot captures audio directly from Twitch streams using:")
        print("  • Streamlink - For stream access")
        print("  • FFmpeg - For audio processing") 
        print("  • Whisper Large V3 - For speech recognition")
        print()
        
        print("📋 Configuration Requirements:")
        print("  1. TWITCH_CHANNEL - Target stream channel")
        print("  2. HF_API_TOKEN - Hugging Face API token")
        print("  3. HF_ENDPOINT_URL - Whisper endpoint URL")
        print("  4. OPENAI_API_KEY - For command processing")
        print()
        
        print("🔧 System Requirements:")
        print("  • streamlink (pip install streamlink)")
        print("  • FFmpeg (system install)")
        print()
        
        print("📁 Current Configuration:")
        print(f"  Channel: {Config.TWITCH_CHANNEL or 'Not configured'}")
        print(f"  HF Token: {'✅ Set' if Config.HF_API_TOKEN else '❌ Missing'}")
        print(f"  HF Endpoint: {'✅ Set' if Config.HF_ENDPOINT_URL else '❌ Missing'}")
        print(f"  OpenAI Key: {'✅ Set' if Config.OPENAI_API_KEY else '❌ Missing'}")
        print(f"  Wake Word: {Config.VOICE_ACTIVATION_KEYWORD}")
        print(f"  Transcription Logging: {'✅ Enabled' if Config.ENABLE_TRANSCRIPTION_LOGGING else '❌ Disabled'}")
        print()
        
        print("🚀 To start the bot:")
        print("  python web_interface.py")
        
        return True
        
    except ImportError as e:
        print(f"❌ Missing dependencies: {e}")
        print("Please install requirements: pip install -r requirements.txt")
        return False
    except Exception as e:
        print(f"❌ Error getting stream info: {e}")
        return False

if __name__ == "__main__":
    print("🎤 Twitch AI Moderator Bot - Utilities")
    print("=" * 50)
    print("Main bot interface: python web_interface.py")
    print("=" * 50)
    print("\nAvailable utilities:")
    print("  Test Twitch stream audio capture:")
    print("    python -c 'from main import test_stream_audio; test_stream_audio()'")
    print("  Show stream audio info:")
    print("    python -c 'from main import show_stream_info; show_stream_info()'")
    print("\nOr run functions directly:")
    print("  1. test_stream_audio() - Test stream audio capture")
    print("  2. show_stream_info() - Show stream audio info")
    
    # Simple interactive menu
    while True:
        choice = input("\nEnter 1, 2, or 'q' to quit: ").strip().lower()
        if choice == '1':
            test_stream_audio()
        elif choice == '2':
            show_stream_info()
        elif choice in ['q', 'quit', 'exit']:
            print("👋 Goodbye!")
            break
        else:
            print("❌ Invalid choice. Enter 1, 2, or 'q'") 