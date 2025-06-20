#!/usr/bin/env python3
"""
Test Script for Hybrid Username Matching
Interactive tool to test hybrid phonetic + AI username matching against recent chat usernames
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
    print("=" * 70)
    print("🔊🤖 HYBRID USERNAME MATCHING TEST TOOL")
    print("=" * 70)
    print("This tool tests the hybrid phonetic + AI username matching system.")
    print("The system uses multiple methods in priority order:")
    print("1. ✅ Exact match (case-insensitive)")
    print("2. 🔍 Fuzzy match (pattern-based)")
    print("3. 🔊 Phonetic match (sound-based, fast)")
    print("4. 🤖 AI match (context-aware, slower)")
    print("=" * 70)

def display_usernames(usernames: List[str]):
    """Display the available usernames"""
    print(f"\n📋 Available usernames ({len(usernames)}):")
    print("-" * 40)
    for i, username in enumerate(usernames, 1):
        print(f"{i:2d}. {username}")
    print("-" * 40)

def test_detailed_matching(ai_helper: AIModerationHelper, spoken_username: str) -> Optional[str]:
    """Test each matching method individually and show results"""
    recent_usernames = ai_helper.username_logger.get_recent_usernames()
    spoken_lower = spoken_username.lower()
    
    # Step 1: Exact match
    print(f"  1. ✅ Exact match: ", end="")
    for username in recent_usernames:
        if username.lower() == spoken_lower:
            print(f"'{spoken_username}' → '{username}' ✅")
            return username
    print("No exact match ❌")
    
    # Step 2: Fuzzy match
    print(f"  2. 🔍 Fuzzy match: ", end="")
    fuzzy_match = ai_helper._try_fuzzy_match(spoken_lower, recent_usernames)
    if fuzzy_match:
        print(f"'{spoken_username}' → '{fuzzy_match}' ✅")
        return fuzzy_match
    print("No fuzzy match ❌")
    
    # Step 3: Phonetic match
    print(f"  3. 🔊 Phonetic match: ", end="")
    try:
        phonetic_result = ai_helper.username_logger.find_phonetically_similar_username(spoken_username, threshold=0.6)
        if phonetic_result:
            matched_username, score = phonetic_result
            print(f"'{spoken_username}' → '{matched_username}' (score: {score:.3f}) ✅")
            return matched_username
        print("No phonetic match ❌")
    except Exception as e:
        print(f"Phonetic matching error: {e} ❌")
    
    # Step 4: AI match
    print(f"  4. 🤖 AI match: ", end="")
    ai_result = ai_helper.username_logger.find_ai_similar_username(spoken_username)
    if ai_result:
        matched_username, reasoning = ai_result
        print(f"'{spoken_username}' → '{matched_username}' ✅")
        print(f"     Reasoning: {reasoning}")
        return matched_username
    print("No AI match ❌")
    
    print(f"  ❌ Final result: No match found for '{spoken_username}'")
    return None

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
    print("- The system will try multiple matching methods automatically")
    print("- You'll see which method successfully matched the username")
    print("- Type 'quit' or 'exit' to stop")
    print("- Type 'list' to see usernames again")
    print("- Type 'add' to add a custom username to test")
    print("- Type 'verbose' to toggle detailed matching info")
    print()
    
    # Add verbose mode tracking
    verbose_mode = False
    
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
            
            if spoken_input.lower() == 'verbose':
                verbose_mode = not verbose_mode
                status = "ON" if verbose_mode else "OFF"
                print(f"🔧 Verbose mode: {status}")
                continue
            
            print(f"\n🔍 Testing: '{spoken_input}'")
            print("-" * 40)
            
            if verbose_mode:
                # Show detailed step-by-step matching
                print("🔍 Step-by-step matching:")
                result = test_detailed_matching(ai_helper, spoken_input)
            else:
                # Regular matching with result indication
                result = ai_helper.resolve_username(spoken_input)
                
                if result and result != spoken_input:
                    # Show which username from the list it matched
                    recent_usernames = test_logger.get_recent_usernames()
                    if result in recent_usernames:
                        index = recent_usernames.index(result) + 1
                        print(f"✅ Matched: '{result}' (username #{index} from the list)")
                elif result == spoken_input:
                    print(f"✅ Found exact match: '{result}'")
                else:
                    print(f"❌ No match found")
            
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
    
    # Add comprehensive test usernames
    test_usernames = [
        # Exact match tests
        "igor_stn",
        "TestUser123", 
        
        # Fuzzy match tests (pattern-based)
        "bob_test",
        "alice123",
        
        # Phonetic match tests (sound-based)
        "brian_the_great",
        "V1king_k1ng",
        "chan_the_magic_man",
        "RoilNavy",
        "john_smith_42",
        "GamerDude2024",
        "XxDarkLordxX"
    ]
    test_logger.add_test_usernames(test_usernames)
    
    # Initialize AI helper
    ai_helper = AIModerationHelper(test_logger)
    
    # Comprehensive test cases targeting different matching methods
    test_cases = [
        # Exact matches
        ("igor_stn", "igor_stn", "✅ Exact"),
        ("testuser123", "TestUser123", "✅ Exact"),
        
        # Fuzzy matches (abbreviation patterns)
        ("igorston", "igor_stn", "🔍 Fuzzy"),
        ("bobtest", "bob_test", "🔍 Fuzzy"),
        
        # Phonetic matches (sound-based)
        ("brianthegreat", "brian_the_great", "🔊 Phonetic"),
        ("viking king", "V1king_k1ng", "🔊 Phonetic"),
        ("chan the magic man", "chan_the_magic_man", "🔊 Phonetic"),
        ("roil navy", "RoilNavy", "🔊 Phonetic"), 
        ("john smith", "john_smith_42", "🔊 Phonetic"),
        ("gamer dude", "GamerDude2024", "🔊 Phonetic"),
        ("dark lord", "XxDarkLordxX", "🔊 Phonetic"),
        
        # AI fallback cases (if phonetic fails)
        ("very complex pattern", None, "🤖 AI (expected fail)"),
        ("nonexistent user", None, "❌ No match")
    ]
    
    print("📋 Comprehensive Test Cases:")
    print("-" * 70)
    
    correct = 0
    total = len(test_cases)
    method_counts = {"✅ Exact": 0, "🔍 Fuzzy": 0, "🔊 Phonetic": 0, "🤖 AI": 0}
    
    for spoken, expected, expected_method in test_cases:
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
            
            # Track which method would have been used
            if success and result:
                recent_usernames = test_logger.get_recent_usernames()
                spoken_lower = spoken.lower()
                
                # Determine actual method used
                if any(username.lower() == spoken_lower for username in recent_usernames):
                    actual_method = "✅ Exact"
                elif ai_helper._try_fuzzy_match(spoken_lower, recent_usernames):
                    actual_method = "🔍 Fuzzy"
                else:
                    phonetic_result = test_logger.find_phonetically_similar_username(spoken, threshold=0.6)
                    if phonetic_result:
                        actual_method = "🔊 Phonetic"
                    else:
                        actual_method = "🤖 AI"
                
                method_counts[actual_method] = method_counts.get(actual_method, 0) + 1
                print(f"   Method: {actual_method}")
        
        if success:
            correct += 1
    
    print("-" * 70)
    print(f"📊 Results: {correct}/{total} correct ({correct/total*100:.1f}%)")
    print(f"📈 Method Distribution:")
    for method, count in method_counts.items():
        percentage = (count / sum(method_counts.values()) * 100) if sum(method_counts.values()) > 0 else 0
        print(f"   {method}: {count} matches ({percentage:.1f}%)")
    print(f"💰 Cost Efficiency: {(method_counts['✅ Exact'] + method_counts['🔍 Fuzzy'] + method_counts['🔊 Phonetic']) / sum(method_counts.values()) * 100:.1f}% free matches")

def main():
    """Main function"""
    if len(sys.argv) > 1 and sys.argv[1] == '--batch':
        run_batch_test()
    else:
        run_interactive_test()

if __name__ == "__main__":
    main() 