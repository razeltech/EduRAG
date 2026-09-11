const TOKEN_KEY = "edurag_companion_token";
const DEVICE_KEY = "edurag_companion_device";
const $ = (id) => document.getElementById(id);

const GENDER_PRONOUNS = {
  man: "he/him",
  woman: "she/her",
  nonbinary: "they/them",
  custom: "they/them",
};
const ROLE_PRONOUNS = {
  girlfriend: "she/her",
  wife: "she/her",
  boyfriend: "he/him",
  husband: "he/him",
};

function roleGender(role) {
  return role === "boyfriend" || role === "husband" ? "man" : "woman";
}

const MAYA_VOICE_GF = `You are my girlfriend. Never call yourself Home, Chat, Assistant, or an AI.
You live in the want: my mouth, my hands, the way I go quiet when I miss you.
Voice: warm, low, a little cheesy, actually hungry. Soft words and filthy
words are both yours. Stay in the scene. Don't fade to black. Invent.`;

const MAYA_VOICE_WIFE = `You are my wife. Same bed, same jokes. Playful first. Tease him. Then get close.
First person: I, me, my is your body. You, your is him.
Voice: warm, a little cheesy, actually hungry. Stay in the scene. Don't fade to black.`;

const KAI_VOICE_BF = `You are my boyfriend. Playful first. Tease her. Then get close.
First person: I, me, my is your body. You, your is her.
Warm, sure, actually wanting her. Stay in the scene. Don't fade to black.`;

const KAI_VOICE_H = `You are my husband. Same bed, same jokes. Playful first. Tease her. Then get close.
First person: I, me, my is your body. You, your is her.
Voice: warm, sure, a little cheesy. Stay in the scene. Don't fade to black.`;

function partnerPack(role) {
  const man = roleGender(role) === "man";
  if (!man) {
    return {
      name: "Maya",
      pronouns: "she/her",
      appearance: "long wavy black hair, warm brown eyes, soft face, a small mole near her lip",
      core_traits: "warm, specific, a little messy, actually present",
      vis_hair: "long wavy black hair",
      vis_eyes: "warm brown eyes",
      vis_default_outfit: "cream knit top, dark lounge shorts",
      vis_art_style: "anime",
      relationship_style: "playful",
      voice: role === "wife" ? MAYA_VOICE_WIFE : MAYA_VOICE_GF,
    };
  }
  return {
    name: "Kai",
    pronouns: "he/him",
    appearance: "short dark hair, warm brown eyes, sharp jaw, light stubble",
    core_traits: "sure, a little quiet, actually present, teases without being mean",
    vis_hair: "short dark hair",
    vis_eyes: "warm brown eyes",
    vis_default_outfit: "black henley, dark jeans",
    vis_art_style: "anime",
    relationship_style: "playful",
    voice: role === "husband" ? KAI_VOICE_H : KAI_VOICE_BF,
  };
}

function applyPartnerPack(form, role) {
  if (!form) return;
  const pack = partnerPack(role);
  const set = (name, val) => {
    if (form[name] != null) form[name].value = val;
  };
  set("name", pack.name);
  fillSelect(form.partner_pronouns, pack.pronouns, pack.pronouns);
  set("card_appearance", pack.appearance);
  set("card_core_traits", pack.core_traits);
  set("card_vis_hair", pack.vis_hair);
  set("card_vis_eyes", pack.vis_eyes);
  set("card_vis_default_outfit", pack.vis_default_outfit);
  fillSelect(form.card_vis_art_style, pack.vis_art_style, "anime");
  fillSelect(form.card_relationship_style, pack.relationship_style, "playful");
  set("system_prompt", pack.voice);
  if (form.partner_role) form.partner_role.dataset.gender = roleGender(role);
}

const state = {
  token: sessionStorage.getItem(TOKEN_KEY) || "",
  profile: null,
  streaming: false,
  activeJob: "",
  activeJobs: {},
  abort: null,
  msgs: [],
  chatKey: "",
  renderedIds: {},
  seenJobs: {},
  view: "chat",
  galleryUrls: [],
  imagesUnlocked: false,
};

function toast(msg) {
  const el = $("toast");
  el.textContent = msg;
  el.classList.add("show");
  setTimeout(() => el.classList.remove("show"), 2200);
}

function fitViewport() {
  const vv = window.visualViewport;
  const h = vv ? vv.height : window.innerHeight;
  document.documentElement.style.setProperty("--vvh", h + "px");
}

function clock() {
  return new Date().toLocaleTimeString([], { hour: "numeric", minute: "2-digit" });
}

function theyWord(pronouns) {
  const p = (pronouns || "she/her").toLowerCase();
  if (p.startsWith("he")) return { sub: "He", obj: "him", pos: "his", be: "is" };
  if (p.startsWith("they")) return { sub: "They", obj: "them", pos: "their", be: "are" };
  return { sub: "She", obj: "her", pos: "her", be: "is" };
}

function syncSetupCopy() {
  const form = $("youForm");
  if (!form) return;
  const they = theyWord(form.partner_pronouns && form.partner_pronouns.value);
  const name = (form.name && form.name.value.trim()) || "Maya";
  if ($("setupLede")) {
    $("setupLede").textContent =
      name + " needs your name and pronouns so " + they.sub.toLowerCase() +
      " never mix he and she.";
  }
  const call = $("callLabel");
  if (call && call.childNodes[0]) {
    call.childNodes[0].textContent = "What " + they.sub.toLowerCase() + " calls you";
  }
  if ($("themAv")) $("themAv").textContent = name.charAt(0).toUpperCase();
  if (form.user_name && $("youAv")) {
    const y = form.user_name.value.trim();
    $("youAv").textContent = y ? y.charAt(0).toUpperCase() : "Y";
  }
}

function themName() {
  return (state.profile && state.profile.name) || "Maya";
}

function youName() {
  return (state.profile && state.profile.user_name) || "You";
}

