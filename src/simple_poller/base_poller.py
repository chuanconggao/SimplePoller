from abc import ABC, abstractmethod
from typing import Awaitable, Callable, Optional


class BasePoller(ABC):
    def __init__(
        self,
        handler: Callable[..., Awaitable[None]],
    ) -> None:
        self.handler = handler

    @abstractmethod
    async def poll(self) -> None:
        ...

    async def poll_until(
        self,
        cond: Optional[Callable[[], Awaitable[bool]]] = None,
    ) -> None:
        while cond is None or await cond():
            await self.poll()
