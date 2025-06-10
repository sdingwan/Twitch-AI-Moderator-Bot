#!/usr/bin/env python3
"""
Utility functions for Twitch AI Moderator Bot
Debug and testing utilities for microphone setup
"""

def test_stream_audio():
    """Test Twitch stream audio capture functionality"""
    try:
        from voice_recognition_hf import VoiceRecognitionHF
        print("🎤 Testing Twitch stream audio capture...")
        voice_recognition = VoiceRecognitionHF(lambda x: None)
        voice_recognition.test_stream_audio()
    except ImportError as e:
        print(f"❌ Missing dependencies: {e}")
        print("Please install requirements: pip install -r requirements.txt")
    except Exception as e:
        print(f"❌ Error testing stream audio capture: {e}")

def show_stream_info():
    """Show information about Twitch stream audio capture"""
    try:
        from voice_recognition_hf import VoiceRecognitionHF
        print("📡 Twitch Stream Audio Capture:")
        VoiceRecognitionHF.list_stream_info()
    except ImportError as e:
        print(f"❌ Missing dependencies: {e}")
        print("Please install requirements: pip install -r requirements.txt")
    except Exception as e:
        print(f"❌ Error getting stream info: {e}")

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