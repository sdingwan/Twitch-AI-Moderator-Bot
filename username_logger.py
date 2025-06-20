#!/usr/bin/env python3
"""
Username Logger and AI-based Matcher for Twitch Chat
Monitors Twitch IRC chat, logs usernames, and provides AI-powered matching for voice commands
"""

import asyncio
import json
import logging
import time
import socket
import ssl
import re
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple
from collections import deque
from openai import OpenAI
from config import Config

# Import phonetic libraries with fallback
try:
    import jellyfish
    from phonetics import dmetaphone
    PHONETIC_AVAILABLE = True
except ImportError:
    PHONETIC_AVAILABLE = False
    logger.warning("Phonetic libraries not available. Install with: pip install jellyfish phonetics")

logger = logging.getLogger(__name__)

class UsernameLogger:
    def __init__(self, max_usernames: int = 50, update_interval: int = 0.3):
        """
        Initialize the username logger
        
        Args:
            max_usernames: Maximum number of usernames to keep in memory and log file
            update_interval: How often to update the log file (in seconds)
        """
        self.max_usernames = max_usernames
        self.update_interval = update_interval
        self.usernames = deque(maxlen=max_usernames)
        self.log_file = "chat_usernames.log"
        self.reader = None
        self.writer = None
        self.is_running = False
        self.last_update = 0
        
        # IRC connection details for Twitch
        self.irc_server = "irc.chat.twitch.tv"
        self.irc_port = 6697
        self.channel = Config.TWITCH_CHANNEL.lower()
        self.bot_username = Config.TWITCH_BOT_USERNAME.lower()
        
        # Handle OAuth token format - IRC needs "oauth:" prefix, API doesn't
        self.oauth_token = Config.TWITCH_TOKEN
        if self.oauth_token and not self.oauth_token.startswith('oauth:'):
            self.oauth_token_for_irc = f"oauth:{self.oauth_token}"
        else:
            self.oauth_token_for_irc = self.oauth_token
        
        # Initialize OpenAI client for AI-based username matching
        self.openai_client = None
        if Config.OPENAI_API_KEY:
            self.openai_client = OpenAI(api_key=Config.OPENAI_API_KEY)
        else:
            logger.warning("OpenAI API key not found. AI username matching will not work.")
        
        # Ensure log file exists
        self._initialize_log_file()
    
    def _initialize_log_file(self):
        """Initialize the log file with proper format"""
        try:
            with open(self.log_file, 'w') as f:
                f.write(f"# Twitch Chat Usernames Log - Started at {datetime.now()}\n")
                f.write("# Format: timestamp,username\n")
            logger.info(f"Initialized username log file: {self.log_file}")
        except Exception as e:
            logger.error(f"Failed to initialize log file: {e}")
    
    async def start_monitoring(self):
        """Start monitoring Twitch IRC chat for usernames"""
        self.is_running = True
        logger.info(f"Starting username monitoring for channel: {self.channel}")
        
        while self.is_running:
            try:
                await self._connect_and_monitor()
            except Exception as e:
                logger.error(f"IRC connection error: {e}")
                if self.is_running:
                    logger.info("Reconnecting in 5 seconds...")
                    await asyncio.sleep(5)
    
    async def _connect_and_monitor(self):
        """Connect to Twitch IRC and monitor chat"""
        try:
            # Create SSL context
            ssl_context = ssl.create_default_context()
            
            # Connect to Twitch IRC
            self.reader, self.writer = await asyncio.open_connection(
                self.irc_server, self.irc_port, ssl=ssl_context
            )
            
            logger.info("Connected to Twitch IRC")
            
            # Send authentication
            await self._send_irc_message(f"PASS {self.oauth_token_for_irc}")
            await self._send_irc_message(f"NICK {self.bot_username}")
            await self._send_irc_message(f"JOIN #{self.channel}")
            
            logger.info(f"Joined channel: #{self.channel}")
            
            # Listen for messages
            while self.is_running:
                try:
                    data = await asyncio.wait_for(self.reader.readline(), timeout=1.0)
                    if not data:
                        break
                    
                    message = data.decode('utf-8', errors='ignore').strip()
                    if message:
                        await self._process_irc_message(message)
                        
                except asyncio.TimeoutError:
                    # Timeout is normal, just continue
                    continue
                except Exception as e:
                    logger.error(f"Error reading IRC message: {e}")
                    break
                    
        except Exception as e:
            logger.error(f"IRC connection error: {e}")
            raise
        finally:
            if self.writer:
                self.writer.close()
                await self.writer.wait_closed()
    
    async def _send_irc_message(self, message: str):
        """Send a message to IRC"""
        if self.writer:
            self.writer.write(f"{message}\r\n".encode('utf-8'))
            await self.writer.drain()
    
    async def _process_irc_message(self, message: str):
        """Process incoming IRC message and extract username"""
        try:
            # Parse IRC message format: :username!username@username.tmi.twitch.tv PRIVMSG #channel :message
            if "PRIVMSG" in message and f"#{self.channel}" in message:
                # Extract username from IRC message
                if message.startswith(":"):
                    username_part = message.split("!")[0][1:]  # Remove leading ':'
                    if username_part and username_part != self.bot_username:
                        await self._add_username(username_part)
            
            # Handle PING/PONG to keep connection alive
            elif message.startswith("PING"):
                pong_response = message.replace("PING", "PONG")
                await self._send_irc_message(pong_response)
                
        except Exception as e:
            logger.error(f"Error processing IRC message: {e}")
    
    async def _add_username(self, username: str):
        """Add username to the collection and update log file if needed"""
        username = username.lower().strip()
        
        # Add to deque (automatically handles max size)
        self.usernames.append({
            'username': username,
            'timestamp': datetime.now().isoformat()
        })
        
        logger.debug(f"Added username: {username}")
        
        # Update log file periodically
        current_time = time.time()
        if current_time - self.last_update >= self.update_interval:
            await self._update_log_file()
            self.last_update = current_time
    
    async def _update_log_file(self):
        """Update the log file with current usernames"""
        try:
            with open(self.log_file, 'w') as f:
                f.write(f"# Twitch Chat Usernames Log - Updated at {datetime.now()}\n")
                f.write("# Format: timestamp,username\n")
                
                for entry in self.usernames:
                    f.write(f"{entry['timestamp']},{entry['username']}\n")
            
            logger.debug(f"Updated log file with {len(self.usernames)} usernames")
            
        except Exception as e:
            logger.error(f"Failed to update log file: {e}")
    
    def stop_monitoring(self):
        """Stop monitoring chat"""
        self.is_running = False
        logger.info("Stopping username monitoring")
    
    def get_recent_usernames(self) -> List[str]:
        """Get list of recent usernames"""
        return [entry['username'] for entry in self.usernames]
    
    def _clean_for_phonetic(self, text: str) -> str:
        """Clean text for better phonetic matching by normalizing numbers and special characters"""
        # Replace common leet speak patterns
        text = text.replace('1', 'i').replace('3', 'e').replace('4', 'a')
        text = text.replace('5', 's').replace('7', 't').replace('0', 'o')
        
        # Remove or replace special characters with spaces
        text = text.replace('_', ' ').replace('-', ' ').replace('.', ' ')
        
        # Remove extra spaces and normalize
        text = re.sub(r'\s+', ' ', text).strip()
        
        return text
    
    def find_phonetically_similar_username(self, spoken_name: str, threshold: float = 0.6) -> Optional[Tuple[str, float]]:
        """
        Find the most phonetically similar username to the spoken name
        
        Args:
            spoken_name: The name as spoken/recognized by voice
            threshold: Minimum similarity score (0.0 to 1.0)
            
        Returns:
            Tuple of (best_match_username, similarity_score) or None if no good match
        """
        if not PHONETIC_AVAILABLE:
            logger.debug("Phonetic libraries not available, skipping phonetic matching")
            return None
            
        if not self.usernames:
            logger.debug("No usernames available for phonetic matching")
            return None
        
        spoken_name = spoken_name.lower().strip()
        recent_usernames = self.get_recent_usernames()
        
        logger.debug(f"Searching for phonetic match for '{spoken_name}' among {len(recent_usernames)} usernames")
        
        best_match = None
        best_score = 0.0
        
        for username in recent_usernames:
            # Calculate multiple phonetic similarity scores
            scores = []
            
            # Use both original and cleaned versions for comparison
            spoken_clean = self._clean_for_phonetic(spoken_name)
            username_clean = self._clean_for_phonetic(username)
            
            # 1. Jaro-Winkler similarity on original strings
            jaro_original = jellyfish.jaro_winkler_similarity(spoken_name, username)
            scores.append(jaro_original)
            
            # 2. Jaro-Winkler similarity on cleaned strings
            jaro_clean = jellyfish.jaro_winkler_similarity(spoken_clean, username_clean)
            scores.append(jaro_clean)
            
            # 3. Levenshtein distance converted to similarity (original)
            lev_distance = jellyfish.levenshtein_distance(spoken_name, username)
            max_len = max(len(spoken_name), len(username))
            lev_similarity = 1.0 - (lev_distance / max_len) if max_len > 0 else 0.0
            scores.append(lev_similarity)
            
            # 4. Soundex comparison (cleaned)
            try:
                spoken_soundex = jellyfish.soundex(spoken_clean)
                username_soundex = jellyfish.soundex(username_clean)
                soundex_match = 1.0 if spoken_soundex == username_soundex else 0.0
                scores.append(soundex_match)
            except:
                scores.append(0.0)
            
            # 5. Metaphone comparison (cleaned)
            try:
                spoken_metaphone = jellyfish.metaphone(spoken_clean)
                username_metaphone = jellyfish.metaphone(username_clean)
                metaphone_match = 1.0 if spoken_metaphone == username_metaphone else 0.0
                scores.append(metaphone_match)
            except:
                scores.append(0.0)
            
            # 6. Double Metaphone comparison (cleaned)
            try:
                spoken_dmetaphone = dmetaphone(spoken_clean)
                username_dmetaphone = dmetaphone(username_clean)
                # Check if any of the double metaphone codes match
                dmetaphone_match = 0.0
                for s_code in spoken_dmetaphone:
                    for u_code in username_dmetaphone:
                        if s_code and u_code and s_code == u_code:
                            dmetaphone_match = 1.0
                            break
                    if dmetaphone_match > 0:
                        break
                scores.append(dmetaphone_match)
            except:
                scores.append(0.0)
            
            # Calculate weighted average score
            # Give more weight to Jaro-Winkler scores
            weights = [0.3, 0.3, 0.2, 0.1, 0.05, 0.05][:len(scores)]
            weighted_score = sum(score * weight for score, weight in zip(scores, weights))
            
            if weighted_score > best_score:
                best_score = weighted_score
                best_match = username
        
        if best_match and best_score >= threshold:
            logger.info(f"Phonetic match: '{spoken_name}' -> '{best_match}' (score: {best_score:.3f})")
            return best_match, best_score
        else:
            logger.debug(f"No phonetic match found for '{spoken_name}' (best score: {best_score:.3f}, threshold: {threshold})")
            return None
    
    def find_ai_similar_username(self, spoken_name: str) -> Optional[Tuple[str, str]]:
        """
        Use OpenAI to find the best matching username from recent chat
        
        Args:
            spoken_name: The name as spoken/recognized by voice
            
        Returns:
            Tuple of (best_match_username, reasoning) or None if no good match
        """
        if not self.usernames:
            logger.warning("No usernames available for AI matching")
            return None
            
        if not self.openai_client:
            logger.error("OpenAI client not available for username matching")
            return None
        
        spoken_name = spoken_name.lower().strip()
        recent_usernames = self.get_recent_usernames()
        
        logger.info(f"Using AI to match '{spoken_name}' among {len(recent_usernames)} usernames")
        
        try:
            # Create a prompt for OpenAI to match usernames
            username_list = "\n".join([f"- {username}" for username in recent_usernames])
            
            prompt = f"""You are helping match a spoken username to an actual Twitch username from recent chat.

Spoken username: "{spoken_name}"

Recent chat usernames:
{username_list}

Please find the best matching username from the list above. Consider:
- Phonetic similarity (how it sounds when spoken)
- Leet speak (1=i, 3=e, 4=a, 5=s, 7=t, 0=o)
- Common misspellings or voice recognition errors
- Underscores, numbers, and special characters that might be omitted when speaking
- Twitch usernames are always lowercase
- Abbreviations or shortened forms (e.g., "stn" for "ston")

If you find a good match, respond with ONLY the exact username from the list.
If no reasonable match exists, respond with "NO_MATCH".

Examples:
- "viking king" might match "v1king_k1ng" or "vikingking123"
- "test user" might match "testuser" or "test_user_42"
- "john smith" might match "johnsmith2024" or "john_smith_"
- "igorston" might match "igor_stn" (stn = ston abbreviated)
- "alexdoe" might match "alex_d" or "alexd123"
- "mikejones" might match "mike_j" or "mikej_"

Your response:"""

            response = self.openai_client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": "You are a username matching expert. Be precise and only return exact usernames from the provided list or 'NO_MATCH'."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=50,
                temperature=0.1  # Low temperature for consistent results
            )
            
            ai_response = response.choices[0].message.content.strip()
            
            # Check if AI found a match
            if ai_response == "NO_MATCH" or not ai_response:
                logger.info(f"AI found no match for '{spoken_name}'")
                return None
            
            # Verify the AI response is actually in our username list
            if ai_response.lower() in [u.lower() for u in recent_usernames]:
                # Find the exact case-sensitive match
                matched_username = next(u for u in recent_usernames if u.lower() == ai_response.lower())
                logger.info(f"AI matched '{spoken_name}' -> '{matched_username}'")
                return matched_username, f"AI matched based on phonetic similarity and patterns"
            else:
                logger.warning(f"AI returned invalid username: '{ai_response}' not in recent chat")
                return None
                
        except Exception as e:
            logger.error(f"Error using AI for username matching: {e}")
            return None


