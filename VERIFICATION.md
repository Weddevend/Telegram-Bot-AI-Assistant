# Verification record

## Latest local setup and verification

The project at `/Users/wedness/ProjectNLP/NLP/NLP_ASSign/Ass3` is now configured with the owner's Telegram user ID in `.env`.

- Full `pip install -r requirements.txt` completed successfully in `.venv`; `pip check` found no broken requirements. Exact versions are recorded in `requirements-lock.txt`.
- FFmpeg and Deno are installed through Homebrew.
- Automated suite: **31 passed, zero skipped**. This includes real DOCX/PDF conversion in both directions, image inpainting, video compression, audio extraction and video delogo on synthetic media.
- Telegram authentication and application startup/shutdown succeeded for `@MHA_AI_Agent_bot`; access is restricted to the configured owner. No webhook conflict was found. No messages were sent during this check.
- Real OpenRouter tool calling, LCEL summary and a follow-up question passed again using synthetic text.
- Real background removal produced a valid RGBA PNG from a synthetic image. The current rembg release selected its default local segmentation model.
- Local Whisper `base` transcribed synthesized English speech and wrote valid TXT/SRT outputs. Recognition was approximate: the artificial product name was misspelled. This is a functionality check, not an accuracy benchmark.
- Model files are stored in ignored `models/`, not in source archives.
- Live YouTube downloads/subtitles and a user-driven Telegram file exchange have not been tested. Public oEmbed and Telegram authentication have been tested.

The older record below describes the initial build **before** the complete installation. Its skipped tests and missing-owner notes are superseded by this section.


Development checks on 2026-11-25 (Asia/Almaty).

## Automated tests

`python -m pytest -q`: **27 passed, 3 skipped** on Python 3.12.14, macOS arm64.

Passed: opaque file IDs; traversal and symlink rejection; URL allowlist/canonicalization; rights gates; image compression; multiple photos to PDF; PDF text extraction; empty/scanned and invalid PDF handling; LCEL summary using a deterministic test model; classic agent tool invocation and multi-turn memory; private-owner filtering across Telegram handlers; captionless upload memory; quotas; expiry/reset; sanitized errors; tool schemas; mocked oEmbed; trace privacy; DOCX external-link rejection; **real LibreOffice DOCX → PDF with extracted-text validation**.

Skipped because dependencies were absent: real PDF → DOCX, OpenCV inpainting, FFmpeg compression/audio extraction. These optional tests are included and run automatically when dependencies are installed.

`pip check`: no broken requirements in the installed core test environment. The complete ML environment was NOT installed: the optional OpenCV wheel download fell to about 18 KB/s with roughly 40 minutes remaining for that wheel alone, so it was stopped. This is not a successful full-stack dependency verification.

Core versions exercised: langchain-classic 1.1.0, langchain-core 1.8.4, langchain-openai 1.8.5, langsmith 0.16.2, python-telegram-bot 22.8, Pillow 11.3.0, PyMuPDF 1.26.3, img2pdf 0.6.3. Requirements use bounded major versions, not a full reproducible lockfile. Re-run tests after installing on your machine.

LangChain reports deprecation warnings for the requested classic memory APIs; the requested architecture still executed successfully with these versions. PyMuPDF emitted SWIG deprecation warnings, not test failures.

## Live API checks

- OpenRouter public catalog: HTTP 200; `nvidia/nemotron-3-ultra-550b-a55b:free` advertised tool support and was selected in the local `.env`.
- OpenRouter credential check: HTTP 200.
- Telegram `getMe`: HTTP 200. No Telegram messages were sent, no polling process started, and no webhook modified.
- LangSmith project-list authentication: HTTP 200.
- YouTube oEmbed: HTTP 200 for a public reference video. No YouTube video was downloaded.
- Real OpenRouter demonstration: successful `summarize_text` tool call, nested LCEL summary, output TXT creation, final answer, and a correct follow-up identifying the previous topic.

The live demonstration used only the harmless sentence “Solar panels turn sunlight into electricity.” It did not upload user documents. These are actual observed executions, separate from README sample conversations and the simulated offline demo.

## Verified actual LangSmith traces

Read back from the service after upload. All inspected runs had empty inputs and outputs; neither root run reported an error. Links require access to the user's LangSmith account. They were not publicly shared.

- [Agent → summarize_text → LCEL → real LLM](https://smith.langchain.com/o/ab2591fc-ffe5-4cfb-aa85-36912aeffaaf/projects/p/d38603e2-b882-4f9b-b712-50820c283d13/r/01a213d6-cc10-778b-a43c-0bfa50d172ca?poll=true): 25 inspected runs; types chain, llm, parser, prompt, tool.
- [Follow-up using conversation history](https://smith.langchain.com/o/ab2591fc-ffe5-4cfb-aa85-36912aeffaaf/projects/p/d38603e2-b882-4f9b-b712-50820c283d13/r/01a213d7-07eb-77d9-863a-ab7b510af6c5?poll=true): 13 inspected runs; types chain, llm, parser, prompt.

For the defense, capture the visible run tree or grant the instructor access. No fabricated screenshots or public trace URLs are provided.

## Not verified end to end

- Telegram polling/file transfer with the actual owner (the owner's numeric user ID is not supplied).
- rembg model download/inference and local Whisper model download/transcription.
- FFmpeg compression, audio extraction and delogo on actual media.
- PDF-to-DOCX layout fidelity, real OpenCV inpainting and YouTube download/subtitle availability.
- The complete set of heavy ML wheels together, and behavior on Intel Macs or older macOS releases.

These functions have implementations, but should not be presented as tested live. Install the full requirements plus FFmpeg, Deno and LibreOffice; run doctor and all tests, then try your own authorized media.

## Delivery and secrets

The source archive is built from an explicit source-file allowlist. It contains no `.env`, virtual environment, Git history, private media, model weights or logs. A byte-for-byte scan against all three supplied credentials passed. Local `.env` permissions are 0600 and Git ignores it; `git ls-files .env` returned no files. A local Git repository was initialized for convenience; no commit, remote or GitHub publication was made.

The local `.env` has the verified model selected and privacy-preserving operational tracing enabled. `ALLOWED_TELEGRAM_USER_ID` remains blank pending your own ID. This intentionally prevents accidental public bot access. Rotate all three exposed credentials before use.
