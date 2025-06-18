import numpy as np
import threading
import queue
import time
import logging
import io
import wave
import tempfile
import os
import requests
import subprocess
import asyncio
from typing import Optional, Callable, List, Dict
from config import Config
from datetime import datetime
from collections import deque
from openai import OpenAI

logger = logging.getLogger(__name__)

class VoiceRecognitionHF:
    def __init__(self, command_callback: Callable[[str], None]):
        """
        Initialize voice recognition system with Hugging Face Inference Endpoints
        
        Args:
            command_callback: Function to call when a voice command is recognized
        """
        self.command_callback = command_callback
        self.is_listening = False
        self.listen_thread = None
        self.audio_queue = queue.Queue()
        
        # Audio recording settings
        self.sample_rate = 16000  # Good quality for speech recognition
        self.chunk_size = 1024
        self.channels = 1
        
        # Streamlink and FFmpeg processes for Twitch stream capture
        self.ffmpeg_process = None
        self.streamlink_process = None
        self.twitch_stream_url = None
        
        # Transcription logging
        self.transcription_log_file = "stream_transcription.log"
        self._setup_transcription_logging()
        
        # Multi-segment command processing
        self.recent_segments = deque(maxlen=4)  # Keep last 4 transcribed segments
        self.segment_timestamps = deque(maxlen=4)  # Keep timestamps for each segment
        
        # Initialize OpenAI client for command assembly
        self.openai_client = None
        if Config.OPENAI_API_KEY:
            self.openai_client = OpenAI(api_key=Config.OPENAI_API_KEY)
        else:
            logger.warning("OpenAI API key not found. Multi-segment command processing will not work.")
        
        # Initialize Hugging Face Inference Endpoint
        self._setup_hf_endpoint()
        self._setup_twitch_stream()
    
    def _setup_hf_endpoint(self):
        """Setup Hugging Face Inference Endpoint for Whisper"""
        try:
            logger.info("Setting up Hugging Face Inference Endpoint...")
            
            if not Config.HF_API_TOKEN:
                raise ValueError("Hugging Face API token not found in configuration")
            
            # Your deployed endpoint URL (replace with your actual endpoint)
            self.hf_endpoint_url = Config.HF_ENDPOINT_URL
            self.hf_headers = {
                "Authorization": f"Bearer {Config.HF_API_TOKEN}",
                "Content-Type": "audio/wav"
            }
            
            logger.info("✅ Hugging Face Inference Endpoint setup successful")
            
        except Exception as e:
            logger.error(f"Failed to setup HF endpoint: {e}")
            raise
    
    def _setup_twitch_stream(self):
        """Setup Twitch stream audio capture"""
        try:
            # Build Twitch stream URL
            if not Config.TWITCH_CHANNEL:
                raise ValueError("Twitch channel not configured")
            
            self.twitch_stream_url = f"https://www.twitch.tv/{Config.TWITCH_CHANNEL}"
            
            # Test streamlink and FFmpeg availability
            try:
                subprocess.run(['streamlink', '--version'], capture_output=True, check=True)
                logger.info("✅ Streamlink found and ready")
            except (subprocess.CalledProcessError, FileNotFoundError):
                raise Exception("Streamlink not found. Please install streamlink to capture Twitch stream audio.")
            
            try:
                subprocess.run(['ffmpeg', '-version'], capture_output=True, check=True)
                logger.info("✅ FFmpeg found and ready")
            except (subprocess.CalledProcessError, FileNotFoundError):
                raise Exception("FFmpeg not found. Please install FFmpeg to process stream audio.")
            
            logger.info(f"✅ Twitch stream setup successful for channel: {Config.TWITCH_CHANNEL}")
            
        except Exception as e:
            logger.error(f"Failed to setup Twitch stream: {e}")
            raise
    
    def _setup_transcription_logging(self):
        """Setup transcription logging to file"""
        if not Config.ENABLE_TRANSCRIPTION_LOGGING:
            logger.info("Transcription logging disabled in configuration")
            return
            
        try:
            # Initialize the transcription log file
            with open(self.transcription_log_file, 'w', encoding='utf-8') as f:
                f.write(f"# Twitch Stream Transcription Log - Started at {datetime.now()}\n")
                f.write(f"# Channel: {Config.TWITCH_CHANNEL}\n")
                f.write("# Format: [timestamp] transcribed_text\n")
                f.write("-" * 80 + "\n\n")
            
            logger.info(f"✅ Transcription logging setup successful: {self.transcription_log_file}")
            
        except Exception as e:
            logger.error(f"Failed to setup transcription logging: {e}")
    
    def _log_transcription(self, text: str):
        """Log transcribed text to file with timestamp"""
        if not Config.ENABLE_TRANSCRIPTION_LOGGING:
            return
            
        try:
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            log_entry = f"[{timestamp}] {text}\n"
            
            # Write to file
            with open(self.transcription_log_file, 'a', encoding='utf-8') as f:
                f.write(log_entry)
            
            # Also log to console for real-time monitoring
            logger.info(f"📝 Transcribed: {text}")
            
        except Exception as e:
            logger.error(f"Failed to log transcription: {e}")
    
    def start_listening(self):
        """Start listening for voice commands from Twitch stream"""
        if self.is_listening:
            logger.warning("Voice recognition is already listening")
            return
        
        try:
            # Start FFmpeg process to capture Twitch stream audio
            self._start_ffmpeg_capture()
            
            self.is_listening = True
            
            # Start processing thread
            self.listen_thread = threading.Thread(target=self._process_audio_loop, daemon=True)
            self.listen_thread.start()
            
            logger.info("🎤 Voice recognition started with Twitch stream audio capture")
            
        except Exception as e:
            logger.error(f"Failed to start voice recognition: {e}")
            raise
    
    def stop_listening(self):
        """Stop listening for voice commands"""
        self.is_listening = False
        
        # Stop streamlink and FFmpeg processes
        if self.ffmpeg_process:
            try:
                self.ffmpeg_process.terminate()
                self.ffmpeg_process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.ffmpeg_process.kill()
            except Exception as e:
                logger.error(f"Error stopping FFmpeg process: {e}")
            finally:
                self.ffmpeg_process = None
        
        if self.streamlink_process:
            try:
                self.streamlink_process.terminate()
                self.streamlink_process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.streamlink_process.kill()
            except Exception as e:
                logger.error(f"Error stopping streamlink process: {e}")
            finally:
                self.streamlink_process = None
        
        if self.listen_thread and self.listen_thread.is_alive():
            self.listen_thread.join(timeout=2)
        
        logger.info("Voice recognition stopped")
    
    def _start_ffmpeg_capture(self):
        """Start streamlink process to capture Twitch stream audio"""
        try:
            # Use streamlink to get the stream and pipe directly to FFmpeg for audio processing
            streamlink_cmd = [
                'streamlink',
                '--stdout',  # Output to stdout
                '--twitch-disable-ads',  # Disable ads for better audio continuity
                '--retry-streams', '5',  # Retry on stream errors
                '--retry-open', '3',  # Retry opening stream
                f'twitch.tv/{Config.TWITCH_CHANNEL}',
                'audio_only,worst'  # Try audio_only first, fallback to worst quality for audio extraction
            ]
            
            # Start streamlink process that pipes to FFmpeg for audio extraction
            streamlink_process = subprocess.Popen(
                streamlink_cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
            
            # FFmpeg command to process the stream from streamlink
            ffmpeg_cmd = [
                'ffmpeg',
                '-i', 'pipe:0',  # Read from stdin (streamlink output)
                '-f', 's16le',  # 16-bit little-endian
                '-ar', str(self.sample_rate),  # Sample rate
                '-ac', str(self.channels),  # Mono audio
                '-acodec', 'pcm_s16le',  # Audio codec
                '-loglevel', 'error',  # Reduce logging
                '-'  # Output to stdout
            ]
            
            # Start FFmpeg process that reads from streamlink
            self.ffmpeg_process = subprocess.Popen(
                ffmpeg_cmd,
                stdin=streamlink_process.stdout,  # Read from streamlink
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                bufsize=self.chunk_size * 2  # Buffer size in bytes
            )
            
            # Close streamlink stdout in parent to avoid broken pipe
            streamlink_process.stdout.close()
            
            # Store reference to streamlink process for cleanup
            self.streamlink_process = streamlink_process
            
            logger.info(f"Started streamlink + FFmpeg capture for Twitch channel: {Config.TWITCH_CHANNEL}")
            
        except Exception as e:
            logger.error(f"Failed to start streamlink capture: {e}")
            raise
    
    def _read_audio_from_ffmpeg(self):
        """Read audio data from FFmpeg process"""
        try:
            if not self.ffmpeg_process or self.ffmpeg_process.poll() is not None:
                return None
            
            # Read chunk of audio data (2 bytes per sample for 16-bit)
            chunk_bytes = self.chunk_size * 2
            audio_data = self.ffmpeg_process.stdout.read(chunk_bytes)
            
            if len(audio_data) == chunk_bytes:
                return audio_data
            else:
                # End of stream or partial read
                return None
                
        except Exception as e:
            logger.error(f"Error reading audio from FFmpeg: {e}")
            return None
    
    def _process_audio_loop(self):
        """Main audio processing loop that runs in a separate thread"""
        logger.info("Starting audio processing loop...")
        
        audio_buffer = []
        silence_threshold = 1000  # Higher threshold to reduce false triggers
        min_audio_length = self.sample_rate * 2  # 2 seconds minimum
        max_audio_length = self.sample_rate * 6  # 8 seconds maximum
        silence_duration = 0
        max_silence = self.sample_rate * 1.5  # 2 seconds of silence to trigger processing
        
        while self.is_listening:
            try:
                # Get audio data from FFmpeg
                audio_chunk = self._read_audio_from_ffmpeg()
                if audio_chunk is None:
                    time.sleep(0.1)
                    continue
                
                # Add to buffer
                audio_buffer.append(audio_chunk)
                
                # Convert to numpy for silence detection
                audio_data = np.frombuffer(audio_chunk, dtype=np.int16)
                
                # Check for silence
                if np.max(np.abs(audio_data)) < silence_threshold:
                    silence_duration += len(audio_data)
                else:
                    silence_duration = 0
                
                # Calculate total buffer length
                total_length = sum(len(np.frombuffer(chunk, dtype=np.int16)) for chunk in audio_buffer)
                
                # Process audio if we have enough and there's been silence
                if (total_length >= min_audio_length and 
                    silence_duration >= max_silence) or total_length >= max_audio_length:
                    
                    if total_length >= min_audio_length:
                        # Process the audio buffer
                        threading.Thread(
                            target=self._transcribe_audio, 
                            args=(audio_buffer.copy(),), 
                            daemon=True
                        ).start()
                    
                    # Reset buffer
                    audio_buffer = []
                    silence_duration = 0
                
            except Exception as e:
                logger.error(f"Error in audio processing loop: {e}")
                time.sleep(0.1)
    
    def _is_gibberish(self, text: str) -> bool:
        """
        Filter out gibberish, short fragments, and meaningless transcriptions
        """
        # If filtering is disabled, never filter
        if not Config.ENABLE_GIBBERISH_FILTERING:
            return False
            
        if not text or not text.strip():
            return True
        
        text = text.strip().lower()
        
        # Too short (configurable minimum length)
        if len(text) < Config.MIN_SEGMENT_LENGTH:
            return True
        
        # Common gibberish patterns
        gibberish_patterns = [
            # Single repeated words
            r'^(you|thank you|thanks|lol|uh|um|ah|oh|yeah|yes|no|okay|ok)$',
            # Very short words (1-2 chars) unless they're commands
            r'^[a-z]{1,2}$',
            # Just punctuation or numbers
            r'^[^a-z]*$',
            # Repeated characters
            r'^(.)\1{3,}$',
            # Common filler words
            r'^(like|well|so|and|but|the|a|an|is|was|are|were|will|would|could|should)$'
        ]
        
        import re
        for pattern in gibberish_patterns:
            if re.match(pattern, text):
                return True
        
        # Check if it's just a single word that's very common and short
        words = text.split()
        if len(words) == 1 and len(text) <= 4 and text not in [Config.VOICE_ACTIVATION_KEYWORD]:
            common_short_words = ['you', 'me', 'my', 'we', 'us', 'he', 'she', 'it', 'they', 'this', 'that', 'here', 'there', 'now', 'then', 'what', 'when', 'where', 'why', 'how', 'who', 'much', 'many', 'some', 'all', 'any', 'each', 'both', 'more', 'most', 'few', 'less', 'same', 'new', 'old', 'good', 'bad', 'big', 'small']
            if text in common_short_words:
                return True
        
        return False
    
    def _transcribe_audio(self, audio_chunks):
        """Transcribe audio using Hugging Face Inference Endpoint"""
        try:
            # Combine audio chunks
            audio_data = b''.join(audio_chunks)
            
            # Check minimum length
            audio_array = np.frombuffer(audio_data, dtype=np.int16)
            if len(audio_array) < self.sample_rate * 0.5:  # Less than 0.5 seconds
                return
            
            # Create WAV file in memory
            wav_buffer = io.BytesIO()
            with wave.open(wav_buffer, 'wb') as wav_file:
                wav_file.setnchannels(self.channels)
                wav_file.setsampwidth(2)  # 16-bit = 2 bytes
                wav_file.setframerate(self.sample_rate)
                wav_file.writeframes(audio_data)
            
            wav_buffer.seek(0)
            
            # Send to Hugging Face Inference Endpoint
            response = requests.post(
                self.hf_endpoint_url,
                headers=self.hf_headers,
                data=wav_buffer.getvalue(),
                timeout=30
            )
            
            if response.status_code == 200:
                result = response.json()
                text = result.get('text', '').strip().lower()
                
                if text:
                    # Check if this is gibberish
                    is_gibberish = self._is_gibberish(text)
                    
                    # Log transcription (filter if enabled)
                    if not is_gibberish or not Config.FILTER_TRANSCRIPTION_LOG:
                        self._log_transcription(text)
                    else:
                        logger.debug(f"Filtered gibberish from log: '{text}'")
                    
                    # Process for commands (always filter gibberish here)
                    if not is_gibberish:
                        # Add to recent segments for multi-segment processing
                        current_time = time.time()
                        self.recent_segments.append(text)
                        self.segment_timestamps.append(current_time)
                        
                        # Check for commands using multi-segment analysis
                        self._process_multi_segment_commands()
                    else:
                        logger.debug(f"Filtered gibberish from processing: '{text}'")
                    
            else:
                logger.error(f"HF Endpoint error: {response.status_code} - {response.text}")
            
        except Exception as e:
            logger.error(f"Error transcribing audio with HF endpoint: {e}")
    
    def _process_multi_segment_commands(self):
        """Process commands across multiple segments using AI"""
        try:
            if not self.openai_client:
                # Fallback to single-segment processing
                self._fallback_single_segment_processing()
                return
            
            # Only process if we have segments and the most recent one is within 10 seconds
            if not self.recent_segments:
                return
                
            current_time = time.time()
            if current_time - self.segment_timestamps[-1] > 10:
                return  # Too old, ignore
            
            # Filter out any remaining gibberish from segments before analysis
            # (Keep wake word segments even if they might seem like gibberish)
            filtered_segments = []
            for segment in self.recent_segments:
                if Config.VOICE_ACTIVATION_KEYWORD in segment or not self._is_gibberish(segment):
                    filtered_segments.append(segment)
            
            if not filtered_segments:
                return  # No meaningful segments
            
            # Check if any segment contains the wake word
            has_wake_word = any(Config.VOICE_ACTIVATION_KEYWORD in segment for segment in filtered_segments)
            
            if not has_wake_word:
                return  # No wake word found, skip processing
            
            # Use AI to analyze the filtered segments for commands
            detected_command = self._ai_analyze_segments(filtered_segments)
            
            if detected_command:
                logger.info(f"🎯 Multi-segment command detected: {detected_command}")
                self.command_callback(detected_command)
                
                # Clear recent segments after successful command processing
                self.recent_segments.clear()
                self.segment_timestamps.clear()
                
        except Exception as e:
            logger.error(f"Error in multi-segment command processing: {e}")
            # Fallback to single-segment processing
            self._fallback_single_segment_processing()
    
    def _ai_analyze_segments(self, segments: List[str]) -> Optional[str]:
        """Use AI to analyze multiple segments and extract complete commands"""
        try:
            # Prepare segments for analysis
            segments_formatted = []
            for i, segment in enumerate(segments, 1):
                segments_formatted.append(f"Segment {i}: \"{segment}\"")
            
            segments_text = "\n".join(segments_formatted)
            
            prompt = f"""You are analyzing voice transcription segments that may contain a split voice command for a Twitch moderation bot.

Recent transcription segments (in chronological order):
{segments_text}

The voice activation keyword is "{Config.VOICE_ACTIVATION_KEYWORD}".

Your task:
1. Look for voice commands that start with "{Config.VOICE_ACTIVATION_KEYWORD}"
2. Determine if segments form a complete command when combined
3. Handle cases where commands are split across segments due to pauses
4. Extract the most complete and recent command

Rules:
- Commands may be split due to natural speech pauses
- Look for patterns like "hey brian set weather to go" + "reme turkey" = "hey brian set weather to goreme turkey"
- Prioritize the most recent complete command
- Ignore unrelated conversation or incomplete fragments
- Only return commands that start with the activation keyword

Examples of what to look for:
- Weather commands: "set weather to [location]", "change weather to [location]"
- Moderation commands: "ban [user]", "timeout [user]", "clear chat"
- Mode commands: "slow mode", "followers only", "subscribers only"

If you find a complete command, respond with ONLY the complete command text starting with "{Config.VOICE_ACTIVATION_KEYWORD}".
If no complete command is found, respond with "NO_COMMAND".

Response:"""

            response = self.openai_client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": "You are a voice command analyzer for a Twitch moderation bot. Extract complete commands from transcription segments."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=100,
                temperature=0.1
            )
            
            ai_response = response.choices[0].message.content.strip()
            
            if ai_response and ai_response != "NO_COMMAND" and Config.VOICE_ACTIVATION_KEYWORD in ai_response.lower():
                # Clean up the response
                cleaned_command = ai_response.lower().strip()
                logger.info(f"🤖 AI assembled command from {len(segments)} segments: {cleaned_command}")
                return cleaned_command
            else:
                logger.debug(f"AI found no complete command in segments: {ai_response}")
                return None
                
        except Exception as e:
            logger.error(f"Error in AI segment analysis: {e}")
            return None
    
    def _fallback_single_segment_processing(self):
        """Fallback to original single-segment processing"""
        if not self.recent_segments:
            return
            
        # Process only the most recent segment that contains the wake word
        for segment in reversed(self.recent_segments):
            if Config.VOICE_ACTIVATION_KEYWORD in segment:
                # Extract command after the activation keyword
                keyword_index = segment.find(Config.VOICE_ACTIVATION_KEYWORD)
                command = segment[keyword_index + len(Config.VOICE_ACTIVATION_KEYWORD):].strip()
                
                if command:
                    logger.info(f"🎯 Fallback single-segment command: {command}")
                    self.command_callback(segment)
                    break
    
    def __del__(self):
        """Cleanup when object is destroyed"""
        if hasattr(self, 'ffmpeg_process') and self.ffmpeg_process:
            try:
                self.ffmpeg_process.terminate()
            except:
                pass
        
        if hasattr(self, 'streamlink_process') and self.streamlink_process:
            try:
                self.streamlink_process.terminate()
            except:
                pass 