"""Run tests with the agents."""
from typing import cast
import pytest

from acapy_revocation_demo import Controller
from acapy_revocation_demo.__main__ import main
from acapy_revocation_demo.controller.utils import unwrap


@pytest.mark.asyncio
async def test_main(issuer: Controller, verifier: Controller, holder: Controller):
    """Test the main script."""
    presentations = await main(issuer, verifier, holder)
    for pres in presentations:
        comment = cast(str, unwrap(pres.record.presentation_request_dict).comment)
        if "should verify false" in comment:
            assert str(pres.record.verified) == "false"

        if "should verify true" in comment:
            assert str(pres.record.verified) == "true"
