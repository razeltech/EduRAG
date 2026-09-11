# Firewall and shutdown

## Inbound LAN (port 4747)

Setup-EduRAG.bat (as Administrator) adds:

```
netsh advfirewall firewall add rule name="EduRAG" dir=in action=allow protocol=TCP localport=4747 profile=private
```

- Profile **Private** only — not Public, not Domain unless you intend that.
- Do not open 11434 (Ollama) to the LAN. Only the EduRAG PC talks to Ollama on localhost.
- Phones must be on the same Wi-Fi as the server PC.

To re-apply without full Setup, run `scripts\firewall-edurag.ps1` elevated.

## Safe close

1. Stop-EduRAG.bat  
   Unloads `qwen2.5:7b-instruct` from VRAM (`keep_alive=0`) and stops the process listening on 4747.
2. Ctrl+C in the Start window also unloads the model (FastAPI shutdown hook).
3. Closing the window with X may skip unload — run Stop-EduRAG.bat after.

Ollama itself can stay installed. We do not leave the 7B weights sitting in 12 GB VRAM.

## Memory budget (RTX 3060 12 GB / 32 GB RAM)

- LLM: Ollama, context 4096, keep_alive **5m**, one model, one parallel slot
- Embeddings: MiniLM ONNX on **CPU**, 2 threads
- OCR: EasyOCR **CPU**, only when a scan has no text
- Do not set `num_gpu: 99` (that tries to pin every layer and can starve the desktop)
