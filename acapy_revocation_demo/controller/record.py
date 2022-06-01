"""Interface for interacting with an agent."""
from abc import abstractproperty
import json
import logging
from typing import (
    Callable,
    ClassVar,
    Generic,
    Optional,
    Protocol,
    TYPE_CHECKING,
    Type,
    TypeVar,
)

from acapy_client.client import Client

if TYPE_CHECKING:
    from .controller import Controller, Event

LOGGER = logging.getLogger(__name__)


T = TypeVar("T")


class RecordProtocol(Protocol):
    @classmethod
    def from_dict(cls: Type[T], src_dict: dict) -> T:
        ...


RecordType = TypeVar("RecordType", bound=RecordProtocol)


class Record(Generic[RecordType]):
    """Base class for record like objects."""

    topic: ClassVar[str]

    def __init__(self, controller: "Controller", record: RecordType):
        self.controller = controller
        self.record = record

    @property
    def client(self) -> Client:
        return self.controller.client

    @abstractproperty
    def name(self) -> str:
        """Return name of object."""
        ...

    def _state_condition(self, event: "Event") -> bool:
        """Condition for matching states to this record."""
        return True

    def listening(self):
        return self.controller.listening()

    async def wait_for_state(
        self,
        state: str,
        *,
        condition: Optional[Callable[["Event"], bool]] = None,
        state_attribute: Optional[str] = None,
    ) -> "Event":
        """Wait for a given record state."""
        assert self.controller.event_queue
        LOGGER.info(
            "%s: %s awaiting state %s...", self.name, type(self).__name__, state
        )
        event = await self.controller.event_queue.get(
            lambda event: event.topic == self.topic
            and event.payload[state_attribute or "state"] == state
            and self._state_condition(event)
            and (condition(event) if condition else True),
            timeout=3,
        )
        LOGGER.info("%s: %s reached state %s", self.name, type(self).__name__, state)
        LOGGER.debug(
            "%s record state: %s",
            type(self).__name__,
            json.dumps(event.payload, sort_keys=True),
        )
        self.record = type(self.record).from_dict(event.payload)
        return event
