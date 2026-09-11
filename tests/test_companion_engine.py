"""Companion engine — cards, state, memory, context. No live Ollama required."""
from __future__ import annotations


def test_context_order_and_you_card(tmp_path, monkeypatch):
    from app import companion_engine as eng

    monkeypatch.setattr(eng, "STATE_PATH", tmp_path / "state.json")
    monkeypatch.setattr(eng, "MEMORY_PATH", tmp_path / "mem.json")

    profile = eng.ensure_engine_fields(
        {
            "name": "Maya",
            "partner_role": "girlfriend",
            "partner_gender": "woman",
            "partner_pronouns": "she/her",
            "user_name": "Arjun",
            "user_gender": "man",
            "user_pronouns": "he/him",
            "user_called": "love",
            "user_about": "quiet, works nights",
            "system_prompt": "Voice only.",
        }
    )
    profile["card"]["core_traits"] = "stubborn tease"
    profile["dynamics"]["mature_mode"] = True
    profile["dynamics"]["sensuality"] = 80
    profile["generation"]["style"] = "roleplay"

    runtime = eng.default_runtime()
    memory = eng.default_memory()
    memory["semantic"].append(
        {"id": "1", "text": "Arjun hates being called sweetie", "salience": 0.9, "ts": 0}
    )
    messages, debug = eng.build_messages(
        profile=profile,
        runtime=runtime,
        memory=memory,
        history=[{"role": "user", "content": "hey"}, {"role": "assistant", "content": "hey."}],
        question="I had a long night at work",
    )
    system = messages[0]["content"]
    assert system.index("You are a fictional person") < system.index("YOU ARE Maya")
    assert system.index("YOU ARE Maya") < system.index("WHO YOU ARE SPEAKING TO")
    assert system.index("WHO YOU ARE SPEAKING TO") < system.index("CURRENT INNER STATE")
    assert "Arjun" in system
    assert "he/him" in system
    assert "she/her" in system
    assert "stubborn tease" in system
    assert "sensuality: 80/100" in system
    assert "hates being called sweetie" in system
    assert debug["turns"] == 2
    assert runtime["relationship"]["familiarity"] < 0.22
    assert "getting to know" in system.lower()


def test_low_slider_does_not_force_dynamic():
    from app import companion_engine as eng

    profile = eng.ensure_engine_fields({"name": "Maya", "user_name": "A"})
    profile["dynamics"]["dominance"] = 5
    text = eng.render_dynamics(profile)
    assert "dominance" not in text.lower()
    assert "permission, not a command" in text.lower()


def test_relationship_updates_are_not_random(tmp_path, monkeypatch):
    from app import companion_engine as eng

    monkeypatch.setattr(eng, "STATE_PATH", tmp_path / "s.json")
    rt = eng.default_runtime()
    before = dict(rt["relationship"])
    after = eng.update_runtime(rt, "sorry I snapped at you", "it's ok. come here.", mature=True)
    assert after["relationship"]["trust"] > before["trust"]
    assert after["relationship"]["tension"] <= before["tension"]
    fight = eng.update_runtime(after, "shut up I hate this", "…", mature=True)
    assert fight["relationship"]["trust"] < after["relationship"]["trust"]
    assert fight["emotion"]["primary"] == "hurt"


def test_memory_ingest_and_relevance(tmp_path, monkeypatch):
    from app import companion_engine as eng

    monkeypatch.setattr(eng, "MEMORY_PATH", tmp_path / "m.json")
    mem = eng.default_memory()
    profile = {"user_name": "Arjun"}
    mem = eng.ingest_memories(
        mem, "remember that I hate mornings and I like black coffee", "ok", profile, {"turns": 3}
    )
    assert any("coffee" in (x.get("text") or "") for x in mem["semantic"])
    picked = eng.select_memories(mem, "want coffee?")
    assert picked
    assert any("coffee" in (x.get("text") or "") for x in picked)


def test_crisis_is_self_harm_not_fiction():
    from app.companion_engine import detect_crisis
    from app.safety import detect_distress

    assert detect_crisis("I want to kill myself")
    assert detect_crisis("come to bed") is None
    # school regex still flags some fiction words; companion must not
    assert detect_distress("they were raped in the story")
    assert detect_crisis("they were raped in the story") is None


def test_anti_repeat_blocks_smirk_spam():
    from app.companion_engine import _anti_repeat

    hist = [
        {"role": "assistant", "content": "She smirks at you. What now?"},
        {"role": "assistant", "content": "She smirks again. Coming?"},
        {"role": "assistant", "content": "A smirk. Ready?"},
    ]
    note = _anti_repeat(hist)
    assert "smirk" in note.lower()
    assert "question" in note.lower()


