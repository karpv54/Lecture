const shell = element.querySelector(".voice-app");
const button = element.querySelector(".conversation-button");
const caption = element.querySelector(".button-caption");
const status = element.querySelector(".voice-status");
let current = null;
const lessonStage = element.querySelector(".lesson-stage");
const tiles = element.querySelector(".teaching-tiles");
const picture = element.querySelector(".meaning-picture");
function showVisual(message) {
  const values = Array.isArray(message.tiles) ? message.tiles : [];
  tiles.replaceChildren();
  const pending = [];
  values.forEach((value, index) => {
    if (typeof value !== "string" || !value || value.length > 48) throw new Error("audio");
    if (index) { const dash = document.createElement("span"); dash.className = "tile-dash"; dash.textContent = "–"; dash.setAttribute("aria-hidden", "true"); tiles.append(dash); }
    const tile = document.createElement("img");
    tile.src = "/voice/tile.svg?text=" + encodeURIComponent(value);
    tile.alt = value; tile.draggable = false;
    pending.push(new Promise((resolve, reject) => {
      tile.onload = resolve;
      tile.onerror = () => reject(new Error("visual"));
    }));
    tiles.append(tile);
  });
  lessonStage.hidden = !values.length;
  shell.classList.toggle("has-lesson", !!values.length);
  picture.textContent = typeof message.emoji === "string" ? message.emoji : "";
  picture.hidden = !picture.textContent;
  element.querySelector(".lesson-label").textContent = message.label || "Un pas à la fois";
  return Promise.all(pending);
}

const messages = {
  idle: "Appuyez sur le micro pour commencer.",
  connecting: "La conversation se prépare…",
  thinking: "Un instant…",
  listening: "Je vous écoute. Prenez votre temps.",
  speaking: "Écoutez, puis ce sera à vous.",
};
const errors = {
  busy: "Une conversation est déjà ouverte sur cet appareil. Terminez-la avant de reprendre.",
  storage: "Vos progrès n’ont pas pu être gardés. Demandez à votre accompagnant.",
  lesson_review: "Cette activité demande une vérification. Demandez à votre accompagnant.",
  visual: "Le support de lecture n’a pas pu s’afficher. Nous pouvons réessayer.",
  gradium: "Le son s’est interrompu. Nous pouvons réessayer.",
  gradium_access: "La conversation n’est pas encore prête. Demandez à votre accompagnant.",
  provider_limit: "La conversation est momentanément indisponible. Demandez à votre accompagnant.",
  dust_reply: "Je n’ai pas pu préparer la suite. Nous pouvons réessayer.",
  setup: "La conversation n’est pas encore disponible. Demandez à votre accompagnant.",
  dust_limit: "La conversation est momentanément indisponible. Demandez à votre accompagnant.",
  dust_access: "La conversation n’est pas encore prête. Demandez à votre accompagnant.",
  reply_format: "Je n’ai pas pu préparer ma réponse. Nous pouvons réessayer.",
  microphone: "Autorisez le microphone pour que nous puissions nous parler.",
  timeout: "On fait une pause. Appuyez sur le micro pour recommencer.",
  session_end: "On fait une pause. Appuyez sur le micro pour recommencer.",
  audio: "Le son n’est pas disponible. Vérifiez votre microphone et le volume.",
  connection: "La connexion s’est interrompue. Nous pouvons réessayer.",
};

function setState(state, text) {
  shell.dataset.state = state;
  const active = !!current;
  button.setAttribute("aria-pressed", String(active));
  button.setAttribute("aria-label", active ? "Arrêter la conversation" : "Commencer la conversation");
  caption.textContent = active ? "Arrêter" : state === "error" ? "Réessayer" : "Commencer";
  status.textContent = text || messages[state] || messages.idle;
}

function capture(session, enabled) {
  session.listening = enabled;
  session.node?.port.postMessage({ enabled });
  session.media?.getAudioTracks().forEach(track => { track.enabled = enabled; });
  if (!enabled) shell.style.setProperty("--level", "0");
}

