"""Object storage boundary. Provider SDKs never escape this module."""

from typing import Protocol, BinaryIO
from urllib.parse import quote
import httpx


class ObjectStorageProvider(Protocol):
    def put_object(self, bucket: str, key: str, data: bytes | BinaryIO, mime: str) -> None: ...
    def get_object(self, bucket: str, key: str) -> bytes: ...
    def delete_object(self, bucket: str, key: str) -> None: ...
    def head_object(self, bucket: str, key: str) -> dict: ...
    def create_signed_url(self, bucket: str, key: str, expires: int = 300) -> str: ...
    def exists(self, bucket: str, key: str) -> bool: ...


class SupabaseStorage:
    def __init__(self, url: str, key: str, *, public_url: str | None = None, transport=None):
        self.public_url = (public_url or url).rstrip("/")
        self.client = httpx.Client(
            base_url=url.rstrip("/") + "/storage/v1/",
            headers={"apikey": key, "Authorization": f"Bearer {key}"},
            timeout=60,
            transport=transport,
        )

    @staticmethod
    def path(bucket: str, key: str) -> str:
        if (
            not bucket
            or "/" in bucket
            or not key
            or any(p in ("", ".", "..") for p in key.split("/"))
        ):
            raise ValueError("Invalid object key")
        return quote(bucket, safe="") + "/" + quote(key, safe="/")

    def put_object(self, bucket, key, data, mime="application/octet-stream"):
        content = iter(lambda: data.read(1024 * 1024), b"") if hasattr(data, "read") else data
        self.client.post(
            "object/" + self.path(bucket, key),
            content=content,
            headers={"Content-Type": mime, "x-upsert": "true"},
        ).raise_for_status()

    def get_object(self, bucket, key):
        return (
            self.client.get("object/authenticated/" + self.path(bucket, key))
            .raise_for_status()
            .content
        )

    def delete_object(self, bucket, key):
        self.path(bucket, key)
        self.client.request(
            "DELETE", "object/" + quote(bucket, safe=""), json={"prefixes": [key]}
        ).raise_for_status()

    def head_object(self, bucket, key):
        response = self.client.head(
            "object/authenticated/" + self.path(bucket, key)
        ).raise_for_status()
        return {
            "size": int(response.headers.get("content-length", 0)),
            "mime_type": response.headers.get("content-type"),
            "etag": response.headers.get("etag"),
        }

    def exists(self, bucket, key):
        try:
            self.head_object(bucket, key)
            return True
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code == 404:
                return False
            if exc.response.status_code == 400:
                # This pinned Storage release wraps NoSuchKey in HTTP 400.
                # Stream so a concurrent object creation cannot download a large raster.
                with self.client.stream(
                    "GET", "object/authenticated/" + self.path(bucket, key)
                ) as probe:
                    if probe.status_code == 400:
                        probe.read()
                        detail = probe.json()
                        if (
                            detail.get("code") == "NoSuchKey"
                            and str(detail.get("statusCode")) == "404"
                        ):
                            return False
            raise

    def create_signed_url(self, bucket, key, expires=300):
        if not 1 <= expires <= 86400:
            raise ValueError("Expiry must be between 1 and 86400 seconds")
        result = (
            self.client.post("object/sign/" + self.path(bucket, key), json={"expiresIn": expires})
            .raise_for_status()
            .json()
        )
        return self.public_url + "/storage/v1" + result["signedURL"]

    def close(self):
        self.client.close()
