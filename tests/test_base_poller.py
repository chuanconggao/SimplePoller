from typing import override
from uuid import uuid4

import pytest

from simple_poller.base_poller import BasePoller


class TestPoller(BasePoller):
    @override
    async def poll(self) -> None:
        await self.handler(str(uuid4()))


@pytest.mark.asyncio
async def test_BasePoller_poll() -> None:  # noqa: N802
    async def test(x: str) -> None:
        print(x)

    poller = TestPoller(test)

    await poller.poll()


@pytest.mark.asyncio
async def test_BasePoller_poll_until() -> None:  # noqa: N802
    c: list[str] = []

    async def test(x: str) -> None:
        c.append(x)

    poller = TestPoller(test)

    async def cond() -> bool:
        return len(c) < 3

    await poller.poll_until(cond=cond)