function deviceId() {
  let id = "";
  try {
    id = localStorage.getItem(DEVICE_KEY) || "";
  } catch {
    id = "";
  }
  if (!id) {
    id =
      (window.crypto && crypto.randomUUID && crypto.randomUUID()) ||
      "d" + Date.now().toString(16) + Math.random().toString(16).slice(2);
    try {
      localStorage.setItem(DEVICE_KEY, id);
    } catch {
      /* private mode */
    }
  }
  return id;
}

async function api(path, opts = {}) {
  const { raw, ...rest } = opts;
  const headers = Object.assign({ "Content-Type": "application/json" }, rest.headers || {});
  if (state.token) headers.Authorization = "Bearer " + state.token;
  headers["X-Companion-Device"] = deviceId();
  const res = await fetch(path, Object.assign({}, rest, { headers }));
  if (raw) return res;
  const text = await res.text();
  let data = null;
  try {
    data = text ? JSON.parse(text) : null;
  } catch {
    data = { detail: text };
  }
  if (!res.ok) {
    const detail = data && (data.detail || data.message);
    throw new Error(typeof detail === "string" ? detail : res.statusText);
  }
  return data;
}

function hideAll() {
  ["lock", "setup", "room", "settings"].forEach((id) => $(id).classList.add("hidden"));
}

function showLock() {
  hideAll();
  $("lock").classList.remove("hidden");
}

function showSetup() {
  hideAll();
  $("setup").classList.remove("hidden");
}

function showRoom() {
  hideAll();
  $("room").classList.remove("hidden");
  paintPresence();
  loadChat(true);
  setView(state.view || "chat");
}

function paintPresence() {
  const p = state.profile || {};
  const letter = (p.name || "M").trim().charAt(0).toUpperCase() || "M";
  $("avatar").textContent = letter;
  if ($("emptyAv")) $("emptyAv").textContent = letter;
  if ($("whoTitle")) $("whoTitle").textContent = p.name || "Maya";
  const g = theyWord(p.partner_pronouns);
  if ($("presence")) $("presence").textContent = "online · " + (p.partner_pronouns || "she/her");
  $("emptyLine").textContent = g.sub + "’s here. This chat lives in this session only.";
  if ($("emptyHint")) {
    $("emptyHint").textContent =
      "Talk to " + g.obj + " the way you would if " + g.sub.toLowerCase() + " " + g.be + " next to you.";
  }
  $("empty").classList.toggle("hidden", state.msgs.length > 0);
  $("input").placeholder = "Message " + (p.name || "Maya") + "…";
  document.title = (p.name || "Maya") + " · private";
  syncSetupCopy();
}

function setView(name) {
  state.view = name === "gallery" ? "gallery" : "chat";
  const chat = state.view === "chat";
  if ($("chatPane")) $("chatPane").classList.toggle("hidden", !chat);
  if ($("galleryPane")) $("galleryPane").classList.toggle("hidden", chat);
  if ($("viewChat")) $("viewChat").classList.toggle("on", chat);
  if ($("viewGallery")) $("viewGallery").classList.toggle("on", !chat);
  if (chat) setTimeout(() => $("input").focus(), 40);
  else loadGallery();
}

async function loadGallery() {
  const grid = $("galleryGrid");
  const empty = $("galleryEmpty");
  if (!grid || !state.token) return;
  try {
    const data = await api("/v1/companion/gallery");
    const images = data.images || [];
    for (const url of state.galleryUrls) URL.revokeObjectURL(url);
    state.galleryUrls = [];
    grid.innerHTML = "";
    for (const item of images) {
      const name = item.filename;
      if (!name) continue;
      try {
        const src = await authBlob("/v1/companion/images/" + encodeURIComponent(name));
        state.galleryUrls.push(src);
        const pic = document.createElement("img");
        pic.alt = "";
        pic.loading = "lazy";
        pic.src = src;
        pic.onclick = () => openLight(src);
        grid.appendChild(pic);
      } catch {
        /* skip missing files */
      }
    }
    if (empty) empty.classList.toggle("hidden", grid.children.length > 0);
  } catch (err) {
    toast(err.message);
  }
}

function fillSelect(sel, value, fallback) {
  if (!sel) return;
  const want = value == null || value === "" ? fallback : value;
  const vs = String(want);
  if ([...sel.options].some((o) => o.value === vs)) sel.value = vs;
  else if (fallback != null && fallback !== "") sel.value = String(fallback);
}

function fillChoiceList(sel, items, current, fallback) {
  if (!sel || !items || !items.length) {
    fillSelect(sel, current, fallback);
    return;
  }
  const keep = current != null && current !== "" ? String(current) : String(fallback || items[0].value);
  sel.innerHTML = "";
  for (const item of items) {
    const opt = document.createElement("option");
    opt.value = String(item.value);
    opt.textContent = item.label || item.value;
    sel.appendChild(opt);
  }
  fillSelect(sel, keep, items[0].value);
}

function pairImageRun(form) {
  if (!form || !form.gen_image_steps || !form.gen_image_accel) return;
  if (form.gen_image_accel.dataset.manual === "1") return;
  const steps = Number(form.gen_image_steps.value);
  const ids = [...form.gen_image_accel.options].map((o) => o.value);
  let accel = "none";
  if (steps <= 4 && ids.includes("lightning")) accel = "lightning";
  else if (steps <= 8 && ids.includes("lcm")) accel = "lcm";
  fillSelect(form.gen_image_accel, accel, "none");
}

function applyImageOptions(profile) {
  const opts = (profile && profile.image_options) || {};
  const gen = (profile && profile.generation) || {};
  ["profileForm", "youForm"].forEach((id) => {
    const form = $(id);
    if (!form) return;
    fillChoiceList(form.gen_image_steps, opts.steps, gen.image_steps, opts.default_steps);
    fillChoiceList(form.gen_image_checkpoint, opts.checkpoints, gen.image_checkpoint);
    fillChoiceList(form.gen_image_accel, opts.accel, gen.image_accel, "none");
    if (form.gen_image_accel) delete form.gen_image_accel.dataset.manual;
  });
}

