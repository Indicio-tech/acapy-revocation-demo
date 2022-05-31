import json
import logging
from typing import (
    Any,
    Callable,
    Coroutine,
    Dict,
    Generic,
    ParamSpec,
    Protocol,
    TypeVar,
    cast,
)

from acapy_client.types import Response
from urllib.parse import urlparse


LOGGER = logging.getLogger(__name__)


class ApiError(Exception):
    """Raised when error on API call."""


class ResultProtocol(Protocol):
    def to_dict(self) -> dict:
        ...


ApiParams = ParamSpec("ApiParams")
ApiResult = TypeVar("ApiResult", bound=ResultProtocol)


class Api(Generic[ApiParams, ApiResult]):
    def __init__(
        self,
        name: str,
        request_builder: Callable[..., Dict[str, Any]],
        api: Callable[ApiParams, Coroutine[Any, Any, Response[ApiResult]]],
    ):
        self.name = name
        self.request_builder = request_builder
        self.api = api

    async def __call__(
        self, *args: ApiParams.args, **kwargs: ApiParams.kwargs
    ) -> ApiResult:
        request = self.request_builder(*args, **kwargs)
        path = urlparse(request["url"]).path
        method = cast(str, request["method"]).upper()
        body = request.get("json", {})
        LOGGER.info(
            "Request to %s %s %s: %s",
            self.name,
            method,
            path,
            json.dumps(body, sort_keys=True, indent=2),
        )
        result: Response = await self.api(*args, **kwargs)
        if result.status_code == 200:
            LOGGER.info(
                "Response: %s",
                json.dumps(
                    result.parsed.to_dict() if result.parsed else {},
                    indent=2,
                    sort_keys=True,
                ),
            )
        else:
            raise ApiError("Request failed!", result.status_code, result.content)

        assert result.parsed is not None
        return result.parsed