class AIModerationHelper:
    """Helper class to integrate AI username matching with moderation commands"""
    
    def __init__(self, username_logger: UsernameLogger):
        self.username_logger = username_logger
    
    def resolve_username(self, spoken_username: str) -> Optional[str]:
        """
        Resolve a spoken username to an actual username from chat using multiple methods
        
        Args:
            spoken_username: Username as recognized by voice
            
        Returns:
            Resolved username or None if no match found
        """
        # Step 1: Try exact match (case insensitive)
        recent_usernames = self.username_logger.get_recent_usernames()
        spoken_lower = spoken_username.lower()
        
        for username in recent_usernames:
            if username.lower() == spoken_lower:
                logger.info(f"✅ Exact match: '{spoken_username}' -> '{username}'")
                return username
        
        # Step 2: Try fuzzy matching for common patterns
        fuzzy_match = self._try_fuzzy_match(spoken_lower, recent_usernames)
        if fuzzy_match:
            logger.info(f"🔍 Fuzzy match: '{spoken_username}' -> '{fuzzy_match}'")
            return fuzzy_match
        
        # Step 3: Try phonetic matching (fast and free)
        phonetic_result = self.username_logger.find_phonetically_similar_username(spoken_username, threshold=0.6)
        if phonetic_result:
            matched_username, score = phonetic_result
            logger.info(f"🔊 Phonetic match: '{spoken_username}' -> '{matched_username}' (score: {score:.3f})")
            return matched_username
        
        # Step 4: If phonetic fails, fall back to AI matching (slower but more intelligent)
        ai_result = self.username_logger.find_ai_similar_username(spoken_username)
        if ai_result:
            matched_username, reasoning = ai_result
            logger.info(f"🤖 AI match: '{spoken_username}' -> '{matched_username}' ({reasoning})")
            return matched_username
        
        logger.warning(f"❌ No username match found for: '{spoken_username}'")
        return None
    
    def _try_fuzzy_match(self, spoken_lower: str, recent_usernames: List[str]) -> Optional[str]:
        """Try fuzzy matching for common patterns"""
        for username in recent_usernames:
            username_lower = username.lower()
            
            # Remove underscores and numbers for comparison
            spoken_clean = ''.join(c for c in spoken_lower if c.isalpha())
            username_clean = ''.join(c for c in username_lower if c.isalpha())
            
            # Pattern 1: Check if spoken name contains the username (e.g., "alicejones" contains "alice")
            if spoken_clean.startswith(username_clean) and len(username_clean) >= 3:
                return username
            
            # Pattern 2: Check if username parts can form the spoken name
            # e.g., "igor_stn" -> "igor" + "stn" could match "igorston"
            if '_' in username_lower:
                username_parts = [part for part in username_lower.split('_') if part]
                username_parts_clean = [''.join(c for c in part if c.isalpha()) for part in username_parts]
                
                # Try to reconstruct spoken name from username parts
                reconstructed = ''.join(username_parts_clean)
                
                # Check if spoken name starts with first part and contains abbreviation of second part
                if (len(username_parts_clean) >= 2 and 
                    spoken_clean.startswith(username_parts_clean[0]) and
                    len(username_parts_clean[0]) >= 3):
                    
                    remaining_spoken = spoken_clean[len(username_parts_clean[0]):]
                    second_part = username_parts_clean[1]
                    
                    # Check if the remaining spoken part could be an expansion of the second part
                    # e.g., "ston" could be an expansion of "stn"
                    if (len(second_part) >= 2 and len(remaining_spoken) >= len(second_part) and
                        remaining_spoken.startswith(second_part)):
                        return username
                    
                    # Also check if second part could be abbreviation of remaining spoken
                    # e.g., "stn" could be abbreviation of "ston"
                    if (len(second_part) >= 2 and len(remaining_spoken) >= 3 and
                        all(char in remaining_spoken for char in second_part)):
                        # Check if characters appear in order
                        pos = 0
                        for char in second_part:
                            pos = remaining_spoken.find(char, pos)
                            if pos == -1:
                                break
                            pos += 1
                        else:
                            return username
            
            # Pattern 3: Check if username is contained within spoken name
            if len(username_clean) >= 3 and username_clean in spoken_clean:
                return username
        
        return None 