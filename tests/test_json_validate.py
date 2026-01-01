import os
import pytest
from utils.json_validate import validate_json_against_schema, load_json, save_json, SchemaValidationError


def test_validate_and_io(tmp_path):
    schema = {"type": "object", "properties": {"name": {"type": "string"}}, "required": ["name"]}

    valid = {"name": "x"}
    # should not raise
    validate_json_against_schema(valid, schema)

    invalid = {"bad": 1}
    with pytest.raises(SchemaValidationError):
        validate_json_against_schema(invalid, schema)

    # test save/load
    p = os.path.join(str(tmp_path), "out.json")
    save_json(p, {"a": 1})
    data = load_json(p)
    assert data["a"] == 1
