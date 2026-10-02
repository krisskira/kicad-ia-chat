"use strict";

const PROJECT_KEY = "kicad-ia-project";

function sessionKey(project) {
  return `kicad-ia-session:${project || sessionStorage.getItem(PROJECT_KEY) || ""}`;
}

function projectPath(status) {
  const caps = status && status.capabilities;
  return (caps && caps.project_path) || "";
}
const TOOL_LABELS = {
  inspect_context: "Leer el proyecto",
  search_parts: "Buscar en bibliotecas",
  search_lcsc: "Buscar en LCSC",
  import_lcsc: "Importar de LCSC",
  describe_part: "Leer símbolo",
  describe_footprint: "Leer huella",
  place_circuit: "Escribir esquemático",
  assign_footprint: "Asignar huella",
  sync_board: "Validar para la PCB",
  board_state: "Estado de la placa",
  move_footprints: "Mover huellas",
  list_models: "Modelos 3D",
  routing: "Ruteo",
  render_view: "Generar imagen",
  organize_layout: "Organizar por funciones",
  ipc_place_components: "Colocar (IPC)",
  autoroute_board: "Autorutear",
  ipc_validate_correct: "Validar IPC",
};
const VIEW_LABELS = {
  schematic: "Esquemático",
  pcb: "Placa, capas",
  pcb_3d: "Placa 3D, cara superior",
  pcb_3d_bottom: "Placa 3D, cara inferior",
  pcb_3d_iso: "Placa 3D, perspectiva",
};

const $ = (id) => document.getElementById(id);
const els = {
  messages: $("messages"),
  welcome: $("welcome"),
  input: $("input"),
  send: $("send"),
  form: $("composer"),
  hint: $("hint"),
  facts: $("facts"),
  notes: $("notes"),
  selection: $("selection"),
  selectionCount: $("selection-count"),
  project: $("project-name"),
  ws: $("ind-ws"),
  kicad: $("ind-kicad"),
  model: $("ind-model"),
  tokens: $("ind-tokens"),
  sessions: $("sessions"),
  sessionsEmpty: $("sessions-empty"),
  quickMenu: $("quick-menu"),
  quickActions: $("quick-actions"),
  side: $("side"),
  toasts: $("toasts"),
  lightbox: $("lightbox"),
  lightboxImg: $("lightbox-img"),
  lightboxOpen: $("lightbox-open"),
};

const state = {
  socket: null,
  connected: false,
  retry: 0,
  busy: false,
  llmReady: false,
  autorouteEnabled: false,
  turns: new Map(),
  typing: null,
  heartbeat: null,
  settingsLoaded: null,
  sessionId: "",
  projectKey: sessionStorage.getItem(PROJECT_KEY) || "",
};

// ---------- WebSocket ----------

function connect() {
  const scheme = location.protocol === "https:" ? "wss" : "ws";
  const session = sessionStorage.getItem(sessionKey()) || "";
  const socket = new WebSocket(`${scheme}://${location.host}/ws?session=${encodeURIComponent(session)}`);
  state.socket = socket;
  setPill(els.ws, "warn", "Conectando");

  socket.addEventListener("open", () => {
    state.connected = true;
    state.retry = 0;
    setPill(els.ws, "ok", "En vivo");
    clearInterval(state.heartbeat);
    state.heartbeat = setInterval(() => send({ type: "ping" }), 25000);
    refreshComposer();
  });
  socket.addEventListener("message", (event) => {
    let message;
    try {
      message = JSON.parse(event.data);
    } catch {
      return;
    }
    handle(message);
  });
  socket.addEventListener("close", () => {
    const wasConnected = state.connected;
    state.connected = false;
    clearInterval(state.heartbeat);
    setPill(els.ws, "bad", "Sin conexión");
    refreshComposer();
    if (wasConnected) toast("Se cortó la conexión con el servidor. Reintentando…", "bad");
    const delay = Math.min(8000, 500 * 2 ** state.retry++);
    setTimeout(connect, delay);
  });
}

