"""업무 지시서: 사무실 화면은 지시서만 남기고, 실제 일은 GitHub 서버(엔진)가 처리한다.

화면(버튼·SHIHO) → add() 로 지시서 저장 → kick() 로 서버에 '일거리 있음' 신호
서버(python -m office.run work|blogwork) → claim() 으로 가져가 처리 → finish()
신호가 누락돼도 Cloudflare 알람 시계가 한 시간마다 순찰(work, blogwork)하며 남은 지시서를 처리한다.

종류
- Threads 계열(같은 상태 파일을 쓰므로 게시 작업과 줄을 선다): produce, remake, post_now  → 'work'
- 블로그 계열(별도 상태 파일): blog_make                                              → 'blogwork'
"""
from __future__ import annotations

import datetime as dt
import json
import os
import uuid

from .staff import KST

JOBS_KEY = "office/jobs.json"
THREADS_TYPES = {"produce", "remake", "post_now", "rebuild"}
BLOG_TYPES = {"blog_make", "blog_draw", "blog_clip"}
LABEL = {"produce": "Threads 재고 채우기", "remake": "Threads 게시물 다시 만들기", "post_now": "Threads 지금 게시", "rebuild": "Threads 예약 전부 새로 만들기",
         "blog_make": "블로그 패키지 만들기", "blog_draw": "블로그 그림 그리기", "blog_clip": "리뷰 10초 클립 만들기"}


def _now() -> str:
    return dt.datetime.now(KST).isoformat(timespec="seconds")


def lane(job_type: str) -> str:
    return "blogwork" if job_type in BLOG_TYPES else "work"


def load() -> list[dict]:
    from . import storage
    try:
        obj = storage._client().get_object(Bucket=storage._bucket(), Key=JOBS_KEY)
        return json.loads(obj["Body"].read().decode("utf-8"))
    except Exception as e:
        if "NoSuchKey" in str(e) or "404" in str(e):
            return []
        raise


def save(jobs: list[dict]) -> None:
    from . import storage
    jobs = jobs[-200:]  # 최근 200장만 보관
    storage.put_bytes(JOBS_KEY, json.dumps(jobs, ensure_ascii=False, indent=1).encode("utf-8"), "application/json")


def add(job_type: str, args: dict | None = None, by: str = "Mr. MOON") -> dict:
    """지시서 한 장을 남긴다. 같은 일이 이미 대기·진행 중이면 새로 만들지 않고 그 지시서를 돌려준다."""
    args = args or {}
    jobs = load()
    for j in jobs:
        if j["type"] == job_type and j["args"] == args and j["status"] in ("pending", "running"):
            return j
    job = {"id": uuid.uuid4().hex[:8], "type": job_type, "args": args, "by": by, "label": LABEL.get(job_type, job_type),
           "created": _now(), "status": "pending", "step": "대기", "result": ""}
    jobs.append(job)
    save(jobs)
    return job


def claim(lane_name: str) -> dict | None:
    """이 줄(work/blogwork)의 가장 오래된 대기 지시서를 '진행 중'으로 바꿔 가져간다."""
    jobs = load()
    for j in jobs:
        if j["status"] == "pending" and lane(j["type"]) == lane_name:
            j["status"], j["started"], j["step"] = "running", _now(), "시작"
            save(jobs)
            return j
    return None


def update(job_id: str, **fields) -> None:
    jobs = load()
    for j in jobs:
        if j["id"] == job_id:
            j.update(fields)
    save(jobs)


def finish(job_id: str, ok: bool, result: str) -> None:
    update(job_id, status="done" if ok else "error", step="완료" if ok else "실패", result=result[:300], ended=_now())


def recover_stale(minutes: int = 50) -> int:
    """서버가 도중에 멈춰 '진행 중'으로 남은 지시서를 다시 대기로 돌린다."""
    jobs, n = load(), 0
    for j in jobs:
        if j["status"] == "running" and j.get("started"):
            if (dt.datetime.now(KST) - dt.datetime.fromisoformat(j["started"])).total_seconds() > minutes * 60:
                j["status"], j["step"] = "pending", "재시도 대기"
                n += 1
    if n:
        save(jobs)
    return n


def kick(lane_name: str) -> bool:
    """GitHub 서버에 '일거리 있음' 신호. GH_TOKEN(Actions 쓰기 권한)이 있어야 한다. 실패해도 순찰이 처리한다."""
    import requests
    token = os.environ.get("GH_TOKEN", "").strip()
    repo = os.environ.get("GH_REPO", "cinepark/AI-Office").strip()
    if not token:
        return False
    try:
        r = requests.post(f"https://api.github.com/repos/{repo}/actions/workflows/office.yml/dispatches",
                          headers={"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json",
                                   "X-GitHub-Api-Version": "2022-11-28"},
                          json={"ref": "main", "inputs": {"command": lane_name, "arg": ""}}, timeout=15)
        return r.status_code in (200, 204)
    except Exception:
        return False


def order(job_type: str, args: dict | None = None, by: str = "Mr. MOON") -> tuple[dict, bool]:
    """화면에서 쓰는 한 줄: 지시서 남기고 신호 보내기. (지시서, 신호 성공 여부)"""
    job = add(job_type, args, by)
    return job, kick(lane(job_type))


def recent(n: int = 15) -> list[dict]:
    return list(reversed(load()[-n:]))
