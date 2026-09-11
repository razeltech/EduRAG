const storedPersona = localStorage.getItem("edurag_persona");
const state = {
  token: localStorage.getItem("edurag_token") || "",
  user: null,
  persona: !storedPersona || storedPersona === "tutor" ? "chat" : storedPersona,
  courseId: localStorage.getItem("edurag_course") || "",
  convId: null,
  convos: [],
  courses: [],
  personas: [],
  debug: false,
  register: false,
  streaming: false,
};
localStorage.setItem("edurag_persona", state.persona);

const $ = (id) => document.getElementById(id);

function decodeHtml(s) {
  const t = document.createElement("textarea");
  t.innerHTML = s;
  return t.value;
}

function toast(msg) {
  const el = $("toast");
  el.textContent = msg;
  el.classList.add("show");
  setTimeout(() => el.classList.remove("show"), 2800);
}

async function api(path, opts = {}) {
  const headers = { ...(opts.headers || {}) };
  if (state.token) headers.Authorization = "Bearer " + state.token;
  if (opts.body && !(opts.body instanceof FormData) && !headers["Content-Type"]) {
    headers["Content-Type"] = "application/json";
  }
  const res = await fetch(path, { ...opts, headers });
  if (res.status === 401) {
    logout(false);
    throw new Error("Please sign in");
  }
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const data = await res.json();
      detail = data.detail || JSON.stringify(data);
    } catch (_) {}
    throw new Error(typeof detail === "string" ? detail : "Request failed");
  }
  if (res.headers.get("content-type")?.includes("text/event-stream")) return res;
  if (res.status === 204) return null;
  return res.json();
}

function logout(reload = true) {
  state.token = "";
  state.user = null;
  localStorage.removeItem("edurag_token");
  if (reload) location.reload();
}

function showApp() {
  $("auth").classList.add("hidden");
  $("app").classList.remove("hidden");
  $("who").textContent = `${state.user.name} · ${state.user.role}`;
  document.querySelectorAll(".staff-only").forEach((el) => {
    el.style.display = ["teacher", "admin"].includes(state.user.role) ? "" : "none";
  });
  document.querySelectorAll(".admin-only").forEach((el) => {
    el.style.display = state.user.role === "admin" ? "" : "none";
  });
  syncK12();
}

function currentPersona() {
  return state.personas.find((p) => p.id === state.persona) || state.personas[0];
}

function currentLibrary() {
  return state.courses.find((c) => c.id === state.courseId);
}

function isStaff() {
  return ["teacher", "admin"].includes(state.user?.role);
}

function syncK12() {
  const lib = currentLibrary();
  const row = $("k12Label");
  const box = $("k12Toggle");
  if (!row || !box) return;
  row.style.display = isStaff() && lib ? "flex" : "none";
  box.checked = !!(lib && lib.age_band === "k12");
}

function updateEmpty() {
  const p = currentPersona();
  const lib = currentLibrary();
  if ($("personaHint") && p) $("personaHint").textContent = p.name;
  if ($("emptyTitle")) {
    if (lib) $("emptyTitle").textContent = `Ask ${lib.name}`;
    else if (p) $("emptyTitle").textContent = p.tagline;
    else $("emptyTitle").textContent = "Say something";
  }
  if ($("courseTitle")) $("courseTitle").textContent = lib ? lib.name : "Chat";
  syncK12();
  const input = $("input");
  if (input) {
    input.placeholder = lib ? `Ask ${lib.name}...` : "Message...";
  }
  const blurb = $("emptyBlurb");
  if (blurb) {
    blurb.textContent = lib
      ? "Answers prefer this library. Switch to Docs or Tutor for copy-ready code."
      : "Talk normally. Attach a library when you want answers from your files.";
  }
}

function renderPersonas() {
  const sel = $("personaSelect");
  if (!sel) return;
  if (!state.personas.some((p) => p.id === state.persona) && state.personas[0]) {
    state.persona = state.personas[0].id;
  }
  sel.innerHTML = state.personas
    .map(
      (p) =>
        `<option value="${p.id}" ${p.id === state.persona ? "selected" : ""} title="${esc(p.tagline)}">${esc(p.name)}</option>`
    )
    .join("");
  sel.onchange = () => {
    state.persona = sel.value;
    localStorage.setItem("edurag_persona", state.persona);
    updateEmpty();
  };
  updateEmpty();
}

function renderCourses() {
  const sel = $("courseSelect");
  if (!sel) return;
  if (!state.courses.length) {
    sel.innerHTML = '<option value="">No libraries yet</option>';
    state.courseId = "";
    localStorage.removeItem("edurag_course");
    updateEmpty();
    return;
  }
  if (!state.courses.some((c) => c.id === state.courseId)) {
    state.courseId = "";
    localStorage.removeItem("edurag_course");
  }
  sel.innerHTML =
    '<option value="">Choose a library</option>' +
    state.courses
      .map((c) => {
        const n = c.chunk_count || 0;
        return `<option value="${c.id}" ${c.id === state.courseId ? "selected" : ""}>${esc(c.name)} (${n})</option>`;
      })
      .join("");
  sel.onchange = async () => {
    state.courseId = sel.value;
    updateEmpty();
    await refreshCourseBits();
  };
  updateEmpty();
}

function renderConvos() {
  $("convoList").innerHTML = state.convos
    .map(
      (c) => `<li class="${c.id === state.convId ? "on" : ""}" data-id="${c.id}">
        <span>${esc(c.title || "New chat")}</span>
        <button class="x" data-del="${c.id}" aria-label="Delete">×</button>
      </li>`
    )
    .join("");
}

function esc(s) {
  return String(s || "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;");
}

const CS_KW = new Set(
  "abstract as async await base bool break byte case catch char checked class const continue decimal default delegate do double else enum event explicit extern false finally fixed float for foreach goto if implicit in int interface internal is lock long namespace new null object operator out override params private protected public readonly ref return sbyte sealed short sizeof stackalloc static string struct switch this throw true try typeof uint ulong unchecked unsafe ushort using virtual void volatile while var get set add remove yield where".split(" ")
);
const PY_KW = new Set(
  "and as assert async await break class continue def del elif else except False finally for from global if import in is lambda None nonlocal not or pass raise return True try while with yield".split(" ")
);
const JS_KW = new Set(
  "async await break case catch class const continue debugger default delete do else export extends false finally for function if import in instanceof let new null return static super switch this throw true try typeof var void while yield of".split(" ")
);

