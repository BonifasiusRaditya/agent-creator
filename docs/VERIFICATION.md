# Verification — 27 October 2026

## Release checks

```text
python -m pytest tests --basetemp=test-results/release -q
21 passed in 28.35s

python -m compileall -q trendforge scripts tests
Passed

node --check trendforge/static/app.js
Passed
```

The automated suite uses isolated local test directories. Its provider contract responses are deliberately simulated; its media processing, local API, database, rendering, download and subprocess tests run the actual implementation.

## Verified media profiles

| Profile | Measured duration | Video | Audio |
|---|---|---|---|
| Three clips → 30 seconds | 30.004 seconds | 1080×1920, 30 fps, H.264, yuv420p | AAC, 48 kHz, stereo |
| Five clips → 60 seconds | 60.014667 seconds | 1080×1920, 30 fps, H.264, yuv420p | AAC, 48 kHz, stereo |

Both profiles passed full decoding and downloaded-file validation. Mixed orientation, input frame rates and missing audio were included. A separate export embedded reviewed test subtitles: decoded frame pixels confirmed text was rendered, and the SRT preserved the reviewed words. Previous export versions remained available. Deleting each test project removed its application-managed media and records.

A real running subprocess was started and cancelled; the test verified that it exited and cancellation was reported rather than success. Restart/interruption behavior, request-key reuse, stale revisions, source validation, expired metadata cleanup, oversized requests, origin/CSRF checks, and credential redaction were also checked.

## Speech runtime

The multilingual faster-whisper Base model was downloaded and executed locally on CPU with INT8. The official Whisper test audio produced three timed cues in approximately 2.12 seconds on this machine. The installed model is retained in the main application's model cache.

This confirms actual model inference and cue generation. The reference recording is English; it does not establish an Indonesian word-error-rate claim. Representative Indonesian creator footage still needs its normal review in the application.

## Browser workflow

An isolated test workspace completed this sequence through the actual interface:

1. Sign in and create a project.
2. Continue with an original topic and write a complete brief/shot list.
3. Approve the brief.
4. Upload three synthetic test clips through the browser file chooser; observe real upload progress and validation.
5. Generate and approve the automatic edit plan.
6. Observe actual asynchronous preparation and automatic navigation to subtitle review.
7. Confirm the correctly detected lack of speech.
8. Export a final video and download the MP4 through the browser.
9. Mark the downloaded result ready to upload.

The final video reported readyState 4, 1080×1920 dimensions, a 30.004-second duration, and no browser playback error. The tab's captured warning/error log was empty. At a 393×852 viewport, the document had no horizontal overflow. The temporary viewport override was reset after checking.

The synthetic QA project and the matching browser download were removed after verification. The real workspace is separate and awaits the user's own setup password; it contains no seeded projects or provider credentials.

Screenshots: `screenshots/dashboard.png` and `screenshots/workflow.png`.

## WorkBuddy protocol

The official MCP Python client successfully initialized the stdio server, discovered 16 tools, and called the local service health tool. No approval tools are exposed. The connector configuration contains executable/location settings, not API keys or the service token.

Actual import and account access in Tencent WorkBuddy, live AI-provider requests, YouTube research with the user's API key, and Pexels access remain account-specific setup. Configure these through Connections; they are not claimed as live-tested without credentials.

## Delivery

- Main local service: `http://127.0.0.1:8765`.
- Setup and operating guide: `README.md`.
- Architecture and endpoint overview: `IMPLEMENTATION.md`.
- Importable local connector package: `../build/trendforge-workbuddy.zip`.
- Locked dependencies: `../uv.lock`.

