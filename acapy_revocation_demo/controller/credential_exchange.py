"""Interface for interacting with an agent."""
import asyncio
from dataclasses import dataclass
import json
import logging
from typing import TYPE_CHECKING, Optional

from acapy_client.api.issue_credential_v1_0 import (
    post_issue_credential_records_cred_ex_id_problem_report as _cred_ex_problem_report,
    post_issue_credential_records_cred_ex_id_send_request as _issue_cred_send_request,
    post_issue_credential_records_cred_ex_id_store as _issue_cred_store,
    post_issue_credential_records_cred_ex_id_issue as _issue_cred_issue,
)
from acapy_client.api.revocation import revoke_credential as _revoke_credential
from acapy_client.models.revoke_request import RevokeRequest
from acapy_client.models.v10_credential_exchange import V10CredentialExchange
from acapy_client.models.v10_credential_issue_request import V10CredentialIssueRequest
from acapy_client.models.v10_credential_problem_report_request import (
    V10CredentialProblemReportRequest,
)
from acapy_client.models.v10_credential_store_request import V10CredentialStoreRequest
from acapy_client.types import UNSET

from .api import Api
from .record import Record
from .utils import unwrap, unwrap_or

if TYPE_CHECKING:
    from .controller import Controller, Event


LOGGER = logging.getLogger(__name__)


@dataclass
class RevocationNotification:
    pass


class CredentialExchange(Record[V10CredentialExchange]):

    topic = "issue_credential"

    def __init__(
        self,
        controller: "Controller",
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

    def _state_condition(self, event: "Event") -> bool:
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

    async def issue(self):
        issue = Api(
            self.name, _issue_cred_issue._get_kwargs, _issue_cred_issue.asyncio_detailed
        )
        result = await issue(
            self.credential_exchange_id,
            client=self.client,
            json_body=V10CredentialIssueRequest(),
        )
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
        try:
            event = await self.controller.event_queue.get(
                lambda event: event.topic == "revocation-notification"
            )
        except asyncio.TimeoutError:
            LOGGER.error(
                "Waiting for revocation notification timed out! "
                "Is --monitor-revocation-notification enabled on the holder? "
                "Is --notify-revocation enabled on the issuer?"
            )
            raise

        LOGGER.debug("%s: received event: %s", self.name, event)
        return RevocationNotification()
