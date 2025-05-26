import re
import logging
from typing import Dict, Optional, Tuple, List
from dataclasses import dataclass
from openai import OpenAI
from config import Config

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
        
        # Predefined patterns for common commands
        # NOTE: Order matters! More specific patterns (like 'unban') should come before general ones (like 'ban')
        self.command_patterns = {
            'unban': [
                r'unban\s+(\w+)',
                r'un\s*ban\s+(\w+)',
                r'remove\s+ban\s+(?:from\s+)?(\w+)',
                r'lift\s+ban\s+(?:from\s+)?(\w+)',
                r'pardon\s+(\w+)'
            ],
            'ban': [
                r'ban\s+(\w+)(?:\s+for\s+(\d+)\s*(minutes?|mins?|hours?|hrs?|seconds?|secs?))?',
                r'ban\s+(\w+)(?:\s+(\d+)\s*(minutes?|mins?|hours?|hrs?|seconds?|secs?))?',
                r'permanently\s+ban\s+(\w+)',
                r'perma\s+ban\s+(\w+)'
            ],
            'timeout': [
                r'timeout\s+(\w+)(?:\s+for\s+(\d+)\s*(minutes?|mins?|hours?|hrs?|seconds?|secs?))?',
                r'time\s*out\s+(\w+)(?:\s+(\d+)\s*(minutes?|mins?|hours?|hrs?|seconds?|secs?))?',
                r'mute\s+(\w+)(?:\s+for\s+(\d+)\s*(minutes?|mins?|hours?|hrs?|seconds?|secs?))?'
            ],
            'clear': [
                r'clear\s+chat',
                r'clear\s+the\s+chat',
                r'delete\s+all\s+messages'
            ],
            'slow': [
                r'slow\s+mode\s+(\d+)',
                r'enable\s+slow\s+mode\s+(\d+)',
                r'set\s+slow\s+mode\s+to\s+(\d+)'
            ],
            'followers_only': [
                r'followers?\s+only\s+mode',
                r'enable\s+followers?\s+only',
                r'followers?\s+only\s+(\d+)\s*(minutes?|mins?|hours?|hrs?|days?)'
            ],
            'subscribers_only': [
                r'subscribers?\s+only\s+mode',
                r'enable\s+subscribers?\s+only',
                r'subs?\s+only\s+mode',
                r'subscriber\s+mode',
                r'sub\s+mode'
            ]
        }
        
        # Time unit conversions to seconds
        self.time_units = {
            'second': 1, 'seconds': 1, 'sec': 1, 'secs': 1,
            'minute': 60, 'minutes': 60, 'min': 60, 'mins': 60,
            'hour': 3600, 'hours': 3600, 'hr': 3600, 'hrs': 3600,
            'day': 86400, 'days': 86400
        }
    
    def process_command(self, command_text: str) -> Optional[ModerationCommand]:
        """
        Process a voice command and return a ModerationCommand object
        
        Args:
            command_text: The recognized voice command text
            
        Returns:
            ModerationCommand object or None if command not recognized
        """
        command_text = command_text.lower().strip()
        logger.info(f"Processing command: {command_text}")
        
        # First try pattern matching for quick recognition
        moderation_cmd = self._pattern_match_command(command_text)
        
        # If pattern matching fails and OpenAI is available, use AI processing
        if not moderation_cmd and self.openai_client:
            moderation_cmd = self._ai_process_command(command_text)
        
        if moderation_cmd:
            logger.info(f"Command processed: {moderation_cmd}")
            return moderation_cmd
        else:
            logger.warning(f"Could not process command: {command_text}")
            return None
    
    def _pattern_match_command(self, command_text: str) -> Optional[ModerationCommand]:
        """Use regex patterns to match common commands"""
        
        for action, patterns in self.command_patterns.items():
            for pattern in patterns:
                match = re.search(pattern, command_text, re.IGNORECASE)
                if match:
                    return self._extract_command_from_match(action, match, command_text)
        
        return None
    
    def _extract_command_from_match(self, action: str, match: re.Match, original_text: str) -> ModerationCommand:
        """Extract command details from regex match"""
        groups = match.groups()
        
        username = None
        duration = None
        reason = None
        
        if action in ['ban', 'timeout', 'unban']:
            username = groups[0] if len(groups) > 0 else None
            
            if len(groups) >= 3 and groups[1] and groups[2]:
                # Duration and time unit specified
                duration_value = int(groups[1])
                time_unit = groups[2].lower()
                duration = duration_value * self.time_units.get(time_unit, 60)  # default to minutes
            elif len(groups) >= 2 and groups[1]:
                # Only duration specified, assume minutes
                try:
                    duration = int(groups[1]) * 60
                except ValueError:
                    duration = Config.DEFAULT_BAN_DURATION
            else:
                # No duration specified, use default
                duration = Config.DEFAULT_BAN_DURATION if action == 'ban' else Config.DEFAULT_BAN_DURATION
        
        elif action == 'slow':
            if len(groups) > 0 and groups[0]:
                duration = int(groups[0])  # slow mode duration in seconds
        
        elif action == 'followers_only':
            if len(groups) >= 2 and groups[0] and groups[1]:
                duration_value = int(groups[0])
                time_unit = groups[1].lower()
                duration = duration_value * self.time_units.get(time_unit, 60)
        
        # Extract reason if present (look for "reason:" or "because")
        reason_patterns = [
            r'reason[:\s]+(.+)',
            r'because\s+(.+)',
            r'for\s+(.+?)(?:\s+for\s+\d+|\s*$)'
        ]
        
        for pattern in reason_patterns:
            reason_match = re.search(pattern, original_text, re.IGNORECASE)
            if reason_match:
                reason = reason_match.group(1).strip()
                break
        
        return ModerationCommand(
            action=action,
            username=username,
            duration=duration,
            reason=reason
        )
    
    def _ai_process_command(self, command_text: str) -> Optional[ModerationCommand]:
        """Use OpenAI to process complex or ambiguous commands"""
        try:
            prompt = f"""
            You are a Twitch chat moderation assistant. Parse the following voice command and extract moderation actions.
            
            Command: "{command_text}"
            
            Respond with a JSON object containing:
            - action: one of [ban, timeout, unban, clear, slow, followers_only, subscribers_only, unknown]
            - username: target username (if applicable)
            - duration: duration in seconds (if applicable)
            - reason: reason for action (if mentioned)
            
            Examples:
            "ban johndoe for 12 minutes" -> {{"action": "ban", "username": "johndoe", "duration": 720}}
            "unban johndoe" -> {{"action": "unban", "username": "johndoe"}}
            "timeout user123 for spam" -> {{"action": "timeout", "username": "user123", "duration": 600, "reason": "spam"}}
            "clear the chat" -> {{"action": "clear"}}
            "subscribers only mode" -> {{"action": "subscribers_only"}}
            
            IMPORTANT: Pay careful attention to "unban" vs "ban" - they are opposite actions!
            
            If the command is unclear or not a moderation action, return {{"action": "unknown"}}.
            """
            
            response = self.openai_client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[{"role": "user", "content": prompt}],
                max_tokens=150,
                temperature=0.1
            )
            
            result = response.choices[0].message.content.strip()
            logger.debug(f"AI response: {result}")
            
            # Parse JSON response
            import json
            try:
                parsed = json.loads(result)
                if parsed.get('action') != 'unknown':
                    return ModerationCommand(
                        action=parsed.get('action'),
                        username=parsed.get('username'),
                        duration=parsed.get('duration'),
                        reason=parsed.get('reason')
                    )
            except json.JSONDecodeError:
                logger.error(f"Failed to parse AI response as JSON: {result}")
            
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
        
        # Validate username for user-specific actions
        if cmd.action in ['ban', 'timeout', 'unban'] and not cmd.username:
            return False, f"Username required for {cmd.action} action"
        
        # Clean and validate username format
        if cmd.username:
            # Clean username: remove spaces, convert to lowercase, take first word if multiple
            cleaned_username = cmd.username.strip().lower()
            if ' ' in cleaned_username:
                # Take the first word if there are spaces (common voice recognition issue)
                cleaned_username = cleaned_username.split()[0]
                logger.info(f"Cleaned username from '{cmd.username}' to '{cleaned_username}'")
                cmd.username = cleaned_username
            
            # Validate cleaned username format
            if not re.match(r'^[a-zA-Z0-9_]{1,25}$', cmd.username):
                return False, f"Invalid username format: {cmd.username}"
        
        # Validate duration limits
        if cmd.duration:
            if cmd.duration < 1:
                return False, "Duration must be at least 1 second"
            if cmd.duration > Config.MAX_BAN_DURATION:
                return False, f"Duration cannot exceed {Config.MAX_BAN_DURATION} seconds"
        
        return True, ""
    
    def get_supported_commands(self) -> List[str]:
        """Get list of supported command types"""
        return list(self.command_patterns.keys()) 