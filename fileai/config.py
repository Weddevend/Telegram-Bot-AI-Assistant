import os
from dataclasses import dataclass
from pathlib import Path
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]

@dataclass(frozen=True)
class Settings:
    token: str
    api_key: str
    model: str
    user_id: int
    tracing: bool

    @classmethod
    def load(cls):
        load_dotenv(ROOT / '.env')
        # Never automatically trace raw agent inputs, errors, or chat identifiers.
        tracing = os.getenv('LANGSMITH_TRACING', 'false').lower() == 'true'
        os.environ['LANGSMITH_TRACING'] = 'false'
        os.environ['LANGCHAIN_TRACING_V2'] = 'false'
        os.environ['LANGSMITH_HIDE_INPUTS'] = 'true'
        os.environ['LANGSMITH_HIDE_OUTPUTS'] = 'true'
        uid = os.getenv('ALLOWED_TELEGRAM_USER_ID', '')
        if not uid.isdigit() or int(uid) <= 0:
            raise ValueError('Set ALLOWED_TELEGRAM_USER_ID to your positive numeric Telegram user ID.')
        values = [os.getenv(k, '').strip() for k in ('TELEGRAM_BOT_TOKEN', 'OPENROUTER_API_KEY', 'MODEL_NAME')]
        if not all(values):
            raise ValueError('Set TELEGRAM_BOT_TOKEN, OPENROUTER_API_KEY and MODEL_NAME in .env.')
        return cls(*values, int(uid), tracing)
