from abc import ABC, abstractmethod


class SandboxBackend(ABC):

    @abstractmethod
    async def create(self, config):
        ...

    @abstractmethod
    async def execute(self, session_id, command, timeout):
        ...

    @abstractmethod
    async def read_file(self, session_id, path):
        ...

    @abstractmethod
    async def write_file(self, session_id, path, content):
        ...

    @abstractmethod
    async def list_files(self, session_id, path):
        ...

    @abstractmethod
    async def start_process(self, session_id, command):
        ...

    @abstractmethod
    async def process_status(self, session_id, process_id):
        ...

    @abstractmethod
    async def stop_process(self, session_id, process_id):
        ...

    @abstractmethod
    async def destroy(self, session_id):
        ...

class DockerBackend(SandboxBackend):

    async def create(self, config):
        ...

    async def execute(self, session_id, command, timeout):
        ...

    async def read_file(self, session_id, path):
        ...

    async def write_file(self, session_id, path, content):
        ...

    async def list_files(self, session_id, path):
        ...

    async def start_process(self, session_id, command):
        ...

    async def process_status(self, session_id, process_id):
        ...

    async def stop_process(self, session_id, process_id):
        ...

    async def destroy(self, session_id):
        ...

class Environment:

    def __init__(self, backend, config=None):
        self.backend = backend
        self.config = config or {}
        self.session_id = None

    async def start(self):
        self.session_id = await self.backend.create(
            self.config
        )

    async def execute(self, command, timeout=30):
        return await self.backend.execute(
            self.session_id,
            command,
            timeout
        )

    async def read_file(self, path):
        return await self.backend.read_file(
            self.session_id, path
        )

    async def write_file(self, path, content):
        return await self.backend.write_file(
            self.session_id, path, content
        )

    async def list_files(self, path="."):
        return await self.backend.list_files(
            self.session_id, path
        )

    async def destroy(self):
        if self.session_id:
            await self.backend.destroy(self.session_id)
            self.session_id = None
