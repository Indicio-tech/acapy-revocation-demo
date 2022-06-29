"""Interface for interacting with an agent."""
import json
import logging
from typing import Any, Dict, List, Optional, TYPE_CHECKING, TypeVar, Union

from acapy_client.api.connection import (
    get_metadata as _get_metadata,
    post_connections_conn_id_accept_invitation as _accept_invitation,
    post_connections_conn_id_accept_request as _accept_request,
    set_metadata as _set_metadata,
)
from acapy_client.api.did_exchange import (
    post_didexchange_conn_id_accept_invitation as _accept_oob_invitation,
    post_didexchange_conn_id_accept_request as _accept_didexchange_request,
)
from acapy_client.api.issue_credential_v1_0 import (
    issue_credential_automated as _issue_credential,
    get_issue_credential_records as _get_cred_ex_records,
    post_issue_credential_send_offer as _send_credential_offer,
)
from acapy_client.api.present_proof_v1_0 import (
    send_proof_request as _send_proof_request,
    get_present_proof_records as _get_pres_ex_records,
)
from acapy_client.api.trustping import (
    post_connections_conn_id_send_ping as _send_trust_ping,
)
from acapy_client.api.basicmessage import send_basicmessage as _send_basicmessage
from acapy_client.models.conn_record import ConnRecord
from acapy_client.models.conn_record_connection_protocol import (
    ConnRecordConnectionProtocol,
)
from acapy_client.models.connection_metadata_set_request import (
    ConnectionMetadataSetRequest,
)
from acapy_client.models.cred_attr_spec import CredAttrSpec
from acapy_client.models.credential_preview import CredentialPreview
from acapy_client.models.indy_proof_request import IndyProofRequest
from acapy_client.models.indy_proof_request_non_revoked import (
    IndyProofRequestNonRevoked,
)
from acapy_client.models.indy_proof_request_requested_attributes import (
    IndyProofRequestRequestedAttributes,
)
from acapy_client.models.indy_proof_request_requested_predicates import (
    IndyProofRequestRequestedPredicates,
)
from acapy_client.models.invitation_result import InvitationResult
from acapy_client.models.ping_request import PingRequest
from acapy_client.models.send_message import SendMessage
from acapy_client.models.v10_credential_exchange import V10CredentialExchange
from acapy_client.models.v10_credential_free_offer_request import (
    V10CredentialFreeOfferRequest,
)
from acapy_client.models.v10_credential_proposal_request_mand import (
    V10CredentialProposalRequestMand,
)
from acapy_client.models.v10_presentation_exchange import V10PresentationExchange
from acapy_client.models.v10_presentation_send_request_request import (
    V10PresentationSendRequestRequest,
)
from acapy_client.types import UNSET

from .api import Api
from .credential_exchange import CredentialExchange
from .presentation_exchange import PresentationExchange
from .record import Record
from .utils import unwrap, unwrap_or

if TYPE_CHECKING:
    from .controller import Controller


LOGGER = logging.getLogger(__name__)


T = TypeVar("T")


