"""Companion image commands, opportunity, and prompt builder."""
from __future__ import annotations


def test_parse_image_commands():
    from app.companion_image import parse_command

    assert parse_command("hello") is None
    a = parse_command("/image")
    assert a["kind"] == "manual" and a["count"] == 1
    b = parse_command("/img 3")
    assert b["count"] == 3
    c = parse_command("/image sitting at the cafe")
    assert "cafe" in c["extra"]
    d = parse_command("/visualize 2 rooftop sunset")
    assert d["count"] == 2 and "rooftop" in d["extra"]
    e = parse_command("/image_test")
    assert e["kind"] == "test"


def test_manual_beats_off_mode():
    from app.companion_image import opportunity_score

    score, reason = opportunity_score(
        mode="off",
        command={"kind": "manual", "count": 1, "extra": ""},
        scene={"location": "cafe"},
        prev={},
        last_ts=0,
        auto_count=0,
        cooldown=90,
        max_auto=4,
        user_text="/image",
        reply="",
    )
    assert score == 100
    auto, why = opportunity_score(
        mode="off",
        command=None,
        scene={"location": "rooftop"},
        prev={},
        last_ts=0,
        auto_count=0,
        cooldown=90,
        max_auto=4,
        user_text="let's go to the rooftop",
        reply="okay",
    )
    assert auto == 0
    assert "mode" in why


def test_scene_change_triggers_occasional_not_smalltalk():
    from app.companion_image import opportunity_score

    hi, _ = opportunity_score(
        mode="occasional",
        command=None,
        scene={"location": "rooftop", "outfit": "red jacket"},
        prev={"location": "kitchen"},
        last_ts=0,
        auto_count=0,
        cooldown=90,
        max_auto=4,
        user_text="come to the rooftop, I put on my red jacket",
        reply="I'm on the rooftop in the red jacket",
    )
    lo, _ = opportunity_score(
        mode="occasional",
        command=None,
        scene={"location": "kitchen"},
        prev={"location": "kitchen"},
        last_ts=0,
        auto_count=0,
        cooldown=90,
        max_auto=4,
        user_text="yeah",
        reply="mm",
    )
    assert hi >= 50
    assert lo < 50 or lo == 0


def test_identity_stable_across_scenes_and_variations():
    from app.companion_image import build_prompts

    profile = {
        "name": "Maya",
        "partner_gender": "woman",
        "card": {
            "vis_hair": "long dark brown hair",
            "vis_eyes": "green eyes",
            "vis_distinctive": "small mole near lip",
            "vis_default_outfit": "black hoodie",
        },
        "generation": {},
    }
    cafe = {"location": "cafe", "outfit": "black hoodie", "action": "sitting", "expression": "shy"}
    roof = {"location": "rooftop", "outfit": "red jacket", "action": "standing", "lighting": "sunset"}
    p1, _ = build_prompts(profile, cafe, variation=0)
    p2, _ = build_prompts(profile, roof, variation=1)
    p3, _ = build_prompts(profile, roof, variation=2)
    for p in (p1, p2, p3):
        assert "long dark brown hair" in p
        assert "green eyes" in p
        assert "small mole near lip" in p
        assert "photoreal" not in p.lower()
    assert "cafe" in p1 and "rooftop" in p2
    assert "red jacket" in p2
    assert p2 != p3
    assert "green eyes" in p3


def test_parse_prompt_command():
    from app.companion_image import parse_command

    p = parse_command("/prompt wide beach at sunset, no people")
    assert p["kind"] == "prompt"
    assert "beach" in p["extra"]


def test_shot_ask_then_view_is_wide_scenery():
    from app.companion_image import build_prompts, prepare_image_turn, shot_size

    profile = {"name": "Maya", "partner_gender": "woman", "card": {}, "generation": {}}
    runtime = {"pending_image": {}, "last_shot": {}}
    cmd = {"kind": "manual", "count": 1, "extra": "looking at the beach together"}
    first = prepare_image_turn(
        profile=profile,
        runtime=runtime,
        user_text="/img looking at the beach together",
        command=cmd,
    )
    assert first["hold"] is True
    assert first["ask"] == "shot"
    runtime["pending_image"] = first["pending"]
    second = prepare_image_turn(
        profile=profile,
        runtime=runtime,
        user_text="the view",
        command=None,
    )
    assert second["hold"] is False
    assert second["kind"] == "scenery"
    w, h = shot_size("scenery")
    assert w > h
    prompt, neg = build_prompts(profile, {"location": "beach", "kind": "scenery"}, kind="scenery")
    low = prompt.lower()
    assert "key visual" in low
    assert "looking at viewer" not in low
    assert "selfie" in neg.lower()


