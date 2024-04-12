from abc import ABC, abstractmethod
from logging import info
import signal
from types import FrameType
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
        exiting: bool = False

        def signal_handler(sig: int, frame: FrameType | None) -> None:
            nonlocal exiting
            exiting = True

        signal.signal(signal.SIGINT, signal_handler)

        while (
            (cond is None or await cond())
            and not exiting
        ):
            info("Polling")

            await self.poll()

        if exiting:
            # Cannot print within `signal_handler`. Otherwise it would cause
            # `RuntimeError: reentrant call inside <_io.BufferedWriter name='<stdout>'>`
            info("Cancelled")
