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
from typing import Optional, Callable
from ..core.config import Config
from datetime import datetime

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
        
        # Streamlink and FFmpeg processes for stream capture
        self.ffmpeg_process = None
        self.streamlink_process = None
        self.primary_stream_url = None
        self.primary_platform = None
        
        # Transcription logging
        self.transcription_log_file = "stream_transcription.log"
        self._setup_transcription_logging()
        
        # Initialize Hugging Face Inference Endpoint
        self._setup_hf_endpoint()
        
        # Determine primary audio source based on enabled platforms
        self._determine_primary_audio_source()
    
    def _determine_primary_audio_source(self):
        """Determine which platform to use for audio capture based on configuration"""
        twitch_enabled = bool(Config.TWITCH_CHANNEL)
        kick_enabled = bool(getattr(Config, 'KICK_CHANNEL', None))
        
        if twitch_enabled and kick_enabled:
            # Both platforms enabled - prefer Twitch for now (could be made configurable)
            self.primary_platform = 'twitch'
            self.primary_stream_url = f"https://www.twitch.tv/{Config.TWITCH_CHANNEL}"
            logger.info(f"🎤 Both platforms enabled - using Twitch audio: {Config.TWITCH_CHANNEL}")
        elif twitch_enabled:
            # Only Twitch enabled
            self.primary_platform = 'twitch'
            self.primary_stream_url = f"https://www.twitch.tv/{Config.TWITCH_CHANNEL}"
            logger.info(f"🎤 Using Twitch audio: {Config.TWITCH_CHANNEL}")
        elif kick_enabled:
            # Only Kick enabled
            self.primary_platform = 'kick'
            self.primary_stream_url = f"https://kick.com/{Config.KICK_CHANNEL}"
            logger.info(f"🎤 Using Kick audio: {Config.KICK_CHANNEL}")
        else:
            # No platforms configured
            self.primary_platform = None
            self.primary_stream_url = None
            logger.warning("⚠️ No platforms configured for audio capture")
            
        # Setup stream capture if we have a source
        if self.primary_stream_url:
            self._setup_stream_capture()
        else:
            logger.warning("⚠️ No audio source available - voice recognition will not work")
    
    def _setup_stream_capture(self):
        """Setup stream audio capture for the determined platform"""
        try:
            if not self.primary_stream_url:
                raise ValueError("No primary stream URL configured")
            
            # Test streamlink and FFmpeg availability
            try:
                subprocess.run(['streamlink', '--version'], capture_output=True, check=True)
                logger.info("✅ Streamlink found and ready")
            except (subprocess.CalledProcessError, FileNotFoundError):
                raise Exception("Streamlink not found. Please install streamlink to capture stream audio.")
            
            try:
                subprocess.run(['ffmpeg', '-version'], capture_output=True, check=True)
                logger.info("✅ FFmpeg found and ready")
            except (subprocess.CalledProcessError, FileNotFoundError):
                raise Exception("FFmpeg not found. Please install FFmpeg to process stream audio.")
            
            logger.info(f"✅ Stream setup successful for {self.primary_platform}: {self.primary_stream_url}")
            
        except Exception as e:
            logger.error(f"Failed to setup stream capture: {e}")
            logger.warning("Continuing without stream audio capture")
    
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
    
    def _setup_transcription_logging(self):
        """Setup transcription logging to file"""
        if not Config.ENABLE_TRANSCRIPTION_LOGGING:
            logger.info("Transcription logging disabled in configuration")
            return
            
        try:
            # Initialize the transcription log file
            with open(self.transcription_log_file, 'w', encoding='utf-8') as f:
                f.write(f"# Stream Transcription Log - Started at {datetime.now()}\n")
                if Config.TWITCH_CHANNEL:
                    f.write(f"# Twitch Channel: {Config.TWITCH_CHANNEL}\n")
                if hasattr(Config, 'KICK_CHANNEL') and Config.KICK_CHANNEL:
                    f.write(f"# Kick Channel: {Config.KICK_CHANNEL}\n")
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
        """Start listening for voice commands from the configured stream"""
        if self.is_listening:
            logger.warning("Voice recognition is already listening")
            return
        
        if not self.primary_stream_url:
            logger.error("No audio source configured - cannot start voice recognition")
            return
        
        try:
            # Start FFmpeg process to capture stream audio
            self._start_ffmpeg_capture()
            
            self.is_listening = True
            
            # Start processing thread
            self.listen_thread = threading.Thread(target=self._process_audio_loop, daemon=True)
            self.listen_thread.start()
            
            logger.info(f"🎤 Voice recognition started with {self.primary_platform} stream audio capture")
            
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
        """Start streamlink process to capture stream audio from the primary platform"""
        try:
            if not self.primary_stream_url or not self.primary_platform:
                raise ValueError("No primary stream configured")
            
            # Build streamlink command based on platform
            if self.primary_platform == 'twitch':
                # Twitch-specific streamlink options
                streamlink_cmd = [
                    'streamlink',
                    '--stdout',  # Output to stdout
                    '--twitch-disable-ads',  # Disable ads for better audio continuity
                    '--retry-streams', '5',  # Retry on stream errors
                    '--retry-open', '3',  # Retry opening stream
                    self.primary_stream_url,
                    'audio_only,worst'  # Try audio_only first, fallback to worst quality for audio extraction
                ]
            elif self.primary_platform == 'kick':
                # Kick-specific streamlink options (no special ad options)
                streamlink_cmd = [
                    'streamlink',
                    '--stdout',  # Output to stdout
                    '--retry-streams', '5',  # Retry on stream errors
                    '--retry-open', '3',  # Retry opening stream
                    self.primary_stream_url,
                    'worst'  # Use worst quality for audio extraction (Kick may not have audio_only)
                ]
            else:
                raise ValueError(f"Unsupported platform: {self.primary_platform}")
            
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
            
            logger.info(f"Started streamlink + FFmpeg capture for {self.primary_platform}: {self.primary_stream_url}")
            
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
        silence_threshold = 1500
        min_audio_length = self.sample_rate * 2  # 2 seconds minimum 
        max_audio_length = self.sample_rate * 8  # 8 seconds maximum 
        silence_duration = 0
        max_silence = self.sample_rate * 3  # 3 seconds of silence to trigger processing 
        
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
                
                # Simple silence detection like microphone version - just check max amplitude
                if np.max(np.abs(audio_data)) < silence_threshold:
                    silence_duration += len(audio_data)
                else:
                    silence_duration = 0
                
                # Calculate total buffer length
                total_length = sum(len(np.frombuffer(chunk, dtype=np.int16)) for chunk in audio_buffer)
                
                # Process audio if we have enough and there's been silence (like microphone version)
                if (total_length >= min_audio_length and 
                    silence_duration >= max_silence) or total_length >= max_audio_length:
                    
                    if total_length >= min_audio_length:
                        # Process the audio buffer
                        logger.debug(f"Processing audio: {total_length/self.sample_rate:.1f}s")
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
    
    def _transcribe_audio(self, audio_chunks):
        """Transcribe audio using Hugging Face Inference Endpoint"""
        try:
            # Combine audio chunks
            audio_data = b''.join(audio_chunks)
            
            # Check minimum length (like microphone version)
            audio_array = np.frombuffer(audio_data, dtype=np.int16)
            if len(audio_array) < self.sample_rate * 0.5:  # Less than 0.5 seconds
                return
            
            # Check if audio has sufficient volume/energy to be actual speech
            # Calculate RMS (Root Mean Square) to get average volume level
            rms = np.sqrt(np.mean(audio_array.astype(float) ** 2))
            min_speech_volume = Config.VOICE_MIN_SPEECH_VOLUME
            
            if rms < min_speech_volume:
                logger.debug(f"Skipping transcription - audio too quiet (RMS: {rms:.1f})")
                return
                
            # Check for consistent audio energy (not just brief spikes)
            # Split into segments and check if enough segments have decent volume
            segment_length = self.sample_rate // 4  # 0.25 second segments
            segments = [audio_array[i:i+segment_length] for i in range(0, len(audio_array), segment_length)]
            
            active_segments = 0
            for segment in segments:
                if len(segment) > 0:
                    segment_rms = np.sqrt(np.mean(segment.astype(float) ** 2))
                    if segment_rms > min_speech_volume * 0.5:  # Lower threshold for segments
                        active_segments += 1
            
            # Require at least 30% of segments to have decent audio
            if active_segments / len(segments) < 0.3:
                logger.debug(f"Skipping transcription - insufficient speech activity ({active_segments}/{len(segments)} segments)")
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
                
                # Filter out common Whisper hallucinations
                hallucination_phrases = {
                    'thank you', 'you', 'okay', 'thanks for watching', 'thanks for watching!',
                    'thank you for watching', 'thank you for watching!', 'thanks', 'obrigado',
                    'gracias', 'merci', 'danke', '.', '..', '...', 'um', 'uh', 'oh',
                    'yeah', 'yes', 'no', 'hi', 'hello', 'bye', 'goodbye'
                }
                
                # Check if the entire text is just a hallucination
                if text in hallucination_phrases:
                    logger.debug(f"Filtering hallucination: '{text}'")
                    return
                
                # Check if text is too short and likely a hallucination
                if len(text.strip()) <= 2:
                    logger.debug(f"Filtering short text: '{text}'")
                    return
                
                if text:
                    # Log ALL transcribed text to file (real-time streamer speech)
                    self._log_transcription(text)
                    
                    # Check if the activation keyword is present for commands (with flexible matching)
                    has_activation_keyword, _, _ = Config.find_activation_keyword(text)
                    if has_activation_keyword:
                        # Extract command after the activation keyword
                        command = Config.extract_command_after_keyword(text)
                        
                        if command:
                            logger.info(f"🎯 Voice command: {command}")
                        else:
                            logger.debug(f"🎯 Activation keyword detected: {Config.VOICE_ACTIVATION_KEYWORD}")
                        
                        # Always pass the full text to the callback when activation keyword is found
                        self.command_callback(text)
                    else:
                        # Also pass text without activation keyword to allow sentence combining
                        # The web interface will decide if it should be combined with pending commands
                        self.command_callback(text)
            else:
                logger.error(f"HF Endpoint error: {response.status_code} - {response.text}")
            
        except Exception as e:
            logger.error(f"Error transcribing audio with HF endpoint: {e}")
    
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