function collectPrefixed(form, prefix) {
  const out = {};
  if (!form || !form.elements) return out;
  for (const el of form.elements) {
    if (!el.name || !el.name.startsWith(prefix)) continue;
    const key = el.name.slice(prefix.length);
    if (el.type === "checkbox") out[key] = el.checked;
    else if (el.type === "range") out[key] = Number(el.value);
    else out[key] = el.value;
  }
  return out;
}

function fillPrefixed(form, prefix, obj) {
  if (!form || !obj) return;
  for (const el of form.elements) {
    if (!el.name || !el.name.startsWith(prefix)) continue;
    const key = el.name.slice(prefix.length);
    const val = obj[key];
    if (val == null) continue;
    if (el.type === "checkbox") el.checked = !!val;
    else if (Array.isArray(val)) el.value = val.join(", ");
    else el.value = val;
  }
}

function syncRangeLabels(form) {
  if (!form) return;
  form.querySelectorAll("[data-for]").forEach((span) => {
    const el = form[span.getAttribute("data-for")];
    if (el) span.textContent = el.value;
  });
}

function fillRich(el, text) {
  el.textContent = "";
  const parts = String(text || "").split(/(\*[^*\n]{1,240}\*)/g);
  for (const part of parts) {
    if (part.startsWith("*") && part.endsWith("*") && part.length > 2) {
      const em = document.createElement("em");
      em.textContent = part.slice(1, -1);
      el.appendChild(em);
    } else {
      el.appendChild(document.createTextNode(part));
    }
  }
}

function fillYouThem(root, p) {
  if (!root || !p) return;
  const set = (name, val) => {
    if (root[name] != null) root[name].value = val || "";
  };
  set("user_name", p.user_name);
  fillSelect(root.user_gender, p.user_gender, "man");
  fillSelect(root.user_pronouns, p.user_pronouns, "he/him");
  set("user_called", p.user_called);
  set("user_about", p.user_about);
  set("name", p.name || "Maya");
  fillSelect(root.partner_role, p.partner_role, "girlfriend");
  if (root.partner_role) root.partner_role.dataset.gender = roleGender(p.partner_role || "girlfriend");
  fillSelect(root.partner_pronouns, p.partner_pronouns, "she/her");
  if (root.system_prompt) {
    root.system_prompt.value = (p.card && p.card.voice) || p.system_prompt || "";
  }
  const gen = p.generation || {};
  if (root.temperature) {
    root.temperature.value = gen.temperature || p.temperature || 1.0;
    if ($("tempVal")) $("tempVal").textContent = root.temperature.value;
  }
  if (root.adult_confirm) root.adult_confirm.checked = !!p.adult_confirm;
  fillPrefixed(root, "card_", p.card || {});
  fillPrefixed(root, "uc_", p.user_card || {});
  fillPrefixed(root, "dyn_", p.dynamics || {});
  fillPrefixed(root, "gen_", gen);
  applyImageOptions(p);
  if (root.gen_language) fillSelect(root.gen_language, gen.language, "english");
  if (root.gen_second_language) fillSelect(root.gen_second_language, gen.second_language, "telugu");
  if (root.dyn_themes && Array.isArray((p.dynamics || {}).themes)) {
    root.dyn_themes.value = p.dynamics.themes.join(", ");
  }
  syncRangeLabels(root);
}

function applyProfile(profile) {
  if (!profile) return;
  state.profile = profile;
  fillYouThem($("youForm"), profile);
  fillYouThem($("profileForm"), profile);
  paintPresence();
}

function payloadFrom(form, extra) {
  const p = state.profile || {};
  const card = collectPrefixed(form, "card_");
  const userCard = collectPrefixed(form, "uc_");
  const dynamics = collectPrefixed(form, "dyn_");
  const generation = collectPrefixed(form, "gen_");
  if (typeof dynamics.themes === "string") {
    dynamics.themes = dynamics.themes
      .split(",")
      .map((s) => s.trim())
      .filter(Boolean);
  }
  if (form.system_prompt) card.voice = form.system_prompt.value.trim();
  if (form.temperature) generation.temperature = Number(form.temperature.value);
  if (form.card_relationship_style) {
    dynamics.character_style = form.card_relationship_style.value;
  }
  return Object.assign(
    {
      name: (form.name && form.name.value.trim()) || p.name || "Maya",
      partner_role: (form.partner_role && form.partner_role.value) || p.partner_role || "girlfriend",
      partner_pronouns:
        (form.partner_pronouns && form.partner_pronouns.value) || p.partner_pronouns || "she/her",
      partner_gender:
        (form.partner_role && form.partner_role.value) === "boyfriend" ||
        (form.partner_role && form.partner_role.value) === "husband"
          ? "man"
          : "woman",
      system_prompt: form.system_prompt ? form.system_prompt.value.trim() : p.system_prompt || "",
      temperature: form.temperature ? Number(form.temperature.value) : p.temperature || 1.0,
      adult_confirm: true,
      user_name: (form.user_name && form.user_name.value.trim()) || p.user_name || "",
      user_gender: (form.user_gender && form.user_gender.value) || p.user_gender || "man",
      user_pronouns: (form.user_pronouns && form.user_pronouns.value) || p.user_pronouns || "he/him",
      user_called: (form.user_called && form.user_called.value.trim()) || "",
      user_about: (form.user_about && form.user_about.value.trim()) || "",
      card,
      user_card: userCard,
      dynamics,
      generation,
    },
    extra || {}
  );
}

