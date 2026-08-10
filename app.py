import os
import tempfile
from flask import Flask, request, jsonify, send_from_directory
from google import genai

app = Flask(__name__, static_folder='.', static_url_path='')

# 🔑 បញ្ចូល Gemini API Key (AQ...) របស់អ្នកនៅទីនេះ (អាចដាក់ច្រើនបាន)
DEFAULT_API_KEYS = [
    "AQ.Ab8RN6Lv...", # បិទ Key AQ. របស់អ្នកទី១ នៅទីនេះ
    "AQ.Ab8RN6Lv...", # បិទ Key AQ. របស់អ្នកទី២ (បើមាន)
]

LANG_MAP = {
    'th': 'Thai',
    'en': 'English',
    'ko': 'Korean',
    'ja': 'Japanese',
    'zh': 'Chinese',
    'vi': 'Vietnamese'
}

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
    lang_code = request.form.get('lang', 'th')
    custom_key = request.form.get('api_key', '').strip()
    source_lang = LANG_MAP.get(lang_code, 'Thai')

    if file.filename == '':
        return jsonify({'error': 'សូមជ្រើសរើស File'}), 400

    # រៀបចំ List API Key
    keys_to_try = []
    if custom_key:
        keys_to_try.append(custom_key)
    
    env_key = os.getenv("GEMINI_API_KEY", "").strip()
    if env_key:
        keys_to_try.append(env_key)
        
    keys_to_try.extend(DEFAULT_API_KEYS)

    temp_path = None
    try:
        # បង្កើត Temp file
        suffix = os.path.splitext(file.filename)[1]
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            file.save(tmp.name)
            temp_path = tmp.name

        prompt = f"""
អ្នកគឺជាអ្នកបកប្រែ និងដកស្រង់សំឡេងអាជីព។
សូមស្ដាប់សំឡេង/វីដេអូដែលបាន Upload នេះ (ភាសាដើម៖ {source_lang}) រួច៖
1. ស្ដាប់ និងបកប្រែខ្លឹមសារទាំងអស់មកជា "ភាសាខ្មែរ" ឱ្យមានលំហូររលូន និងពិរោះ។
2. បើជាសាច់រឿង ឬកិច្ចសន្ទនា សូមរៀបចំជាកថាខណ្ឌ ឬរៀបតាមលំដាប់លំដោយឱ្យងាយអាន។
3. រក្សាឈ្មោះតួអង្គ និងពាក្យសំខាន់ៗឱ្យបានត្រឹមត្រូវ។
"""

        last_error = None

        for api_key in keys_to_try:
            key_clean = api_key.strip()
            if not key_clean:
                continue

            uploaded_file = None
            try:
                # ប្រើ Client នៃ google-genai សម្រាប់ Key AQ.
                client = genai.Client(api_key=key_clean)
                
                # Upload File
                uploaded_file = client.files.upload(file=temp_path)

                # ហៅ Model ដំណើរការបកប្រែ
                response = client.models.generate_content(
                    model='gemini-2.5-flash',
                    contents=[uploaded_file, prompt]
                )

                # លុប File ចោលវិញ
                try:
                    client.files.delete(name=uploaded_file.name)
                except Exception:
                    pass

                return jsonify({'translated_text': response.text})

            except Exception as e:
                last_error = str(e)
                if uploaded_file and 'client' in locals():
                    try:
                        client.files.delete(name=uploaded_file.name)
                    except Exception:
                        pass
                continue

        return jsonify({'error': f'កំហុសក្នុងការប្រើប្រាស់ API Key៖ {last_error}'}), 500

    except Exception as e:
        return jsonify({'error': str(e)}), 500

    finally:
        if temp_path and os.path.exists(temp_path):
            os.remove(temp_path)

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
    
