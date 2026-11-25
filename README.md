# FileAI — private Telegram file assistant

FileAI turns natural-language requests into local document and media operations. It can also chat and summarize through OpenRouter. A LangChain classic tool-calling agent selects among 15 typed tools, chains their results, and remembers follow-up questions. This project is intended for a single trusted owner on a personal computer.

## Features

| Tool | Implementation / behavior |
|---|---|
| `remove_background` | Local rembg default segmentation model; transparent PNG |
| `compress_image` | Pillow optimized JPEG, adjustable quality |
| `images_to_pdf` | img2pdf; up to 20 photos in supplied order |
| `remove_image_watermark` | OpenCV inpainting in a user-specified rectangle; authorization required |
| `compress_video` | FFmpeg H.264/AAC MP4, adjustable CRF |
| `extract_audio` | FFmpeg MP3 extraction |
| `remove_video_watermark` | FFmpeg delogo, fixed rectangle; authorization required |
| `transcribe_video` | Local OpenAI Whisper, TXT and SRT output |
| `docx_to_pdf` | Headless LibreOffice, isolated temporary profile |
| `pdf_to_docx` | pdf2docx, best effort editable layout |
| `extract_pdf_text` | PyMuPDF text-layer extraction |
| `summarize_text` | LCEL `prompt | llm | StrOutputParser`, chunk summaries then synthesis |
| `get_video_info` | Real keyless YouTube oEmbed API, parsed JSON title/author |
| `download_youtube` | yt-dlp, authorized public single videos only |
| `get_subtitles` | yt-dlp human or automatic VTT captions when available |

## macOS setup

Use Python **3.12** (3.11 is also a reasonable choice). Avoid Python 3.14 for this ML dependency stack. Install Homebrew from its official site if it is not already installed, then:

```bash
brew install python@3.12 ffmpeg deno
brew install --cask libreoffice
cd "/absolute/path/to/FileAI"
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
# Exact versions installed and tested on this Mac are recorded in requirements-lock.txt.
```

The full environment is installed in `.venv` on this Mac. It was created using the available Python 3.12 runtime. For a fresh installation, use the setup commands above. The full environment is large: Whisper/PyTorch, ONNX Runtime and image processing libraries can require several GB. Initial Whisper and rembg use downloads model weights. These models subsequently run locally. `deno` and yt-dlp's default extras support modern YouTube JavaScript challenges; availability still varies by region/video and YouTube changes.

If `.env` is absent (e.g. after downloading the source archive), create it without overwriting an existing local file:

```bash
test -f .env || cp .env.example .env
chmod 600 .env
nano .env
```

Set these locally, never in source code:

- `OPENROUTER_API_KEY`: your **new, rotated** OpenRouter key.
- `TELEGRAM_BOT_TOKEN`: the replacement token issued by BotFather.
- `LANGSMITH_API_KEY`: a replacement LangSmith key.
- `ALLOWED_TELEGRAM_USER_ID`: your positive numeric Telegram user ID, not your username, bot ID or phone number. Obtain it from a trusted Telegram ID lookup or an existing authenticated Telegram client. Keep it local. The bot intentionally refuses startup without this value and ignores group chats and other users.
- `MODEL_NAME`: a current OpenRouter model with `tools` support. Do not assume the model named in an earlier chat exists or is still free.
- `LANGSMITH_TRACING=true` to enable privacy-preserving operational traces. Default is false, so development/testing does not upload anything accidentally.
- `WHISPER_MODEL=base` (optional; allowed: tiny/base/small).

The Telegram owner ID is configured in the local `.env`. The supplied credentials were placed only in the local ignored `.env`. They are not in the distributable archive. They appeared in chat and should be revoked and replaced before deployment.

```bash
python -m fileai.doctor
python -m fileai.doctor --online
python -m pytest -q
python main.py
```

`doctor --online` fetches the public OpenRouter model catalog, checks the configured model's tool capability, lists some current free candidates, and checks public YouTube oEmbed. It does not print credentials or make a paid completion. Choose a model and set `MODEL_NAME`; catalog presence does not guarantee quota, uptime or provider availability. Free plans have changing limits, and paid models can incur charges.

Only one polling process should use a bot token at a time. Stop with Ctrl-C. A pre-existing Telegram webhook must be removed before polling can work. The startup drops queued updates to avoid replaying old processing requests.

## Using the bot

1. Send `/start` in a **private** chat with your bot.
2. Upload a document, image, video or audio. The bot returns a random file ID. Photos sent as Telegram photos are already compressed; send as a document to preserve original quality.
3. Send a task, optionally as the upload caption. For multiple photos, upload each first and include their IDs in the desired order.
4. Generated files are sent automatically. Follow-ups can refer to previous file IDs; `/files` lists available files.
5. Before downloading YouTube/subtitles or removing a watermark, send `/authorize` to affirm you own the content or have the necessary permission. Authorization is enforced in code, not by trusting an LLM argument. It lasts for the next processing request, including multiple tools in that request. `/revoke` cancels it.
6. `/reset` deletes local files and in-memory chat history. It does not delete messages from Telegram or provider records.

