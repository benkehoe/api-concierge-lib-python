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

from dataclasses import dataclass, field as dataclass_field
from typing import Mapping, Optional, Any, Tuple, Union
import typing
import json
import base64
import re
import sys

__version__ = "0.1.0"


def _get_simple_schema(type):
    if type is str:
        return {"type": "string"}
    if type is bool:
        return {"type": "boolean"}
    if type is int:
        return {"type": "integer"}
    if type is float:
        return {"type": "number"}
    if type is list or type is tuple:
        return {"type": "array"}
    if type is dict:
        return {"type": "object"}
    if sys.version_info[1] < 8:
        raise ValueError(f"Unknown type {type}")
    origin = typing.get_origin(type)
    args = typing.get_args(type)
    if origin is list:
        value = {
            "type": "array",
        }
        if args:
            value["items"] = _get_simple_schema(args[0])
        return value
    if origin is tuple:
        value = {
            "type": "array",
        }
        if args:
            value["items"] = [_get_simple_schema(arg) for arg in args]
        return value
    if origin is dict:
        return {"type": "object", "additionalProperties": _get_simple_schema(args[1])}
    raise ValueError(f"Unknown type {type}")


def simple_schema(
    schema: Mapping,
    *,
    required: Union[bool, list] = True,
    additional_properties: bool = False,
):
    """Input a dict with field names as keys and types as values, get a JSON schema back."""
    properties = {}
    for key, value in schema.items():
        properties[key] = _get_simple_schema(value)
    output = {
        "$schema": "http://json-schema.org/draft-07/schema#",
        "properties": properties,
    }
    if not isinstance(required, bool):
        output["required"] = required
    elif required:
        output["required"] = list(properties.keys())
    if not additional_properties:
        output["additionalProperties"] = False
    return output


FIELD_PREFIX = "x-api-concierge-"
REQUEST_FIELD = FIELD_PREFIX + "request"
RESPONSE_FIELD = FIELD_PREFIX + "response"
SCHEMA_FIELD = FIELD_PREFIX + "schema"
INSTRUCTIONS_FIELD = FIELD_PREFIX + "instructions"
CLIENT_FIELD = FIELD_PREFIX + "client"
ERROR_FIELD = FIELD_PREFIX + "error"
STATE_FIELD = FIELD_PREFIX + "state"
BASE_FIELD = FIELD_PREFIX + "base"
PATH_FIELD = FIELD_PREFIX + "path"


class InvalidRequestError(Exception):
    pass


class InvalidStateError(Exception):
    pass


def _serialize(data: Any) -> str:
    return str(base64.urlsafe_b64encode(json.dumps(data).encode("ascii")), "ascii")


def _serialize_state(state: Any, serialized: bool) -> str:
    if serialized:
        return _serialize(state)
    if not isinstance(state, str):
        raise TypeError("Unserialized state must be str")
    if re.match(r"[^A-Za-z0-9,;-_=]", state):
        raise ValueError("State contains invalid characters, should be serialized")
    return state


def _deserialize_state(state_data: str, serialized: bool) -> Any:
    if not serialized:
        return state_data
    try:
        return json.loads(base64.urlsafe_b64decode(state_data))
    except Exception as e:
        raise InvalidStateError(e)


@dataclass(frozen=True)
class SchemaRequest:
    client: Optional[str] = None

    @classmethod
    def is_schema_request(cls, data: Mapping[str, Any]) -> bool:
        for data_field, data_value in data.items():
            if data_field.lower() == REQUEST_FIELD.lower():
                return data_value == "schema"
        return False

    @classmethod
    def load(cls, data: Mapping[str, Any]) -> "SchemaRequest":
        if not cls.is_schema_request(data):
            raise InvalidRequestError("Input is not a schema request.")
        kwargs = {}
        fields = {CLIENT_FIELD.lower(): "client"}
        for data_field, data_value in data.items():
            if data_field.lower() in fields:
                kwargs[fields[data_field.lower()]] = data_value
                break
        return cls(**kwargs)


