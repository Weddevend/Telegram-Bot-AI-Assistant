"""Real local agent execution with a simulated LLM. Optional actual LangSmith traces."""
import argparse
import os
import logging
import tempfile
from pathlib import Path
from dotenv import load_dotenv
from langchain_core.language_models.fake_chat_models import FakeMessagesListChatModel
from langchain_core.messages import AIMessage
from langsmith import Client, tracing_context
from .agent import FileAgent, make_llm
from .config import ROOT
from .storage import Workspace

class DemoModel(FakeMessagesListChatModel):
    def bind_tools(self, tools, **kwargs):
        return self


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--live', action='store_true', help='Use real OpenRouter with synthetic text; consumes quota')
    parser.add_argument('--trace', action='store_true', help='Upload an actual synthetic demo trace to LangSmith; uses a simulated LLM, no OpenRouter cost')
    args = parser.parse_args()
    logging.basicConfig(level=logging.CRITICAL)
    load_dotenv(ROOT / '.env')
    os.environ['LANGSMITH_TRACING'] = 'false'
    os.environ['LANGCHAIN_TRACING_V2'] = 'false'
    os.environ['LANGSMITH_HIDE_INPUTS'] = 'true'
    os.environ['LANGSMITH_HIDE_OUTPUTS'] = 'true'
    model = DemoModel(responses=[
        AIMessage(content='', tool_calls=[{'name':'summarize_text','args':{'text':'Solar panels turn sunlight into electricity.'},'id':'demo1','type':'tool_call'}]),
        AIMessage(content='Solar panels generate electricity from sunlight.'),
        AIMessage(content='The summary has been saved.'),
        AIMessage(content='The previous topic was solar energy.')])
    if args.live:
        from types import SimpleNamespace
        model = make_llm(SimpleNamespace(model=os.environ['MODEL_NAME'], api_key=os.environ['OPENROUTER_API_KEY']))
    project = 'FileAI-live-demo' if args.live else 'FileAI-synthetic-demo'
    with tempfile.TemporaryDirectory() as temp:
        agent = FileAgent(Workspace(Path(temp)), model)
        client = Client(hide_inputs=True, hide_outputs=True) if args.trace else None
        with tracing_context(enabled=args.trace, client=client, project_name=project):
            print(agent.invoke('Use summarize_text to summarize this source: Solar panels turn sunlight into electricity.'))
            print(agent.invoke('What was the previous topic?'))
        if client:
            client.flush()
        print(('Real OpenRouter model. ' if args.live else 'Actual local execution; simulated LLM. ') + ('Trace upload requested; verify project ' + project if args.trace else 'No remote trace was created.'))

if __name__ == '__main__':
    main()
