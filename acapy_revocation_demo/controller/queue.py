import asyncio
from typing import Any, Callable, Generic, List, Optional, Sequence, TypeVar


QueueEntry = TypeVar("QueueEntry")


class Queue(Generic[QueueEntry]):
    def __init__(
        self,
        *,
        condition: Optional[Callable[[QueueEntry], bool]] = None,
    ):
        self._queue: List[Any] = []
        self._cond: asyncio.Condition = asyncio.Condition()
        self.condition = condition

    def _first_matching_index(self, condition: Callable[[QueueEntry], bool]):
        for index, entry in enumerate(self._queue):
            if condition(entry):
                return index
        return None

    async def _get(
        self, condition: Optional[Callable[[QueueEntry], bool]] = None
    ) -> QueueEntry:
        """Retrieve a message from the queue."""
        while True:
            async with self._cond:
                # Lock acquired
                if not self._queue:
                    # No items on queue yet so we need to wait for items to show up
                    await self._cond.wait()

                if not self._queue:
                    # Another task grabbed the value before we got to it
                    continue

                if not condition:
                    # Just get the first message
                    return self._queue.pop()

                # Return first matching item, if present
                match_idx = self._first_matching_index(condition)
                if match_idx is not None:
                    return self._queue.pop(match_idx)
                else:
                    # Queue is not empty but no matching elements
                    # We need to wait for more before checking again
                    # Otherwise, this becomes a busy loop
                    await self._cond.wait()

    async def get(
        self,
        condition: Optional[Callable[[QueueEntry], bool]] = None,
        *,
        timeout: int = 5,
    ) -> QueueEntry:
        """Retrieve a message from the queue."""
        try:
            return await asyncio.wait_for(self._get(condition), timeout)
        except asyncio.TimeoutError:
            raise asyncio.TimeoutError("Retrieval from queue timed out") from None

    def get_all(
        self, condition: Optional[Callable[[QueueEntry], bool]] = None
    ) -> Sequence[QueueEntry]:
        """Return all messages matching a given condition."""
        messages = []
        if not self._queue:
            return messages

        if not condition:
            messages = [entry for entry in self._queue]
            self._queue.clear()
            return messages

        # Store messages that didn't match in the order they are seen
        filtered: List[QueueEntry] = []
        for entry in self._queue:
            if condition(entry):
                messages.append(entry)
            else:
                filtered.append(entry)

        # Queue contents set to messages that didn't match condition
        self._queue[:] = filtered
        return messages

    def get_nowait(
        self, condition: Optional[Callable[[QueueEntry], bool]] = None
    ) -> Optional[QueueEntry]:
        """Return a message from the queue without waiting."""
        if not self._queue:
            return None

        if not condition:
            return self._queue.pop()

        match_idx = self._first_matching_index(condition)
        if match_idx is not None:
            return self._queue.pop(match_idx)

        return None

    async def put(self, value: QueueEntry):
        """Push a message onto the queue and notify waiting tasks."""
        if not self.condition or self.condition(value):
            async with self._cond:
                self._queue.append(value)
                self._cond.notify_all()

    def flush(self) -> Sequence[QueueEntry]:
        """Clear queue and return final contents of queue at time of clear."""
        final = self._queue.copy()
        self._queue.clear()
        return final
