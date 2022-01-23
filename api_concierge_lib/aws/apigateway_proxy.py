# Copyright 2022 Ben Kehoe
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import enum
import json
import functools
from typing import Mapping, Any, Optional

from ..api_concierge_lib import (
    SchemaRequest,
    SchemaResponse,
    InvocationRequest,
    ErrorResponse,
    InvalidStateError,
)

EventType = Mapping[str, Any]


class EventMode(enum.Enum):
    Body = enum.auto()
    Headers = enum.auto()


def is_schema_request(event: EventType, mode: EventMode) -> bool:
    if mode == EventMode.Headers:
        headers = event.get("headers")
        if not isinstance(headers, dict):
            return False
        return SchemaRequest.is_schema_request(headers)
    if not event.get("body"):
        return False
    try:
        payload = json.loads(event["body"])
        if not isinstance(payload, dict):
            return False
        return SchemaRequest.is_schema_request(payload)
    except json.JSONDecodeError:
        return False


def load_schema_request(event: EventType, mode: EventMode) -> Optional[SchemaRequest]:
    if mode == EventMode.Headers:
        try:
            return SchemaRequest.load(event.get("headers", {}))
        except ValueError:
            return None
    if not event.get("body"):
        return None
    try:
        payload = json.loads(event["body"])
        if not isinstance(payload, dict):
            return None
        return SchemaRequest.load(payload)
    except (ValueError, json.JSONDecodeError):
        return None


def schema_response(
    schema: Any,
    mode: EventMode,
    *,
    instructions: Optional[str] = None,
    state: Optional[Any] = None
) -> SchemaResponse:
    response = SchemaResponse(schema=schema, instructions=instructions, state=state)
    if mode == EventMode.Headers:
        return {"statusCode": 200, "headers": response.get_headers(), "body": ""}
    return {"statusCode": 200, "body": json.dumps(response.get_payload())}


def is_invocation_request(
    event: EventType, mode: EventMode, *, state: Any = None
) -> bool:
    if mode == EventMode.Headers:
        headers = event.get("headers")
        if not isinstance(headers, dict):
            return False
        return InvocationRequest.is_invocation_request(headers, state=state)
    try:
        payload = json.loads(event["body"])
        if not isinstance(payload, dict):
            return False
        return InvocationRequest.is_invocation_request(payload, state=state)
    except (ValueError, json.JSONDecodeError):
        return False


def load_invoke_request(
    event: EventType, mode: EventMode
) -> Optional[InvocationRequest]:
    if mode == EventMode.Headers:
        headers = event.get("headers")
        if not isinstance(headers, dict):
            return None
        return InvocationRequest.load_from_headers(headers, payload=event.get("body"))
    try:
        payload = json.loads(event["body"])
        if not isinstance(payload, dict):
            return None
        return InvocationRequest.load_from_payload(event)
    except (ValueError, json.JSONDecodeError):
        return None


def error_response(
    error_message: str,
    mode: EventMode,
    *,
    schema: Optional[Any] = None,
    state: Optional[Any] = None
) -> ErrorResponse:
    response = ErrorResponse(error_message=error_message, schema=schema, state=state)
    if mode == EventMode.Headers:
        return {"statusCode": 400, "headers": response.get_headers(), "body": ""}
    else:
        return {"statusCode": 400, "body": json.dumps(response.get_payload())}


def api_concierge_handler(
    schema: Any, mode: EventMode, *, instructions: Optional[str] = None
):
    def decorator(f):
        @functools.wraps(f)
        def handler(event, *args, **kwargs):
            if is_schema_request(event, mode):
                response = SchemaResponse(schema, instructions=instructions)
                if mode == EventMode.Headers:
                    return {
                        "statusCode": 200,
                        "headers": response.get_headers(),
                        "body": "",
                    }
                return {"statusCode": 200, "body": json.dumps(response.get_payload())}
            return f(event, *args, **kwargs)

        return handler

    return decorator