function send(message) {
  if (!state.socket || state.socket.readyState !== WebSocket.OPEN) return false;
  state.socket.send(JSON.stringify(message));
  return true;
}

function handle(message) {
  switch (message.type) {
    case "hello":
      rememberProject(projectPath(message.status));
      sessionStorage.setItem(sessionKey(), message.session_id);
      state.sessionId = message.session_id;
      renderStatus(message.status);
      renderSelection(message.selection);
      renderSessions(message.sessions, message.session_id);
      if (message.history && message.history.length && !els.messages.querySelector(".msg")) {
        renderHistory(message.history);
      }
      setBusy(Boolean(message.busy));
      break;
    case "session.opened":
      rememberProject(projectPath(message.status));
      sessionStorage.setItem(sessionKey(), message.session_id);
      state.sessionId = message.session_id;
      clearMessages();
      renderSessions(message.sessions, message.session_id);
      if (message.history && message.history.length) renderHistory(message.history);
      setBusy(false);
      break;
    case "session.preview":
      showHistory(message);
      break;
    case "sessions":
      renderSessions(message.sessions, state.sessionId);
      break;
    case "status":
      renderStatus(message);
      noteProject(projectPath(message));
      break;
    case "selection":
      renderSelection(message);
      break;
    case "turn.started":
      setBusy(true);
      if (!document.querySelector(`[data-turn="${message.turn_id}"]`)) ensureTurn(message.turn_id);
      break;
    case "llm.round":
      showTyping();
      break;
    case "llm.usage":
      renderTokens(message.tokens);
      break;
    case "llm.text":
      hideTyping();
      addAssistant(message.text, message.turn_id);
      break;
    case "tool.started":
      hideTyping();
      stepStarted(message);
      break;
    case "tool.finished":
      stepFinished(message);
      break;
    case "turn.finished":
      finishTurn(message);
      break;
    case "turn.failed":
      hideTyping();
      addError(`El turno falló: ${message.error}`);
      setBusy(false);
      break;
    case "error":
      toast(message.error, "bad");
      break;
    case "pong":
      break;
    default:
      break;
  }
}

// ---------- Estado y selección ----------

function renderStatus(status) {
  if (!status) return;
  const caps = status.capabilities || {};
  state.llmReady = Boolean(status.llm_ready);
  state.autorouteEnabled = Boolean(status.autoroute_enabled);
  const connected = Boolean(caps.connected);
  const backend = caps.backend || "";
  if (connected) setPill(els.kicad, "ok", `KiCad ${caps.kicad_version || ""}`.trim());
  else if (backend === "fake") setPill(els.kicad, "warn", "Modo desarrollo");
  else setPill(els.kicad, "bad", "KiCad sin respuesta");

  if (status.llm_ready) {
    const model = status.review_model ? `${status.model} · revisor ${status.review_model}` : status.model;
    setPill(els.model, "ok", status.model);
    els.model.title = `Modelo: ${model}`;
  } else {
    setPill(els.model, "bad", "Sin modelo");
  }
  renderTokens(status.tokens);

  els.project.textContent = caps.project ? `· ${caps.project}` : "";
  const rows = [
    ["Proyecto", caps.project || "—"],
    ["Esquemático", caps.schematic_open_in_editor ? "abierto en el editor" : caps.schematic_write ? "listo para escribir" : "—"],
    ["Placa", caps.board_open ? "abierta" : "cerrada"],
    ["Autoruteo", status.autoroute_enabled ? "activo" : "desactivado"],
  ];
  if (status.java) {
    rows.push(["Java", status.java.ok ? (status.java.label || status.java.java || "listo") : "no encontrado"]);
  }
  if (caps.libraries) rows.push(["Bibliotecas", `${caps.libraries.symbol_libraries ?? "?"} de símbolos, ${caps.libraries.footprint_libraries ?? "?"} de huellas`]);
  if (caps.erc !== undefined) rows.push(["kicad-cli", caps.erc ? "encontrado" : "no encontrado"]);
  els.facts.replaceChildren(
    ...rows.flatMap(([key, value]) => [el("dt", {}, key), el("dd", {}, String(value))]),
  );
  els.notes.replaceChildren(
    ...(caps.notes || []).map((note) =>
      el("li", { className: /abierto|cerrarlo|no respond|dejó|Java|Autoruteo/i.test(note) ? "alert" : "" }, note),
    ),
  );
  const autoBtn = $("btn-autoroute");
  if (autoBtn) autoBtn.hidden = !state.autorouteEnabled;
  refreshComposer();
}

