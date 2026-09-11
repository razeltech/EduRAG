"""Local SDXL generator using checkpoints already on disk. No Fooocus UI."""
from __future__ import annotations

import gc
import time
from pathlib import Path
from typing import Any, Callable

from app.companion_image import checkpoint_path, lora_path

CancelFn = Callable[[], bool]


class ImageError(RuntimeError):
    pass


_PIPE = None
_PIPE_KEY = ""


def _torch():
    try:
        import torch
    except ImportError as exc:
        raise ImageError("PyTorch is not available in this environment.") from exc
    return torch


def unload_pipeline() -> None:
    """Drop SDXL entirely. Only for OOM or a checkpoint change."""
    global _PIPE, _PIPE_KEY
    torch = _torch()
    if _PIPE is not None:
        try:
            del _PIPE
        except Exception:
            pass
        _PIPE = None
        _PIPE_KEY = ""
    gc.collect()
    if torch.cuda.is_available():
        torch.cuda.empty_cache()
        torch.cuda.ipc_collect()


def sleep_pipeline() -> None:
    """Park SDXL in RAM so Qwen can use the GPU. Avoids a 1–2 min disk reload."""
    global _PIPE
    torch = _torch()
    if _PIPE is None:
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
        return
    try:
        _PIPE.to("cpu")
    except Exception:
        unload_pipeline()
        return
    gc.collect()
    if torch.cuda.is_available():
        torch.cuda.empty_cache()
        torch.cuda.ipc_collect()


def _load_pipeline(ckpt: Path, accel: str | None, cancel: CancelFn | None = None):
    global _PIPE, _PIPE_KEY
    torch = _torch()
    if cancel and cancel():
        raise ImageError("cancelled")
    key = f"{ckpt}:{accel or 'none'}"
    if _PIPE is not None and _PIPE_KEY == key:
        if torch.cuda.is_available():
            _PIPE = _PIPE.to("cuda")
        return _PIPE
    unload_pipeline()
    from diffusers import DPMSolverMultistepScheduler, EulerDiscreteScheduler, StableDiffusionXLPipeline

    if not ckpt.is_file():
        raise ImageError(f"Checkpoint missing: {ckpt}")
    dtype = torch.float16 if torch.cuda.is_available() else torch.float32
    try:
        pipe = StableDiffusionXLPipeline.from_single_file(
            str(ckpt),
            torch_dtype=dtype,
            local_files_only=True,
            use_safetensors=True,
        )
    except Exception as first:
        try:
            pipe = StableDiffusionXLPipeline.from_single_file(
                str(ckpt),
                torch_dtype=dtype,
                use_safetensors=True,
            )
        except Exception as exc:
            raise ImageError(
                f"Could not load {ckpt.name} with diffusers ({first}). {exc}"
            ) from exc
    if cancel and cancel():
        del pipe
        gc.collect()
        raise ImageError("cancelled")
    wanted = (accel or "none").lower()
    lora = lora_path(wanted)
    if wanted in {"lightning", "lcm", "hyper"}:
        if lora is None:
            raise ImageError(f"Speed LoRA missing for {wanted}.")
        try:
            import peft  # noqa: F401
        except ImportError as exc:
            raise ImageError("Lightning needs peft. Install peft in the EduRAG venv.") from exc
        try:
            pipe.load_lora_weights(str(lora.parent), weight_name=lora.name)
            pipe.fuse_lora()
        except Exception as exc:
            raise ImageError(f"Could not load {lora.name}: {exc}") from exc
        pipe.scheduler = EulerDiscreteScheduler.from_config(
            pipe.scheduler.config, timestep_spacing="trailing"
        )
    elif wanted in {None, "", "none"}:
        try:
            pipe.scheduler = DPMSolverMultistepScheduler.from_config(
                pipe.scheduler.config, use_karras_sigmas=True
            )
        except Exception:
            pass
    pipe._companion_accel = wanted if lora is not None or wanted == "none" else "none"
    if torch.cuda.is_available():
        pipe = pipe.to("cuda")
        try:
            pipe.enable_attention_slicing()
        except Exception:
            pass
        try:
            pipe.enable_vae_slicing()
        except Exception:
            pass
    if cancel and cancel():
        _PIPE = pipe
        _PIPE_KEY = key
        sleep_pipeline()
        raise ImageError("cancelled")
    _PIPE = pipe
    _PIPE_KEY = key
    return pipe


