import os
import tempfile
from flask import Flask, request, jsonify, send_from_directory
import google.generativeai as genai

app = Flask(__name__, static_folder='.', static_url_path='')

# កំណត់ Gemini API Key
API_KEY = os.getenv("GEMINI_API_KEY")
if API_KEY:
    genai.configure(api_key=API_KEY)

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
    source_lang = LANG_MAP.get(lang_code, 'Thai')

    if file.filename == '':
        return jsonify({'error': 'សូមជ្រើសរើស File'}), 400

    if not API_KEY:
        return jsonify({'error': 'មិនទាន់កំណត់ GEMINI_API_KEY'}), 500

    temp_path = None
    uploaded_file = None

    try:
        # បង្កើត Temp File ដើម្បី រក្សាទុក Video/Audio ជាបណ្តោះអាសន្ន
        suffix = os.path.splitext(file.filename)[1]
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            file.save(tmp.name)
            temp_path = tmp.name

        # Upload File ទៅ Gemini File API
        uploaded_file = genai.upload_file(path=temp_path)

        prompt = f"""
អ្នកគឺជាអ្នកបកប្រែ និងដកស្រង់សំឡេងអាជីព។
សូមស្ដាប់សំឡេង/វីដេអូដែលបាន Upload នេះ (ភាសាដើម៖ {source_lang}) រួច៖
1. ស្ដាប់ និងបកប្រែខ្លឹមសារទាំងអស់មកជា "ភាសាខ្មែរ" ឱ្យមានលំហូររលូន និងពិរោះ។
2. បើជាសាច់រឿង ឬកិច្ចសន្ទនា សូមរៀបចំជាកថាខណ្ឌ ឬរៀបតាមលំដាប់លំដោយឱ្យងាយអាន។
3. រក្សាឈ្មោះតួអង្គ និងពាក្យសំខាន់ៗឱ្យបានត្រឹមត្រូវ។
"""

        model = genai.GenerativeModel('gemini-1.5-flash')
        response = model.generate_content([uploaded_file, prompt])

        return jsonify({'translated_text': response.text})

    except Exception as e:
        return jsonify({'error': str(e)}), 500

    finally:
        # លុប Temp File និង File លើ Gemini Clean up
        if temp_path and os.path.exists(temp_path):
            os.remove(temp_path)
        if uploaded_file:
            try:
                genai.delete_file(uploaded_file.name)
            except Exception:
                pass

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
