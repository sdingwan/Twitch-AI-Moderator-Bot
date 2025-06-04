import numpy as np
import pyaudio
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
from typing import Callable
from config import Config

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

        # External stream processes when using Twitch audio
        self.streamlink_process = None
        self.ffmpeg_process = None
        self.stream_read_thread = None
        
        # Audio recording settings
        self.sample_rate = 16000  # Good quality for speech recognition
        self.chunk_size = 1024
        self.channels = 1
        self.format = pyaudio.paInt16  # 16-bit for better compatibility
        
        # PyAudio setup (used for WAV formatting)
        self.audio = pyaudio.PyAudio()
        
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
        """Prepare to capture audio from the Twitch stream"""
        if not Config.TWITCH_CHANNEL:
            raise ValueError("Twitch channel not set for Twitch audio source")
        logger.info(f"Using Twitch stream audio from channel: {Config.TWITCH_CHANNEL}")

    def _start_twitch_stream(self):
        """Start capturing audio from Twitch using streamlink and ffmpeg"""
        try:
            cmd_streamlink = [
                'streamlink', f'https://twitch.tv/{Config.TWITCH_CHANNEL}',
                'audio_only', '-O'
            ]
            self.streamlink_process = subprocess.Popen(
                cmd_streamlink, stdout=subprocess.PIPE, bufsize=0
            )

            ffmpeg_cmd = [
                'ffmpeg', '-loglevel', 'quiet', '-i', 'pipe:0',
                '-f', 's16le', '-acodec', 'pcm_s16le',
                '-ac', str(self.channels), '-ar', str(self.sample_rate), '-'
            ]
            self.ffmpeg_process = subprocess.Popen(
                ffmpeg_cmd, stdin=self.streamlink_process.stdout,
                stdout=subprocess.PIPE, bufsize=0
            )

            self.stream_read_thread = threading.Thread(
                target=self._read_twitch_audio, daemon=True
            )
            self.stream_read_thread.start()
        except Exception as e:
            logger.error(f"Failed to start Twitch audio stream: {e}")
            raise

    def _read_twitch_audio(self):
        """Read raw PCM audio from ffmpeg process and queue it"""
        try:
            while self.is_listening and self.ffmpeg_process:
                data = self.ffmpeg_process.stdout.read(self.chunk_size * 2)
                if not data:
                    time.sleep(0.01)
                    continue
                self.audio_queue.put(data)
        except Exception as e:
            logger.error(f"Error reading Twitch audio: {e}")
    
    def start_listening(self):
        """Start listening for voice commands in a separate thread"""
        if self.is_listening:
            logger.warning("Voice recognition is already listening")
            return
        
        try:
            self._start_twitch_stream()

            self.is_listening = True

            # Start processing thread
            self.listen_thread = threading.Thread(target=self._process_audio_loop, daemon=True)
            self.listen_thread.start()

            logger.info("🎤 Voice recognition started with Hugging Face Inference Endpoint")
            
        except Exception as e:
            logger.error(f"Failed to start voice recognition: {e}")
            raise
    
    def stop_listening(self):
        """Stop listening for voice commands"""
        self.is_listening = False

        if self.ffmpeg_process:
            self.ffmpeg_process.terminate()
            self.ffmpeg_process = None
        if self.streamlink_process:
            self.streamlink_process.terminate()
            self.streamlink_process = None
        if self.stream_read_thread and self.stream_read_thread.is_alive():
            self.stream_read_thread.join(timeout=2)
        
        if self.listen_thread and self.listen_thread.is_alive():
            self.listen_thread.join(timeout=2)
        
        logger.info("Voice recognition stopped")
    
    
    def _process_audio_loop(self):
        """Main audio processing loop that runs in a separate thread"""
        logger.info("Starting audio processing loop...")
        
        audio_buffer = []
        silence_threshold = 1000  # Higher threshold to reduce false triggers
        min_audio_length = self.sample_rate * 2  # 2 seconds minimum
        max_audio_length = self.sample_rate * 8  # 8 seconds maximum
        silence_duration = 0
        max_silence = self.sample_rate * 3  # 3 seconds of silence to trigger processing
        
        while self.is_listening:
            try:
                # Get audio data with timeout
                try:
                    audio_chunk = self.audio_queue.get(timeout=0.1)
                except queue.Empty:
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
                wav_file.setsampwidth(self.audio.get_sample_size(self.format))
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
                    # Check if the activation keyword is present
                    if Config.VOICE_ACTIVATION_KEYWORD in text:
                        # Extract command after the activation keyword
                        keyword_index = text.find(Config.VOICE_ACTIVATION_KEYWORD)
                        command = text[keyword_index + len(Config.VOICE_ACTIVATION_KEYWORD):].strip()
                        
                        if command:
                            logger.info(f"🎯 Voice command detected: {command}")
                            # Pass the full text including "Hey Brian" to the callback
                            self.command_callback(text)
                        else:
                            logger.debug("Activation keyword detected but no command found")
            else:
                logger.error(f"HF Endpoint error: {response.status_code} - {response.text}")
            
        except Exception as e:
            logger.error(f"Error transcribing audio with HF endpoint: {e}")
    
    
    def __del__(self):
        """Cleanup when object is destroyed"""
        try:
            self.stop_listening()
        except Exception:
            pass
        if hasattr(self, 'audio') and self.audio:
            self.audio.terminate()
