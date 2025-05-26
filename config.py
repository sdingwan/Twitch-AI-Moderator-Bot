import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

class Config:
    # Twitch Configuration
    TWITCH_TOKEN = os.getenv('TWITCH_TOKEN')
    TWITCH_CLIENT_ID = os.getenv('TWITCH_CLIENT_ID')
    TWITCH_CLIENT_SECRET = os.getenv('TWITCH_CLIENT_SECRET')
    TWITCH_CHANNEL = os.getenv('TWITCH_CHANNEL')
    TWITCH_BOT_USERNAME = os.getenv('TWITCH_BOT_USERNAME')
    
    # OpenAI Configuration
    OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')
    
    # Hugging Face Configuration (for Inference Endpoints)
    HF_API_TOKEN = os.getenv('HF_API_TOKEN')
    HF_ENDPOINT_URL = os.getenv('HF_ENDPOINT_URL')
    
    # Voice Recognition Settings
    VOICE_ACTIVATION_KEYWORD = os.getenv('VOICE_ACTIVATION_KEYWORD', 'hey brian').lower()
    MICROPHONE_INDEX = int(os.getenv('MICROPHONE_INDEX', 0))
    VOICE_TIMEOUT = int(os.getenv('VOICE_TIMEOUT', 5))
    VOICE_PHRASE_TIMEOUT = int(os.getenv('VOICE_PHRASE_TIMEOUT', 2))
    USE_LOCAL_WHISPER = os.getenv('USE_LOCAL_WHISPER', 'false').lower() == 'true'
    
    # Moderation Settings
    DEFAULT_BAN_DURATION = int(os.getenv('DEFAULT_BAN_DURATION', 600))  # 10 minutes
    MAX_BAN_DURATION = int(os.getenv('MAX_BAN_DURATION', 86400))  # 24 hours
    ENABLE_AUTO_MODERATION = os.getenv('ENABLE_AUTO_MODERATION', 'true').lower() == 'true'
    
    # Rate Limiting (per Twitch guidelines)
    MESSAGE_RATE_LIMIT = 20  # messages per 30 seconds for regular bots
    JOIN_RATE_LIMIT = 20     # joins per 10 seconds
    
    @classmethod
    def validate(cls):
        """Validate that all required configuration is present"""
        required_vars = [
            'TWITCH_TOKEN', 'TWITCH_CLIENT_ID', 'TWITCH_CLIENT_SECRET',
            'TWITCH_CHANNEL', 'TWITCH_BOT_USERNAME'
        ]
        
        missing_vars = []
        for var in required_vars:
            if not getattr(cls, var):
                missing_vars.append(var)
        
        if missing_vars:
            raise ValueError(f"Missing required environment variables: {', '.join(missing_vars)}")
        
        return True 