// Suma del proceso (modelo principal + revisores). Solo lo que el proveedor
// devuelve en `usage`; si no lo manda, se dice en vez de enseñar 0.
function renderTokens(tokens) {
  if (!els.tokens || !tokens) return;
  const label = els.tokens.querySelector("span");
  const number = new Intl.NumberFormat("es").format(tokens.total || 0);
  const prefix = tokens.estimated ? "~" : "";
  label.textContent = `${prefix}${number} tokens`;
  const detail =
    `Entrada ${new Intl.NumberFormat("es").format(tokens.prompt || 0)} · ` +
    `salida ${new Intl.NumberFormat("es").format(tokens.completion || 0)} · ` +
    `${tokens.calls || 0} llamadas desde que se abrió el chat`;
  els.tokens.title = tokens.estimated
    ? `Estimado, porque el proveedor no informó el consumo. ${detail}`
    : detail;
}

function renderSelection(selection) {
  const items = (selection && selection.items) || [];
  els.selectionCount.textContent = String(items.length);
  if (!items.length) {
    els.selection.replaceChildren(el("span", { className: "muted" }, selection && selection.error ? selection.error : "Nada seleccionado en el editor de PCB."));
    return;
  }
  els.selection.replaceChildren(
    ...items.slice(0, 40).map((item) => {
      const label = item.reference || item.kind || "ítem";
      return el("span", { className: "chip", title: [item.value, item.footprint].filter(Boolean).join(" · ") }, label);
    }),
  );
}

// ---------- Chat ----------

function submit(text) {
  const clean = text.trim();
  if (!clean || state.busy) return;
  if (!send({ type: "chat.send", text: clean })) {
    toast("No hay conexión con el servidor todavía.", "bad");
    return;
  }
  els.welcome.hidden = true;
  addUser(clean);
  els.input.value = "";
  autosize();
  setBusy(true);
  showTyping();
}

function setBusy(busy) {
  state.busy = busy;
  if (!busy) hideTyping();
  refreshComposer();
}

function refreshComposer() {
  const blocked = !state.connected || state.busy;
  els.send.disabled = blocked;
  document.querySelectorAll("[data-prompt], [data-local]").forEach((button) => {
    button.disabled = blocked;
  });
  if (!state.connected) els.hint.textContent = "Sin conexión con el servidor. Reintentando…";
  else if (state.busy) els.hint.textContent = "Trabajando… puedes ver cada paso abajo.";
  else if (!state.llmReady) els.hint.textContent = "Configura el modelo en ⚙ Ajustes. Funcionan /estado y /herramientas.";
  else els.hint.textContent = "";
}

function ensureTurn(turnId) {
  let block = document.querySelector(`.steps[data-turn="${turnId}"]`);
  if (!block) {
    block = el("div", { className: "steps" });
    block.dataset.turn = turnId;
    block.hidden = true;
    append(block);
  }
  return block;
}

function stepStarted(message) {
  const block = ensureTurn(message.turn_id);
  block.hidden = false;
  const details = el("details", { className: "step running" });
  details.dataset.index = String(message.index);
  const summary = el("summary", {},
    el("span", { className: "state" }),
    el("span", { className: "name" }, TOOL_LABELS[message.tool] || message.tool),
    el("span", { className: "arg" }, briefArgs(message.tool, message.arguments || {})),
  );
  details.append(summary);
  block.append(details);
  // Las herramientas que siguen van debajo del último texto del modelo.
  els.messages.append(block);
  scrollDown();
}

