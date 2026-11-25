"""Isolated heavyweight jobs (invoked only with application-owned paths)."""
import os
import sys
from pathlib import Path


def main():
    operation, source, target = sys.argv[1:]
    model_root = Path(__file__).resolve().parents[1] / 'models'
    os.environ.setdefault('U2NET_HOME', str(model_root / 'rembg'))
    os.environ.setdefault('XDG_CACHE_HOME', str(model_root / 'cache'))
    if operation == 'background':
        from rembg import remove
        Path(target).write_bytes(remove(Path(source).read_bytes()))
    elif operation == 'pdf_docx':
        import pymupdf
        from pdf2docx import Converter
        with pymupdf.open(source) as doc:
            if doc.is_encrypted or len(doc) > 100:
                raise ValueError('PDF conversion limit is 100 unencrypted pages.')
        converter = Converter(source)
        try:
            converter.convert(target, multi_processing=False)
        finally:
            converter.close()
    elif operation == 'whisper':
        import whisper
        from whisper.utils import get_writer
        model_name = os.getenv('WHISPER_MODEL', 'base')
        if model_name not in {'tiny', 'base', 'small'}:
            raise ValueError('WHISPER_MODEL must be tiny, base or small.')
        model = whisper.load_model(model_name)
        result = model.transcribe(source, fp16=False, verbose=False)
        Path(target).write_text(result['text'], encoding='utf-8')
        get_writer('srt', str(Path(target).parent))(result, Path(target).stem, {})
    else:
        raise ValueError('Unknown operation.')

if __name__ == '__main__':
    main()
