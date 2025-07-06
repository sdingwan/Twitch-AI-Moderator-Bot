#!/usr/bin/env python3
"""
Username Logger for Kick.com Chat
Monitors Kick chat via WebSocket, logs usernames, and provides AI-powered matching for voice commands
"""

import asyncio
import json
import logging
import time
import websockets
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple, Callable, Any
from collections import deque
from openai import OpenAI
from ...core.config import Config

# Import phonetic libraries with fallback
try:
    import jellyfish
    from phonetics import dmetaphone
    PHONETIC_AVAILABLE = True
except ImportError:
    PHONETIC_AVAILABLE = False

logger = logging.getLogger(__name__)

class KickUsernameLogger:
    def __init__(self, max_usernames: int = 50, update_interval: int = 0.3, username_callback: Optional[Callable] = None, kick_api=None):
        """
        Initialize the Kick username logger with integrated chat monitoring
        
        Args:
            max_usernames: Maximum number of usernames to keep in memory and log file
            update_interval: How often to update the log file (in seconds)
            username_callback: Callback function for when usernames are detected in chat
            kick_api: Authenticated KickAPI instance to use for getting channel info
        """
        self.max_usernames = max_usernames
        self.update_interval = update_interval
        self.usernames = deque(maxlen=max_usernames)
        self.log_file = "kick_chat_usernames.log"
        self.is_running = False
        self.last_update = 0
        self.username_callback = username_callback
        self.kick_api = kick_api
        
        # WebSocket chat monitoring
        self.websocket = None
        self.chatroom_id = None
        
        # Kick's Pusher configuration
        self.app_key = "32cbd69e4b950bf97679"  # Kick's public Pusher key
        self.cluster = "us2"  # Kick's Pusher cluster (us2 = Ohio)
        self.ws_url = f"wss://ws-{self.cluster}.pusher.com/app/{self.app_key}?protocol=7&client=js&version=7.6.0&flash=false"
        
        # Initialize OpenAI client for AI-based username matching
        self.openai_client = None
        if Config.OPENAI_API_KEY:
            self.openai_client = OpenAI(api_key=Config.OPENAI_API_KEY)
        else:
            logger.warning("OpenAI API key not found. AI username matching will not work for Kick.")
        
        # Ensure log file exists
        self._initialize_log_file()
    
    def _initialize_log_file(self):
        """Initialize the log file with proper format"""
        try:
            with open(self.log_file, 'w') as f:
                f.write(f"# Kick Chat Usernames Log - Started at {datetime.now()}\n")
                f.write("# Format: timestamp,username\n")
            logger.info(f"Initialized Kick username log file: {self.log_file}")
        except Exception as e:
            logger.error(f"Failed to initialize Kick log file: {e}")
    
    async def initialize(self):
        """Initialize the Kick chat monitor for the configured channel"""
        try:
            # Use requests instead of aiohttp to match the working translator approach
            import requests
            headers = {"User-Agent": "Mozilla/5.0 (compatible; TranslatorBot/1.0)"}
            
            response = requests.get(f"https://kick.com/api/v2/channels/{Config.KICK_CHANNEL}", headers=headers)
            if response.status_code == 200:
                channel_info = response.json()
                self.chatroom_id = channel_info['chatroom']['id']
                logger.info(f"✅ Kick chat monitor initialized for channel: {Config.KICK_CHANNEL} (chatroom_id: {self.chatroom_id})")
                return True
            else:
                logger.error(f"Failed to get channel info via public API: {response.status_code} - {response.text}")
                return False
                
        except Exception as e:
            logger.error(f"Failed to initialize Kick chat monitor: {e}")
            return False
    
    async def start_monitoring(self):
        """Start monitoring Kick chat for usernames"""
        self.is_running = True
        logger.info(f"Starting Kick username monitoring for channel: {Config.KICK_CHANNEL}")
        
        while self.is_running:
            try:
                await self._connect_and_monitor()
            except Exception as e:
                logger.error(f"Kick WebSocket connection error: {e}")
                if self.is_running:
                    logger.info("Reconnecting to Kick in 5 seconds...")
                    await asyncio.sleep(5)
    
    async def _connect_and_monitor(self):
        """Connect to Kick WebSocket and monitor chat"""
        try:
            # Connect to Kick's Pusher WebSocket
            self.websocket = await websockets.connect(self.ws_url)
            logger.info("Connected to Kick WebSocket")
            
            # Subscribe to the chatroom channel
            if self.chatroom_id:
                subscribe_msg = {
                    "event": "pusher:subscribe",
                    "data": {
                        "auth": "",
                        "channel": f"chatrooms.{self.chatroom_id}.v2"
                    }
                }
                await self.websocket.send(json.dumps(subscribe_msg))
                logger.info(f"Subscribed to Kick chatroom: {self.chatroom_id}")
            
            # Listen for messages
            while self.is_running:
                try:
                    message = await asyncio.wait_for(self.websocket.recv(), timeout=30.0)
                    await self._process_websocket_message(message)
                except asyncio.TimeoutError:
                    # Send ping to keep connection alive
                    ping_msg = {"event": "pusher:ping", "data": {}}
                    await self.websocket.send(json.dumps(ping_msg))
                except Exception as e:
                    logger.error(f"Error receiving Kick message: {e}")
                    break
                    
        except Exception as e:
            logger.error(f"Kick WebSocket connection error: {e}")
            raise
        finally:
            if self.websocket:
                await self.websocket.close()
    
    async def _process_websocket_message(self, message: str):
        """Process incoming Kick WebSocket message"""
        try:
            msg = json.loads(message)
            event = msg.get("event")
            
            # Handle different message types
            if event == "pusher:connection_established":
                logger.info("✅ Kick WebSocket connection established")
            
            elif event == "pusher:pong":
                logger.debug("📡 Kick WebSocket pong received")
            
            elif event == "App\\Events\\ChatMessageEvent":
                # Chat message event - extract username
                payload = json.loads(msg["data"])
                username = payload["sender"]["username"]
                message_content = payload["content"]
                
                # Log the chat message
                logger.debug(f"Kick chat - {username}: {message_content}")
                
                # Add username to our logger for AI matching
                await self._add_username(username)
                
                # Call username callback if provided
                if self.username_callback:
                    await self.username_callback(username, "kick")
            
            else:
                logger.debug(f"Kick WebSocket event: {event}")
                
        except Exception as e:
            logger.error(f"Error processing Kick WebSocket message: {e}")
    
    async def stop_monitoring(self):
        """Stop monitoring chat"""
        self.is_running = False
        if self.websocket:
            await self.websocket.close()
        logger.info("Kick chat monitoring stopped")
    
    async def _add_username(self, username: str):
        """Add username to the collection and update log file if needed"""
        username = username.lower().strip()
        
        # Add to deque (automatically handles max size)
        self.usernames.append({
            'username': username,
            'timestamp': datetime.now().isoformat()
        })
        
        logger.debug(f"Added Kick username: {username}")
        
        # Update log file periodically
        current_time = time.time()
        if current_time - self.last_update >= self.update_interval:
            await self._update_log_file()
            self.last_update = current_time
    
    async def _update_log_file(self):
        """Update the log file with current usernames"""
        try:
            with open(self.log_file, 'w') as f:
                f.write(f"# Kick Chat Usernames Log - Updated at {datetime.now()}\n")
                f.write("# Format: timestamp,username\n")
                
                for entry in self.usernames:
                    f.write(f"{entry['timestamp']},{entry['username']}\n")
            
            logger.debug(f"Updated Kick log file with {len(self.usernames)} usernames")
            
        except Exception as e:
            logger.error(f"Failed to update Kick log file: {e}")
    
    def get_recent_usernames(self) -> List[str]:
        """Get list of recent usernames"""
        return [entry['username'] for entry in self.usernames]
    
    def _clean_for_phonetic(self, text: str) -> str:
        """Clean text for better phonetic matching by normalizing numbers and special characters"""
        import re
        
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
            logger.debug("No Kick usernames available for phonetic matching")
            return None
        
        spoken_name = spoken_name.lower().strip()
        recent_usernames = self.get_recent_usernames()
        
        logger.debug(f"Searching for phonetic match for '{spoken_name}' among {len(recent_usernames)} Kick usernames")
        
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
            logger.info(f"Kick phonetic match: '{spoken_name}' -> '{best_match}' (score: {best_score:.3f})")
            return best_match, best_score
        else:
            logger.debug(f"No Kick phonetic match found for '{spoken_name}' (best score: {best_score:.3f}, threshold: {threshold})")
            return None
    
    def find_ai_similar_username(self, spoken_name: str) -> Optional[Tuple[str, str]]:
        """
        Use OpenAI to find the best matching username from recent Kick chat
        
        Args:
            spoken_name: The name as spoken/recognized by voice
            
        Returns:
            Tuple of (best_match_username, reasoning) or None if no good match
        """
        if not self.usernames:
            logger.warning("No Kick usernames available for AI matching")
            return None
            
        if not self.openai_client:
            logger.error("OpenAI client not available for Kick username matching")
            return None
        
        spoken_name = spoken_name.lower().strip()
        recent_usernames = self.get_recent_usernames()
        
        logger.info(f"Using AI to match '{spoken_name}' among {len(recent_usernames)} Kick usernames")
        
        try:
            # Create a prompt for OpenAI to match usernames
            username_list = "\n".join([f"- {username}" for username in recent_usernames])
            
            prompt = f"""You are helping match a spoken username to an actual Kick.com username from recent chat.

Spoken username: "{spoken_name}"

Recent Kick chat usernames:
{username_list}

Please find the best matching username from the list above. Consider:
- Phonetic similarity (how it sounds when spoken)
- Leet speak (1=i, 3=e, 4=a, 5=s, 7=t, 0=o)
- Common misspellings or voice recognition errors
- Underscores, numbers, and special characters that might be omitted when speaking
- Kick usernames are always lowercase
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
                    {"role": "system", "content": "You are a username matching expert for Kick.com. Be precise and only return exact usernames from the provided list or 'NO_MATCH'."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=50,
                temperature=0.1  # Low temperature for consistent results
            )
            
            ai_response = response.choices[0].message.content.strip()
            
            # Check if AI found a match
            if ai_response == "NO_MATCH" or not ai_response:
                logger.info(f"AI found no match for '{spoken_name}' in Kick chat")
                return None
            
            # Verify the AI response is actually in our username list
            if ai_response.lower() in [u.lower() for u in recent_usernames]:
                # Find the exact case-sensitive match
                matched_username = next(u for u in recent_usernames if u.lower() == ai_response.lower())
                logger.info(f"Kick AI matched '{spoken_name}' -> '{matched_username}'")
                return matched_username, f"AI matched based on phonetic similarity and patterns"
            else:
                logger.warning(f"AI returned invalid Kick username: '{ai_response}' not in recent chat")
                return None
                
        except Exception as e:
            logger.error(f"Error using AI for Kick username matching: {e}")
            return None


class KickAIModerationHelper:
    """Helper class to integrate AI username matching with Kick moderation commands"""
    
    def __init__(self, username_logger: KickUsernameLogger):
        self.username_logger = username_logger
    
    def get_ai_helper(self) -> 'KickAIModerationHelper':
        """Get the AI moderation helper for username matching"""
        return self
    
    def get_recent_usernames(self) -> List[str]:
        """Get list of recent usernames from chat"""
        return self.username_logger.get_recent_usernames()
    
    def resolve_username(self, spoken_username: str) -> Optional[str]:
        """
        Resolve a spoken username to an actual Kick username from chat using multiple methods
        
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
                logger.info(f"✅ Kick exact match: '{spoken_username}' -> '{username}'")
                return username
        
        # Step 2: Try fuzzy matching for common patterns
        fuzzy_match = self._try_fuzzy_match(spoken_lower, recent_usernames)
        if fuzzy_match:
            logger.info(f"🔍 Kick fuzzy match: '{spoken_username}' -> '{fuzzy_match}'")
            return fuzzy_match
        
        # Step 3: Try phonetic matching (fast and free)
        phonetic_result = self.username_logger.find_phonetically_similar_username(spoken_username, threshold=0.6)
        if phonetic_result:
            matched_username, score = phonetic_result
            logger.info(f"🔊 Kick phonetic match: '{spoken_username}' -> '{matched_username}' (score: {score:.3f})")
            return matched_username
        
        # Step 4: If phonetic fails, fall back to AI matching (slower but more intelligent)
        ai_result = self.username_logger.find_ai_similar_username(spoken_username)
        if ai_result:
            matched_username, reasoning = ai_result
            logger.info(f"🤖 Kick AI match: '{spoken_username}' -> '{matched_username}' ({reasoning})")
            return matched_username
        
        logger.warning(f"❌ No Kick username match found for: '{spoken_username}'")
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
    
    def find_best_username_matches(self, partial_username: str, max_results: int = 5) -> List[str]:
        """
        Find the best username matches for a partial username (used by multi-platform manager)
        
        Args:
            partial_username: Partial username to match
            max_results: Maximum number of results to return
            
        Returns:
            List of matching usernames
        """
        # Try to resolve the username using all available methods
        resolved = self.resolve_username(partial_username)
        if resolved:
            return [resolved]
        
        # If no perfect match, return fuzzy matches
        recent_usernames = self.username_logger.get_recent_usernames()
        fuzzy_matches = [username for username in recent_usernames 
                        if partial_username.lower() in username.lower()][:max_results]
        
        return fuzzy_matches 