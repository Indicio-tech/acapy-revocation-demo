"""Interface for interacting with an agent."""
from abc import abstractproperty
import asyncio
from contextlib import asynccontextmanager, suppress
from dataclasses import dataclass
import json
import logging
from typing import (
    Any,
    Callable,
    ClassVar,
    Dict,
    Generic,
    List,
    NamedTuple,
    Optional,
    Protocol,
    Tuple,
    Type,
    TypeVar,
    Union,
)

from acapy_client.api.connection import (
    create_invitation as _create_invitation,
    get_connection as _get_connection,
    get_connections as _get_connections,
    get_metadata as _get_metadata,
    post_connections_conn_id_accept_invitation as _accept_invitation,
    post_connections_conn_id_accept_request as _accept_request,
    receive_invitation as _receive_invitation,
    set_metadata as _set_metadata,
)
from acapy_client.api.credential_definition import publish_cred_def as _publish_cred_def
from acapy_client.api.issue_credential_v1_0 import (
    get_issue_credential_records as _get_cred_ex_records,
    get_issue_credential_records_cred_ex_id as _get_cred_ex_record,
    issue_credential_automated as _issue_credential,
    post_issue_credential_records_cred_ex_id_problem_report as _cred_ex_problem_report,
    post_issue_credential_records_cred_ex_id_send_request as _issue_cred_send_request,
    post_issue_credential_records_cred_ex_id_store as _issue_cred_store,
)
from acapy_client.api.ledger import accept_taa as _accept_taa, fetch_taa as _fetch_taa
from acapy_client.api.present_proof_v1_0 import (
    get_present_proof_records_pres_ex_id_credentials as _fetch_relevant_credentials,
    post_present_proof_records_pres_ex_id_problem_report as _pres_ex_problem_report,
    post_present_proof_records_pres_ex_id_send_presentation as _send_presentation,
    post_present_proof_records_pres_ex_id_verify_presentation as _verify_presentation,
    send_proof_request as _send_proof_request,
)
from acapy_client.api.revocation import (
    publish_revocations as _publish_revocations,
    revoke_credential as _revoke_credential,
)
from acapy_client.api.schema import publish_schema as _publish_schema
from acapy_client.api.server import get_status_config
from acapy_client.api.trustping import (
    post_connections_conn_id_send_ping as _send_trust_ping,
)
from acapy_client.api.wallet import (
    create_did as _create_did,
    get_wallet_did_public as _get_public_did,
    set_public_did as _set_public_did,
)
from acapy_client.client import Client
from acapy_client.models.conn_record import ConnRecord
from acapy_client.models.connection_invitation import ConnectionInvitation
from acapy_client.models.connection_list import ConnectionList
from acapy_client.models.connection_metadata_set_request import (
    ConnectionMetadataSetRequest,
)
from acapy_client.models.create_invitation_request import CreateInvitationRequest
from acapy_client.models.create_invitation_request_metadata import (
    CreateInvitationRequestMetadata,
)
from acapy_client.models.cred_attr_spec import CredAttrSpec
from acapy_client.models.credential_definition_send_request import (
    CredentialDefinitionSendRequest,
)
from acapy_client.models.credential_definition_send_result import (
    CredentialDefinitionSendResult,
)
from acapy_client.models.credential_preview import CredentialPreview
from acapy_client.models.did import DID
from acapy_client.models.did_create import DIDCreate
from acapy_client.models.did_result import DIDResult
from acapy_client.models.indy_cred_info import IndyCredInfo
from acapy_client.models.indy_cred_precis import IndyCredPrecis
from acapy_client.models.indy_non_revocation_interval import IndyNonRevocationInterval
from acapy_client.models.indy_pres_spec import IndyPresSpec
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
from acapy_client.models.publish_revocations import PublishRevocations
from acapy_client.models.receive_invitation_request import ReceiveInvitationRequest
from acapy_client.models.revoke_request import RevokeRequest
from acapy_client.models.schema_send_request import SchemaSendRequest
from acapy_client.models.schema_send_result import SchemaSendResult
from acapy_client.models.taa_accept import TAAAccept
from acapy_client.models.taa_info import TAAInfo
from acapy_client.models.taa_record import TAARecord
from acapy_client.models.taa_result import TAAResult
from acapy_client.models.txn_or_credential_definition_send_result import (
    TxnOrCredentialDefinitionSendResult,
)
from acapy_client.models.txn_or_schema_send_result import TxnOrSchemaSendResult
from acapy_client.models.v10_credential_exchange import V10CredentialExchange
from acapy_client.models.v10_credential_exchange_list_result import (
    V10CredentialExchangeListResult,
)
from acapy_client.models.v10_credential_problem_report_request import (
    V10CredentialProblemReportRequest,
)
from acapy_client.models.v10_credential_proposal_request_mand import (
    V10CredentialProposalRequestMand,
)
from acapy_client.models.v10_credential_store_request import V10CredentialStoreRequest
from acapy_client.models.v10_presentation_exchange import V10PresentationExchange
from acapy_client.models.v10_presentation_problem_report_request import (
    V10PresentationProblemReportRequest,
)
from acapy_client.models.v10_presentation_send_request_request import (
    V10PresentationSendRequestRequest,
)
from acapy_client.types import Response, UNSET, Unset
from aiohttp import ClientSession
import aiohttp
from aiohttp.http_websocket import WSMsgType
from httpx import AsyncClient

