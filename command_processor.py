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
    action: str  # 'ban', 'timeout', 'unban', 'clear', 'slow', 'followers_only', 'subscribers_only', etc.
    username: Optional[str] = None
    duration: Optional[int] = None  # in seconds
    reason: Optional[str] = None
    additional_params: Optional[Dict] = None

class CommandProcessor:
    def __init__(self):
        """Initialize the command processor with AI capabilities"""
        self.openai_client = None
        if Config.OPENAI_API_KEY:
            self.openai_client = OpenAI(api_key=Config.OPENAI_API_KEY)
        else:
            logger.error("OpenAI API key not found. Command processing will not work.")
    
    def process_command(self, command_text: str) -> Optional[ModerationCommand]:
        """
        Process a voice command using OpenAI API
        
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
        
        if moderation_cmd:
            logger.info(f"Command processed: {moderation_cmd}")
            return moderation_cmd
        else:
            logger.warning(f"Could not process command: {command_text}")
            return None
    
    def _ai_process_command(self, command_text: str) -> Optional[ModerationCommand]:
        """Use OpenAI to process all commands"""
        try:
            prompt = f"""
            You are a Twitch chat moderation assistant. Parse the following voice command and extract moderation actions.
            
            Command: "{command_text}"
            
            Respond ONLY with a valid JSON object containing:
            - action: one of [ban, unban, timeout, untimeout, clear, slow, slow_off, followers_only, followers_off, subscribers_only, subscribers_off, emote_only, emote_off, restrict, unrestrict, unknown]
            - username: target username (if applicable, null otherwise)
            - duration: duration in seconds (if applicable, null otherwise)
            - reason: reason for action (if mentioned, null otherwise)
            
            Rules for parsing:
            1. BANS are PERMANENT - never set duration for "ban" action, always null
            2. For "timeout" without duration: use {Config.DEFAULT_BAN_DURATION} seconds
            3. For "followers_only" duration means minimum follow time required (e.g., "followers only 10 minutes" = must follow for 10+ minutes to chat)
            4. Convert time units: minutes->seconds (*60), hours->seconds (*3600), days->seconds (*86400)
            5. Clean usernames: lowercase, no spaces, alphanumeric + underscore only
            6. Pay attention to opposite actions: "unban" vs "ban", "untimeout" vs "timeout", etc.
            7. For unclear commands, use "unknown" action
            8. "slow" duration is chat delay in seconds between messages
            9. Only these actions can have durations: timeout, slow, followers_only
            
            Command variations to recognize:
            - "ban", "permanently ban" -> ban (always permanent, duration = null)
            - "timeout", "mute" -> timeout (with duration)
            - "unban", "untimeout", "unmute" -> remove timeout/ban
            - "clear chat", "clear the chat" -> clear
            - "slow mode", "enable slow mode" -> slow
            - "disable slow mode", "turn off slow mode", "slow off" -> slow_off
            - "followers only", "follower mode" -> followers_only
            - "disable followers only", "followers off" -> followers_off
            - "subscribers only", "sub mode", "subs only" -> subscribers_only
            - "disable subscribers only", "subs off" -> subscribers_off
            - "emote only", "emotes only" -> emote_only
            - "disable emote only", "emotes off" -> emote_off
            - "restrict user", "put user in restricted mode" -> restrict
            - "unrestrict user", "remove restrictions" -> unrestrict
            
            Examples:
            "ban johndoe" -> {{"action": "ban", "username": "johndoe", "duration": null, "reason": null}}
            "ban johndoe for spam" -> {{"action": "ban", "username": "johndoe", "duration": null, "reason": "spam"}}
            "permanently ban user123" -> {{"action": "ban", "username": "user123", "duration": null, "reason": null}}
            "timeout user123 for 10 minutes" -> {{"action": "timeout", "username": "user123", "duration": 600, "reason": null}}
            "timeout spammer for spam" -> {{"action": "timeout", "username": "spammer", "duration": {Config.DEFAULT_BAN_DURATION}, "reason": "spam"}}
            "unban johndoe" -> {{"action": "unban", "username": "johndoe", "duration": null, "reason": null}}
            "untimeout user123" -> {{"action": "untimeout", "username": "user123", "duration": null, "reason": null}}
            "clear the chat" -> {{"action": "clear", "username": null, "duration": null, "reason": null}}
            "slow mode 30 seconds" -> {{"action": "slow", "username": null, "duration": 30, "reason": null}}
            "disable slow mode" -> {{"action": "slow_off", "username": null, "duration": null, "reason": null}}
            "followers only 10 minutes" -> {{"action": "followers_only", "username": null, "duration": 600, "reason": null}}
            "followers only mode" -> {{"action": "followers_only", "username": null, "duration": null, "reason": null}}
            "turn off followers only" -> {{"action": "followers_off", "username": null, "duration": null, "reason": null}}
            "subscribers only" -> {{"action": "subscribers_only", "username": null, "duration": null, "reason": null}}
            "disable subs only" -> {{"action": "subscribers_off", "username": null, "duration": null, "reason": null}}
            "emote only mode" -> {{"action": "emote_only", "username": null, "duration": null, "reason": null}}
            "turn off emote only" -> {{"action": "emote_off", "username": null, "duration": null, "reason": null}}
            "restrict baduser" -> {{"action": "restrict", "username": "baduser", "duration": null, "reason": null}}
            "unrestrict gooduser" -> {{"action": "unrestrict", "username": "gooduser", "duration": null, "reason": null}}
            
            Respond with ONLY the JSON object, no other text.
            """
            
            response = self.openai_client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[{"role": "user", "content": prompt}],
                max_tokens=200,
                temperature=0.1
            )
            
            result = response.choices[0].message.content.strip()
            logger.debug(f"AI response: {result}")
            
            # Parse JSON response
            try:
                parsed = json.loads(result)
                if parsed.get('action') != 'unknown':
                    return ModerationCommand(
                        action=parsed.get('action'),
                        username=parsed.get('username'),
                        duration=parsed.get('duration'),
                        reason=parsed.get('reason')
                    )
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
        
        # Commands that can have durations
        duration_allowed_actions = ['timeout', 'slow', 'followers_only']
        
        # Validate username for user-specific actions
        if cmd.action in user_required_actions and not cmd.username:
            return False, f"Username required for {cmd.action} action"
        
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
        if cmd.duration:
            if cmd.duration < 1:
                return False, "Duration must be at least 1 second"
            if cmd.duration > Config.MAX_BAN_DURATION:
                return False, f"Duration cannot exceed {Config.MAX_BAN_DURATION} seconds"
        
        return True, ""
    
    def get_supported_commands(self) -> List[str]:
        """Get list of supported command types"""
        return [
            'ban', 'unban', 'timeout', 'untimeout', 'clear', 'slow', 'slow_off',
            'followers_only', 'followers_off', 'subscribers_only', 'subscribers_off',
            'emote_only', 'emote_off', 'restrict', 'unrestrict'
        ] 