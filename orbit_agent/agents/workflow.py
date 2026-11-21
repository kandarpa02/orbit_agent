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
from .skill_picker import load_skill_tool

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

    def create_agent(self, model:OpenAIChatCompletionsModel):
        return Agent(
            "Orbit",
            model=model,
            instructions=load_agent_instructions(),
            tools=[load_skill_tool, *get_system_tools(), *get_web_tools()],
        )

    async def chat_box(
        self,
        model: str,
        message: str,
        session_id: str = "default",
        user_id: str = "local",
    ):
        session = self.memory.get_session(
            session_id=session_id,
            user_id=user_id
        )

        chat_model = OpenAIChatCompletionsModel(
            openai_client=self.client,
            model=model
        )

        result = Runner.run_streamed(
            starting_agent=self.create_agent(chat_model),
            input=message,
            session=session,
            max_turns=None,
        )
        return result

    async def chat(
        self,
        model: str,
        message: str,
        session_id: str = "default",
        user_id: str = "local",
    ):
        session = self.memory.get_session(
            session_id=session_id,
            user_id=user_id
        )

        chat_model = OpenAIChatCompletionsModel(
            openai_client=self.client,
            model=model
        )

        result = Runner.run_streamed(
            starting_agent=self.create_agent(chat_model),
            input=message,
            session=session,
            max_turns=None,
        )

        async for event in result.stream_events():

            # 1. Raw model response events
            if event.type == "raw_response_event":

                if isinstance(event.data, ResponseTextDeltaEvent):
                    print(event.data.delta, end="", flush=True)

            # 2. Agent transitions
            elif event.type == "agent_updated_stream_event":

                print(
                    f"\n\n[AGENT] Switched to: {event.new_agent.name}\n",
                    flush=True
                )

            # 3. Run item events
            elif event.type == "run_item_stream_event":

                item = event.item
                item_type = item.type

                if item_type == "tool_call_item":
                    print(
                        f"\n[TOOL CALL] {item.raw_item.name}",
                        flush=True
                    )

                    print(
                        f"[TOOL ARGUMENTS] {item.raw_item.arguments}",
                        flush=True
                    )

                elif item_type == "tool_call_output_item":
                    print(
                        f"\n[TOOL OUTPUT] {item.output}",
                        flush=True
                    )

                elif item_type == "handoff_call_item":
                    print(
                        f"\n[HANDOFF] Agent requested handoff",
                        flush=True
                    )

                elif item_type == "handoff_output_item":
                    print(
                        f"\n[HANDOFF COMPLETE]",
                        flush=True
                    )

                elif item_type == "message_output_item":
                    pass

        return result.final_output