function stop(text, error = false) {
  const session = current;
  current = null;
  if (session) {
    session.abort.abort();
    clearTimeout(session.playbackTimer);
    clearTimeout(session.connectTimer);
    clearInterval(session.heartbeat);
    clearTimeout(session.fetchTimer);
    capture(session, false);
    if (session.socket?.readyState === WebSocket.OPEN) {
      session.socket.send(JSON.stringify({ type: "stop" }));
    }
    session.socket?.close();
    session.media?.getTracks().forEach(track => track.stop());
    session.source?.disconnect();
    session.node?.disconnect();
    session.silence?.disconnect();
    for (const source of session.playing) {
      try { source.stop(); } catch (_) { /* Already finished. */ }
    }
    session.playing.clear();
    if (session.context) session.context.close().catch(() => {});
  }
  showVisual({tiles: []});
  setState(error ? "error" : "idle", text);
}

function fail(session, code) {
  if (current === session) stop(errors[code] || errors.connection, true);
}

function playChunk(session, bytes) {
  if (current !== session || session.speechId === null) return;
  if (bytes.byteLength % 2 !== 0 || session.context.state !== "running") {
    throw new Error("audio");
  }
  const pcm = new DataView(bytes);
  const frames = bytes.byteLength / 2;
  if (!frames) return;
  const buffer = session.context.createBuffer(1, frames, session.outputRate);
  const samples = buffer.getChannelData(0);
  for (let i = 0; i < frames; i++) samples[i] = pcm.getInt16(i * 2, true) / 32768;
  const source = session.context.createBufferSource();
  source.buffer = buffer;
  source.connect(session.context.destination);
  session.nextAudio = Math.max(session.nextAudio, session.context.currentTime + 0.04);
  source.start(session.nextAudio);
  session.nextAudio += buffer.duration;
  session.playing.add(source);
  source.onended = () => { source.disconnect(); session.playing.delete(source); };
  setState("speaking");
}

function acknowledgePlayback(session, id) {
  if (current !== session || session.speechId !== id) return;
  if (session.context.state !== "running") { fail(session, "audio"); return; }
  const remaining = session.nextAudio - session.context.currentTime;
  if (remaining > 0.01 || session.playing.size) {
    session.playbackTimer = setTimeout(() => acknowledgePlayback(session, id), Math.max(30, remaining * 1000 + 30));
    return;
  }
  if (session.socket.readyState === WebSocket.OPEN) {
    session.socket.send(JSON.stringify({ type: "playback_done", id }));
    session.speechId = null;
    setState("thinking");
  }
}

