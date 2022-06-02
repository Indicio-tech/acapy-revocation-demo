import json
import logging
from typing import (
    Any,
    Callable,
    Coroutine,
    Dict,
    Generic,
    List,
    ParamSpec,
    Protocol,
    TypeVar,
    Union,
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
ApiResult = TypeVar("ApiResult", bound=Union[List[ResultProtocol], ResultProtocol])


def _serialize(
    value: Union[List[ResultProtocol], ResultProtocol, None]
) -> Union[Dict, List, None]:
    """Serialize result."""
    if value is None:
        return value
    if isinstance(value, List):
        return [res.to_dict() for res in value]
    return value.to_dict()


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
            serialized = _serialize(result.parsed)
            response_out = json.dumps(serialized, indent=2, sort_keys=True)
            if response_out.count("\n") > 30:
                response_out = json.dumps(serialized, sort_keys=True)
            LOGGER.info("Response: %s", response_out)
        else:
            raise ApiError("Request failed!", result.status_code, result.content)

        assert result.parsed is not None
        return result.parsed
