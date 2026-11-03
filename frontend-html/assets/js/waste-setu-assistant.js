(() => {
  if (window.__wasteSetuAssistantLoaded) return;
  window.__wasteSetuAssistantLoaded = true;

  const css = document.createElement('link');
  css.rel = 'stylesheet';
  const assistantScript = document.currentScript;
  css.href = assistantScript && assistantScript.src
    ? new URL('../css/waste-setu-assistant.css', assistantScript.src).href
    : new URL('../css/waste-setu-assistant.css', window.location.href).href;
  document.head.appendChild(css);

  const root = document.createElement('div');
  root.id = 'ws-ai-root';
  root.innerHTML = `
    <section id="ws-ai-panel" aria-label="Waste Setu AI assistant" aria-live="polite">
      <header class="ws-ai-head"><div><strong>Waste Setu Assistant</strong><small>Chat and voice support</small></div><button id="ws-ai-close" aria-label="Close">×</button></header>
      <div class="ws-ai-tools"><select id="ws-ai-language" aria-label="Voice language">
        <option value="en-IN">English</option><option value="hi-IN">हिन्दी</option><option value="mr-IN">मराठी</option><option value="gu-IN">ગુજરાતી</option><option value="bn-IN">বাংলা</option><option value="ta-IN">தமிழ்</option><option value="te-IN">తెలుగు</option><option value="kn-IN">ಕನ್ನಡ</option>
      </select><span id="ws-ai-status">Ready to help</span></div>
      <div id="ws-ai-messages"><div class="ws-ai-msg bot">Hello! I’m the Waste Setu assistant. Ask me about waste segregation, recycling, creating a household lot, or using this website.</div></div>
      <div class="ws-ai-compose"><textarea id="ws-ai-input" rows="1" maxlength="4000" placeholder="Type your message..."></textarea><button class="ws-ai-action" id="ws-ai-mic" title="Speak" aria-label="Speak">🎙</button><button class="ws-ai-action" id="ws-ai-speak" title="Read last reply aloud" aria-label="Read reply aloud">🔊</button><button class="ws-ai-action" id="ws-ai-send" title="Send" aria-label="Send">➤</button></div>
      <div class="ws-ai-foot">AI responses may be imperfect. Do not share passwords or OTPs.</div>
    </section>
    <button id="ws-ai-launch" aria-label="Open Waste Setu assistant" title="Waste Setu Assistant">✦</button>`;
  document.body.appendChild(root);

  const panel = root.querySelector('#ws-ai-panel');
  const launch = root.querySelector('#ws-ai-launch');
  const close = root.querySelector('#ws-ai-close');
  const input = root.querySelector('#ws-ai-input');
  const messagesEl = root.querySelector('#ws-ai-messages');
  const sendBtn = root.querySelector('#ws-ai-send');
  const micBtn = root.querySelector('#ws-ai-mic');
  const speakBtn = root.querySelector('#ws-ai-speak');
  const language = root.querySelector('#ws-ai-language');
  const status = root.querySelector('#ws-ai-status');
  const history = [];
  let lastReply = '';
  let recognition = null;

  const pageLang = (document.documentElement.lang || '').toLowerCase();
  const langMap = {'hi':'hi-IN','mr':'mr-IN','gu':'gu-IN','bn':'bn-IN','ta':'ta-IN','te':'te-IN','kn':'kn-IN'};
  if (langMap[pageLang]) language.value = langMap[pageLang];

  function addMessage(text, who) {
    const node = document.createElement('div');
    node.className = `ws-ai-msg ${who}`;
    node.textContent = text;
    messagesEl.appendChild(node);
    messagesEl.scrollTop = messagesEl.scrollHeight;
    return node;
  }
  function setBusy(busy, label) {
    sendBtn.disabled = busy;
    status.textContent = label || (busy ? 'Thinking…' : 'Ready to help');
  }
  function openPanel() { panel.classList.add('ws-open'); launch.style.display = 'none'; input.focus(); }
  function closePanel() { panel.classList.remove('ws-open'); launch.style.display = 'grid'; }
  launch.addEventListener('click', openPanel);
  close.addEventListener('click', closePanel);

  async function sendMessage(text) {
    const clean = text.trim();
    if (!clean) return;
    addMessage(clean, 'user');
    history.push({role:'user', content:clean});
    input.value = '';
    setBusy(true, 'Connecting to AI…');
    const typing = addMessage('Please wait…', 'bot');
    try {
      const response = await fetch('https://waste-setuu.onrender.com/api/assistant/chat', {
        method:'POST', headers:{'Content-Type':'application/json'},
        body:JSON.stringify({messages:history.slice(-12)})
      });
      const data = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(data.detail || `Request failed (${response.status})`);
      lastReply = data.reply || 'I could not prepare a response. Please try again.';
      typing.textContent = lastReply;
      history.push({role:'assistant', content:lastReply});
      status.textContent = 'Reply received';
    } catch (error) {
      typing.textContent = `Sorry, I couldn't connect: ${error.message}. Check that the FastAPI backend is running.`;
      status.textContent = 'Connection issue';
    } finally { setBusy(false); messagesEl.scrollTop = messagesEl.scrollHeight; }
  }
  sendBtn.addEventListener('click', () => sendMessage(input.value));
  input.addEventListener('keydown', event => {
    if (event.key === 'Enter' && !event.shiftKey) { event.preventDefault(); sendMessage(input.value); }
  });

  const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
  if (SpeechRecognition) {
    recognition = new SpeechRecognition();
    recognition.continuous = false;
    recognition.interimResults = false;
    recognition.onstart = () => { status.textContent = 'Listening…'; micBtn.textContent = '■'; };
    recognition.onresult = event => {
      const transcript = event.results[0][0].transcript;
      input.value = transcript;
      sendMessage(transcript);
    };
    recognition.onerror = event => { status.textContent = `Mic: ${event.error}`; };
    recognition.onend = () => { micBtn.textContent = '🎙'; if (status.textContent === 'Listening…') status.textContent = 'Ready to help'; };
    micBtn.addEventListener('click', () => {
      try { recognition.lang = language.value; recognition.start(); }
      catch (_) { status.textContent = 'Microphone is already active'; }
    });
  } else {
    micBtn.addEventListener('click', () => { status.textContent = 'Voice input is not supported in this browser. Try Chrome or Edge.'; });
  }
  speakBtn.addEventListener('click', () => {
    if (!lastReply) { status.textContent = 'No reply to read yet'; return; }
    if (!('speechSynthesis' in window)) { status.textContent = 'Voice output is not supported in this browser'; return; }
    window.speechSynthesis.cancel();
    const utterance = new SpeechSynthesisUtterance(lastReply);
    utterance.lang = language.value;
    window.speechSynthesis.speak(utterance);
  });
})();
