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
              <h1 id="titleText">HealthDiary MVP Demo / 健康日记示例</h1>
              <p id="subtitleText">Interactive symptom intake, detailed recommendations, and patient-ready visit preparation. / 记录症状、获取建议、就诊准备。</p>
            </div>
          </header>
          <main>
          <div class="row">
            <div class="col">
              <div class="card">
                <h3 id="card1Title">1) Symptom Entry / 症状记录 (LLM chat → single saved entry)</h3>
                <label>User ID / 用户 ID</label>
                <input id="userId" value="demo-user-1"/>
                <div style="display:flex; gap:8px;">
                  <div style="flex:1;">
                    <label>Date (YYYY-MM-DD) / 日期</label>
                    <input id="dateInput" type="date" />
                  </div>
                  <div style="flex:1;">
                    <label>Time (24h, HH:MM) / 時間</label>
                    <input id="timeInput" type="time" />
                  </div>
                </div>
                <div id="chatBox" style="height:200px; overflow:auto; margin:10px 0;"></div>
                <input id="chatInput" placeholder="Describe your symptom / 描述症状（中英文皆可）" />
                <div style="display:flex; gap:8px; margin:8px 0; flex-wrap:wrap;">
                  <button onclick="chatSend()">Send / 发送</button>
                  <button class="secondary" onclick="chatReset()">Reset / 重置</button>
                  <button class="secondary" id="backendAsrBtn" onclick="toggleSymptomBackendAsr()" title="Record then transcribe (Qwen3-ASR-Flash, auto language)">
                    <span id="backendAsrIcon">🎤</span><span id="backendAsrLabel">Voice Input / 语音输入</span>
                  </button>
                  <button class="secondary" id="ttsBtn" onclick="toggleTts()">🔊 Voice On / 语音朗读</button>
                </div>
                <small>Tip: Reply follows your language. Type or use voice (auto-detects). / 回复与您同语言，可打字或语音。</small>
                <pre id="diaryOut"></pre>
              </div>

              <div class="card">
                <h3 id="card2Title">2) GET /recommendations / 获取建议</h3>
                <div style="display:flex; gap:8px; flex-wrap:wrap; margin-bottom:8px;">
                  <button onclick="getRecs()">Fetch Recommendations / 获取建议</button>
                  <button class="secondary" id="recsSpeakBtn" onclick="toggleRecsSpeech()" disabled>🔊 Play (EN) / 朗读（英文）</button>
                </div>
                <pre id="recsOut"></pre>
              </div>

              <div class="card">
                <h3 id="card3Title">3) POST /doctor-pack / 就诊摘要</h3>
                <button onclick="doctorPack()">Generate Doctor Pack / 生成就诊摘要</button>
                <div id="packLinks"></div>
              </div>
            </div>

            <div class="col">
              <div class="card">
                <h3 id="card4Title">4) Visit Capture / 门诊录音 (record + summary)</h3>
                <div class="record-status" id="recordStatus">Microphone idle / 麦克风闲置</div>
                <div style="display:flex; gap:8px; flex-wrap:wrap; margin-bottom:12px;">
                  <button id="recordBtn" onclick="startRecording()">Start Recording / 开始录音</button>
                  <button class="secondary" id="stopRecordBtn" onclick="stopRecording()" disabled>Stop Recording / 停止</button>
                  <button class="secondary" id="downloadBtn" onclick="downloadRecording()" disabled style="display:none;">Download Audio / 下载</button>
                  <button class="secondary" id="uploadBtn" onclick="uploadRecording()">Upload / Select Audio / 上传音频</button>
                  <input type="file" id="audioFileInput" accept="audio/*" style="display:none;" onchange="handleAudioFileUpload(event)">
                </div>
                <small>Chrome / Edge. Record then upload for transcription. / 录音后上传转写。</small>
                <div style="margin-top:18px;">
                  <h4 style="margin:0 0 8px; font-size:16px; color:#0f172a;">Doctor instructions summary / 医师嘱托摘要</h4>
                  <pre id="sumOut">(no summary yet / 尚无摘要)</pre>
                  <button class="secondary" id="transcriptToggle" style="display:none; margin-top:8px;" onclick="toggleTranscript()">Show full transcript / 显示全文</button>
                  <pre id="transOut" style="display:none; margin-top:10px;"></pre>
                </div>
              </div>

              <div class="card">
                <h3 id="card5Title">5) Meal Recording / 饮食记录</h3>
                <label for="mealInput">Describe what you ate / 描述饮食：</label>
                <textarea id="mealInput" rows="3" placeholder="e.g. This morning I had oatmeal... / 例如：早上吃了燕麥..."></textarea>
                <div style="margin-top:8px; display:flex; gap:8px; flex-wrap:wrap;">
                <button onclick="logMeal()">Save Meal / 保存</button>
                  <button class="secondary" id="mealBackendAsrBtn" onclick="toggleMealBackendAsr()" title="Record then transcribe (Qwen3-ASR-Flash)">
                    <span id="mealBackendAsrIcon">🎤</span><span id="mealBackendAsrLabel">Voice Input / 语音输入</span>
                  </button>
                </div>
                <div style="margin-top:8px; display:flex; gap:8px; flex-wrap:wrap;">
                  <button class="secondary" onclick="analyzeMeals()">Analyze last 30 days / 分析近30天</button>
                  <button class="secondary" id="mealSpeakBtn" onclick="toggleMealSpeech()" disabled>🔊 Play (EN) / 朗读（英文）</button>
                </div>
                <small>Voice uses Qwen3-ASR-Flash, auto-detects. Play reads in English. / 语音自动辨识；朗读为英文。</small>
                <pre id="mealOut"></pre>
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
            // Last recommendations text for manual playback
            window._recsSpeech = { text: '', active: false };
            // Last meal analysis text for manual playback
            window._mealSpeech = { text: '', active: false };
            // Visit capture state
            window._visitState = { recorder:null, chunks:[], stream:null, transcript:'', spans:[], summary:null, showTranscript:false, recordedBlob:null };
            // Meal recording state (simple)
            window._mealState = { recorder:null, chunks:[], stream:null, recordedBlob:null };
            // Default lang for visit transcribe etc. (UI is bilingual; chat uses reply_lang from backend)
            window._langCode = 'en';
            function updateTtsUI(){
              const btn = document.getElementById('ttsBtn');
              if(!btn) return;
              if(!window._tts.supported){
                btn.textContent = '🔈 Voice not supported / 不支持';
                btn.disabled = true;
                btn.style.opacity = 0.6;
                return;
              }
              btn.textContent = window._tts.enabled ? '🔊 Voice On / 语音朗读' : '🔇 Voice Off / 关闭';
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
            function speak(text, lang){
              if(!text || !window._tts.supported || !window._tts.enabled) return;
              try{
                const utter = new SpeechSynthesisUtterance(text);
                utter.lang = (lang === 'zh') ? 'zh-CN' : 'en-US';
                utter.rate = 1;
                window.speechSynthesis.cancel();
                window.speechSynthesis.speak(utter);
              }catch(err){
                console.warn('TTS error', err);
              }
            }
            function renderChat(){
              const box = document.getElementById('chatBox');
              box.innerHTML = window._chat.messages.map(m => `<div><b>${m.role}:<\\/b> ${m.text}<\\/div>`).join('');
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
              if (window._lastChatLang) body.lang = window._lastChatLang;
              const prevLang = window._lastChatLang;
              window._lastChatLang = null;
              const r = await fetch('/diary/chat/step', { method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify(body)});
              const j = await r.json();
              window._chat.fields = j.fields || {};
              window._chat.ready = !!j.ready;
              const replyLang = j.reply_lang || prevLang || 'en';
              if (j.clarifiers && j.clarifiers.length){
                const q = j.clarifiers[0].question;
                window._chat.messages.push({role:'assistant', text: q});
                speak(q, replyLang);
              }
              if (j.saved_id){
                const savedMsg = j.saved_message || "Thanks for sharing. I've saved this for you. I hope you feel better soon.";
                window._chat.messages.push({role:'assistant', text: savedMsg});
                speak(savedMsg, replyLang);
              }
              renderChat();
              document.getElementById('diaryOut').innerText = JSON.stringify({fields: window._chat.fields, ready: window._chat.ready}, null, 2);
            }

            async function getRecs(){
              const userId = document.getElementById('userId').value;
              // Prefer last explicit lang, otherwise infer from latest user chat message.
              let recLang = (window._lastChatLang === 'zh') ? 'zh' : 'en';
              try{
                const msgs = (window._chat && Array.isArray(window._chat.messages)) ? window._chat.messages : [];
                const latestUser = [...msgs].reverse().find(m => m && m.role === 'user' && m.text);
                if(latestUser && /[\u4e00-\u9fff]/.test(latestUser.text)){
                  recLang = 'zh';
                }
              }catch(_e){}
              const r = await fetch(`/recommendations?user_id=${encodeURIComponent(userId)}&window_days=30&label=abdominal%20pain&lang=${encodeURIComponent(recLang)}`);
              const j = await r.json();
              document.getElementById('recsOut').innerText = JSON.stringify(j, null, 2);
              const spoken = Array.isArray(j.suggestions)
                ? j.suggestions.map(s => (s && s.text) ? s.text : (typeof s === 'string' ? s : '')).filter(Boolean).join('. ')
                : '';
              // Store for manual playback; do not auto-play
              window._recsSpeech.text = spoken;
              window._recsSpeech.active = false;
              const btn = document.getElementById('recsSpeakBtn');
              if(btn){
                const hasText = !!spoken;
                btn.disabled = !hasText || !window._tts.supported;
                btn.textContent = hasText ? '🔊 Play Recommendations' : '🔊 Play Recommendations';
              }
            }

            async function logMeal(){
              const userId = document.getElementById('userId').value;
              const text = (document.getElementById('mealInput').value || '').trim();
              const out = document.getElementById('mealOut');
              if(!text){
                alert('Please describe what you ate.');
                return;
              }
              out.innerText = '(saving meal...)';
              try{
                const res = await fetch('/meals/log', {
                  method:'POST',
                  headers:{'Content-Type':'application/json'},
                  body: JSON.stringify({user_id:userId, text})
                });
                const j = await res.json();
                if(!res.ok){
                  out.innerText = 'Error: ' + (j.detail || JSON.stringify(j));
                  return;
                }
                out.innerText = JSON.stringify(j, null, 2);
                document.getElementById('mealInput').value = '';
              }catch(e){
                console.error('Meal log error', e);
                out.innerText = 'Error: ' + e;
              }
            }

            async function analyzeMeals(){
              const userId = document.getElementById('userId').value;
              const out = document.getElementById('mealOut');
              out.innerText = '(analyzing meals...)';
              try{
                const res = await fetch(`/meals/summary?user_id=${encodeURIComponent(userId)}&window_days=30`);
                const j = await res.json();
                if(!res.ok){
                  out.innerText = 'Error: ' + (j.detail || JSON.stringify(j));
                  return;
                }
                out.innerText = JSON.stringify(j, null, 2);
                // Prepare text for optional TTS playback
                const analysis = j.analysis || {};
                const suggs = Array.isArray(analysis.suggestions) ? analysis.suggestions : [];
                const spoken = [analysis.summary || '']
                  .concat(suggs.map(s => (s && s.text) ? s.text : (typeof s === 'string' ? s : '')).filter(Boolean))
                  .filter(Boolean)
                  .join('. ');
                window._mealSpeech.text = spoken;
                window._mealSpeech.active = false;
                const btn = document.getElementById('mealSpeakBtn');
                if(btn){
                  const hasText = !!spoken;
                  btn.disabled = !hasText || !window._tts.supported;
                  btn.textContent = '🔊 Play Meal Analysis';
                }
              }catch(e){
                console.error('Meal analysis error', e);
                out.innerText = 'Error: ' + e;
              }
            }

            function toggleMealSpeech(){
              const btn = document.getElementById('mealSpeakBtn');
              if(!btn) return;
              const text = (window._mealSpeech && window._mealSpeech.text) || '';
              if(!text){
                alert('No meal analysis to read yet. Analyze meals first.');
                return;
              }
              if(!window._tts.supported){
                alert('Voice playback is not supported in this browser.');
                return;
              }
              if(window._mealSpeech.active){
                if(window.speechSynthesis){
                  window.speechSynthesis.cancel();
                }
                window._mealSpeech.active = false;
                btn.textContent = '🔊 Play Meal Analysis';
                return;
              }
              speak(text, 'en');
              window._mealSpeech.active = true;
              btn.textContent = '⏹ Stop Audio';
            }

            // Backend ASR (Qwen3-ASR-Flash) for meal voice
            window._mealBackendAsr = { recording: false, recorder: null, stream: null, chunks: [] };
            async function toggleMealBackendAsr(){
              const btn = document.getElementById('mealBackendAsrBtn');
              const label = document.getElementById('mealBackendAsrLabel');
              const icon = document.getElementById('mealBackendAsrIcon');
              const out = document.getElementById('mealOut');
              if(!btn || !label) return;
              if(window._mealBackendAsr.recording){
                const r = window._mealBackendAsr.recorder;
                if(r && r.state !== 'inactive') r.stop();
                window._mealBackendAsr.recording = false;
                if(window._mealBackendAsr.stream) window._mealBackendAsr.stream.getTracks().forEach(t => t.stop());
                window._mealBackendAsr.stream = null;
                label.textContent = 'Voice Input';
                icon.textContent = '🎤';
                btn.style.background = '';
                return;
              }
              if(!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia || typeof MediaRecorder === 'undefined'){
                if(out) out.innerText = 'Recording not supported in this browser.';
                return;
              }
              try{
                const stream = await navigator.mediaDevices.getUserMedia({audio: true});
                window._mealBackendAsr.stream = stream;
                window._mealBackendAsr.chunks = [];
                const mimeType = MediaRecorder.isTypeSupported('audio/webm;codecs=opus') ? 'audio/webm;codecs=opus' : undefined;
                const recorder = new MediaRecorder(stream, mimeType ? { mimeType } : undefined);
                window._mealBackendAsr.recorder = recorder;
                recorder.ondataavailable = (e) => { if(e.data && e.data.size > 0) window._mealBackendAsr.chunks.push(e.data); };
                recorder.onstop = async () => {
                  try{
                    const blob = new Blob(window._mealBackendAsr.chunks, { type: recorder.mimeType || 'audio/webm' });
                    window._mealBackendAsr.recorder = null;
                    if(out) out.innerText = 'Transcribing...';
                    label.textContent = 'Transcribing...';
                    const userId = document.getElementById('userId').value;
                    const fd = new FormData();
                    fd.append('user_id', userId);
                    fd.append('audio', blob, 'meal.webm');
                    const resp = await fetch('/diary/transcribe', { method: 'POST', body: fd });
                    const data = await resp.json();
                    if(!resp.ok){
                      if(out) out.innerText = 'Error: ' + (data.detail || resp.statusText);
                      alert('Transcription failed: ' + (data.detail || resp.statusText));
                      return;
                    }
                    const transcript = data.transcript || '';
                    const lang = data.language || '';
                    if(transcript){
                      document.getElementById('mealInput').value = transcript;
                      await logMeal();
                      if(out) out.innerText = 'Saved. Detected language: ' + (lang || 'unknown');
                      if(lang) console.log('Meal detected language:', lang);
                    }else{
                      if(out) out.innerText = 'No speech recognized. Try again.';
                      alert('No speech recognized. Try again.');
                    }
                  }catch(err){
                    console.error('Meal backend ASR error', err);
                    if(out) out.innerText = 'Error: ' + (err.message || err);
                    alert('Error: ' + (err.message || err));
                  }finally{
                    label.textContent = 'Voice Input';
                    icon.textContent = '🎤';
                    btn.style.background = '';
                  }
                };
                recorder.start();
                window._mealBackendAsr.recording = true;
                label.textContent = 'Stop & transcribe';
                icon.textContent = '⏹';
                btn.style.background = '#fde68a';
                btn.style.color = '#7c2d12';
                if(out) out.innerText = 'Recording... click Stop & transcribe when done.';
              }catch(err){
                console.error('Meal mic error', err);
                if(out) out.innerText = 'Could not access microphone.';
                alert('Could not access microphone: ' + (err.message || err));
              }
            }

            function toggleRecsSpeech(){
              const btn = document.getElementById('recsSpeakBtn');
              if(!btn) return;
              const text = (window._recsSpeech && window._recsSpeech.text) || '';
              if(!text){
                alert('No recommendations to read yet. Fetch recommendations first.');
                return;
              }
              if(!window._tts.supported){
                alert('Voice playback is not supported in this browser.');
                return;
              }
              // If currently speaking, stop
              if(window._recsSpeech.active){
                if(window.speechSynthesis){
                  window.speechSynthesis.cancel();
                }
                window._recsSpeech.active = false;
                btn.textContent = '🔊 Play Recommendations';
                return;
              }
              // Start speaking
              speak(text, 'en');
              window._recsSpeech.active = true;
              btn.textContent = '⏹ Stop Audio';
            }

            async function doctorPack(){
              const userId = document.getElementById('userId').value;
              const r = await fetch('/doctor-pack', { method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({user_id: userId, window_days: 30, format: 'pdf'}) });
              const j = await r.json();
              const div = document.getElementById('packLinks');
              div.innerHTML = `<p>Pack: <a href="${j.pdf_uri}" target="_blank">Open<\/a><\/p><p>Share: <code>\/shares\/${j.share_token}<\/code> (<a href="\/shares\/${j.share_token}" target="_blank">Open<\/a>)<\/p>`;
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
              const transOut = document.getElementById('transOut');
              const toggle = document.getElementById('transcriptToggle');
              if(transOut){ transOut.style.display = 'none'; transOut.textContent = ''; }
              if(toggle){ toggle.style.display = 'none'; toggle.textContent = 'Show full transcript'; }
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

            // Backend ASR (Qwen3-ASR-Flash) for symptom voice
            window._symptomBackendAsr = { recording: false, recorder: null, stream: null, chunks: [] };
            async function toggleSymptomBackendAsr(){
              const btn = document.getElementById('backendAsrBtn');
              const label = document.getElementById('backendAsrLabel');
              const icon = document.getElementById('backendAsrIcon');
              if(!btn || !label) return;
              if(window._symptomBackendAsr.recording){
                const r = window._symptomBackendAsr.recorder;
                if(r && r.state !== 'inactive') r.stop();
                window._symptomBackendAsr.recording = false;
                if(window._symptomBackendAsr.stream) window._symptomBackendAsr.stream.getTracks().forEach(t => t.stop());
                window._symptomBackendAsr.stream = null;
                label.textContent = 'Voice Input';
                icon.textContent = '🎤';
                btn.style.background = '';
                return;
              }
              if(!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia || typeof MediaRecorder === 'undefined'){
                alert('Recording not supported in this browser.');
                return;
              }
              try{
                const stream = await navigator.mediaDevices.getUserMedia({audio: true});
                window._symptomBackendAsr.stream = stream;
                window._symptomBackendAsr.chunks = [];
                const mimeType = MediaRecorder.isTypeSupported('audio/webm;codecs=opus') ? 'audio/webm;codecs=opus' : undefined;
                const recorder = new MediaRecorder(stream, mimeType ? { mimeType } : undefined);
                window._symptomBackendAsr.recorder = recorder;
                recorder.ondataavailable = (e) => { if(e.data && e.data.size > 0) window._symptomBackendAsr.chunks.push(e.data); };
                recorder.onstop = async () => {
                  try{
                    const blob = new Blob(window._symptomBackendAsr.chunks, { type: recorder.mimeType || 'audio/webm' });
                    window._symptomBackendAsr.recorder = null;
                    document.getElementById('backendAsrLabel').textContent = 'Transcribing...';
                    const userId = document.getElementById('userId').value;
                    const fd = new FormData();
                    fd.append('user_id', userId);
                    fd.append('audio', blob, 'symptom.webm');
                    const resp = await fetch('/diary/transcribe', { method: 'POST', body: fd });
                    const data = await resp.json();
                    if(!resp.ok){
                      alert('Transcription failed: ' + (data.detail || resp.statusText));
                      return;
                    }
                    const transcript = data.transcript || '';
                    const lang = data.language || '';
                    if(transcript){
                      document.getElementById('chatInput').value = transcript;
                      window._lastChatLang = (lang === 'zh' || lang === 'yue') ? 'zh' : (lang || 'en');
                      chatSend(transcript);
                      if(lang) console.log('Detected language:', lang);
                    }else{
                      alert('No speech recognized. Try again.');
                    }
                  }catch(err){
                    console.error('Backend ASR error', err);
                    alert('Error: ' + (err.message || err));
                  }finally{
                    document.getElementById('backendAsrLabel').textContent = 'Voice Input';
                    document.getElementById('backendAsrIcon').textContent = '🎤';
                    document.getElementById('backendAsrBtn').style.background = '';
                  }
                };
                recorder.start();
                window._symptomBackendAsr.recording = true;
                label.textContent = 'Stop & transcribe';
                icon.textContent = '⏹';
                btn.style.background = '#fde68a';
                btn.style.color = '#7c2d12';
              }catch(err){
                console.error('Mic error', err);
                alert('Could not access microphone: ' + (err.message || err));
              }
            }

            function setDefaultDateTime(){
              const now = new Date();
              const y = now.getFullYear();
              const m = String(now.getMonth() + 1).padStart(2, '0');
              const day = String(now.getDate()).padStart(2, '0');
              const h = String(now.getHours()).padStart(2, '0');
              const min = String(now.getMinutes()).padStart(2, '0');
              const dateEl = document.getElementById('dateInput');
              const timeEl = document.getElementById('timeInput');
              if(dateEl) dateEl.value = `${y}-${m}-${day}`;
              if(timeEl) timeEl.value = `${h}:${min}`;
            }

            // Initialize button state on load
            try {
              setDefaultDateTime();
              updateTtsUI();
              resetVisitView();
              console.log('HealthDiary demo script loaded');
            }catch(e){
              console.error('Demo init error:', e);
            }
          </script>
          </main>
        </body>
        </html>
        """
    )