## Architecture and defense notes

`main.py` → `bot.py` validates the Telegram sender and accepts an upload → `FileAgent` formats a `ChatPromptTemplate` → `create_tool_calling_agent` asks the model for a tool name and typed arguments → `AgentExecutor` runs it and supplies its JSON result back to the model → the agent produces a final answer and the bot sends generated files.

- `fileai/config.py`: local configuration and fail-closed access control setup.
- `fileai/storage.py`: file IDs, containment, size limits, retention, command timeouts and YouTube URL validation.
- `fileai/tools.py`: 15 typed LangChain tools with docstrings and safe error envelopes. The `safe` decorator applies `@tool` to a signature-preserving error wrapper.
- `fileai/agent.py`: classic agent/executor, scratchpad, tool results and `RunnableWithMessageHistory`.
- `fileai/prompts.py`: role, evidence rules, follow-ups, rights checks and treatment of extracted material as untrusted data.
- `fileai/worker.py`: heavyweight local jobs in timeout-controlled subprocesses.
- `fileai/tracing.py`: privacy-preserving request traces.
- `fileai/demo.py`: repeatable actual agent execution with a **simulated** LLM.

The LLM chooses tools using their names, descriptions and JSON schemas. Application code validates arguments, enforces permissions and restricts paths regardless of what the model asks. A failed tool returns `{"ok": false, "error": "..."}`; success returns `{"ok": true, "result": ...}`. oEmbed JSON is parsed and reduced to selected fields, not passed through as HTML.

Memory is one in-memory private session. It retains six prior exchanges, with bounded message lengths. It is reset on restart or `/reset`. File IDs in previous exchanges enable follow-up operations. Tool scratchpads are per request; full file content is not placed in conversation memory. `/files` provides recovery if an old ID has fallen out of memory.

Summarization is a separate LCEL chain with a prompt, the same OpenRouter model and a string parser. Text is split into 10,000-character chunks and reduced to a final summary. The overall input limit is 80,000 characters; this is character-based, not an exact token budget. Smaller-context models may require smaller inputs. Summaries can contain mistakes and should be reviewed.

Model choice is configurable because free endpoints change. Select a tool-capable model using the catalog and demonstrate it live; the included offline tests use a deterministic simulated model, not a claim that a particular remote model was evaluated.

## Three illustrative conversations

These are **sample conversations, not recorded live results**. Replace placeholder IDs with actual upload IDs. Exact phrasing depends on the selected model.

### 1. Photo conversion and follow-up

**User:** [uploads a PNG] Compress this photo.

**Bot:** Created an optimized JPEG. [sends output]

**User:** Now put that compressed photo into a PDF.

**Bot:** Created a one-page PDF using the JPEG from the previous request. [sends PDF]

Tools: `compress_image`, then `images_to_pdf`. Memory supplies the previous output ID.

### 2. PDF text and summary

**User:** [uploads a text-based PDF] Extract the text and summarize it in Russian.

**Bot:** Extracted the text and created a Russian summary. [sends TXT files]

**User:** Make the summary three bullet points in English.

**Bot:** [uses the previous summary TXT ID and sends a shorter English summary]

Tools: `extract_pdf_text`, `summarize_text`, then another `summarize_text` call.

### 3. Permitted YouTube video

**User:** What is the title and author of this YouTube video? [public link]

**Bot:** [reports title and author from oEmbed]

**User:** /authorize

**Bot:** You confirmed ownership or permission for your next processing request.

**User:** Download this video, extract the audio, transcribe it locally and summarize it in English.

**Bot:** [sends permitted video, MP3, TXT, SRT and summary, if size/duration/availability limits permit]

Tools: `get_video_info`; later `download_youtube` → `extract_audio` → `transcribe_video` → `summarize_text`. Eight agent iterations allow this sequence and a final response. No download is attempted without `/authorize`.

## LangSmith: actual traces versus examples

Operational mode (`LANGSMITH_TRACING=true`) uploads a request run with status and duration only. Chat text, file contents, file IDs, Telegram IDs, raw errors, credentials and nested LLM/tool inputs are excluded. This is deliberately less detailed than a full agent trace. Automatic nested tracing is disabled even if legacy tracing environment variables are present. OpenRouter still receives prompts and requested summary text; hiding LangSmith inputs does not make OpenRouter local.

For assignment evidence of an actual nested agent → tool → LCEL execution, use the synthetic demo:

