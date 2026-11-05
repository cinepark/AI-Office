"""R2 보관소: 상태 파일(state.json)과 게시 이미지.

MakingShorts-Engine 의 r2_store.py 와 같은 R2 키 4개를 씁니다.
Threads 는 공개 주소의 이미지만 가져가므로, 게시 순간에 1시간짜리 서명 링크를 만들어 넘깁니다.
버킷 자체는 비공개 그대로 둡니다.
"""
from __future__ import annotations

import json
import os
from urllib.parse import urlparse

STATE_KEY = "turnerbro-threads/state.json"


def _client():
    import boto3
    from botocore.config import Config
    ep = os.environ["R2_ENDPOINT"].strip().rstrip("/")
    if not ep.startswith("http"):
        ep = "https://" + ep
    u = urlparse(ep)
    return boto3.client(
        "s3",
        endpoint_url=f"{u.scheme}://{u.netloc}",
        aws_access_key_id=os.environ["R2_ACCESS_KEY_ID"].strip(),
        aws_secret_access_key=os.environ["R2_SECRET_ACCESS_KEY"].strip(),
        region_name="auto",
        config=Config(signature_version="s3v4", retries={"max_attempts": 3}),
    )


def _bucket() -> str:
    return os.environ["R2_BUCKET"].strip()


def load_state() -> dict:
    try:
        obj = _client().get_object(Bucket=_bucket(), Key=STATE_KEY)
        return json.loads(obj["Body"].read().decode("utf-8"))
    except Exception as e:  # 처음 실행: 파일 없음
        if "NoSuchKey" in str(e) or "404" in str(e):
            return {}
        raise


def save_state(state: dict) -> None:
    _client().put_object(Bucket=_bucket(), Key=STATE_KEY,
                         Body=json.dumps(state, ensure_ascii=False, indent=1).encode("utf-8"),
                         ContentType="application/json")


def put_bytes(key: str, data: bytes, content_type: str) -> str:
    _client().put_object(Bucket=_bucket(), Key=key, Body=data, ContentType=content_type)
    return key


def get_bytes(key: str) -> bytes:
    return _client().get_object(Bucket=_bucket(), Key=key)["Body"].read()


def signed_url(key: str, seconds: int = 3600) -> str:
    return _client().generate_presigned_url("get_object", Params={"Bucket": _bucket(), "Key": key},
                                            ExpiresIn=seconds)


def delete(key: str) -> None:
    _client().delete_object(Bucket=_bucket(), Key=key)
