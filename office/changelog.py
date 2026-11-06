"""설계·개발·보안 담당의 업무 기록.

코드를 고칠 때마다 CHANGES 맨 아래에 한 줄을 더한다. 새 코드가 올라간 뒤
사무실 화면이 처음 열리거나 서버가 처음 돌 때, 아직 알리지 않은 항목을 그 담당 책상에
'완료'로 띄우고 활동 기록에 남긴다.

보안 담당은 하루 한 번 서버가 쓰는 열쇠(비밀값)와 Threads 토큰 남은 기간을 점검한다.
"""
from __future__ import annotations

import datetime as dt
import os

from .staff import KST, act

# who: design(설계) | dev(개발) | security(보안)
CHANGES = [
    {"id": "2026-11-06-jobs", "who": "dev", "text": "업무 지시서 도입: 버튼·SHIHO 지시를 서버가 받아 처리, 브라우저를 닫아도 계속"},
    {"id": "2026-11-06-cine-plan", "who": "design", "text": "CINEPARK 그림 6장 구성 개편: 시호 2장 + BTS 촬영장 + 사물 2장 + 자연 풍광"},
    {"id": "2026-11-06-bts", "who": "design", "text": "BTS 촬영장 시네마틱 3D, 촬영장 12종 무작위, 시호 카메오(민소매)"},
    {"id": "2026-11-06-names", "who": "dev", "text": "해외 시상식·기관 이름은 국내 언론 표기 + 원어로 쓰기 (고담 어워즈 건)"},
    {"id": "2026-11-06-cats", "who": "dev", "text": "Threads 고양이 장면 40개, 계절 장면, 시점·시간대 무작위로 중복 방지"},
    {"id": "2026-11-06-delete", "who": "design", "text": "블로그 패키지 삭제 버튼 추가"},
    {"id": "2026-11-06-exif", "who": "dev", "text": "휴대폰 여행 사진이 눕는 문제 수정: 사진 방향 정보(EXIF)대로 바로 세움"},
    {"id": "2026-11-06-rebuild", "who": "dev", "text": "Threads '예약 전부 새로 만들기' 버튼 (중복·누운 사진 일괄 교체)"},
    {"id": "2026-11-06-imgcache", "who": "dev", "text": "다시 만든 게시물이 화면에 예전 그림·멘트로 보이던 문제 수정"},
    {"id": "2026-11-06-posted", "who": "design", "text": "블로그 '네이버에 올림' 버튼과 올린 글 기록(주소 저장)"},
    {"id": "2026-11-06-review-img", "who": "design", "text": "리뷰&리뷰 그림 3장이 같은 구도로 반복되던 문제: 장소·거리·동작을 그림마다 다르게"},
    {"id": "2026-11-06-editor", "who": "dev", "text": "CINEPARK 편집장 검토 추가: 작품 설명·'왜'에 대한 답이 없는 원고는 그림 전에 돌려보내 다시 쓰기"},
    {"id": "2026-11-06-magazine", "who": "dev", "text": "CINEPARK 영화잡지 기준: 관점(angle)·배경 자료 4곳 이상, 편집장이 속보형 원고 반려"},
    {"id": "2026-11-06-market", "who": "dev", "text": "CINEPARK 돈·셀럽·뒷얘기를 한·미·일 상장사 사업 경로와 연결(공시·IR 근거), 주가 전망 금지"},
    {"id": "2026-11-06-kr-first", "who": "dev", "text": "상장사 연결은 국내 종목 우선, 해외(미·일)는 국내 회사와 얽힌 경우 함께"},
    {"id": "2026-11-06-sync", "who": "dev", "text": "블로그 패키지 삭제·게시가 사무실 화면에 바로 반영, SHIHO가 'CINEPARK 글감' 지시를 바로 실행"},
    {"id": "2026-11-06-security", "who": "security", "text": "매일 비밀값·Threads 토큰 남은 기간 자동 점검 시작"},
]

SERVER_KEYS = ["OPENAI_API_KEY", "THREADS_ACCESS_TOKEN", "THREADS_USER_ID",
               "R2_ENDPOINT", "R2_ACCESS_KEY_ID", "R2_SECRET_ACCESS_KEY", "R2_BUCKET", "GOOGLE_SA_JSON"]


def announce(state: dict) -> bool:
    """아직 알리지 않은 변경을 담당 책상에 띄운다. 바뀐 것이 있으면 True."""
    seen = state.setdefault("changes_seen", [])
    new = [c for c in CHANGES if c["id"] not in seen]
    for c in new:
        act(state, c["who"], f"반영 완료: {c['text']}", "done")
        seen.append(c["id"])
    return bool(new)


def security_check(state: dict) -> bool:
    """서버에서 하루 한 번: 비밀값이 다 있는지, Threads 토큰이 얼마나 남았는지. 점검했으면 True."""
    today = dt.datetime.now(KST).date().isoformat()
    if state.get("security_checked") == today:
        return False
    missing = [k for k in SERVER_KEYS if not os.environ.get(k, "").strip()]
    left = None
    if state.get("threads_token_refreshed") and state.get("threads_token_expires_in"):
        exp = dt.datetime.fromisoformat(state["threads_token_refreshed"]) + dt.timedelta(
            seconds=int(state["threads_token_expires_in"]))
        left = (exp - dt.datetime.now(KST)).days
    if missing:
        act(state, "security", f"점검: 비어 있는 비밀값 {', '.join(missing)}", "error")
    elif left is not None and left < 10:
        act(state, "security", f"점검: Threads 토큰이 {left}일 남았습니다. 월요일 자동 갱신을 확인합니다.", "error")
    else:
        tail = f", Threads 토큰 {left}일 남음" if left is not None else ""
        act(state, "security", f"점검 완료: 비밀값 {len(SERVER_KEYS)}개 정상{tail}", "done")
    state["security_checked"] = today
    return True
