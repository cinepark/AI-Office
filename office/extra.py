"""Threads '지금 한 편': 예약과 별개로, 대표님이 누를 때만 만드는 한 편.

순서(멘트 먼저, 그림은 나중): 소재 후보 3개 → 하나 고르기 → 멘트 3안 → 확정 → 그림 → 지금 올리기 / 다음 시간 게시물과 바꾸기.
소재: trend(오늘의 트렌드, 웹 검색) · random(랜덤 한 장면) · photo(대표님 사진을 수채화로).
그림: watercolor(계정 그림체) · photo(실사풍, 멘트 끝에 AI 표시).
상태는 st["extra"] 한 칸에만 둔다.
"""
from __future__ import annotations

import datetime as dt
import random

from . import planner as P

AI_MARK = "(AI로 만든 이미지)"

TREND_RULES = """당신은 Threads 계정 'Turner Bro'(turnerbro.32)의 기획 담당입니다.
이 계정은 여행 그림·고양이 그림을 올리고, 독자는 여행·고양이·책·일상·맛집·카페·재테크를 좋아하는 한국 사람입니다.
웹 검색으로 '오늘(또는 이번 주) 사람들이 많이 이야기하는 화제' 3개를 찾으세요. 생활 화제뿐 아니라 경제·주식·브랜드 소식도 좋습니다.
예: 코카콜라 주가 상승, 첫눈 예보, 연말 베스트셀러 발표, 일본 단풍 절정, 붕어빵 가격, 크리스마스 마켓 개장.
제외: 정치, 사건·사고, 범죄, 재난 피해, 특정 연예인·실존 인물.
세 소재는 서로 다른 분야로 고르세요(예: 경제 하나, 계절·생활 하나, 여행·문화 하나).
각 소재마다 그림 한 장의 장면을 영어로 단정적으로 쓰세요. 브랜드 소식이라도 로고·상표·글자는 그리지 않고 사물로만 표현합니다
(예: 코카콜라 주가 → 카페 테이블 위 김이 맺힌 로고 없는 빨간 콜라 병과 유리잔). 사람 얼굴·실존 인물 없이, 한 순간, 한 동작.
JSON 만 출력: {"ideas": [{"title": "소재 한 줄(한국어)", "why": "왜 지금 이야기되는지 한 줄(검색 근거, 숫자가 있으면 숫자로)", "scene": "English scene", "source": "출처 이름"}]}"""

RANDOM_SEEDS = ["새벽 편의점", "비 오는 날 서점 창가", "지하철 마지막 칸", "동네 빨래방의 밤", "문 닫기 직전의 빵집",
                "첫 손님 받는 카페", "퇴근길 붕어빵 노점", "겨울 아침 버스 정류장", "헌책방 계단", "옥상 빨랫줄",
                "새벽 수산시장", "기차 창가 자리", "동네 목욕탕 앞", "밤 열한 시 분식집", "눈 오는 날 골목 계단",
                "도서관 열람실 창가", "공항 출국장 의자", "시장 입구 국화빵", "한강 편의점 라면", "오래된 다방"]

RANDOM_RULES = """당신은 Threads 계정 'Turner Bro'(turnerbro.32)의 기획 담당입니다. 여행·고양이 정규편 사이에 혼자서도 눈길을 끌 '한 장면'을 기획합니다.
주어진 장소 씨앗 3개마다, 사람들이 '아 이 느낌 알지' 하고 멈출 한 순간을 정하세요.
장면은 영어로 단정적으로(사람 얼굴·실존 인물·로고·글자 없이, 한 순간, 한 동작).
JSON 만 출력: {"ideas": [{"title": "장면 한 줄(한국어)", "why": "왜 눈길을 끄는지 한 줄", "scene": "English scene", "source": ""}]}"""

PHOTO_RULES = """당신은 Threads 계정 'Turner Bro'(turnerbro.32)의 기획 담당입니다. 대표님이 직접 찍은 사진 한 장을 봅니다.
사진 속 장소·상황을 한 줄로 요약하고(동네 분위기와 상황까지만, 너무 자세하지 않게), 멘트를 쓸 관점 3가지를 제안하세요.
JSON 만 출력: {"ideas": [{"title": "장면 요약 + 관점 한 줄(한국어)", "why": "이 관점이 좋은 이유 한 줄", "scene": "", "source": ""}]}"""

REALISTIC = ("Photorealistic image in the look of a casual smartphone photo, natural light, true-to-life textures, "
             "square composition. No people's faces, no text, no logos.")


def _ask(cfg: dict, system: str, user: str, search: bool, image: bytes | None = None) -> dict:
    from . import ai
    import base64
    import json
    import re
    kw = {}
    if search:
        kw["tools"] = [{"type": "web_search", "search_context_size": "medium",
                        "user_location": {"type": "approximate", "country": "KR", "timezone": "Asia/Seoul"}}]
    content = [{"type": "input_text", "text": user}]
    if image:
        content.append({"type": "input_image",
                        "image_url": "data:image/png;base64," + base64.b64encode(ai._shrink(image, 768)).decode()})
    r = ai._client().responses.create(model=cfg["openai"]["text_model"],
                                      input=[{"role": "system", "content": system},
                                             {"role": "user", "content": content}], **kw)
    m = re.search(r"\{.*\}", r.output_text or "", re.S)
    if not m:
        raise RuntimeError("소재 응답을 읽지 못했습니다")
    return json.loads(m.group(0))