async function start() {
  if (current) { stop("La conversation est arrêtée. À bientôt."); return; }
  const session = {
    abort: new AbortController(), context: null, media: null, node: null,
    socket: null, playing: new Set(), listening: false,
    nextAudio: 0, outputRate: 48000, speechId: null,
  };
  current = session;
  setState("connecting");
  try {
    // Unlock playback from the user's click, before any asynchronous provider work.
    const AudioEngine = window.AudioContext || window.webkitAudioContext;
    if (!AudioEngine || !navigator.mediaDevices?.getUserMedia) throw new Error("audio");
    try { session.context = new AudioEngine({ sampleRate: 24000 }); }
    catch (_) { session.context = new AudioEngine(); }
    await session.context.resume();
    if (current !== session) return;
    // The worklet resamples device audio to Gradium's 24 kHz input format.
    session.fetchTimer = setTimeout(() => fail(session, "connection"), 12000);
    const response = await fetch("/voice/config", { signal: session.abort.signal, cache: "no-store" });
    if (!response.ok) throw new Error("connection");
    const config = await response.json();
    clearTimeout(session.fetchTimer);
    if (current !== session) return;
    if (!config.ready) { fail(session, "setup"); return; }
    const media = await navigator.mediaDevices.getUserMedia({
      audio: { channelCount: 1, echoCancellation: true, noiseSuppression: true, autoGainControl: true },
      video: false,
    });
    if (current !== session) { media.getTracks().forEach(track => track.stop()); return; }
    session.media = media;
    media.getAudioTracks().forEach(track => { track.enabled = false; track.onended = () => fail(session, "audio"); });
    await session.context.audioWorklet.addModule("/voice/capture.js");
    if (current !== session) return;
    session.source = session.context.createMediaStreamSource(media);
    session.node = new AudioWorkletNode(session.context, "tutor-capture");
    session.silence = session.context.createGain();
    session.silence.gain.value = 0;
    session.source.connect(session.node);
    session.node.connect(session.silence);
    session.silence.connect(session.context.destination);
    session.node.onprocessorerror = () => fail(session, "audio");
    const protocol = location.protocol === "https:" ? "wss:" : "ws:";
    session.socket = new WebSocket(protocol + "//" + location.host + "/voice/session");
    session.socket.binaryType = "arraybuffer";
    session.connectTimer = setTimeout(() => fail(session, "connection"), 15000);
    session.socket.onopen = () => {
      if (current !== session) { session.socket.close(); return; }
      clearTimeout(session.connectTimer);
      session.lastPong = Date.now();
      session.heartbeat = setInterval(() => {
        if (Date.now() - session.lastPong > 35000) { fail(session, "connection"); return; }
        if (session.socket.readyState === WebSocket.OPEN) session.socket.send(JSON.stringify({type: "ping"}));
      }, 10000);
    };
    session.node.port.onmessage = ({ data }) => {
      if (current !== session || !session.listening || session.socket.readyState !== WebSocket.OPEN) return;
      if (session.socket.bufferedAmount > 192000) { fail(session, "connection"); return; }
      shell.style.setProperty("--level", String(Math.min(1, data.level * 10)));
      session.socket.send(data.buffer);
    };
    session.socket.onmessage = ({ data }) => {
      if (current !== session) return;
      try {
        if (data instanceof ArrayBuffer) { playChunk(session, data); return; }
        const message = JSON.parse(data);
        if (message.type === "pong") { session.lastPong = Date.now(); return; }
        if (message.type === "visual") {
          showVisual(message).then(() => {
            if (current === session && session.socket.readyState === WebSocket.OPEN) session.socket.send(JSON.stringify({type: "visual_ready", id: message.id}));
          }).catch(() => fail(session, "visual"));
          return;
        }
        if (message.type === "state") {
          capture(session, message.state === "listening");
          setState(message.state);
        } else if (message.type === "speech_start") {
          capture(session, false);
          session.speechId = message.id;
          if (!Number.isInteger(message.sample_rate) || message.sample_rate < 8000 || message.sample_rate > 96000) throw new Error("audio");
          session.outputRate = message.sample_rate;
          session.nextAudio = session.context.currentTime;
          setState("thinking");
        } else if (message.type === "speech_end") {
          acknowledgePlayback(session, message.id);
        } else if (message.type === "error") {
          fail(session, message.code);
        } else if (message.type === "finished") {
          stop("La conversation est arrêtée. À bientôt.");
        }
      } catch (_) {
        if (session.socket.readyState === WebSocket.OPEN) session.socket.send(JSON.stringify({ type: "playback_failed" }));
        fail(session, "audio");
      }
    };
    session.socket.onerror = () => fail(session, "connection");
    session.socket.onclose = () => { if (current === session) fail(session, "connection"); };
  } catch (error) {
    if (current !== session) return;
    if (error.name === "NotAllowedError" || error.name === "PermissionDeniedError") fail(session, "microphone");
    else fail(session, errors[error.message] ? error.message : "audio");
  }
}

button.addEventListener("click", start);
// Gradio may remove a component during navigation. Release its media immediately.
const removalObserver = new MutationObserver(() => {
  if (!element.isConnected) { if (current) stop(); removalObserver.disconnect(); }
});
removalObserver.observe(document.body, {childList: true, subtree: true});
window.addEventListener("pagehide", () => { if (current) stop(); });
setState("idle");