def generate(
    *,
    prompt: str,
    negative_prompt: str,
    width: int = 768,
    height: int = 1152,
    steps: int = 4,
    guidance: float = 1.2,
    seed: int = -1,
    count: int = 1,
    checkpoint: str | None = None,
    accel: str | None = "none",
    out_dir: Path,
    cancel: CancelFn | None = None,
    on_phase: Callable[[str], None] | None = None,
) -> list[dict[str, Any]]:
    torch = _torch()
    ckpt = checkpoint_path(checkpoint)
    if cancel and cancel():
        raise ImageError("cancelled")
    if on_phase:
        on_phase("loading")
    pipe = _load_pipeline(ckpt, accel, cancel=cancel)
    if cancel and cancel():
        sleep_pipeline()
        raise ImageError("cancelled")
    if on_phase:
        on_phase("drawing")
    used = getattr(pipe, "_companion_accel", accel or "none")
    if used in {"lightning", "hyper"}:
        steps = max(2, min(int(steps), 8))
        if float(guidance) > 2.5 or float(guidance) < 0.5:
            guidance = 1.2
    elif used == "lcm":
        steps = max(4, min(int(steps), 8))
        if float(guidance) > 2.5 or float(guidance) < 0.5:
            guidance = 1.5
    elif used in {None, "", "none"}:
        steps = max(2, min(int(steps), 60))
        if float(guidance) < 1:
            guidance = 4.0
    out_dir.mkdir(parents=True, exist_ok=True)
    count = max(1, min(3, int(count)))
    width = max(512, min(1280, int(width) // 8 * 8))
    height = max(512, min(1536, int(height) // 8 * 8))
    steps = max(2, min(60, int(steps)))
    results: list[dict[str, Any]] = []
    base_seed = int(time.time()) if int(seed) < 0 else int(seed)

    def _cb(pipe_ref, step_index, timestep, extra_kwargs):
        del pipe_ref, step_index, timestep
        if cancel and cancel():
            raise ImageError("cancelled")
        return extra_kwargs

    for i in range(count):
        if cancel and cancel():
            raise ImageError("cancelled")
        this_seed = base_seed + i * 17
        gen = torch.Generator(device="cuda" if torch.cuda.is_available() else "cpu")
        gen.manual_seed(this_seed)
        t0 = time.time()
        try:
            out = pipe(
                prompt=prompt,
                negative_prompt=negative_prompt,
                width=width,
                height=height,
                num_inference_steps=steps,
                guidance_scale=float(guidance),
                generator=gen,
                callback_on_step_end=_cb,
            )
        except ImageError:
            raise
        except Exception as exc:
            msg = str(exc).lower()
            if "out of memory" in msg or "cuda" in msg and "memory" in msg:
                unload_pipeline()
                raise ImageError("VRAM exhausted while generating. Chat should still work.") from exc
            raise ImageError(f"Generation failed: {exc}") from exc
        image = out.images[0]
        name = f"{int(time.time())}_{i}_{this_seed}.png"
        path = out_dir / name
        seconds = round(time.time() - t0, 2)
        meta = {
            "prompt": prompt,
            "negative": negative_prompt,
            "seed": this_seed,
            "steps": steps,
            "cfg": guidance,
            "width": width,
            "height": height,
            "accel": used,
            "checkpoint": ckpt.name,
            "seconds": seconds,
        }
        from app.companion_image import pnginfo_from_meta

        image.save(path, pnginfo=pnginfo_from_meta(meta))
        results.append(
            {
                "path": str(path),
                "filename": name,
                "seed": this_seed,
                "seconds": seconds,
                "checkpoint": ckpt.name,
                "accel": used,
            }
        )
    return results
