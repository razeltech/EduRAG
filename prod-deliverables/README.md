# EduRAG — client test pack

Local LAN learning assistant. Nothing is sent to the cloud. Port **4747** only.

## On the test PC

1. Unzip / copy the appliance folder (see PACKING-LIST.md).
2. Right-click **Setup-EduRAG.bat** → Run as administrator (first time).
3. Later days: double-click **Start-EduRAG.bat**. Leave that window open.
4. This PC: http://127.0.0.1:4747  
   Other devices on the same Wi-Fi: the LAN URL printed in the Start window.

## Demo seats

| Seat    | Email                  | Password    |
|---------|------------------------|-------------|
| Admin   | admin@edurag.local     | admin123    |
| Teacher | teacher@edurag.local   | teacher123  |
| Student | student@edurag.local   | student123  |

Click a seat on the sign-in screen. Change these passwords before a real class.

## Stop (required)

Double-click **Stop-EduRAG.bat**. That unloads the chat model from VRAM and frees port 4747. Do not only kill the window if you can help it.

## Do not

- Bind 8080 or 3636
- Point config at a cloud API
- Open 4747 on the Public firewall profile
- Copy `data/` or `config.yaml` JWT secrets between sites

Read TEST-PLAN.md before you sign off.
