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
from typing import Optional, Callable
from openai import OpenAI
from config import Config

logger = logging.getLogger(__name__)

class VoiceRecognition:
    def __init__(self, command_callback: Callable[[str], None]):
        """
        Initialize voice recognition system with OpenAI Whisper API
        
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
        self.format = pyaudio.paInt16  # 16-bit for better compatibility
        
        # PyAudio setup
        self.audio = pyaudio.PyAudio()
        self.stream = None
        
        # Initialize OpenAI client
        self._setup_openai_client()
        self._setup_microphone()
    
    def _setup_openai_client(self):
        """Setup OpenAI client for Whisper API"""
        try:
            logger.info("Setting up OpenAI Whisper API client...")
            
            if not Config.OPENAI_API_KEY:
                raise ValueError("OpenAI API key not found in configuration")
            
            self.openai_client = OpenAI(api_key=Config.OPENAI_API_KEY)
            
            # Disable HTTP logging after OpenAI client is created
            import logging
            logging.getLogger('httpx').disabled = True
            logging.getLogger('httpcore').disabled = True
            
            logger.info("✅ OpenAI Whisper API client setup successful")
            
        except Exception as e:
            logger.error(f"Failed to setup OpenAI client: {e}")
            raise
    
    def _setup_microphone(self):
        """Setup and configure microphone"""
        try:
            # Get microphone info
            if Config.MICROPHONE_INDEX >= 0:
                device_info = self.audio.get_device_info_by_index(Config.MICROPHONE_INDEX)
                logger.info(f"Using microphone: {device_info['name']}")
            else:
                device_info = self.audio.get_default_input_device_info()
                Config.MICROPHONE_INDEX = device_info['index']
                logger.info(f"Using default microphone: {device_info['name']}")
            
            # Test microphone access
            test_stream = self.audio.open(
                format=self.format,
                channels=self.channels,
                rate=self.sample_rate,
                input=True,
                input_device_index=Config.MICROPHONE_INDEX,
                frames_per_buffer=self.chunk_size
            )
            test_stream.close()
            
            logger.info("✅ Microphone setup successful")
            
        except Exception as e:
            logger.error(f"Failed to setup microphone: {e}")
            raise
    
    def start_listening(self):
        """Start listening for voice commands in a separate thread"""
        if self.is_listening:
            logger.warning("Voice recognition is already listening")
            return
        
        try:
            # Open audio stream
            self.stream = self.audio.open(
                format=self.format,
                channels=self.channels,
                rate=self.sample_rate,
                input=True,
                input_device_index=Config.MICROPHONE_INDEX,
                frames_per_buffer=self.chunk_size,
                stream_callback=self._audio_callback
            )
            
            self.is_listening = True
            self.stream.start_stream()
            
            # Start processing thread
            self.listen_thread = threading.Thread(target=self._process_audio_loop, daemon=True)
            self.listen_thread.start()
            
            logger.info("🎤 Voice recognition started with OpenAI Whisper API")
            
        except Exception as e:
            logger.error(f"Failed to start voice recognition: {e}")
            raise
    
    def stop_listening(self):
        """Stop listening for voice commands"""
        self.is_listening = False
        
        if self.stream:
            self.stream.stop_stream()
            self.stream.close()
            self.stream = None
        
        if self.listen_thread and self.listen_thread.is_alive():
            self.listen_thread.join(timeout=2)
        
        logger.info("Voice recognition stopped")
    
    def _audio_callback(self, in_data, frame_count, time_info, status):
        """Callback function for audio stream"""
        if self.is_listening:
            self.audio_queue.put(in_data)
        
        return (None, pyaudio.paContinue)
    
    def _process_audio_loop(self):
        """Main audio processing loop that runs in a separate thread"""
        logger.info("Starting audio processing loop...")
        
        audio_buffer = []
        silence_threshold = 1000  # Higher threshold to reduce false triggers
        min_audio_length = self.sample_rate * 2  # 2 seconds minimum (longer to avoid short sounds)
        max_audio_length = self.sample_rate * 8  # 8 seconds maximum
        silence_duration = 0
        max_silence = self.sample_rate * 3  # 3 seconds of silence to trigger processing (longer delay)
        
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
        """Transcribe audio using OpenAI Whisper API"""
        try:
            # Combine audio chunks
            audio_data = b''.join(audio_chunks)
            
            # Check minimum length
            audio_array = np.frombuffer(audio_data, dtype=np.int16)
            if len(audio_array) < self.sample_rate * 0.5:  # Less than 0.5 seconds
                return
            
            logger.debug(f"Transcribing audio of length: {len(audio_array)/self.sample_rate:.2f} seconds")
            
            # Create a temporary WAV file for the API
            with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as temp_file:
                # Write WAV file
                with wave.open(temp_file.name, 'wb') as wav_file:
                    wav_file.setnchannels(self.channels)
                    wav_file.setsampwidth(self.audio.get_sample_size(self.format))
                    wav_file.setframerate(self.sample_rate)
                    wav_file.writeframes(audio_data)
                
                # Transcribe with OpenAI Whisper API
                with open(temp_file.name, 'rb') as audio_file:
                    transcript = self.openai_client.audio.transcriptions.create(
                        model="whisper-1",
                        file=audio_file,
                        language="en"
                    )
                
                # Clean up temp file
                os.unlink(temp_file.name)
            
            text = transcript.text.strip().lower()
            
            if text:
                logger.debug(f"Whisper API transcription: {text}")
                
                # Check if the activation keyword is present
                if Config.VOICE_ACTIVATION_KEYWORD in text:
                    # Extract command after the activation keyword
                    keyword_index = text.find(Config.VOICE_ACTIVATION_KEYWORD)
                    command = text[keyword_index + len(Config.VOICE_ACTIVATION_KEYWORD):].strip()
                    
                    if command:
                        logger.info(f"🎯 Voice command detected: {command}")
                        self.command_callback(command)
                    else:
                        logger.debug("Activation keyword detected but no command found")
            
        except Exception as e:
            logger.error(f"Error transcribing audio with OpenAI API: {e}")
    
    def test_microphone(self):
        """Test microphone functionality with OpenAI Whisper API"""
        try:
            logger.info("Testing microphone with OpenAI Whisper API...")
            logger.info("Speak for 3 seconds after the beep...")
            
            # Record test audio
            test_stream = self.audio.open(
                format=self.format,
                channels=self.channels,
                rate=self.sample_rate,
                input=True,
                input_device_index=Config.MICROPHONE_INDEX,
                frames_per_buffer=self.chunk_size
            )
            
            print("🔴 Recording... (3 seconds)")
            audio_data = []
            for _ in range(int(self.sample_rate * 3 / self.chunk_size)):
                data = test_stream.read(self.chunk_size)
                audio_data.append(data)
            
            test_stream.close()
            print("⏹️ Recording stopped")
            
            # Combine audio data
            combined_audio = b''.join(audio_data)
            
            # Create temporary WAV file
            with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as temp_file:
                with wave.open(temp_file.name, 'wb') as wav_file:
                    wav_file.setnchannels(self.channels)
                    wav_file.setsampwidth(self.audio.get_sample_size(self.format))
                    wav_file.setframerate(self.sample_rate)
                    wav_file.writeframes(combined_audio)
                
                # Transcribe with OpenAI API
                logger.info("Transcribing with OpenAI Whisper API...")
                with open(temp_file.name, 'rb') as audio_file:
                    transcript = self.openai_client.audio.transcriptions.create(
                        model="whisper-1",
                        file=audio_file,
                        language="en"
                    )
                
                # Clean up temp file
                os.unlink(temp_file.name)
            
            text = transcript.text.strip()
            logger.info(f"✅ Microphone test successful. You said: '{text}'")
            return True
            
        except Exception as e:
            logger.error(f"❌ Microphone test failed: {e}")
            return False
    
    @staticmethod
    def list_microphones():
        """List available microphones"""
        audio = pyaudio.PyAudio()
        microphones = []
        
        try:
            logger.info("Available microphones:")
            
            for i in range(audio.get_device_count()):
                device_info = audio.get_device_info_by_index(i)
                if device_info['maxInputChannels'] > 0:
                    logger.info(f"  {i}: {device_info['name']} (Channels: {device_info['maxInputChannels']})")
                    microphones.append(device_info)
        
        finally:
            audio.terminate()
        
        return microphones
    
    def __del__(self):
        """Cleanup when object is destroyed"""
        if hasattr(self, 'audio') and self.audio:
            self.audio.terminate() 