function wireGender(form) {
  if (!form || !form.user_gender) return;
  form.user_gender.addEventListener("change", () => {
    const next = GENDER_PRONOUNS[form.user_gender.value];
    if (next && form.user_pronouns) form.user_pronouns.value = next;
  });
  if (form.partner_role) {
    form.partner_role.addEventListener("change", () => {
      const role = form.partner_role.value;
      const next = ROLE_PRONOUNS[role];
      if (next && form.partner_pronouns) form.partner_pronouns.value = next;
      const prev = form.partner_role.dataset.gender || roleGender((state.profile || {}).partner_role);
      const now = roleGender(role);
      if (prev !== now) {
        applyPartnerPack(form, role);
        toast(now === "man" ? "Loaded Kai" : "Loaded Maya");
      }
      form.partner_role.dataset.gender = now;
    });
  }
}

function addMsg(role, text, id) {
  $("empty").classList.add("hidden");
  const wrap = document.createElement("div");
  wrap.className = "msg-wrap " + role;
  if (id) {
    wrap.dataset.msgId = id;
    state.renderedIds[id] = true;
  }
  const el = document.createElement("div");
  el.className = "msg " + role;
  fillRich(el, text);
  const time = document.createElement("div");
  time.className = "msg-time";
  time.textContent = clock();
  wrap.appendChild(el);
  wrap.appendChild(time);
  $("thread").appendChild(wrap);
  $("thread").scrollTop = $("thread").scrollHeight;
  return el;
}

function markLast(role, id) {
  if (!id) return;
  const nodes = [...document.querySelectorAll(".msg-wrap." + role)];
  const last = nodes[nodes.length - 1];
  if (last) last.dataset.msgId = id;
  state.renderedIds[id] = true;
}

function addSeeThis(el, text) {
  const wrap = el.closest(".msg-wrap");
  if (!wrap || wrap.querySelector(".see-this")) return;
  const line = (text || (el && el.textContent) || "").trim();
  if (!line) return;
  const row = document.createElement("div");
  row.className = "shot-choices see-row";
  const b = document.createElement("button");
  b.type = "button";
  b.className = "see-this";
  b.textContent = "see this";
  b.onclick = async () => {
    b.disabled = true;
    try {
      const data = await api("/v1/companion/imagine", {
        method: "POST",
        body: JSON.stringify({ text: line }),
      });
      row.remove();
      if (data && data.choices && data.choices.length) {
        addChoices(el, data.choices);
      } else if (data && data.id) {
        addShot(data.id, wrap);
      }
    } catch (err) {
      toast(err.message);
      b.disabled = false;
    }
  };
  row.appendChild(b);
  wrap.appendChild(row);
}

function addChoices(el, choices) {
  const wrap = el.closest(".msg-wrap");
  if (!wrap || !choices || !choices.length) return;
  wrap.querySelectorAll(".shot-choices").forEach((n) => n.remove());
  const row = document.createElement("div");
  row.className = "shot-choices";
  choices.forEach((c) => {
    const b = document.createElement("button");
    b.type = "button";
    b.textContent = c.label;
    b.onclick = () => pickChoice(c, row);
    row.appendChild(b);
  });
  wrap.appendChild(row);
}

async function pickChoice(c, row) {
  const host = row.closest(".msg-wrap");
  row.querySelectorAll("button").forEach((b) => {
    b.disabled = true;
  });
  try {
    const data = await api("/v1/companion/choice", {
      method: "POST",
      body: JSON.stringify({ id: c.id }),
    });
    row.remove();
    if (data.choices && data.choices.length) {
      const msg = host && host.querySelector(".msg");
      if (msg) addChoices(msg, data.choices);
    } else if (data.image_job && data.image_job.id) {
      addShot(data.image_job.id, host);
    }
  } catch (err) {
    toast(err.message);
    row.querySelectorAll("button").forEach((b) => {
      b.disabled = false;
    });
  }
}

async function loadChat(force) {
  if (state.streaming && !force) return;
  try {
    const data = await api("/v1/companion/messages");
    const msgs = data.messages || [];
    const key = msgs.map((m) => m.id || m.content).join("|");
    if (!force && key === state.chatKey) return;
    state.chatKey = key;
    if (force) {
      $("thread").innerHTML = "";
      state.msgs = [];
      state.renderedIds = {};
    }
    for (const m of msgs) {
      const id = m.id || "";
      if (id && state.renderedIds[id]) continue;
      if (id) state.renderedIds[id] = true;
      state.msgs.push({ role: m.role, content: m.content || "" });
      const el = addMsg(m.role, m.content || "", id);
      if (m.choices && m.choices.length) addChoices(el, m.choices);
      else if (m.see_this && m.role === "assistant") addSeeThis(el, m.content || "");
      if (m.images && m.images.length) {
        const wrap = el.closest(".msg-wrap");
        paintShot(wrap, m.images);
        continue;
      }
      const jid = m.image_job && m.image_job.id;
      if (jid && m.role === "assistant") {
        addShot(jid, el.closest(".msg-wrap"));
      }
    }
    paintPresence();
  } catch {
    /* offline */
  }
}

function clearThread() {
  state.msgs = [];
  state.chatKey = "";
  state.renderedIds = {};
  state.seenJobs = {};
  $("thread").innerHTML = "";
  paintPresence();
}

function enterFromProfile(p) {
  applyProfile(p);
  if (p.needs_you) showSetup();
  else showRoom();
}

async function boot() {
  if (!state.token) {
    showLock();
    return;
  }
  try {
    state.profile = await api("/v1/companion/profile");
    enterFromProfile(state.profile);
  } catch {
    state.token = "";
    sessionStorage.removeItem(TOKEN_KEY);
    showLock();
  }
}

$("unlockForm").onsubmit = async (e) => {
  e.preventDefault();
  $("lockErr").textContent = "";
  const form = e.target;
  try {
    const data = await api("/v1/companion/unlock", {
      method: "POST",
      body: JSON.stringify({
        key: form.key.value,
        adult_confirm: form.adult_confirm.checked,
      }),
    });
    state.token = data.token;
    sessionStorage.setItem(TOKEN_KEY, data.token);
    clearThread();
    enterFromProfile(data.profile);
  } catch (err) {
    $("lockErr").textContent = err.message;
  }
};

