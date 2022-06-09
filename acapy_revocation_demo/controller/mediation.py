"""Interface for mediation."""

from typing import TYPE_CHECKING
from .record import Record

from acapy_client.api.mediation import (
    put_mediation_mediation_id_default_mediator as _set_default_mediator,
)
from acapy_client.models.mediation_record import MediationRecord

from .api import Api

if TYPE_CHECKING:
    from .controller import Controller, Event


class Mediation(Record[MediationRecord]):
    topic = "mediation"

    def __init__(
        self,
        controller: "Controller",
        connection_id: str,
        mediation_id: str,
        record: MediationRecord,
    ):
        super().__init__(controller, record)
        self.connection_id = connection_id
        self.mediation_id = mediation_id

    @property
    def name(self) -> str:
        return f"{self.controller.name} Mediation {self.mediation_id}"

    def _state_condition(self, event: "Event") -> bool:
        return (
            event.payload["connection_id"] == self.connection_id
            and event.payload["mediation_id"] == self.mediation_id
        )

    async def set_default(self):
        set_default_mediator = Api(
            self.name,
            _set_default_mediator._get_kwargs,
            _set_default_mediator.asyncio_detailed,
        )
        await set_default_mediator(self.mediation_id, client=self.client)

    async def granted(self):
        await self.wait_for_state("granted")
