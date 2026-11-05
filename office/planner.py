"""무엇을 만들지 정하는 담당 (네트워크 없음 — 테스트 가능).

- 고양이: 품종·장면 추첨. 직전 고양이와 같은 품종 금지, 최근 7일 같은 '품종+장면' 금지.
- 여행: 아직 안 쓴 원본 사진 선택. 직전 여행과 같은 도시 금지(가능할 때).
- 멘트 검사: 글자 수·금지어·이모지 수.
"""
from __future__ import annotations

import datetime as dt
import random
import re
from zoneinfo import ZoneInfo

KST = ZoneInfo("Asia/Seoul")


def now_kst() -> dt.datetime:
    return dt.datetime.now(KST)


def slot_key(date: dt.date, time_str: str) -> str:
    return f"{date.isoformat()}_{time_str.replace(':', '')}"


def upcoming_slot_keys(cfg: dict, start: dt.date, days: int) -> list[tuple[str, dict]]:
    out = []
    for d in range(days):
        day = start + dt.timedelta(days=d)
        for s in cfg["slots"]:
            out.append((slot_key(day, s["time"]), s))
    return out


def current_slot(cfg: dict, now: dt.datetime, window_min: int = 120) -> tuple[str, dict, float] | None:
    """지금 올려야 할 슬롯과 '예약 시각까지 남은 분'(음수=늦음).
    예약 시각 25분 전부터 window_min 분 뒤까지 허용 (GitHub 예약 실행 지연 대비)."""
    best = None
    for s in cfg["slots"]:
        hh, mm = map(int, s["time"].split(":"))
        target = now.replace(hour=hh, minute=mm, second=0, microsecond=0)
        diff = (now - target).total_seconds() / 60
        if -25 <= diff <= window_min:
            if best is None or abs(diff) < best[0]:
                best = (abs(diff), slot_key(now.date(), s["time"]), s, -diff)
    return (best[1], best[2], best[3]) if best else None


def _recent(history: list[dict], days: int, today: dt.date) -> list[dict]:
    lim = today - dt.timedelta(days=days)
    out = []
    for h in history:
        try:
            if dt.date.fromisoformat(h["date"]) >= lim:
                out.append(h)
        except (KeyError, ValueError):
            continue
    return out


def pick_cat(cfg: dict, history: list[dict], today: dt.date, rng: random.Random | None = None) -> tuple[dict, dict]:
    rng = rng or random.Random()
    cats = [h for h in history if h.get("kind") == "cat"]
    last_breed = cats[-1]["breed"] if cats else None
    recent_pairs = {(h.get("breed"), h.get("scene")) for h in _recent(cats, 7, today)}
    recent_scenes = [h.get("scene") for h in cats[-8:]]  # 장면 14개 중 최근 8개는 쉬게 함

    breeds = [b for b in cfg["breeds"] if b["id"] != last_breed] or cfg["breeds"]
    scenes = cfg["scenes"]
    candidates = [(b, s) for b in breeds for s in scenes
                  if (b["id"], s["id"]) not in recent_pairs and s["id"] not in recent_scenes]
    if not candidates:
        candidates = [(b, s) for b in breeds for s in scenes if (b["id"], s["id"]) not in recent_pairs]
    if not candidates:
        candidates = [(b, s) for b in breeds for s in scenes]
    return rng.choice(candidates)


def cat_prompt(cfg: dict, breed: dict, scene: dict) -> str:
    return (f"Match the drawing style of the attached reference images. "
            f"{breed['look'][0].upper() + breed['look'][1:]} {scene['text']}. {cfg['style']}")


def pick_travel(photos: list[dict], history: list[dict], used_ids: set[str],
                rng: random.Random | None = None) -> dict | None:
    """photos: [{id, name, city, year}] — 원본 사진 목록."""
    rng = rng or random.Random()
    fresh = [p for p in photos if p["id"] not in used_ids]
    if not fresh:
        return None
    travels = [h for h in history if h.get("kind") == "travel"]
    last_city = (travels[-1].get("city") or "").lower() if travels else ""
    other = [p for p in fresh if p["city"].lower() != last_city]
    pool = other or fresh
    # 도시를 먼저 고르고 그 안에서 사진을 고른다 → 사진이 많은 도시만 계속 나오는 것을 막음
    cities = sorted({p["city"] for p in pool})
    city = rng.choice(cities)
    return rng.choice([p for p in pool if p["city"] == city])


def parse_city_folder(name: str) -> tuple[str, str]:
    """'2006 Barcelona' → ('Barcelona', '2006'), 'LONDON' → ('LONDON', '')"""
    m = re.match(r"^\s*(\d{4})\s+(.+)$", name)
    if m:
        return m.group(2).strip(), m.group(1)
    return name.strip(), ""


_YEAR = re.compile(r"(?:19|20)\d{2}|\d+\s*년|몇\s*년")  # 연도·햇수 표기 금지
_EMOJI = re.compile("[\U0001F300-\U0001FAFF\U00002600-\U000027BF\U0001F000-\U0001F2FF]")


def _bigrams(t: str) -> set[str]:
    s = re.sub(r"[^\w]", "", t)
    return {s[i:i + 2] for i in range(len(s) - 1)}


def similarity(a: str, b: str) -> float:
    """두 멘트의 글자 겹침 정도 (0~1)."""
    x, y = _bigrams(a), _bigrams(b)
    return len(x & y) / len(x | y) if x and y else 0.0


def caption_problems(text: str, cfg: dict, recent: list[str] | tuple = ()) -> list[str]:
    c = cfg["caption"]
    probs = []
    t = text.strip()
    if not t:
        probs.append("빈 멘트")
    if len(t) > c["max_chars"]:
        probs.append(f"{len(t)}자 (최대 {c['max_chars']}자)")
    for w in c["banned"]:
        if w in t:
            probs.append(f"금지어 '{w}'")
    if len(_EMOJI.findall(t)) > c["max_emoji"]:
        probs.append("이모지 과다")
    if "#" in t:
        probs.append("해시태그 포함")
    if _YEAR.search(t):
        probs.append("연도 표기")
    if any(similarity(t, r) >= 0.25 for r in recent):
        probs.append("최근 멘트와 비슷함")
    return probs


def choose_caption(options: list[str], cfg: dict, recent: list[str] | tuple = ()) -> tuple[str, list[str]]:
    """검사를 통과한 첫 안. 모두 탈락이면 가장 짧은 안을 고르고 문제 목록을 함께 돌려준다."""
    clean = [o.strip().strip('"').strip("“”") for o in options if o and o.strip()]
    for o in clean:
        if not caption_problems(o, cfg, recent):
            return o, []
    if not clean:
        return "", ["멘트 생성 실패"]
    o = min(clean, key=len)
    return o, caption_problems(o, cfg, recent)
