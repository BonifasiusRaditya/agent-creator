"""Where video files live: the local data folder, or S3-compatible object storage (Tencent COS).

Keys are POSIX paths such as ``projects/<pid>/uploads/<id>.mp4`` or ``jobs/<jid>/final.mp4``.
They are written once and never overwritten, which keeps backups incremental.
"""
import os
import shutil
from pathlib import Path, PurePosixPath
from urllib.parse import quote, urlparse

from fastapi.responses import FileResponse, RedirectResponse

from .errors import AppError

# Only these prefixes hold creator media; everything else in the data folder is local-only.
MEDIA_PREFIXES = ("projects/", "jobs/")


def normalize_key(key):
    """Accept refs saved on Windows (backslashes) and reject anything outside the store."""
    text = str(key).replace("\\", "/").lstrip("/")
    path = PurePosixPath(text)
    if not text or path.is_absolute() or any(part in {"..", ""} for part in path.parts):
        raise AppError("This file is no longer available.", "FILE_NOT_FOUND", 404)
    return path.as_posix()


def attachment(filename):
    return f"attachment; filename=\"{filename}\"; filename*=UTF-8''{quote(filename)}"


class LocalStorage:
    backend = "local"
    origin = None  # Served by the application itself.

    def __init__(self, root):
        self.root = Path(root).resolve()

    def path(self, key):
        path = (self.root / normalize_key(key)).resolve()
        if not path.is_relative_to(self.root):
            raise AppError("This file is no longer available.", "FILE_NOT_FOUND", 404)
        return path

    def put_file(self, key, source, content_type=None):
        target = self.path(key)
        if Path(source).resolve() == target:
            return  # The worker already wrote the file in place.
        target.parent.mkdir(parents=True, exist_ok=True)
        temp = target.with_name(target.name + ".part")
        shutil.copyfile(source, temp)
        temp.replace(target)

    def put_bytes(self, key, data, content_type=None):
        target = self.path(key)
        target.parent.mkdir(parents=True, exist_ok=True)
        temp = target.with_name(target.name + ".part")
        temp.write_bytes(data)
        temp.replace(target)

    def get_bytes(self, key):
        try:
            return self.path(key).read_bytes()
        except OSError:
            raise AppError("This file is no longer available.", "FILE_NOT_FOUND", 404) from None

    def fetch(self, key, scratch):
        """Return a readable local path for the object (no copy is needed locally)."""
        path = self.path(key)
        if not path.is_file():
            raise AppError("This file is no longer available.", "FILE_NOT_FOUND", 404)
        return path

    def size(self, key):
        path = self.path(key)
        return path.stat().st_size if path.is_file() else None

    def delete(self, key):
        self.path(key).unlink(missing_ok=True)

    def delete_prefix(self, prefix):
        path = self.path(prefix)
        if path.is_dir():
            shutil.rmtree(path)
        else:
            path.unlink(missing_ok=True)

    def list(self, prefix):
        base = self.path(prefix)
        if not base.is_dir():
            return
        for item in sorted(base.rglob("*")):
            if item.is_file() and not item.name.endswith(".part"):
                yield item.relative_to(self.root).as_posix(), item.stat().st_size

    def copy(self, source_key, target_key):
        self.put_file(target_key, self.fetch(source_key, None))

    def upload_target(self, key, max_bytes, content_type, local_url):
        # The application receives the file itself at local_url.
        return {"url": local_url, "fields": {}, "max_bytes": max_bytes}

    def response(self, key, media_type, filename=None):
        path = self.path(key)
        if not path.is_file():
            raise AppError("This file is no longer available.", "FILE_NOT_FOUND", 404)
        return FileResponse(path, media_type=media_type, filename=filename)


