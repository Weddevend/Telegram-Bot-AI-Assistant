"""Privacy-first operational traces. Raw agent/LLM callback tracing is disabled."""
import os
import time
from contextlib import contextmanager
from langsmith import Client, tracing_context


class PrivateTrace:
    def __init__(self, enabled=False):
        self.client = Client(hide_inputs=True, hide_outputs=True) if enabled else None

    @contextmanager
    def request(self):
        started = time.monotonic()
        status = 'success'
        try:
            # Suppress nested auto-traces, including exceptions containing source text.
            with tracing_context(enabled=False):
                yield
        except Exception:
            status = 'failure'
            raise
        finally:
            if self.client:
                try:
                    from uuid import uuid4
                    self.client.create_run(
                        name='FileAI request', run_type='chain', id=uuid4(), inputs={},
                        outputs={}, project_name=os.getenv('LANGSMITH_PROJECT', 'FileAI'),
                        extra={'metadata': {'status': status, 'duration_seconds': round(time.monotonic()-started, 2)}},
                        end_time=__import__('datetime').datetime.now(__import__('datetime').timezone.utc))
                except Exception:
                    # Tracing outages must not expose secrets or break processing.
                    pass
