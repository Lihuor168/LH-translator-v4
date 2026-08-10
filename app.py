import os
from flask import Flask, request, jsonify, send_from_directory
import google.generativeai as genai

app = Flask(__name__, static_folder='.', static_url_path='')

# កំណត់ Gemini API Key ពី Environment Variable
API_KEY = os.getenv("GEMINI_API_KEY")
if API_KEY:
    genai.configure(api_key=API_KEY)

@app.route('/')
def index():
    return send_from_directory('.', 'index.html')

@app.route('/<path:path>')
def serve_static(path):
    return send_from_directory('.', path)

@app.route('/translate', methods=['POST'])
def translate():
    try:
        data = request.json
        story_text = data.get('text', '')
        source_lang = data.get('source_lang', 'Auto-detect')

        if not story_text.strip():
            return jsonify({'error': 'សូមបញ្ចូលអត្ថបទសាច់រឿង'}), 400

        if not API_KEY:
            return jsonify({'error': 'មិនទាន់មាន GEMINI_API_KEY ក្នុង Environment Variable ទេ'}), 500

        # បង្កើត Prompt សម្រាប់បកប្រែរឿងនិទានឱ្យមានលំហូរល្អ
        prompt = f"""
អ្នកគឺជាអ្នកបកប្រែប្រលោមលោក និងរឿងនិទានជើងចាស់ម្នាក់។ 
សូមបកប្រែអត្ថបទខាងក្រោមពី {source_lang} មកជា ភាសាខ្មែរ ដោយគោរពតាមគោលការណ៍៖
1. ប្រើប្រាស់ភាសាខ្មែរឱ្យមានលំហូររលូន ពិរោះ រំភើប ឬសោកសៅ តាមសាច់រឿងដើម (មិនបកប្រែពាក្យជាន់ពាក្យរឹងៗទេ)។
2. រក្សាឈ្មោះតួអង្គ និងទីកន្លែងឱ្យបានត្រឹមត្រូវ និងថេររហូតចប់។
3. រក្សាទម្រង់កថាខណ្ឌ (Paragraph formatting) ឱ្យដូចដើម។

អត្ថបទដើម៖
{story_text}
"""

        model = genai.GenerativeModel('gemini-1.5-flash')
        response = model.generate_content(prompt)

        return jsonify({'translated_text': response.text})

    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
 
