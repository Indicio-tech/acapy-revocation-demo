"""Run the demo."""

import asyncio
from contextlib import contextmanager
import os
from os import getenv
import sys

from typing import Optional

from blessings import Terminal

from . import Controller, logging_to_stdout
from .scenarios import exchanged_dids


ISSUER = getenv("ISSUER", "http://localhost:3003")
VERIFIER = getenv("VERIFIER", "http://localhost:3005")
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
    verifier: Optional[Controller] = None,
    holder: Optional[Controller] = None,
):
    """Run steps."""
    logging_to_stdout()

    issuer = issuer or Controller("issuer", ISSUER, long_timeout=30)
    verifier = verifier or Controller("verifier", VERIFIER)
    holder = holder or Controller("holder", HOLDER)

    with section("Prepare for writing to the ledger"):
        await issuer.onboard()

    with section(
        "Section 1: Try Connection Reuse, use public did, single use, auto accept"
    ):

        issuer_conn, holder_conn = await exchanged_dids(
            lhs=issuer, rhs=holder, use_public_did=True, auto_accept=True
        )
        print(holder_conn.__repr__)
        assert holder_conn.record.their_public_did

        # try:
        issuer_conn, holder_conn = await exchanged_dids(
            lhs=issuer,
            rhs=holder,
            use_public_did=True,
            auto_accept=True,
            use_existing_connection=True,
        )
        assert holder_conn.record.their_public_did
        # except:
        # pass

    with section(
        "Section 2: Try Connection Reuse, use public did, multi use, auto accept"
    ):
        try:
            # Fails due to mutual exclusion of multi_use and use_public_did in ACA-Py
            invite = await issuer.create_oob_invitation(
                use_public_did=True, auto_accept=True, multi_use=True
            )
        except:
            invite = None
            print("Expected failure in creating multi-use invite with public DID.")

        if not invite:
            print("Invitation creation failed, unable to attempt connection")
        else:
            issuer_conn, holder_conn = await exchanged_dids(
                lhs=issuer,
                rhs=holder,
                use_public_did=True,
                auto_accept=True,
                invite=invite,
            )
            print(holder_conn.__repr__)
            assert holder_conn.record.their_public_did

    with section(
        "Section 3: Try using same invite twice, use public did, single use, auto accept."
    ):
        invite = await issuer.create_oob_invitation(
            use_public_did=True,
            auto_accept=True,
        )
        issuer_conn, holder_conn = await exchanged_dids(
            lhs=issuer, rhs=holder, use_public_did=True, auto_accept=True, invite=invite
        )
        print(holder_conn.__repr__)
        assert holder_conn.record.their_public_did

        try:
            issuer_conn, holder_conn = await exchanged_dids(
                lhs=issuer,
                rhs=holder,
                use_public_did=True,
                auto_accept=True,
                invite=invite,
            )
            assert holder_conn.record.their_public_did
        except:
            print("Expected failure of conn reuse.")


if __name__ == "__main__":
    asyncio.get_event_loop().run_until_complete(main())