def ideas(cfg: dict, st: dict, mode: str, photo_key: str = "") -> dict:
    """1단계: 소재 후보 3개."""
    from . import storage
    today = P.now_kst().date()
    if mode == "trend":
        d = _ask(cfg, TREND_RULES, f"오늘은 {today:%Y년 %m월 %d일}입니다. 오늘의 소재 3개를 찾아 주세요.", search=True)
    elif mode == "photo":
        d = _ask(cfg, PHOTO_RULES, "대표님 사진입니다.", search=False, image=storage.get_bytes(photo_key))
    else:
        seeds = random.sample(RANDOM_SEEDS, 3)
        d = _ask(cfg, RANDOM_RULES, "장소 씨앗: " + " / ".join(seeds), search=False)
    ex = {"mode": mode, "stage": "ideas", "ideas": d.get("ideas", [])[:3], "photo_key": photo_key,
          "at": P.now_kst().isoformat()}
    st["extra"] = ex
    return ex


def captions(cfg: dict, st: dict, idx: int) -> dict:
    """2단계: 고른 소재로 멘트 3안(그림 없이 글만 먼저)."""
    from . import ai, storage
    ex = st["extra"]
    idea = ex["ideas"][idx]
    img = storage.get_bytes(ex["photo_key"]) if ex.get("mode") == "photo" else None
    subject = (f"자유 주제 한 편. 소재: {idea.get('title', '')}. 배경: {idea.get('why', '')}. "
               "아직 그림은 없습니다. 이 소재로 사람들이 한마디 보태고 싶어지는 멘트를 쓰세요. "
               "여행·고양이 유형 규칙 대신, 혼잣말 / 공감 / 말 걸기 세 가지로 쓰세요. "
               "경제·주식 소재면 사라·팔라 같은 투자 권유는 하지 않고, 숫자는 배경에 있는 것만 씁니다.")
    ex.update({"pick": idx, "options": ai.captions(cfg, subject, img), "stage": "captions"})
    return ex


def draw(cfg: dict, base_cfg: dict, st: dict, caption: str, style: str) -> dict:
    """3단계: 확정된 멘트에 맞춰 그림."""
    from . import ai, drive, storage
    ex = st["extra"]
    idea = ex["ideas"][ex.get("pick", 0)]
    if ex.get("mode") == "photo":
        style = "watercolor"  # 대표님 사진은 수채화로만(실사는 원본 사진 그대로가 낫다)
        refs = [drive.download(f) for f in base_cfg["google_drive"]["travel_reference_files"]]
        png = ai.draw(base_cfg, base_cfg["travel_style"], [storage.get_bytes(ex["photo_key"])] + refs)
    elif style == "photo":
        png = ai.render(base_cfg, f"{idea.get('scene', '')} The moment matches this caption: {caption} {REALISTIC}", [], "1024x1024")
    else:
        refs = [drive.download(f) for f in base_cfg["google_drive"]["travel_reference_files"]]
        png = ai.draw(base_cfg, f"{idea.get('scene', '')} The moment matches this caption: {caption} {base_cfg['style']}", refs)
    ext = "jpg" if png[:3] == b"\xff\xd8\xff" else "png"
    key = f"turnerbro-threads/extra/{P.now_kst():%Y%m%d_%H%M%S}.{ext}"
    storage.put_bytes(key, png, "image/jpeg" if ext == "jpg" else "image/png")
    final = caption.strip()
    if style == "photo" and AI_MARK not in final:
        final = f"{final}\n\n{AI_MARK}"
    today = P.now_kst().date().isoformat()
    st["images_made"][today] = st["images_made"].get(today, 0) + 1
    ex.update({"stage": "drawn", "r2_key": key, "caption": final, "style": style})
    return ex


def place(st: dict, cfg: dict, action: str) -> str:
    """4단계: 큐에 넣는다. now = 지금 게시용 칸 / swap = 다음 예약 게시물 자리를 대신한다. 큐 키를 돌려준다."""
    ex = st["extra"]
    now = P.now_kst()
    if action == "swap":
        later = sorted(k for k, v in st["queue"].items() if v.get("status") == "ready"
                       and k > f"{now:%Y-%m-%d}_{now:%H%M}" and v.get("kind") != "extra")
        if not later:
            raise RuntimeError("바꿀 예약 게시물이 없습니다")
        key = later[0]
        st["queue"][key]["status"] = "skipped"
    else:
        key = f"{now:%Y-%m-%d}_E{now:%H%M}"
    st["queue"][key] = {"kind": "extra", "date": key[:10], "slot": key, "r2_key": ex["r2_key"],
                        "caption": ex["caption"], "options": [ex["caption"]], "problems": [], "status": "ready",
                        "extra_title": ex["ideas"][ex.get("pick", 0)].get("title", ""), "style": ex.get("style", "")}
    # 대표님이 확정한 멘트 → 게시 직전 재검사가 바꾸지 않게
    st.setdefault("caption_edits", []).append({"t": now.isoformat(), "slot": key, "before": "", "after": ex["caption"]})
    ex["stage"] = "placed"
    ex["queue_key"] = key
    return key