def test_character_default_is_cowboy_not_closeup():
    from app.companion_image import build_prompts

    profile = {
        "name": "Maya",
        "partner_gender": "woman",
        "card": {"vis_hair": "black hair", "vis_default_outfit": "red saree"},
        "generation": {},
    }
    prompt, _ = build_prompts(profile, {"location": "balcony"}, kind="character")
    low = prompt.lower()
    assert "complete head" in low
    assert "close-up portrait" not in low
    assert "red saree" in low
    assert "black hair" in low


def test_unknown_look_holds_character_image():
    from app.companion_image import prepare_image_turn

    profile = {"name": "Maya", "partner_gender": "woman", "card": {}, "generation": {}}
    plan = prepare_image_turn(
        profile=profile,
        runtime={"pending_image": {}, "last_shot": {}},
        user_text="/img I wanna see you in a saree",
        command={"kind": "manual", "count": 1, "extra": "I wanna see you in a saree"},
    )
    assert plan["hold"] is True
    assert plan["ask"] == "look"
    assert plan["kind"] == "character"
    assert "saree" in (plan.get("extra") or "")


def test_shot_choices_are_tappable():
    from app.companion_image import shot_choice_list

    chips = shot_choice_list("shot")
    assert [c["id"] for c in chips] == ["scenery", "together", "character"]
    assert [c["id"] for c in shot_choice_list("angle")] == ["close", "body", "original"]
    assert [c["id"] for c in shot_choice_list("frame")] == ["portrait", "landscape", "original"]
    assert shot_choice_list("look") == []


def test_day_output_and_log_html(tmp_path, monkeypatch):
    from app import companion_image as img

    monkeypatch.setattr(img, "OUTPUT_ROOT", tmp_path / "out")
    monkeypatch.setattr(img, "IMAGE_DIR", tmp_path / "legacy")
    day = img.day_output_dir()
    pic = day / "demo.png"
    pic.write_bytes(b"png")
    html = img.append_day_log(
        [{"filename": "demo.png", "seconds": 12.4, "seed": 7, "checkpoint": "animaPencilXL_v500.safetensors"}],
        {"prompt": "cafe hoodie", "width": 768, "height": 1152},
        12.4,
    )
    assert html.is_file()
    text = html.read_text(encoding="utf-8")
    assert "demo.png" in text
    assert "12.4s" in text
    assert "cafe hoodie" in text
    assert img.find_image("demo.png") == pic
    names = [row["filename"] for row in img.list_gallery()]
    assert "demo.png" in names
    extra = tmp_path / "out" / "other-phone" / "stray.png"
    extra.parent.mkdir(parents=True)
    extra.write_bytes(b"old")
    names = [row["filename"] for row in img.list_gallery()]
    assert "stray.png" not in names


def test_user_stop_does_not_requeue(monkeypatch):
    from app import companion_jobs as jobs

    monkeypatch.setattr(jobs, "_ensure_worker", lambda: None)
    job = jobs.enqueue({"prompt": "x", "negative": "", "manual": True})
    out = jobs.request_stop(job_id=job["id"], chat=False, image=True)
    got = jobs.get_job(job["id"])
    assert out["image"] is True
    assert got["status"] == "cancelled"
    assert got["user_stop"] is True
    assert got["id"] not in jobs._QUEUE


def test_no_invented_hoodie_when_look_unknown():
    from app.companion_image import build_prompts, look_unknown

    profile = {"name": "Maya", "partner_gender": "woman", "card": {}, "generation": {}}
    assert look_unknown(profile)
    prompt, _ = build_prompts(profile, {})
    low = prompt.lower()
    assert "hoodie" not in low
    assert "casual indoor" not in low
    assert "standing, relaxed" not in low


def test_reject_hoodie_neckline_wins():
    from app.companion_image import apply_visual_intent, build_prompts, extract_scene, learn_look

    text = "its good if u show neckline but u r in hoodie too bad"
    profile = {
        "name": "Maya",
        "partner_gender": "woman",
        "card": {"vis_default_outfit": "hoodie"},
        "generation": {},
    }
    learned = learn_look(profile, text)
    assert "vis_default_outfit" in learned["clears"]
    scene = extract_scene(text, "okay", {"visual": {"outfit": "hoodie"}}, "", profile)
    scene = apply_visual_intent(text, scene, {"default_outfit": "hoodie"})
    assert "hoodie" not in (scene.get("outfit") or "").lower()
    prompt, _ = build_prompts({**profile, "card": {}}, scene)
    assert "hoodie" not in prompt.lower()
    assert "neckline" in prompt.lower()