function stepFinished(message) {
  const block = ensureTurn(message.turn_id);
  let details = block.querySelector(`.step[data-index="${message.index}"]`);
  if (!details) {
    stepStarted(message);
    details = block.querySelector(`.step[data-index="${message.index}"]`);
  }
  const result = message.result || {};
  const failed = result.ok === false || result.written === false;
  details.classList.remove("running");
  details.classList.add(failed ? "fail" : "ok");
  if (failed && result.error) details.querySelector(".arg").textContent = result.error;
  details.append(el("pre", {}, JSON.stringify(result, null, 2)));
  if (result.image) addImage(result.image, VIEW_LABELS[(message.arguments || {}).view] || captionFor(message));
  if (result.before_image && result.before_image !== result.image) {
    addImage(result.before_image, "Antes");
  }
  showTyping();
}

function captionFor(message) {
  if (message.tool === "autoroute_board") return "Placa autoruteada (candidato)";
  if (message.tool === "ipc_place_components") return "Colocación IPC (propuesta)";
  return "Vista del circuito";
}

function finishTurn(message) {
  hideTyping();
  if (message.tokens) renderTokens(message.tokens);
  const said = document.querySelectorAll(`.msg.assistant[data-turn="${message.turn_id}"]`);
  const lastText = said.length ? said[said.length - 1].dataset.raw : "";
  if (message.reply && message.reply !== lastText) addAssistant(message.reply, message.turn_id);
  setBusy(false);
}

function clearMessages() {
  els.messages.querySelectorAll(".msg, .steps, .figure").forEach((node) => node.remove());
  els.welcome.hidden = false;
}

function rememberProject(path) {
  if (!path) return;
  state.projectKey = path;
  sessionStorage.setItem(PROJECT_KEY, path);
}

function noteProject(path) {
  if (!path) return;
  if (!state.projectKey) {
    rememberProject(path);
    send({ type: "session.sync" });
    return;
  }
  if (path === state.projectKey) return;
  rememberProject(path);
  if (state.busy) return;
  clearMessages();
  send({ type: "session.bind" });
}

function showHistory(message) {
  const modal = $("history-modal");
  $("history-title").textContent = message.title || "Conversación";
  const body = $("history-body");
  const lines = message.history || [];
  body.replaceChildren(
    ...(lines.length
      ? lines
          .filter((row) => row.role === "user" || row.role === "assistant")
          .map((row) => {
            const who = el("span", { className: "who" }, row.role === "user" ? "Tú" : "KiCad IA");
            return el("p", {}, who, row.text || "");
          })
      : [el("p", { className: "muted" }, "Esta conversación no tiene texto.")]),
  );
  modal.hidden = false;
}

function renderSessions(rows, activeId) {
  if (!els.sessions) return;
  const list = rows || [];
  els.sessionsEmpty.hidden = list.length > 0;
  els.sessions.replaceChildren(
    ...list.map((row) => {
      const open = el("button", { type: "button", className: "open", title: row.title }, row.title);
      open.addEventListener("click", () => {
        send({ type: "session.preview", session_id: row.id });
      });
      const drop = el("button", { type: "button", className: "drop", title: "Borrar conversación", "aria-label": "Borrar conversación" }, "✕");
      drop.addEventListener("click", (event) => {
        event.stopPropagation();
        if (state.busy) return;
        send({ type: "session.delete", session_id: row.id });
      });
      return el("li", { className: row.id === activeId ? "session-row active" : "session-row" }, open, drop);
    }),
  );
}

function renderHistory(rows) {
  els.welcome.hidden = true;
  for (const row of rows) {
    if (row.role === "user") addUser(row.text);
    else if (row.role === "assistant") addAssistant(row.text);
    else if (row.role === "image") addImage(row.image, "Vista del circuito");
  }
}

function addUser(text) {
  append(el("div", { className: "msg user" }, text));
}

function addAssistant(text, turnId) {
  const node = el("div", { className: "msg assistant" });
  node.innerHTML = markdown(text);
  node.dataset.raw = text;
  if (turnId) node.dataset.turn = turnId;
  append(node);
}

function addError(text) {
  append(el("div", { className: "msg error" }, text));
}

