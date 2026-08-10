import os,json,uuid,shutil,subprocess
from pathlib import Path
from flask import Flask,render_template,request,jsonify,send_from_directory
from google import genai
from google.genai import types
app=Flask(__name__); app.config['MAX_CONTENT_LENGTH']=500*1024*1024
JOB=Path('/tmp/khmer-translator-v4'); JOB.mkdir(parents=True,exist_ok=True)
KEY=os.getenv('GEMINI_API_KEY',''); MODEL=os.getenv('GEMINI_MODEL','gemini-2.5-flash'); client=genai.Client(api_key=KEY) if KEY else None
EXT={'.mp4','.mkv','.mov','.avi','.webm','.mp3','.wav','.m4a','.aac','.flac','.ogg'}
LANG={'th':'Thai','ko':'Korean','ja':'Japanese','km':'Khmer'}
def cmd(c):
 p=subprocess.run(c,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
 if p.returncode: raise RuntimeError(p.stderr[-3000:])
 return p.stdout
def duration(p): return float(cmd(['ffprobe','-v','error','-show_entries','format=duration','-of','default=noprint_wrappers=1:nokey=1',str(p)]).strip())
def extract(src,dst): cmd(['ffmpeg','-y','-i',str(src),'-vn','-ac','1','-ar','16000','-c:a','pcm_s16le',str(dst)])
def parts(src,out,sec=600):
 d=duration(src)
 if d<=sec:return [(src,0.0)]
 a=[]; start=0.; i=0
 while start<d:
  p=out/f'part_{i:04d}.wav'; cmd(['ffmpeg','-y','-ss',str(start),'-i',str(src),'-t',str(sec),'-ac','1','-ar','16000','-c:a','pcm_s16le',str(p)]); a.append((p,start)); start+=sec;i+=1
 return a
def transcribe(p):
 f=client.files.upload(file=str(p))
 prompt='''Transcribe this audio. Return ONLY valid JSON: {"segments":[{"start":0.0,"end":2.5,"text":"..."}]}. Times are seconds from the beginning of THIS file. Keep chronological order, do not summarize or invent, and make subtitle-friendly short segments.'''
 r=client.models.generate_content(model=MODEL,contents=[f,prompt],config=types.GenerateContentConfig(response_mime_type='application/json'))
 try: client.files.delete(name=f.name)
 except: pass
 return json.loads(r.text).get('segments',[])
def translate_segments(segs,lang):
 if not segs:return []
 numbered='\n'.join(f'{i+1}. {s["text"].strip()}' for i,s in enumerate(segs))
 prompt=f'''Translate each numbered subtitle into natural {LANG[lang]}. Return ONLY JSON {{"translations":["..."]}}. Return exactly one item per input, same order, do not merge/split. For Khmer use natural Cambodian Khmer.\n{numbered}'''
 r=client.models.generate_content(model=MODEL,contents=prompt,config=types.GenerateContentConfig(response_mime_type='application/json'))
 return [str(x).strip() for x in json.loads(r.text).get('translations',[])][:len(segs)]
def srt_time(x):
 ms=max(0,int(round(float(x)*1000)));h,ms=divmod(ms,3600000);m,ms=divmod(ms,60000);s,ms=divmod(ms,1000);return f'{h:02d}:{m:02d}:{s:02d},{ms:03d}'
def srt(segs,texts=None):
 out=[]
 for i,s in enumerate(segs):
  t=(texts[i] if texts and i<len(texts) else s['text']).strip()
  if t: out += [str(i+1),f"{srt_time(s['start'])} --> {srt_time(s['end'])}",t,'']
 return '\n'.join(out)
def script(segs):
 src='\n'.join(s['text'].strip() for s in segs)
 p=f'''Convert this transcript into a polished natural Khmer script for a Cambodian story/drama voice-over. Preserve events, names, dialogue and emotions. Do not invent. Return only Khmer script.\n\n{src}'''
 return client.models.generate_content(model=MODEL,contents=p).text.strip()
@app.get('/')
def home():return render_template('index.html')
@app.get('/health')
def health():return jsonify(ok=True,version='V4-Gemini')
@app.post('/api/process')
def process():
 if not KEY:return jsonify(error='GEMINI_API_KEY is not configured.'),500
 if 'file' not in request.files:return jsonify(error='No file uploaded.'),400
 u=request.files['file']; ext=Path(u.filename).suffix.lower()
 if ext not in EXT:return jsonify(error='Unsupported file type.'),400
 selected=request.form.getlist('languages') or ['km']; jid=uuid.uuid4().hex; w=JOB/jid;w.mkdir()
 try:
  inp=w/f'input{ext}';u.save(inp); audio=w/'audio.wav';extract(inp,audio)
  segs=[]
  for p,off in parts(audio,w):
   for s in transcribe(p):
    try: segs.append({'start':float(s.get('start',0))+off,'end':float(s.get('end',0))+off,'text':str(s.get('text','')).strip()})
    except: pass
  segs=[s for s in segs if s['text']]; transcript='\n'.join(s['text'] for s in segs)
  outputs={'transcript':transcript}; (w/'transcript.txt').write_text(transcript,encoding='utf-8');(w/'transcript.srt').write_text(srt(segs),encoding='utf-8')
  for lang in selected:
   vals=translate_segments(segs,lang); outputs[lang]=script(segs) if lang=='km' else '\n'.join(vals)
   (w/f'{lang}.txt').write_text(outputs[lang],encoding='utf-8');(w/f'{lang}.srt').write_text(srt(segs,vals),encoding='utf-8')
  for p in [inp,audio]:
   try:p.unlink()
   except:pass
  d={'transcript_txt':f'/download/{jid}/transcript.txt','transcript_srt':f'/download/{jid}/transcript.srt'}
  for l in selected:d[f'{l}_txt']=f'/download/{jid}/{l}.txt';d[f'{l}_srt']=f'/download/{jid}/{l}.srt'
  return jsonify(ok=True,version='V4-Gemini',job_id=jid,transcript=transcript,outputs=outputs,downloads=d)
 except Exception as e: shutil.rmtree(w,ignore_errors=True);return jsonify(error=str(e)),500
@app.get('/download/<jid>/<filename>')
def download(jid,filename):return send_from_directory(JOB/jid,filename,as_attachment=True)
if __name__=='__main__':app.run(host='0.0.0.0',port=int(os.getenv('PORT',10000)))
