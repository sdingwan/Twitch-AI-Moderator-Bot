import re
import logging
from typing import Dict, Optional, Tuple, List
from dataclasses import dataclass
from openai import OpenAI
from config import Config
import json

logger = logging.getLogger(__name__)

@dataclass
class ModerationCommand:
    action: str  # 'ban', 'timeout', 'unban', 'clear', 'slow', 'followers_only', 'subscribers_only', 'weather', etc.
    username: Optional[str] = None
    duration: Optional[int] = None  # in seconds
    reason: Optional[str] = None
    additional_params: Optional[Dict] = None
    original_username: Optional[str] = None  # Store the original spoken username
    weather_location: Optional[str] = None  # Store weather location for weather commands

class CommandProcessor:
    def __init__(self, phonetic_helper=None):
        """Initialize the command processor with AI capabilities and optional phonetic matching"""
        self.openai_client = None
        self.phonetic_helper = phonetic_helper
        if Config.OPENAI_API_KEY:
            self.openai_client = OpenAI(api_key=Config.OPENAI_API_KEY)
        else:
            logger.error("OpenAI API key not found. Command processing will not work.")
    
    def set_phonetic_helper(self, phonetic_helper):
        """Set the phonetic helper for username resolution"""
        self.phonetic_helper = phonetic_helper
    
    def process_command(self, command_text: str) -> Optional[ModerationCommand]:
        """
        Process a voice command using OpenAI API and phonetic username matching
        
        Args:
            command_text: The recognized voice command text
            
        Returns:
            ModerationCommand object or None if command not recognized
        """
        command_text = command_text.strip()
        logger.info(f"Processing command: {command_text}")
        
        if not self.openai_client:
            logger.error("OpenAI client not available")
            return None
        
        moderation_cmd = self._ai_process_command(command_text)
        
        if moderation_cmd and moderation_cmd.username:
            # Try to resolve the username using phonetic matching
            original_username = moderation_cmd.username
            resolved_username = self._resolve_username(moderation_cmd.username)
            
            if resolved_username:
                moderation_cmd.username = resolved_username
                moderation_cmd.original_username = original_username
                logger.info(f"Username resolved: '{original_username}' -> '{resolved_username}'")
            else:
                logger.warning(f"Could not resolve username: '{original_username}'")
                # Keep the original username but mark it as unresolved
                moderation_cmd.original_username = original_username
        
        if moderation_cmd:
            logger.info(f"Command processed: {moderation_cmd}")
            return moderation_cmd
        else:
            logger.warning(f"Could not process command: {command_text}")
            return None
    
    def _resolve_username(self, spoken_username: str) -> Optional[str]:
        """Resolve a spoken username using AI matching"""
        if not self.phonetic_helper:
            logger.debug("No AI username helper available, using original username")
            return spoken_username
        
        try:
            resolved = self.phonetic_helper.resolve_username(spoken_username)
            return resolved if resolved else spoken_username
        except Exception as e:
            logger.error(f"Error resolving username '{spoken_username}': {e}")
            return spoken_username
    
    def _ai_process_command(self, command_text: str) -> Optional[ModerationCommand]:
        """Use OpenAI to process all commands"""
        try:
            prompt = f"""
            You are a Twitch chat moderation assistant. Parse the following voice command and extract moderation actions.
            
            Command: "{command_text}"
            
            Respond ONLY with a valid JSON object containing:
            - action: one of [ban, unban, timeout, untimeout, clear, slow, slow_off, followers_only, followers_off, subscribers_only, subscribers_off, emote_only, emote_off, restrict, unrestrict, weather, unknown]
            - username: target username (if applicable, null otherwise)
            - duration: duration in seconds (if applicable, null otherwise)
            - reason: reason for action (if mentioned, null otherwise)
            - weather_location: location for weather commands (if applicable, null otherwise)
            
            Rules for parsing:
            1. BANS are PERMANENT - never set duration for "ban" action, always null
            2. For "timeout" without duration: use {Config.DEFAULT_BAN_DURATION} seconds
            3. For "slow mode" without duration: use 10 seconds as default
            4. For "followers_only" default duration is 1 second. Otherwise, use the duration provided.
            5. Convert time units: minutes->seconds (*60), hours->seconds (*3600), days->seconds (*86400)
            6. Clean usernames: lowercase, no spaces, alphanumeric + underscore only
            7. Pay attention to opposite actions: "unban" vs "ban", "untimeout" vs "timeout", etc.
            8. For unclear commands, use "unknown" action
            9. Only these actions can have durations: timeout, slow, followers_only
            10. Always convert weather country to abbreviation. Example: "United States" -> "US" or "United Kingdom" -> "UK" or "Italy" -> "IT"
            
            Command variations to recognize:
            - "ban", "permanently ban", "band", "bend" -> ban (always permanent, duration = null)
            - "timeout", "mute" -> timeout (with duration)
            - "unban", "unben" -> remove ban
            - "untimeout", "un tie mount", "remove timeout" -> remove timeout
            - "clear chat", "clear the chat" -> clear
            - "slow mode", "enable slow mode" -> slow
            - "disable slow mode", "turn off slow mode", "slow off" -> slow_off
            - "followers only", "follower mode" -> followers_only
            - "disable followers only", "followers off", "remove followers only" -> followers_off
            - "subscribers only", "sub mode", "subs only", "sub only" -> subscribers_only
            - "disable subscribers only", "subs off", "sub off", "remove sub only", "remove subs only", "turn off sub only", "turn off subs only", "disable sub only", "disable sub mode" -> subscribers_off
            - "emote only", "emotes only" -> emote_only
            - "disable emote only", "emotes off", "remove emote only" -> emote_off
            - "restrict user", "put user in restricted mode" -> restrict
            - "unrestrict user", "remove restrictions" -> unrestrict
            - "change weather to [location]", "set weather to [location]", "weather location [location]" -> weather
            
            Examples:
            "ban johndoe" -> {{"action": "ban", "username": "johndoe", "duration": null, "reason": null}}
            "permanently ban user123" -> {{"action": "ban", "username": "user123", "duration": null, "reason": null}}
            "timeout user123 for 10 minutes" -> {{"action": "timeout", "username": "user123", "duration": 600, "reason": null}}
            "unban johndoe" -> {{"action": "unban", "username": "johndoe", "duration": null, "reason": null}}
            "untimeout user123" -> {{"action": "untimeout", "username": "user123", "duration": null, "reason": null}}
            "clear the chat" -> {{"action": "clear", "username": null, "duration": null, "reason": null}}
            "slow mode" -> {{"action": "slow", "username": null, "duration": 10, "reason": null}}
            "slow mode 30 seconds" -> {{"action": "slow", "username": null, "duration": 30, "reason": null}}
            "disable slow mode" -> {{"action": "slow_off", "username": null, "duration": null, "reason": null}}
            "followers only 10 minutes" -> {{"action": "followers_only", "username": null, "duration": 600, "reason": null}}
            "followers only mode" -> {{"action": "followers_only", "username": null, "duration": 1, "reason": null}}
            "turn off followers only" -> {{"action": "followers_off", "username": null, "duration": null, "reason": null}}
            "remove followers only" -> {{"action": "followers_off", "username": null, "duration": null, "reason": null}}
            "subscribers only" -> {{"action": "subscribers_only", "username": null, "duration": null, "reason": null}}
            "sub only" -> {{"action": "subscribers_only", "username": null, "duration": null, "reason": null}}
            "subs only mode" -> {{"action": "subscribers_only", "username": null, "duration": null, "reason": null}}
            "disable subs only" -> {{"action": "subscribers_off", "username": null, "duration": null, "reason": null}}
            "remove sub only" -> {{"action": "subscribers_off", "username": null, "duration": null, "reason": null}}
            "turn off sub only" -> {{"action": "subscribers_off", "username": null, "duration": null, "reason": null}}
            "emote only mode" -> {{"action": "emote_only", "username": null, "duration": null, "reason": null}}
            "turn off emote only" -> {{"action": "emote_off", "username": null, "duration": null, "reason": null, "weather_location": null}}
            "restrict baduser" -> {{"action": "restrict", "username": "baduser", "duration": null, "reason": null, "weather_location": null}}
            "unrestrict gooduser" -> {{"action": "unrestrict", "username": "gooduser", "duration": null, "reason": null, "weather_location": null}}
            "change weather to Naples, Italy" -> {{"action": "weather", "username": null, "duration": null, "reason": null, "weather_location": "Naples, IT"}}
            "set weather to Tokyo, Japan" -> {{"action": "weather", "username": null, "duration": null, "reason": null, "weather_location": "Tokyo, JP"}}
            
            Respond with ONLY the JSON object, no other text.
            """
            
            response = self.openai_client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[{"role": "user", "content": prompt}],
                max_tokens=200,
                temperature=0.2
            )
            
            result = response.choices[0].message.content.strip()
            logger.debug(f"AI response: {result}")
            
            # Parse JSON response
            try:
                parsed = json.loads(result)
                logger.debug(f"Parsed AI response: {parsed}")
                
                if parsed.get('action') != 'unknown':
                    cmd = ModerationCommand(
                        action=parsed.get('action'),
                        username=parsed.get('username'),
                        duration=parsed.get('duration'),
                        reason=parsed.get('reason'),
                        weather_location=parsed.get('weather_location')
                    )
                    
                    # Post-process: Ensure slow mode always has a duration (default 10 seconds)
                    if cmd.action == 'slow' and cmd.duration is None:
                        cmd.duration = 10
                        logger.debug(f"Applied default slow mode duration: 10 seconds")
                    
                    logger.debug(f"Created command object: {cmd}")
                    return cmd
                else:
                    logger.info(f"Command not recognized as moderation action: {command_text}")
                    return None
            except json.JSONDecodeError:
                logger.error(f"Failed to parse AI response as JSON: {result}")
                return None
            
        except Exception as e:
            logger.error(f"AI command processing failed: {e}")
            return None
    
    def validate_command(self, cmd: ModerationCommand) -> Tuple[bool, str]:
        """
        Validate a moderation command
        
        Returns:
            Tuple of (is_valid, error_message)
        """
        if not cmd.action:
            return False, "No action specified"
        
        # Commands that require a username
        user_required_actions = ['ban', 'unban', 'timeout', 'untimeout', 'restrict', 'unrestrict']
        
        # Commands that require a weather location
        weather_required_actions = ['weather']
        
        # Commands that can have durations
        duration_allowed_actions = ['timeout', 'slow', 'followers_only']
        
        # Validate username for user-specific actions
        if cmd.action in user_required_actions and not cmd.username:
            return False, f"Username required for {cmd.action} action"
        
        # Validate weather location for weather actions
        if cmd.action in weather_required_actions and not cmd.weather_location:
            return False, f"Weather location required for {cmd.action} action"
        
        # Validate username format
        if cmd.username:
            if not re.match(r'^[a-zA-Z0-9_]{1,25}$', cmd.username):
                return False, f"Invalid username format: {cmd.username}"
        
        # Validate that bans never have durations (they are permanent)
        if cmd.action == 'ban' and cmd.duration is not None:
            return False, "Bans are permanent and cannot have durations"
        
        # Validate that only certain actions can have durations
        if cmd.duration is not None and cmd.action not in duration_allowed_actions:
            return False, f"Duration not allowed for {cmd.action} action"
        
        # Validate duration limits
        if cmd.duration is not None:
            # For followers_only, duration 0 is valid (no minimum follow time)
            if cmd.action == 'followers_only':
                if cmd.duration < 0:
                    return False, "Duration cannot be negative"
            else:
                # For other actions, duration must be at least 1 second
                if cmd.duration < 1:
                    return False, "Duration must be at least 1 second"
            
            # Check maximum duration for all actions
            if cmd.duration > Config.MAX_BAN_DURATION:
                return False, f"Duration cannot exceed {Config.MAX_BAN_DURATION} seconds"
        
        return True, ""
    
    def get_supported_commands(self) -> List[str]:
        """Get list of supported command types"""
        return [
            'ban', 'unban', 'timeout', 'untimeout', 'clear', 'slow', 'slow_off',
            'followers_only', 'followers_off', 'subscribers_only', 'subscribers_off',
            'emote_only', 'emote_off', 'restrict', 'unrestrict', 'weather'
        ] 