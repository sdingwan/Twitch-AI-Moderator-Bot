#!/usr/bin/env python3
"""
Username Logger and Phonetic Matcher for Twitch Chat
Monitors Twitch IRC chat, logs usernames, and provides phonetic matching for voice commands
"""

import asyncio
import json
import logging
import time
import socket
import ssl
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple
from collections import deque
import jellyfish
from phonetics import dmetaphone, soundex
from config import Config

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
    
    def find_phonetically_similar_username(self, spoken_name: str, threshold: float = 0.6) -> Optional[Tuple[str, float]]:
        """
        Find the most phonetically similar username to the spoken name
        
        Args:
            spoken_name: The name as spoken/recognized by voice
            threshold: Minimum similarity score (0.0 to 1.0)
            
        Returns:
            Tuple of (best_match_username, similarity_score) or None if no good match
        """
        if not self.usernames:
            logger.warning("No usernames available for phonetic matching")
            return None
        
        spoken_name = spoken_name.lower().strip()
        recent_usernames = self.get_recent_usernames()
        
        logger.info(f"Searching for phonetic match for '{spoken_name}' among {len(recent_usernames)} usernames")
        
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
            
            logger.debug(f"Username '{username}' scores: {scores}, weighted: {weighted_score:.3f}")
            
            if weighted_score > best_score:
                best_score = weighted_score
                best_match = username
        
        if best_match and best_score >= threshold:
            logger.info(f"Found phonetic match: '{spoken_name}' -> '{best_match}' (score: {best_score:.3f})")
            return best_match, best_score
        else:
            logger.info(f"No phonetic match found for '{spoken_name}' (best score: {best_score:.3f}, threshold: {threshold})")
            return None
    
    def _clean_for_phonetic(self, text: str) -> str:
        """Clean text for better phonetic matching by normalizing numbers and special characters"""
        import re
        
        # More conservative number replacement - only replace when they're likely to be pronounced
        # Replace common leet speak patterns
        text = text.replace('1', 'i').replace('3', 'e').replace('4', 'a')
        text = text.replace('5', 's').replace('7', 't').replace('0', 'o')
        
        # Remove or replace special characters with spaces
        text = text.replace('_', ' ').replace('-', ' ').replace('.', ' ')
        
        # Remove extra spaces and normalize
        text = re.sub(r'\s+', ' ', text).strip()
        
        return text


class PhoneticModerationHelper:
    """Helper class to integrate phonetic username matching with moderation commands"""
    
    def __init__(self, username_logger: UsernameLogger):
        self.username_logger = username_logger
    
    def resolve_username(self, spoken_username: str, threshold: float = 0.5) -> Optional[str]:
        """
        Resolve a spoken username to an actual username from chat
        
        Args:
            spoken_username: Username as recognized by voice
            threshold: Minimum similarity threshold (lowered to 0.5 for better matching)
            
        Returns:
            Resolved username or None if no match found
        """
        # First try exact match (case insensitive)
        recent_usernames = self.username_logger.get_recent_usernames()
        spoken_lower = spoken_username.lower()
        
        for username in recent_usernames:
            if username.lower() == spoken_lower:
                logger.info(f"Exact match found: '{spoken_username}' -> '{username}'")
                return username
        
        # If no exact match, try phonetic matching
        result = self.username_logger.find_phonetically_similar_username(spoken_username, threshold)
        if result:
            matched_username, score = result
            logger.info(f"Phonetic match: '{spoken_username}' -> '{matched_username}' (score: {score:.3f})")
            return matched_username
        
        logger.warning(f"No username match found for: '{spoken_username}'")
        return None 