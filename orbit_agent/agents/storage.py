
from abc import ABC, abstractmethod
from agents import Session
from agents.items import TResponseInputItem


class StorageProvider(ABC):

    @abstractmethod
    def get_session(
        self,
        session_id: str,
        user_id: str,
        workspace_id: str | None = None,
    ) -> Session:
        ...


class InMemorySession:

    def __init__(self, session_id: str):
        self.session_id = session_id
        self.items: list[TResponseInputItem] = []

    async def get_items(self, limit=None):
        if limit is None:
            return list(self.items)

        if limit <= 0:
            return []

        return list(self.items[-limit:])

    async def add_items(self, items):
        self.items.extend(items)

    async def pop_item(self):
        return self.items.pop() if self.items else None

    async def clear_session(self):
        self.items.clear()


class InMemoryStore(StorageProvider):

    def __init__(self):
        self.sessions: dict[tuple, InMemorySession] = {}

    def get_session(
        self,
        session_id: str,
        user_id: str,
        workspace_id: str | None = None,
    ) -> Session:

        key = (user_id, workspace_id, session_id)

        if key not in self.sessions:
            self.sessions[key] = InMemorySession(session_id)

        return self.sessions[key]
