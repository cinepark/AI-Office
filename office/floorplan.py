"""오피스 화면: 사무실 그림 한 장 위에 담당자 이름표, 벽 화면 상황판, 지시 흐름선.

좌표는 그림 크기 대비 % 입니다 (x = 머리 가로 위치, y = 머리 꼭대기 높이).
그림을 바꾸면 SEATS 좌표와 BOARD 위치만 고치면 됩니다.
"""
from __future__ import annotations

import base64
import datetime as dt
import html
from pathlib import Path

from .staff import KST, STAFF_BY_ID

STATIC = Path(__file__).resolve().parent.parent / "static"
OFFICE_IMG = "office.jpg"
CINEPARK_IMG = "cinepark_room.jpg"

# 담당자 id: (x%, y%, 이름표 위치 'up'=머리 위 | 'right'=머리 오른쪽)
SEATS = {
    "moon": (72.7, 12.6, "up"),
    "shiho": (34.3, 23.2, "up"),
    "research": (55.6, 25.4, "up"),
    "writer": (66.8, 25.4, "up"),
    "image": (74.6, 25.6, "right"),
    "design": (15.0, 39.6, "up"),
    "dev": (26.2, 39.6, "up"),
    "security": (38.4, 39.8, "up"),
    "video": (56.4, 43.6, "up"),
    "review": (70.6, 39.8, "up"),
    "channel": (81.0, 40.0, "right"),
    "strategy": (24.2, 63.2, "up"),
}
BOARD = (13.2, 8.1, 23.7, 18.8)  # 벽 화면 (왼쪽, 위, 오른쪽, 아래) %
LABEL = {"working": "작업 중", "done": "완료", "error": "문제", "idle": "대기"}


def _b64(name: str) -> str:
    return base64.b64encode((STATIC / name).read_bytes()).decode()


