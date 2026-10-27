"""A small JSON Schema checker for docs/04-findings.schema.json, standard library only.

It supports only the schema keywords our contract uses: type, required,
additionalProperties: false, properties, items, enum, const and minimum.
It returns a list of error messages; an empty list means the output is valid.
"""

import json
from pathlib import Path

SCHEMA_PATH = Path(__file__).parent.parent.parent / "docs" / "04-findings.schema.json"

PYTHON_TYPES = {"object": dict, "array": list, "string": str, "integer": int, "boolean": bool}


def load_schema():
    with open(SCHEMA_PATH, encoding="utf-8") as handle:
        return json.load(handle)


def schema_errors(value, schema, where="output"):
    """All the ways `value` breaks `schema`, as readable messages."""
    expected = schema.get("type")
    if expected:
        # In Python True is also an int, so rule booleans out for "integer".
        if not isinstance(value, PYTHON_TYPES[expected]) or (expected == "integer" and isinstance(value, bool)):
            return [where + ": should be " + expected]

    errors = []
    if "const" in schema and value != schema["const"]:
        errors.append(where + ": should be " + repr(schema["const"]))
    if "enum" in schema and value not in schema["enum"]:
        errors.append(where + ": " + repr(value) + " is not one of " + repr(schema["enum"]))
    if "minimum" in schema and value < schema["minimum"]:
        errors.append(where + ": should be at least " + str(schema["minimum"]))

    if expected == "object":
        properties = schema.get("properties", {})
        for name in schema.get("required", []):
            if name not in value:
                errors.append(where + ": missing " + name)
        for name, item in value.items():
            if name in properties:
                errors += schema_errors(item, properties[name], where + "." + name)
            elif schema.get("additionalProperties") is False:
                errors.append(where + ": unexpected field " + name)
    if expected == "array" and "items" in schema:
        for index, item in enumerate(value):
            errors += schema_errors(item, schema["items"], where + "[" + str(index) + "]")
    return errors
