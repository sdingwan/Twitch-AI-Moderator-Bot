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
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple
from collections import deque
from openai import OpenAI
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
- Case variations

If you find a good match, respond with ONLY the exact username from the list.
If no reasonable match exists, respond with "NO_MATCH".

Examples:
- "viking king" might match "V1king_k1ng" or "VikingKing123"
- "test user" might match "TestUser" or "test_user_42"
- "john smith" might match "johnsmith2024" or "john_smith_"

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
        Resolve a spoken username to an actual username from chat using AI
        
        Args:
            spoken_username: Username as recognized by voice
            
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
        
        # If no exact match, try AI matching
        result = self.username_logger.find_ai_similar_username(spoken_username)
        if result:
            matched_username, reasoning = result
            logger.info(f"AI match: '{spoken_username}' -> '{matched_username}' ({reasoning})")
            return matched_username
        
        logger.warning(f"No username match found for: '{spoken_username}'")
        return None 