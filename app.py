import os
import re
import shutil
import tempfile
import asyncio
import subprocess
import requests
from flask import Flask, request, jsonify, send_from_directory, send_file

app = Flask(__name__, static_folder='.', static_url_path='')

@app.route('/')
def index():
    return send_from_directory('.', 'index.html')

@app.route('/<path:path>')
def serve_static(path):
    return send_from_directory('.', path)

def parse_srt(srt_text):
    """Parse SRT subtitles with robust regex."""
    blocks = re.split(r'\n\s*\n', srt_text.strip())
    subtitles = []
    
    for block in blocks:
        lines = block.strip().split('\n')
        if len(lines) >= 3:
            index = lines[0].strip()
            time_match = re.match(r'(\d{2}:\d{2}:\d{2},\d{3})\s*-->\s*(\d{2}:\d{2}:\d{2},\d{3})', lines[1].strip())
            if time_match:
                start_time, end_time = time_match.groups()
                text = " ".join([l.strip() for l in lines[2:] if l.strip()])
                subtitles.append({
                    'index': index,
                    'start': start_time,
                    'end': end_time,
                    'text': text
                })
    return subtitles

def srt_time_to_seconds(srt_time):
    """Convert SRT timestamp (00:01:23,456) to floating point seconds."""
    hours, minutes, seconds_ms = srt_time.split(':')
    seconds, milliseconds = seconds_ms.split(',')
    return int(hours) * 3600 + int(minutes) * 60 + int(seconds) + int(milliseconds) / 1000.0

async def generate_tts_async(text, output_path):
    """Generate audio using Edge TTS."""
    communicate = edge_tts.Communicate(text, "km-KH-PisethNeural")
    await communicate.save(output_path)

def generate_tts(text, output_path):
    """Synchronous wrapper for Edge TTS."""
    asyncio.run(generate_tts_async(text, output_path))

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
    
    try:
        file.save(video_path)

        # 1. Whisper Transcribe -> Get SRT with Timestamps
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
                    res_audio = requests.post(transcribe_url, headers=headers, files=files, timeout=120)

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
            return jsonify({'error': f'Whisper Transcription Error: {last_error}'}), 500

        # 2. Translate SRT into Khmer using Llama-3.3-70b
        chat_url = "https://api.groq.com/openai/v1/chat/completions"
        prompt = f"""You are a professional subtitle translator into Khmer.
Translate the following SRT subtitles from {lang} to Khmer.
Maintain the exact SRT timing format (00:00:00,000 --> 00:00:00,000).
Style: {style}.
Output ONLY valid SRT blocks. No introductions, no commentary.

Original SRT:
{srt_transcript}
"""

        payload = {
            "model": "llama-3.3-70b-versatile",
            "messages": [
                {"role": "system", "content": "You are a professional SRT translator. Output raw SRT content only."},
                {"role": "user", "content": prompt}
            ],
            "temperature": 0.3
        }

        res_chat = requests.post(
            chat_url, 
            headers={"Authorization": f"Bearer {working_key}", "Content-Type": "application/json"}, 
            json=payload,
            timeout=90
        )

        if res_chat.status_code != 200:
            return jsonify({'error': f'Groq Translation Error: {res_chat.text}'}), 500

        khmer_srt = res_chat.json()['choices'][0]['message']['content'].strip()

        # Clean markdown codeblocks if LLM included them
        if khmer_srt.startswith("```"):
            khmer_srt = re.sub(r'^```[a-zA-Z]*\n', '', khmer_srt)
            khmer_srt = re.sub(r'\n```$', '', khmer_srt)

        # 3. Parse Khmer SRT and Generate Audio Clips
        parsed_subs = parse_srt(khmer_srt)
        
        if not parsed_subs:
            return jsonify({'error': 'មិនអាចបកប្រែជា SRT Subtitle បានទេ'}), 500

        input_files = []
        filter_complex_parts = []
        valid_audio_index = 0

        for sub in parsed_subs:
            if not sub['text'].strip():
                continue
            
            snippet_path = os.path.join(temp_dir, f"audio_{valid_audio_index}.mp3")
            generate_tts(sub['text'], snippet_path)
            
            start_sec = srt_time_to_seconds(sub['start'])
            delay_ms = int(start_sec * 1000)
            
            input_files.extend(['-i', snippet_path])
            # Delay audio for timing alignment
            filter_complex_parts.append(f"[{valid_audio_index}:a]adelay={delay_ms}|{delay_ms}[a{valid_audio_index}];")
            valid_audio_index += 1

        if valid_audio_index == 0:
            return jsonify({'error': 'គ្មានអត្ថបទត្រូវបង្កើតសំឡេងឡើយ'}), 500

        # 4. Merge Audio Clips with FFmpeg
        merged_audio_path = os.path.join(temp_dir, "final_dubbed_audio.mp3")
        inputs_tag = "".join([f"[a{i}]" for i in range(valid_audio_index)])
        filter_str = "".join(filter_complex_parts) + f"{inputs_tag}amix=inputs={valid_audio_index}:dropout_transition=0:normalize=0[outa]"

        ffmpeg_audio_cmd = ['ffmpeg', '-y'] + input_files + [
            '-filter_complex', filter_str,
            '-map', '[outa]',
            '-ac', '2',
            '-ar', '44100',
            merged_audio_path
        ]
        
        subprocess.run(ffmpeg_audio_cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

        # 5. Merge New Khmer Audio into Original Video
        output_video_path = os.path.join(temp_dir, "dubbed_output.mp4")
        merge_cmd = [
            'ffmpeg', '-y',
            '-i', video_path,
            '-i', merged_audio_path,
            '-c:v', 'copy',
            '-c:a', 'aac',
            '-map', '0:v:0',
            '-map', '1:a:0',
            '-shortest',
            output_video_path
        ]
        
        subprocess.run(merge_cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

        # Send finished video back to user
        return send_file(output_video_path, mimetype='video/mp4', as_attachment=False, download_name="dubbed_video.mp4")

    except subprocess.CalledProcessError as spe:
        return jsonify({'error': f'FFmpeg Processing Error: {spe.stderr.decode("utf-8", errors="ignore")}'}), 500
    except Exception as e:
        return jsonify({'error': f'Server Error: {str(e)}'}), 500
    finally:
        # Clean up temporary directory to avoid filling up disk storage
        shutil.rmtree(temp_dir, ignore_errors=True)

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
    
