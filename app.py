import os
import tempfile
from flask import Flask, request, jsonify, send_from_directory
from openai import OpenAI

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

    # យក API Key ពី Input ឬ Environment Variable
    api_key = custom_key or os.getenv("OPENAI_API_KEY", "").strip()

    if not api_key:
        return jsonify({'error': 'មិនទាន់មាន OpenAI API Key ទេ! សូមបញ្ចូល Key (ផ្តើមដោយ sk-...)'}), 400

    temp_path = None
    try:
        # Save temporary file
        suffix = os.path.splitext(file.filename)[1]
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            file.save(tmp.name)
            temp_path = tmp.name

        client = OpenAI(api_key=api_key)

        # ជំហានទី ១៖ ប្រើ Whisper ដើម្បី Extract Transcript
        with open(temp_path, "rb") as audio_file:
            transcript_res = client.audio.transcriptions.create(
                model="whisper-1", 
                file=audio_file
            )
        
        transcript_text = transcript_res.text

        # ជំហានទី ២៖ ប្រើ GPT-4o-mini បកប្រែជាស្គ្រីបខ្មែរ
        prompt = f"""
អ្នកគឺជាអ្នកសម្រាយរឿង និងបកប្រែវីដេអូអាជីព។
ខាងក្រោមនេះជា Transcript ដើម (ភាសា {lang})៖
"{transcript_text}"

សូមបកប្រែ និងរៀបចំអត្ថបទខាងលើជា "ភាសាខ្មែរ" តាមទម្រង់/ស្ទីល៖ {style} ឱ្យមានន័យពិរោះ ស្ទាត់ ទាក់ទាញ និងសមស្របតាមសាច់រឿង។
"""

        completion = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are an expert translator and scriptwriter for YouTube videos."},
                {"role": "user", "content": prompt}
            ]
        )

        khmer_script = completion.choices[0].message.content

        return jsonify({
            'transcript': transcript_text,
            'khmer_script': khmer_script
        })

    except Exception as e:
        return jsonify({'error': f'OpenAI Error: {str(e)}'}), 500

    finally:
        if temp_path and os.path.exists(temp_path):
            os.remove(temp_path)

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
