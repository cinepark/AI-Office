"""Threads API (Meta 공식 문서 기준).

게시: 컨테이너 생성 → 30초 대기(처리 시간) → 게시 → 링크 조회.
토큰: 60일짜리 장기 토큰. 24시간이 지난 토큰은 갱신 가능 → 매주 갱신해 R2 상태 파일에 보관.
"""
from __future__ import annotations

import time

import requests

BASE = "https://graph.threads.com/v1.0"


class ThreadsError(RuntimeError):
    pass


def _check(r: requests.Response) -> dict:
    try:
        data = r.json()
    except ValueError:
        data = {"raw": r.text[:500]}
    if r.status_code >= 400 or "error" in data:
        raise ThreadsError(f"HTTP {r.status_code}: {data}")
    return data


def me(token: str) -> dict:
    return _check(requests.get(f"{BASE}/me", params={"fields": "id,username", "access_token": token}, timeout=30))


def publish_image(user_id: str, token: str, image_url: str, text: str) -> dict:
    c = _check(requests.post(f"{BASE}/{user_id}/threads", timeout=60, data={
        "media_type": "IMAGE", "image_url": image_url, "text": text, "access_token": token}))
    cid = c["id"]
    # 처리 완료까지 기다린다 (문서 권장 약 30초). 최대 3분.
    for _ in range(12):
        time.sleep(15)
        st = _check(requests.get(f"{BASE}/{cid}", timeout=30,
                                 params={"fields": "status,error_message", "access_token": token}))
        if st.get("status") == "FINISHED":
            break
        if st.get("status") in ("ERROR", "EXPIRED"):
            raise ThreadsError(f"컨테이너 처리 실패: {st}")
    p = _check(requests.post(f"{BASE}/{user_id}/threads_publish", timeout=60,
                             data={"creation_id": cid, "access_token": token}))
    mid = p["id"]
    link = _check(requests.get(f"{BASE}/{mid}", timeout=30,
                               params={"fields": "permalink", "access_token": token}))
    return {"media_id": mid, "permalink": link.get("permalink", "")}


def refresh(token: str) -> dict:
    return _check(requests.get("https://graph.threads.com/refresh_access_token", timeout=30,
                               params={"grant_type": "th_refresh_token", "access_token": token}))
