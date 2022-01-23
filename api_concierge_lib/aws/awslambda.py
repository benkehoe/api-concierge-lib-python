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

"""
@api_concierge_handler(SCHEMA)
def handler(event, context):
    pass

def handler(event, context):
    if SchemaRequest.is_schema_request(event):
        return SchemaResponse(schema, state).get_payload()
    invoke_request = InvocationRequest.from_payload(event)

    return ErrorResponse(msg, schema, state).get_payload()

"""
import functools
from typing import Any, Optional

from ..api_concierge_lib import SchemaRequest, SchemaResponse, InvocationRequest


def api_concierge_handler(schema: Any, *, instructions: Optional[str] = None):
    def decorator(f):
        @functools.wraps(f)
        def handler(event, context, *args, **kwargs):
            if SchemaRequest.is_schema_request(event):
                response = SchemaResponse(schema, instructions=instructions)
                return response.get_payload()
            if InvocationRequest.is_invocation_request(event):
                event = InvocationRequest.load_from_payload(event).payload
            return f(event, context, *args, **kwargs)

        return handler

    return decorator
