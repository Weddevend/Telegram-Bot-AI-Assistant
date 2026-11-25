from langchain_classic.agents import AgentExecutor, create_tool_calling_agent
from langchain_core.chat_history import InMemoryChatMessageHistory
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.runnables.history import RunnableWithMessageHistory
from langchain_openai import ChatOpenAI
from .prompts import SYSTEM
from .tools import build_tools


def make_llm(settings):
    return ChatOpenAI(model=settings.model, api_key=settings.api_key,
                      base_url='https://openrouter.ai/api/v1', temperature=0,
                      timeout=60, max_retries=1, max_tokens=1800,
                      extra_body={'provider': {'require_parameters': True}})


class FileAgent:
    def __init__(self, workspace, llm):
        self.history = InMemoryChatMessageHistory()
        tools = build_tools(workspace, llm)
        prompt = ChatPromptTemplate.from_messages([
            ('system', SYSTEM), MessagesPlaceholder('chat_history'),
            ('human', '{input}'), MessagesPlaceholder('agent_scratchpad')])
        agent = create_tool_calling_agent(llm, tools, prompt)
        executor = AgentExecutor(agent=agent, tools=tools, max_iterations=8,
                                 max_execution_time=1100, verbose=False,
                                 handle_parsing_errors='Invalid response. Use the tool schema.')
        self.chain = RunnableWithMessageHistory(
            executor, lambda session_id: self.history,
            input_messages_key='input', history_messages_key='chat_history',
            output_messages_key='output')

    def invoke(self, text):
        # One private owner/session. Retain at most six complete exchanges.
        self.history.messages = self.history.messages[-12:]
        for message in self.history.messages:
            if isinstance(message.content, str):
                message.content = message.content[:12000]
        return self.chain.invoke({'input': text}, config={'configurable': {'session_id': 'private'}})['output']