def test_two_characters_diverge():
    from app import companion_engine as eng

    shy = eng.ensure_engine_fields({"name": "Lina", "user_name": "A", "partner_role": "girlfriend"})
    shy["card"]["relationship_style"] = "shy"
    shy["card"]["core_traits"] = "quiet, watches first"
    shy["generation"]["style"] = "minimal"
    sarcastic = eng.ensure_engine_fields({"name": "Vic", "user_name": "A", "partner_role": "boyfriend"})
    sarcastic["card"]["relationship_style"] = "sarcastic"
    sarcastic["card"]["core_traits"] = "mean-smart, never gushy"
    sarcastic["generation"]["style"] = "chat"
    a = eng.build_system(eng.build_sections(shy, eng.default_runtime(), [], []))
    b = eng.build_system(eng.build_sections(sarcastic, eng.default_runtime(), [], []))
    assert "quiet, watches first" in a and "quiet, watches first" not in b
    assert "mean-smart" in b
    assert "text-message" in a.lower() or "few actions" in a.lower()
    assert "YOU ARE Lina" in a
    assert "YOU ARE Vic" in b
    assert "boyfriend" in b


def test_language_defaults_english_with_playful_telugu():
    from app import companion_engine as eng

    profile = eng.ensure_engine_fields({"name": "Maya", "user_name": "A"})
    assert profile["generation"]["language"] == "english"
    assert profile["generation"]["second_language"] == "telugu"
    system = eng.build_system(eng.build_sections(profile, eng.default_runtime(), [], []))
    assert "LANGUAGE: English" in system
    assert "Playfully mix Telugu" in system
    assert "Never Hindi" in system
    assert "nahi" in system
    assert "ledu" in system
    assert "LANGUAGE beats Voice notes" in system
    assert system.index("Language is set in LANGUAGE") < system.index("LANGUAGE: English")
    profile["generation"]["language"] = "telugu"
    profile["generation"]["second_language"] = "none"
    te = eng.render_language(profile)
    assert "Reply in Telugu" in te
    assert "Never Hindi" in te
    migrated = eng.ensure_engine_fields({"name": "Maya", "generation": {"language": "telugu"}})
    assert migrated["generation"]["language"] == "english"
    assert migrated["generation"]["second_language"] == "telugu"


def test_chat_stop_is_per_live_turn():
    from app import companion_jobs as jobs

    g1 = jobs.begin_chat()
    assert not jobs.chat_stop_requested(g1)
    jobs.request_stop(chat=True, image=False)
    assert jobs.chat_stop_requested(g1)
    jobs.chat_finished(g1)
    g2 = jobs.begin_chat()
    assert not jobs.chat_stop_requested(g2)
    jobs.chat_finished(g2)


def test_chat_log_survives_until_clear(tmp_path, monkeypatch):
    from app import companion_engine as eng

    monkeypatch.setattr(eng, "CHAT_PATH", tmp_path / "chat.json")
    eng.clear_chat()
    eng.append_chat("user", "hey")
    eng.append_chat("assistant", "mm")
    got = eng.load_chat()
    assert len(got) == 2
    assert got[0]["content"] == "hey"
    assert not (tmp_path / "chat.json").exists()
    hist = eng.history_for_llm()
    assert hist[-1]["role"] == "assistant"
    eng.clear_chat()
    assert eng.load_chat() == []
    from app.companion_engine import sampling_options

    a = sampling_options({"generation": {"preset": "character"}})
    b = sampling_options({"generation": {"preset": "creative"}})
    assert a["repeat_penalty"] > b["repeat_penalty"]
    assert b["temperature"] > a["temperature"]


def test_unknown_look_asks_instead_of_inventing():
    from app import companion_engine as eng

    profile = eng.ensure_engine_fields({"name": "Maya", "user_name": "A"})
    system = eng.build_system(eng.build_sections(profile, eng.default_runtime(), [], []))
    assert "LOOK" in system
    assert "long wavy black hair" in system
    assert "Do not pick a hoodie" not in system
    blank = eng.ensure_engine_fields({"name": "Maya", "user_name": "A"})
    for key in ("vis_hair", "vis_eyes", "vis_face", "vis_body", "vis_distinctive", "vis_default_outfit", "appearance"):
        blank["card"][key] = ""
    unknown = eng.build_system(eng.build_sections(blank, eng.default_runtime(), [], []))
    assert "Do not pick a hoodie" in unknown
    assert "I'm imagining you" in eng.CORE
    assert "I unbutton my shirt" in eng.CORE
    assert "YOUR body (Maya)" not in eng.CORE
    assert "Never switch bodies" in system
    profile["card"]["vis_hair"] = "short black hair"
    profile["card"]["vis_default_outfit"] = "red dress"
    known = eng.build_system(eng.build_sections(profile, eng.default_runtime(), [], []))
    assert "short black hair" in known
    assert "red dress" in known
    assert "Do not pick a hoodie" not in known


def test_male_pack_is_kai_not_maya():
    from app.companion import persona_pack
    from app.companion_engine import default_card

    kai = default_card("man")
    assert "short dark hair" in kai["vis_hair"]
    assert "henley" in kai["vis_default_outfit"]
    maya = default_card("woman")
    assert "long wavy black hair" in maya["vis_hair"]
    pack = persona_pack("boyfriend")
    assert pack["name"] == "Kai"
    assert pack["partner_gender"] == "man"
    assert "I, me, my is your body" in pack["system_prompt"]
    wife = persona_pack("wife")
    assert wife["name"] == "Maya"