class S3Storage:
    """Tencent COS (or any S3-compatible service). The browser uploads and downloads
    directly with short-lived signed URLs; credentials never leave the server."""

    backend = "cos"
    URL_SECONDS = 15 * 60

    def __init__(self, bucket, region, secret_id, secret_key, endpoint=None):
        import boto3
        from botocore.config import Config
        if not bucket or not region or not secret_id or not secret_key:
            raise AppError("Set TRENDFORGE_COS_BUCKET, TRENDFORGE_COS_REGION, TRENDFORGE_COS_SECRET_ID and "
                           "TRENDFORGE_COS_SECRET_KEY to use COS storage.", "STORAGE_CONFIG", 503)
        self.bucket = bucket
        self.endpoint = endpoint or f"https://cos.{region}.myqcloud.com"
        self.client = boto3.client("s3", region_name=region, endpoint_url=self.endpoint,
                                   aws_access_key_id=secret_id, aws_secret_access_key=secret_key,
                                   config=Config(signature_version="s3v4", s3={"addressing_style": "virtual"},
                                                 retries={"max_attempts": 4, "mode": "standard"}))
        parsed = urlparse(self.endpoint)
        self.origin = f"{parsed.scheme}://{bucket}.{parsed.netloc}"

    def _errors(self):
        from botocore.exceptions import BotoCoreError, ClientError
        return (BotoCoreError, ClientError)

    def put_file(self, key, source, content_type=None):
        extra = {"ContentType": content_type} if content_type else {}
        try:
            self.client.upload_file(str(source), self.bucket, normalize_key(key), ExtraArgs=extra or None)
        except self._errors():
            raise AppError("Video storage is unavailable. Your work is saved; try again shortly.", "STORAGE_UNAVAILABLE", 503) from None

    def put_bytes(self, key, data, content_type=None):
        try:
            self.client.put_object(Bucket=self.bucket, Key=normalize_key(key), Body=data,
                                   **({"ContentType": content_type} if content_type else {}))
        except self._errors():
            raise AppError("Video storage is unavailable. Try again shortly.", "STORAGE_UNAVAILABLE", 503) from None

    def get_bytes(self, key):
        try:
            return self.client.get_object(Bucket=self.bucket, Key=normalize_key(key))["Body"].read()
        except self._errors():
            raise AppError("This file is no longer available.", "FILE_NOT_FOUND", 404) from None

    def fetch(self, key, scratch):
        key = normalize_key(key)
        target = Path(scratch) / "inputs" / key
        if target.is_file():
            return target
        target.parent.mkdir(parents=True, exist_ok=True)
        try:
            self.client.download_file(self.bucket, key, str(target))
        except self._errors():
            target.unlink(missing_ok=True)
            raise AppError("A saved video could not be read from storage. Try again shortly.", "STORAGE_UNAVAILABLE", 503) from None
        return target

    def size(self, key):
        from botocore.exceptions import ClientError
        try:
            return self.client.head_object(Bucket=self.bucket, Key=normalize_key(key))["ContentLength"]
        except ClientError as exc:
            if exc.response.get("Error", {}).get("Code") in {"404", "NoSuchKey", "NotFound"}:
                return None
            raise AppError("Video storage is unavailable. Try again shortly.", "STORAGE_UNAVAILABLE", 503) from None

    def delete(self, key):
        try:
            self.client.delete_object(Bucket=self.bucket, Key=normalize_key(key))
        except self._errors():
            raise AppError("A stored file could not be deleted. Try again.", "STORAGE_UNAVAILABLE", 503) from None

    def delete_prefix(self, prefix):
        keys = [key for key, _ in self.list(prefix)]
        try:
            for start in range(0, len(keys), 1000):
                self.client.delete_objects(Bucket=self.bucket, Delete={"Objects": [{"Key": k} for k in keys[start:start + 1000]], "Quiet": True})
        except self._errors():
            raise AppError("Some stored files could not be deleted. Try again.", "STORAGE_UNAVAILABLE", 503) from None

    def list(self, prefix):
        prefix = normalize_key(prefix).rstrip("/") + "/"
        try:
            for page in self.client.get_paginator("list_objects_v2").paginate(Bucket=self.bucket, Prefix=prefix):
                for item in page.get("Contents", []):
                    yield item["Key"], item["Size"]
        except self._errors():
            raise AppError("Video storage is unavailable. Try again shortly.", "STORAGE_UNAVAILABLE", 503) from None

    def copy(self, source_key, target_key):
        try:
            self.client.copy({"Bucket": self.bucket, "Key": normalize_key(source_key)}, self.bucket, normalize_key(target_key))
        except self._errors():
            raise AppError("A stored file could not be copied.", "STORAGE_UNAVAILABLE", 503) from None

    def upload_target(self, key, max_bytes, content_type, local_url):
        # A POST policy lets COS itself refuse files over the size limit.
        post = self.client.generate_presigned_post(
            self.bucket, normalize_key(key), Fields={"Content-Type": content_type},
            Conditions=[{"Content-Type": content_type}, ["content-length-range", 1, max_bytes]],
            ExpiresIn=self.URL_SECONDS)
        return {"url": post["url"], "fields": post["fields"], "max_bytes": max_bytes}

    def response(self, key, media_type, filename=None):
        params = {"Bucket": self.bucket, "Key": normalize_key(key), "ResponseContentType": media_type}
        if filename:
            params["ResponseContentDisposition"] = attachment(filename)
        url = self.client.generate_presigned_url("get_object", Params=params, ExpiresIn=self.URL_SECONDS)
        return RedirectResponse(url, status_code=307)


def create_storage(local_root):
    backend = os.environ.get("TRENDFORGE_STORAGE_BACKEND", "local").strip() or "local"
    if backend == "local":
        return LocalStorage(local_root)
    if backend == "cos":
        return S3Storage(os.environ.get("TRENDFORGE_COS_BUCKET", "").strip(), os.environ.get("TRENDFORGE_COS_REGION", "").strip(),
                         os.environ.get("TRENDFORGE_COS_SECRET_ID", "").strip(), os.environ.get("TRENDFORGE_COS_SECRET_KEY", "").strip(),
                         os.environ.get("TRENDFORGE_COS_ENDPOINT", "").strip() or None)
    raise AppError("Set TRENDFORGE_STORAGE_BACKEND to local or cos.", "STORAGE_CONFIG", 503)
