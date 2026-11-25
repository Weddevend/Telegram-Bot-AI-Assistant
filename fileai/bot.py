import asyncio
import logging
from pathlib import Path
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters
from .agent import FileAgent, make_llm
from .config import ROOT, Settings
from .storage import Workspace, MAX_INPUT, EXTENSIONS
from .tracing import PrivateTrace


def is_owner(update, user_id):
    return bool(update.effective_user and update.effective_user.id == user_id
                and update.effective_chat and update.effective_chat.type == 'private')


def build_app(settings):
    ws = Workspace(ROOT / 'storage' / 'private')
    ws.cleanup()
    agent = FileAgent(ws, make_llm(settings))
    trace = PrivateTrace(settings.tracing)
    app = Application.builder().token(settings.token).concurrent_updates(False).build()

    async def start(update, context):
        if not is_owner(update, settings.user_id):
            return
        await update.message.reply_text(
            'FileAI ready. Upload a file, then describe the task. /files lists file IDs; '
            '/reset deletes local files and memory. Files expire after 24h (checked on requests/startup). '
            'Chat and requested summaries go to OpenRouter. Media processing is local; '
            'YouTube requires internet. /authorize confirms you own or have permission '
            'to download/edit the content for your next request. /revoke cancels it.')

    async def authorize(update, context):
        if is_owner(update, settings.user_id):
            ws.rights = True
            await update.message.reply_text('You confirmed ownership or permission for your next processing request. Send that request now.')

    async def revoke(update, context):
        if is_owner(update, settings.user_id):
            ws.rights = False
            await update.message.reply_text('Authorization revoked.')

    async def reset(update, context):
        if is_owner(update, settings.user_id):
            ws.reset()
            agent.history.clear()
            await update.message.reply_text('Local files and conversation memory deleted. Telegram messages and remote provider records are not deleted.')

    async def files(update, context):
        if is_owner(update, settings.user_id):
            ws.cleanup()
            names = [p.name for p in ws.root.iterdir() if p.is_file() and not p.is_symlink()]
            await update.message.reply_text('\n'.join(names[-60:]) or 'No files.')

    async def handle(update, context):
        if not is_owner(update, settings.user_id):
            return
        message = update.message
        if not message:
            return
        ws.cleanup()
        ws.deliveries.clear()
        text = (message.text or message.caption or '')[:12000]
        media = message.document or message.video or message.audio or message.voice
        extension = None
        if message.photo:
            media, extension = message.photo[-1], '.jpg'
        if media:
            extension = extension or Path(getattr(media, 'file_name', '') or '').suffix.lower()
            extension = extension or ('.ogg' if message.voice else '.mp4' if message.video else '')
            if extension not in EXTENSIONS or not media.file_size or media.file_size > MAX_INPUT:
                await message.reply_text('Unsupported file or size above 20 MB. Use a smaller supported document/image/audio/video.')
                return
            path = ws.allocate(extension)
            try:
                remote = await media.get_file()
                await remote.download_to_drive(path)
                if path.stat().st_size > MAX_INPUT:
                    raise ValueError('Oversized upload')
            except Exception:
                path.unlink(missing_ok=True)
                await message.reply_text('Upload failed. Try a smaller file.')
                return
            await message.reply_text(f'Uploaded file ID: {path.name}')
            if not text:
                agent.history.add_user_message(f'Uploaded file ID: {path.name}')
                agent.history.add_ai_message('File received. Awaiting an operation.')
                return
            text += f'\nUploaded file ID: {path.name}'
        if not text:
            return
        try:
            await message.reply_text('Processing…')
            def process():
                with trace.request():
                    return agent.invoke(text)
            answer = await asyncio.to_thread(process)
            for offset in range(0, min(len(answer), 24000), 3500):
                await message.reply_text(answer[offset:offset+3500])
            for file_id in dict.fromkeys(ws.deliveries):
                with ws.get(file_id).open('rb') as stream:
                    await message.reply_document(stream, filename=file_id, read_timeout=120, write_timeout=120)
        except Exception:
            await message.reply_text('Request failed. Check model availability, dependencies and file format. No private error details were logged.')
        finally:
            ws.rights = False
            ws.deliveries.clear()

    async def error_handler(update, context):
        # Never log Telegram request URLs: they contain the bot token.
        logging.getLogger('fileai').error('Telegram handler failed; details suppressed.')

    for name, handler in [('start', start), ('help', start), ('authorize', authorize), ('revoke', revoke), ('reset', reset), ('files', files)]:
        app.add_handler(CommandHandler(name, handler))
    app.add_handler(MessageHandler(~filters.COMMAND & (filters.TEXT | filters.ATTACHMENT), handle))
    app.add_error_handler(error_handler)
    return app


def main():
    logging.basicConfig(level=logging.CRITICAL)
    try:
        settings = Settings.load()
    except ValueError as exc:
        raise SystemExit(str(exc)) from None
    build_app(settings).run_polling(allowed_updates=[Update.MESSAGE], drop_pending_updates=True)
