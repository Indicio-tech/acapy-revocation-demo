"""Interface for interacting with an agent."""
import asyncio
from contextlib import asynccontextmanager, suppress
import json
import logging
from typing import List, NamedTuple, Optional, Tuple, Union

from acapy_client.api.connection import (
    create_invitation as _create_invitation,
    get_connection as _get_connection,
    get_connections as _get_connections,
    receive_invitation as _receive_invitation,
)
from acapy_client.api.credential_definition import publish_cred_def as _publish_cred_def
from acapy_client.api.issue_credential_v1_0 import (
    get_issue_credential_records as _get_cred_ex_records,
    get_issue_credential_records_cred_ex_id as _get_cred_ex_record,
)
from acapy_client.api.ledger import accept_taa as _accept_taa, fetch_taa as _fetch_taa
from acapy_client.api.out_of_band import (
    post_out_of_band_create_invitation as _create_oob_invitation,
    post_out_of_band_receive_invitation as _receive_oob_invitation,
)
from acapy_client.api.present_proof_v1_0 import (
    get_present_proof_records as _get_pres_ex_records,
    get_present_proof_records_pres_ex_id as _get_pres_ex_record,
)
from acapy_client.api.revocation import publish_revocations as _publish_revocations
from acapy_client.api.schema import publish_schema as _publish_schema
from acapy_client.api.server import get_status_config
from acapy_client.api.wallet import (
    create_did as _create_did,
    get_wallet_did_public as _get_public_did,
    set_public_did as _set_public_did,
)
from acapy_client.client import Client
from acapy_client.models.connection_invitation import ConnectionInvitation
from acapy_client.models.connection_list import ConnectionList
from acapy_client.models.create_invitation_request import CreateInvitationRequest
from acapy_client.models.create_invitation_request_metadata import (
    CreateInvitationRequestMetadata,
)
from acapy_client.models.credential_definition_send_request import (
    CredentialDefinitionSendRequest,
)
from acapy_client.models.credential_definition_send_result import (
    CredentialDefinitionSendResult,
)
from acapy_client.models.did import DID
from acapy_client.models.did_create import DIDCreate
from acapy_client.models.did_result import DIDResult
from acapy_client.models.invitation_create_request import InvitationCreateRequest
from acapy_client.models.invitation_create_request_metadata import (
    InvitationCreateRequestMetadata,
)
from acapy_client.models.invitation_message import InvitationMessage
from acapy_client.models.invitation_result import InvitationResult
from acapy_client.models.publish_revocations import PublishRevocations
from acapy_client.models.receive_invitation_request import ReceiveInvitationRequest
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
from acapy_client.types import Response, UNSET, Unset
from aiohttp import ClientSession
import aiohttp
from aiohttp.http_websocket import WSMsgType
from httpx import AsyncClient

from .api import Api
from .connection import Connection
from .credential_exchange import CredentialExchange
from .invitation import Invitation
from .onboarding import get_onboarder
from .presentation_exchange import PresentationExchange
from .queue import Queue
from .utils import unwrap, unwrap_or


LOGGER = logging.getLogger(__name__)


class ControllerError(Exception):
    """Raised on error in controller."""


class Event(NamedTuple):
    topic: str
    payload: dict

    def __str__(self) -> str:
        payload = json.dumps(self.payload, sort_keys=True, indent=2)
        if len(payload) > 1000:
            payload = json.dumps(self.payload, sort_keys=True)
        return f'Event(topic="{self.topic}", payload={payload})'


