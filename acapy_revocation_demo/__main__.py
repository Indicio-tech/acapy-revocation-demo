"""Run the demo."""

import asyncio
from contextlib import contextmanager
import os
from os import getenv
import sys
from typing import Optional

from blessings import Terminal

from . import Controller, logging_to_stdout
from .scenarios import connected, random_string


ISSUER = getenv("ISSUER", "http://localhost:3003")
HOLDER = getenv("HOLDER", "http://localhost:3001")
LOG_LEVEL = getenv("LOG_LEVEL", "debug")

term = Terminal()


@contextmanager
def section(title: str):
    if sys.stdout.isatty():
        size = os.get_terminal_size()
        left = "=" * (int(size.columns / 2) - int((len(title) + 1) / 2))
        right = "=" * (size.columns - (len(left) + len(title) + 2))
        print(f"{term.blue}{term.bold}{left} {title} {right}{term.normal}")
    else:
        print(title)
    yield


async def main(
    issuer: Optional[Controller] = None,
    holder: Optional[Controller] = None,
):
    """Run steps."""
    logging_to_stdout()

    issuer = issuer or Controller("issuer", ISSUER, long_timeout=30)
    holder = holder or Controller("holder", HOLDER)

    with section("Establish Connection"):
        issuer_conn, holder_conn = await connected(issuer, holder)

    with section("Prepare for writing to the ledger"):
        await issuer.onboard()

    with section("Prepare credential ledger artifacts"):
        schema_id = await issuer.publish_schema(
            attributes=["firstname", "age"],
            schema_name="revocation_testing",
            schema_version="0.1.0",
        )
        cred_def_id = await issuer.publish_cred_def(
            schema_id, tag=random_string(5), support_revocation=True
        )

    async with issuer.listening(), holder.listening():
        with section("Issue credential but issuer abandons after offer"):
            issuer_cred_ex = await issuer_conn.send_credential_offer(
                cred_def_id=cred_def_id,
                firstname="Bob",
                age="42",
            )
            holder_cred_ex = await holder_conn.receive_cred_ex()
            await issuer_cred_ex.abandon("I don't like you after all")
            # This fails because no "state" attribute is found in payload
            # await holder_cred_ex.wait_for_state("abandoned")
            print(
                (
                    await holder.get_cred_ex_record(
                        holder_cred_ex.credential_exchange_id
                    )
                ).summary()
            )


if __name__ == "__main__":
    asyncio.get_event_loop().run_until_complete(main())