from .api import Api
from .onboarding import get_onboarder
from .queue import Queue


LOGGER = logging.getLogger(__name__)


T = TypeVar("T")


def unwrap(value: Union[Unset, T]) -> T:
    """Unwrap a potentially unset value."""
    assert not isinstance(value, Unset)
    return value


def unwrap_or(value: Union[Unset, T], default: Optional[T] = None) -> Optional[T]:
    if not isinstance(value, Unset):
        return value
    return default


class ControllerError(Exception):
    """Raised on error in controller."""


class Event(NamedTuple):
    topic: str
    payload: dict

    def __str__(self) -> str:
        payload = json.dumps(self.payload, sort_keys=True, indent=2)
        return f'Event(topic="{self.topic}", payload={payload})'


class Controller:
    """Interface for interacting with an agent."""

    def __init__(self, name: str, base_url: str, *, headers: Optional[dict] = None):
        self.name = name
        self.client = Client(
            base_url=base_url, headers=headers or {}, timeout=5.0, verify_ssl=True
        )

        self.event_queue: Optional[Queue[Event]] = None
        self._ws_task: Optional[asyncio.Task] = None
        self._ws: Optional[aiohttp.ClientWebSocketResponse] = None

    @asynccontextmanager
    async def listening(self):
        if not self.event_queue:
            self.event_queue = Queue()

        self.event_queue.flush()
        self._ws_task = asyncio.get_event_loop().create_task(self.ws())
        yield

        if self._ws and not self._ws.closed:
            await self._ws.close()
        self._ws = None

        self._ws_task.cancel()
        with suppress(asyncio.CancelledError):
            await self._ws_task
        self._ws_task = None

    async def ws(self):
        assert self.event_queue
        async with ClientSession(self.client.base_url) as session:
            async with session.ws_connect("/ws", timeout=30.0) as ws:
                self._ws = ws
                async for msg in ws:
                    if msg.type == WSMsgType.TEXT:
                        data = msg.json()
                        if data.get("topic") != "ping":
                            try:
                                event = Event(**data)
                                LOGGER.debug("%s: Event received: %s", self.name, event)
                                await self.event_queue.put(event)
                            except Exception:
                                LOGGER.warning(
                                    "Unable to parse event: %s",
                                    json.dumps(data, indent=2),
                                )
                        elif data.get("topic") == "ping":
                            LOGGER.debug("%s: WS Ping received", self.name)
                    if msg.type == WSMsgType.ERROR:
                        break

    def clear_events(self):
        assert self.event_queue
        self.event_queue.flush()

    async def get_connections(self) -> ConnectionList:
        get_connections = Api(
            self.name, _get_connections._get_kwargs, _get_connections.asyncio_detailed
        )
        return await get_connections(client=self.client)

    async def get_connection(self, connection_id: str) -> "Connection":
        get_connection = Api(
            self.name, _get_connection._get_kwargs, _get_connection.asyncio_detailed
        )
        record = await get_connection(client=self.client, conn_id=connection_id)
        return Connection(self, unwrap(record.connection_id), record)

    async def receive_invitation(
        self,
        invite: ConnectionInvitation,
        *,
        auto_accept: bool = False,
        alias: Optional[str] = None,
    ) -> "Connection":
        receive_invitation = Api(
            self.name,
            _receive_invitation._get_kwargs,
            _receive_invitation.asyncio_detailed,
        )
        record = await receive_invitation(
            client=self.client,
            json_body=ReceiveInvitationRequest.from_dict(invite.to_dict()),
            auto_accept=auto_accept,
            alias=alias,
        )
        return Connection(self, unwrap(record.connection_id), record)

    async def create_invitation(
        self,
        *,
        auto_accept: bool = False,
        alias: Optional[str] = None,
        metadata: Optional[dict] = None,
    ) -> Tuple["Connection", ConnectionInvitation]:
        create_invitation = Api(
            self.name,
            _create_invitation._get_kwargs,
            _create_invitation.asyncio_detailed,
        )
        invitation_result = await create_invitation(
            client=self.client,
            json_body=CreateInvitationRequest(
                metadata=CreateInvitationRequestMetadata.from_dict(metadata or {})
            ),
            auto_accept=auto_accept,
            alias=alias,
        )
        return (
            Connection(
                self, unwrap(invitation_result.connection_id), invitation_result
            ),
            unwrap(invitation_result.invitation),
        )

    async def publish_schema(
        self, schema_name: str, schema_version: str, attrs: List[str]
    ) -> str:
        publish_schema = Api(
            self.name, _publish_schema._get_kwargs, _publish_schema.asyncio_detailed
        )
        result = await publish_schema(
            client=self.client,
            json_body=SchemaSendRequest(
                schema_name=schema_name,
                schema_version=schema_version,
                attributes=attrs,
            ),
        )
        if isinstance(result, SchemaSendResult):
            return result.schema_id

        assert isinstance(result, TxnOrSchemaSendResult)
        return unwrap(result.sent).schema_id

    async def publish_cred_def(
        self,
        schema_id: str,
        *,
        tag: Optional[str] = None,
        support_revocation: bool = False,
        revocation_registry_size: Optional[int] = None,
    ) -> str:
        """Publish cred def and return cred def id."""
        publish_cred_def = Api(
            self.name, _publish_cred_def._get_kwargs, _publish_cred_def.asyncio_detailed
        )
        result = await publish_cred_def(
            client=self.client.with_timeout(30.0),
            json_body=CredentialDefinitionSendRequest(
                schema_id=schema_id,
                revocation_registry_size=revocation_registry_size or UNSET,
                support_revocation=support_revocation,
                tag=tag or UNSET,
            ),
        )
        if isinstance(result, CredentialDefinitionSendResult):
            return result.credential_definition_id

        assert isinstance(result, TxnOrCredentialDefinitionSendResult)
        return unwrap(result.sent).credential_definition_id

    async def get_cred_ex_records(self) -> V10CredentialExchangeListResult:
        get_cred_ex_records = Api(
            self.name,
            _get_cred_ex_records._get_kwargs,
            _get_cred_ex_records.asyncio_detailed,
        )
        return await get_cred_ex_records(client=self.client)

    async def get_cred_ex_record(self, cred_ex_id: str) -> "CredentialExchange":
        get_cred_ex_record = Api(
            self.name,
            _get_cred_ex_record._get_kwargs,
            _get_cred_ex_record.asyncio_detailed,
        )
        result = await get_cred_ex_record(cred_ex_id, client=self.client)
        return CredentialExchange(
            self,
            unwrap(result.connection_id),
            unwrap(result.credential_exchange_id),
            result,
        )

    async def publish_revocations(self):
        publish_revocations = Api(
            self.name,
            _publish_revocations._get_kwargs,
            _publish_revocations.asyncio_detailed,
        )
        await publish_revocations(client=self.client, json_body=PublishRevocations())

    async def fetch_taa(self) -> TAAInfo:
        # TODO Fix
        async def _manual_override(*, client: Client):
            async with AsyncClient(base_url=self.client.base_url) as session:
                result = await session.get("/ledger/taa")
                info = result.json().get("result", {})
                return Response(
                    status_code=result.status_code,
                    content=result.content,
                    headers=result.headers,
                    parsed=TAAResult(
                        result=TAAInfo.from_dict(
                            {
                                "aml_record": info.get("aml_record") or UNSET,
                                "taa_record": info.get("taa_record") or UNSET,
                                "taa_accepted": info.get("taa_accepted"),
                                "taa_required": info.get("taa_required"),
                            }
                        )
                    ),
                )

        fetch_taa = Api(self.name, _fetch_taa._get_kwargs, _manual_override)
        return unwrap((await fetch_taa(client=self.client)).result)

    async def accept_taa(self, text: str, version: str):
        accept_taa = Api(
            self.name,
            _accept_taa._get_kwargs,
            _accept_taa.asyncio_detailed,
        )
        await accept_taa(
            client=self.client,
            json_body=TAAAccept(
                mechanism="on_file",
                text=text,
                version=version,
            ),
        )

    async def create_did(self) -> Tuple[str, str]:
        create_did = Api(
            self.name, _create_did._get_kwargs, _create_did.asyncio_detailed
        )
        result = unwrap(
            (await create_did(client=self.client, json_body=DIDCreate())).result
        )
        return unwrap(result.did), unwrap(result.verkey)

    async def get_public_did(self) -> Optional[str]:
        # TODO Fix
        async def _manual_override(*, client: Client):
            async with AsyncClient(base_url=self.client.base_url) as session:
                result = await session.get("/wallet/did/public")
                did = result.json().get("result")
                return Response(
                    status_code=result.status_code,
                    content=result.content,
                    headers=result.headers,
                    parsed=DIDResult(result=DID.from_dict(did) if did else UNSET),
                )

        get_public_did = Api(self.name, _get_public_did._get_kwargs, _manual_override)
        result = await get_public_did(client=self.client)
        if isinstance(result.result, Unset):
            return None

        return unwrap(result.result.did)

    async def get_genesis_url(self) -> Optional[str]:
        config = await get_status_config.asyncio(client=self.client)
        assert config
        config = unwrap(config.config).to_dict()
        return config.get("ledger.genesis_url")

    async def set_public_did(self, did: str):
        set_public_did = Api(
            self.name,
            _set_public_did._get_kwargs,
            _set_public_did.asyncio_detailed,
        )
        await set_public_did(client=self.client, did=did)

    async def onboard(self):
        genesis_url = await self.get_genesis_url()
        if not genesis_url:
            raise ControllerError("No ledger configured on agent")

        taa = await self.fetch_taa()
        if taa.taa_required is True and (
            isinstance(taa.taa_accepted, (Unset)) or taa.taa_accepted is None
        ):
            assert isinstance(taa.taa_record, TAARecord)
            await self.accept_taa(
                unwrap(taa.taa_record.text), unwrap(taa.taa_record.version)
            )

        public_did = await self.get_public_did()
        if not public_did:
            public_did, verkey = await self.create_did()
            onboarder = get_onboarder(genesis_url)
            if not onboarder:
                raise ControllerError(
                    "Unrecognized ledger, cannot automatically onboard"
                )
            await onboarder.onboard(public_did, verkey)
            await self.set_public_did(public_did)