class Controller:
    """Interface for interacting with an agent."""

    def __init__(
        self,
        name: str,
        base_url: str,
        *,
        headers: Optional[dict] = None,
        timeout: float = 5.0,
        long_timeout: float = 15.0,
    ):
        self.name = name
        self.client = Client(
            base_url=base_url, headers=headers or {}, timeout=timeout, verify_ssl=True
        )

        self.long_timeout = long_timeout
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

    async def get_connection(self, connection_id: str) -> Connection:
        get_connection = Api(
            self.name, _get_connection._get_kwargs, _get_connection.asyncio_detailed
        )
        record = await get_connection(client=self.client, conn_id=connection_id)
        return Connection(self, unwrap(record.connection_id), record)

    async def receive_invitation(
        self,
        invite: Union[InvitationResult, ConnectionInvitation],
        *,
        auto_accept: bool = False,
        alias: Optional[str] = None,
    ) -> Connection:
        receive_invitation = Api(
            self.name,
            _receive_invitation._get_kwargs,
            _receive_invitation.asyncio_detailed,
        )
        connection_invitation = (
            unwrap(invite.invitation).to_dict()
            if isinstance(invite, InvitationResult)
            else invite.to_dict()
        )
        record = await receive_invitation(
            client=self.client,
            json_body=ReceiveInvitationRequest.from_dict(connection_invitation),
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
    ) -> Tuple[Connection, InvitationResult]:
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
            invitation_result,
        )

    async def receive_oob_invitation(
        self,
        invite: InvitationMessage,
        *,
        auto_accept: Optional[bool] = None,
        alias: Optional[str] = None,
    ) -> Connection:
        receive_invitation = Api(
            self.name,
            _receive_oob_invitation._get_kwargs,
            _receive_oob_invitation.asyncio_detailed,
        )
        record = await receive_invitation(
            client=self.client,
            json_body=InvitationMessage.from_dict(invite.to_dict()),
            auto_accept=auto_accept,
            alias=alias,
        )
        return Connection(self, unwrap(record.connection_id), record)

    async def create_oob_invitation(
        self,
        *,
        auto_accept: Optional[bool] = None,
        alias: Optional[str] = None,
        metadata: Optional[dict] = None,
        use_public_did: Optional[bool] = None,
        my_label: Optional[str] = None,
        multi_use: Optional[bool] = None,
    ) -> Invitation:
        create_invitation = Api(
            self.name,
            _create_oob_invitation._get_kwargs,
            _create_oob_invitation.asyncio_detailed,
        )
        invitation_result = await create_invitation(
            client=self.client,
            json_body=InvitationCreateRequest(
                alias=alias if alias is not None else UNSET,
                metadata=InvitationCreateRequestMetadata.from_dict(metadata or {}),
                handshake_protocols=[
                    "did:sov:BzCbsNYhMrjHiqZDTUASHg;spec/didexchange/1.0",
                    "did:sov:BzCbsNYhMrjHiqZDTUASHg;spec/connections/1.0",
                ],
                use_public_did=use_public_did if use_public_did is not None else UNSET,
                my_label=my_label if my_label is not None else UNSET,
            ),
            auto_accept=auto_accept if auto_accept is not None else UNSET,
            multi_use=multi_use if multi_use is not None else UNSET,
        )
        return Invitation(
            self,
            unwrap(invitation_result.invi_msg_id),
            invitation_result,
        )

    async def publish_schema(
        self, schema_name: str, schema_version: str, attributes: List[str]
    ) -> str:
        publish_schema = Api(
            self.name, _publish_schema._get_kwargs, _publish_schema.asyncio_detailed
        )
        result = await publish_schema(
            client=self.client,
            json_body=SchemaSendRequest(
                schema_name=schema_name,
                schema_version=schema_version,
                attributes=attributes,
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
            client=self.client.with_timeout(self.long_timeout),
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

    async def get_cred_ex_records(self) -> List[CredentialExchange]:
        get_cred_ex_records = Api(
            self.name,
            _get_cred_ex_records._get_kwargs,
            _get_cred_ex_records.asyncio_detailed,
        )
        result = await get_cred_ex_records(client=self.client)
        return [
            CredentialExchange(
                self,
                unwrap(record.connection_id),
                unwrap(record.credential_exchange_id),
                record,
            )
            for record in unwrap_or(result.results) or []
        ]

    async def get_cred_ex_record(self, cred_ex_id: str) -> CredentialExchange:
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

    async def get_pres_ex_records(self) -> List[PresentationExchange]:
        get_pres_ex_records = Api(
            self.name,
            _get_pres_ex_records._get_kwargs,
            _get_pres_ex_records.asyncio_detailed,
        )
        result = await get_pres_ex_records(client=self.client)
        return [
            PresentationExchange(
                self,
                unwrap(record.connection_id),
                unwrap(record.presentation_exchange_id),
                record,
            )
            for record in unwrap_or(result.results) or []
        ]

    async def get_pres_ex_record(self, pres_ex_id: str) -> PresentationExchange:
        get_pres_ex_record = Api(
            self.name,
            _get_pres_ex_record._get_kwargs,
            _get_pres_ex_record.asyncio_detailed,
        )
        result = await get_pres_ex_record(pres_ex_id, client=self.client)
        return PresentationExchange(
            self,
            unwrap(result.connection_id),
            unwrap(result.presentation_exchange_id),
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