function addImage(src, caption) {
  const img = el("img", { src, alt: caption, loading: "lazy" });
  img.addEventListener("click", () => openLightbox(src));
  img.addEventListener("load", scrollDown);
  img.addEventListener("error", () => {
    img.replaceWith(el("span", { className: "muted" }, "No pude cargar la imagen."));
  });
  const figure = el("figure", { className: "figure" },
    img,
    el("figcaption", {}, el("span", {}, caption), el("a", { href: src, target: "_blank", rel: "noopener" }, "Abrir")),
  );
  els.welcome.hidden = true;
  append(figure);
}

function showTyping() {
  if (!state.busy) return;
  if (!state.typing) {
    state.typing = el("div", { className: "typing" }, el("span"), el("span"), el("span"));
  }
  els.messages.append(state.typing);
  scrollDown();
}

function hideTyping() {
  if (state.typing) state.typing.remove();
}

function append(node) {
  if (state.typing && state.typing.isConnected) els.messages.insertBefore(node, state.typing);
  else els.messages.append(node);
  scrollDown();
}

function scrollDown() {
  els.messages.scrollTop = els.messages.scrollHeight;
}

function briefArgs(tool, args) {
  if (args.query) return `«${args.query}»`;
  if (args.lib_id) return args.lib_id;
  if (args.lcsc_id) return args.lcsc_id;
  if (args.view) return VIEW_LABELS[args.view] || args.view;
  if (tool === "organize_layout") {
    const groups = (args.groups || []).map((group) => group.name).join(", ");
    return `${args.target || ""}${groups ? ` · ${groups}` : ""}`;
  }
  if (tool === "place_circuit") return `${(args.symbols || []).length} símbolos, ${(args.nets || []).length} redes`;
  if (args.reference) return args.reference;
  if (args.placements) return `${args.placements.length} huellas`;
  return "";
}

// ---------- Markdown ligero ----------

function escapeHtml(text) {
  return text.replace(/[&<>"']/g, (char) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[char]);
}

function inline(text) {
  return text
    .replace(/`([^`]+)`/g, "<code>$1</code>")
    .replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>")
    .replace(/(^|[\s(])\*([^*\s][^*]*)\*/g, "$1<em>$2</em>");
}

function markdown(source) {
  const lines = escapeHtml(source || "").split("\n");
  const html = [];
  let list = null;
  let paragraph = [];
  let code = null;
  const flushParagraph = () => {
    if (paragraph.length) html.push(`<p>${inline(paragraph.join("<br>"))}</p>`);
    paragraph = [];
  };
  const closeList = () => {
    if (list) html.push(`</${list}>`);
    list = null;
  };
  for (const line of lines) {
    if (line.trim().startsWith("```")) {
      if (code === null) {
        flushParagraph();
        closeList();
        code = [];
      } else {
        html.push(`<pre><code>${code.join("\n")}</code></pre>`);
        code = null;
      }
      continue;
    }
    if (code !== null) {
      code.push(line);
      continue;
    }
    const bullet = line.match(/^\s*[-*•]\s+(.*)$/);
    const numbered = line.match(/^\s*\d+[.)]\s+(.*)$/);
    if (bullet || numbered) {
      flushParagraph();
      const kind = bullet ? "ul" : "ol";
      if (list !== kind) {
        closeList();
        html.push(`<${kind}>`);
        list = kind;
      }
      html.push(`<li>${inline((bullet || numbered)[1])}</li>`);
      continue;
    }
    if (!line.trim()) {
      flushParagraph();
      closeList();
      continue;
    }
    const heading = line.match(/^#{1,4}\s+(.*)$/);
    if (heading) {
      flushParagraph();
      closeList();
      html.push(`<p><strong>${inline(heading[1])}</strong></p>`);
      continue;
    }
    closeList();
    paragraph.push(line);
  }
  if (code !== null) html.push(`<pre><code>${code.join("\n")}</code></pre>`);
  flushParagraph();
  closeList();
  return html.join("");
}

// ---------- Utilidades de interfaz ----------

