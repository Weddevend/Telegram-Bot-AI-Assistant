import json
from pathlib import Path
from types import SimpleNamespace
import pytest
from langchain_core.language_models.fake_chat_models import FakeMessagesListChatModel
from langchain_core.messages import AIMessage, HumanMessage
from fileai.storage import Workspace, youtube_url
from fileai.tools import build_tools
from fileai.agent import FileAgent
from fileai.bot import is_owner

class ToolModel(FakeMessagesListChatModel):
    def bind_tools(self, tools, **kwargs):
        return self

@pytest.fixture
def ws(tmp_path):
    return Workspace(tmp_path / 'private')

@pytest.fixture
def tools(ws):
    llm = ToolModel(responses=[AIMessage(content='A concise summary.')])
    return {t.name: t for t in build_tools(ws, llm)}


def invoke(tools, name, **args):
    return json.loads(tools[name].invoke(args))

@pytest.mark.parametrize('value', ['../.env', '/etc/passwd', '.env', 'a'*32+'.txt/../.env'])
def test_path_traversal(ws, value):
    with pytest.raises(ValueError):
        ws.get(value)


def test_symlink_block(ws, tmp_path):
    target = tmp_path / 'secret.txt'
    target.write_text('private')
    path = ws.root / ('a'*32+'.txt')
    path.symlink_to(target)
    with pytest.raises(ValueError):
        ws.get(path.name)

@pytest.mark.parametrize('url', ['http://youtube.com/watch?v=jNQXAC9IVRw', 'https://youtube.com.evil.com/watch?v=jNQXAC9IVRw', 'https://localhost/a', 'https://user@youtube.com/watch?v=jNQXAC9IVRw', 'https://youtube.com/playlist?list=a'])
def test_urls_rejected(url):
    with pytest.raises(ValueError):
        youtube_url(url)


def test_url_canonicalized():
    assert youtube_url('https://youtu.be/jNQXAC9IVRw?list=abc') == 'https://www.youtube.com/watch?v=jNQXAC9IVRw'


def test_permission_gate(tools):
    for name, args in [('download_youtube', {'url': 'https://youtu.be/jNQXAC9IVRw'}), ('remove_image_watermark', dict(file_id='a'*32+'.png', x=1,y=1,width=2,height=2))]:
        result = invoke(tools, name, **args)
        assert not result['ok'] and '/authorize' in result['error']


def test_image_pdf_text_summary(ws, tools):
    from PIL import Image
    import pymupdf
    path = ws.allocate('.png')
    Image.new('RGB', (100, 100), 'red').save(path)
    compressed = invoke(tools, 'compress_image', file_id=path.name)
    assert compressed['ok']
    assert ws.get(compressed['result']['file_id']).suffix == '.jpg'
    pdf = invoke(tools, 'images_to_pdf', file_ids=[path.name, path.name])
    with pymupdf.open(ws.get(pdf['result']['file_id'])) as doc:
        assert len(doc) == 2
    textpdf = ws.allocate('.pdf')
    with pymupdf.open() as doc:
        doc.new_page().insert_text((72,72), 'A test document about renewable energy.')
        doc.save(textpdf)
    extracted = invoke(tools, 'extract_pdf_text', file_id=textpdf.name)
    fid = extracted['result']['file_id']
    assert 'renewable' in ws.get(fid).read_text()
    summary = invoke(tools, 'summarize_text', file_id=fid)
    assert summary['ok'] and 'concise' in summary['result']['summary']


def test_validation_and_errors(tools):
    assert not invoke(tools, 'compress_image', file_id='missing', quality=999)['ok']
    assert isinstance(tools['compress_image'].invoke({'file_id':'missing','quality':'bad'}), str)
    assert not invoke(tools, 'get_video_info', url='https://localhost/secret')['ok']
    assert len(tools) == 15
    for t in tools.values():
        assert t.description and t.args_schema.model_json_schema()['properties']


def test_agent_tool_call_and_followup(ws):
    responses = [
        AIMessage(content='', tool_calls=[{'name':'compress_image','args':{'file_id':'missing'},'id':'call1','type':'tool_call'}]),
        AIMessage(content='Please upload the image.'),
        AIMessage(content='You asked to compress an image.')]
    model = ToolModel(responses=responses)
    agent = FileAgent(ws, model)
    assert 'upload' in agent.invoke('Compress my image.')
    assert 'compress' in agent.invoke('What did I ask?')
    assert len(agent.history.messages) == 4
    assert isinstance(agent.history.messages[0], HumanMessage)


def test_owner_only_private_chat():
    update = SimpleNamespace(effective_user=SimpleNamespace(id=42), effective_chat=SimpleNamespace(type='private'))
    assert is_owner(update, 42)
    assert not is_owner(update, 43)
    update.effective_chat.type = 'group'
    assert not is_owner(update, 42)


def test_reset_and_expiry(ws):
    p = ws.allocate('.txt')
    p.write_text('data')
    ws.rights = True
    ws.cleanup(age=-1)
    assert not p.exists()
    ws.reset()
    assert not ws.rights and not list(ws.root.iterdir())


