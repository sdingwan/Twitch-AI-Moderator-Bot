#!/usr/bin/env python3
"""
Interactive Username Matching Test Tool
Test the AI-powered username matching feature without running the full bot
"""

import asyncio
import logging
import os
from datetime import datetime
from collections import deque
from openai import OpenAI
from config import Config

# Set up logging
logging.basicConfig(level=logging.WARNING)  # Suppress INFO logs for cleaner output

class UsernameMatchingTester:
    """Standalone tester for AI username matching"""
    
    def __init__(self):
        self.usernames = deque(maxlen=100)  # Store more usernames for testing
        self.openai_client = OpenAI(api_key=Config.OPENAI_API_KEY)
        self.load_usernames_from_log()
    
    def load_usernames_from_log(self):
        """Load usernames from the chat log file"""
        log_file = "chat_usernames.log"
        
        if not os.path.exists(log_file):
            print(f"❌ Chat log file '{log_file}' not found!")
            print("💡 Run the bot first to generate some chat data, or create a sample log file.")
            return
        
        try:
            with open(log_file, 'r') as f:
                lines = f.readlines()
            
            usernames_loaded = 0
            for line in lines:
                line = line.strip()
                # Skip comment lines
                if line.startswith('#') or not line:
                    continue
                
                # Parse format: timestamp,username
                if ',' in line:
                    timestamp, username = line.split(',', 1)
                    self.usernames.append({
                        'username': username.strip(),
                        'timestamp': timestamp.strip()
                    })
                    usernames_loaded += 1
            
            print(f"✅ Loaded {usernames_loaded} usernames from chat log")
            
            # Show some examples
            recent_usernames = list(set([entry['username'] for entry in self.usernames]))[-10:]
            print(f"📝 Recent usernames: {', '.join(recent_usernames[:10])}")
            
        except Exception as e:
            print(f"❌ Error reading chat log: {e}")
    
    def get_recent_usernames(self):
        """Get list of unique recent usernames"""
        return list(set([entry['username'] for entry in self.usernames]))
    
    async def find_similar_username_with_ai(self, spoken_name: str):
        """Use OpenAI API to find the best matching username"""
        if not self.usernames:
            print("❌ No usernames available for matching")
            return None
        
        recent_usernames = self.get_recent_usernames()
        print(f"🔍 Searching among {len(recent_usernames)} usernames...")
        
        try:
            usernames_list = ", ".join(recent_usernames)
            
            prompt = f"""You are helping match a spoken username to actual Twitch chat usernames.

Spoken name: "{spoken_name}"
Available usernames from recent chat: {usernames_list}

Task: Find the username that best matches the spoken name. Consider:
- Phonetic similarity (how they sound)
- Common name variations (honey/honi, berry/berrii, etc.)
- Leetspeak patterns (ii instead of y, numbers for letters)
- Partial matches where the spoken name might be a shortened version

Return ONLY the exact username from the list that best matches, or "NONE" if no reasonable match exists.

Examples:
- "honey berry" could match "honiiberrii" 
- "fire bat" could match "firebat1989"
- "awkward cyborg" could match "awkward_cyborg"
- "RoilNavy" could match "roilnave"

Your response:"""

            response = self.openai_client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": "You are a precise username matching assistant. Return only the exact username or 'NONE'."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=50,
                temperature=0.1
            )
            
            matched_username = response.choices[0].message.content.strip()
            
            # Validate the response
            if matched_username == "NONE" or matched_username not in recent_usernames:
                return None
            
            return matched_username
            
        except Exception as e:
            print(f"❌ Error using AI for username matching: {e}")
            return None
    
    async def test_username(self, spoken_name: str):
        """Test a single username match"""
        print(f"\n🎯 Testing: '{spoken_name}'")
        print("-" * 40)
        
        # First try exact match
        recent_usernames = self.get_recent_usernames()
        spoken_lower = spoken_name.lower()
        
        exact_match = None
        for username in recent_usernames:
            if username.lower() == spoken_lower:
                exact_match = username
                break
        
        if exact_match:
            print(f"✅ Exact match found: '{spoken_name}' → '{exact_match}'")
            return exact_match
        
        # Try AI matching
        print("🤖 Using AI to find similar username...")
        ai_match = await self.find_similar_username_with_ai(spoken_name)
        
        if ai_match:
            print(f"✅ AI match found: '{spoken_name}' → '{ai_match}'")
            return ai_match
        else:
            print(f"❌ No match found for: '{spoken_name}'")
            return None
    
    async def run_interactive_test(self):
        """Run interactive testing session"""
        print("=" * 60)
        print("🤖 AI Username Matching Test Tool")
        print("=" * 60)
        
        if not self.usernames:
            print("❌ No usernames loaded. Please run the bot first or check the chat log file.")
            return
        
        print(f"📊 Loaded {len(set([u['username'] for u in self.usernames]))} unique usernames")
        print("\n💡 Tips for testing:")
        print("   - Try variations like 'honey berry' if you see 'honiiberrii'")
        print("   - Test partial names like 'fire' for 'firebat1989'")
        print("   - Try different pronunciations or misspellings")
        print("   - Type 'list' to see available usernames")
        print("   - Type 'quit' to exit")
        
        while True:
            print("\n" + "=" * 40)
            spoken_name = input("🎤 Enter a spoken username to test: ").strip()
            
            if spoken_name.lower() in ['quit', 'exit', 'q']:
                print("👋 Goodbye!")
                break
            
            if spoken_name.lower() == 'list':
                usernames = self.get_recent_usernames()
                print(f"\n📝 Available usernames ({len(usernames)}):")
                for i, username in enumerate(sorted(usernames), 1):
                    print(f"   {i:2d}. {username}")
                continue
            
            if not spoken_name:
                print("❌ Please enter a username to test")
                continue
            
            # Test the username
            await self.test_username(spoken_name)
    
    async def run_batch_test(self):
        """Run a batch of predefined tests"""
        print("=" * 60)
        print("🧪 Running Batch Tests")
        print("=" * 60)
        
        # Get some usernames to create test cases
        usernames = self.get_recent_usernames()
        if not usernames:
            print("❌ No usernames available for testing")
            return
        
        # Create some test cases based on available usernames
        test_cases = []
        
        for username in usernames[:5]:  # Test first 5 usernames
            original = username
            
            # Create variations
            variations = []
            
            # Remove numbers
            no_numbers = ''.join([c for c in username if not c.isdigit()])
            if no_numbers != username and len(no_numbers) > 2:
                variations.append(no_numbers)
            
            # Add spaces before uppercase or numbers
            spaced = ""
            for i, char in enumerate(username):
                if i > 0 and (char.isupper() or char.isdigit()):
                    spaced += " " + char.lower()
                else:
                    spaced += char.lower()
            if spaced != username.lower():
                variations.append(spaced)
            
            # Replace underscores with spaces
            if '_' in username:
                variations.append(username.replace('_', ' '))
            
            for variation in variations[:2]:  # Max 2 variations per username
                test_cases.append((variation, original))
        
        # Add some manual test cases
        manual_tests = [
            ("honey berry", "honiiberrii"),
            ("fire bat", "firebat1989"),
            ("awkward cyborg", "awkward_cyborg"),
        ]
        
        # Only add manual tests if the target username exists
        for spoken, target in manual_tests:
            if target in usernames:
                test_cases.append((spoken, target))
        
        if not test_cases:
            print("❌ No test cases could be generated")
            return
        
        print(f"🧪 Running {len(test_cases)} test cases...")
        
        passed = 0
        failed = 0
        
        for spoken, expected in test_cases:
            print(f"\n🎯 Test: '{spoken}' → expecting '{expected}'")
            result = await self.test_username(spoken)
            
            if result == expected:
                print(f"✅ PASS")
                passed += 1
            else:
                print(f"❌ FAIL - got '{result}', expected '{expected}'")
                failed += 1
        
        print(f"\n📊 Results: {passed} passed, {failed} failed")

async def main():
    """Main function"""
    tester = UsernameMatchingTester()
    
    if len(tester.usernames) == 0:
        return
    
    print("\nChoose test mode:")
    print("1. Interactive testing (recommended)")
    print("2. Batch testing")
    
    choice = input("Enter choice (1 or 2): ").strip()
    
    if choice == "2":
        await tester.run_batch_test()
    else:
        await tester.run_interactive_test()

if __name__ == "__main__":
    asyncio.run(main()) 