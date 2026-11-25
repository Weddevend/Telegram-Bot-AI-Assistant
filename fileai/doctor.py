"""Safe dependency and public model-capability checks. Never prints credentials."""
import argparse
import importlib.util
import os
import shutil
import sys
from pathlib import Path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--online', action='store_true', help='Check public OpenRouter model catalog and YouTube oEmbed')
    args = parser.parse_args()
    print('Python:', sys.version.split()[0], '(recommended: 3.11 or 3.12)')
    for module in ['langchain_classic', 'langchain_openai', 'telegram', 'PIL', 'pymupdf', 'pdf2docx', 'img2pdf', 'cv2', 'rembg', 'whisper', 'yt_dlp']:
        print(module + ':', 'available' if importlib.util.find_spec(module) else 'MISSING')
    for exe in ['ffmpeg', 'ffprobe', 'deno']:
        print(exe + ':', 'available' if shutil.which(exe) else 'MISSING')
    print('LibreOffice:', 'available' if shutil.which('soffice') or Path('/Applications/LibreOffice.app/Contents/MacOS/soffice').exists() else 'MISSING')
    if args.online:
        import httpx
        from dotenv import load_dotenv
        from .config import ROOT
        load_dotenv(ROOT / '.env')
        try:
            r = httpx.get('https://openrouter.ai/api/v1/models', timeout=30)
            r.raise_for_status()
            models = r.json()['data']
            name = os.getenv('MODEL_NAME', '')
            match = next((m for m in models if m['id'] == name), None)
            print('Configured model supports tools:', bool(match and 'tools' in match.get('supported_parameters', [])))
            print('Examples of tool-capable free models (availability can change):')
            for m in [m for m in models if m['id'].endswith(':free') and 'tools' in m.get('supported_parameters', [])][:8]:
                print(' ', m['id'])
            response = httpx.get('https://www.youtube.com/oembed', params={'url': 'https://www.youtube.com/watch?v=jNQXAC9IVRw', 'format': 'json'}, timeout=20)
            print('YouTube oEmbed HTTP:', response.status_code)
        except Exception:
            print('Online check failed; no secrets or raw network errors displayed.')

if __name__ == '__main__':
    main()