def test_png_keeps_prompt_metadata(tmp_path):
    from PIL import Image

    from app.companion_image import pnginfo_from_meta, write_image_sidecar

    path = tmp_path / "scene.png"
    meta = {
        "prompt": "1girl, adult, red dress, open neckline",
        "negative": "hoodie, extra fingers",
        "seed": 42,
        "steps": 4,
        "cfg": 1.2,
        "width": 8,
        "height": 8,
        "accel": "lightning",
        "checkpoint": "animaPencilXL_v500.safetensors",
    }
    Image.new("RGB", (8, 8), "red").save(path, pnginfo=pnginfo_from_meta(meta))
    write_image_sidecar(path, meta)
    loaded = Image.open(path)
    info = getattr(loaded, "text", None) or loaded.info
    blob = " ".join(str(v) for v in info.values())
    assert "red dress" in blob
    assert "42" in blob
    assert "parameters" in info or "prompt" in blob.lower() or "red dress" in blob
    assert not path.with_suffix(".txt").exists()


def test_prompt_person_is_portrait_not_landscape():
    from app.companion_image import infer_kind, prepare_image_turn, shot_size

    extra = "Low angle: A 30 year old woman in a tight golden micro-bikini standing next to a wall"
    plan = prepare_image_turn(
        profile={
            "name": "Maya",
            "partner_gender": "woman",
            "card": {"vis_hair": "black hair", "vis_default_outfit": "saree"},
            "generation": {},
        },
        runtime={"pending_image": {}, "last_shot": {}, "images_unlocked": True, "turns": 20},
        user_text="/prompt " + extra,
        command={"kind": "prompt", "count": 1, "extra": extra},
    )
    assert plan["hold"] is True
    assert plan["ask"] == "angle"
    assert plan["kind"] == "character"
    assert extra in (plan.get("extra") or "")
    assert infer_kind("wide beach at sunset, no people") == "scenery"
    w, h = shot_size(plan["kind"], frame="portrait")
    assert h > w
    wl, hl = shot_size("character", frame="landscape")
    assert wl > hl


def test_frame_chips_keep_the_written_prompt(monkeypatch):
    from app import companion_jobs as jobs
    from app.companion_image import apply_shot_choice, detect_style, prepare_image_turn

    captured = {}

    def fake_enqueue(payload):
        captured.update(payload)
        return {"id": "job1", "status": "queued"}

    monkeypatch.setattr(jobs, "enqueue", fake_enqueue)
    extra = "manga style, you feeding me ramen at a night stall"
    profile = {
        "name": "Maya",
        "partner_gender": "woman",
        "card": {"vis_hair": "black hair"},
        "generation": {"image_mode": "manual"},
    }
    runtime = {
        "pending_image": {},
        "last_shot": {},
        "visual": {},
        "images_unlocked": True,
        "turns": 20,
    }
    plan = prepare_image_turn(
        profile=profile,
        runtime=runtime,
        user_text="/prompt " + extra,
        command={"kind": "prompt", "count": 1, "extra": extra},
    )
    assert plan["hold"] is True
    assert plan["ask"] == "angle"
    runtime["pending_image"] = plan["pending"]
    job = apply_shot_choice(profile=profile, runtime=runtime, choice_id="original")
    assert job and job["id"] == "job1"
    assert extra in (captured.get("prompt") or "")
    assert "manga" in (captured.get("prompt") or "").lower()
    assert detect_style(extra) == "manga"
    w, h = captured.get("width"), captured.get("height")
    assert w and h


def test_sketch_style_follows_words():
    from app.companion_image import build_prompts, detect_style

    extra = "you are sketching an art form in pencil"
    assert detect_style(extra) == "sketch"
    prompt, neg = build_prompts(
        {"name": "Maya", "partner_gender": "woman", "card": {}, "generation": {}},
        {"rewrite": extra, "literal": "1", "kind": "character", "style": "sketch", "frame": "original"},
        kind="character",
    )
    low = prompt.lower()
    assert "sketch" in low
    assert "photoreal" in neg.lower()
    assert "cowboy shot" not in low


def test_scene_caption_drops_repeated_tags():
    from app.companion_image import scene_caption

    blob = "kiss, lips, foreplay, foreplay, foreplay, foreplay, night stall"
    out = scene_caption(blob)
    assert out.lower().count("foreplay") == 1
    assert "night stall" in out