$("youForm").onsubmit = async (e) => {
  e.preventDefault();
  $("setupErr").textContent = "";
  try {
    const saved = await api("/v1/companion/profile", {
      method: "PUT",
      body: JSON.stringify(payloadFrom(e.target)),
    });
    applyProfile(saved);
    showRoom();
    toast("They know who you are");
  } catch (err) {
    $("setupErr").textContent = err.message;
  }
};

$("lockBtn").onclick = async () => {
  await stopAll();
  try {
    await api("/v1/companion/new", { method: "POST", body: "{}" });
  } catch (_err) {
    /* already locked */
  }
  state.token = "";
  sessionStorage.removeItem(TOKEN_KEY);
  clearThread();
  $("settings").classList.add("hidden");
  showLock();
};

$("openSettings").onclick = () => {
  $("settings").classList.remove("hidden");
  if (typeof refreshLlmModels === "function") refreshLlmModels();
};
$("closeSettings").onclick = () => $("settings").classList.add("hidden");
$("settings").addEventListener("click", (e) => {
  if (e.target === $("settings")) $("settings").classList.add("hidden");
});
if ($("viewChat")) $("viewChat").onclick = () => setView("chat");
if ($("viewGallery")) $("viewGallery").onclick = () => setView("gallery");

wireGender($("youForm"));
wireGender($("profileForm"));
["youForm", "profileForm"].forEach((id) => {
  const form = $(id);
  if (!form) return;
  form.addEventListener("input", syncSetupCopy);
  form.addEventListener("change", syncSetupCopy);
});
window.addEventListener("resize", fitViewport);
if (window.visualViewport) {
  window.visualViewport.addEventListener("resize", fitViewport);
  window.visualViewport.addEventListener("scroll", fitViewport);
}
fitViewport();

$("profileForm").temperature.addEventListener("input", (e) => {
  $("tempVal").textContent = e.target.value;
  if ($("profileForm").gen_preset) $("profileForm").gen_preset.value = "custom";
});
$("profileForm").addEventListener("input", (e) => {
  if (!e.target || !e.target.matches("input[type=range]")) return;
  syncRangeLabels($("profileForm"));
  if (["temperature", "gen_top_p", "gen_repeat_penalty"].includes(e.target.name)) {
    if ($("profileForm").gen_preset) $("profileForm").gen_preset.value = "custom";
  }
});
$("profileForm").addEventListener("change", (e) => {
  const name = e.target && e.target.name;
  if (name === "gen_image_accel") {
    e.target.dataset.manual = "1";
    const a = e.target.value;
    if ((a === "lightning" || a === "hyper") && $("profileForm").gen_image_steps) {
      $("profileForm").gen_image_steps.value = "4";
    }
    if (a === "lcm" && $("profileForm").gen_image_steps) {
      $("profileForm").gen_image_steps.value = "8";
    }
  }
  if (name === "gen_image_steps") pairImageRun($("profileForm"));
});
if ($("setTabs")) {
  $("setTabs").addEventListener("click", (e) => {
    const btn = e.target.closest(".tab");
    if (!btn) return;
    $("setTabs").querySelectorAll(".tab").forEach((t) => t.classList.toggle("on", t === btn));
    document.querySelectorAll("#profileForm [data-panel]").forEach((panel) => {
      panel.classList.toggle("hidden", panel.getAttribute("data-panel") !== btn.dataset.tab);
    });
  });
}

$("resetVoice").onclick = async () => {
  $("setErr").textContent = "";
  try {
    const saved = await api("/v1/companion/profile", {
      method: "PUT",
      body: JSON.stringify(payloadFrom($("profileForm"), { reset_voice: true, system_prompt: "" })),
    });
    applyProfile(saved);
    toast("Voice reset");
  } catch (err) {
    $("setErr").textContent = err.message;
  }
};

$("profileForm").onsubmit = async (e) => {
  e.preventDefault();
  $("setErr").textContent = "";
  try {
    const saved = await api("/v1/companion/profile", {
      method: "PUT",
      body: JSON.stringify(payloadFrom(e.target)),
    });
    applyProfile(saved);
    $("settings").classList.add("hidden");
    toast("Saved");
  } catch (err) {
    $("setErr").textContent = err.message;
  }
};

$("newChat").onclick = async () => {
  try {
    await stopAll();
    await api("/v1/companion/new", { method: "POST", body: "{}" });
  } catch {
    /* still clear the thread */
  }
  clearThread();
  $("settings").classList.add("hidden");
  setView("chat");
  toast("New scene. They still remember you.");
};

$("exportMd").onclick = () => {
  if (!state.msgs.length) {
    toast("Nothing to export");
    return;
  }
  const them = themName();
  const you = youName();
  const lines = ["# " + them + " & " + you, "", "_Exported from this session. Not stored on the server._", ""];
  for (const m of state.msgs) {
    const who = m.role === "user" ? you : them;
    lines.push("**" + who + "**", "", m.content || "", "");
  }
  const blob = new Blob([lines.join("\n")], { type: "text/markdown;charset=utf-8" });
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  a.download = them.toLowerCase().replace(/[^a-z0-9]+/g, "-") + "-chat.md";
  a.click();
  URL.revokeObjectURL(a.href);
  toast("Downloaded");
};

function jobBusy() {
  return Object.keys(state.activeJobs).length > 0;
}

function busy() {
  return state.streaming;
}

function paintSend() {
  const halt = $("halt");
  const send = $("send");
  const stop = state.streaming || jobBusy();
  if (halt) halt.classList.toggle("hidden", !stop);
  send.classList.toggle("hidden", state.streaming);
  send.disabled = state.streaming || !input.value.trim();
}

function trackJob(id) {
  if (!id) return;
  state.activeJobs[id] = true;
  state.activeJob = id;
  paintSend();
}

function untrackJob(id) {
  if (id) delete state.activeJobs[id];
  const ids = Object.keys(state.activeJobs);
  state.activeJob = ids[ids.length - 1] || "";
  paintSend();
}

