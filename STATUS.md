---
name: Coding experiments
summary: Small Python experiments - primes, a curses snake game, and OpenCV/YOLO IP-camera capture and human detection.
stage: paused
state: at-risk
progress: 5 scripts; last commit 2026-09-21
updated: 2026-10-17
purpose: >
  Personal coding sandbox. The camera scripts grab frames from an IP camera and run Ultralytics YOLO
  person detection; the detection scripts also reference Telegram alerts.
stack: [Python, OpenCV, Ultralytics YOLO, requests, curses]
entry_points:
  - primes.py
  - snake.py
  - capture.py
  - human_detect.py
  - headless_detection.py
deploy:
  label: Not applicable
milestones:
  - { label: "Primes and snake game", state: done }
  - { label: "IP-camera frame capture", state: done }
  - { label: "YOLO human detection (desktop and headless)", state: done }
next_action: Privately audit the camera scripts for hard-coded credentials, move them to local config, and rotate any that were pushed.
blockers:
  - Audit privately for hard-coded camera and alert credentials before sharing or resuming work.
boundaries:
  - Never copy credentials, camera addresses or captures into docs, dashboards or chat.
  - Do not open or index captures/.
  - Model weights (*.pt) stay git-ignored.
read_next: []
---

No README. Code headers show camera-config sections in all three camera scripts; the credential risk was
pattern-checked only, not reproduced here. captures/ files are tracked in git, and local `main` has no
commits ahead of `origin/main`. No script was run for this card.
