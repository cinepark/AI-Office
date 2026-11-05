"""AI OFFICE 직원 명부와 업무 일지.

담당자는 그림이 아니라 실제 업무를 맡습니다. 각 업무 함수가 일을 시작·끝낼 때
act() 로 일지를 남기고, 오피스 화면은 이 일지를 읽어 담당자 상태를 보여 줍니다.
"""
from __future__ import annotations

import datetime as dt
from zoneinfo import ZoneInfo

KST = ZoneInfo("Asia/Seoul")

DEPARTMENTS = [
    {"id": "management", "name": "총괄관리"},
    {"id": "it", "name": "IT기획전략실"},
    {"id": "content", "name": "콘텐츠 제작실"},
    {"id": "cinepark", "name": "CINEPARK"},
]

# id, 이름, 역할, 부서, 맡은 실제 업무
STAFF = [
    ("shiho", "SHIHO", "총괄 매니저", "management", "예약표를 보고 담당자에게 일을 나눕니다. 재고·실패를 챙깁니다."),
    ("strategy", "전략 담당", "기획·전략", "it", "주간 성과(게시 수·품종·시간대)를 정리합니다."),
    ("design", "설계 담당", "화면·업무 설계", "it", "오피스 화면과 업무 흐름을 관리합니다."),
    ("dev", "개발 담당", "개발·오류 대응", "it", "실패한 작업의 오류를 기록합니다."),
    ("security", "보안 담당", "권한·토큰", "it", "Threads 토큰을 매주 갱신하고 만료를 감시합니다."),
    ("research", "리서치 담당", "주제·출처", "content", "날씨·계절·영화계 뉴스를 찾아 글감을 만듭니다."),
    ("writer", "작가·편집 담당", "멘트·원고", "content", "Threads 멘트 3안과 블로그 원고를 씁니다."),
    ("image", "이미지 담당", "그림", "content", "고양이를 그리고 여행 사진을 펜 수채화로 바꿉니다."),
    ("video", "영상 담당", "영상", "content", "(대기) 숏폼 영상 업무가 생기면 맡습니다."),
    ("review", "검수 담당", "검사", "content", "멘트의 글자 수·금지어·이모지를 검사합니다."),
    ("channel", "채널 운영 담당", "게시", "content", "정해진 시각에 Threads에 게시하고 링크를 남깁니다."),
    ("cinepark", "CINEPARK", "영화 글", "cinepark", "영화잡지형 글감·원고·이미지 패키지를 만듭니다."),
]
STAFF_BY_ID = {s[0]: s for s in STAFF}


def now_iso() -> str:
    return dt.datetime.now(KST).isoformat(timespec="seconds")


def act(state: dict, agent: str, text: str, status: str = "done") -> None:
    """status: working | done | error | idle"""
    entry = {"t": now_iso(), "agent": agent, "status": status, "text": text}
    log = state.setdefault("agent_log", [])
    log.append(entry)
    del log[:-300]  # 최근 300건만 보관
    state.setdefault("agent_now", {})[agent] = entry


def latest(state: dict, agent: str) -> dict | None:
    return state.get("agent_now", {}).get(agent)
