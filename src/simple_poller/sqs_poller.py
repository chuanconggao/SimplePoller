import logging
from asyncio import as_completed
from collections.abc import Awaitable
from os import getenv
from typing import Any, Callable, override

import boto3

from .base_poller import BasePoller

STAGE: str = getenv("STAGE", "dev")

logger = logging.getLogger(__name__)


class SqsPoller(BasePoller):
    def __init__(
        self,
        queue_url: str,
        handler: Callable[..., Awaitable[None]],
        client: Any = None,
    ) -> None:
        super().__init__(handler)

        self.__queue_url: str = queue_url

        self.__client = client or boto3.client(
            service_name="sqs",
            endpoint_url=(
                "http://localhost:4566" if STAGE == "local"
                else None
            ),
        )

    @override
    async def poll(self) -> None:
        messages: list[dict[str, Any]] = self.__client.receive_message(
            # Maximum allowed number
            MaxNumberOfMessages=10,
            QueueUrl=self.__queue_url,
            # To enable long polling
            WaitTimeSeconds=1,
        ).get("Messages", [])

        logger.info(f"Received {len(messages)} message")

        to_be_deleted: list[dict[str, str]] = []

        async def process(message: dict[str, Any]) -> None:
            message_id: str = message["MessageId"]
            logger.info(f"Processing message with ID {message_id}")

            try:
                await self.handler(message)

                to_be_deleted.append({
                    "Id": message_id,
                    "ReceiptHandle": message["ReceiptHandle"],
                })
            except RuntimeError:
                logger.exception(f"Failed to process message with ID {message_id}")

        try:
            # async for is only available in Python 3.13+
            async for task in as_completed(process(message) for message in messages):
                await task
        finally:
            if to_be_deleted:
                self.__client.delete_message_batch(
                    Entries=to_be_deleted,
                    QueueUrl=self.__queue_url,
                )

                logger.info(f"Deleted {len(to_be_deleted)} message")
