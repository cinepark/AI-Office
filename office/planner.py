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
    recent_scenes = [h.get("scene") for h in cats[-24:]]  # 장면 40개 중 최근 24개(약 12일)는 쉬게 함

    breeds = [b for b in cfg["breeds"] if b["id"] != last_breed] or cfg["breeds"]
    scenes = [s for s in cfg["scenes"] if today.month in s.get("months", range(1, 13))] or cfg["scenes"]  # 계절 장면은 그 달에만
    # 장면 묶음(group) 쉬게 하기: 직전 3편과 같은 묶음 금지, '숨기·들어가기(inside)'는 최근 6편에 한 번만
    gmap = {sc["id"]: sc.get("group") for sc in cfg["scenes"]}
    recent_groups = [gmap.get(h.get("scene")) for h in cats[-6:]]
    blocked = set(g for g in recent_groups[-3:] if g)
    if "inside" in recent_groups:
        blocked.add("inside")
    fresh = [sc for sc in scenes if sc.get("group") not in blocked]
    scenes = fresh or scenes
    candidates = [(b, s) for b in breeds for s in scenes
                  if (b["id"], s["id"]) not in recent_pairs and s["id"] not in recent_scenes]
    if not candidates:
        candidates = [(b, s) for b in breeds for s in scenes if (b["id"], s["id"]) not in recent_pairs]
    if not candidates:
        candidates = [(b, s) for b in breeds for s in scenes]
    return rng.choice(candidates)


CAT_VIEWS = [
    "Close-up at the cat's eye level.",
    "Seen from directly above.",
    "Low angle from the floor.",
    "Wide view showing the whole room around the cat.",
    "Side view with the cat small on the right third of the frame.",
    "Three-quarter view from the left.",
]
CAT_TIMES = ["Morning light.", "Bright afternoon light.", "Evening lamp light.", "Soft grey light of a cloudy day."]


def cat_prompt(cfg: dict, breed: dict, scene: dict, rng: random.Random | None = None) -> str:
    """같은 장면이 다시 나와도 같은 그림이 되지 않도록 시점·시간대를 무작위로 바꾼다."""
    rng = rng or random.Random()
    return (f"Match the drawing style of the attached reference images. "
            f"{breed['look'][0].upper() + breed['look'][1:]} {scene['text']}. "
            f"{rng.choice(CAT_VIEWS)} {rng.choice(CAT_TIMES)} "
            + ("No human face appears anywhere in the frame. " if "person" in scene["text"] else "")
            + cfg["style"])


def pick_travel(photos: list[dict], history: list[dict], used_ids: set[str],
                rng: random.Random | None = None, k: int = 1) -> dict | list[dict] | None:
    """photos: [{id, name, city, year}] — 원본 사진 목록. k>1 이면 같은 도시의 후보 k장을 돌려준다."""
    rng = rng or random.Random()
    fresh = [p for p in photos if p["id"] not in used_ids]
    if not fresh:
        return None
    travels = [h for h in history if h.get("kind") == "travel"]
    # 도시 한 바퀴 돌기: 가장 오래전에 나온 도시(한 번도 안 나온 도시가 맨 먼저)부터 차례로
    last_seen = {}
    for i, h in enumerate(travels):
        last_seen[(h.get("city") or "").lower()] = i
    cities = sorted({p["city"] for p in fresh})
    oldest = min(last_seen.get(c.lower(), -1) for c in cities)
    turn = [c for c in cities if last_seen.get(c.lower(), -1) == oldest]
    city = rng.choice(turn)
    pool = fresh
    same = [p for p in pool if p["city"] == city]
    if k <= 1:
        return rng.choice(same)
    return rng.sample(same, min(k, len(same)))


def parse_city_folder(name: str) -> tuple[str, str]:
    """'2006 Barcelona' → ('Barcelona', '2006'), 'LONDON' → ('LONDON', ''),
    여러 도시를 묶은 폴더: 'Osaka_Kyoto' → ('Osaka · Kyoto', ''), '2016 PragueDresdenVienBudapest' → ('Prague · Dresden · Vien · Budapest', '2016')"""
    name = re.sub(r"\s*[(\[][^)\]]*[)\]]\s*", " ", name).strip()  # 'Italy (미분류)' → 'Italy': 괄호 안 메모는 무시
    m = re.match(r"^\s*(\d{4})\s+(.+)$", name)
    city, year = (m.group(2).strip(), m.group(1)) if m else (name.strip(), "")
    parts = [p for p in re.split(r"[_,/&+]+|\s{2,}", city) if p.strip()]
    out = []
    for p in parts:  # 붙여 쓴 대문자 이름(PragueDresden)을 나눈다. 전부 대문자(LONDON)는 그대로
        out += re.findall(r"[A-Z][a-z]+|[a-z]+|[A-Z]+(?![a-z])|[^A-Za-z]+", p.strip()) if not p.isupper() else [p.strip()]
    out = [o.strip() for o in out if o.strip()]
    return (" · ".join(out) if len(out) > 1 else city), year


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
