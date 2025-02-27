import streamlit as st
import queue
import re
import os
import threading
import time
from dotenv import load_dotenv
from google.cloud import speech
# import pyaudio

# Load environment variables
load_dotenv()

# Audio recording parameters
RATE = 16000
CHUNK = int(RATE / 10)  # 100ms


class MicrophoneStream:
    """Opens a recording stream as a generator yielding the audio chunks."""

    def __init__(self, rate=RATE, chunk=CHUNK):
        """The audio -- and generator -- is guaranteed to be on the main thread."""
        self._rate = rate
        self._chunk = chunk

        # Create a thread-safe buffer of audio data
        self._buff = queue.Queue()
        self.closed = True

    def __enter__(self):
        self._audio_interface = pyaudio.PyAudio()
        self._audio_stream = self._audio_interface.open(
            format=pyaudio.paInt16,
            # The API currently only supports 1-channel (mono) audio
            channels=1,
            rate=self._rate,
            input=True,
            frames_per_buffer=self._chunk,
            # Run the audio stream asynchronously to fill the buffer object.
            stream_callback=self._fill_buffer,
        )

        self.closed = False
        return self

    def __exit__(self, type, value, traceback):
        """Closes the stream, regardless of whether the connection was lost or not."""
        self._audio_stream.stop_stream()
        self._audio_stream.close()
        self.closed = True
        # Signal the generator to terminate
        self._buff.put(None)
        self._audio_interface.terminate()

    def _fill_buffer(self, in_data, frame_count, time_info, status_flags):
        """Continuously collect data from the audio stream, into the buffer."""
        self._buff.put(in_data)
        return None, pyaudio.paContinue

    def generator(self):
        """Generates audio chunks from the stream of audio data in chunks."""
        while not self.closed:
            # Use a blocking get() to ensure there's at least one chunk of
            # data, and stop iteration if the chunk is None, indicating the
            # end of the audio stream.
            chunk = self._buff.get()
            if chunk is None:
                return
            data = [chunk]

            # Now consume whatever other data's still buffered.
            while True:
                try:
                    chunk = self._buff.get(block=False)
                    if chunk is None:
                        return
                    data.append(chunk)
                except queue.Empty:
                    break

            yield b"".join(data)


def listen_and_transcribe(stop_event, result_queue, language_code="en-US"):
    """Transcribe speech from microphone and put results in a queue."""
    # Initialize Google Cloud Speech client
    client = speech.SpeechClient()

    config = speech.RecognitionConfig(
        encoding=speech.RecognitionConfig.AudioEncoding.LINEAR16,
        sample_rate_hertz=RATE,
        language_code=language_code,
    )

    streaming_config = speech.StreamingRecognitionConfig(
        config=config, interim_results=True
    )

    with MicrophoneStream(RATE, CHUNK) as stream:
        audio_generator = stream.generator()
        requests = (
            speech.StreamingRecognizeRequest(audio_content=content)
            for content in audio_generator
        )

        responses = client.streaming_recognize(streaming_config, requests)

        # Process the responses
        for response in responses:
            if stop_event.is_set():
                break

            if not response.results:
                continue

            result = response.results[0]
            if not result.alternatives:
                continue

            transcript = result.alternatives[0].transcript
            is_final = result.is_final

            # Put the result in the queue
            result_queue.put((transcript, is_final))

            # Check for exit commands
            if is_final and re.search(r"\b(exit|quit)\b", transcript, re.I):
                break


def main():
    st.title("Live Speech-to-Text Transcription")
    st.write("Click the button below to start speech recognition")

    # Set up language selection
    languages = {
        "English (US)": "en-US",
        "English (UK)": "en-GB",
        "Spanish": "es-ES",
        "French": "fr-FR",
        "German": "de-DE",
        "Japanese": "ja-JP",
        "Mandarin Chinese": "zh"
    }

    selected_language = st.selectbox("Select Language", list(languages.keys()))
    language_code = languages[selected_language]

    # Create placeholders for the transcription output
    interim_result = st.empty()
    final_transcript = st.text_area("Transcription History", height=300)

    # Create control buttons
    col1, col2 = st.columns(2)
    with col1:
        start_button = st.button("Start Listening")
    with col2:
        stop_button = st.button("Stop Listening")

    # State management
    if 'listening' not in st.session_state:
        st.session_state.listening = False
    if 'stop_event' not in st.session_state:
        st.session_state.stop_event = threading.Event()
    if 'result_queue' not in st.session_state:
        st.session_state.result_queue = queue.Queue()
    if 'thread' not in st.session_state:
        st.session_state.thread = None

    # Handle start button
    if start_button and not st.session_state.listening:
        st.session_state.stop_event.clear()
        st.session_state.listening = True
        st.session_state.thread = threading.Thread(
            target=listen_and_transcribe,
            args=(st.session_state.stop_event, st.session_state.result_queue, language_code)
        )
        st.session_state.thread.daemon = True
        st.session_state.thread.start()
        st.success("Listening started! Speak into your microphone.")

    # Handle stop button
    if stop_button and st.session_state.listening:
        st.session_state.stop_event.set()
        st.session_state.listening = False
        if st.session_state.thread:
            st.session_state.thread.join(timeout=1)
            st.session_state.thread = None
        st.info("Listening stopped.")

    # Process results from the queue
    if st.session_state.listening:
        try:
            # Add a placeholder for the "listening" indicator
            status_indicator = st.empty()
            status_indicator.markdown("🎤 **Listening...**")

            # Non-blocking check for results
            while not st.session_state.result_queue.empty():
                transcript, is_final = st.session_state.result_queue.get(block=False)

                if is_final:
                    # Add final result to the transcript history
                    final_transcript += transcript + "\n"
                    st.session_state.final_transcript = final_transcript
                else:
                    # Update the interim result
                    interim_result.markdown(f"*{transcript}*")

            # Keep the UI updating
            time.sleep(0.1)
            st.rerun()

        except Exception as e:
            st.error(f"Error processing audio: {str(e)}")
            st.session_state.listening = False

    # Clear interim results when not listening
    if not st.session_state.listening:
        interim_result.empty()

    # Display the saved transcript
    if 'final_transcript' in st.session_state:
        final_transcript = st.session_state.final_transcript

    # Add download button for the transcript
    if final_transcript.strip():
        st.download_button(
            label="Download Transcript",
            data=final_transcript,
            file_name="transcript.txt",
            mime="text/plain"
        )

    # Add some additional info
    st.sidebar.header("About")
    st.sidebar.info(
        "This app uses Google Cloud Speech-to-Text API to transcribe speech from your microphone in real-time. "
        "Make sure you have set up your Google Cloud credentials via environment variables."
    )

    st.sidebar.header("Setup Instructions")
    st.sidebar.markdown(
        """
        1. Create a `.env` file in the same directory as this script
        2. Add your Google Cloud credentials:
           ```
           GOOGLE_APPLICATION_CREDENTIALS=path/to/your/credentials.json
           ```
        3. Make sure you have enabled the Speech-to-Text API in your Google Cloud Console
        """
    )


if __name__ == "__main__":
    main()