def _ago(iso: str) -> str:
    t = dt.datetime.fromisoformat(iso)
    m = int((dt.datetime.now(KST) - t).total_seconds() // 60)
    return "방금" if m < 1 else f"{m}분 전" if m < 60 else f"{m // 60}시간 전" if m < 1440 else t.strftime("%m/%d")


def _short(sid: str) -> str:
    if sid == "moon":
        return "Mr. MOON"
    return STAFF_BY_ID[sid][1].replace(" 담당", "").replace("·편집", "")


def _status(now: dict | None) -> str:
    if not now:
        return "idle"
    st = now["status"]
    # 작업 중 표시가 3시간 넘게 남아 있으면 멈춘 것으로 보고 대기로 표시
    if st == "working" and (dt.datetime.now(KST) - dt.datetime.fromisoformat(now["t"])).total_seconds() > 10800:
        return "idle"
    return st


def _tag(sid: str, x: float, y: float, side: str, now: dict | None) -> str:
    if sid == "moon":
        cls, head, tip = "boss", "대표", "Mr. MOON · 대표"
    else:
        cls = _status(now)
        head = LABEL[cls]
        tip = f"{STAFF_BY_ID[sid][2]} · {now['text']}" if now else STAFF_BY_ID[sid][4]
    return (f"<div class='tag {cls} {side}' style='left:{x}%;top:{y}%' title='{html.escape(tip)}'>"
            f"<i></i><b>{html.escape(_short(sid))}</b><span>{head}</span></div>")


def _board(state: dict, slots: list[dict]) -> str:
    q = state.get("queue", {})
    now = dt.datetime.now(KST)
    today = now.date().isoformat()
    posted = sum(1 for k, v in q.items() if k.startswith(today) and v.get("status") == "posted")
    ready = sorted(k for k, v in q.items() if v.get("status") == "ready" and k >= f"{today}_{now:%H%M}")
    nxt = f"{ready[0][-4:-2]}:{ready[0][-2:]} {'고양이' if q[ready[0]]['kind'] == 'cat' else '여행'}" if ready else "재고 없음"
    l, t, r, b = BOARD
    return (f"<div class='board' style='left:{l}%;top:{t}%;width:{r - l}%;height:{b - t}%'>"
            f"<div><small>다음</small><b>{nxt}</b></div>"
            f"<div><small>오늘</small><b>{posted}/{len(slots)}</b><small>재고</small><b>{len(ready)}</b></div></div>")


def _lines(now: dict) -> str:
    """SHIHO 자리에서 지금 작업 중인 담당자 자리까지 빛나는 선."""
    sx, sy, _ = SEATS["shiho"]
    out = []
    for sid, (x, y, _) in SEATS.items():
        if sid in ("shiho", "moon") or _status(now.get(sid)) != "working":
            continue
        out.append(f"<line x1='{sx}' y1='{sy + 4}' x2='{x}' y2='{y + 4}'/>")
    return f"<svg class='flow' viewBox='0 0 100 100' preserveAspectRatio='none'>{''.join(out)}</svg>" if out else ""


def render(state: dict, slots: list[dict] | None = None) -> str:
    slots = slots or [{}] * 4
    now = state.get("agent_now", {})
    tags = "".join(_tag(sid, x, y, side, now.get(sid)) for sid, (x, y, side) in SEATS.items())

    c = now.get("cinepark")
    cst = _status(c)
    cine = (f"<div class='room'><img src='data:image/jpeg;base64,{_b64(CINEPARK_IMG)}'>"
            f"<div class='rt'><div class='rh'>CINEPARK 블로그실 <span class='st {cst}'>{LABEL[cst] if c else '준비 중'}</span></div>"
            f"<div class='rn'>영화잡지형 기획기사 · 정보</div>"
            f"<p>{html.escape(c['text'] if c else STAFF_BY_ID['cinepark'][4])}</p></div></div>")

    cards = []
    for sid in [s for s in SEATS if s != "moon"] + ["cinepark"]:
        n = now.get(sid)
        stt = _status(n)
        cards.append(f"<div class='card'><div><i class='d {stt}'></i><b>{html.escape(STAFF_BY_ID[sid][1])}</b>"
                     f"<small>{_ago(n['t']) if n else ''}</small></div>"
                     f"<p>{html.escape(n['text'] if n else STAFF_BY_ID[sid][4])}</p></div>")

    feed = []
    for e in reversed(state.get("agent_log", [])[-8:]):
        feed.append(f"<li><time>{e['t'][11:16]}</time><b>{html.escape(STAFF_BY_ID.get(e['agent'], (0, e['agent']))[1])}</b>"
                    f"<span>{html.escape(e['text'])}</span></li>")

    return f"""<!doctype html><meta charset='utf-8'><style>
body{{margin:0;font-family:Paperlogy,'Apple SD Gothic Neo','Noto Sans KR',sans-serif;color:#142C3C;background:transparent}}
.pic{{position:relative;border-radius:14px;overflow:hidden;border:1px solid #C8D6DD}} .pic>img{{width:100%;display:block}}
.flow{{position:absolute;inset:0;width:100%;height:100%;pointer-events:none}}
.flow line{{stroke:#fffbe8;stroke-width:3.5;filter:drop-shadow(0 0 3px #DBA12C) drop-shadow(0 0 2px #0F3B59);vector-effect:non-scaling-stroke;stroke-dasharray:8 6;stroke-linecap:round;animation:fl 1s linear infinite}}
@keyframes fl{{to{{stroke-dashoffset:-14}}}}
.tag{{position:absolute;display:flex;align-items:center;gap:.35vw;white-space:nowrap;background:#ffffffee;border:1px solid #0F3B59;
border-radius:999px;padding:.25vw .7vw;font-size:clamp(9px,1.05vw,13px);line-height:1.2;box-shadow:0 1px 4px #0F3B5926;cursor:default}}
.tag.up{{transform:translate(-50%,-100%)}} .tag.right{{transform:translate(18%,-50%)}}
.tag b{{font-weight:700;color:#0F3B59}} .tag span{{color:#5b7486;font-size:.86em}}
.tag i{{width:.55vw;height:.55vw;min-width:6px;min-height:6px;border-radius:50%;background:#C8D6DD}}
.tag.working i{{background:#DBA12C;animation:p 1.2s infinite}} .tag.done i{{background:#2fbf71}} .tag.error i{{background:#e5484d}}
.tag.error{{border-color:#e5484d}} .tag.idle{{opacity:.85}} .tag.boss{{background:#0F3B59}} .tag.boss b{{color:#fff}} .tag.boss span{{color:#DBA12C}}
.tag.boss i{{background:#DBA12C}}
@keyframes p{{50%{{box-shadow:0 0 0 .35vw #DBA12C55}}}}
.board{{position:absolute;display:flex;flex-direction:column;justify-content:center;gap:.3vw;padding:0 .8vw;box-sizing:border-box;color:#F7FBFC;
font-size:clamp(8px,.95vw,12px)}}
.board div{{display:flex;align-items:baseline;gap:.4vw}} .board small{{color:#9fb4c2}} .board b{{color:#DBA12C;font-weight:800;margin-right:.6vw}}
.room{{display:flex;gap:12px;margin:12px 0;border:1px solid #C8D6DD;border-radius:14px;overflow:hidden;background:#F7FBFC}}
.room img{{width:38%;object-fit:cover;display:block}} .rt{{padding:10px 12px 10px 0}} .rh{{font-weight:800;color:#0F3B59}}
.rn{{font-size:.8rem;color:#5b7486;margin:2px 0 6px}} .room p{{margin:0;font-size:.86rem}}
.st{{font-size:.72rem;font-weight:600;color:#8aa0ae;margin-left:4px}} .st.working{{color:#b8860b}} .st.error{{color:#e5484d}} .st.done{{color:#2fbf71}}
.grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(190px,1fr));gap:8px;margin-bottom:12px}}
.card{{border:1px solid #C8D6DD;border-radius:12px;padding:8px 10px;background:#fff}} .card b{{font-size:.84rem;color:#0F3B59}}
.card small{{float:right;font-size:.68rem;color:#8aa0ae}} .card p{{margin:4px 0 0;font-size:.78rem;color:#3d5566;
overflow:hidden;display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical}}
.d{{display:inline-block;width:8px;height:8px;border-radius:50%;margin-right:6px;background:#C8D6DD}}
.d.working{{background:#DBA12C}} .d.done{{background:#2fbf71}} .d.error{{background:#e5484d}}
ul{{list-style:none;padding:0;margin:0;border-top:1px solid #C8D6DD}}
li{{display:flex;gap:10px;padding:7px 2px;border-bottom:1px solid #eef3f5;font-size:.84rem;align-items:baseline}}
li time{{color:#8aa0ae;font-variant-numeric:tabular-nums}} li b{{white-space:nowrap;color:#0F3B59}} li span{{color:#3d5566}}
</style>
<div class='pic'><img src='data:image/jpeg;base64,{_b64(OFFICE_IMG)}'>{_lines(now)}{_board(state, slots)}{tags}</div>
{cine}<div class='grid'>{''.join(cards)}</div>
<ul>{''.join(feed) or '<li><span>아직 활동 기록이 없습니다.</span></li>'}</ul>"""
