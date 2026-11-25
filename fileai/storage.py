"""Opaque file IDs; paths and ownership are never selected by the model."""
import re
import shutil
import subprocess
import time
import uuid
from pathlib import Path
from urllib.parse import urlparse, parse_qs

MAX_INPUT = 20_000_000
MAX_OUTPUT = 49_000_000
MAX_STORAGE = 500_000_000
EXTENSIONS = {'.jpg', '.jpeg', '.png', '.webp', '.pdf', '.docx', '.mp4', '.mov', '.mkv', '.webm', '.mp3', '.wav', '.m4a', '.ogg', '.txt', '.vtt', '.srt'}

class Workspace:
    def __init__(self, root: Path):
        self.root = root.resolve()
        self.root.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.rights = False
        self.deliveries: list[str] = []

    def allocate(self, extension: str) -> Path:
        if extension not in EXTENSIONS:
            raise ValueError('Unsupported file extension.')
        self.check_quota()
        return self.root / (uuid.uuid4().hex + extension)

    def get(self, file_id: str, extensions=None) -> Path:
        if not re.fullmatch(r'[a-f0-9]{32}\.[a-z0-9]+', file_id):
            raise ValueError('Use a file ID returned by this bot.')
        path = self.root / file_id
        if path.is_symlink() or not path.is_file() or path.resolve().parent != self.root:
            raise ValueError('File unavailable. Upload it again.')
        if extensions and path.suffix not in extensions:
            raise ValueError('Wrong file type for this operation.')
        if path.stat().st_size > MAX_OUTPUT:
            raise ValueError('File exceeds processing limit.')
        return path

    def check_quota(self):
        size = sum(p.stat().st_size for p in self.root.rglob('*') if p.is_file())
        if size >= MAX_STORAGE:
            raise ValueError('Storage limit reached. Use /reset.')

    def publish(self, path: Path) -> dict:
        if path.parent != self.root or path.is_symlink() or not path.is_file():
            raise ValueError('No output was produced.')
        if not 0 < path.stat().st_size <= MAX_OUTPUT:
            path.unlink(missing_ok=True)
            raise ValueError('Output exceeds Telegram limit or is empty.')
        self.check_quota()
        self.deliveries.append(path.name)
        return {'file_id': path.name, 'bytes': path.stat().st_size}

    def cleanup(self, age=86400):
        for p in self.root.iterdir():
            if p.is_file() and time.time() - p.stat().st_mtime > age:
                p.unlink()

    def reset(self):
        shutil.rmtree(self.root)
        self.root.mkdir(mode=0o700)
        self.rights = False
        self.deliveries.clear()

    def require_rights(self):
        if not self.rights:
            raise ValueError('First send /authorize to confirm ownership or permission for this request.')


def run(args: list[str], timeout=300):
    try:
        subprocess.run(args, check=True, timeout=timeout, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except FileNotFoundError:
        raise ValueError('Required executable missing. Run python -m fileai.doctor.') from None
    except (subprocess.TimeoutExpired, subprocess.CalledProcessError):
        raise ValueError('Processing failed or timed out. Check file format and dependencies.') from None


def youtube_url(url: str) -> str:
    parsed = urlparse(url)
    if parsed.scheme != 'https' or parsed.username or parsed.password or parsed.port not in (None, 443):
        raise ValueError('Use an HTTPS YouTube video URL.')
    host = (parsed.hostname or '').lower()
    if host == 'youtu.be':
        video_id = parsed.path.strip('/')
    elif host in {'youtube.com', 'www.youtube.com', 'm.youtube.com'}:
        if parsed.path == '/watch':
            video_id = parse_qs(parsed.query).get('v', [''])[0]
        elif parsed.path.startswith(('/shorts/', '/embed/')):
            video_id = parsed.path.split('/')[2]
        else:
            video_id = ''
    else:
        video_id = ''
    if not re.fullmatch(r'[A-Za-z0-9_-]{11}', video_id):
        raise ValueError('Only individual YouTube videos are accepted.')
    return 'https://www.youtube.com/watch?v=' + video_id
