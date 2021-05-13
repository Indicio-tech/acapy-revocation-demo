from typing import Any, Dict, Optional, Union

import httpx

from ...client import Client
from ...models.revocation_module_response import RevocationModuleResponse
from ...types import UNSET, Response, Unset


def _get_kwargs(
    *,
    client: Client,
    rev_reg_id: str,
    cred_rev_id: int,
    publish: Union[Unset, bool] = UNSET,
) -> Dict[str, Any]:
    url = "{}/issue-credential/revoke".format(client.base_url)

    headers: Dict[str, Any] = client.get_headers()
    cookies: Dict[str, Any] = client.get_cookies()

    params: Dict[str, Any] = {
        "rev_reg_id": rev_reg_id,
        "cred_rev_id": cred_rev_id,
        "publish": publish,
    }
    params = {k: v for k, v in params.items() if v is not UNSET and v is not None}

    return {
        "url": url,
        "headers": headers,
        "cookies": cookies,
        "timeout": client.get_timeout(),
        "params": params,
    }


def _parse_response(*, response: httpx.Response) -> Optional[RevocationModuleResponse]:
    if response.status_code == 200:
        response_200 = RevocationModuleResponse.from_dict(response.json())

        return response_200
    return None


def _build_response(*, response: httpx.Response) -> Response[RevocationModuleResponse]:
    return Response(
        status_code=response.status_code,
        content=response.content,
        headers=response.headers,
        parsed=_parse_response(response=response),
    )


def sync_detailed(
    *,
    client: Client,
    rev_reg_id: str,
    cred_rev_id: int,
    publish: Union[Unset, bool] = UNSET,
) -> Response[RevocationModuleResponse]:
    kwargs = _get_kwargs(
        client=client,
        rev_reg_id=rev_reg_id,
        cred_rev_id=cred_rev_id,
        publish=publish,
    )

    response = httpx.post(
        **kwargs,
    )

    return _build_response(response=response)


def sync(
    *,
    client: Client,
    rev_reg_id: str,
    cred_rev_id: int,
    publish: Union[Unset, bool] = UNSET,
) -> Optional[RevocationModuleResponse]:
    """ """

    return sync_detailed(
        client=client,
        rev_reg_id=rev_reg_id,
        cred_rev_id=cred_rev_id,
        publish=publish,
    ).parsed


async def asyncio_detailed(
    *,
    client: Client,
    rev_reg_id: str,
    cred_rev_id: int,
    publish: Union[Unset, bool] = UNSET,
) -> Response[RevocationModuleResponse]:
    kwargs = _get_kwargs(
        client=client,
        rev_reg_id=rev_reg_id,
        cred_rev_id=cred_rev_id,
        publish=publish,
    )

    async with httpx.AsyncClient() as _client:
        response = await _client.post(**kwargs)

    return _build_response(response=response)


async def asyncio(
    *,
    client: Client,
    rev_reg_id: str,
    cred_rev_id: int,
    publish: Union[Unset, bool] = UNSET,
) -> Optional[RevocationModuleResponse]:
    """ """

    return (
        await asyncio_detailed(
            client=client,
            rev_reg_id=rev_reg_id,
            cred_rev_id=cred_rev_id,
            publish=publish,
        )
    ).parsed
