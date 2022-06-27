import json
import logging
from typing import TYPE_CHECKING
from acapy_client.models.conn_record import ConnRecord
from acapy_client.models.invitation_message import InvitationMessage

from acapy_client.models.invitation_record import InvitationRecord

from acapy_revocation_demo.controller.utils import unwrap

from .record import Record
from .connection import Connection

if TYPE_CHECKING:
    from .controller import Controller


LOGGER = logging.getLogger(__name__)


class Invitation(Record[InvitationRecord]):
    """Class for OOB Invitation Records."""

    topic = "oob_invitation"
    connection_source_topic = "connections"

    def __init__(
        self,
        controller: "Controller",
        invitation_id: str,
        record: InvitationRecord,
    ):
        super().__init__(controller, record)
        self.invitation_id = invitation_id

    @property
    def name(self) -> str:
        return f"{self.controller.name} OOB ({self.invitation_id})"

    @property
    def invitation(self) -> InvitationMessage:
        return unwrap(self.record.invitation)

    async def connection_from_event(self) -> Connection:
        """Get connection from invitation record through event."""
        assert self.controller.event_queue
        LOGGER.info(
            "%s: %s awaiting associated connection...", self.name, type(self).__name__
        )
        event = await self.controller.event_queue.get(
            lambda event: event.topic == self.connection_source_topic
            and event.payload["invitation_msg_id"] == self.invitation_id,
            timeout=3,
        )
        LOGGER.info("%s: %s connection found", self.name, type(self).__name__)
        LOGGER.debug(
            "%s connection record: %s",
            type(self).__name__,
            json.dumps(event.payload, sort_keys=True),
        )
        return Connection(
            self.controller,
            event.payload["connection_id"],
            ConnRecord.from_dict(event.payload),
        )
