import os
import re
import tempfile
import asyncio
import subprocess
import requests
from flask import Flask, request, jsonify, send_from_directory, send_file
import edge_tts

app = Flask(__name__, static_folder='.', static_url_path='')

@app.route('/')
def index():
    return send_from_directory('.', 'index.html')

@app.route('/<path:path>')
def serve_static(path):
    return send_from_directory('.', path)

def parse_srt(srt_text):
    """បំបែក SRT Format យក Start Time, End Time និង Text"""
    pattern = re.compile(r'(\d+)\n(\d\d:\d\d:\d\d,\d\d\d) --> (\d\d:\d\d:\d\d,\d\d\d)\n([\s\S]*?)(?=\n\n|\Z)')
    matches = pattern.findall(srt_text)
    subtitles = []
    for match in matches:
        index, start_time, end_time, text = match
        subtitles.append({
            'index': index,
            'start': start_time.strip(),
            'end': end_time.strip(),
            'text': text.strip().replace('\n', ' ')
        })
    return subtitles

def srt_time_to_seconds(srt_time):
    """បំប្លែង 00:01:23,456 ទៅជា Seconds (Floating number)"""
    hours, minutes, seconds = srt_time.split(':')
    seconds, milliseconds = seconds.split(',')
    return int(hours) * 3600 + int(minutes) * 60 + int(seconds) + int(milliseconds) / 1000.0

async def generate_khmer_audio(text, output_path):
    """បង្កើតសំឡេងខ្មែរដោយប្រើ Edge TTS"""
    communicate = edge_tts.Communicate(text, "km-KH-PisethNeural")
    await communicate.save(output_path)

@app.route('/process-video-dubbing', methods=['POST'])
def process_video_dubbing():
    if 'file' not in request.files:
        return jsonify({'error': 'មិនមាន File ត្រូវបាន Upload ទេ'}), 400

    file = request.files['file']
    lang = request.form.get('lang', 'Chinese')
    style = request.form.get('style', 'សម្រាយរឿង YouTube')
    raw_keys = request.form.get('api_key', '').strip()

    if file.filename == '':
        return jsonify({'error': 'សូមជ្រើសរើស File'}), 400

    env_keys = os.getenv("GROQ_API_KEY", "").strip()
    combined_keys_text = raw_keys or env_keys

    if not combined_keys_text:
        return jsonify({'error': 'មិនទាន់មាន Groq API Key ទេ!'}), 400

    key_list = [k.strip() for k in combined_keys_text.replace('\n', ',').split(',') if k.strip()]

    temp_dir = tempfile.mkdtemp()
    video_path = os.path.join(temp_dir, "input_video.mp4")
    file.save(video_path)

    try:
        # ជំហានទី ១៖ Whisper Speech-to-Text យក SRT Subtitle ជាមួយ Timeline
        srt_transcript = None
        working_key = None
        last_error = ""

        for key in key_list:
            headers = {"Authorization": f"Bearer {key}"}
            transcribe_url = "https://api.groq.com/openai/v1/audio/transcriptions"
            
            try:
                with open(video_path, "rb") as audio_file:
                    files = {
                        "file": (file.filename, audio_file, file.mimetype or "video/mp4"),
                        "model": (None, "whisper-large-v3"),
                        "response_format": (None, "srt")
                    }
                    res_audio = requests.post(transcribe_url, headers=headers, files=files, timeout=90)

                if res_audio.status_code == 200:
                    srt_transcript = res_audio.text
                    working_key = key
                    break
                else:
                    last_error = f"Key ({key[:8]}...): {res_audio.text}"
            except Exception as ex:
                last_error = str(ex)
                continue

        if not srt_transcript or not working_key:
            return jsonify({'error': f'Whisper Error: {last_error}'}), 500

        # ជំហានទី ២៖ បកប្រែ SRT Subtitle ទៅជាភាសាខ្មែរដោយរក្សា Timeline/SRT Format ដដែល
        chat_url = "https://api.groq.com/openai/v1/chat/completions"
        prompt = f"""
អ្នកគឺជាអ្នកជំនាញបកប្រែ Subtitle និងស្គ្រីបវីដេអូភាសាខ្មែរ។
ខាងក្រោមនេះជា Subtitle SRT ដើម (ភាសា {lang})៖
```srt
{srt_transcript}
        
