import os
import tempfile
import requests
from flask import Flask, request, jsonify, send_from_directory

app = Flask(__name__, static_folder='.', static_url_path='')

@app.route('/')
def index():
    return send_from_directory('.', 'index.html')

@app.route('/<path:path>')
def serve_static(path):
    return send_from_directory('.', path)

@app.route('/translate-video', methods=['POST'])
def translate_video():
    if 'file' not in request.files:
        return jsonify({'error': 'មិនមាន File ត្រូវបាន Upload ទេ'}), 400

    file = request.files['file']
    lang = request.form.get('lang', 'Chinese')
    style = request.form.get('style', 'សម្រាយរឿង YouTube')
    raw_keys = request.form.get('api_key', '').strip()

    if file.filename == '':
        return jsonify({'error': 'សូមជ្រើសរើស File'}), 400

    # យក Keys ពី Frontend ឬ Environment Variable ក្នុង Render
    env_keys = os.getenv("GROQ_API_KEY", "").strip()
    combined_keys_text = raw_keys or env_keys

    if not combined_keys_text:
        return jsonify({'error': 'មិនទាន់មាន Groq API Key ទេ! សូមបញ្ចូល Key យ៉ាងហោចណាស់ ១'}), 400

    # បំបែក Key ចេញជា List
    key_list = [k.strip() for k in combined_keys_text.replace('\n', ',').split(',') if k.strip()]

    temp_path = None
    try:
        # រក្សាទុក File បណ្តោះអាសន្ន
        suffix = os.path.splitext(file.filename)[1]
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            file.save(tmp.name)
            temp_path = tmp.name

        transcript_text = None
        working_key = None
        last_error = ""

        # 🔄 Auto Switch: លុប/ប្តូរទៅ Key បន្ទាប់ស្វ័យប្រវត្តិបើ Key មួយជួប Error
        for key in key_list:
            headers = {"Authorization": f"Bearer {key}"}
            transcribe_url = "https://api.groq.com/openai/v1/audio/transcriptions"
            
            try:
                with open(temp_path, "rb") as audio_file:
                    files = {
                        "file": (file.filename, audio_file, file.mimetype or "audio/mp3"),
                        "model": (None, "whisper-large-v3")
                    }
                    res_audio = requests.post(transcribe_url, headers=headers, files=files, timeout=60)

                if res_audio.status_code == 200:
                    transcript_text = res_audio.json().get("text", "")
                    working_key = key
                    break # ដើរជោគជ័យ បញ្ចប់ Loop
                else:
                    last_error = f"Key ({key[:8]}...): {res_audio.text}"
            except Exception as ex:
                last_error = str(ex)
                continue

        if not transcript_text or not working_key:
            return jsonify({'error': f'Key ទាំងអស់មានបញ្ហា! Error ចុងក្រោយ៖ {last_error}'}), 500

        # ជំហានទី ២៖ ប្រើ Key ដែលដើរនោះទៅបកប្រែជាស្គ្រីបខ្មែរជាមួយ Llama 3.3 70B
        chat_url = "https://api.groq.com/openai/v1/chat/completions"
        prompt = f"""
អ្នកគឺជាអ្នកសម្រាយរឿង និងជាអ្នកសរសេរស្គ្រីបវីដេអូអាជីពភាសាខ្មែរ។
ខាងក្រោមនេះជា Transcript ដើម (ភាសា {lang})៖
"{transcript_text}"

សូមធ្វើការបកប្រែ និងរៀបចំសរសេរឡើងវិញជា "ភាសាខ្មែរ" ឱ្យសមស្របតាមស្ទីល៖ {style} ដោយគោរពតាមលក្ខខណ្ឌដូចខាងក្រោម៖
1. ប្រើប្រាស់ភាសាខ្មែរដែលរលូន ពិរោះ ងាយយល់ និងមានលំហូរធម្មជាតិ (មិនបកប្រែពាក្យទល់ពាក្យ ឬតាមរចនាសម្ព័ន្ធភាសាដើមត្រង់ៗពេកទេ)។
2. សម្រួលពាក្យពេចន៍ឱ្យត្រូវតាមកថាខណ្ឌ និងបរិបទនៃសាច់រឿង (បើជាសាច់រឿង/សម្រាយរឿង ប្រើពាក្យទាក់ទាញអារម្មណ៍)។
3. រក្សាឈ្មោះតួអង្គ ទីកន្លែង និងខ្លឹមសារសំខាន់ៗនៃសាច់រឿងឱ្យនៅដដែល។
"""

        payload = {
            "model": "llama-3.3-70b-versatile",
            "messages": [
                {"role": "system", "content": "You are an expert translator and scriptwriter for YouTube videos. Respond in Khmer."},
                {"role": "user", "content": prompt}
            ]
        }

        res_chat = requests.post(
            chat_url, 
            headers={"Authorization": f"Bearer {working_key}", "Content-Type": "application/json"}, 
            json=payload,
            timeout=60
        )

        if res_chat.status_code != 200:
            return jsonify({'error': f'Groq Translation Error: {res_chat.text}'}), 500

        khmer_script = res_chat.json()['choices'][0]['message']['content']

        return jsonify({
            'transcript': transcript_text,
            'khmer_script': khmer_script
        })

    except Exception as e:
        return jsonify({'error': f'Server Error: {str(e)}'}), 500

    finally:
        if temp_path and os.path.exists(temp_path):
            os.remove(temp_path)

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
    
