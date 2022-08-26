import json
import logging
from typing import TYPE_CHECKING
from acapy_client.models.conn_record import ConnRecord
from acapy_client.models.invitation_message import InvitationMessage
from acapy_client.models.connection_invitation import (
    ConnectionInvitation as AcapyConnectionInvitation,
)

from acapy_client.models.invitation_record import InvitationRecord
from acapy_client.models.invitation_result import InvitationResult

from acapy_revocation_demo.controller.utils import unwrap

from .record import Record
from .connection import Connection
from .api import Api
from acapy_client.api.did_exchange import (
    post_didexchange_conn_id_accept_invitation as _accept_oob_invitation,
)

if TYPE_CHECKING:
    from .controller import Controller


LOGGER = logging.getLogger(__name__)


class ConnectionInvitation(Record[InvitationResult]):
    topic = "connections"

    def __init__(
        self,
        controller: "Controller",
        connection_id: str,
        record: InvitationResult,
    ):
        super().__init__(controller, record)
        self.connection_id = connection_id

    @property
    def invitation(self) -> AcapyConnectionInvitation:
        return unwrap(self.record.invitation)

    @property
    def invitation_url(self) -> str:
        return unwrap(self.record.invitation_url)

    async def connection_from_event(self) -> Connection:
        """Get connection from invitation record through event."""
        assert self.controller.event_queue
        LOGGER.info(
            "%s: %s awaiting associated connection...", self.name, type(self).__name__
        )
        event = await self.controller.event_queue.get(
            lambda event: event.topic == self.topic
            and event.payload["connection_id"] == self.connection_id,
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


class OOBInvitation(Record[InvitationRecord]):
    """Class for OOB Invitation Records."""

    topic = "oob_invitation"
    connection_source_topic = "connections"

    def __init__(
        self,
        controller: "Controller",
        invitation_id: str,
        connection_id: str,
        record: InvitationRecord,
    ):
        super().__init__(controller, record)
        self.invitation_id = invitation_id
        self.connection_id = connection_id

    @property
    def name(self) -> str:
        return f"{self.controller.name} OOB ({self.invitation_id})"

    @property
    def invitation(self) -> InvitationMessage:
        return unwrap(self.record.invitation)

    async def done(self):
        await self.wait_for_state("done")
        self.connection_id = unwrap(self.record.connection_id)

    async def reuse_accepted(self):
        await self.wait_for_state("reuse-accepted")

    async def accept_invitation(self) -> Connection:

        accept_oob_invitation = Api(
            self.name,
            _accept_oob_invitation._get_kwargs,
            _accept_oob_invitation.asyncio_detailed,
        )

        result = await accept_oob_invitation(
            client=self.client, conn_id=self.connection_id
        )
        self.record = result
        return Connection(self.controller, self.connection_id, result)

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