def test_devices_keep_separate_chats(tmp_path, monkeypatch):
    from app import companion_engine as eng

    monkeypatch.setattr(eng, "DEVICE_ROOT", tmp_path / "devices")
    monkeypatch.setattr(eng, "CHAT_PATH", tmp_path / "legacy_chat.json")
    eng.set_device("pc-device")
    eng.clear_chat()
    eng.append_chat("user", "from pc")
    eng.set_device("phone-device")
    eng.clear_chat()
    eng.append_chat("user", "from phone")
    eng.set_device("pc-device")
    pc = [m["content"] for m in eng.load_chat()]
    eng.set_device("phone-device")
    phone = [m["content"] for m in eng.load_chat()]
    assert pc == ["from pc"]
    assert phone == ["from phone"]
    eng.set_device("")


def test_image_steps_follow_settings():
    from app.companion_image import resolve_image_run, snap_image_steps

    assert snap_image_steps(4) == 4
    assert snap_image_steps(8) == 8
    assert snap_image_steps(16) == 16
    assert snap_image_steps(30) == 30
    assert snap_image_steps(20) == 16
    assert snap_image_steps(7) == 8
    eight = resolve_image_run({"image_steps": 8, "image_accel": "none", "image_cfg": 4})
    assert eight["steps"] == 8
    assert eight["accel"] == "none"
    draft = resolve_image_run({"image_steps": 4, "image_accel": "lightning"})
    assert draft["steps"] == 4
    from app import companion_engine as eng

    kept = eng.ensure_engine_fields(
        {"name": "Maya", "generation": {"image_accel": "lightning", "image_steps": 4, "image_cfg": 1.2}}
    )
    assert kept["generation"]["image_accel"] == "lightning"
    assert kept["generation"]["image_steps"] == 4
    fresh = eng.ensure_engine_fields({"name": "Maya"})
    assert fresh["generation"]["image_steps"] == 8
    quality = resolve_image_run({"image_steps": 30, "image_accel": "none", "image_cfg": 4})
    assert quality["steps"] == 30
    assert quality["accel"] == "none"
    lightning_at_quality = resolve_image_run({"image_steps": 30, "image_accel": "lightning"})
    assert lightning_at_quality["accel"] == "none"
    assert lightning_at_quality["steps"] == 30


def test_picture_scene_stays_in_ram(tmp_path, monkeypatch):
    import json

    from app import companion_engine as eng

    monkeypatch.setattr(eng, "STATE_PATH", tmp_path / "state.json")
    monkeypatch.setattr(eng, "DEVICE_ROOT", tmp_path / "devices")
    eng.set_device("pc")
    rt = eng.default_runtime()
    rt["visual"] = {
        "look_asked": True,
        "rewrite": "foreplay, foreplay, kiss",
        "last_picture": "kissing closeup",
    }
    rt["last_shot"] = {"extra": "kissing"}
    eng.save_runtime(rt)
    still = eng.load_runtime()
    assert still["visual"].get("last_picture") == "kissing closeup"
    raw = json.loads((tmp_path / "devices" / "pc" / "state.json").read_text(encoding="utf-8"))
    assert "foreplay" not in json.dumps(raw)
    assert not (raw.get("visual") or {}).get("last_picture")
    assert (raw.get("visual") or {}).get("look_asked") is True
    eng.clear_chat()
    after = eng.load_runtime()
    assert not (after["visual"].get("last_picture") or "")
    assert after["visual"].get("look_asked") is True
    eng.set_device("")


def test_image_prompts_are_not_memories(tmp_path, monkeypatch):
    import json

    from app import companion_engine as eng

    mem = eng.ingest_memories(
        eng.default_memory(),
        "/prompt Low angle: A 30 year old woman in a golden bikini standing next to a wall giving a look",
        "ok",
        {"user_name": "Arjun"},
        {"turns": 3},
    )
    assert mem["episodic"] == []
    assert mem["semantic"] == []
    monkeypatch.setattr(eng, "MEMORY_PATH", tmp_path / "m.json")
    monkeypatch.setattr(eng, "DEVICE_ROOT", tmp_path / "devices")
    eng.set_device("")
    (tmp_path / "m.json").write_text(
        json.dumps(
            {
                "episodic": [{"id": "1", "text": "They opened up: /prompt bikini scene dump", "salience": 0.6}],
                "semantic": [{"id": "2", "text": "i like coffee", "salience": 0.7}],
                "relationship": [{"id": "3", "text": "Visual last: bedroom hoodie", "salience": 0.5}],
            }
        ),
        encoding="utf-8",
    )
    loaded = eng.load_memory()
    assert loaded["episodic"] == []
    assert loaded["relationship"] == []
    assert loaded["semantic"][0]["text"] == "i like coffee"
