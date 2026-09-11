from uuid import uuid4
import pytest
from fastapi import HTTPException
from pydantic import ValidationError
from geoai.spatial import RenameInput, UserSQLRepository


def test_name_only_schema():
    assert RenameInput(name="  农田样例  ", expected_name="old").name == "农田样例"
    for data in (
        {"name": " "},
        {"name": "a" * 121},
        {"name": "ok", "geometry": {}},
        {"name": "ok", "project_id": str(uuid4())},
    ):
        with pytest.raises(ValidationError):
            RenameInput(expected_name="old", **data)


@pytest.mark.parametrize("kind", ["aoi", "prompt"])
def test_rename_scopes_and_conflicts(kind):
    repo = UserSQLRepository(uuid4())
    calls = []
    responses = iter([[{"role": "editor"}], [{"id": "x", "name": "new"}]])

    def execute(query, params=()):
        calls.append((query, params))
        return next(responses)

    repo.execute = execute
    data = RenameInput(name="new", expected_name="old")
    assert repo.rename(kind, "project", "object", data)["name"] == "new"
    assert calls[1][1] == ("new", "object", "project", "old")
    assert "SET name=%s" in calls[1][0]
    responses = iter([[{"role": "viewer"}]])
    with pytest.raises(HTTPException) as error:
        repo.rename(kind, "project", "object", data)
    assert error.value.status_code == 403
    responses = iter([[{"role": "owner"}], [], [{"id": "x"}]])
    with pytest.raises(HTTPException) as error:
        repo.rename(kind, "project", "object", data)
    assert error.value.status_code == 409
    responses = iter([[{"role": "owner"}], [], []])
    with pytest.raises(HTTPException) as error:
        repo.rename(kind, "project", "object", data)
    assert error.value.status_code == 404


def test_description_requires_previous_value_and_is_bounded():
    for fields in (
        {"description": "new"},
        {"expected_description": "old"},
        {"description": "x" * 2001, "expected_description": ""},
    ):
        with pytest.raises(ValidationError):
            RenameInput(name="name", expected_name="name", **fields)
    assert (
        RenameInput(
            name="name", expected_name="name", description="", expected_description="old"
        ).description
        == ""
    )


def test_description_compare_and_swap():
    repo = UserSQLRepository(uuid4())
    calls = []
    responses = iter([[{"role": "owner"}], [{"name": "name", "description": "new"}]])

    def execute(query, params=()):
        calls.append((query, params))
        return next(responses)

    repo.execute = execute
    repo.rename(
        "prompt",
        "project",
        "object",
        RenameInput(
            name="name", expected_name="name", description="new", expected_description="old"
        ),
    )
    assert calls[1][1] == ("name", "new", "object", "project", "name", "old")
    assert "AND description=%s" in calls[1][0]
