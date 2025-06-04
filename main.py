#!/usr/bin/env python3
"""
Utility functions for Twitch AI Moderator Bot
Debug and testing utilities for microphone setup
"""

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

if __name__ == "__main__":
    print("🎤 Twitch AI Moderator Bot - Utilities")
    print("=" * 50)
    print("Main bot interface: python web_interface.py")
    print("=" * 50)
    print("\nAvailable utilities:")
    print("  Test microphone:")
    print("    python -c 'from main import test_microphone; test_microphone()'")
    print("  List microphones:")
    print("    python -c 'from main import list_microphones; list_microphones()'")
    print("\nOr run functions directly:")
    print("  1. test_microphone()")
    print("  2. list_microphones()")
    
    # Simple interactive menu
    while True:
        choice = input("\nEnter 1, 2, or 'q' to quit: ").strip().lower()
        if choice == '1':
            test_microphone()
        elif choice == '2':
            list_microphones()
        elif choice in ['q', 'quit', 'exit']:
            print("👋 Goodbye!")
            break
        else:
            print("❌ Invalid choice. Enter 1, 2, or 'q'") 