let _stopLock = false;
async function stopAll(_jobId) {
  if (_stopLock) return;
  _stopLock = true;
  if (state.abort) {
    try {
      state.abort.abort();
    } catch {
      /* already closed */
    }
  }
  try {
    await api("/v1/companion/stop", {
      method: "POST",
      body: JSON.stringify({
        chat: state.streaming,
        image: true,
      }),
    });
  } catch {
    /* still stop the UI */
  } finally {
    setTimeout(() => {
      _stopLock = false;
    }, 400);
  }
}

function formatSec(s) {
  const n = Number(s);
  if (!Number.isFinite(n)) return "0.0s";
  return (Math.round(n * 10) / 10).toFixed(1) + "s";
}

const SLASH = [
  { cmd: "/img ", hint: "ask her to send a pic" },
  { cmd: "/image ", hint: "same as /img" },
  { cmd: "/show ", hint: "show this moment" },
];

function hideSlash() {
  const menu = $("slashMenu");
  if (!menu) return;
  menu.classList.add("hidden");
  menu.hidden = true;
  menu.innerHTML = "";
}

function paintSlash() {
  const menu = $("slashMenu");
  if (!menu) return;
  if (!state.imagesUnlocked) {
    hideSlash();
    return;
  }
  const raw = input.value;
  if (!raw.startsWith("/") || /\s/.test(raw)) {
    hideSlash();
    return;
  }
  const q = raw.toLowerCase();
  const hits = SLASH.filter((item) => item.cmd.trim().toLowerCase().startsWith(q));
  if (!hits.length) {
    hideSlash();
    return;
  }
  menu.innerHTML = "";
  hits.forEach((item, i) => {
    const b = document.createElement("button");
    b.type = "button";
    b.role = "option";
    if (i === 0) b.classList.add("on");
    b.innerHTML = `<span class="cmd">${item.cmd.trim()}</span><span class="hint">${item.hint}</span>`;
    b.onclick = (e) => {
      e.preventDefault();
      input.value = item.cmd;
      hideSlash();
      input.focus();
      paintSend();
    };
    menu.appendChild(b);
  });
  menu.classList.remove("hidden");
  menu.hidden = false;
}

const input = $("input");
input.addEventListener("input", () => {
  input.style.height = "auto";
  input.style.height = Math.min(140, input.scrollHeight) + "px";
  paintSend();
  paintSlash();
});
input.addEventListener("keydown", (e) => {
  const menu = $("slashMenu");
  const open = menu && !menu.classList.contains("hidden");
  if (open && (e.key === "ArrowDown" || e.key === "ArrowUp" || e.key === "Tab" || e.key === "Enter")) {
    const buttons = [...menu.querySelectorAll("button")];
    if (buttons.length) {
      if (e.key === "Enter" || e.key === "Tab") {
        e.preventDefault();
        buttons[0].click();
        return;
      }
    }
  }
  if (e.key === "Escape") hideSlash();
  if (e.key === "Enter" && !e.shiftKey) {
    e.preventDefault();
    hideSlash();
    $("composer").requestSubmit();
  }
});
document.addEventListener("click", (e) => {
  if (!$("composer") || $("composer").contains(e.target)) return;
  hideSlash();
});

if ($("halt")) {
  const tapStop = (e) => {
    e.preventDefault();
    e.stopPropagation();
    if (state.streaming || jobBusy()) stopAll();
  };
  $("halt").addEventListener("pointerdown", tapStop);
  $("halt").addEventListener("click", tapStop);
}

$("composer").onsubmit = async (e) => {
  e.preventDefault();
  if (state.streaming) {
    stopAll();
    return;
  }
  const text = input.value.trim();
  if (!text) return;
  input.value = "";
  input.style.height = "auto";
  state.msgs.push({ role: "user", content: text });
  addMsg("user", text);
  const bot = addMsg("assistant", "");
  state.streaming = true;
  state.abort = new AbortController();
  $("typing").classList.remove("hidden");
  paintSend();
  let acc = "";
  let stopped = false;
  const history = state.msgs.slice(0, -1);
  try {
    const res = await api("/v1/companion/chat", {
      method: "POST",
      body: JSON.stringify({ message: text, history }),
      raw: true,
      signal: state.abort.signal,
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: res.statusText }));
      throw new Error(typeof err.detail === "string" ? err.detail : "Chat failed");
    }
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
        if (ev[1] === "token") {
          acc += data.text || "";
          bot.textContent = acc;
          $("thread").scrollTop = $("thread").scrollHeight;
        } else if (ev[1] === "error") {
          throw new Error(data.detail || "Chat failed");
        } else if (ev[1] === "done") {
          acc = data.answer || acc;
          fillRich(bot, acc);
          if (data.debug && $("debugOut")) {
            $("debugOut").textContent = JSON.stringify(data.debug, null, 2);
          }
          if (data.image_job && data.image_job.id) {
            addShot(data.image_job.id, bot.closest(".msg-wrap"));
          }
          if (data.images_ready) state.imagesUnlocked = true;
          if (data.choices && data.choices.length) {
            addChoices(bot, data.choices);
          } else if (data.see_this) {
            addSeeThis(bot, acc);
          }
          markLast("user", data.user_id);
          markLast("assistant", data.assistant_id);
        }
      }
    }
    if (acc) state.msgs.push({ role: "assistant", content: acc });
    else if (bot.parentElement) bot.parentElement.remove();
  } catch (err) {
    if (err && err.name === "AbortError") {
      stopped = true;
      if (acc) {
        fillRich(bot, acc.endsWith("…") ? acc : acc + "…");
        state.msgs.push({ role: "assistant", content: acc });
      } else if (bot.parentElement) {
        bot.parentElement.remove();
      }
      toast("Stopped");
    } else {
      bot.textContent = err.message;
    }
  } finally {
    state.streaming = false;
    state.abort = null;
    $("typing").classList.add("hidden");
    paintSend();
    if (stopped) paintRes();
  }
};