def test_oembed_mock(tools, monkeypatch):
    import httpx
    def get(url, **kwargs):
        assert url == 'https://www.youtube.com/oembed'
        return httpx.Response(200, json={'title':'Public demo','html':'untrusted embed'}, request=httpx.Request('GET', url))
    monkeypatch.setattr(httpx, 'get', get)
    result = invoke(tools, 'get_video_info', url='https://youtu.be/jNQXAC9IVRw')
    assert result['result']['title'] == 'Public demo'
    assert 'html' not in result['result']


def test_trace_privacy(monkeypatch):
    import fileai.tracing as tracing
    records = []
    monkeypatch.setattr(tracing, 'Client', lambda **kwargs: SimpleNamespace(create_run=lambda **data: records.append(data)))
    with pytest.raises(RuntimeError):
        with tracing.PrivateTrace(True).request():
            raise RuntimeError('secret source text')
    assert len(records) == 1
    assert 'secret source text' not in str(records)
    assert records[0]['inputs'] == {} and records[0]['outputs'] == {}


def test_invalid_upload_pdf_is_safe(ws, tools):
    p = ws.allocate('.pdf')
    p.write_bytes(b'not a PDF /private/secret')
    result = invoke(tools, 'extract_pdf_text', file_id=p.name)
    assert not result['ok'] and '/private' not in str(result)


def test_empty_scanned_pdf(ws, tools):
    import pymupdf
    p = ws.allocate('.pdf')
    with pymupdf.open() as doc:
        doc.new_page()
        doc.save(p)
    result = invoke(tools, 'extract_pdf_text', file_id=p.name)
    assert result['ok'] and 'OCR' in result['result']['notice']


def test_subprocess_errors_sanitized(monkeypatch):
    import subprocess
    from fileai.storage import run
    def fail(*args, **kwargs):
        assert isinstance(args[0], list)
        assert not kwargs.get('shell')
        raise subprocess.CalledProcessError(1, args[0], stderr='private')
    monkeypatch.setattr(subprocess, 'run', fail)
    with pytest.raises(ValueError, match='Processing failed'):
        run(['ffmpeg', 'input'])


def test_limits(ws, tools, monkeypatch):
    import fileai.storage as storage
    p = ws.allocate('.txt')
    p.write_text('large')
    monkeypatch.setattr(storage, 'MAX_OUTPUT', 2)
    with pytest.raises(ValueError):
        ws.publish(p)
    assert not p.exists()
    assert not invoke(tools, 'summarize_text', text='x'*80001)['ok']


def test_bot_denies_unauthorized_without_network(tmp_path, monkeypatch):
    import asyncio
    import fileai.bot as bot
    monkeypatch.setattr(bot, 'ROOT', tmp_path)
    monkeypatch.setattr(bot, 'make_llm', lambda settings: ToolModel(responses=[AIMessage(content='ok')]))
    app = bot.build_app(SimpleNamespace(token='123:local-test',user_id=42,tracing=False))
    update = SimpleNamespace(effective_user=SimpleNamespace(id=99), effective_chat=SimpleNamespace(type='private'), message=None)
    for handler in app.handlers[0]:
        asyncio.run(handler.callback(update, None))


def test_captionless_upload_enters_memory(tmp_path, monkeypatch):
    import asyncio
    from unittest.mock import AsyncMock
    from langchain_core.chat_history import InMemoryChatMessageHistory
    import fileai.bot as bot
    monkeypatch.setattr(bot, 'ROOT', tmp_path)
    monkeypatch.setattr(bot, 'make_llm', lambda settings: None)
    agent = SimpleNamespace(history=InMemoryChatMessageHistory())
    monkeypatch.setattr(bot, 'FileAgent', lambda ws, llm: agent)
    app=bot.build_app(SimpleNamespace(token='123:local-test', user_id=42, tracing=False))
    async def download(path):
        path.write_text('test')
    remote=SimpleNamespace(download_to_drive=download)
    media=SimpleNamespace(file_name='notes.txt', file_size=4, get_file=AsyncMock(return_value=remote))
    message=SimpleNamespace(text=None,caption=None,document=media,video=None,audio=None,voice=None,photo=None,reply_text=AsyncMock())
    update=SimpleNamespace(effective_user=SimpleNamespace(id=42),effective_chat=SimpleNamespace(type='private'),message=message)
    asyncio.run(app.handlers[0][-1].callback(update,None))
    assert len(agent.history.messages)==2
    assert 'Uploaded file ID:' in agent.history.messages[0].content


def test_external_docx_relationship_rejected(ws, tools):
    import zipfile
    p=ws.allocate('.docx')
    with zipfile.ZipFile(p,'w') as archive:
        archive.writestr('word/document.xml','<document/>')
        archive.writestr('word/_rels/document.xml.rels', "<Relationships><Relationship TargetMode = 'External' Target='https://example.org'/></Relationships>")
    assert not invoke(tools,'docx_to_pdf',file_id=p.name)['ok']