@dataclass(frozen=True)
class SchemaResponse:
    schema: Any
    instructions: Optional[str] = None
    state: Optional[Any] = None
    base: Optional[dict] = None
    path: Optional[str] = None

    def __post_init__(self):
        if self.path is not None and self.base is None:
            raise ValueError("Cannot set path without base")

    def get_payload(self, *, serialized_state: bool = True):
        payload = {RESPONSE_FIELD: "schema", SCHEMA_FIELD: self.schema}
        if self.instructions is not None:
            payload[INSTRUCTIONS_FIELD] = self.instructions
        if self.state is not None:
            payload[STATE_FIELD] = _serialize_state(self.state, serialized_state)
        if self.base is not None:
            payload[BASE_FIELD] = self.base
            if self.path is not None:
                payload[PATH_FIELD] = self.path
        return payload

    def get_headers(self, *, serialized_state: bool = True):
        headers = {RESPONSE_FIELD: "schema", SCHEMA_FIELD: _serialize(self.schema)}
        if self.instructions is not None:
            headers[INSTRUCTIONS_FIELD] = self.instructions
        if self.state is not None:
            headers[STATE_FIELD] = _serialize_state(self.state, serialized_state)
        if self.base is not None:
            headers[BASE_FIELD] = _serialize(self.base)
            if self.path is not None:
                headers[PATH_FIELD] = self.path
        return headers


@dataclass(frozen=True)
class InvocationRequest:
    payload: Any
    client: Optional[str] = None
    state: Optional[Any] = None

    @classmethod
    def _identify(cls, data: Mapping[str, Any]) -> Tuple[bool, Any]:
        request = None
        state = None
        for data_field, data_value in data.items():
            if data_field.lower() == REQUEST_FIELD.lower():
                if data_value != "invoke":
                    return False, None
                request = data_value
            elif data_field.lower() == STATE_FIELD.lower():
                state = data_value
        if request is None:
            return False, None
        return True, state

    @classmethod
    def is_invocation_request(
        cls,
        data: Mapping[str, Any],
        *,
        state: Optional[Any] = None,
        serialized_state: bool = True,
    ) -> bool:
        result, data_state = cls._identify(data)
        if not result:
            return False
        if state is None:
            return True
        data_state = _deserialize_state(data_state, serialized_state)
        return state == data_state

    @classmethod
    def load_from_payload(
        cls, data: Mapping[str, Any], *, serialized_state: bool = True
    ) -> "InvocationRequest":
        result, state = cls._identify(data)
        if not result:
            raise InvalidRequestError("Input is not a invocation request.")
        kwargs = {}
        if state is not None:
            kwargs["state"] = _deserialize_state(state, serialized_state)
        payload = {}
        fields = {CLIENT_FIELD.lower(): "client"}
        for data_field, data_value in data.items():
            if not data_field.startswith(FIELD_PREFIX):
                payload[data_field] = data_value
                continue
            if data_field.lower() in fields:
                kwargs[fields[data_field.lower()]] = data_value
                break

        kwargs["payload"] = payload
        return cls(**kwargs)

    @classmethod
    def load_from_headers(
        cls, headers: Mapping[str, Any], payload: Any, *, serialized_state: bool = False
    ) -> "InvocationRequest":
        result, state = cls._identify(headers)
        if not result:
            raise InvalidRequestError("Input is not a invocation request.")
        kwargs = {}
        if state is not None:
            kwargs["state"] = _deserialize_state(state, serialized_state)
        fields = {CLIENT_FIELD.lower(): "client"}
        for data_field, data_value in headers.items():
            if data_field.lower() in fields:
                kwargs[fields[data_field.lower()]] = data_value
                break
        kwargs["payload"] = payload
        return cls(**kwargs)


@dataclass(frozen=True)
class ErrorResponse:
    error_message: str
    schema: Optional[Any] = None
    state: Optional[Any] = None
    base: Optional[dict] = None
    path: Optional[str] = None

    def __post_init__(self):
        if self.path is not None and self.base is None:
            raise ValueError("Cannot set path without base")

    def get_payload(self, *, serialized_state: bool = True):
        payload = {RESPONSE_FIELD: "error", ERROR_FIELD: self.error_message}
        if self.schema:
            payload[SCHEMA_FIELD] = self.schema
        if self.state is not None:
            payload[STATE_FIELD] = _serialize_state(self.state, serialized_state)
        if self.base is not None:
            payload[BASE_FIELD] = self.base
            if self.path is not None:
                payload[PATH_FIELD] = self.path
        return payload

    def get_headers(self, *, serialized_state: bool = True):
        headers = {RESPONSE_FIELD: "error", ERROR_FIELD: self.error_message}
        if self.schema:
            headers[SCHEMA_FIELD] = _serialize(self.schema)
        if self.state is not None:
            headers[STATE_FIELD] = _serialize_state(self.state, serialized_state)
        if self.base is not None:
            headers[BASE_FIELD] = _serialize(self.base)
            if self.path is not None:
                headers[PATH_FIELD] = self.path
        return headers
