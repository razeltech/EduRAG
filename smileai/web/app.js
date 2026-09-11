/**
 * SmileAI Educational Web Suite — Client Application Logic
 * Powered by Razel Tech | 100% Vanilla JavaScript (Zero Dependencies)
 */

document.addEventListener("DOMContentLoaded", () => {
  // Global Application State
  const state = {
    activeStream: "MPC",
    activeVoice: "en-IN-NeerjaExpressiveNeural",
    currentVocabWord: "",
    currentVocabTarget: null,
    vocabScore: 0,
    currentAudio: null,
  };

  // Elements
  const globalStreamSelect = document.getElementById("globalStreamSelect");
  const globalVoiceSelect = document.getElementById("globalVoiceSelect");
  const navTabs = document.querySelectorAll(".nav-tab");
  const tabPanes = document.querySelectorAll(".tab-pane");

  // ==============================================================================
  // 1. Navigation & Stream Switching
  // ==============================================================================

  navTabs.forEach(tab => {
    tab.addEventListener("click", () => {
      navTabs.forEach(t => t.classList.remove("active"));
      tabPanes.forEach(p => p.classList.remove("active"));

      tab.classList.add("active");
      const targetId = tab.getAttribute("data-tab");
      const targetPane = document.getElementById(targetId);
      if (targetPane) {
        targetPane.classList.add("active");
      }
    });
  });

  if (globalStreamSelect) {
    globalStreamSelect.addEventListener("change", (e) => {
      state.activeStream = e.target.value;
      const chatBadge = document.getElementById("chatStreamBadge");
      if (chatBadge) {
        chatBadge.textContent = `${state.activeStream} Stream`;
      }
      loadVocabChallenge();
    });
  }

  if (globalVoiceSelect) {
    globalVoiceSelect.addEventListener("change", (e) => {
      state.activeVoice = e.target.value;
    });
  }

  // ==============================================================================
  // 2. Audio Waveform & Speech Synthesis
  // ==============================================================================

  function setWaveformSpeaking(isSpeaking) {
    const bars = document.querySelectorAll(".wave-bar");
    const label = document.getElementById("voiceSpeakingLabel");
    bars.forEach(b => {
      if (isSpeaking) b.classList.add("speaking");
      else b.classList.remove("speaking");
    });
    if (label) {
      label.textContent = isSpeaking ? "Aarti Speaking..." : "Smiley Voice Ready";
    }
  }

  function playSmileyVoice(text) {
    if (!text || !text.trim()) return;

    if (state.currentAudio) {
      state.currentAudio.pause();
      state.currentAudio = null;
    }

    setWaveformSpeaking(true);

    const speakUrl = `/api/smileai/voice/speak?text=${encodeURIComponent(text.substring(0, 350))}&voice=${encodeURIComponent(state.activeVoice)}`;
    const audio = new Audio(speakUrl);
    state.currentAudio = audio;

    audio.onplay = () => setWaveformSpeaking(true);
    audio.onended = () => {
      setWaveformSpeaking(false);
      state.currentAudio = null;
    };
    audio.onerror = () => {
      // Fallback to browser speech synthesis if offline
      fallbackBrowserSpeech(text);
    };

    audio.play().catch(() => {
      fallbackBrowserSpeech(text);
    });
  }

  function fallbackBrowserSpeech(text) {
    if (!('speechSynthesis' in window)) {
      setWaveformSpeaking(false);
      return;
    }
    window.speechSynthesis.cancel();
    const cleanText = text.substring(0, 250);
    const utterance = new SpeechSynthesisUtterance(cleanText);
    utterance.rate = 0.85; // Warm, gentle rate
    utterance.pitch = 1.15; // Gentle smiling pitch

    const voices = window.speechSynthesis.getVoices();
    const preferred = voices.find(v => 
      v.name.toLowerCase().includes("aarti") || 
      v.name.toLowerCase().includes("neerja") || 
      v.name.toLowerCase().includes("india") || 
      v.lang.includes("en-IN")
    );
    if (preferred) utterance.voice = preferred;

    utterance.onstart = () => setWaveformSpeaking(true);
    utterance.onend = () => setWaveformSpeaking(false);
    utterance.onerror = () => setWaveformSpeaking(false);

    window.speechSynthesis.speak(utterance);
  }

  // ==============================================================================
  // 3. Student Chat with Smiley
  // ==============================================================================

  const chatMessages = document.getElementById("chatMessages");
  const chatInput = document.getElementById("chatInput");
  const sendChatBtn = document.getElementById("sendChatBtn");
  const micBtn = document.getElementById("micBtn");
  const clearChatBtn = document.getElementById("clearChatBtn");
  const replayVoiceBtn = document.getElementById("replayVoiceBtn");
  let lastAssistantReply = "Namaste! I am Smiley, your learning companion.";

  function appendChatMessage(sender, text) {
    const bubble = document.createElement("div");
    bubble.className = `chat-bubble ${sender}`;
    bubble.innerHTML = text.replace(/\n/g, "<br>");
    chatMessages.appendChild(bubble);
    chatMessages.scrollTop = chatMessages.scrollHeight;
  }

  async function handleSendChat() {
    const text = chatInput.value.trim();
    if (!text) return;

    appendChatMessage("student", text);
    chatInput.value = "";

    try {
      const res = await fetch("/api/smileai/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: jsonSafeStringify({
          message: text,
          stream: state.activeStream,
          student_name: "Student",
        }),
      });

      if (!res.ok) throw new Error("Chat request failed");
      const data = await res.json();

      appendChatMessage("assistant", data.content);
      lastAssistantReply = data.content;

      // Automatically speak first sentence with Aarti warm voice
      playSmileyVoice(data.content);
    } catch (e) {
      appendChatMessage("assistant", "I am happy to assist you! Please try asking another question.");
    }
  }

  if (sendChatBtn) sendChatBtn.addEventListener("click", handleSendChat);
  if (chatInput) {
    chatInput.addEventListener("keydown", (e) => {
      if (e.key === "Enter") handleSendChat();
    });
  }

  if (replayVoiceBtn) {
    replayVoiceBtn.addEventListener("click", () => {
      playSmileyVoice(lastAssistantReply);
    });
  }

  if (clearChatBtn) {
    clearChatBtn.addEventListener("click", () => {
      chatMessages.innerHTML = `
        <div class="chat-bubble assistant">
          <strong>Namaste! I am Smiley, your learning companion.</strong><br>
          Ask me any question from your syllabus, or drop an exam paper photo on the right to get a complete step-by-step solution!
        </div>
      `;
    });
  }

  // Native Microphone STT
  if (micBtn && ('webkitSpeechRecognition' in window || 'SpeechRecognition' in window)) {
    const SpeechRec = window.SpeechRecognition || window.webkitSpeechRecognition;
    const recognition = new SpeechRec();
    recognition.lang = "en-IN";
    recognition.interimResults = false;

    recognition.onresult = (event) => {
      const transcript = event.results[0][0].transcript;
      chatInput.value = transcript;
      micBtn.style.color = "";
    };

    recognition.onerror = () => { micBtn.style.color = ""; };
    recognition.onend = () => { micBtn.style.color = ""; };

    micBtn.addEventListener("click", () => {
      micBtn.style.color = "#dc2626";
      recognition.start();
    });
  }

  // ==============================================================================
  // 4. Snap & Solve Exam Paper Dropzone
  // ==============================================================================

  const dropzone = document.getElementById("dropzone");
  const fileInput = document.getElementById("fileInput");
  const solverStatus = document.getElementById("solverStatus");
  const solutionBox = document.getElementById("solutionBox");
  const solutionConcept = document.getElementById("solutionConcept");
  const solutionCitation = document.getElementById("solutionCitation");
  const solutionSteps = document.getElementById("solutionSteps");
  const teacherTipBox = document.getElementById("teacherTipBox");
  const listenSolutionBtn = document.getElementById("listenSolutionBtn");
  let currentSolutionSpeechText = "";

  if (dropzone && fileInput) {
    dropzone.addEventListener("click", () => fileInput.click());
    dropzone.addEventListener("dragover", (e) => {
      e.preventDefault();
      dropzone.classList.add("dragover");
    });
    dropzone.addEventListener("dragleave", () => dropzone.classList.remove("dragover"));
    dropzone.addEventListener("drop", (e) => {
      e.preventDefault();
      dropzone.classList.remove("dragover");
      if (e.dataTransfer.files.length > 0) {
        handleExamFileUpload(e.dataTransfer.files[0]);
      }
    });

    fileInput.addEventListener("change", (e) => {
      if (e.target.files.length > 0) {
        handleExamFileUpload(e.target.files[0]);
      }
    });
  }

  async function handleExamFileUpload(file) {
    if (!file) return;

    solverStatus.style.display = "block";
    solverStatus.textContent = `Analyzing ${file.name}, reading equations, and retrieving syllabus...`;
    solutionBox.style.display = "none";

    const formData = new FormData();
    formData.append("file", file);
    formData.append("stream", state.activeStream);

    try {
      const res = await fetch("/api/smileai/solve/snap", {
        method: "POST",
        body: formData,
      });

      const data = await res.json();
      solverStatus.style.display = "none";

      if (data.status === "success" && data.solution) {
        const sol = data.solution;
        solutionConcept.textContent = sol.concept;
        solutionCitation.textContent = sol.citation;

        solutionSteps.innerHTML = sol.steps
          .map(s => `<div class="pedagogical-step">${s.replace(/\n/g, "<br>")}</div>`)
          .join("");

        teacherTipBox.innerHTML = `<strong>💡 Teacher's Note:</strong> ${sol.pitfall}`;
        solutionBox.style.display = "block";

        currentSolutionSpeechText = `Here is the solution for ${sol.concept}. ${sol.steps[0]}. ${sol.pitfall}`;
      } else {
        alert(data.message || "Could not read text from image. Please try a clearer photo.");
      }
    } catch (err) {
      solverStatus.style.display = "none";
      alert("Exam paper upload failed. Please verify server connection.");
    }
  }

  if (listenSolutionBtn) {
    listenSolutionBtn.addEventListener("click", () => {
      playSmileyVoice(currentSolutionSpeechText);
    });
  }

  // ==============================================================================
  // 5. Vocabulary Practice & Sentence Evaluator
  // ==============================================================================

  const vocabDefText = document.getElementById("vocabDefinitionText");
  const vocabOptionsContainer = document.getElementById("vocabOptionsContainer");
  const vocabResultBox = document.getElementById("vocabResultBox");
  const nextVocabBtn = document.getElementById("nextVocabBtn");
  const targetWordDisplay = document.getElementById("targetWordDisplay");
  const sentenceInput = document.getElementById("sentenceInput");
  const evaluateSentenceBtn = document.getElementById("evaluateSentenceBtn");
  const sentenceFeedbackBox = document.getElementById("sentenceFeedbackBox");
  const vocabScoreBadge = document.getElementById("vocabScoreBadge");

  async function loadVocabChallenge() {
    try {
      const res = await fetch(`/api/smileai/vocab/challenge?stream=${encodeURIComponent(state.activeStream)}`);
      const data = await res.json();
      state.currentVocabTarget = data;
      state.currentVocabWord = data.correct_answer;

      if (vocabDefText) vocabDefText.textContent = data.definition;
      if (targetWordDisplay) targetWordDisplay.textContent = `"${data.correct_answer}"`;
      if (vocabResultBox) vocabResultBox.style.display = "none";
      if (sentenceFeedbackBox) sentenceFeedbackBox.style.display = "none";

      if (vocabOptionsContainer) {
        vocabOptionsContainer.innerHTML = "";
        data.options.forEach(opt => {
          const btn = document.createElement("button");
          btn.className = "btn-secondary";
          btn.style.padding = "10px";
          btn.style.textAlign = "center";
          btn.textContent = opt;
          btn.addEventListener("click", () => handleVocabOptionClick(btn, opt, data.correct_answer, data.example_usage));
          vocabOptionsContainer.appendChild(btn);
        });
      }
    } catch (e) {
      console.warn("Vocab challenge load error", e);
    }
  }

  function handleVocabOptionClick(btn, selected, correct, example) {
    const allButtons = vocabOptionsContainer.querySelectorAll("button");
    allButtons.forEach(b => b.disabled = true);

    if (selected === correct) {
      btn.style.background = "var(--emerald-bg)";
      btn.style.borderColor = "var(--emerald-success)";
      btn.style.color = "var(--emerald-success)";
      vocabResultBox.style.display = "block";
      vocabResultBox.innerHTML = `<span style="color: var(--emerald-success); font-weight: 700;">&check; Correct!</span> <em>${example}</em>`;
    } else {
      btn.style.background = "var(--rose-bg)";
      btn.style.borderColor = "var(--rose-danger)";
      btn.style.color = "var(--rose-danger)";
      vocabResultBox.style.display = "block";
      vocabResultBox.innerHTML = `<span style="color: var(--rose-danger); font-weight: 700;">&cross; Incorrect.</span> The correct answer was <strong>${correct}</strong>.`;
    }
  }

  if (nextVocabBtn) nextVocabBtn.addEventListener("click", loadVocabChallenge);

  if (evaluateSentenceBtn) {
    evaluateSentenceBtn.addEventListener("click", async () => {
      const sentence = sentenceInput.value.trim();
      if (!sentence) {
        alert("Please write a sentence first!");
        return;
      }

      try {
        const res = await fetch("/api/smileai/vocab/evaluate", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: jsonSafeStringify({
            word: state.currentVocabWord,
            sentence: sentence,
            stream: state.activeStream,
          }),
        });

        const data = await res.json();
        if (vocabScoreBadge) {
          vocabScoreBadge.textContent = `${data.score} / 10 pts`;
          vocabScoreBadge.style.color = data.score >= 8 ? "var(--emerald-success)" : "var(--amber-warning)";
        }

        if (sentenceFeedbackBox) {
          sentenceFeedbackBox.style.display = "block";
          sentenceFeedbackBox.innerHTML = `
            <strong>Score: ${data.score} / 10 (${data.percentage}%)</strong><br>
            ${data.feedback}<br><br>
            <em style="font-size: 12px; color: var(--text-muted);">${data.example_solution}</em>
          `;
        }
      } catch (e) {
        alert("Evaluation failed. Please check server.");
      }
    });
  }

  // ==============================================================================
  // 6. AI Builder Lab (Tokens, Vectors, Bot Builder)
  // ==============================================================================

  const tokenizerInput = document.getElementById("tokenizerInput");
  const tokensChipsBox = document.getElementById("tokensChipsBox");
  const tokenCountBadge = document.getElementById("tokenCountBadge");
  const vectorCanvas = document.getElementById("vectorCanvas");
  const evaluateBotBtn = document.getElementById("evaluateBotBtn");
  const exportBotBtn = document.getElementById("exportBotBtn");
  const botRubricResults = document.getElementById("botRubricResults");
  const rubricScoreBadge = document.getElementById("rubricScoreBadge");

  let tokenDebounce = null;
  if (tokenizerInput) {
    tokenizerInput.addEventListener("input", () => {
      clearTimeout(tokenDebounce);
      tokenDebounce = setTimeout(handleTokenAnalysis, 300);
    });
    handleTokenAnalysis();
  }

  async function handleTokenAnalysis() {
    const text = tokenizerInput.value || "";
    try {
      const res = await fetch("/api/smileai/builder/tokens", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: jsonSafeStringify({ text }),
      });
      const data = await res.json();

      if (tokenCountBadge) tokenCountBadge.textContent = `${data.token_count} Tokens`;
      if (tokensChipsBox) {
        tokensChipsBox.innerHTML = data.tokens.map(t => `
          <div class="token-chip" style="background: ${t.color}">
            <span>${escapeHtml(t.token)}</span>
            <span class="token-id-sub">#${t.token_id}</span>
          </div>
        `).join("");
      }
    } catch (e) {
      console.warn("Token analysis error", e);
    }
  }

  async function loadVectorMap() {
    try {
      const res = await fetch("/api/smileai/builder/embeddings", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: jsonSafeStringify({
          concepts: ["Doctor", "Hospital", "Medicine", "Cricket", "Stadium", "Newton", "Force"]
        }),
      });
      const data = await res.json();

      if (vectorCanvas && data.points) {
        vectorCanvas.innerHTML = "";
        const w = vectorCanvas.clientWidth || 400;
        const h = vectorCanvas.clientHeight || 280;

        data.points.forEach(p => {
          // Map [-1, 1] to canvas pixels
          const px = ((p.x + 1.0) / 2.0) * (w - 60) + 30;
          const py = ((1.0 - p.y) / 2.0) * (h - 60) + 30;

          const dot = document.createElement("div");
          dot.className = "vector-point";
          dot.style.left = `${px}px`;
          dot.style.top = `${py}px`;

          const lbl = document.createElement("div");
          lbl.className = "vector-label";
          lbl.style.left = `${px}px`;
          lbl.style.top = `${py}px`;
          lbl.textContent = p.concept;

          vectorCanvas.appendChild(dot);
          vectorCanvas.appendChild(lbl);
        });
      }
    } catch (e) {
      console.warn("Vector map load error", e);
    }
  }

  if (evaluateBotBtn) {
    evaluateBotBtn.addEventListener("click", async () => {
      const botName = document.getElementById("botNameInput").value;
      const notes = document.getElementById("botNotesInput").value;
      const prompt = document.getElementById("botPromptInput").value;

      try {
        const res = await fetch("/api/smileai/builder/evaluate", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: jsonSafeStringify({
            bot_name: botName,
            notes_text: notes,
            persona_prompt: prompt,
          }),
        });

        const data = await res.json();
        if (rubricScoreBadge) {
          rubricScoreBadge.textContent = `${data.total_score} / 100 (${data.grade})`;
        }

        if (botRubricResults) {
          botRubricResults.style.display = "block";
          botRubricResults.innerHTML = `
            <strong>CBSE/NEP Rubric Result: ${data.grade} (${data.total_score}/100)</strong><br>
            <em>${data.smiley_mentor_message}</em><br><br>
            <strong>Praise:</strong> ${data.praise.join(" ")}<br>
            <strong>Suggestions:</strong> ${data.suggestions.join(" ")}
          `;
        }
      } catch (e) {
        alert("Bot assessment failed.");
      }
    });
  }

  if (exportBotBtn) {
    exportBotBtn.addEventListener("click", async () => {
      const botName = document.getElementById("botNameInput").value;
      const author = document.getElementById("botAuthorInput").value;
      const notes = document.getElementById("botNotesInput").value;
      const prompt = document.getElementById("botPromptInput").value;

      const res = await fetch("/api/smileai/builder/export", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: jsonSafeStringify({
          bot_name: botName,
          author_name: author,
          notes_text: notes,
          persona_prompt: prompt,
        }),
      });

      if (res.ok) {
        const blob = await res.blob();
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement("a");
        a.href = url;
        a.download = `${botName.toLowerCase().replace(/\s+/g, "_")}_bot.py`;
        document.body.appendChild(a);
        a.click();
        a.remove();
      } else {
        alert("Export failed.");
      }
    });
  }

  // ==============================================================================
  // 7. Admin Bulk Roster Importer
  // ==============================================================================

  const uploadRosterBtn = document.getElementById("uploadRosterBtn");
  const rosterFileInput = document.getElementById("rosterFileInput");
  const rosterResultBox = document.getElementById("rosterResultBox");

  if (uploadRosterBtn && rosterFileInput) {
    uploadRosterBtn.addEventListener("click", async () => {
      if (rosterFileInput.files.length === 0) {
        alert("Please select a CSV roster file first!");
        return;
      }

      const formData = new FormData();
      formData.append("file", rosterFileInput.files[0]);
      formData.append("institution_id", "inst_default");

      try {
        const res = await fetch("/api/smileai/roster/import", {
          method: "POST",
          body: formData,
        });
        const data = await res.json();

        if (rosterResultBox && data.result) {
          rosterResultBox.style.display = "block";
          rosterResultBox.innerHTML = `
            <span style="color: var(--emerald-success); font-weight: 700;">&check; Successfully imported ${data.result.imported} students!</span><br>
            Auto-generated 4-digit PIN credentials are ready for lab distribution.
          `;
        }
      } catch (e) {
        alert("Roster import failed.");
      }
    });
  }

  // Utility helpers
  function jsonSafeStringify(obj) {
    return JSON.stringify(obj);
  }

  function escapeHtml(str) {
    return str.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
  }

  // Initial Boot
  loadVocabChallenge();
  loadVectorMap();
});
