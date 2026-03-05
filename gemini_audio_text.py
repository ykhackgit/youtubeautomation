import argparse
import os
import sys
import wave

# Ensure the correct library is installed: pip install google-genai pyaudio python-dotenv
from google import genai
import pyaudio
from dotenv import load_dotenv

def record_audio(filename, duration):
    """Records audio from the default microphone and saves it to a WAV file."""
    chunk = 1024
    sample_format = pyaudio.paInt16
    channels = 1
    fs = 44100  # 44100 samples per second

    p = pyaudio.PyAudio()

    print(f"🎤 Recording for {duration} seconds...")

    # Open stream
    try:
        stream = p.open(format=sample_format,
                        channels=channels,
                        rate=fs,
                        frames_per_buffer=chunk,
                        input=True)
    except Exception as e:
        print(f"Error opening audio stream: {e}", file=sys.stderr)
        p.terminate()
        return False

    frames = []

    # Store data in chunks for the specified duration
    for i in range(0, int(fs / chunk * duration)):
        data = stream.read(chunk)
        frames.append(data)

    # Stop and close the stream 
    stream.stop_stream()
    stream.close()
    
    # Terminate the PortAudio interface
    p.terminate()

    print("✅ Recording finished.")

    # Save the recorded data as a WAV file
    try:
        wf = wave.open(filename, 'wb')
        wf.setnchannels(channels)
        wf.setsampwidth(p.get_sample_size(sample_format))
        wf.setframerate(fs)
        wf.writeframes(b''.join(frames))
        wf.close()
        return True
    except Exception as e:
        print(f"Error saving audio file: {e}", file=sys.stderr)
        return False

def main():
    # Load environment variables from .env file
    load_dotenv()
    
    parser = argparse.ArgumentParser(description="Process audio and text using Gemini API")
    parser.add_argument("--record", action="store_true", help="Record audio from microphone")
    parser.add_argument("--duration", type=int, default=5, help="Duration to record in seconds (default: 5)")
    parser.add_argument("--prompt", help="Text input prompt for the model (Optional)")
    parser.add_argument("--model", default="gemini-2.5-flash", help="Gemini model to use (default: gemini-2.5-flash)")
    
    args = parser.parse_args()
    
    if not args.record and not args.prompt:
        print("Error: You must provide at least one input: --record or --prompt.", file=sys.stderr)
        parser.print_help()
        sys.exit(1)
    
    # Check for API key
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        print("Error: GEMINI_API_KEY environment variable is not set.", file=sys.stderr)
        print("Please set it in a .env file: GEMINI_API_KEY='your_api_key'", file=sys.stderr)
        sys.exit(1)
        
    audio_path = None
    is_temp_audio = False
    
    if args.record:
        audio_path = "temp_recorded_audio.wav"
        if not record_audio(audio_path, args.duration):
            sys.exit(1)
        is_temp_audio = True

    try:
        # Initialize the client. It automatically picks up GEMINI_API_KEY from the environment
        client = genai.Client()
        
        contents = []

        if audio_path:
            print(f"Uploading audio file: {audio_path}...")
            # Upload the audio file using the Files API
            audio_file = client.files.upload(file=audio_path)
            print(f"File uploaded successfully (Name: {audio_file.name})")
            contents.append(audio_file)
            
        if args.prompt:
            print(f"\nAdding text prompt: '{args.prompt}'")
            contents.append(args.prompt)
            
        print(f"\nUsing model: {args.model}")
        print("Waiting for response...\n")
        
        # Generate content
        response = client.models.generate_content(
            model=args.model,
            contents=contents
        )
        
        print("=== Gemini Response ===")
        print(response.text)
        print("=======================")
        
        # Clean up: delete the file from Gemini servers after processing
        if audio_path:
            print(f"\nCleaning up: Deleting {audio_file.name} from Gemini servers...")
            client.files.delete(name=audio_file.name)
            
        if is_temp_audio and os.path.exists(audio_path):
            print(f"Cleaning up: Deleting local temporary file {audio_path}...")
            os.remove(audio_path)
            
        print("Cleanup complete.")
        
    except Exception as e:
        print(f"\nAn error occurred: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()