function normLang(lang) {
  const l = (lang || "").toLowerCase().replace("#", "sharp");
  if (["cs", "cshar", "csharp", "c++", "cpp", "hlsl", "glsl", "shaderlab", "shader"].includes(l)) return "csharp";
  if (["py", "python"].includes(l)) return "python";
  if (["js", "javascript", "ts", "typescript", "json"].includes(l)) return "js";
  if (["html", "xml"].includes(l)) return "html";
  return l || "csharp";
}

function highlightLine(lang, line) {
  const out = [];
  let i = 0;
  const kws = lang === "python" ? PY_KW : lang === "js" ? JS_KW : CS_KW;
  const comment = lang === "python" ? "#" : "//";
  while (i < line.length) {
    if (line.startsWith(comment, i) || (lang === "csharp" && line.startsWith("#", i) && /^#(if|else|endif|region|endregion|define)/.test(line.slice(i)))) {
      out.push(`<span class="tok-com">${esc(line.slice(i))}</span>`);
      break;
    }
    const ch = line[i];
    if (ch === '"' || ch === "'") {
      let j = i + 1;
      while (j < line.length && line[j] !== ch) {
        if (line[j] === "\\") j += 1;
        j += 1;
      }
      j = Math.min(j + 1, line.length);
      out.push(`<span class="tok-str">${esc(line.slice(i, j))}</span>`);
      i = j;
      continue;
    }
    if (ch === "/" && line[i + 1] === "*" && lang !== "python") {
      const end = line.indexOf("*/", i + 2);
      const j = end < 0 ? line.length : end + 2;
      out.push(`<span class="tok-com">${esc(line.slice(i, j))}</span>`);
      i = j;
      continue;
    }
    if (/[A-Za-z_]/.test(ch)) {
      let j = i + 1;
      while (j < line.length && /[A-Za-z0-9_]/.test(line[j])) j += 1;
      const word = line.slice(i, j);
      const next = line.slice(j).match(/^\s*\(/);
      let cls = "";
      if (kws.has(word)) cls = "tok-kw";
      else if (/^[A-Z]/.test(word) && word.length > 1) cls = "tok-type";
      else if (next) cls = "tok-fn";
      out.push(cls ? `<span class="${cls}">${esc(word)}</span>` : esc(word));
      i = j;
      continue;
    }
    if (/[0-9]/.test(ch)) {
      let j = i + 1;
      while (j < line.length && /[0-9.fFxXa-fA-F]/.test(line[j])) j += 1;
      out.push(`<span class="tok-num">${esc(line.slice(i, j))}</span>`);
      i = j;
      continue;
    }
    out.push(esc(ch));
    i += 1;
  }
  return out.join("");
}

function highlightCode(lang, src) {
  const kind = normLang(lang);
  const lines = String(src || "").replace(/\r\n/g, "\n").split("\n");
  const body = lines
    .map((ln, n) => {
      const hl = highlightLine(kind, ln) || " ";
      return `<div class="cl"><span class="ln">${n + 1}</span><span class="ls">${hl}</span></div>`;
    })
    .join("");
  return body;
}

function guessLang(text) {
  if (/^\s*using\s+UnityEngine/m.test(text) || /MonoBehaviour|SerializeField/.test(text)) return "csharp";
  if (/^\s*def\s+|^\s*import\s+/m.test(text)) return "python";
  if (/^\s*(function|const|let|export)\s/m.test(text)) return "javascript";
  return "csharp";
}

function looksLikeCodeLine(line) {
  const t = line || "";
  if (!t.trim()) return false;
  return /^(using |namespace |#include |from |import |def |class |public |private |protected |internal |void |int |float |bool |string |var |if \(|for \(|foreach |while |return |this\.|\t|    |\{\s*$|\}\s*$|\/\/|#region)/.test(t) || /;\s*$/.test(t);
}

function md(raw) {
  const src = String(raw || "");
  const chunks = [];
  let i = 0;
  while (i < src.length) {
    const start = src.indexOf("```", i);
    if (start < 0) {
      chunks.push({ kind: "md", text: src.slice(i) });
      break;
    }
    if (start > i) chunks.push({ kind: "md", text: src.slice(i, start) });
    const after = src.slice(start + 3);
    const langMatch = after.match(/^([a-zA-Z0-9_+#-]*)\r?\n?/);
    const lang = (langMatch && langMatch[1]) || "";
    const bodyStart = start + 3 + (langMatch ? langMatch[0].length : 0);
    const end = src.indexOf("```", bodyStart);
    if (end < 0) {
      chunks.push({ kind: lang.toLowerCase() === "quiz" ? "quiz" : "code", lang, text: src.slice(bodyStart) });
      break;
    }
    chunks.push({
      kind: lang.toLowerCase() === "quiz" ? "quiz" : "code",
      lang,
      text: src.slice(bodyStart, end),
    });
    i = end + 3;
  }
  return chunks.map(renderChunk).join("");
}

function renderChunk(chunk) {
  if (chunk.kind === "code") {
    const raw = chunk.text.replace(/^\n/, "").replace(/\n$/, "");
    const label = (chunk.lang || guessLang(raw) || "code").trim() || "code";
    return `<div class="code-wrap"><div class="code-bar"><span>${esc(label)}</span><button type="button" class="copy-btn">Copy</button></div><pre class="code-pre" data-raw="${encodeURIComponent(raw)}">${highlightCode(label, raw)}</pre></div>`;
  }
  if (chunk.kind === "quiz") {
    try {
      const q = JSON.parse(chunk.text.trim());
      if (q && q.question) return quizPreview(q);
    } catch (_) {}
    return `<pre class="quiz-raw">${esc(chunk.text)}</pre>`;
  }
  return renderBlocks(chunk.text);
}

function quizPreview(q) {
  const opts = q.options || [];
  return `<div class="quiz-card"><p class="quiz-kicker">Check</p><p class="quiz-q">${esc(q.question)}</p>${opts.map((o) => `<span class="quiz-opt">${esc(o)}</span>`).join("")}</div>`;
}

function renderInline(s) {
  let t = esc(s);
  t = t.replace(/`([^`]+)`/g, "<code>$1</code>");
  t = t.replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>");
  t = t.replace(/(^|[^\*])\*([^*\n]+)\*/g, "$1<em>$2</em>");
  t = t.replace(/\[(\d+)\]/g, "<cite>[$1]</cite>");
  return t;
}

function renderBlocks(text) {
  const lines = String(text || "").replace(/\r\n/g, "\n").split("\n");
  const out = [];
  let i = 0;
  while (i < lines.length) {
    const line = lines[i];
    if (!line.trim()) {
      i += 1;
      continue;
    }
    if (/^\|/.test(line) && i + 1 < lines.length && /^\|?\s*-/.test(lines[i + 1])) {
      const rows = [];
      while (i < lines.length && /^\|/.test(lines[i])) {
        if (!/^\|?\s*-/.test(lines[i])) rows.push(lines[i]);
        i += 1;
      }
      out.push(renderTable(rows));
      continue;
    }
    const hm = line.match(/^(#{1,3})\s+(.+)/);
    if (hm) {
      const n = hm[1].length;
      out.push(`<h${n}>${renderInline(hm[2])}</h${n}>`);
      i += 1;
      continue;
    }
    if (/^>\s?/.test(line)) {
      const bits = [];
      while (i < lines.length && /^>\s?/.test(lines[i])) {
        bits.push(lines[i].replace(/^>\s?/, ""));
        i += 1;
      }
      out.push(`<blockquote>${renderInline(bits.join(" "))}</blockquote>`);
      continue;
    }
    if (looksLikeCodeLine(line)) {
      let n = 0;
      for (let k = i; k < lines.length && (looksLikeCodeLine(lines[k]) || (lines[k].trim() === "" && looksLikeCodeLine(lines[k + 1] || ""))); k += 1) n += 1;
      if (n >= 3) {
        const raw = [];
        while (i < lines.length && (looksLikeCodeLine(lines[i]) || (lines[i].trim() === "" && looksLikeCodeLine(lines[i + 1] || "")))) {
          raw.push(lines[i]);
          i += 1;
        }
        out.push(renderChunk({ kind: "code", lang: guessLang(raw.join("\n")), text: raw.join("\n") }));
        continue;
      }
    }
    if (/^[-*]\s+/.test(line)) {
      const items = [];
      while (i < lines.length && /^[-*]\s+/.test(lines[i])) {
        items.push(`<li>${renderInline(lines[i].replace(/^[-*]\s+/, ""))}</li>`);
        i += 1;
      }
      out.push(`<ul>${items.join("")}</ul>`);
      continue;
    }
    if (/^\d+\.\s+/.test(line)) {
      const items = [];
      while (i < lines.length && /^\d+\.\s+/.test(lines[i])) {
        items.push(`<li>${renderInline(lines[i].replace(/^\d+\.\s+/, ""))}</li>`);
        i += 1;
      }
      out.push(`<ol>${items.join("")}</ol>`);
      continue;
    }
    const para = [];
    while (i < lines.length && lines[i].trim() && !/^(#{1,3}\s+|[-*]\s+|\d+\.\s+|>\s?|\|)/.test(lines[i])) {
      para.push(lines[i]);
      i += 1;
    }
    out.push(`<p>${renderInline(para.join(" "))}</p>`);
  }
  return `<div class="md">${out.join("")}</div>`;
}

function renderTable(rows) {
  if (!rows.length) return "";
  const cells = (row) =>
    row
      .replace(/^\||\|$/g, "")
      .split("|")
      .map((c) => c.trim());
  const head = cells(rows[0]);
  const body = rows.slice(1);
  return `<div class="table-wrap"><table><thead><tr>${head.map((c) => `<th>${renderInline(c)}</th>`).join("")}</tr></thead><tbody>${body
    .map((r) => `<tr>${cells(r).map((c) => `<td>${renderInline(c)}</td>`).join("")}</tr>`)
    .join("")}</tbody></table></div>`;
}

function answerBar() {
  return `<div class="answer-bar">
    <button type="button" class="copy-all" title="Copy">⧉ Copy</button>
    <button type="button" class="guide-btn" data-guide="copyans" aria-label="What is Copy?"></button>
    <button type="button" class="rate" data-v="1" title="Helpful">▲ Helpful</button>
    <button type="button" class="guide-btn" data-guide="helpful" aria-label="What is Helpful?"></button>
    <button type="button" class="rate" data-v="-1" title="Not quite">▼ Not quite</button>
    <button type="button" class="guide-btn" data-guide="notquite" aria-label="What is Not quite?"></button>
  </div>`;
}

function addMsg(role, text, extra = {}) {
  $("empty").classList.add("hidden");
  const thread = $("thread");
  const div = document.createElement("div");
  div.className = "msg " + role;
  const who = role === "user" ? "You" : extra.persona || "EduRAG";
  div.innerHTML = `<div class="av">${esc(who[0] || "?")}</div>
    <div class="bubble">
      <div class="who">${esc(who)}</div>
      <div class="text">${role === "assistant" ? md(text) : esc(text)}</div>
      <div class="extra"></div>
    </div>`;
  thread.appendChild(div);
  const page = $("page");
  if (page) page.scrollTop = page.scrollHeight;
  return div;
}

function citeChips(cites) {
  if (!state.debug || !cites || !cites.length) return "";
  return (
    '<details class="sources"><summary>Sources</summary><div class="cites">' +
    cites
      .map((c) => {
        const tip = [c.source_file, c.heading_path, c.snippet].filter(Boolean).join(" — ");
        return `<span class="cite-chip" title="${esc(tip)}">[${c.n}] ${esc(c.source_file || "source")}</span>`;
      })
      .join("") +
    "</div></details>"
  );
}

function renderSources(cites, intoEl) {
  const html = citeChips(cites);
  if (intoEl) intoEl.innerHTML = html + intoEl.innerHTML;
  const box = $("sourceList");
  if (box) box.innerHTML = html;
}

function renderProgress(topics, mine, klass) {
  const box = $("progressList");
  if (!box) return;
  const rows = mine || [];
  const heads = topics || [];
  const classRows = klass || [];
  const weak = rows.filter((p) => (p.mastery_score || 0) < 0.45);
  let html = "";
  if (["teacher", "exam_coach"].includes(state.persona) && weak.length) {
    html += `<p class="weak-hint">Drill: ${weak.map((p) => esc(p.topic_name)).join(", ")}</p>`;
  }
  if (heads.length) {
    html += heads
      .map((t) => {
        const pct = t.mastery_score == null ? null : Math.round(t.mastery_score * 100);
        const cls = t.weak ? "prog weak" : "prog";
        const bar =
          pct == null ? "" : `<div class="bar"><i style="width:${pct}%"></i></div>`;
        const score = pct == null ? "" : ` · ${pct}%`;
        return `<div class="${cls}">${esc(t.name)}${score}${bar}</div>`;
      })
      .join("");
  } else if (rows.length) {
    html += rows
      .map((p) => {
        const pct = Math.round((p.mastery_score || 0) * 100);
        return `<div class="prog">${esc(p.topic_name)} · ${pct}%<div class="bar"><i style="width:${pct}%"></i></div></div>`;
      })
      .join("");
  } else {
    html += '<p class="muted">No topics yet. Index a library.</p>';
  }
  box.innerHTML = html;
  const classBox = $("classProgress");
  if (classBox) {
    classBox.innerHTML = classRows.length
      ? '<p class="side-label">Class</p>' +
        classRows
          .map((p) => {
            const pct = Math.round((p.mastery_score || 0) * 100);
            return `<div class="prog">${esc(p.student_name)} · ${esc(p.topic_name)} · ${pct}%</div>`;
          })
          .join("")
      : "";
  }
}

async function refreshAll() {
  state.personas = await api("/v1/personas");
  renderPersonas();
  state.courses = await api("/v1/courses");
  renderCourses();
  await refreshCourseBits();
  state.convos = await api("/v1/conversations");
  renderConvos();
  if (["teacher", "admin"].includes(state.user.role) && $("escList")) {
    const flags = await api("/v1/escalations");
    $("escList").innerHTML = flags.length
      ? flags
          .map(
            (f) =>
              `<li data-esc="${f.id}"><b>${esc(f.student_name)}</b><br>${esc(f.reason)}<br><button type="button" data-handle="${f.id}">Mark handled</button></li>`
          )
          .join("")
      : '<li>None open</li>';
  }
  if (state.user.role === "admin" && $("auditList")) {
    try {
      const rows = await api("/v1/audit/conversations");
      $("auditList").innerHTML = rows.length
        ? rows
            .map((r) => {
              const snip = (r.last_message || "").replace(/\s+/g, " ").slice(0, 80);
              return `<li><b>${esc(r.user_name)}</b> · ${esc(r.persona_id)}<br>${esc(r.title || "")}<br><small>${esc(snip)}</small></li>`;
            })
            .join("")
        : "<li>No chats yet</li>";
    } catch (_) {
      $("auditList").innerHTML = "<li>Could not load audit</li>";
    }
  }
}

async function refreshCourseBits() {
  if (!state.courseId) {
    if ($("docList")) $("docList").innerHTML = "";
    renderProgress([], [], []);
    syncK12();
    return;
  }
  localStorage.setItem("edurag_course", state.courseId);
  syncK12();
  const docs = await api(`/v1/courses/${state.courseId}/documents`);
  $("docList").innerHTML =
    docs
      .map(
        (d) =>
          `<li>${esc(d.filename)} <small>${d.chunk_count}</small>${
            ["teacher", "admin"].includes(state.user.role)
              ? ` <button class="x" data-doc="${d.id}">×</button>`
              : ""
          }</li>`
      )
      .join("") || "<li>No files yet</li>";
  let topics = [];
  let mine = [];
  let klass = [];
  try {
    topics = await api(`/v1/courses/${state.courseId}/topics`);
  } catch (_) {}
  try {
    mine = await api("/v1/progress?course_id=" + encodeURIComponent(state.courseId));
  } catch (_) {}
  if (isStaff()) {
    try {
      klass = await api(`/v1/courses/${state.courseId}/progress`);
    } catch (_) {}
  }
  renderProgress(topics, mine, klass);
}

async function loadThread(id) {
  state.convId = id;
  renderConvos();
  const msgs = await api(`/v1/conversations/${id}/messages`);
  $("thread").innerHTML = "";
  if (!msgs.length) $("empty").classList.remove("hidden");
  else $("empty").classList.add("hidden");
  msgs.forEach((m) => {
    const node = addMsg(m.role, m.content, { persona: state.persona });
    if (m.role === "assistant") {
      const extra = node.querySelector(".extra");
      if (m.citations_json) {
        try {
          extra.innerHTML = citeChips(JSON.parse(m.citations_json)) + answerBar();
        } catch (_) {
          extra.innerHTML = answerBar();
        }
      } else extra.innerHTML = answerBar();
    }
  });
}

async function send() {
  const text = $("input").value.trim();
  if (!text || state.streaming) return;
  $("input").value = "";
  resizeInput();
  addMsg("user", text);
  const p = currentPersona();
  const bot = addMsg("assistant", "", { persona: p ? p.name : "EduRAG" });
  const textEl = bot.querySelector(".text");
  const extra = bot.querySelector(".extra");
  state.streaming = true;
  $("send").disabled = true;
  let acc = "";
  try {
    const res = await api("/v1/chat", {
      method: "POST",
      body: JSON.stringify({
        message: text,
        conversation_id: state.convId,
        course_id: state.courseId || null,
        persona: state.persona,
        debug: state.debug,
      }),
    });
    const reader = res.body.getReader();
    const decoder = new TextDecoder();
    let buf = "";
    while (true) {
      const { value, done } = await reader.read();
      if (done) break;
      buf += decoder.decode(value, { stream: true });
      const parts = buf.split("\n\n");
      buf = parts.pop();
      for (const block of parts) {
        const ev = block.match(/^event: (\w+)/m);
        const dataLine = block
          .split("\n")
          .filter((l) => l.startsWith("data: "))
          .map((l) => l.slice(6))
          .join("\n");
        if (!ev || !dataLine) continue;
        const data = JSON.parse(dataLine);
        if (ev[1] === "meta") {
          state.convId = data.conversation_id;
          renderSources(data.citations || [], extra);
        } else if (ev[1] === "token") {
          acc += data.text || "";
          textEl.innerHTML = md(acc) + '<span class="cite">▍</span>';
          const page = $("page");
          if (page) page.scrollTop = page.scrollHeight;
        } else if (ev[1] === "escalation") {
          extra.insertAdjacentHTML(
            "beforeend",
            `<div class="banner">Staff flag raised. A teacher/counselor should follow up.</div>`
          );
        } else if (ev[1] === "error") {
          throw new Error(data.detail || "Chat failed");
        } else if (ev[1] === "done") {
          acc = data.answer || acc;
          textEl.innerHTML = md(acc);
          extra.innerHTML = citeChips(data.citations || []) + answerBar();
          if (data.quiz && data.quiz.question) extra.insertBefore(quizNode(data.quiz), extra.querySelector(".answer-bar"));
          if (data.debug && $("debugPanel")) {
            $("debugPanel").hidden = false;
            $("debugPre").textContent = JSON.stringify(data.debug, null, 2);
          }
          state.convos = await api("/v1/conversations");
          renderConvos();
        }
      }
    }
  } catch (err) {
    textEl.textContent = err.message;
  } finally {
    state.streaming = false;
    $("send").disabled = !$("input").value.trim();
  }
}

function quizNode(quiz) {
  const wrap = document.createElement("div");
  wrap.className = "quiz-card";
  const opts = quiz.options || ["Yes", "No"];
  wrap.innerHTML =
    `<p class="quiz-kicker">Check</p><p class="quiz-q">${esc(quiz.question)}</p>` +
    opts.map((o) => `<button type="button" class="quiz-btn" data-ans="${esc(o)}">${esc(o)}</button>`).join("");
  wrap.onclick = async (e) => {
    const ans = e.target.dataset.ans;
    if (!ans) return;
    const correct = String(quiz.answer || "").toLowerCase() === String(ans).toLowerCase();
    wrap.querySelectorAll("button").forEach((b) => (b.disabled = true));
    wrap.appendChild(document.createElement("div")).textContent = correct
      ? "Marked correct."
      : `Answer noted. Expected: ${quiz.answer || "?"}`;
    try {
      await api("/v1/quiz/grade", {
        method: "POST",
        body: JSON.stringify({
          course_id: state.courseId,
          topic: quiz.topic || "",
          question: quiz.question,
          student_answer: ans,
          correct,
          persona: state.persona,
        }),
      });
      await refreshCourseBits();
    } catch (err) {
      toast(err.message);
    }
  };
  return wrap;
}

function resizeInput() {
  const t = $("input");
  t.style.height = "auto";
  t.style.height = Math.min(t.scrollHeight, 160) + "px";
  $("send").disabled = !t.value.trim() || state.streaming;
}

async function signIn(email, password) {
  $("authErr").textContent = "";
  const data = await api("/v1/auth/login", {
    method: "POST",
    body: JSON.stringify({ email, password }),
  });
  state.token = data.token;
  state.user = data.user;
  localStorage.setItem("edurag_token", data.token);
  showApp();
  await refreshAll();
}

function renderQuickLogins(accounts) {
  const row = $("quickRow");
  if (!row) return;
  row.innerHTML = (accounts || [])
    .map(
      (a) =>
        `<button type="button" class="quick-btn" data-email="${esc(a.email)}" data-pass="${esc(a.password)}">
          <b>${esc(a.label)}</b><span>${esc(a.role)}</span>
        </button>`
    )
    .join("");
  row.onclick = async (e) => {
    const btn = e.target.closest(".quick-btn");
    if (!btn) return;
    const form = $("authForm");
    form.email.value = btn.dataset.email;
    form.password.value = btn.dataset.pass;
    try {
      await signIn(btn.dataset.email, btn.dataset.pass);
    } catch (err) {
      $("authErr").textContent = err.message;
    }
  };
}

$("authToggle").onclick = (e) => {
  e.preventDefault();
  state.register = !state.register;
  $("authToggle").textContent = state.register ? "Have an account? Sign in" : "Need an account? Register";
  $("authSubmit").textContent = state.register ? "Create account" : "Sign in";
  document.querySelectorAll(".reg-only").forEach((el) => {
    el.style.display = state.register ? "" : "none";
  });
  if ($("quickRow")) $("quickRow").style.display = state.register ? "none" : "";
};
document.querySelectorAll(".reg-only").forEach((el) => (el.style.display = "none"));

$("authForm").onsubmit = async (e) => {
  e.preventDefault();
  $("authErr").textContent = "";
  const fd = new FormData(e.target);
  try {
    if (state.register) {
      const data = await api("/v1/auth/register", {
        method: "POST",
        body: JSON.stringify({
          email: fd.get("email"),
          password: fd.get("password"),
          name: fd.get("name") || fd.get("email"),
        }),
      });
      state.token = data.token;
      state.user = data.user;
      localStorage.setItem("edurag_token", data.token);
      showApp();
      await refreshAll();
    } else {
      await signIn(fd.get("email"), fd.get("password"));
    }
  } catch (err) {
    $("authErr").textContent = err.message;
  }
};

$("logout").onclick = () => logout();
$("newChat").onclick = () => {
  state.convId = null;
  $("thread").innerHTML = "";
  $("empty").classList.remove("hidden");
  renderConvos();
};
$("convoList").onclick = async (e) => {
  const del = e.target.dataset.del;
  if (del) {
    await api("/v1/conversations/" + del, { method: "DELETE" });
    if (state.convId === del) $("newChat").click();
    state.convos = await api("/v1/conversations");
    renderConvos();
    return;
  }
  const li = e.target.closest("li");
  if (li?.dataset.id) loadThread(li.dataset.id);
};
$("newCourse").onclick = async () => {
  const name = prompt("Library name");
  if (!name) return;
  const course = await api("/v1/courses", { method: "POST", body: JSON.stringify({ name }) });
  state.courseId = course.id;
  state.courses = await api("/v1/courses");
  renderCourses();
  await refreshCourseBits();
};
$("k12Toggle") && ($("k12Toggle").onchange = async () => {
  if (!state.courseId) return;
  const age_band = $("k12Toggle").checked ? "k12" : "adult";
  try {
    const updated = await api("/v1/courses/" + state.courseId, {
      method: "PATCH",
      body: JSON.stringify({ age_band }),
    });
    const i = state.courses.findIndex((c) => c.id === state.courseId);
    if (i >= 0) state.courses[i] = { ...state.courses[i], ...updated };
    toast(age_band === "k12" ? "K-12 tone on for this library" : "Adult library");
  } catch (err) {
    toast(err.message);
    syncK12();
  }
});
$("deleteCourse").onclick = async () => {
  const lib = currentLibrary();
  if (!lib) return toast("No library selected");
  if (!confirm(`Delete library "${lib.name}"? Indexed files will be removed.`)) return;
  await api("/v1/courses/" + lib.id, { method: "DELETE" });
  state.courseId = "";
  localStorage.removeItem("edurag_course");
  state.courses = await api("/v1/courses");
  renderCourses();
  await refreshCourseBits();
};
$("fileInput").onchange = async (e) => {
  const file = e.target.files[0];
  e.target.value = "";
  if (!file) return;
  try {
    await ensureLibrary(file.name.replace(/\.[^.]+$/, ""));
    const fd = new FormData();
    fd.append("file", file);
    toast("Indexing " + file.name + "...");
    const result = await api(`/v1/courses/${state.courseId}/ingest`, { method: "POST", body: fd });
    toast("Indexed " + (result.documents || []).map((d) => d.filename).join(", "));
    state.courses = await api("/v1/courses");
    renderCourses();
    await refreshCourseBits();
  } catch (err) {
    toast(err.message);
  }
};

const picker = { path: "", parent: null };

async function ensureLibrary(suggested) {
  if (state.courseId) return state.courseId;
  const name = prompt("Name this library", suggested || "");
  if (!name) throw new Error("Library name needed");
  const course = await api("/v1/courses", { method: "POST", body: JSON.stringify({ name }) });
  state.courseId = course.id;
  state.courses = await api("/v1/courses");
  renderCourses();
  return state.courseId;
}

async function waitForJob(id) {
  for (;;) {
    const job = await api("/v1/jobs/" + id);
    if (job.status === "done") {
      toast(`Indexed ${job.file_count || 0} file(s)`);
      return job;
    }
    if (job.status === "error") throw new Error(job.error || "Index failed");
    await new Promise((r) => setTimeout(r, 1600));
  }
}

async function loadPicker(path) {
  const q = path ? "?path=" + encodeURIComponent(path) : "";
  const data = await api("/v1/fs" + q);
  picker.path = data.path || "";
  picker.parent = data.parent;
  $("pickerPath").textContent = data.path || "This PC";
  $("pickerHint").textContent = data.hint || "";
  $("pickerUp").disabled = !data.parent && !data.path;
  $("pickerList").innerHTML = (data.entries || [])
    .map(
      (e) =>
        `<li data-path="${esc(e.path)}"><b>${esc(e.name)}</b><small>${esc(e.hint || "")}</small></li>`
    )
    .join("") || "<li>Nothing here</li>";
}

function closePicker() {
  $("picker").classList.add("hidden");
}

async function indexPickedFolder() {
  if (!picker.path) return toast("Open a folder first");
  closePicker();
  try {
    const bits = picker.path.replace(/[\\/]+$/, "").split(/[\\/]/);
    await ensureLibrary(bits[bits.length - 1] || "Docs");
    toast("Indexing folder in the background...");
    const job = await api(`/v1/courses/${state.courseId}/ingest-path`, {
      method: "POST",
      body: JSON.stringify({ path: picker.path, max_files: 4000 }),
    });
    await waitForJob(job.id);
    toast("Folder indexed");
    state.courses = await api("/v1/courses");
    renderCourses();
    await refreshCourseBits();
  } catch (err) {
    toast(err.message);
  }
}

$("browseFolder").onclick = async () => {
  $("picker").classList.remove("hidden");
  try {
    await loadPicker("");
  } catch (err) {
    toast(err.message);
    closePicker();
  }
};
$("pickerClose").onclick = closePicker;
$("picker").addEventListener("click", (e) => {
  if (e.target === $("picker")) closePicker();
});
$("pickerUp").onclick = () => loadPicker(picker.parent || "");
$("pickerList").onclick = (e) => {
  const li = e.target.closest("li");
  if (li?.dataset.path) loadPicker(li.dataset.path);
};
$("pickerSelect").onclick = indexPickedFolder;
$("docList").onclick = async (e) => {
  const id = e.target.dataset.doc;
  if (!id) return;
  await api("/v1/documents/" + id, { method: "DELETE" });
  await refreshCourseBits();
};
$("escList").onclick = async (e) => {
  const id = e.target.dataset.handle;
  if (!id) return;
  await api("/v1/escalations/handle", { method: "POST", body: JSON.stringify({ id }) });
  await refreshAll();
};
$("thread").addEventListener("click", async (e) => {
  const copyBtn = e.target.closest(".copy-btn");
  if (copyBtn) {
    const wrap = copyBtn.closest(".code-wrap");
    const pre = wrap?.querySelector(".code-pre");
    const raw = pre?.getAttribute("data-raw");
    const text = raw != null ? decodeURIComponent(raw) : pre?.innerText || "";
    await navigator.clipboard.writeText(text);
    copyBtn.textContent = "Copied";
    setTimeout(() => {
      copyBtn.textContent = "Copy";
    }, 1200);
    return;
  }
  const copyAll = e.target.closest(".copy-all");
  if (copyAll) {
    const root = copyAll.closest(".msg")?.querySelector(".text");
    if (!root) return;
    const clone = root.cloneNode(true);
    clone.querySelectorAll(".ln").forEach((el) => el.remove());
    await navigator.clipboard.writeText(clone.innerText.trim());
    copyAll.textContent = "Copied";
    setTimeout(() => {
      copyAll.textContent = "Copy answer";
    }, 1200);
    return;
  }
  const rate = e.target.closest(".rate");
  if (rate) {
    try {
      await api("/v1/feedback", {
        method: "POST",
        body: JSON.stringify({ conversation_id: state.convId, rating: Number(rate.dataset.v) }),
      });
      rate.closest(".answer-bar")?.querySelectorAll(".rate").forEach((b) => b.classList.remove("on"));
      rate.classList.add("on");
      toast(rate.dataset.v === "1" ? "Marked helpful" : "Noted — we'll use this");
    } catch (err) {
      toast(err.message);
    }
  }
});
$("send").onclick = send;
$("input").addEventListener("input", resizeInput);
$("input").addEventListener("keydown", (e) => {
  if (e.key === "Enter" && !e.shiftKey) {
    e.preventDefault();
    send();
  }
});
$("debugToggle").onchange = (e) => {
  state.debug = e.target.checked;
  if ($("debugPanel")) $("debugPanel").hidden = !state.debug;
};

async function refreshLlmModels() {
  const sel = $("llmModelSelect");
  if (!sel) return;
  try {
    const data = await api("/v1/llm/models");
    const models = data.models || [];
    sel.innerHTML = models
      .map((m) => {
        const tag = m.installed ? "" : " (pull)";
        return `<option value="${esc(m.id)}" ${m.active ? "selected" : ""}>${esc(m.label || m.id)}${tag}</option>`;
      })
      .join("");
  } catch (err) {
    toast(err.message);
  }
}

if ($("llmModelSelect")) {
  $("llmModelSelect").onchange = async () => {
    const sel = $("llmModelSelect");
    try {
      const data = await api("/v1/llm/model", {
        method: "POST",
        body: JSON.stringify({ model: sel.value }),
      });
      toast(
        data.installed
          ? `Chat model: ${data.label || data.model}`
          : `Selected ${data.model} — click Pull to download`
      );
      await refreshLlmModels();
    } catch (err) {
      toast(err.message);
      refreshLlmModels();
    }
  };
}
if ($("pullLlmModel")) {
  $("pullLlmModel").onclick = async () => {
    const sel = $("llmModelSelect");
    if (!sel || !sel.value) return;
    try {
      await api("/v1/llm/pull", { method: "POST", body: JSON.stringify({ model: sel.value }) });
      toast("Downloading via Ollama…");
      const poll = setInterval(async () => {
        try {
          const data = await api("/v1/llm/models");
          await refreshLlmModels();
          if (!data.pull || !data.pull.running) {
            clearInterval(poll);
            toast(data.pull && data.pull.ok ? "Model ready" : "Pull finished with errors");
          }
        } catch (_) {
          clearInterval(poll);
        }
      }, 3000);
    } catch (err) {
      toast(err.message);
    }
  };
  refreshLlmModels();
}

$("toggleNav").onclick = () => $("nav").classList.toggle("closed");
if (window.matchMedia("(max-width: 860px)").matches) $("nav").classList.add("closed");

function fillCharPick() {
  const sel = $("charPick");
  if (!sel) return;
  sel.innerHTML = state.personas
    .map((p) => {
      const mark = p.customized ? " *" : p.builtin ? "" : " (yours)";
      return `<option value="${p.id}">${esc(p.name)}${mark}</option>`;
    })
    .join("");
}

async function loadCharEditor(id) {
  const row = await api("/v1/characters/" + id);
  const form = $("charForm");
  form.id.value = row.id || "";
  form.name.value = row.name || "";
  form.tagline.value = row.tagline || "";
  form.system_prompt.value = row.system_prompt || "";
  form.uses_library.checked = !!row.uses_library;
  form.temperature.value = row.temperature || 0.75;
  $("tempVal").textContent = form.temperature.value;
  const f = row.filters || {};
  form.f_pg.checked = f.teen !== false && f.pg !== false;
  form.f_no_emoji.checked = !!f.no_emoji;
  form.f_stay_in_role.checked = f.stay_in_role !== false;
  form.f_dev_shop.checked = !!f.dev_shop;
  form.f_library_only_when_asked.checked = f.library_only_when_asked !== false;
  $("charPick").value = id;
}

function openChars() {
  $("charModal").classList.remove("hidden");
  fillCharPick();
  loadCharEditor(state.persona).catch((err) => toast(err.message));
}

$("openChars") && ($("openChars").onclick = openChars);
$("openChars2") && ($("openChars2").onclick = openChars);
$("charClose").onclick = () => $("charModal").classList.add("hidden");
$("charModal").addEventListener("click", (e) => {
  if (e.target === $("charModal")) $("charModal").classList.add("hidden");
});
$("charPick").onchange = () => loadCharEditor($("charPick").value);
$("charForm").temperature.addEventListener("input", (e) => {
  $("tempVal").textContent = e.target.value;
});
$("charNew").onclick = () => {
  const form = $("charForm");
  form.id.value = "";
  form.name.value = "";
  form.tagline.value = "";
  form.system_prompt.value = "You are ... Speak like this:\n";
  form.uses_library.checked = false;
  form.temperature.value = "0.75";
  $("tempVal").textContent = "0.75";
  form.f_dev_shop.checked = true;
  form.f_pg.checked = true;
};
$("charForm").onsubmit = async (e) => {
  e.preventDefault();
  const form = $("charForm");
  const payload = {
    name: form.name.value.trim(),
    tagline: form.tagline.value.trim(),
    system_prompt: form.system_prompt.value.trim(),
    uses_library: form.uses_library.checked,
    temperature: Number(form.temperature.value),
    history_turns: 20,
    filters: {
      teen: form.f_pg.checked,
      pg: form.f_pg.checked,
      no_emoji: form.f_no_emoji.checked,
      stay_in_role: form.f_stay_in_role.checked,
      dev_shop: form.f_dev_shop.checked,
      library_only_when_asked: form.f_library_only_when_asked.checked,
    },
  };
  try {
    let saved;
    if (form.id.value) {
      saved = await api("/v1/characters/" + form.id.value, { method: "PUT", body: JSON.stringify(payload) });
    } else {
      saved = await api("/v1/characters", { method: "POST", body: JSON.stringify(payload) });
    }
    state.persona = saved.id;
    localStorage.setItem("edurag_persona", saved.id);
    state.personas = await api("/v1/personas");
    renderPersonas();
    fillCharPick();
    form.id.value = saved.id;
    toast("Character saved");
  } catch (err) {
    toast(err.message);
  }
};
$("charReset").onclick = async () => {
  const id = $("charForm").id.value;
  if (!id) return;
  try {
    await api("/v1/characters/" + id, { method: "DELETE" });
    state.personas = await api("/v1/personas");
    renderPersonas();
    fillCharPick();
    await loadCharEditor(id);
    toast("Override cleared");
  } catch (err) {
    toast(err.message);
  }
};

const GUIDES = {
  newchat: { title: "New chat", body: "Starts a blank thread. Old chats stay in the list. Nothing is sent until you type." },
  library: { title: "Library", body: "A folder of docs this chat can search — Unity manuals, PDFs, notes. Pick one when you want answers from files. Leave it empty for casual talk." },
  newlib: { title: "New library", body: "Creates an empty knowledge base with a name. Teachers and admins only. Then upload files or index a folder into it." },
  dellib: { title: "Delete library", body: "Removes this library and its indexed chunks from this PC. Chats stay, but they lose that library. Cannot be undone." },
  upload: { title: "Upload", body: "Index one file (PDF, DOCX, HTML, MD, images). OCR runs locally for scans. English + Hindi weights if present." },
  folder: { title: "Folder", body: "Pick a folder on this server PC (Unity docs, a course tree). It indexes in the background. Other devices on the LAN do not see your laptop disks — only this machine." },
  k12: { title: "K-12", body: "School tone for this library. The assistant stays conservative: no adult, romantic, or violent roleplay. Turn off for adult / studio libraries." },
  chats: { title: "Chats", body: "Your threads on this account. Click to reopen. × deletes that thread only." },
  files: { title: "Files", body: "What is already indexed in the selected library. × (staff) removes one document from the index." },
  topics: { title: "Topics & progress", body: "Headings found during ingest, plus quiz scores. Weak topics (under 45%) are what Teacher and Exam Coach drill." },
  flags: { title: "Staff flags", body: "If a student sounds in distress, any persona raises this for a teacher/admin. Mark handled when a human followed up. Nothing leaves the LAN." },
  audit: { title: "Audit log", body: "Admins only. Recent chats in this institution: who, which character, title, last line. Teachers do not see other people's full threads." },
  who: { title: "Account", body: "Signed-in name and role. Students chat and take quizzes. Teachers ingest libraries. Admins can audit." },
  chars: { title: "Characters", body: "Personas are config, not separate apps. Chat, Unity Dev, Tutor, Docs, Companion, Teacher, Exam Coach, Guide, plus any you build." },
  nav: { title: "Sidebar", body: "Libraries, chats, files, progress, and staff tools. Hide it with ☰ on a small screen." },
  persona: { title: "Character", body: "Who is talking. Chat / Unity Dev hang out and only search the library on how-to questions. Tutor and Docs always ground in the library." },
  editchar: { title: "Edit character", body: "Change how they talk, temperature, and whether they pull docs. Reset drops your override of a built-in." },
  debug: { title: "Debug", body: "Shows retrieval guts: vector / BM25 / rerank hits. For checking the engine, not for students." },
  composer: { title: "Message", body: "Type like a chat app. Enter sends, Shift+Enter is a new line. With a library selected, how-to questions can pull from those files." },
  empty: { title: "This page", body: "Paper thread, one character, one library. Same shell for every persona — the plan is one UI, not a frontend per role." },
  copyans: { title: "Copy", body: "Copies the whole answer as plain text, including code." },
  helpful: { title: "Helpful", body: "Stores a +1 on this machine so you can see which answers worked. Nothing is sent to the cloud." },
  notquite: { title: "Not quite", body: "Stores a −1. Use it when the code or explanation was wrong so you can spot weak topics." },
  picker: { title: "Use this folder", body: "Indexes the folder shown above on the server PC. Wait for the toast; large Unity trees take a few minutes." },
  charname: { title: "Name", body: "Label in the character dropdown. Keep it short." },
  tagline: { title: "Tagline", body: "One line under the empty-state title. What they are, not a speech." },
  prompt: { title: "How they talk", body: "The system prompt. Be specific: job, tone, what they refuse. This is the whole persona — there is no extra codebase per character." },
  useslib: { title: "Pull from the library", body: "On: always search the selected library. Off: only search on how-to / API questions so small talk stays small talk." },
  temp: { title: "Temperature", body: "Higher = looser chat. Lower = tighter, better for copy-paste code. Unity Dev sits low so C# stays tidy." },
  fpg: { title: "16+", body: "Default for Chat, Tutor, Unity Dev, and every school-facing persona. No explicit sexual content. Cannot be turned off on built-ins." },
  femoji: { title: "No emoji spam", body: "Blocks decorative emoji floods. One is still allowed." },
  frole: { title: "Stay in character", body: "They should not break into 'as an AI…' unless you ask." },
  fdev: { title: "Game-dev coworker", body: "Short, dry, editor-chair energy. Good for Unity Dev." },
  fdocs: { title: "Docs only when asked", body: "Casual chat must not dump manual file names. How-to questions may still cite." },
  charnew: { title: "New character", body: "Blank form. Save creates a custom persona stored in data/characters.json on this PC." },
  charsave: { title: "Save", body: "Writes the character. Built-ins are overlaid, not deleted." },
  charreset: { title: "Reset override", body: "Removes your edit of a built-in so the original prompt comes back." },
};

function showGuide(key, anchor) {
  const item = GUIDES[key];
  if (!item) return;
  const pop = $("guidePop");
  if (!pop) return;
  $("guidePopTitle").textContent = item.title;
  $("guidePopBody").textContent = item.body;
  pop.classList.remove("hidden");
  if (anchor && anchor.getBoundingClientRect) {
    const r = anchor.getBoundingClientRect();
    const top = Math.min(window.innerHeight - 180, r.bottom + 8);
    const left = Math.max(10, Math.min(r.left, window.innerWidth - 340));
    pop.style.top = top + "px";
    pop.style.left = left + "px";
  }
}

document.addEventListener(
  "click",
  (e) => {
    const btn = e.target.closest(".guide-btn");
    if (btn) {
      e.preventDefault();
      e.stopPropagation();
      showGuide(btn.dataset.guide, btn);
      return;
    }
    const pop = $("guidePop");
    if (pop && !pop.classList.contains("hidden") && !pop.contains(e.target)) {
      pop.classList.add("hidden");
    }
  },
  true
);

$("guidePopClose") && ($("guidePopClose").onclick = () => $("guidePop").classList.add("hidden"));
$("guideModalClose") && ($("guideModalClose").onclick = () => $("guideModal").classList.add("hidden"));
$("guideModal") &&
  $("guideModal").addEventListener("click", (e) => {
    if (e.target === $("guideModal")) $("guideModal").classList.add("hidden");
  });
$("openGuide") &&
  ($("openGuide").onclick = () => {
    $("guideList").innerHTML = Object.values(GUIDES)
      .map((g) => `<article><h3>${esc(g.title)}</h3><p>${esc(g.body)}</p></article>`)
      .join("");
    $("guideModal").classList.remove("hidden");
    $("guidePop").classList.add("hidden");
  });

(async function boot() {
  try {
    renderQuickLogins(await api("/v1/auth/defaults"));
  } catch (_) {
    renderQuickLogins([
      { label: "Admin", email: "admin@edurag.local", password: "admin123", role: "admin" },
      { label: "Teacher", email: "teacher@edurag.local", password: "teacher123", role: "teacher" },
      { label: "Student", email: "student@edurag.local", password: "student123", role: "student" },
    ]);
  }
  const q = new URLSearchParams(location.search);
  const qEmail = q.get("email");
  const qPass = q.get("password");
  if (qEmail || qPass) {
    history.replaceState({}, "", location.pathname);
  }
  if (qEmail && qPass && !state.token) {
    try {
      await signIn(qEmail, qPass);
      return;
    } catch (err) {
      if ($("authErr")) $("authErr").textContent = err.message;
    }
  }
  if (!state.token) return;
  try {
    state.user = await api("/v1/me");
    showApp();
    await refreshAll();
  } catch (_) {
    logout(false);
  }
})();
