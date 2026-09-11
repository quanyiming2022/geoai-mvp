import pytest
from fastapi import HTTPException
from geoai.rasters import validate_header, safe_filename


def test_only_tiff_headers():
    for header in (b"II*\x00", b"MM\x00*", b"II+\x00", b"MM\x00+"):
        validate_header(header)
    for header in (b"<VRT", b"abcd", b""):
        with pytest.raises(HTTPException):
            validate_header(header)


def test_filename_is_plain_tiff_basename():
    assert safe_filename("image.tif") == "image.tif"
    for name in ("../a.tif", "a.png", "", "folder/a.tif", "a\x00.tif"):
        with pytest.raises(HTTPException):
            safe_filename(name)


@pytest.mark.parametrize("chunked", [True, False])
def test_streamed_upload_limit(monkeypatch, chunked):
    from fastapi.testclient import TestClient
    from geoai import rasters
    from geoai.main import app
    from geoai.auth import identity, Identity

    class Repo:
        def members(self, _):
            return []

    class Config:
        max_upload_bytes = 1024

    app.dependency_overrides[identity] = lambda: Identity("test", {"id": "owner"})
    monkeypatch.setattr(rasters, "accessible", lambda *args: (Repo(), {"owner_id": "owner"}))
    monkeypatch.setattr(rasters, "Settings", Config)
    try:
        response = TestClient(app).post(
            "/projects/00000000-0000-0000-0000-000000000001/rasters",
            headers={"x-filename": "big.tif"},
            content=iter([b"II*\x00", b"x" * 1024]) if chunked else b"II*\x00" + b"x" * 1024,
        )
        assert response.status_code == 413
    finally:
        app.dependency_overrides.clear()


@pytest.mark.parametrize("committed", [True, False])
def test_registration_timeout_does_not_delete_source(monkeypatch, tmp_path, committed):
    from geoai import rasters
    from geoai.auth import Identity

    class Config:
        storage_bucket = "test"

    deleted = []

    class Storage:
        def put_object(self, *args):
            pass

        def delete_object(self, *args):
            deleted.append(args)

        def close(self):
            pass

    class Repo:
        row = None

        def __init__(self, *args):
            pass

        def create(self, data):
            Repo.row = data if committed else None
            raise HTTPException(503, "response lost")

        def get(self, *args):
            return Repo.row

    source = tmp_path / "source.tif"
    source.write_bytes(b"test")
    monkeypatch.setattr(rasters, "validate_raster", lambda _: None)
    monkeypatch.setattr(rasters, "provider", lambda _: Storage())
    monkeypatch.setattr(rasters, "PostgrestRasterRepository", Repo)
    args = (
        source,
        "source.tif",
        4,
        "checksum",
        "project",
        Identity("token", {"id": "user"}),
        Config(),
    )
    if committed:
        assert rasters.persist(*args)["checksum"] == "checksum"
    else:
        with pytest.raises(HTTPException) as error:
            rasters.persist(*args)
        assert error.value.detail["code"] == "registration_uncertain"
    assert not deleted
