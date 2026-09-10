import httpx
import pytest
from geoai.storage import SupabaseStorage
from geoai.models import MockAdapter, ResearchSkySensePPAdapter
from geoai.compute import MockComputeProvider


def test_storage_missing_is_false_but_auth_errors_propagate():
    storage = SupabaseStorage(
        "http://storage.test",
        "secret",
        transport=httpx.MockTransport(lambda r: httpx.Response(404)),
    )
    assert storage.exists("rasters", "test.tif") is False
    denied = SupabaseStorage(
        "http://storage.test",
        "secret",
        transport=httpx.MockTransport(lambda r: httpx.Response(403)),
    )
    with pytest.raises(httpx.HTTPStatusError):
        denied.exists("rasters", "test.tif")


def test_storage_signed_url_and_upload_body():
    requests = []

    def server(req):
        requests.append(req)
        return httpx.Response(200, json={"signedURL": "/object/sign/rasters/a.tif?token=example"})

    s = SupabaseStorage("http://storage.test", "secret", transport=httpx.MockTransport(server))
    s.put_object("rasters", "a.tif", b"raster", "image/tiff")
    assert requests[-1].content == b"raster"
    assert requests[-1].headers["authorization"] == "Bearer secret"
    assert (
        s.create_signed_url("rasters", "a.tif", 60)
        == "http://storage.test/storage/v1/object/sign/rasters/a.tif?token=example"
    )


def test_mock_pipeline_and_research_boundary():
    adapter = MockAdapter()
    provider = MockComputeProvider(adapter)
    output = provider.execute({"width": 2, "height": 2}, {"support_mask": [0, 1]})
    assert len(output["probabilities"]) == 4
    assert output["mock"] is True
    assert adapter.healthcheck()["status"] == "ok"
    research = ResearchSkySensePPAdapter()
    assert research.model_info()["usage_policy"] == "research_only"
    assert research.healthcheck()["status"] == "disabled"
    with pytest.raises(NotImplementedError):
        research.predict({}, {})


def test_mock_rejects_unbounded_query():
    with pytest.raises(ValueError):
        MockAdapter().prepare_query({"width": 100000, "height": 100000})


@pytest.mark.parametrize("key", ["../escape", "/absolute", "a//b", "a/./b"])
def test_storage_rejects_ambiguous_object_keys(key):
    with pytest.raises(ValueError):
        SupabaseStorage.path("rasters", key)


def test_storage_stream_upload_and_delete():
    from io import BytesIO

    seen = []

    def handler(request):
        seen.append(request)
        return httpx.Response(200, content=b"abc")

    storage = SupabaseStorage(
        "http://storage.test", "secret", transport=httpx.MockTransport(handler)
    )
    storage.put_object("rasters", "a.tif", BytesIO(b"abc"), "image/tiff")
    assert seen[-1].content == b"abc"
    assert storage.get_object("rasters", "a.tif") == b"abc"
    storage.delete_object("rasters", "a.tif")
    assert seen[-1].method == "DELETE"
    assert b"a.tif" in seen[-1].content


def test_storage_legacy_missing_error_is_normalized():
    def handler(request):
        return httpx.Response(400, json={"statusCode": "404", "code": "NoSuchKey"})

    storage = SupabaseStorage(
        "http://storage.test", "secret", transport=httpx.MockTransport(handler)
    )
    assert storage.exists("rasters", "missing.tif") is False


def test_storage_other_bad_request_is_not_missing():
    def handler(request):
        return httpx.Response(400, json={"statusCode": "403", "code": "AccessDenied"})

    storage = SupabaseStorage(
        "http://storage.test", "secret", transport=httpx.MockTransport(handler)
    )
    with pytest.raises(httpx.HTTPStatusError):
        storage.exists("rasters", "private.tif")
