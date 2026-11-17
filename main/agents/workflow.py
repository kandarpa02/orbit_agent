from agents import (
    Agent,
    OpenAIChatCompletionsModel,
    Runner,
    Session,
    set_tracing_disabled,
)
from openai import AsyncOpenAI
from openai.types.responses import ResponseTextDeltaEvent

from .storage import InMemoryStore, StorageProvider
from ..tools.tools_registry import get_system_tools, get_web_tools
from ..prompts.base import load_agent_instructions

set_tracing_disabled(True)

class OrbitClient:

    def __init__(
        self,
        base_url: str,
        api_key: str,
        memory: StorageProvider | None = None,
    ) -> None:

        self.memory = memory or InMemoryStore()

        self.client = AsyncOpenAI(
            api_key=api_key,
            base_url=base_url
        )

    async def get_models(self):
        models_page = await self.client.models.list()
        return [model.id for model in models_page.data]

    def create_agent(self, model):

        chat_model = OpenAIChatCompletionsModel(
            openai_client=self.client,
            model=model
        )

        return Agent(
            "Orbit",
            model=chat_model,
            instructions=load_agent_instructions(),
            tools=[*get_system_tools(), *get_web_tools()]
        )

    async def chat(
        self,
        model: str,
        message: str,
        session_id: str = "default",
        user_id: str = "local",
    ):

        session = self.memory.get_session(session_id=session_id, user_id=user_id)

        result = Runner.run_streamed(
            starting_agent=self.create_agent(model),
            input=message,
            session=session,
            max_turns=None,
        )

        async for event in result.stream_events():

            if (
                event.type == "raw_response_event"
                and isinstance(event.data, ResponseTextDeltaEvent)
            ):
                print(event.data.delta, end="", flush=True)

        return result.final_output[0]