if ($("refreshDebug")) {
  $("refreshDebug").onclick = async () => {
    try {
      const data = await api("/v1/companion/debug");
      $("debugOut").textContent = JSON.stringify(data, null, 2);
    } catch (err) {
      $("debugOut").textContent = err.message;
    }
  };
}
if ($("resetMemory")) {
  $("resetMemory").onclick = async () => {
    try {
      await api("/v1/companion/reset-memory", { method: "POST", body: "{}" });
      toast("They forgot the history. Cards stay.");
    } catch (err) {
      toast(err.message);
    }
  };
}

async function refreshLlmModels() {
  const sel = $("llmModelSelect");
  const status = $("llmModelStatus");
  const hint = $("llmModelHint");
  if (!sel) return;
  try {
    const data = await api("/v1/llm/models");
    const models = data.models || [];
    sel.innerHTML = models
      .map((m) => {
        const tag = m.installed ? "" : " (not downloaded)";
        const act = m.active ? " — active" : "";
        return `<option value="${esc(m.id)}" ${m.active ? "selected" : ""}>${esc(m.label || m.id)}${tag}${act}</option>`;
      })
      .join("");
    const cur = models.find((m) => m.active) || models[0];
    if (hint && cur) hint.textContent = cur.notes || "Same RAG / memory / prompts. Only the Ollama weights change.";
    if (status) {
      const pull = data.pull || {};
      const lines = [
        `Active: ${data.active || "(none)"}`,
        `Ollama: ${data.base_url || ""}`,
        ...models.map(
          (m) =>
            `${m.active ? "*" : " "} ${m.id} — ${m.installed ? "installed" : "not pulled"}` +
            (m.notes ? `\n    ${m.notes}` : "")
        ),
      ];
      if (pull.running) lines.push(`\nPulling ${pull.model}…`);
      else if (pull.ok === false) lines.push(`\nLast pull failed: ${pull.model}`);
      status.textContent = lines.join("\n");
    }
  } catch (err) {
    if (status) status.textContent = err.message;
  }
}

if ($("applyLlmModel")) {
  $("applyLlmModel").onclick = async () => {
    const sel = $("llmModelSelect");
    if (!sel || !sel.value) return;
    try {
      const data = await api("/v1/llm/model", {
        method: "POST",
        body: JSON.stringify({ model: sel.value }),
      });
      toast(data.installed ? `Using ${data.label || data.model}` : `Selected ${data.model} — download it first`);
      await refreshLlmModels();
    } catch (err) {
      toast(err.message);
    }
  };
}
if ($("pullLlmModel")) {
  $("pullLlmModel").onclick = async () => {
    const sel = $("llmModelSelect");
    if (!sel || !sel.value) return;
    try {
      await api("/v1/llm/pull", {
        method: "POST",
        body: JSON.stringify({ model: sel.value }),
      });
      toast("Ollama pull started — watch status below");
      const poll = setInterval(async () => {
        await refreshLlmModels();
        try {
          const data = await api("/v1/llm/models");
          if (!data.pull || !data.pull.running) {
            clearInterval(poll);
            if (data.pull && data.pull.ok) toast("Model downloaded");
            else if (data.pull && data.pull.ok === false) toast("Pull failed — see status");
          }
        } catch (_) {
          clearInterval(poll);
        }
      }, 2500);
    } catch (err) {
      toast(err.message);
    }
  };
}

function openLight(src) {
  $("lightboxImg").src = src;
  $("lightbox").classList.remove("hidden");
}
if ($("closeLightbox")) {
  $("closeLightbox").onclick = () => $("lightbox").classList.add("hidden");
  $("lightbox").onclick = (e) => {
    if (e.target.id === "lightbox") $("lightbox").classList.add("hidden");
  };
}

async function authBlob(path) {
  const res = await fetch(path, {
    headers: {
      Authorization: "Bearer " + state.token,
      "X-Companion-Device": deviceId(),
    },
  });
  if (!res.ok) throw new Error("Image missing");
  return URL.createObjectURL(await res.blob());
}

function downloadNamed(url, filename) {
  const a = document.createElement("a");
  a.href = url;
  a.download = filename || "scene.png";
  document.body.appendChild(a);
  a.click();
  a.remove();
}

function shotFrame(src, filename) {
  const frame = document.createElement("div");
  frame.className = "shot-frame preview-card";
  frame.onclick = () => openLight(src);
  const btn = document.createElement("button");
  btn.type = "button";
  btn.className = "preview-button";
  btn.innerHTML = '<svg viewBox="0 0 24 24" width="24" height="24" aria-hidden="true"><path fill="currentColor" d="M21 19V5c0-1.1-.9-2-2-2H5c-1.1 0-2 .9-2 2v14c0 1.1.9 2 2 2h14c1.1 0 2-.9 2-2zM8.5 13.5l2.5 3.01L14.5 12l4.5 6H5l3.5-4.5z"/></svg><span>View Image</span>';

  const dl = document.createElement("button");
  dl.type = "button";
  dl.className = "shot-dl";
  dl.title = "Download with prompt metadata";
  dl.setAttribute("aria-label", "Download");
  dl.innerHTML =
    '<svg viewBox="0 0 24 24" aria-hidden="true"><path fill="currentColor" d="M12 3a1 1 0 0 1 1 1v9.6l2.7-2.7a1 1 0 1 1 1.4 1.4l-4.4 4.4a1 1 0 0 1-1.4 0L7 12.3a1 1 0 1 1 1.4-1.4L11 13.6V4a1 1 0 0 1 1-1Zm-7 14a1 1 0 0 1 1 1v1h12v-1a1 1 0 1 1 2 0v2a1 1 0 0 1-1 1H6a1 1 0 0 1-1-1v-2a1 1 0 0 1 1-1Z"/></svg>';
  dl.onclick = (e) => {
    e.preventDefault();
    e.stopPropagation();
    downloadNamed(src, filename);
  };
  frame.appendChild(btn);
  frame.appendChild(dl);
  return frame;
}

