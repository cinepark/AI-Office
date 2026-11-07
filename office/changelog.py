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
    {"id": "2026-11-07-title", "who": "dev", "text": "제목에 '돈·팔릴까' 주제어 금지, 작품·사람 이름이 들어간 질문으로. 반말체 문장은 편집장이 반려"},
    {"id": "2026-11-07-demand", "who": "dev", "text": "편집장이 글감을 검색 수요로 고름: 사람들이 검색창·AI에 묻는 질문 확인 → 본문이 그 질문에 답하는지 최종 점검"},
    {"id": "2026-11-07-imgretry", "who": "dev", "text": "블로그 그림이 거절되면(실존 캐릭터·작품명 등) 무난한 장면으로 자동 재시도, 그림 지시문에 실존 이름 금지"},
    {"id": "2026-11-07-info", "who": "design", "text": "CINEPARK 정보글(순위·목록·업데이트) 추가: 대표님 베트남·인도네시아 글 형식, 화·목·토 예약, 썸네일 1장 + 포스터 자리"},
    {"id": "2026-11-07-exclude", "who": "dev", "text": "베트남·인도네시아 흥행순위는 글감에서 제외(대표님이 매년 1월 직접 정리)"},
    {"id": "2026-11-07-info-manual", "who": "dev", "text": "정보글 자동 예약 해제: 예약은 매일 기획기사, 정보글은 대표님이 필요할 때만"},
    {"id": "2026-11-07-feature", "who": "dev", "text": "CINEPARK 정체성: 전 세계 영화 산업의 자금·사람·비하인드 피처 기사. 리드-넛그래프-본문-키커, 네 갈래(돈의 경로·사람·제작기·업계 구조), 1차 자료"},
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
