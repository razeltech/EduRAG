"""Local MiniLM embeddings via ONNX — CPU, offline, no Hugging Face calls."""
from __future__ import annotations

from pathlib import Path

import numpy as np
import onnxruntime as ort
from tokenizers import Tokenizer

from app.config_load import load_config

MAX_LEN = 256


class Embedder:
    def __init__(self, model_dir: Path | None = None):
        cfg = load_config()
        raw = model_dir or Path((cfg.get("embedding") or {}).get("path") or "")
        if not raw or not Path(raw).exists():
            raise FileNotFoundError("Embedding model path missing. Run: python -m app model-discovery")
        self.model_dir = Path(raw)
        onnx_path = self.model_dir / "onnx" / "model_quantized.onnx"
        tok_path = self.model_dir / "tokenizer.json"
        if not onnx_path.is_file() or not tok_path.is_file():
            raise FileNotFoundError(f"ONNX MiniLM files missing in {self.model_dir}")
        self.tokenizer = Tokenizer.from_file(str(tok_path))
        self.tokenizer.enable_truncation(max_length=MAX_LEN)
        self.tokenizer.enable_padding(length=MAX_LEN)
        so = ort.SessionOptions()
        threads = 2
        try:
            threads = int((cfg.get("resources") or {}).get("onnx_threads") or 2)
        except (TypeError, ValueError):
            threads = 2
        so.intra_op_num_threads = max(1, min(threads, 4))
        so.inter_op_num_threads = 1
        self.session = ort.InferenceSession(
            str(onnx_path), sess_options=so, providers=["CPUExecutionProvider"]
        )
        self.dim = 384

    def encode(self, texts: list[str], batch_size: int = 16) -> np.ndarray:
        if not texts:
            return np.zeros((0, self.dim), dtype=np.float32)
        parts = []
        for i in range(0, len(texts), batch_size):
            parts.append(self._encode_batch(texts[i : i + batch_size]))
        return np.vstack(parts)

    def encode_query(self, text: str) -> np.ndarray:
        return self._encode_batch([text])[0]

    def _encode_batch(self, texts: list[str]) -> np.ndarray:
        encoded = self.tokenizer.encode_batch(texts)
        input_ids = np.array([e.ids for e in encoded], dtype=np.int64)
        attention = np.array([e.attention_mask for e in encoded], dtype=np.int64)
        token_types = np.zeros_like(input_ids, dtype=np.int64)
        hidden = self.session.run(
            None,
            {
                "input_ids": input_ids,
                "attention_mask": attention,
                "token_type_ids": token_types,
            },
        )[0]
        mask = attention.astype(np.float32)[:, :, None]
        summed = (hidden * mask).sum(axis=1)
        counts = np.clip(mask.sum(axis=1), 1e-6, None)
        pooled = summed / counts
        norms = np.linalg.norm(pooled, axis=1, keepdims=True)
        norms = np.clip(norms, 1e-12, None)
        return (pooled / norms).astype(np.float32)


_embedder: Embedder | None = None


def get_embedder() -> Embedder:
    global _embedder
    if _embedder is None:
        _embedder = Embedder()
    return _embedder
