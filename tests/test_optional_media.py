"""Real converter smoke tests, skipped when their dependencies are absent."""
import importlib.util
import json
import shutil
import subprocess
from pathlib import Path
import pytest
from langchain_core.language_models.fake_chat_models import FakeMessagesListChatModel
from langchain_core.messages import AIMessage
from fileai.storage import Workspace
from fileai.tools import build_tools


def toolset(tmp_path):
    ws = Workspace(tmp_path / 'files')
    llm = FakeMessagesListChatModel(responses=[AIMessage(content='summary')])
    return ws, {t.name:t for t in build_tools(ws,llm)}


def test_docx_to_pdf_real(tmp_path):
    if not (shutil.which('soffice') or Path('/Applications/LibreOffice.app/Contents/MacOS/soffice').exists()):
        pytest.skip('LibreOffice missing')
    from docx import Document
    import pymupdf
    ws, tools = toolset(tmp_path)
    p=ws.allocate('.docx')
    doc=Document(); doc.add_paragraph('FileAI conversion smoke test.'); doc.save(p)
    result=json.loads(tools['docx_to_pdf'].invoke({'file_id':p.name}))
    assert result['ok'], result
    with pymupdf.open(ws.get(result['result']['file_id'])) as pdf:
        assert 'FileAI' in pdf[0].get_text()


def test_pdf_to_docx_real(tmp_path):
    if not importlib.util.find_spec('pdf2docx'):
        pytest.skip('pdf2docx missing')
    import pymupdf
    from docx import Document
    ws, tools=toolset(tmp_path)
    p=ws.allocate('.pdf')
    with pymupdf.open() as pdf:
        pdf.new_page().insert_text((72,72),'FileAI editable text.')
        pdf.save(p)
    result=json.loads(tools['pdf_to_docx'].invoke({'file_id':p.name}))
    assert result['ok'],result
    assert 'FileAI' in '\n'.join(x.text for x in Document(ws.get(result['result']['file_id'])).paragraphs)


def test_image_inpainting_real(tmp_path):
    if not importlib.util.find_spec('cv2'):
        pytest.skip('OpenCV missing')
    from PIL import Image
    ws, tools=toolset(tmp_path)
    p=ws.allocate('.png'); Image.new('RGB',(80,80),'blue').save(p)
    ws.rights=True
    result=json.loads(tools['remove_image_watermark'].invoke(dict(file_id=p.name,x=10,y=10,width=10,height=10)))
    assert result['ok'],result
    assert Image.open(ws.get(result['result']['file_id'])).size == (80,80)


def test_ffmpeg_real(tmp_path):
    if not shutil.which('ffmpeg') or not shutil.which('ffprobe'):
        pytest.skip('FFmpeg/ffprobe missing')
    ws,tools=toolset(tmp_path)
    p=ws.allocate('.mp4')
    subprocess.run(['ffmpeg','-nostdin','-y','-v','error','-f','lavfi','-i','color=c=blue:s=160x120:d=2','-f','lavfi','-i','sine=frequency=440:duration=2','-c:v','libx264','-c:a','aac','-shortest',str(p)],check=True,timeout=30)
    for name in ('compress_video','extract_audio'):
        result=json.loads(tools[name].invoke({'file_id':p.name}))
        assert result['ok'],result


def test_video_watermark_real(tmp_path):
    if not shutil.which('ffmpeg') or not shutil.which('ffprobe') or not importlib.util.find_spec('cv2'):
        pytest.skip('FFmpeg/ffprobe/OpenCV missing')
    ws, tools = toolset(tmp_path)
    p = ws.allocate('.mp4')
    subprocess.run(['ffmpeg','-nostdin','-y','-v','error','-f','lavfi','-i','testsrc=size=160x120:duration=1','-c:v','libx264','-pix_fmt','yuv420p',str(p)], check=True, timeout=30)
    ws.rights = True
    result = json.loads(tools['remove_video_watermark'].invoke(dict(file_id=p.name, x=10, y=10, width=20, height=20)))
    assert result['ok'], result