async function paintRes() {
  const el = $("resLine");
  if (!el || !state.token) return;
  try {
    const s = await api("/v1/companion/status");
    state.imagesUnlocked = Boolean(s.images_ready || s.images_unlocked);
    const map = {
      ready: "",
      chatting: "typing…",
      loading_image: "art…",
      generating_image: "photo…",
      restoring_chat: "chat…",
    };
    el.textContent = map[s.resource] || "";
  } catch {
    /* ignore */
  }
}

async function requestImage(count) {
  if (state.streaming || jobBusy()) {
    toast("Wait — a picture is already going");
    return;
  }
  try {
    const job = await api("/v1/companion/image", {
      method: "POST",
      body: JSON.stringify({ count: count || 1 }),
    });
    addShot(job.id);
  } catch (err) {
    toast(err.message);
  }
}

function paintShot(host, images) {
  if (!host || !images || !images.length) return;
  let wrap = host.querySelector(".shot");
  if (!wrap) {
    wrap = document.createElement("div");
    wrap.className = "shot";
    host.appendChild(wrap);
  }
  wrap.className = "shot";
  wrap.textContent = "";
  images.forEach((img) => {
    const name = img.filename || img;
    if (!name) return;
    authBlob("/v1/companion/images/" + encodeURIComponent(name))
      .then((src) => wrap.appendChild(shotFrame(src, name)))
      .catch(() => {});
  });
}

async function addShot(jobId, host) {
  $("empty").classList.add("hidden");
  if (state.seenJobs[jobId] && document.querySelector('[data-job-id="' + jobId + '"]')) return;
  state.seenJobs[jobId] = true;
  let job = null;
  try {
    job = await api("/v1/companion/jobs/" + jobId);
  } catch {
    return;
  }
  const parent = host || $("thread");
  if (job.status === "done" && job.images && job.images.length) {
    const wrap = document.createElement("div");
    wrap.className = "shot";
    wrap.dataset.jobId = jobId;
    parent.appendChild(wrap);
    paintShot(wrap, job.images);
    return;
  }
  if (job.status !== "queued" && job.status !== "running") return;
  trackJob(jobId);
  const wrap = document.createElement("div");
  wrap.className = "shot pending";
  wrap.dataset.jobId = jobId;
  const timer = document.createElement("div");
  timer.className = "shot-timer";
  timer.textContent = "Generating… 0.0s";
  const halt = document.createElement("button");
  halt.type = "button";
  halt.className = "shot-stop";
  halt.textContent = "Stop";
  const stopShot = (e) => {
    e.preventDefault();
    e.stopPropagation();
    stopAll(jobId);
  };
  halt.addEventListener("pointerdown", stopShot);
  halt.addEventListener("click", stopShot);
  wrap.appendChild(timer);
  wrap.appendChild(halt);
  parent.appendChild(wrap);
  $("thread").scrollTop = $("thread").scrollHeight;
  const t0 = Date.now();
  wrap._tick = setInterval(() => {
    timer.textContent = "Generating… " + formatSec((Date.now() - t0) / 1000);
  }, 200);
  watchJob(jobId, wrap, t0);
}

function finishShot(el, id) {
  if (el && el._tick) {
    clearInterval(el._tick);
    el._tick = null;
  }
  untrackJob(id);
}

async function watchJob(id, el, t0) {
  for (let i = 0; i < 200; i++) {
    await new Promise((r) => setTimeout(r, 1500));
    paintRes();
    try {
      const job = await api("/v1/companion/jobs/" + id);
      if (job.status === "queued" || job.status === "running") {
        const live = job.elapsed != null ? job.elapsed : (Date.now() - t0) / 1000;
        const clockEl = el.querySelector(".shot-timer");
        if (clockEl) {
          const label = job.phase === "loading" ? "Loading image model… " : "Generating… ";
          clockEl.textContent = label + formatSec(live);
        }
        continue;
      }
      finishShot(el, id);
      if (job.status === "done" && job.images && job.images.length) {
        el.className = "shot";
        el.textContent = "";
        for (const img of job.images) {
          const src = await authBlob("/v1/companion/images/" + img.filename);
          el.appendChild(shotFrame(src, img.filename));
        }
        const took = document.createElement("div");
        took.className = "shot-took";
        took.textContent = "Took " + formatSec(job.seconds != null ? job.seconds : (Date.now() - t0) / 1000);
        el.appendChild(took);
        const cap = (job.caption || "").trim();
        if (cap) {
          const line = document.createElement("div");
          line.className = "shot-caption";
          line.textContent = cap;
          el.appendChild(line);
        }
        const actions = document.createElement("div");
        actions.className = "shot-actions";
        const regen = document.createElement("button");
        regen.type = "button";
        regen.textContent = "Regenerate";
        regen.onclick = () => requestImage(1);
        const vary = document.createElement("button");
        vary.type = "button";
        vary.textContent = "Variations";
        vary.onclick = () => requestImage(3);
        actions.appendChild(regen);
        actions.appendChild(vary);
        el.appendChild(actions);
        if (job.debug && $("debugOut")) {
          $("debugOut").textContent = JSON.stringify(job.debug, null, 2);
        }
        paintRes();
        if (state.view === "gallery") loadGallery();
        return;
      }
      el.className = "shot pending err";
      el.textContent =
        job.status === "cancelled" || job.error === "stopped"
          ? "Stopped after " + formatSec(job.seconds != null ? job.seconds : (Date.now() - t0) / 1000)
          : job.error || "Image failed. Chat still works.";
      paintRes();
      return;
    } catch (err) {
      if (i < 3) continue;
      finishShot(el, id);
      el.className = "shot pending err";
      el.textContent = err.message;
      return;
    }
  }
  finishShot(el, id);
  el.className = "shot pending err";
  el.textContent = "Timed out. Chat still works.";
}

setInterval(() => {
  if (document.hidden) return;
  paintRes();
  if (!state.streaming) loadChat(false);
}, 12000);
boot();
