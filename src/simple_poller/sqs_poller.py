import json
import logging
from asyncio import as_completed, sleep
from collections.abc import Awaitable, Callable
from typing import Any, override

from botocore.client import BaseClient
from box import Box
from extratools_cloud.aws.helpers import get_client
from extratools_core.str import decode

from .base_poller import BasePoller

logger = logging.getLogger(__name__)


class SqsPoller(BasePoller):
    def __init__(
        self,
        queue_url: str,
        handler: Callable[..., Awaitable[None]],
        *,
        client: BaseClient | None = None,
        raw_message: bool = True,
        batch_size: int = 10,
        idle_duration: float = 0,
    ) -> None:
        super().__init__(handler)

        self.__client: BaseClient = client or get_client("sqs")

        self.__queue_url: str = (
            queue_url if queue_url.startswith(("https://", "http://"))
            else self.__client.get_queue_url(
                QueueName=queue_url,
            )["QueueUrl"]

        )
        self.__fifo: bool = queue_url.endswith(".fifo")

        self.__raw_message = raw_message

        if batch_size < 1 or batch_size > 10:
            msg = "batch_size must be between 1 and 10"
            raise ValueError(msg)
        self.__batch_size = batch_size

        if idle_duration < 0:
            msg = "idle_duration must be non-negative"
            raise ValueError(msg)
        self.__idle_duration = idle_duration

    @override
    async def poll(self) -> None:
        # Sleep first to make sure it is satisfied even on the first poll
        await sleep(self.__idle_duration)

        messages: list[dict[str, Any]] = self.__client.receive_message(
            MessageAttributeNames=["All"],
            MessageSystemAttributeNames=["All"],
            # Maximum allowed number
            MaxNumberOfMessages=self.__batch_size,
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
                await self.handler(
                    # Use `Box` to provide object-like attribute access (like `message.Body`)
                    # while still being instance of `dict`
                    Box(message)
                    if self.__raw_message
                    else json.loads(decode(
                        message["Body"],
                        encoding=(
                            message
                            .get("MessageAttributes", {})
                            .get("ContentEncoding", {})
                            .get("StringValue")
                        ),
                    )),
                )

                to_be_deleted.append({
                    "Id": message_id,
                    "ReceiptHandle": message["ReceiptHandle"],
                })
            except RuntimeError:
                logger.exception(f"Failed to process message with ID {message_id}")

        try:
            if self.__fifo:
                for message in messages:
                    await process(message)
            else:
                # TODO: Use `async for` which is only available in Python 3.13+
                for task in as_completed(process(message) for message in messages):
                    await task
        finally:
            if to_be_deleted:
                self.__client.delete_message_batch(
                    Entries=to_be_deleted,
                    QueueUrl=self.__queue_url,
                )

                logger.info(f"Deleted {len(to_be_deleted)} message")