```bash
python -m fileai.demo
python -m fileai.demo --trace
# Real OpenRouter model, synthetic text only (consumes quota):
python -m fileai.demo --live --trace
```

The second command uploads actual execution traces under **FileAI-synthetic-demo**, using harmless synthetic text and a **simulated LLM**, with inputs and outputs hidden. It does not prove real OpenRouter reasoning. Open LangSmith, confirm the runs arrived, and take screenshots of the run tree. A request to upload is not proof of receipt; verify in the dashboard. Do not fabricate trace URLs or label the sample conversations as observed runs.

For a live defense, run the configured bot with tracing enabled and non-sensitive test inputs; show the operational trace plus real Telegram outputs. If your instructor requires detailed traces from a real LLM, use a dedicated synthetic-only demonstration and review its privacy before enabling full callbacks. The default bot intentionally does not send those details.

Verified real OpenRouter traces from development are linked in `VERIFICATION.md`. The live demo uses the `FileAI-live-demo` project. These links are private to the LangSmith account; capture reviewed screenshots or grant your instructor access before submission. The sample conversations above remain illustrative.

## Limits and privacy

- Standard Telegram Bot API downloads are limited to 20 MB; outgoing files are capped conservatively at 49 MB. Large local videos are unsuitable for this bot.
- Files stay in ignored `storage/private/`. Files older than 24 hours are removed on startup and subsequent requests; nothing runs a cleanup timer while the app is stopped. `/reset` deletes them immediately. Storage quota is 500 MB, checked before and after operations; it is not a hard OS disk quota.
- Supported extensions are allowlisted; parsers validate actual content. Random IDs prevent using arbitrary paths or exposing upload names. Symlinks and traversal are rejected. Commands use argument lists without a shell. File parsers are not a security sandbox; process only trusted uploads and keep dependencies updated.
- YouTube URLs are canonicalized to individual HTTPS YouTube videos. No playlists, arbitrary sites, cookies, DRM bypass or login bypass. Downloads are limited to 30 minutes and about 45 MB; videos may have no compatible format or subtitles. Use only downloads allowed by the rights holder and applicable service terms.
- Compression is lossy and may increase small/already-optimized files. Review results. Watermark removal is approximate inpainting of a fixed rectangle, not recovery of the hidden original; moving marks are not tracked.
- PDF-to-DOCX may change layout. No OCR: scanned PDFs can produce no text. Encrypted/oversized PDFs are rejected. DOCX files with external relationships (including external hyperlinks) are rejected to prevent fetching remote resources.
- Local Whisper/rembg can be slow, especially on first use. Jobs have timeouts; very large or long files may fail. No promise of instant processing or unlimited free usage.
- Never turn on HTTP debug logs: Telegram URLs contain the bot token. Do not upload `.env`, user files, model weights or unredacted traces.

## GitHub submission (manual; nothing is published automatically)

Create an empty repository on GitHub without a generated README, then run from this folder:

```bash
git init
git branch -M main
git check-ignore .env
# Expected: .env
git add .gitignore .env.example README.md VERIFICATION.md requirements.txt pytest.ini main.py fileai tests
# If present, also add requirements-lock.txt after reviewing it.
git status --short
git ls-files .env
# Expected: NO output from the preceding command.
git diff --cached --stat
git diff --cached
# Inspect the staged contents before committing.
git commit -m "Build FileAI Telegram file assistant"
git remote add origin https://github.com/YOUR_USERNAME/FileAI.git
git push -u origin main
```

Use the repository URL, README and your actual LangSmith screenshots/links in the assignment submission box. For a private repository, grant the instructor access. GitHub publication has **not** been performed for you.

Commit: source, tests, README, verification notes, `.env.example`, `.gitignore`, requirements and optional reviewed lockfile.

Never commit: `.env` or other secret files, `.venv`, `storage`, user media/documents, model weights, logs, caches or unredacted traces. `.gitignore` does not remove a file already tracked by Git. If a secret was previously committed, rotate it first, remove it from tracking (`git rm --cached .env`), then clean repository history as appropriate. Deleting it from the latest commit alone does not revoke it.

## Official references checked during development

- [LangChain classic tool-calling agent](https://reference.langchain.com/python/langchain-classic/agents/tool_calling_agent/base/create_tool_calling_agent)
- [LangSmith privacy controls](https://docs.langchain.com/langsmith/mask-inputs-outputs)
- [OpenRouter tool calling](https://openrouter.ai/docs/guides/features/tool-calling)
- [Telegram Bot API](https://core.telegram.org/bots/api)
- [yt-dlp documentation](https://github.com/yt-dlp/yt-dlp)
- [OpenAI Whisper](https://github.com/openai/whisper)
