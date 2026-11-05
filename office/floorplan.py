"""오피스 건물 화면: 층 그림 위, 각 담당자 자리에 '지금 하는 일' 말풍선.

좌표는 그림 크기 대비 % (x=말풍선 꼬리가 가리키는 머리 위치, y=그 높이).
그림을 바꾸면 이 좌표만 고치면 됩니다.
"""
from __future__ import annotations

import base64
import datetime as dt
import html
from pathlib import Path

from .staff import KST, STAFF_BY_ID

STATIC = Path(__file__).resolve().parent.parent / "static"

FLOORS = [
    {"id": "f1", "img": "floor01.jpg", "title": "01 총괄 · IT · 보안", "seats": {
        "shiho": (31, 49), "design": (45, 33), "dev": (44, 55), "security": (44, 76)}},
    {"id": "f2", "img": "floor02.jpg", "title": "02 콘텐츠 제작 · 채널 운영", "seats": {
        "research": (14, 34), "writer": (44, 19), "image": (66, 22),
        "video": (14, 62), "review": (45, 41), "channel": (70, 60)}},
]
ROOMS = [  # 그림 없는 방 (상태 카드)
    ("cinepark", "CINEPARK 블로그실"), ("strategy", "전략실"),
]
LABEL = {"working": "작업 중", "done": "완료", "error": "문제", "idle": "대기"}


def _b64(name: str) -> str:
    return base64.b64encode((STATIC / name).read_bytes()).decode()


def _ago(iso: str) -> str:
    t = dt.datetime.fromisoformat(iso)
    m = int((dt.datetime.now(KST) - t).total_seconds() // 60)
    return "방금" if m < 1 else f"{m}분 전" if m < 60 else f"{m // 60}시간 전" if m < 1440 else t.strftime("%m/%d")


def _bubble(sid: str, x: float, y: float, now: dict | None) -> str:
    status = now["status"] if now else "idle"
    text = now["text"] if now else STAFF_BY_ID[sid][4]
    head = f"{LABEL[status]} · {_ago(now['t'])}" if now else "대기"
    side = "r" if x > 60 else "l"
    return (f"<div class='bub {status} {side}' style='left:{x}%;top:{y}%' title='{html.escape(text)}'>"
            f"<div class='h'><i></i>{html.escape(STAFF_BY_ID[sid][1])} · {head}</div>"
            f"<div class='t'>{html.escape(text)}</div></div>")


def render(state: dict) -> str:
    now = state.get("agent_now", {})
    floors = []
    for f in FLOORS:
        bubbles = "".join(_bubble(sid, x, y, now.get(sid)) for sid, (x, y) in f["seats"].items())
        working = any((now.get(s) or {}).get("status") == "working" for s in f["seats"])
        floors.append(f"<section class='floor'><div class='tag'>{f['title']} <span>{'일하는 중' if working else '켜져 있어요'}</span></div>"
                      f"<div class='pic'><img src='data:image/jpeg;base64,{_b64(f['img'])}'>{bubbles}</div></section>")
    rooms = []
    for sid, name in ROOMS:
        n = now.get(sid)
        st = n["status"] if n else "idle"
        rooms.append(f"<div class='room'><b>{name}</b> <span class='st {st}'>{LABEL[st] if n else '준비 중'}</span>"
                     f"<p>{html.escape(n['text'] if n else STAFF_BY_ID[sid][4])}</p></div>")
    feed = []
    for e in reversed(state.get("agent_log", [])[-10:]):
        feed.append(f"<li><time>{e['t'][11:16]}</time><b>{html.escape(STAFF_BY_ID.get(e['agent'], (0, e['agent']))[1])}</b>"
                    f"<span>{html.escape(e['text'])}</span></li>")
    return f"""<!doctype html><meta charset='utf-8'><style>
body{{margin:0;font-family:Paperlogy,'Apple SD Gothic Neo','Noto Sans KR',sans-serif;color:#191970;background:transparent}}
.floor{{margin:0 0 14px;border:2px solid #191970;border-radius:14px;overflow:hidden;background:#fff}}
.tag{{font-weight:700;padding:8px 12px;border-bottom:2px solid #191970;background:#f9f9fd}}
.tag span{{font-weight:400;color:#8a8aa3;font-size:.8rem;margin-left:6px}}
.pic{{position:relative}} .pic img{{width:100%;display:block}}
.bub{{position:absolute;transform:translate(-50%,-100%);max-width:23%;min-width:120px;background:#fff;border:1.5px solid #191970;
border-radius:12px;padding:5px 9px;box-shadow:0 2px 6px #19197022;font-size:clamp(10px,1.1vw,13px);line-height:1.3}}
.bub:after{{content:'';position:absolute;left:50%;bottom:-7px;width:10px;height:10px;background:#fff;border-right:1.5px solid #191970;
border-bottom:1.5px solid #191970;transform:translateX(-50%) rotate(45deg)}}
.bub .h{{font-weight:700;font-size:.82em;white-space:nowrap}} .bub .t{{overflow:hidden;display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical}}
.bub i{{display:inline-block;width:7px;height:7px;border-radius:50%;margin-right:5px;vertical-align:middle;background:#c9c9d6}}
.bub.working i{{background:#ffcb05;animation:p 1.2s infinite}} .bub.done i{{background:#2fbf71}} .bub.error i{{background:#e5484d}}
.bub.error{{border-color:#e5484d}} .bub.idle{{opacity:.78}}
@keyframes p{{50%{{box-shadow:0 0 0 5px #ffcb0544}}}}
.rooms{{display:grid;grid-template-columns:1fr 1fr;gap:10px;margin-bottom:14px}}
.room{{border:2px solid #191970;border-radius:14px;padding:10px 12px;background:#fff}} .room p{{margin:6px 0 0;font-size:.85rem;color:#2b2b45}}
.st{{font-size:.75rem;color:#8a8aa3}} .st.working{{color:#b38900}} .st.error{{color:#e5484d}} .st.done{{color:#2fbf71}}
ul{{list-style:none;padding:0;margin:0;border-top:1px solid #e6e6f0}}
li{{display:flex;gap:12px;padding:9px 2px;border-bottom:1px solid #f0f0f6;font-size:.9rem;align-items:baseline}}
li time{{color:#8a8aa3;font-variant-numeric:tabular-nums}} li b{{white-space:nowrap}} li span{{color:#55557a}}
</style>{''.join(floors)}<div class='rooms'>{''.join(rooms)}</div><ul>{''.join(feed) or '<li><span>아직 활동 기록이 없습니다.</span></li>'}</ul>"""
