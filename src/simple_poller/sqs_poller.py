from asyncio import as_completed
from logging import error, info
from os import getenv
from typing import Any, Awaitable, Callable, override

import boto3

from .base_poller import BasePoller

STAGE: str = getenv("STAGE", "dev")


class SqsPoller(BasePoller):
    def __init__(
        self,
        queue_url: str,
        handler: Callable[..., Awaitable[None]],
    ) -> None:
        super().__init__(handler)

        self.__queue_url: str = queue_url

        self.__client = boto3.client(
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

        info(f"Received {len(messages)} message")

        to_be_deleted: list[dict[str, str]] = []

        async def process(message: dict[str, Any]) -> None:
            message_id: str = message["MessageId"]
            info(f"Processing message with ID {message_id}")

            try:
                await self.handler(message)

                to_be_deleted.append({
                    "Id": message_id,
                    "ReceiptHandle": message["ReceiptHandle"],
                })
            except RuntimeError:
                error("Failed to process message with ID {message_id}")

        try:
            for task in as_completed(process(message) for message in messages):
                await task
        finally:
            if to_be_deleted:
                self.__client.delete_message_batch(
                    Entries=to_be_deleted,
                    QueueUrl=self.__queue_url,
                )

                info(f"Deleted {len(to_be_deleted)} message")
