import os
import re
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

class Config:
    # Twitch Configuration
    TWITCH_TOKEN = os.getenv('TWITCH_TOKEN')
    TWITCH_CLIENT_ID = os.getenv('TWITCH_CLIENT_ID')
    TWITCH_CLIENT_SECRET = os.getenv('TWITCH_CLIENT_SECRET')
    TWITCH_CHANNEL = None  # Will be set dynamically
    TWITCH_BOT_USERNAME = os.getenv('TWITCH_BOT_USERNAME')
    
    # OpenAI Configuration
    OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')
    
    # Hugging Face Configuration (for Inference Endpoints)
    HF_API_TOKEN = os.getenv('HF_API_TOKEN')
    HF_ENDPOINT_URL = os.getenv('HF_ENDPOINT_URL')
    
    # Voice Recognition Settings
    VOICE_ACTIVATION_KEYWORD = os.getenv('VOICE_ACTIVATION_KEYWORD', 'hey brian').lower()
    VOICE_TIMEOUT = int(os.getenv('VOICE_TIMEOUT', 5))
    VOICE_PHRASE_TIMEOUT = int(os.getenv('VOICE_PHRASE_TIMEOUT', 2))
    VOICE_COMMAND_TIMEOUT = float(os.getenv('VOICE_COMMAND_TIMEOUT', 15.0))  # Seconds to wait for sentence continuation
    
    # Transcription Logging
    ENABLE_TRANSCRIPTION_LOGGING = os.getenv('ENABLE_TRANSCRIPTION_LOGGING', 'true').lower() == 'true'
    
    # Voice Activity Detection Settings
    VOICE_SILENCE_THRESHOLD = int(os.getenv('VOICE_SILENCE_THRESHOLD', 1500))
    VOICE_MIN_SPEECH_CHUNKS = int(os.getenv('VOICE_MIN_SPEECH_CHUNKS', 8))
    VOICE_NO_SPEECH_THRESHOLD = float(os.getenv('VOICE_NO_SPEECH_THRESHOLD', 0.6))
    VOICE_MIN_SPEECH_VOLUME = int(os.getenv('VOICE_MIN_SPEECH_VOLUME', 100))  # Minimum RMS for speech detection
    
    # Moderation Settings
    DEFAULT_BAN_DURATION = int(os.getenv('DEFAULT_BAN_DURATION', 600))  # 10 minutes
    MAX_BAN_DURATION = int(os.getenv('MAX_BAN_DURATION', 86400))  # 24 hours
    ENABLE_AUTO_MODERATION = os.getenv('ENABLE_AUTO_MODERATION', 'true').lower() == 'true'
    
    # Rate Limiting (per Twitch guidelines)
    MESSAGE_RATE_LIMIT = 20  # messages per 30 seconds for regular bots
    JOIN_RATE_LIMIT = 20     # joins per 10 seconds
    
    @classmethod
    def set_twitch_channel(cls, channel: str):
        """Set the Twitch channel dynamically"""
        cls.TWITCH_CHANNEL = channel.lower().strip()
        if cls.TWITCH_CHANNEL.startswith('#'):
            cls.TWITCH_CHANNEL = cls.TWITCH_CHANNEL[1:]  # Remove # if present
    
    @classmethod
    def validate(cls):
        """Validate that all required configuration is present"""
        required_vars = [
            'TWITCH_TOKEN', 'TWITCH_CLIENT_ID', 'TWITCH_CLIENT_SECRET',
            'TWITCH_BOT_USERNAME'
        ]
        
        missing_vars = []
        for var in required_vars:
            if not getattr(cls, var):
                missing_vars.append(var)
        
        if missing_vars:
            raise ValueError(f"Missing required environment variables: {', '.join(missing_vars)}")
        
        # Check if channel is set
        if not cls.TWITCH_CHANNEL:
            raise ValueError("Twitch channel not set. Please specify a channel.")
        
        return True 
    
    @classmethod
    def find_activation_keyword(cls, text: str) -> tuple[bool, int, int]:
        """
        Find activation keyword in text with flexible matching for punctuation variations.
        
        Returns:
            (found, start_index, end_index) - end_index is exclusive
        """
        # Create regex pattern that matches "hey" followed by optional punctuation/spaces, then "brian"
        # This will match: "hey brian", "hey, brian", "hey, brian.", "hey brian!", etc.
        pattern = r'\b' + re.escape("hey") + r'[,\s]*' + re.escape("brian") + r'[!\.\?]*\b'
        
        match = re.search(pattern, text.lower())
        if match:
            return True, match.start(), match.end()
        
        return False, -1, -1
    
    @classmethod
    def extract_command_after_keyword(cls, text: str) -> str:
        """Extract command text after the activation keyword, handling punctuation variations."""
        found, start_idx, end_idx = cls.find_activation_keyword(text)
        if found:
            # Extract everything after the activation keyword match
            command_part = text[end_idx:].strip()
            # Remove leading punctuation/connectors like "." "," etc.
            command_part = re.sub(r'^[,\.\!\?\s]+', '', command_part)
            return command_part
        return text 