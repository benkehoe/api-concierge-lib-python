# API Concierge service-side library for Python

These are service-side helpers for creating endpoints that support the [API Concierge protocol](https://github.com/benkehoe/api-concierge-cli/blob/main/docs/protocol.md).

# Usage

```
pip install git+https://github.com/benkehoe/api-concierge-lib-python.git
```

# Example
You can see example Lambda handlers in the API Concierge CLI repo [here](https://github.com/benkehoe/api-concierge-cli/blob/main/example-stack/src/handlers.py).

# Basic API

The basic API is not platform-specific.
It consists of classes representing schema and invocation requests and schema and error responses.

## Simple schema
For a simpler definition of a schema, you can use the `simple_schema()` function.
It creates a JSON schema for an object using Python types.
You pass it a dict with field names as keys, and the Python types `bool`, `int`, `float`, `str`, `dict`, `list` or `tuple`.
If you're using Python 3.8 or newer, you can additionally use the `dict[str, ___]`, `list[___]` and `tuple[__, ___, ...]` syntax.
By default, the schema will prohibit any additional fields; you can change this by setting the `additional_properties` parameter to `True`.

## Schema request
The `SchemaRequest` class represents a schema request.
It has the following fields:
* `client`: The value of the `x-api-concierge-client` field, if it exists.

You can check an incoming request with `SchemaRequest.is_schema_request()`.
You can create a `SchemaRequest` object with `SchemaRequest.load()`; this raises `InvalidRequestError` if it is not a schema request.

## Schema response
The `SchemaResponse` class represents a schema response.
It has the following fields:
* `schema`: The JSON schema.
* `instructions`: Instructions to provide the user.
* `state`: A value that the client will provide back in the invocation request.
* `base`: A JSON object that will be used for the invocation request, with the JSON object created from the schema merged into it.
* `path`: If `base` is provided, `path` can be specified as a JSON Pointer to where the JSON object created from the schema should be inserted.

A `SchemaResponse` can be converted into output with the `get_payload()` and `get_headers()` methods, depending on what kind of output is needed.
Both return a dict; `get_headers()` ensures that all values are strings.
By default, the state is always serialized (JSON-serialized and base64-encoded); this can be controlled with the `serialized_state` parameter.

## Invocation request
The `InvocationRequest` class represents an invocation request.
It has the following fields:
* `payload`: The invocation payload. It does not contain any API Concierge keys.
* `client`: The value of the `x-api-concierge-client` field, if it exists.
* `state`: The state value that was returned to the client previously, if one was given.

You can check an incoming request with `InvocationRequest.is_invocation_request()`.
You can create an `InvocationRequest` object with `InvocationRequest.load_from_payload()` or `InvocationRequest.load_from_headers()`; this raises `InvalidRequestError` if it is not an invocation request.
If you set `serialized_state` to `False` in the schema response or error response, you must set it the same here.

## Error response
The `ErrorResponse` class represents an error response.
It has the following fields:
* `error_message`: The error message to display to the user.
* `schema`: The JSON schema.
* `instructions`: Instructions to provide the user.
* `state`: A value that the client will provide back in the invocation request.
* `base`: A JSON object that will be used for the invocation request, with the JSON object created from the schema merged into it.
* `path`: If `base` is provided, `path` can be specified as a JSON Pointer to where the JSON object created from the schema should be inserted.

An `ErrorResponse` can be converted into output with the `get_payload()` and `get_headers()` methods, depending on what kind of output is needed.
Both return a dict; `get_headers()` ensures that all values are strings.
By default, the state is always serialized (JSON-serialized and base64-encoded); this can be controlled with the `serialized_state` parameter.

# AWS Lambda

There is a decorator to wrap a Lambda handler to provide a schema.

```python
from api_concierge_lib.aws.awslambda import api_concierge_handler

SCHEMA = {
    #...
}

INSTRUCTIONS = "..."

@api_concierge_handler(SCHEMA, instructions=INSTRUCTIONS)
def handler(event, context):
    # ...
```

The event passed the handler will be the invocation request (or a plain invocation that did not use API Concierge).

# AWS API Gateway proxy

For API Gateway proxy events, there's an `EventMode` enum for specifying whether to use the headers or the payload.
Then there are helper functions corresponding to the basic API classes, and a decorator for Lambda handlers, all of which take the `EventMode` as an extra parameter.