class RecordProtocol(Protocol):
    @classmethod
    def from_dict(cls: Type[T], src_dict: dict) -> T:
        ...


RecordType = TypeVar("RecordType", bound=RecordProtocol)


class Record(Generic[RecordType]):
    """Base class for record like objects."""

    topic: ClassVar[str]

    def __init__(self, controller: Controller, record: RecordType):
        self.controller = controller
        self.record = record

    @property
    def client(self) -> Client:
        return self.controller.client

    @abstractproperty
    def name(self) -> str:
        """Return name of object."""
        ...

    def _state_condition(self, event: Event) -> bool:
        """Condition for matching states to this record."""
        return True

    async def wait_for_state(
        self,
        state: str,
        *,
        condition: Optional[Callable[[Event], bool]] = None,
        state_attribute: Optional[str] = None,
    ) -> Event:
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
            json.dumps(event.payload, sort_keys=True, indent=2),
        )
        self.record = type(self.record).from_dict(event.payload)
        return event


class Connection(Record[Union[InvitationResult, ConnRecord]]):
    topic = "connections"

    def __init__(
        self,
        controller: Controller,
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
        result = await accept_invitation(client=self.client, conn_id=self.connection_id)
        self.record = result
        return result

    async def accept_request(self) -> ConnRecord:
        accept_request = Api(
            self.name, _accept_request._get_kwargs, _accept_request.asyncio_detailed
        )
        result = await accept_request(client=self.client, conn_id=self.connection_id)
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

    async def issue_credential(
        self, cred_def_id: str, **attributes
    ) -> "CredentialExchange":
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
        LOGGER.info(
            "CredentialExchange record from event: %s",
            json.dumps(event.payload, sort_keys=True, indent=2),
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
    ) -> "PresentationExchange":
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

    async def receive_pres_ex(self) -> "PresentationExchange":
        assert self.controller.event_queue
        LOGGER.info("%s: Connection awaiting presentation exchange...", self.name)
        event = await self.controller.event_queue.get(
            lambda event: event.topic == PresentationExchange.topic
            and event.payload["connection_id"] == self.connection_id,
            timeout=3,
        )
        LOGGER.info(
            "PresentationExchange record from event: %s",
            json.dumps(event.payload, sort_keys=True, indent=2),
        )
        return PresentationExchange(
            self.controller,
            self.connection_id,
            presentation_exchange_id=event.payload.get("presentation_exchange_id"),
            record=V10PresentationExchange.from_dict(event.payload),
        )


@dataclass
class RevocationNotification:
    pass


class CredentialExchange(Record[V10CredentialExchange]):

    topic = "issue_credential"

    def __init__(
        self,
        controller: Controller,
        connection_id: str,
        credential_exchange_id: str,
        record: V10CredentialExchange,
    ):
        super().__init__(controller, record)
        self.connection_id = connection_id
        self.credential_exchange_id = credential_exchange_id

    @property
    def name(self) -> str:
        return f"{self.controller.name} Cred Ex ({self.credential_exchange_id})"

    def summary(self) -> str:
        return f"{self.name} Summary: " + json.dumps(
            {
                "connection_id": self.connection_id,
                "credential_exchange_id": self.credential_exchange_id,
                "state": self.record.state,
                "credential_definition_id": self.record.credential_definition_id,
                "attributes": {
                    name: value["raw"]
                    for name, value in unwrap(self.record.raw_credential)
                    .to_dict()["values"]
                    .items()
                }
                if unwrap_or(self.record.raw_credential)
                else {},
            },
            indent=2,
            sort_keys=True,
        )

    def _state_condition(self, event: Event) -> bool:
        return (
            event.payload["connection_id"] == self.connection_id
            and event.payload["credential_exchange_id"] == self.credential_exchange_id
        )

    async def _problem_report(self, description: str):
        problem_report = Api(
            self.name,
            _cred_ex_problem_report._get_kwargs,
            _cred_ex_problem_report.asyncio_detailed,
        )
        await problem_report(
            self.credential_exchange_id,
            client=self.client,
            json_body=V10CredentialProblemReportRequest(description=description),
        )

    async def reject(self, reason: str):
        return await self._problem_report(reason)

    async def abandon(self, reason: str):
        return await self._problem_report(reason)

    async def send_request(self):
        send_request = Api(
            self.name,
            _issue_cred_send_request._get_kwargs,
            _issue_cred_send_request.asyncio_detailed,
        )
        result = await send_request(self.credential_exchange_id, client=self.client)
        self.record = result

    async def store(self):
        store = Api(
            self.name, _issue_cred_store._get_kwargs, _issue_cred_store.asyncio_detailed
        )
        result = await store(
            self.credential_exchange_id,
            client=self.client,
            json_body=V10CredentialStoreRequest(),
        )
        self.record = result

    async def offer_received(self):
        return await self.wait_for_state("offer_received")

    async def request_received(self):
        return await self.wait_for_state("request_received")

    async def credential_received(self):
        return await self.wait_for_state("credential_received")

    async def credential_acked(self):
        return await self.wait_for_state("credential_acked")

    async def revoke(self, *, publish: bool = False, comment: Optional[str] = None):
        revoke_credential = Api(
            self.name,
            _revoke_credential._get_kwargs,
            _revoke_credential.asyncio_detailed,
        )
        await revoke_credential(
            client=self.client,
            json_body=RevokeRequest(
                comment=comment or UNSET,
                connection_id=self.connection_id,
                cred_ex_id=self.credential_exchange_id,
                publish=publish,
            ),
        )

    async def receive_revocation_notification(self) -> RevocationNotification:
        assert self.controller.event_queue
        LOGGER.info("%s awaiting notification of revocation...", self.name)
        event = await self.controller.event_queue.get(
            lambda event: event.topic == "revocation-notification"
        )
        LOGGER.debug("%s: received event: %s", event)
        return RevocationNotification()


class PresentationExchange(Record[V10PresentationExchange]):
    topic = "present_proof"

    def __init__(
        self,
        controller: Controller,
        connection_id: str,
        presentation_exchange_id: str,
        record: V10PresentationExchange,
    ):
        super().__init__(controller, record)
        self.connection_id = connection_id
        self.presentation_exchange_id = presentation_exchange_id
        self.record = record

    @property
    def name(self) -> str:
        return f"{self.controller.name} Pres Ex ({self.presentation_exchange_id})"

    def _state_condition(self, event: Event) -> bool:
        return (
            event.payload["connection_id"] == self.connection_id
            and event.payload["presentation_exchange_id"]
            == self.presentation_exchange_id
        )

    def summary(self):
        comment = unwrap_or(unwrap(self.record.presentation_request_dict).comment, None)
        return f"{self.name} Summary: " + json.dumps(
            {
                "state": self.record.state,
                "verified": unwrap_or(self.record.verified, None),
                "presentation_request": unwrap(
                    self.record.presentation_request
                ).to_dict(),
                "comment": comment,
            },
            sort_keys=True,
            indent=2,
        )

    async def request_received(self):
        """Wait for record to advance to request_received state."""
        return await self.wait_for_state("request_received")

    async def presentation_received(self):
        """Wait for record to advance to presentation_received state."""
        return await self.wait_for_state("presentation_received")

    async def verified(self):
        """Wait for record to advance to verified state."""
        return await self.wait_for_state("verified")

    async def presentation_acked(self):
        """Wait for record to advance to presentation_acked state."""
        return await self.wait_for_state("presentation_acked")

    async def fetch_relevant_credentials(self) -> List[IndyCredPrecis]:
        """Fetch credentials that could be used to fulfill this presentation request."""
        # TODO fix
        async def _manual_override(presentation_exchange_id: str, *, client: Client):
            async with AsyncClient(base_url=self.client.base_url) as session:
                result = await session.get(
                    f"/present-proof/records/{presentation_exchange_id}/credentials"
                )
                creds = result.json()
                return Response(
                    status_code=result.status_code,
                    content=result.content,
                    parsed=[
                        IndyCredPrecis(
                            cred_info=IndyCredInfo.from_dict(value["cred_info"]),
                            interval=IndyNonRevocationInterval.from_dict(
                                value["interval"]
                            )
                            if value.get("interval")
                            else UNSET,
                            presentation_referents=value.get("presentation_referents")
                            or [],
                        )
                        for value in creds
                    ],
                    headers=result.headers,
                )

        fetch_relevant_credentials = Api(
            self.name,
            _fetch_relevant_credentials._get_kwargs,
            _manual_override,
        )
        result = await fetch_relevant_credentials(
            self.presentation_exchange_id,
            client=self.client,
        )
        return result

    async def _problem_report(self, description: str):
        problem_report = Api(
            self.name,
            _pres_ex_problem_report._get_kwargs,
            _pres_ex_problem_report.asyncio_detailed,
        )
        await problem_report(
            self.presentation_exchange_id,
            client=self.client,
            json_body=V10PresentationProblemReportRequest(description=description),
        )

    async def reject(self, reason: str):
        return await self._problem_report(reason)

    async def abandon(self, reason: str):
        return await self._problem_report(reason)

    async def auto_prepare_presentation(
        self, fetched_credentials: List[IndyCredPrecis]
    ) -> IndyPresSpec:
        """Automatically fulfill a presentation.

        Uses the first available cred for each attribute and predicate.
        """
        request = unwrap(self.record.presentation_request)
        requested_attributes = {}
        for pres_referrent in request.requested_attributes.to_dict().keys():
            for cred_precis in fetched_credentials:
                if pres_referrent in unwrap(cred_precis.presentation_referents):
                    requested_attributes[pres_referrent] = {
                        "cred_id": unwrap(unwrap(cred_precis.cred_info).referent),
                        "revealed": True,
                    }
        requested_predicates = {}
        for pres_referrent in request.requested_predicates.to_dict().keys():
            for cred_precis in fetched_credentials:
                if pres_referrent in unwrap(cred_precis.presentation_referents):
                    requested_predicates[pres_referrent] = {
                        "cred_id": unwrap(unwrap(cred_precis.cred_info).referent),
                    }

        return IndyPresSpec.from_dict(
            {
                "requested_attributes": requested_attributes,
                "requested_predicates": requested_predicates,
                "self_attested_attributes": {},
            }
        )

    async def send_presentation(
        self, pres_spec: IndyPresSpec
    ) -> V10PresentationExchange:
        send_presentation = Api(
            self.name,
            _send_presentation._get_kwargs,
            _send_presentation.asyncio_detailed,
        )
        result = await send_presentation(
            self.presentation_exchange_id, client=self.client, json_body=pres_spec
        )
        self.record = result
        return result

    async def verify_presentation(self) -> V10PresentationExchange:
        verify_presentation = Api(
            self.name,
            _verify_presentation._get_kwargs,
            _verify_presentation.asyncio_detailed,
        )
        result = await verify_presentation(
            self.presentation_exchange_id, client=self.client
        )
        self.record = result
        return result