function el(tag, props = {}, ...children) {
  const node = document.createElement(tag);
  for (const [key, value] of Object.entries(props)) {
    if (key in node) node[key] = value;
    else node.setAttribute(key, value);
  }
  for (const child of children) {
    if (child === null || child === undefined) continue;
    node.append(child instanceof Node ? child : document.createTextNode(String(child)));
  }
  return node;
}

function setPill(pill, kind, text) {
  pill.classList.remove("ok", "warn", "bad", "busy");
  pill.classList.add(kind);
  pill.querySelector("span").textContent = text;
}

function toast(text, kind = "") {
  const node = el("div", { className: `toast ${kind}` }, text);
  els.toasts.append(node);
  setTimeout(() => node.remove(), 5000);
}

function openLightbox(src) {
  els.lightboxImg.src = src;
  els.lightboxOpen.href = src;
  els.lightbox.hidden = false;
}

function closeLightbox() {
  els.lightbox.hidden = true;
  els.lightboxImg.removeAttribute("src");
}

function autosize() {
  els.input.style.height = "auto";
  els.input.style.height = `${Math.min(els.input.scrollHeight, 180)}px`;
}

// ---------- Eventos de la página ----------

els.form.addEventListener("submit", (event) => {
  event.preventDefault();
  submit(els.input.value);
});
els.input.addEventListener("keydown", (event) => {
  if (event.key === "Enter" && !event.shiftKey && !event.isComposing) {
    event.preventDefault();
    submit(els.input.value);
  }
});
els.input.addEventListener("input", autosize);
els.quickActions.addEventListener("click", (event) => {
  event.stopPropagation();
  const open = els.quickMenu.hidden;
  els.quickMenu.hidden = !open;
  els.quickActions.setAttribute("aria-expanded", open ? "true" : "false");
});
document.addEventListener("click", (event) => {
  if (!els.quickMenu.hidden && !els.quickMenu.contains(event.target)) {
    els.quickMenu.hidden = true;
    els.quickActions.setAttribute("aria-expanded", "false");
  }
  const button = event.target.closest("[data-prompt], [data-local]");
  if (!button || button.disabled) return;
  els.quickMenu.hidden = true;
  els.quickActions.setAttribute("aria-expanded", "false");
  submit(button.dataset.prompt || button.dataset.local);
  els.side.classList.remove("open");
});
$("toggle-side").addEventListener("click", () => els.side.classList.toggle("open"));
function closeModal(id) {
  $(id).hidden = true;
}
$("history-close").addEventListener("click", () => closeModal("history-modal"));
$("history-modal").addEventListener("click", (event) => {
  if (event.target === $("history-modal")) closeModal("history-modal");
});
$("new-chat").addEventListener("click", () => {
  if (state.busy) {
    toast("Espera a que termine el turno actual.");
    return;
  }
  clearMessages();
  send({ type: "session.reset" });
});
$("lightbox-close").addEventListener("click", closeLightbox);
els.lightbox.addEventListener("click", (event) => {
  if (event.target === els.lightbox) closeLightbox();
});
document.addEventListener("visibilitychange", () => {
  if (!document.hidden) send({ type: "status.refresh" });
});

// ---------- Ajustes ----------

const settingsModal = $("settings-modal");
const settingsForm = $("settings-form");

function openSettings() {
  settingsModal.hidden = false;
  loadSettingsForm().catch((err) => toast(String(err.message || err), "bad"));
}

function closeSettings() {
  settingsModal.hidden = true;
}

