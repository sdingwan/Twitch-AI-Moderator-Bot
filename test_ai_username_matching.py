#!/usr/bin/env python3
"""
Test Script for AI Username Matching
Interactive tool to test AI-powered username matching against recent chat usernames
"""

import os
import sys
from datetime import datetime
from typing import List, Optional, Tuple
from collections import deque

# Add current directory to path to import our modules
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from config import Config
from username_logger import UsernameLogger, AIModerationHelper

class TestUsernameLogger(UsernameLogger):
    """Test version of UsernameLogger that loads from file instead of monitoring IRC"""
    
    def __init__(self):
        # Initialize with minimal setup
        self.max_usernames = 50
        self.usernames = deque(maxlen=self.max_usernames)
        self.log_file = "chat_usernames.log"
        
        # Initialize OpenAI client
        from openai import OpenAI
        if Config.OPENAI_API_KEY:
            self.openai_client = OpenAI(api_key=Config.OPENAI_API_KEY)
        else:
            print("❌ Error: OpenAI API key not found in .env file")
            sys.exit(1)
    
    def load_usernames_from_file(self) -> bool:
        """Load usernames from the chat log file"""
        try:
            if not os.path.exists(self.log_file):
                print(f"❌ Error: {self.log_file} not found. Run the bot first to generate username data.")
                return False
            
            with open(self.log_file, 'r') as f:
                lines = f.readlines()
            
            # Parse the log file (skip comment lines)
            for line in lines:
                line = line.strip()
                if line and not line.startswith('#'):
                    try:
                        timestamp, username = line.split(',', 1)
                        self.usernames.append({
                            'username': username.strip(),
                            'timestamp': timestamp.strip()
                        })
                    except ValueError:
                        continue  # Skip malformed lines
            
            print(f"✅ Loaded {len(self.usernames)} usernames from {self.log_file}")
            return True
            
        except Exception as e:
            print(f"❌ Error loading usernames: {e}")
            return False
    
    def add_test_usernames(self, test_usernames: List[str]):
        """Add custom test usernames to the collection"""
        for username in test_usernames:
            self.usernames.append({
                'username': username.lower().strip(),
                'timestamp': datetime.now().isoformat()
            })
        print(f"✅ Added {len(test_usernames)} test usernames")

def print_banner():
    """Print the test banner"""
    print("=" * 60)
    print("🤖 AI USERNAME MATCHING TEST TOOL")
    print("=" * 60)
    print("This tool tests the AI-powered username matching system.")
    print("You can enter spoken usernames and see how the AI matches them.")
    print("=" * 60)

def display_usernames(usernames: List[str]):
    """Display the available usernames"""
    print(f"\n📋 Available usernames ({len(usernames)}):")
    print("-" * 40)
    for i, username in enumerate(usernames, 1):
        print(f"{i:2d}. {username}")
    print("-" * 40)

