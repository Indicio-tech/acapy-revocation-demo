"""A set of scenarios to be executed by the demo scripts."""

import logging
from os import getenv
import sys
import random
import string
import asyncio
from typing import Optional
from colored import attr

from . import Controller, Connection

ISSUER = getenv("ISSUER", "http://host.docker.internal:8021")
VERIFIER = getenv("VERIFIER", "http://host.docker.internal:8031")
HOLDER = getenv("HOLDER", "http://host.docker.internal:8041")
LOG_LEVEL = getenv("LOG_LEVEL", "debug")


def random_string(size):
    """Generate a random string."""
    return "".join(
        random.choice(string.ascii_letters + string.digits) for _ in range(size)
    )


async def connected(lhs: Controller, rhs: Controller):
    """Connect two agents."""
    async with lhs.listening(), rhs.listening():
        lhs_conn, invite = await lhs.create_invitation()
        lhs.clear_events()

        rhs_conn = await rhs.receive_invitation(invite, auto_accept=False)

        await rhs_conn.accept_invitation()
        rhs.clear_events()

        await lhs_conn.request_received()
        await lhs_conn.accept_request()

        await rhs_conn.response_received()
        await rhs_conn.send_trust_ping()

        await lhs_conn.active()
        await rhs_conn.active()

        return lhs_conn, rhs_conn


async def connected_issuer_holder(
    issuer_url: Optional[str] = None, holder_url: Optional[str] = None
):
    """Connect issuer and holder."""
    issuer = Controller("issuer", issuer_url or ISSUER)
    holder = Controller("holder", holder_url or HOLDER)
    return await connected(issuer, holder)


async def connected_verifier_holder(
    verifier_url: Optional[str] = None, holder_url: Optional[str] = None
):
    """Connect verifier and holder."""
    verifier = Controller("verifier", verifier_url or VERIFIER)
    holder = Controller("holder", holder_url or HOLDER)
    return await connected(verifier, holder)


async def prepare_ledger_artifacts(issuer: Controller, *, revocable: bool = False):
    """Prepare ledger artifacts for issuing a credential."""
    await issuer.onboard()
    schema_id = await issuer.publish_schema(
        random_string(8), "0.1", ["attr0", "attr1", "attr2"]
    )
    cred_def_id = await issuer.publish_cred_def(schema_id, support_revocation=revocable)
    return schema_id, cred_def_id


async def issued_credential(
    issuer: Connection, holder: Connection, *, revocable: bool = False
):
    """Issue credential to holder."""

    async with issuer.controller.listening(), holder.controller.listening():
        _, cred_def_id = await prepare_ledger_artifacts(
            issuer.controller, revocable=revocable
        )
        issuer_cred_ex = await issuer.issue_credential(
            cred_def_id,
            attr0="test0",
            attr1="test1",
            attr2="test2",
        )
        holder_cred_ex = await holder.receive_cred_ex()
        assert holder_cred_ex.record.state == "offer_received"
        await holder_cred_ex.send_request()
        await issuer_cred_ex.request_received()
        # Issuer automatically issues
        await holder_cred_ex.credential_received()
        await holder_cred_ex.store()
        await issuer_cred_ex.credential_acked()
        await holder_cred_ex.credential_acked()
        print(issuer_cred_ex.summary())
        print(holder_cred_ex.summary())
        return issuer_cred_ex, holder_cred_ex


async def revoked_credential(issuer: Connection, holder: Connection):
    issuer_cred_ex, holder_cred_ex = await issued_credential(
        issuer, holder, revocable=True
    )

    async with issuer.controller.listening(), holder.controller.listening():
        await issuer_cred_ex.revoke(comment="revoked by demo script", publish=False)
        holder.controller.clear_events()
        await issuer.controller.publish_revocations()
        await holder_cred_ex.receive_revocation_notification()


async def presented_proof(verifier: Connection, holder: Connection):
    """Proof presented to verifier from holder."""
    async with verifier.controller.listening(), holder.controller.listening():
        holder.controller.clear_events()
        verifier.controller.clear_events()
        verifier_pres = await verifier.request_presentation(
            requested_attributes=[{"name": "attr0"}]
        )
        holder_pres = await holder.receive_pres_ex()
        relevant_creds = await holder_pres.fetch_relevant_credentials()
        pres_spec = await holder_pres.auto_prepare_presentation(relevant_creds)
        await holder_pres.send_presentation(pres_spec)

        await verifier_pres.presentation_received()
        await verifier_pres.verify_presentation()
        await verifier_pres.verified()
        await holder_pres.presentation_acked()

        print(holder_pres.summary())
        print(verifier_pres.summary())


class ColorFormatter(logging.Formatter):
    def __init__(self, fmt: str):
        self.default = logging.Formatter(fmt)
        self.formats = {
            logging.DEBUG: logging.Formatter(f'{attr("dim")}{fmt}{attr("reset")}'),
        }

    def format(self, record):
        formatter = self.formats.get(record.levelno, self.default)
        return formatter.format(record)


async def main():
    if sys.stdout.isatty():
        logger = logging.getLogger("acapy_revocation_demo")
        logger.setLevel(LOG_LEVEL.upper())
        ch = logging.StreamHandler()
        ch.setLevel(LOG_LEVEL.upper())
        ch.setFormatter(ColorFormatter("%(message)s"))
        logger.addHandler(ch)
    else:
        logging.basicConfig(
            stream=sys.stdout, level=LOG_LEVEL.upper(), format="%(message)s"
        )

    issuer, holder = await connected_issuer_holder()
    verifier, holder_v = await connected_verifier_holder()
    await issued_credential(issuer, holder)
    await presented_proof(verifier, holder_v)


if __name__ == "__main__":
    asyncio.run(main())