async function loadSettingsForm() {
  const res = await fetch("/api/settings");
  if (!res.ok) throw new Error("No pude cargar los ajustes.");
  const data = await res.json();
  state.settingsLoaded = data;
  const preset = $("set-preset");
  preset.replaceChildren();
  for (const item of data.presets || []) {
    preset.append(el("option", { value: item.id }, item.label));
  }
  preset.value = guessPreset(data);
  $("set-base-url").value = data.llm_base_url || "";
  $("set-api-key").value = "";
  $("set-api-key").placeholder = data.llm_api_key_set
    ? `Guardada (${data.llm_api_key_masked || "****"}) — deja vacío para no cambiar`
    : "Se guarda en este equipo";
  $("set-api-hint").textContent = data.llm_api_key_set
    ? "Hay una API key guardada. Escribe otra para sustituirla."
    : "Gemini y OpenAI necesitan API key. Ollama puede ir vacío.";
  $("set-model").value = data.llm_model || "";
  $("set-review-model").value = data.llm_review_model || "";
  $("set-java").value = data.java_bin || "";
  $("set-autoroute").checked = Boolean(data.autoroute_enabled);
  const fab = data.fab || {};
  $("fab-track").value = fab.min_track_mm ?? 0.15;
  $("fab-clearance").value = fab.min_clearance_mm ?? 0.15;
  $("fab-via-dia").value = fab.min_via_diameter_mm ?? 0.6;
  $("fab-via-drill").value = fab.min_via_drill_mm ?? 0.3;
  $("fab-hole").value = fab.min_hole_mm ?? 0.3;
  $("fab-fields").hidden = !$("set-autoroute").checked;
  $("settings-path").textContent = data.path ? `Se guardan en ${data.path}` : "";
  showJavaStatus(data.java_probe);
}

function guessPreset(data) {
  const url = (data.llm_base_url || "").toLowerCase();
  if (url.includes("generativelanguage.googleapis.com")) return "gemini";
  if (url.includes("11434")) return "ollama";
  if (url.includes("api.openai.com")) return "openai";
  return "custom";
}

function showJavaStatus(probe) {
  const node = $("set-java-status");
  if (!probe) {
    node.textContent = "";
    return;
  }
  if (probe.ok) {
    node.textContent = `✓ ${probe.label || probe.java}`;
    node.style.color = "var(--ok)";
    if (probe.java && !$("set-java").value) $("set-java").value = probe.java;
  } else {
    node.textContent = probe.error || "Java no encontrado";
    node.style.color = "var(--bad)";
  }
}

$("open-settings").addEventListener("click", openSettings);
$("settings-close").addEventListener("click", closeSettings);
$("settings-cancel").addEventListener("click", closeSettings);
settingsModal.addEventListener("click", (event) => {
  if (event.target === settingsModal) closeSettings();
});
$("set-autoroute").addEventListener("change", () => {
  $("fab-fields").hidden = !$("set-autoroute").checked;
});
$("set-preset").addEventListener("change", () => {
  const data = state.settingsLoaded;
  const preset = (data.presets || []).find((item) => item.id === $("set-preset").value);
  if (!preset || preset.id === "custom") return;
  $("set-base-url").value = preset.llm_base_url || "";
  $("set-model").value = preset.llm_model || "";
  $("set-review-model").value = preset.llm_review_model || "";
});
$("set-java-detect").addEventListener("click", async () => {
  const res = await fetch("/api/settings/probe-java", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ java_bin: $("set-java").value.trim() }),
  });
  const probe = await res.json();
  showJavaStatus(probe);
  if (probe.ok && probe.java) $("set-java").value = probe.java;
});
settingsForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const key = $("set-api-key").value.trim();
  const payload = {
    llm_base_url: $("set-base-url").value.trim(),
    llm_model: $("set-model").value.trim(),
    llm_review_model: $("set-review-model").value.trim(),
    java_bin: $("set-java").value.trim(),
    autoroute_enabled: $("set-autoroute").checked,
    keep_api_key: !key,
    fab: {
      min_track_mm: Number($("fab-track").value),
      min_clearance_mm: Number($("fab-clearance").value),
      min_via_diameter_mm: Number($("fab-via-dia").value),
      min_via_drill_mm: Number($("fab-via-drill").value),
      min_hole_mm: Number($("fab-hole").value),
    },
  };
  if (key) payload.llm_api_key = key;
  const res = await fetch("/api/settings", {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    toast(err.detail || "No pude guardar los ajustes.", "bad");
    return;
  }
  toast("Ajustes guardados.", "ok");
  closeSettings();
  send({ type: "status.refresh" });
});
document.addEventListener("keydown", (event) => {
  if (event.key === "Escape") {
    closeLightbox();
    closeSettings();
  }
});

connect();
els.input.focus();