def test_bare_img_asks_with_chips():
    from app.companion_image import prepare_image_turn, shot_choice_list

    plan = prepare_image_turn(
        profile={"name": "Maya", "partner_gender": "woman", "card": {}, "generation": {}},
        runtime={"pending_image": {}, "last_shot": {}},
        user_text="/img",
        command={"kind": "manual", "count": 1, "extra": ""},
    )
    assert plan["hold"] is True
    assert plan["ask"] == "angle"
    assert shot_choice_list(plan["ask"])


def test_pictures_wait_until_twenty_turns():
    from app.companion_image import detect_user_image_ask, images_ready, queue_if_needed

    assert detect_user_image_ask("show me what you're wearing")
    assert not detect_user_image_ask("hey")
    assert not images_ready({"turns": 3, "images_unlocked": False})
    assert images_ready({"turns": 20})
    assert images_ready({"images_unlocked": True, "turns": 1})
    job = queue_if_needed(
        profile={"name": "Maya", "partner_gender": "woman", "card": {}, "generation": {"image_mode": "manual"}},
        runtime={"turns": 2, "images_unlocked": False, "visual": {}, "pending_image": {}, "last_shot": {}},
        user_text="/img",
        reply="okay",
        command={"kind": "manual", "count": 1, "extra": "cafe"},
        shot_kind="character",
    )
    assert job is None


def test_nude_prompt_drops_sticky_clothes():
    from app.companion_image import build_prompts, extract_scene, learn_look

    profile = {
        "name": "Maya",
        "partner_gender": "woman",
        "card": {"vis_hair": "black hair", "vis_default_outfit": "red saree"},
        "generation": {},
    }
    text = "nude woman, full body, show her legs"
    learned = learn_look(profile, text)
    assert "vis_default_outfit" in learned["clears"]
    scene = extract_scene(text, "okay", {"visual": {"outfit": "red saree"}}, text, profile)
    assert "nude" in (scene.get("outfit") or "").lower()
    assert "saree" not in (scene.get("outfit") or "").lower()
    prompt, neg = build_prompts(
        profile,
        {
            "outfit": scene["outfit"],
            "rewrite": text,
            "literal": "1",
            "kind": "character",
            "frame": "body",
            "drop": "clothes",
        },
        kind="character",
    )
    low = prompt.lower()
    assert "nude" in low
    assert "saree" not in low
    assert "head to feet" in low or "full body" in low
    assert "legs" in low
    assert "clothes" in neg.lower()


def test_legs_camera_is_full_body():
    from app.companion_image import build_prompts

    prompt, _ = build_prompts(
        {"name": "Maya", "partner_gender": "woman", "card": {"vis_hair": "black hair"}, "generation": {}},
        {"kind": "character", "frame": "body", "rewrite": "show your legs"},
        kind="character",
    )
    low = prompt.lower()
    assert "full body" in low
    assert "head to feet" in low
    assert "cowboy shot" not in low


def test_see_this_asks_angle_not_queue(monkeypatch):
    from app.companion_image import apply_shot_choice, prepare_image_turn, shot_choice_list

    profile = {
        "name": "Maya",
        "partner_gender": "woman",
        "card": {"vis_hair": "black hair"},
        "generation": {"image_mode": "manual"},
    }
    runtime = {"pending_image": {"kind": "character", "extra": "on the bed", "reply": "on the bed"}, "last_shot": {}}
    job = apply_shot_choice(profile=profile, runtime=runtime, choice_id="see_this")
    assert job is None
    assert runtime["pending_image"]["asked"] == "angle"
    assert shot_choice_list("angle")
    plan = prepare_image_turn(
        profile=profile,
        runtime={"pending_image": {}, "last_shot": {}, "images_unlocked": True, "turns": 20},
        user_text="let me see you",
        command={"kind": "manual", "count": 1, "extra": "", "name": "ask"},
    )
    assert plan["hold"] is True
    assert plan["ask"] == "angle"


def test_see_this_only_on_visual_beats():
    from app.companion_image import should_offer_see_this

    rt = {"images_unlocked": True, "turns": 24, "last_see_turn": 0}
    assert not should_offer_see_this("hey", rt, {})
    assert not should_offer_see_this("I missed you today after that long shift.", rt, {})
    assert should_offer_see_this(
        "[I run my fingers over the fabric of my t-shirt, leaning back a little.]",
        rt,
        {},
    )
    assert rt["last_see_turn"] == 24
    rt["turns"] = 26
    assert not should_offer_see_this(
        "[I unbutton my shirt slowly, watching you.]",
        rt,
        {},
    )
