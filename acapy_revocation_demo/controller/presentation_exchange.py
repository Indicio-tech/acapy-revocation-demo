"""Interface for interacting with an agent."""
import json
import logging
from typing import (
    TYPE_CHECKING,
    List,
)

from acapy_client.api.present_proof_v1_0 import (
    get_present_proof_records_pres_ex_id_credentials as _fetch_relevant_credentials,
    post_present_proof_records_pres_ex_id_problem_report as _pres_ex_problem_report,
    post_present_proof_records_pres_ex_id_send_presentation as _send_presentation,
    post_present_proof_records_pres_ex_id_verify_presentation as _verify_presentation,
)
from acapy_client.client import Client
from acapy_client.models.indy_cred_info import IndyCredInfo
from acapy_client.models.indy_cred_precis import IndyCredPrecis
from acapy_client.models.indy_non_revocation_interval import IndyNonRevocationInterval
from acapy_client.models.indy_pres_spec import IndyPresSpec
from acapy_client.models.v10_presentation_exchange import V10PresentationExchange
from acapy_client.models.v10_presentation_problem_report_request import (
    V10PresentationProblemReportRequest,
)
from acapy_client.types import Response, UNSET
from httpx import AsyncClient

from .api import Api
from .record import Record
from .utils import unwrap, unwrap_or

if TYPE_CHECKING:
    from .controller import Controller, Event


LOGGER = logging.getLogger(__name__)


class PresentationExchange(Record[V10PresentationExchange]):
    topic = "present_proof"

    def __init__(
        self,
        controller: "Controller",
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

    def _state_condition(self, event: "Event") -> bool:
        return (
            event.payload["connection_id"] == self.connection_id
            and event.payload["presentation_exchange_id"]
            == self.presentation_exchange_id
        )

    def summary(self) -> str:
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