def run_interactive_test():
    """Run the interactive username matching test"""
    print_banner()
    
    # Initialize test logger
    test_logger = TestUsernameLogger()
    
    # Try to load existing usernames from file
    has_real_data = test_logger.load_usernames_from_file()
    
    # If no real data, offer to add test data
    if not has_real_data or len(test_logger.get_recent_usernames()) == 0:
        print("\n🔧 No username data found. Adding test usernames...")
        test_usernames = [
            "V1king_k1ng",
            "TestUser123", 
            "chan_the_magic_man",
            "RoilNavy",
            "john_smith_42",
            "GamerDude2024",
            "StreamerFan",
            "chatbot_helper",
            "XxDarkLordxX",
            "simple_user",
            "ComplexUsername2024",
            "user_with_numbers_123",
            "ALLCAPS_USER",
            "mixed_CaSe_UsEr",
            "underscore_username_test"
        ]
        test_logger.add_test_usernames(test_usernames)
    
    # Initialize AI helper
    ai_helper = AIModerationHelper(test_logger)
    recent_usernames = test_logger.get_recent_usernames()
    
    # Display available usernames
    display_usernames(recent_usernames)
    
    print("\n🎯 Test Instructions:")
    print("- Enter a spoken username (how you would say it)")
    print("- The AI will try to match it to an actual username")
    print("- Type 'quit' or 'exit' to stop")
    print("- Type 'list' to see usernames again")
    print("- Type 'add' to add a custom username to test")
    print()
    
    # Interactive testing loop
    while True:
        try:
            spoken_input = input("🎤 Enter spoken username: ").strip()
            
            if not spoken_input:
                continue
            
            if spoken_input.lower() in ['quit', 'exit', 'q']:
                print("👋 Goodbye!")
                break
            
            if spoken_input.lower() == 'list':
                display_usernames(test_logger.get_recent_usernames())
                continue
            
            if spoken_input.lower() == 'add':
                new_username = input("Enter username to add: ").strip()
                if new_username:
                    test_logger.add_test_usernames([new_username])
                    recent_usernames = test_logger.get_recent_usernames()
                    display_usernames(recent_usernames)
                continue
            
            print(f"\n🔍 Testing: '{spoken_input}'")
            print("-" * 30)
            
            # Test AI matching
            result = ai_helper.resolve_username(spoken_input)
            
            if result and result != spoken_input:
                print(f"✅ AI Match Found: '{spoken_input}' → '{result}'")
                
                # Show which username from the list it matched
                recent_usernames = test_logger.get_recent_usernames()
                if result in recent_usernames:
                    index = recent_usernames.index(result) + 1
                    print(f"   Matched username #{index} from the list")
                
            elif result == spoken_input:
                print(f"🔍 Exact match: '{result}'")
            else:
                print(f"❌ No match found for: '{spoken_input}'")
            
            print()
            
        except KeyboardInterrupt:
            print("\n👋 Goodbye!")
            break
        except Exception as e:
            print(f"❌ Error: {e}")

def run_batch_test():
    """Run a batch test with predefined test cases"""
    print_banner()
    print("🧪 Running batch test with predefined cases...\n")
    
    # Initialize test logger
    test_logger = TestUsernameLogger()
    
    # Add test usernames
    test_usernames = [
        "V1king_k1ng",
        "TestUser123", 
        "chan_the_magic_man",
        "RoilNavy",
        "john_smith_42",
        "GamerDude2024",
        "XxDarkLordxX"
    ]
    test_logger.add_test_usernames(test_usernames)
    
    # Initialize AI helper
    ai_helper = AIModerationHelper(test_logger)
    
    # Test cases
    test_cases = [
        ("viking king", "V1king_k1ng"),
        ("test user", "TestUser123"),
        ("chan the magic man", "chan_the_magic_man"),
        ("roil navy", "RoilNavy"), 
        ("john smith", "john_smith_42"),
        ("gamer dude", "GamerDude2024"),
        ("dark lord", "XxDarkLordxX"),
        ("nonexistent user", None)  # Should not match
    ]
    
    print("📋 Test Cases:")
    print("-" * 50)
    
    correct = 0
    total = len(test_cases)
    
    for spoken, expected in test_cases:
        result = ai_helper.resolve_username(spoken)
        
        if expected is None:
            # Should not find a match
            success = result is None or result == spoken
            status = "✅" if success else "❌"
            print(f"{status} '{spoken}' → {result} (expected: no match)")
        else:
            # Should find the expected match
            success = result == expected
            status = "✅" if success else "❌"
            print(f"{status} '{spoken}' → {result} (expected: {expected})")
        
        if success:
            correct += 1
    
    print("-" * 50)
    print(f"📊 Results: {correct}/{total} correct ({correct/total*100:.1f}%)")

def main():
    """Main function"""
    if len(sys.argv) > 1 and sys.argv[1] == '--batch':
        run_batch_test()
    else:
        run_interactive_test()

if __name__ == "__main__":
    main() 