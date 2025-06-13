#!/usr/bin/env python3
"""
Username Logger and AI-powered Username Matcher for Twitch Chat
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
        
        # Initialize OpenAI client for intelligent username matching
        self.openai_client = OpenAI(api_key=Config.OPENAI_API_KEY)
        
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
    
    async def find_similar_username_with_ai(self, spoken_name: str) -> Optional[str]:
        """
        Use OpenAI API to find the best matching username from recent chat users
        
        Args:
            spoken_name: The name as spoken/recognized by voice
            
        Returns:
            Best matching username or None if no good match
        """
        if not self.usernames:
            logger.warning("No usernames available for AI matching")
            return None
        
        recent_usernames = self.get_recent_usernames()
        logger.info(f"Using AI to match '{spoken_name}' against {len(recent_usernames)} usernames")
        
        try:
            # Prepare the prompt for OpenAI
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
                temperature=0.1  # Low temperature for consistent results
            )
            
            matched_username = response.choices[0].message.content.strip()
            
            # Validate the response
            if matched_username == "NONE" or matched_username not in recent_usernames:
                logger.info(f"AI found no good match for '{spoken_name}' (returned: '{matched_username}')")
                return None
            
            logger.info(f"AI matched '{spoken_name}' -> '{matched_username}'")
            return matched_username
            
        except Exception as e:
            logger.error(f"Error using AI for username matching: {e}")
            # Fallback to simple exact match
            spoken_lower = spoken_name.lower()
            for username in recent_usernames:
                if username.lower() == spoken_lower:
                    logger.info(f"Fallback exact match: '{spoken_name}' -> '{username}'")
                    return username
            return None


class AIModerationHelper:
    """Helper class to integrate AI username matching with moderation commands"""
    
    def __init__(self, username_logger: UsernameLogger):
        self.username_logger = username_logger
    
    async def resolve_username(self, spoken_username: str) -> Optional[str]:
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
        
        # If no exact match, use AI matching
        matched_username = await self.username_logger.find_similar_username_with_ai(spoken_username)
        if matched_username:
            logger.info(f"AI match: '{spoken_username}' -> '{matched_username}'")
            return matched_username
        
        logger.warning(f"No username match found for: '{spoken_username}'")
        return None 