import os
import tempfile
from flask import Flask, request, jsonify, send_from_directory
from google import genai

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
    custom_key = request.form.get('api_key', '').strip()

    if file.filename == '':
        return jsonify({'error': 'សូមជ្រើសរើស File'}), 400

    # យក API Key ពី Input ឬ Environment Variable លើ Render
    api_key = custom_key or os.getenv("GEMINI_API_KEY", "").strip()

    if not api_key:
        return jsonify({'error': 'មិនទាន់មាន API Key ទេ! សូមបញ្ចូល Key ឬដាក់ក្នុង Render Environment'}), 400

    temp_path = None
    uploaded_file = None
    try:
        # Save temp file
        suffix = os.path.splitext(file.filename)[1]
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            file.save(tmp.name)
            temp_path = tmp.name

        # ប្រើ Google GenAI Client ថ្មី
        client = genai.Client(api_key=api_key)

        # Upload file ទៅ Google Gemini
        uploaded_file = client.files.upload(file=temp_path)

        # Prompt
        prompt = f"""
អ្នកគឺជាអ្នកសម្រាយរឿង និងបកប្រែវីដេអូអាជីព។
សូមស្ដាប់សំឡេង/វីដេអូនេះ (ភាសាដើម៖ {lang}) ហើយធ្វើការឆ្លើយតបជា ២ ផ្នែកដូចខាងក្រោម៖

---TRANSCRIPT---
(សរសេរអត្ថបទដើមដែលស្ដាប់បានពីសំឡេងក្នុងវីដេអូជាភាសា {lang})

---KHMER_SCRIPT---
(បកប្រែ និងរៀបចំអត្ថបទខាងលើជា "ភាសាខ្មែរ" តាមទម្រង់/ស្ទីល៖ {style} ឱ្យមានន័យពិរោះ ស្ទាត់ និងទាក់ទាញ)
"""

        # Generate Response
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=[uploaded_file, prompt]
        )

        full_text = response.text or ""

        # បំបែកចេញជា ២ ផ្នែក (Transcript និង Khmer Script)
        transcript = ""
        khmer_script = ""

        if "---TRANSCRIPT---" in full_text and "---KHMER_SCRIPT---" in full_text:
            parts = full_text.split("---KHMER_SCRIPT---")
            transcript = parts[0].replace("---TRANSCRIPT---", "").strip()
            khmer_script = parts[1].strip()
        else:
            khmer_script = full_text

        return jsonify({
            'transcript': transcript,
            'khmer_script': khmer_script
        })

    except Exception as e:
        return jsonify({'error': str(e)}), 500

    finally:
        # Clean up files
        if uploaded_file and 'client' in locals():
            try:
                client.files.delete(name=uploaded_file.name)
            except Exception:
                pass
        if temp_path and os.path.exists(temp_path):
            os.remove(temp_path)

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
    
