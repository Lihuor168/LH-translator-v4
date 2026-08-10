import os
import tempfile
from flask import Flask, request, jsonify, send_from_directory
import google.generativeai as genai

app = Flask(__name__, static_folder='.', static_url_path='')

# 🔑 System Default API Keys (ប្រើពេលអ្នកប្រើប្រាស់មិនបានវាយ Key ចូល)
DEFAULT_API_KEYS = [
    "AIzaSyYourFirstKeyHere001",
    "AIzaSyYourSecondKeyHere002",
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

    # កំណត់ List នៃ API Key ត្រូវប្រើ (បើមាន Custom Key ប្រើ Custom Key មុន)
    keys_to_try = [custom_key] if custom_key else DEFAULT_API_KEYS

    temp_path = None
    try:
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
            if not api_key:
                continue
            
            uploaded_file = None
            try:
                genai.configure(api_key=api_key.strip())
                uploaded_file = genai.upload_file(path=temp_path)

                model = genai.GenerativeModel('gemini-1.5-flash')
                response = model.generate_content([uploaded_file, prompt])

                try:
                    genai.delete_file(uploaded_file.name)
                except Exception:
                    pass

                return jsonify({'translated_text': response.text})

            except Exception as e:
                last_error = str(e)
                if uploaded_file:
                    try:
                        genai.delete_file(uploaded_file.name)
                    except Exception:
                        pass
                continue

        return jsonify({'error': f'API Key មានបញ្ហា ឬមិនត្រឹមត្រូវ! កំហុស៖ {last_error}'}), 500

    except Exception as e:
        return jsonify({'error': str(e)}), 500

    finally:
        if temp_path and os.path.exists(temp_path):
            os.remove(temp_path)

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
    