class Connection(Record[Union[InvitationResult, ConnRecord]]):
    topic = "connections"

    def __init__(
        self,
        controller: "Controller",
        connection_id: str,
        record: Union[InvitationResult, ConnRecord],
    ):
        super().__init__(controller, record)
        self.connection_id = connection_id

    @property
    def name(self) -> str:
        return f"{self.controller.name} ({self.connection_id})"

    async def wait_for_state(self, state: str):
        await super().wait_for_state(
            state=state,
            state_attribute="rfc23_state",
            condition=lambda event: event.payload["connection_id"]
            == self.connection_id,
        )

    async def invitation_received(self):
        await self.wait_for_state("invitation-received")

    async def request_received(self):
        await self.wait_for_state("request-received")

    async def response_received(self):
        await self.wait_for_state("response-received")

    async def completed(self):
        await self.wait_for_state("completed")

    async def active(self):
        await self.wait_for_state("completed")

    async def accept_invitation(self) -> ConnRecord:
        accept_invitation = Api(
            self.name,
            _accept_invitation._get_kwargs,
            _accept_invitation.asyncio_detailed,
        )
        accept_oob_invitation = Api(
            self.name,
            _accept_oob_invitation._get_kwargs,
            _accept_oob_invitation.asyncio_detailed,
        )

        if (
            self.record.connection_protocol
            is ConnRecordConnectionProtocol.CONNECTIONS1_0
        ):
            handler = accept_invitation
        elif (
            self.record.connection_protocol
            is ConnRecordConnectionProtocol.DIDEXCHANGE1_0
        ):
            handler = accept_oob_invitation
        else:
            raise ValueError(
                f"Unexected connection protocol: {self.record.connection_protocol}"
            )

        result = await handler(client=self.client, conn_id=self.connection_id)
        self.record = result
        return result

    async def accept_request(self) -> ConnRecord:
        accept_request = Api(
            self.name, _accept_request._get_kwargs, _accept_request.asyncio_detailed
        )
        accept_didexchange_request = Api(
            self.name,
            _accept_didexchange_request._get_kwargs,
            _accept_didexchange_request.asyncio_detailed,
        )

        if (
            self.record.connection_protocol
            is ConnRecordConnectionProtocol.CONNECTIONS1_0
        ):
            handler = accept_request
        elif (
            self.record.connection_protocol
            is ConnRecordConnectionProtocol.DIDEXCHANGE1_0
        ):
            handler = accept_didexchange_request
        else:
            raise ValueError(
                f"Unexected connection protocol: {self.record.connection_protocol}"
            )

        result = await handler(client=self.client, conn_id=self.connection_id)
        self.record = result
        return result

    async def get_metadata(self) -> dict:
        get_metadata = Api(
            self.name, _get_metadata._get_kwargs, _get_metadata.asyncio_detailed
        )
        return unwrap(
            (await get_metadata(client=self.client, conn_id=self.connection_id)).results
        ).to_dict()

    async def set_metadata(self, **metadata):
        set_metadata = Api(
            self.name, _set_metadata._get_kwargs, _set_metadata.asyncio_detailed
        )
        await set_metadata(
            self.connection_id,
            client=self.client,
            json_body=ConnectionMetadataSetRequest.from_dict({"metadata": metadata}),
        )

    async def send_trust_ping(self, comment: Optional[str] = None):
        send_trust_ping = Api(
            self.name, _send_trust_ping._get_kwargs, _send_trust_ping.asyncio_detailed
        )
        await send_trust_ping(
            self.connection_id,
            client=self.client,
            json_body=PingRequest(comment=comment),
        )

    async def send_credential_offer(
        self, cred_def_id: str, **attributes
    ) -> "CredentialExchange":
        send_credential_offer = Api(
            self.name,
            _send_credential_offer._get_kwargs,
            _send_credential_offer.asyncio_detailed,
        )
        result = await send_credential_offer(
            client=self.client,
            json_body=V10CredentialFreeOfferRequest(
                connection_id=self.connection_id,
                cred_def_id=cred_def_id,
                credential_preview=CredentialPreview(
                    attributes=[
                        CredAttrSpec(name, value) for name, value in attributes.items()
                    ]
                ),
            ),
        )
        return CredentialExchange(
            self.controller,
            self.connection_id,
            unwrap(result.credential_exchange_id),
            result,
        )

    async def issue_credential_auto(
        self, cred_def_id: str, **attributes
    ) -> "CredentialExchange":
        """Automated credential issuance."""
        issue_credential = Api(
            self.name, _issue_credential._get_kwargs, _issue_credential.asyncio_detailed
        )
        result = await issue_credential(
            client=self.client,
            json_body=V10CredentialProposalRequestMand(
                connection_id=self.connection_id,
                cred_def_id=cred_def_id,
                credential_proposal=CredentialPreview(
                    attributes=[
                        CredAttrSpec(name, value) for name, value in attributes.items()
                    ]
                ),
            ),
        )
        return CredentialExchange(
            self.controller,
            self.connection_id,
            unwrap(result.credential_exchange_id),
            result,
        )

    async def receive_cred_ex(self) -> "CredentialExchange":
        assert self.controller.event_queue
        LOGGER.info("%s: Connection awaiting credential exchange...", self.name)
        event = await self.controller.event_queue.get(
            lambda event: event.topic == CredentialExchange.topic
            and event.payload["connection_id"] == self.connection_id,
            timeout=3,
        )
        LOGGER.debug(
            "CredentialExchange record from event: %s",
            json.dumps(event.payload, sort_keys=True),
        )
        return CredentialExchange(
            self.controller,
            self.connection_id,
            credential_exchange_id=event.payload.get("credential_exchange_id"),
            record=V10CredentialExchange.from_dict(event.payload),
        )

    async def request_presentation(
        self,
        *,
        name: Optional[str] = None,
        version: Optional[str] = None,
        comment: Optional[str] = None,
        requested_attributes: Optional[List[Dict[str, Any]]] = None,
        requested_predicates: Optional[List[Dict[str, Any]]] = None,
        non_revoked: Optional[Dict[str, int]] = None,
    ) -> PresentationExchange:
        """Request a presentation from connection."""
        send_proof_request = Api(
            self.name,
            _send_proof_request._get_kwargs,
            _send_proof_request.asyncio_detailed,
        )
        result = await send_proof_request(
            client=self.client,
            json_body=V10PresentationSendRequestRequest(
                comment=comment or UNSET,
                connection_id=self.connection_id,
                proof_request=IndyProofRequest(
                    name=name or "proof",
                    version=version or "0.1.0",
                    requested_attributes=IndyProofRequestRequestedAttributes.from_dict(
                        {attr["name"]: attr for attr in requested_attributes or []}
                    ),
                    requested_predicates=IndyProofRequestRequestedPredicates.from_dict(
                        {pred["name"]: pred for pred in requested_predicates or []}
                    ),
                    non_revoked=IndyProofRequestNonRevoked.from_dict(non_revoked)
                    if non_revoked
                    else UNSET,
                ),
            ),
        )
        return PresentationExchange(
            self.controller,
            self.connection_id,
            unwrap(result.presentation_exchange_id),
            result,
        )

    async def receive_pres_ex(self) -> PresentationExchange:
        assert self.controller.event_queue
        LOGGER.info("%s: Connection awaiting presentation exchange...", self.name)
        event = await self.controller.event_queue.get(
            lambda event: event.topic == PresentationExchange.topic
            and event.payload["connection_id"] == self.connection_id,
            timeout=3,
        )
        LOGGER.debug(
            "PresentationExchange record from event: %s",
            json.dumps(event.payload, sort_keys=True),
        )
        return PresentationExchange(
            self.controller,
            self.connection_id,
            presentation_exchange_id=event.payload.get("presentation_exchange_id"),
            record=V10PresentationExchange.from_dict(event.payload),
        )

    async def get_cred_ex_records(self) -> List[CredentialExchange]:
        get_cred_ex_records = Api(
            self.name,
            _get_cred_ex_records._get_kwargs,
            _get_cred_ex_records.asyncio_detailed,
        )
        result = await get_cred_ex_records(
            client=self.client, connection_id=self.connection_id
        )
        return [
            CredentialExchange(
                self.controller,
                unwrap(record.connection_id),
                unwrap(record.credential_exchange_id),
                record,
            )
            for record in unwrap_or(result.results) or []
        ]

    async def get_pres_ex_records(self) -> List[PresentationExchange]:
        get_pres_ex_records = Api(
            self.name,
            _get_pres_ex_records._get_kwargs,
            _get_pres_ex_records.asyncio_detailed,
        )
        result = await get_pres_ex_records(
            client=self.client, connection_id=self.connection_id
        )
        return [
            PresentationExchange(
                self.controller,
                unwrap(record.connection_id),
                unwrap(record.presentation_exchange_id),
                record,
            )
            for record in unwrap_or(result.results) or []
        ]

    async def basicmessage(self, content: str):
        send_basicmessage = Api(
            self.name,
            _send_basicmessage._get_kwargs,
            _send_basicmessage.asyncio_detailed,
        )
        await send_basicmessage(
            self.connection_id,
            client=self.client,
            json_body=SendMessage(content=content),
        )
