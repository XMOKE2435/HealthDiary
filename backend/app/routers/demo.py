from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse


router = APIRouter(tags=["demo"]) 


@router.get("/demo", response_class=HTMLResponse)
def demo_home(request: Request):
    return HTMLResponse(
        """
        <html>
        <head>
          <meta charset="utf-8">
          <meta http-equiv="Cache-Control" content="no-cache, no-store, must-revalidate">
          <meta http-equiv="Pragma" content="no-cache">
          <meta http-equiv="Expires" content="0">
          <title>HealthDiary Demo</title>
          <style>
            :root{
              font-family:'Segoe UI',system-ui,-apple-system,BlinkMacSystemFont,'Helvetica Neue',sans-serif;
              color:#1f2933;
            }
            body{
              margin:0;
              background:#f5f7fa;
            }
            header{
              background:linear-gradient(135deg,#0b6efd,#175cd3);
              color:#fff;
              padding:32px 36px 38px;
              box-shadow:0 8px 24px rgba(13,64,165,0.25);
            }
            header h1{margin:0;font-size:30px;font-weight:600;}
            header p{margin:10px 0 0;font-size:15px;color:rgba(255,255,255,0.85);}
            main{
              padding:32px 36px 48px;
              max-width:1200px;
              margin:auto;
            }
            .row{display:flex;gap:28px;flex-wrap:wrap;}
            .col{flex:1;min-width:340px;}
            .card{
              background:#fff;
              border-radius:18px;
              padding:22px 24px;
              box-shadow:0 10px 30px rgba(15,23,42,0.1);
              margin-bottom:28px;
              border:1px solid #e4e7ec;
            }
            h3{margin:0 0 18px;font-size:19px;color:#101828;}
            label{
              font-size:12px;
              font-weight:600;
              color:#475467;
              text-transform:uppercase;
              letter-spacing:0.05em;
            }
            input,textarea,select{
              width:100%;
              padding:11px 13px;
              margin:8px 0 16px;
              border:1px solid #d0d5dd;
              border-radius:12px;
              font-size:14px;
              background:#fff;
              transition:border 0.2s, box-shadow 0.2s;
            }
            input:focus,textarea:focus{
              outline:none;
              border-color:#0b6efd;
              box-shadow:0 0 0 3px rgba(11,110,253,0.15);
            }
            button{
              padding:11px 18px;
              border:none;
              border-radius:12px;
              background:#0b6efd;
              color:#fff;
              font-weight:600;
              cursor:pointer;
              transition:all 0.15s;
              box-shadow:0 8px 16px rgba(11,110,253,0.2);
            }
            button:hover{background:#0955c1;transform:translateY(-1px);}
            button.secondary{
              background:#eef2ff;
              color:#19365f;
              box-shadow:none;
            }
            small{color:#5e6472;}
            pre{
              background:#0f172a;
              color:#e4e7ec;
              padding:14px 16px;
              border-radius:12px;
              font-size:13px;
              max-height:280px;
              overflow:auto;
            }
            #chatBox{
              border-radius:14px;
              background:#f8fafc;
              border:1px solid #e4e7ec;
              padding:10px 12px;
            }
            #chatBox div{margin-bottom:8px;}
            #chatBox b{display:inline-block;width:80px;text-transform:capitalize;color:#0f172a;}
            code{
              background:#e6efff;
              color:#0b6efd;
              padding:5px 9px;
              border-radius:9px;
              font-size:13px;
            }
            .record-status{
              background:#e0f2fe;
              color:#0b5394;
              padding:10px 14px;
              border-radius:10px;
              font-size:14px;
              margin-bottom:12px;
            }
            @media(max-width:900px){
              .row{flex-direction:column;}
            }
          </style>
        </head>
        <body>
          <header style="display:flex;justify-content:space-between;align-items:flex-start;gap:16px;flex-wrap:wrap;">
            <div>
              <h1 id="titleText">HealthDiary MVP Demo</h1>
              <p id="subtitleText">Interactive symptom intake, detailed recommendations, and patient-ready visit preparation.</p>
            </div>
            <div style="flex-shrink:0;">
              <button class="secondary" id="langToggleBtn" onclick="toggleLanguageMode()" title="Switch language / 切换语言" style="background:rgba(255,255,255,0.25);color:#fff;border:2px solid #fff;font-weight:600;padding:10px 16px;">
                🌐 Language / 语言
              </button>
              <small style="display:block;color:rgba(255,255,255,0.85);margin-top:6px;">If you don't see this button, press Ctrl+Shift+R to refresh.</small>
            </div>
          </header>
          <main>
          <div class="row">
            <div class="col">
              <div class="card">
                <h3 id="card1Title">1) Symptom Entry (LLM chat → single saved entry)</h3>
                <label>User ID</label>
                <input id="userId" value="demo-user-1"/>
                <div style="display:flex; gap:8px;">
                  <div style="flex:1;">
                    <label>Date (YYYY-MM-DD)</label>
                    <input id="dateInput" type="date" />
                  </div>
                  <div style="flex:1;">
                    <label>Time (24h, HH:MM)</label>
                    <input id="timeInput" type="time" />
                  </div>
                </div>
                <div id="chatBox" style="height:200px; overflow:auto; margin:10px 0;"></div>
                <input id="chatInput" placeholder="Describe your symptom (you can start here)" />
                <div style="display:flex; gap:8px; margin:8px 0; flex-wrap:wrap;">
                  <button onclick="chatSend()">Send</button>
                  <button class="secondary" onclick="chatReset()">Reset</button>
                  <button class="secondary" id="voiceBtn" style="display:flex;align-items:center;gap:6px;" onclick="toggleVoice()">
                    <span id="voiceIcon">🎙️</span><span id="voiceLabel">Voice Input</span>
                  </button>
                  <button class="secondary" id="ttsBtn" onclick="toggleTts()">🔊 Voice On</button>
                </div>
                <small>Tip: The assistant asks one concise follow-up per turn; once enough info is collected, it auto-saves. You can type or use voice capture.</small>
                <pre id="diaryOut"></pre>
              </div>

              <div class="card">
                <h3 id="card2Title">2) GET /recommendations</h3>
                <button onclick="getRecs()">Fetch Recommendations</button>
                <pre id="recsOut"></pre>
              </div>

              <div class="card">
                <h3 id="card3Title">3) POST /doctor-pack</h3>
                <button onclick="doctorPack()">Generate Doctor Pack</button>
                <div id="packLinks"></div>
              </div>
            </div>

            <div class="col">
              <div class="card">
                <h3 id="card4Title">4) Visit Capture (record + summary)</h3>
                <div class="record-status" id="recordStatus">Microphone idle</div>
                <div style="display:flex; gap:8px; flex-wrap:wrap; margin-bottom:12px;">
                  <button id="recordBtn" onclick="startRecording()">Start Recording</button>
                  <button class="secondary" id="stopRecordBtn" onclick="stopRecording()" disabled>Stop Recording</button>
                  <button class="secondary" id="downloadBtn" onclick="downloadRecording()" disabled style="display:none;">Download Audio</button>
                  <button class="secondary" id="uploadBtn" onclick="uploadRecording()">Upload / Select Audio</button>
                  <input type="file" id="audioFileInput" accept="audio/*" style="display:none;" onchange="handleAudioFileUpload(event)">
                </div>
                <small>Chrome / Edge desktop only. Record audio, then download or upload for transcription.</small>
                <div style="margin-top:18px;">
                  <h4 style="margin:0 0 8px; font-size:16px; color:#0f172a;">Doctor instructions summary</h4>
                  <pre id="sumOut">(no summary yet)</pre>
                  <button class="secondary" id="transcriptToggle" style="display:none; margin-top:8px;" onclick="toggleTranscript()">Show full transcript</button>
                  <pre id="transOut" style="display:none; margin-top:10px;"></pre>
                </div>
              </div>
            </div>
          </div>

          <script>
            // Unified Symptom Chat → single entry
            window._chat = { messages: [], fields: {}, ready:false };
            // Text-to-speech playback for assistant replies
            window._tts = {
              supported: typeof window !== 'undefined' && 'speechSynthesis' in window && typeof SpeechSynthesisUtterance !== 'undefined',
              enabled: true
            };
            // Visit capture state
            window._visitState = { recorder:null, chunks:[], stream:null, transcript:'', spans:[], summary:null, showTranscript:false, recordedBlob:null };
            // Language mode state
            window._langMode = 'ENGLISH';
            window._langCode = 'en';

            async function loadLanguageMode(){
              try{
                const r = await fetch('/language-mode');
                if(!r.ok) return;
                const j = await r.json();
                window._langMode = (j.mode_name || j.mode || 'ENGLISH').toUpperCase();
                applyLanguageToUI();
              }catch(e){
                console.warn('Failed to load language mode', e);
              }
            }

            function applyLanguageToUI(){
              const mode = window._langMode || 'ENGLISH';
              window._langCode = mode === 'CHINESE' ? 'zh' : 'en';
              const title = document.getElementById('titleText');
              const subtitle = document.getElementById('subtitleText');
              const card1 = document.getElementById('card1Title');
              const card2 = document.getElementById('card2Title');
              const card3 = document.getElementById('card3Title');
              const card4 = document.getElementById('card4Title');
              const langBtn = document.getElementById('langToggleBtn');
              if(mode === 'CHINESE'){
                if(title) title.textContent = 'HealthDiary 示例（双语版）';
                if(subtitle) subtitle.textContent = '记录症状、获取生活建议，并为就诊提前做好准备。';
                if(card1) card1.textContent = '1）症状记录（聊天方式 → 自动保存一条记录）';
                if(card2) card2.textContent = '2）获取生活方式建议（GET /recommendations）';
                if(card3) card3.textContent = '3）生成就诊摘要（POST /doctor-pack）';
                if(card4) card4.textContent = '4）门诊录音与总结（语音转写 + 嘱托摘要）';
                if(langBtn) langBtn.textContent = '🌐 当前：中文（点击切换 English）';
              }else{
                if(title) title.textContent = 'HealthDiary MVP Demo';
                if(subtitle) subtitle.textContent = 'Interactive symptom intake, detailed recommendations, and patient-ready visit preparation.';
                if(card1) card1.textContent = '1) Symptom Entry (LLM chat → single saved entry)';
                if(card2) card2.textContent = '2) GET /recommendations';
                if(card3) card3.textContent = '3) POST /doctor-pack';
                if(card4) card4.textContent = '4) Visit Capture (record + summary)';
                if(langBtn) langBtn.textContent = '🌐 Language / 语言';
              }
            }

            async function toggleLanguageMode(){
              const current = window._langMode || 'ENGLISH';
              const next = current === 'CHINESE' ? 'ENGLISH' : 'CHINESE';
              try{
                const r = await fetch('/language-mode', {
                  method: 'POST',
                  headers: {'Content-Type':'application/json'},
                  body: JSON.stringify({mode: next})
                });
                if(r.ok){
                  const j = await r.json();
                  window._langMode = (j.mode_name || j.mode || next).toUpperCase();
                  applyLanguageToUI();
                }else{
                  alert('Failed to switch language mode.');
                }
              }catch(e){
                console.error('Language toggle error', e);
                alert('Unable to switch language mode.');
              }
            }
            function updateTtsUI(){
              const btn = document.getElementById('ttsBtn');
              if(!btn) return;
              if(!window._tts.supported){
                btn.textContent = '🔈 Voice not supported';
                btn.disabled = true;
                btn.style.opacity = 0.6;
                return;
              }
              btn.textContent = window._tts.enabled ? '🔊 Voice On' : '🔇 Voice Off';
              btn.style.opacity = window._tts.enabled ? 1 : 0.65;
            }
            function toggleTts(){
              if(!window._tts.supported){
                alert('Voice playback is not supported in this browser.');
                updateTtsUI();
                return;
              }
              window._tts.enabled = !window._tts.enabled;
              if(!window._tts.enabled && window.speechSynthesis){
                window.speechSynthesis.cancel();
              }
              updateTtsUI();
            }
            function speak(text){
              if(!text || !window._tts.supported || !window._tts.enabled) return;
              try{
                const utter = new SpeechSynthesisUtterance(text);
                utter.lang = (window._langCode === 'zh') ? 'zh-CN' : 'en-US';
                utter.rate = 1;
                window.speechSynthesis.cancel();
                window.speechSynthesis.speak(utter);
              }catch(err){
                console.warn('TTS error', err);
              }
            }
            function renderChat(){
              const box = document.getElementById('chatBox');
              box.innerHTML = window._chat.messages.map(m => `<div><b>${m.role}:</b> ${m.text}</div>`).join('');
              box.scrollTop = box.scrollHeight;
            }
            function chatReset(){ window._chat = { messages: [], fields: {}, ready:false }; renderChat(); document.getElementById('diaryOut').innerText=''; }
            function buildTs(){
              const d = document.getElementById('dateInput').value; // YYYY-MM-DD
              const t = document.getElementById('timeInput').value; // HH:MM
              if (!d || !t) return null;
              // Build ISO with Z (UTC). For demo simplicity.
              return `${d}T${t}:00Z`;
            }
            async function chatSend(textOverride){
              const userId = document.getElementById('userId').value;
              const input = document.getElementById('chatInput');
              const raw = textOverride !== undefined ? textOverride : input.value;
              const text = (raw || '').trim();
              if(!text) return;
              window._chat.messages.push({role:'user', text});
              input.value = '';
              renderChat();
              const ts = buildTs();
              const body = {user_id:userId, messages: window._chat.messages, fields: window._chat.fields, pathway:'abdominal_pain'};
              if (ts) body.ts = ts;
              const r = await fetch('/diary/chat/step', { method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify(body)});
              const j = await r.json();
              window._chat.fields = j.fields || {};
              window._chat.ready = !!j.ready;
              if (j.clarifiers && j.clarifiers.length){
                const q = j.clarifiers[0].question;
                window._chat.messages.push({role:'assistant', text: q});
                speak(q);
              }
              if (j.saved_id){
                const savedMsg = (window._langMode === 'CHINESE')
                  ? '谢谢您的分享，我已经为您保存好了。祝您早日好起来。'
                  : 'Thanks for sharing. I’ve saved this for you. I hope you feel better soon.';
                window._chat.messages.push({role:'assistant', text: savedMsg});
                speak(savedMsg);
              }
              renderChat();
              document.getElementById('diaryOut').innerText = JSON.stringify({fields: window._chat.fields, ready: window._chat.ready}, null, 2);
            }

            async function getRecs(){
              const userId = document.getElementById('userId').value;
              const r = await fetch(`/recommendations?user_id=${encodeURIComponent(userId)}&window_days=30&label=abdominal%20pain`);
              const j = await r.json();
              document.getElementById('recsOut').innerText = JSON.stringify(j, null, 2);
              const spoken = Array.isArray(j.suggestions) ? j.suggestions.map(s => (s && s.text) ? s.text : (typeof s === 'string' ? s : '')).filter(Boolean).join('. ') : '';
              if(spoken) speak(spoken);
            }

            async function doctorPack(){
              const userId = document.getElementById('userId').value;
              const r = await fetch('/doctor-pack', { method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({user_id: userId, window_days: 30, format: 'pdf'}) });
              const j = await r.json();
              const div = document.getElementById('packLinks');
              div.innerHTML = `<p>Pack: <a href="${j.pdf_uri}" target="_blank">Open</a></p><p>Share: <code>/shares/${j.share_token}</code> (<a href="/shares/${j.share_token}" target="_blank">Open</a>)</p>`;
            }

            async function transcribe(){
              const userId = document.getElementById('userId').value;
              const audioUri = document.getElementById('audioUri').value.trim();
              if(!audioUri){
                alert('Provide an audio URI or use the recorder.');
                return;
              }
              const fd = new FormData();
              fd.append('user_id', userId);
              fd.append('lang', window._langCode || 'en');
              fd.append('audio_uri', audioUri);
              setVisitSummary("(processing audio...)");
              const r = await fetch('/visit/transcribe', { method:'POST', body: fd});
              const j = await r.json();
              handleVisitTranscript(j);
            }

            function setVisitSummary(text){
              document.getElementById('sumOut').innerText = text || '(no summary yet)';
            }

            function handleVisitTranscript(payload){
              if(!payload || payload.detail){
                setVisitSummary(payload?.detail || 'Unable to transcribe audio.');
                return;
              }
              window._visitState.transcript = payload.transcript || '';
              window._visitState.spans = payload.spans || [];
              const transcriptBox = document.getElementById('transOut');
              transcriptBox.textContent = payload.transcript || '(no transcript text)';
              transcriptBox.style.display = 'none';
              window._visitState.showTranscript = false;
              const toggle = document.getElementById('transcriptToggle');
              toggle.style.display = 'inline-flex';
              toggle.textContent = 'Show full transcript';
              summarizeVisit();
            }

            async function summarizeVisit(){
              if(!window._visitState.transcript){
                setVisitSummary('No transcript captured yet.');
                return;
              }
              const userId = document.getElementById('userId').value;
              const body = {
                user_id: userId,
                transcript: window._visitState.transcript,
                spans: window._visitState.spans,
                lang: 'en'
              };
              setVisitSummary('(summarizing instructions...)');
              try{
                const r = await fetch('/visit/summary', { method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify(body)});
                const data = await r.json();
                if(data.detail){
                  setVisitSummary(data.detail);
                  return;
                }
                window._visitState.summary = data;
                setVisitSummary(data.summary_md || JSON.stringify(data, null, 2));
              }catch(err){
                console.error('Summary error', err);
                setVisitSummary('Unable to summarize audio.');
              }
            }

            function toggleTranscript(){
              const box = document.getElementById('transOut');
              const btn = document.getElementById('transcriptToggle');
              if(!box || !btn || !window._visitState.transcript){
                alert('No transcript available yet.');
                return;
              }
              const show = !window._visitState.showTranscript;
              box.style.display = show ? 'block' : 'none';
              btn.textContent = show ? 'Hide transcript' : 'Show full transcript';
              window._visitState.showTranscript = show;
            }

            function updateRecordStatus(text){
              const el = document.getElementById('recordStatus');
              if(el) el.textContent = text;
            }

            function resetVisitView(){
              window._visitState.transcript = '';
              window._visitState.spans = [];
              window._visitState.summary = null;
              window._visitState.showTranscript = false;
              document.getElementById('transOut').style.display = 'none';
              document.getElementById('transOut').textContent = '';
              const toggle = document.getElementById('transcriptToggle');
              toggle.style.display = 'none';
              toggle.textContent = 'Show full transcript';
              setVisitSummary('(no summary yet)');
            }

            async function startRecording(){
              if(!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia || typeof MediaRecorder === 'undefined'){
                alert('Recording not supported in this browser. Please use the latest Chrome or Edge desktop.');
                return;
              }
              try{
                const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
                const mimeType = MediaRecorder.isTypeSupported('audio/webm;codecs=opus') ? 'audio/webm;codecs=opus' : undefined;
                const recorder = new MediaRecorder(stream, mimeType ? { mimeType } : undefined);
                window._visitState.stream = stream;
                window._visitState.recorder = recorder;
                window._visitState.chunks = [];
                recorder.ondataavailable = (event) => {
                  if(event.data && event.data.size > 0){
                    window._visitState.chunks.push(event.data);
                  }
                };
                recorder.onstop = () => {
                  stream.getTracks().forEach(track => track.stop());
                  const blob = new Blob(window._visitState.chunks, { type: recorder.mimeType || 'audio/webm' });
                  window._visitState.chunks = [];
                  window._visitState.recordedBlob = blob;
                  // Show download button instead of auto-upload
                  document.getElementById('downloadBtn').style.display = 'inline-block';
                  document.getElementById('downloadBtn').disabled = false;
                  updateRecordStatus('Recording stopped. Download or upload the audio for transcription.');
                };
                recorder.start();
                document.getElementById('recordBtn').disabled = true;
                document.getElementById('stopRecordBtn').disabled = false;
                updateRecordStatus('Recording in progress... speak normally.');
              }catch(err){
                console.error('Recorder error', err);
                alert('Unable to access microphone. Please check permissions.');
                updateRecordStatus('Microphone access denied');
              }
            }

            function stopRecording(){
              const recorder = window._visitState.recorder;
              if(recorder && recorder.state !== 'inactive'){
                recorder.stop();
              }
              if(window._visitState.stream){
                window._visitState.stream.getTracks().forEach(track => track.stop());
              }
              document.getElementById('recordBtn').disabled = false;
              document.getElementById('stopRecordBtn').disabled = true;
              updateRecordStatus('Recording stopped. Download or upload the audio for transcription.');
            }

            function downloadRecording(){
              const blob = window._visitState.recordedBlob;
              if(!blob){
                alert('No audio recorded yet.');
                return;
              }
              const url = URL.createObjectURL(blob);
              const a = document.createElement('a');
              a.href = url;
              a.download = `visit-recording-${new Date().toISOString().replace(/[:.]/g, '-')}.webm`;
              document.body.appendChild(a);
              a.click();
              document.body.removeChild(a);
              URL.revokeObjectURL(url);
              updateRecordStatus('Audio downloaded. You can upload it for transcription.');
            }

            function handleAudioFileUpload(event){
              const file = event.target.files?.[0];
              if(!file){
                return;
              }
              const mime = file.type || '';
              if(mime && !(mime.startsWith('audio/') || mime.startsWith('video/'))){
                alert('Please select an audio or video file.');
                return;
              }
              uploadVisitBlob(file);
              // Reset input
              event.target.value = '';
            }

            function uploadRecording(){
              if(window._visitState.recordedBlob){
                uploadVisitBlob(window._visitState.recordedBlob);
                return;
              }
              document.getElementById('audioFileInput').click();
            }

            async function uploadVisitBlob(blob){
              // Check if blob has actual audio data
              if(!blob || blob.size === 0){
                setVisitSummary('No audio recorded. Please record some audio first.');
                updateRecordStatus('No audio data');
                return;
              }
              // Check if blob is too small (likely empty or just silence)
              if(blob.size < 100){
                setVisitSummary('Audio too short or empty. Please record at least a few seconds of audio.');
                updateRecordStatus('Audio too short');
                return;
              }
              const userId = document.getElementById('userId').value;
              const fd = new FormData();
              fd.append('user_id', userId);
              fd.append('lang', window._langCode || 'en');
              fd.append('audio', blob, 'visit.webm');
              setVisitSummary('(processing audio...)');
              try{
                const resp = await fetch('/visit/transcribe', { method:'POST', body: fd});
                const data = await resp.json();
                if(!resp.ok){
                  const detail = data.detail || data.message || 'Transcription failed';
                  throw new Error(detail);
                }
                handleVisitTranscript(data);
                updateRecordStatus('Microphone idle');
              }catch(err){
                console.error('Upload error', err);
                let errorMsg = 'Unable to process audio.';
                if(err.message){
                  errorMsg = err.message;
                }else if(typeof err === 'string'){
                  errorMsg = err;
                }
                setVisitSummary('Error: ' + errorMsg);
                updateRecordStatus('Recording failed: ' + errorMsg);
              }finally{
                document.getElementById('recordBtn').disabled = false;
                document.getElementById('stopRecordBtn').disabled = true;
                // Clear recorded blob after upload
                window._visitState.recordedBlob = null;
                document.getElementById('downloadBtn').style.display = 'none';
                document.getElementById('downloadBtn').disabled = true;
              }
            }

            // Voice input helpers (browser speech recognition)
            window._voice = {
              supported: ('SpeechRecognition' in window) || ('webkitSpeechRecognition' in window),
              recognizer: null,
              active: false
            };
            function updateVoiceUI(active, text){
              const btn = document.getElementById('voiceBtn');
              const label = document.getElementById('voiceLabel');
              const icon = document.getElementById('voiceIcon');
              if(!btn || !label || !icon) return;
              if(!window._voice.supported){
                label.textContent = 'Voice not supported';
                icon.textContent = '⚠️';
                btn.disabled = true;
                return;
              }
              if(active){
                label.textContent = text || 'Listening...';
                icon.textContent = '🔴';
                btn.style.background = '#fde68a';
                btn.style.color = '#7c2d12';
              }else{
                label.textContent = text || 'Voice Input';
                icon.textContent = '🎙️';
                btn.style.background = '';
                btn.style.color = '';
              }
            }
            function initSpeechRecognizer(){
              if(!window._voice.supported) return null;
              if(window._voice.recognizer) return window._voice.recognizer;
              const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
              const rec = new SR();
              rec.lang = (window._langCode === 'zh') ? 'zh-CN' : 'en-US';
              rec.interimResults = false;
              rec.maxAlternatives = 1;
              rec.onresult = (event) => {
                const transcript = event.results?.[0]?.[0]?.transcript || '';
                if(transcript){
                  document.getElementById('chatInput').value = transcript;
                  chatSend(transcript);
                }
              };
              rec.onerror = (event) => {
                console.error('Voice error', event);
                updateVoiceUI(false, 'Try again');
                alert('Voice capture error: ' + (event.error || 'unknown'));
              };
              rec.onend = () => {
                window._voice.active = false;
                updateVoiceUI(false);
              };
              window._voice.recognizer = rec;
              return rec;
            }
            function toggleVoice(){
              if(!window._voice.supported){
                alert('Voice input not supported in this browser. Please use the latest Chrome or Edge on desktop.');
                updateVoiceUI(false, 'Not supported');
                return;
              }
              const rec = initSpeechRecognizer();
              if(!rec) return;
              if(window._voice.active){
                rec.stop();
                window._voice.active = false;
                updateVoiceUI(false);
                return;
              }
              try{
                rec.start();
                window._voice.active = true;
                updateVoiceUI(true);
              }catch(err){
                console.error('Unable to start voice', err);
                alert('Unable to access microphone. Please check browser permissions.');
                updateVoiceUI(false, 'Unavailable');
              }
            }
            // Initialize button state on load
            updateVoiceUI(false);
            updateTtsUI();
            loadLanguageMode();
            resetVisitView();
          </script>
          </main>
        </body>
        </html>
        """
    )


