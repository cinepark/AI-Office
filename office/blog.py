"""네이버 블로그 글감 패키지: CINEPARK(영화잡지형) · 리뷰&리뷰(쿠팡 정보형).

흐름: 리서치 담당(웹 검색으로 글감 3개) → 작가 담당(원고) → 이미지 담당(그림) → 검수 담당(점검)
결과는 R2 에 패키지로 보관되고, 데스크에서 본문 복사·그림 받기로 가져가 Mr. MOON 이 직접 올립니다.

실행 방식 두 가지
- 예약: 매일 21:00 재고 채우기 때, 다음 날이 예약 요일이면 그날 패키지를 미리 만든다.
- 실시간: 데스크의 '지금 만들기' 버튼 또는 SHIHO 지시 → 화면 서버에서 바로 만든다.
"""
from __future__ import annotations

import datetime as dt
import io
import json
import re
import threading
import zipfile

from .staff import KST, act

BSTATE_KEY = "blog/state.json"
STATIC = __import__("pathlib").Path(__file__).resolve().parent.parent / "static"
_lock = threading.Lock()

# ───────────────────────── 작법 ─────────────────────────
CINEPARK_RESEARCH = """당신은 네이버 영화 블로그 CINEPARK 의 리서치 담당입니다. 영화잡지형 포스팅의 글감을 찾습니다.

글감 기준 (Mr. MOON 이 정한 기준)
- 반드시 '영화'와 관련된 이야기. 그중에서도 사람들이 끌리는 세 가지 고리 중 하나가 있어야 한다:
  돈(제작비·투자·흥행 수익·배우 출연료·인수합병·해외 자본) / 셀럽(배우·감독의 행보·캐스팅·발언·논란) / 뒷얘기(제작 비하인드·갈등·숨은 사연·기록).
- 기준이 되는 글감: "중동의 돈이 한국 콘텐츠로 온다? 두바이·아부다비·사우디의 서로 다른 속셈"
  → 세계 영화계에서 벌어지는 일을 한국 독자가 바로 궁금해할 한 줄 질문으로 바꾼 것. 두바이 머니, 한국 영화, 실제로 들어오나? 처럼
  '누가 · 무엇이 · 한국 영화(관객)와 어떻게 연결되나'가 질문 하나에 들어 있다.
- 기사 한 건을 옮기는 주제는 안 된다. 서로 다른 매체·기관 자료 2곳 이상을 엮어야 답이 나오는 질문만 고른다.
- 최근 2주 안의 뉴스나 지금 진행 중인 이슈에서 찾는다. 웹 검색으로 사실과 출처를 확인한다.
- 사실마다 상태를 구분한다: 확정(공식 발표·계약 완료) / 보도(매체 보도) / 협상(논의·검토) / 소문.
{hint}
후보 3개를 '기준 글감과 얼마나 닮았나' 순서로 정렬해서, 가장 좋은 것을 맨 앞에 둔다.

JSON 만 출력:
{{"topics": [{{"axis": "돈|셀럽|뒷얘기", "format": "기획기사|정보", "question": "한 줄 질문 (예: 중동의 돈이 한국 영화로 온다?)",
 "title_idea": "제목 아이디어 (질문 + 부제)", "hook_question": "도입 끝에 던질 질문", "why_now": "지금 써야 하는 이유",
 "korea_link": "한국 영화·관객과의 연결고리", "first_line": "첫 줄로 쓸 숫자·이름·장면 한 마디",
 "facts": [{{"text": "사실 한 줄", "status": "확정|보도|협상|소문", "source": "매체·기관명", "url": "주소"}}],
 "related_companies": ["관련 상장사 이름"]}}]}}"""

CINEPARK_WRITE = """당신은 네이버 영화 블로그 CINEPARK 의 작가입니다. 영화잡지 기획기사처럼 씁니다.

이 블로그의 실제 글 (구성과 말투를 그대로 따른다)
제목: 중동의 돈이 한국 콘텐츠로 온다? 두바이·아부다비·사우디의 서로 다른 속셈
261억 원.
지난 9월 말 두바이에서 열린 한국 콘텐츠 행사에서 오간 비즈니스 상담 규모입니다. 한국 기업 16곳과 현지 바이어 53곳이 만나 241건을 상담했습니다. 한국콘텐츠진흥원 발표
꽤 큰 숫자입니다. 그런데 한 가지는 분명히 해야 합니다. 261억 원이 한국 콘텐츠에 투자됐다는 뜻은 아닙니다. 유통과 공동제작, 라이선스와 투자 등을 놓고 논의한 금액입니다.
그렇다면 중동과 한국 콘텐츠 사이에서는 실제로 어떤 일이 벌어지고 있을까요?
[이미지 1: 썸네일]
소제목: 두바이·아부다비·사우디는 같은 곳이 아닙니다
소제목: 사우디는 실제로 한국 콘텐츠 기업에 투자했다
문단 예: 2023년 카카오엔터는 해외 국부펀드로부터 총 1조 2천억 원의 투자를 유치했다고 발표했습니다. (…) 카카오엔터 발표 · 연합뉴스 보도
문단 예: 여기서도 주의할 점이 있습니다. 1조 2천억 원 전부가 사우디 돈은 아니고, 특정 영화 한 편의 제작비도 아닙니다.
소제목: 콘텐츠를 사는 것과 회사에 투자하는 것도 다르다
소제목: 그렇다면 왜 한국일까?  (문단 끝: 이것은 여러 발표를 연결한 해석이지, 모든 투자자의 공식적인 이유는 아닙니다.)
소제목: CINEPARK의 한 줄 정리  (핵심 질문 한 줄: 누가, 어디에, 어떤 방식으로 돈을 쓰는가?)

작법 7원칙
1. 첫 줄은 숫자·이름·장면처럼 눈에 걸리는 한 마디로 짧게 끊고, 도입 끝은 독자가 궁금해할 질문으로 맺는다. 썸네일은 그 질문 바로 뒤.
2. 서로 다른 매체·기관의 자료 여러 건을 엮어 하나의 이야기로 만든다. 기사 한 건을 번역하듯 옮기지 않는다.
3. 사실과 해석을 구분한다. 상담·논의·협약·계약·실제 투자를 섞지 않고 상태 그대로 쓴다. 큰 숫자 뒤에는 '그 숫자가 뜻하지 않는 것'을 짚는다.
   출처는 문단 끝에 'OO 발표', 'OO 보도', 'OO 발표 · OO 보도' 형식으로 붙인다.
4. 제작자의 시선으로 쉽게 풀어 쓴다. ~입니다/~습니다 체. 소제목은 주장하는 문장으로. 지어낸 인용·숫자 금지. 해석은 해석이라고 밝힌다.
5. 돈·셀럽·뒷얘기 중 이 글의 축을 끝까지 밀고 간다.
6. 그림은 내용을 설명하는 AI 재구성 장면이다(끝에 고지 문구를 넣는다).
7. 끝에 관련 기업·종목을 정리하되 매수·매도를 권하지 않는다. 상장사만, 시장과 종목코드 포함. 비상장사·펀드는 종목으로 쓰지 않고 그 사실을 밝힌다.

형식
- 제목: 가운데 정렬로 쓸 한 줄, '…온다? …' 처럼 질문과 부제가 이어지는 형태, 40자 안팎.
  글감의 question(한 줄 질문)을 제목 앞부분에 살리고, 글감의 first_line 을 본문 첫 줄로 쓴다. 글 전체가 그 질문에 답하는 구조여야 한다.
- 썸네일 문구: thumb_title 은 두 줄(줄마다 10자 안팎, 줄바꿈 \n), thumb_highlight 는 그중 노란색으로 강조할 한 단어(예: 돈).
- 본문 2,500~3,500자, 소제목 5~6개(마지막은 'CINEPARK의 한 줄 정리').
- 그림 {n}장: 0번 썸네일, 1~{last}번은 본문 사이 {{"type": "image", "no": 번호}}. 캡션은 '[이미지 2: 아부다비]'처럼 짧은 장소·주제어.
- 그림 prompt 는 영어 한 단락, 사진 한 장을 단정적으로 묘사(한 상태, 한 동작). 'or', 'maybe', 'slightly' 같은 말 금지.
  모든 그림에 블로그 캐릭터 한 사람만 넣는다: {character}.
  그녀가 뉴스 상황 속에서 한 동작을 하는 장면(예: 두바이 야경이 보이는 회의실 창가에 서서 태블릿을 든 모습, 사우디 촬영장 세트 앞에 선 모습, 서울 야경 앞 책상에서 자료를 확인하는 모습).
  남자는 어떤 그림에도 절대 넣지 않는다. 그녀 외의 사람은 그리지 않는다(군중·배우·감독·사업가 모두 금지). 그림 prompt 마다 'She is the only person in the frame.' 를 넣는다.
  썸네일은 화면 위쪽 가운데(위에서 1/2 까지)를 밤하늘처럼 단순하게 비운다(제목 글자를 가운데에 얹음). 그녀는 화면 가운데 아래쪽에 상반신이 보이게 둔다.
  책상은 단순하게: 노트북 한 대와 컵 하나만. 필름 릴·클래퍼보드·서류 더미 같은 소품을 늘어놓지 않는다.
  실내 장면은 남산서울타워가 보이는 서울 야경 큰 창을 배경으로 하는 것을 기본으로 한다.
  6장의 장소·구도·동작이 서로 겹치지 않게 한다. 실존 인물·로고·글자·숫자는 그림에 넣지 않는다. 16:9 가로 구도, 화려한 야경과 따뜻한 조명.
- 관련 종목 reason 은 이 글과의 관계 한두 문장. stock_note 에 비상장사·펀드 안내와 '사업 관련성이 곧 주가 상승이나 투자 수익을 뜻하지는 않습니다.'를 쓴다.

JSON 만 출력:
{{"title": "...", "thumb_title": "첫 줄\n둘째 줄", "thumb_highlight": "...",
 "blocks": [{{"type": "p", "text": "261억 원."}}, {{"type": "p", "text": "..."}}, {{"type": "image", "no": 0}}, {{"type": "h", "text": "소제목"}}, {{"type": "p", "text": "..."}}, {{"type": "image", "no": 1}}],
 "images": [{{"no": 0, "role": "썸네일", "prompt": "...", "caption": "[이미지 1: 썸네일]"}}],
 "stocks": [{{"name": "...", "market": "코스피|코스닥|NASDAQ|NYSE|Tadawul|...", "code": "...", "reason": "..."}}], "stock_note": "...",
 "sources": [{{"title": "...", "url": "..."}}], "tags": ["...", "CINEPARK"]}}"""

REVIEW_RESEARCH = """당신은 네이버 블로그 '리뷰&리뷰'의 리서치 담당입니다.
이 블로그는 고양이 돌봄, 생활용품, 계절 살림의 '고르는 법 · 관리법 · 안전 수칙'을 제조사·보호단체·공공기관 안내로 정리합니다.
(지난 글 예: 고양이 겨울 잠자리, 담요보다 먼저 살펴볼 위치와 높이 / 경량패딩 세탁 전 확인할 것 / 난방텐트 고르는 법 / 전기매트 vs 온수매트)

웹 검색으로 오늘 날짜 기준 계절·날씨·행사에 맞춰 지금 사람들이 많이 찾는 주제 3개를 제안합니다.
- 세 주제 중 하나는 고양이 돌봄 주제로 합니다.
- 근거가 되는 공식 안내(제조사 설명서, 보호단체, 공공기관)를 실제로 찾은 주제만 고릅니다.
{hint}{avoid}
JSON 만 출력:
{{"topics": [{{"axis": "고양이|생활용품|살림", "title_idea": "...", "hook_question": "...", "why_now": "...",
 "criteria": ["확인할 점"], "facts": [{{"text": "...", "source": "기관·제조사명", "url": "..."}}], "buy_related": true}}]}}"""

REVIEW_WRITE = """당신은 네이버 블로그 '리뷰&리뷰'의 작가입니다.

이 블로그의 실제 글 (구성과 말투를 그대로 따른다)
제목: 고양이 겨울 잠자리, 담요보다 먼저 살펴볼 위치와 높이
[그림: 고양이 겨울 잠자리]
고양이의 겨울 잠자리를 준비할 때, 새 방석을 고르기 전에 지금 쉬는 자리를 살펴보세요. 바람이 들어오는지, 편하게 올라갈 수 있는지부터 확인하면 준비할 것이 조금 더 분명해집니다.
[그림: 외풍 없는 위치]
잠자리의 첫 조건은 외풍 없는 위치
고양이 보호단체 Cats Protection은 따뜻하고 편안하며 외풍이 없는 실내 휴식 공간을 권합니다. 방석을 놓을 후보 자리를 정했다면 창문이나 문틈에서 찬바람이 직접 닿는지 확인해보세요.
[그림: 쉽게 오르는 낮은 계단]
높이도 편안함의 일부예요
(…)
출처: Cats Protection의 고양이 겨울철 돌봄 안내 (주소)
오늘 밤 확인할 세 가지
□ 잠자리에 외풍이 직접 들어오지 않나요?
□ 고양이가 무리하게 뛰지 않고 접근할 수 있나요?
□ 물과 화장실까지 편하게 이동할 수 있나요?
잠자리 환경을 바꾸는 일과 몸 상태를 살피는 일은 함께 가야 합니다.

규칙
- 구성: 썸네일 그림 → 도입 문단 → (그림 → 소제목 → 문단) 4~5번 → 출처 → '오늘 ~ 확인할 세 가지' □ 체크리스트 3개 → 마무리 한 문단.
- 1,100~1,800자. 존댓말(~요/~습니다 섞어도 됨). 직접 써 본 것처럼 꾸미지 않고, 근거는 문장 안에 기관·제조사 이름으로 밝힌다. 지어낸 숫자·후기 금지.
- 아픈 증상이 의심되면 수의사·전문가 상담을 권하는 한 줄을 넣는다(고양이 주제).
- 구매와 관련된 주제일 때만 쿠팡 링크 자리 {{"type": "link", "text": "[쿠팡 링크: 상품군]"}} 를 1~2곳 넣고,
  그때는 맨 첫 블록을 이 문장 그대로 둔다: "이 포스팅은 쿠팡 파트너스 활동의 일환으로, 이에 따른 일정액의 수수료를 제공받습니다."
- 그림 {n}장. 0번은 썸네일, 1~{last}번은 본문. 그림마다 label(그림 위에 얹을 글자, 띄어쓰기 포함 12자 이내, 예: '외풍 없는 위치')을 정한다.
  0번 label 은 글 주제(예: '고양이 겨울 잠자리'). 본문 그림 label 은 바로 뒤 소제목의 핵심어.
- 그림 prompt 는 영어 한 단락, 사진 한 장을 단정적으로 묘사(한 상태, 한 동작). 고양이 주제면 고양이가 그 장면 속에서 한 동작을 하고,
  생활용품 주제면 그 물건이 놓인 집 안 장면. 화면 위쪽 1/4 은 글자를 얹을 수 있게 벽·하늘처럼 단순하게 비운다. 그림 속 글자·로고·숫자 금지.
- 태그 6개 안팎, 해시태그 없이 단어만.

JSON 만 출력:
{{"title": "...", "blocks": [{{"type": "image", "no": 0}}, {{"type": "p", "text": "도입"}}, {{"type": "image", "no": 1}}, {{"type": "h", "text": "소제목"}},
 {{"type": "p", "text": "..."}}, {{"type": "source", "text": "출처: 기관 안내 이름 (주소)"}}, {{"type": "h", "text": "오늘 밤 확인할 세 가지"}},
 {{"type": "check", "items": ["...", "...", "..."]}}, {{"type": "p", "text": "마무리"}}],
 "images": [{{"no": 0, "role": "썸네일", "label": "...", "prompt": "...", "caption": ""}}],
 "sources": [{{"title": "...", "url": "..."}}], "tags": ["...", "..."]}}"""

PROMPTS = {"cinepark": (CINEPARK_RESEARCH, CINEPARK_WRITE), "review": (REVIEW_RESEARCH, REVIEW_WRITE)}


# ───────────────────────── 보관 ─────────────────────────
def load() -> dict:
    from . import storage
    try:
        obj = storage._client().get_object(Bucket=storage._bucket(), Key=BSTATE_KEY)
        b = json.loads(obj["Body"].read().decode("utf-8"))
    except Exception as e:
        if "NoSuchKey" not in str(e) and "404" not in str(e):
            raise
        b = {}
    b.setdefault("packages", {})
    b.setdefault("schedule", {})
    b.setdefault("running", {})
    b.setdefault("images_made", {})
    return b


def save(b: dict) -> None:
    from . import storage
    storage.put_bytes(BSTATE_KEY, json.dumps(b, ensure_ascii=False, indent=1).encode("utf-8"), "application/json")


def schedule_of(b: dict, cfg: dict, blog: str) -> dict:
    d = b.get("schedule", {}).get(blog)
    if d is None:
        d = {"on": True, "days": cfg["blog"]["blogs"][blog]["schedule_days"]}
    return d


def _now() -> dt.datetime:
    return dt.datetime.now(KST)


def _log(agent: str, text: str, status: str) -> None:
    """사무실 활동 기록(Threads 와 같은 상태 파일)에 짧게 남긴다."""
    from . import storage
    try:
        st = storage.load_state()
        act(st, agent, text, status)
        storage.save_state(st)
    except Exception:
        pass


def _json(text: str) -> dict:
    m = re.search(r"\{.*\}", text or "", re.S)
    if not m:
        raise ValueError("JSON 응답을 찾지 못했습니다.")
    return json.loads(m.group(0))


def _ask(cfg: dict, system: str, user: str, search: bool) -> dict:
    from . import ai
    kw = {}
    if search:
        kw["tools"] = [{"type": "web_search", "search_context_size": "high",
                        "user_location": {"type": "approximate", "country": "KR", "timezone": "Asia/Seoul"}}]
    last = None
    for _ in range(2):  # JSON 이 깨지면 한 번 더
        r = ai._client().responses.create(model=cfg["openai"]["text_model"],
                                          input=[{"role": "system", "content": system},
                                                 {"role": "user", "content": user}], **kw)
        try:
            return _json(r.output_text)
        except (ValueError, json.JSONDecodeError) as e:
            last = e
    raise RuntimeError(f"응답 형식 오류: {last}")


# ───────────────────────── 단계 ─────────────────────────
def research(cfg: dict, blog: str, hint: str = "", avoid: list[str] | None = None) -> list[dict]:
    av = f"\n최근에 이미 쓴 글(같은 주제 피하기): {' / '.join(avoid[-20:])}\n" if avoid else ""
    fmt = {"hint": f"\nMr. MOON 지정 주제: {hint} (이 주제를 중심으로 세 글감을 고른다)\n" if hint else ""}
    if "{avoid}" in PROMPTS[blog][0]:
        fmt["avoid"] = av
    else:
        fmt["hint"] += av
    sys_r = PROMPTS[blog][0].format(**fmt)
    data = _ask(cfg, sys_r, f"오늘은 {_now():%Y년 %m월 %d일}입니다. 글감 3개를 찾아 주세요.", search=True)
    return data.get("topics", [])[:3]


def write(cfg: dict, blog: str, topic: dict) -> dict:
    bc = cfg["blog"]["blogs"][blog]
    n = bc["images"]
    sys_w = PROMPTS[blog][1].format(n=n, last=n - 1, character=bc.get("character", "").strip())
    user = (f"오늘은 {_now():%Y년 %m월 %d일}입니다. 아래 글감으로 원고를 쓰세요. 필요하면 웹 검색으로 사실을 다시 확인하세요.\n"
            + json.dumps(topic, ensure_ascii=False))
    art = _ask(cfg, sys_w, user, search=True)
    art["images"] = sorted(art.get("images", []), key=lambda x: x.get("no", 0))[:n]
    return art


def check(blog: str, art: dict) -> list[str]:
    """검수 담당: 형식 점검 (내용 판단은 Mr. MOON)."""
    probs = []
    body = "".join(b.get("text", "") for b in art.get("blocks", []) if b.get("type") in ("p", "h"))
    if blog == "cinepark":
        if not 2000 <= len(body) <= 4500:
            probs.append(f"본문 {len(body)}자")
        if not art.get("stocks"):
            probs.append("관련 종목 없음")
        if len(art.get("sources", [])) < 2:
            probs.append("출처 2곳 미만")
    else:
        first = (art.get("blocks") or [{}])[0].get("text", "")
        has_link = any(bl.get("type") == "link" for bl in art.get("blocks", []))
        if has_link and "쿠팡 파트너스 활동의 일환" not in first:
            probs.append("쿠팡 링크가 있는데 대가성 문구가 첫 줄이 아님")
        if any(not im.get("label") for im in art.get("images", [])):
            probs.append("그림 글자(label) 빠짐")
    if not art.get("images"):
        probs.append("그림 계획 없음")
    return probs


def draw_images(cfg: dict, blog: str, pid: str, art: dict, b: dict) -> None:
    from . import ai, drive, storage
    bc = cfg["blog"]["blogs"][blog]
    refs = [drive.download(f) for f in bc.get("reference_files", [])]
    refs += [(STATIC / f).read_bytes() for f in bc.get("reference_local", [])]
    style = bc.get("image_style", "").strip()
    today = _now().date().isoformat()
    for im in art["images"]:
        if b["images_made"].get(today, 0) >= cfg["blog"]["daily_image_limit"]:
            im["error"] = "오늘 블로그 그림 상한 도달"
            continue
        _log("image", f"{bc['name']} 그림 {im['no'] + 1}/{len(art['images'])} 그리는 중", "working")
        try:
            prompt = im["prompt"] + (f" {style}" if style else "")
            png = ai.render(cfg, prompt, refs, cfg["blog"]["image_size"])
            if bc.get("labels") and im.get("label"):
                png = label(png, im["label"])
            elif blog == "cinepark":
                png = (cine_thumb(png, art["thumb_title"], art.get("thumb_highlight", ""))
                       if im["no"] == 0 and art.get("thumb_title") else crop169(png))
            ext = "jpg" if png[:3] == b"\xff\xd8\xff" else "png"
            key = f"blog/{blog}/{pid}/{im['no']:02d}.{ext}"
            storage.put_bytes(key, png, "image/jpeg" if ext == "jpg" else "image/png")
            im["r2_key"] = key
            b["images_made"][today] = b["images_made"].get(today, 0) + 1
        except Exception as e:
            im["error"] = str(e)[:200]
            _log("dev", f"{bc['name']} 그림 {im['no'] + 1} 실패: {str(e)[:120]}", "error")


def make_package(cfg: dict, blog: str, hint: str = "", topic: dict | None = None,
                 mode: str = "실시간", for_date: str | None = None) -> str:
    """글감 → 원고 → 그림 → 점검 → 보관. 패키지 id 를 돌려준다."""
    name = cfg["blog"]["blogs"][blog]["name"]
    pid = f"{blog}_{_now():%Y%m%d_%H%M%S}"
    with _lock:
        b = load()
        b["running"][blog] = {"t": _now().isoformat(timespec="seconds"), "step": "글감 찾는 중", "mode": mode}
        save(b)
    try:
        if topic is None:
            _log("research", f"{name} 글감 찾는 중" + (f" (지정: {hint[:20]})" if hint else ""), "working")
            prev = [p["article"].get("title", "") for p in sorted(load()["packages"].values(), key=lambda x: x["made"])
                    if p["blog"] == blog]
            topics = research(cfg, blog, hint, prev)
            if not topics:
                raise RuntimeError("글감을 찾지 못했습니다.")
            topic, others = topics[0], topics[1:]
            _log("research", f"{name} 글감 {len(topics)}개 → '{topic.get('title_idea', '')[:30]}'", "done")
        else:
            others = []
        _set_step(blog, "원고 쓰는 중")
        _log("writer", f"{name} 원고 쓰는 중: {topic.get('title_idea', '')[:30]}", "working")
        art = write(cfg, blog, topic)
        _log("writer", f"{name} 원고 완성: {art.get('title', '')[:30]}", "done")
        _set_step(blog, "그림 그리는 중")
        b = load()
        draw_images(cfg, blog, pid, art, b)
        probs = check(blog, art)
        _log("review", f"{name} 점검 {'통과' if not probs else '주의: ' + ', '.join(probs)}", "done" if not probs else "error")
        pkg = {"id": pid, "blog": blog, "mode": mode, "date": for_date or _now().date().isoformat(),
               "made": _now().isoformat(timespec="seconds"), "hint": hint, "topic": topic, "others": others,
               "article": art, "problems": probs, "status": "ready"}
        with _lock:
            b2 = load()
            b2["images_made"] = {**b2.get("images_made", {}), **b["images_made"]}
            b2["packages"][pid] = pkg
            b2["running"].pop(blog, None)
            save(b2)
        _log("shiho", f"{name} 패키지 준비 완료 → {name} 데스크", "done")
        return pid
    except Exception as e:
        with _lock:
            b3 = load()
            b3["running"].pop(blog, None)
            b3.setdefault("errors", []).append({"t": _now().isoformat(timespec="seconds"), "blog": blog, "error": str(e)[:300]})
            del b3["errors"][:-20]
            save(b3)
        _log("dev", f"{name} 패키지 실패: {str(e)[:150]}", "error")
        raise


def _set_step(blog: str, step: str) -> None:
    with _lock:
        b = load()
        if blog in b["running"]:
            b["running"][blog]["step"] = step
            save(b)


def start_background(cfg: dict, blog: str, hint: str = "", topic: dict | None = None) -> bool:
    """실시간 만들기: 화면 서버에서 따로 돌린다. 이미 만드는 중이면 False."""
    b = load()
    r = b["running"].get(blog)
    if r and (_now() - dt.datetime.fromisoformat(r["t"])).total_seconds() < 2400:
        return False
    th = threading.Thread(target=_safe, args=(cfg, blog, hint, topic), daemon=True)
    th.start()
    return True


def _safe(*args) -> None:
    try:
        make_package(*args)
    except Exception:
        pass


def scheduled(cfg: dict, target: dt.date) -> list[str]:
    """예약: target 날짜가 예약 요일이고 아직 그날 예약 패키지가 없으면 만든다."""
    b = load()
    out = []
    for blog in cfg["blog"]["blogs"]:
        sc = schedule_of(b, cfg, blog)
        if not sc.get("on") or target.weekday() not in sc.get("days", []):
            continue
        if any(p["blog"] == blog and p.get("mode") == "예약" and p.get("date") == target.isoformat()
               for p in b["packages"].values()):
            continue
        try:
            out.append(make_package(cfg, blog, mode="예약", for_date=target.isoformat()))
        except Exception as e:
            out.append(f"{blog} 실패: {e}")
    return out


def label(img: bytes, text: str) -> bytes:
    """그림 위쪽 가운데에 흰 글씨(Paperlogy ExtraBold) + 부드러운 그림자. 글자 높이는 그림 높이의 8% (예전 게시물의 약 2/3)."""
    from PIL import Image, ImageDraw, ImageFilter, ImageFont
    im = Image.open(io.BytesIO(img)).convert("RGBA")
    w, h = im.size
    size = int(h * 0.08)
    font = ImageFont.truetype(str(STATIC / "Paperlogy-8ExtraBold.woff2"), size)
    d0 = ImageDraw.Draw(im)
    words, lines, cur = text.split(), [], ""
    for wd in words:  # 그림 폭의 80% 를 넘으면 줄바꿈
        t = (cur + " " + wd).strip()
        if cur and d0.textlength(t, font=font) > w * 0.8:
            lines.append(cur)
            cur = wd
        else:
            cur = t
    lines.append(cur)
    lines = lines[:2]
    shadow = Image.new("RGBA", im.size, (0, 0, 0, 0))
    ds, top = ImageDraw.Draw(shadow), int(h * 0.075)
    pos = []
    for i, ln in enumerate(lines):
        tw = d0.textlength(ln, font=font)
        xy = ((w - tw) / 2, top + i * size * 1.22)
        pos.append((xy, ln))
        ds.text((xy[0] + 2, xy[1] + 3), ln, font=font, fill=(0, 0, 0, 170))
    im = Image.alpha_composite(im, shadow.filter(ImageFilter.GaussianBlur(size * 0.12)))
    d = ImageDraw.Draw(im)
    for xy, ln in pos:
        d.text(xy, ln, font=font, fill="white")
    out = io.BytesIO()
    im.convert("RGB").save(out, "JPEG", quality=90)
    return out.getvalue()


def crop169(img: bytes) -> bytes:
    from PIL import Image
    im = Image.open(io.BytesIO(img)).convert("RGB")
    w, h = im.size
    th = int(w * 9 / 16)
    if th < h:
        top = (h - th) // 2
        im = im.crop((0, top, w, top + th))
    out = io.BytesIO()
    im.save(out, "JPEG", quality=92)
    return out.getvalue()


def cine_thumb(img: bytes, title: str, highlight: str = "") -> bytes:
    """CINEPARK 썸네일: 제목 두 줄을 가로 정가운데에. 모바일에서 정사각형으로 잘려도 보이도록
    글자 덩어리를 화면 폭의 50% 안에 넣는다. 강조 단어는 노란색, 부드러운 그림자."""
    from PIL import Image, ImageDraw, ImageFilter, ImageFont
    im = Image.open(io.BytesIO(crop169(img))).convert("RGBA")
    w, h = im.size
    lines = [x.strip() for x in title.replace("\\n", "\n").split("\n") if x.strip()][:2]
    d0 = ImageDraw.Draw(im)
    size = int(h * 0.11)
    while size > 20:
        font = ImageFont.truetype(str(STATIC / "Paperlogy-8ExtraBold.woff2"), size)
        if max(d0.textlength(ln, font=font) for ln in lines) <= w * 0.50:
            break
        size -= 2
    y = h * 0.36 - (len(lines) * size * 1.25) / 2
    shadow = Image.new("RGBA", im.size, (0, 0, 0, 0))
    ds = ImageDraw.Draw(shadow)
    runs = []
    for ln in lines:
        x = (w - d0.textlength(ln, font=font)) / 2
        ds.text((x + 3, y + 4), ln, font=font, fill=(0, 0, 0, 200))
        parts = ln.split(highlight) if highlight and highlight in ln else [ln]
        xx = x
        for i, part in enumerate(parts):
            runs.append(((xx, y), part, "white"))
            xx += d0.textlength(part, font=font)
            if i < len(parts) - 1:
                runs.append(((xx, y), highlight, (255, 214, 10)))
                xx += d0.textlength(highlight, font=font)
        y += size * 1.25
    im = Image.alpha_composite(im, shadow.filter(ImageFilter.GaussianBlur(size * 0.12)))
    d = ImageDraw.Draw(im)
    for xy, t, col in runs:
        d.text(xy, t, font=font, fill=col)
    out = io.BytesIO()
    im.convert("RGB").save(out, "JPEG", quality=90)
    return out.getvalue()


# ───────────────────────── 가져가기 ─────────────────────────
def plain_text(pkg: dict) -> str:
    """네이버 에디터에 붙여 넣을 본문. 그림 자리는 【그림 n】 으로 표시."""
    a = pkg["article"]
    caps = {im["no"]: im.get("caption", "") for im in a.get("images", [])}
    blocks = list(a.get("blocks", []))
    lines = [a.get("title", ""), ""]
    if blocks and "쿠팡 파트너스 활동의 일환" in blocks[0].get("text", ""):  # 대가성 문구는 맨 위
        lines += [blocks.pop(0)["text"], ""]
    if not any(bl.get("type") == "image" and bl.get("no") == 0 for bl in blocks):
        lines += ["【그림 1 · 썸네일】", ""]
    for bl in blocks:
        t = bl.get("type")
        if t == "image":
            n = bl.get("no", 0)
            cap = caps.get(n, "")
            lines += [cap if cap.startswith("[이미지") else f"【그림 {n + 1}】 {cap}".rstrip(), ""]
        elif t == "h":
            lines += [f"■ {bl.get('text', '')}", ""]
        elif t in ("p", "memo", "link", "source"):
            lines += [bl.get("text", ""), ""]
        elif t == "check":
            lines += [f"□ {x}" for x in bl.get("items", [])] + [""]
    if a.get("stocks"):
        lines += ["■ 관련 기업과 종목", ""]
        for x in a["stocks"]:
            lines += [f"• {x.get('name', '')} | {x.get('market', '')} {x.get('code', '')}", x.get("reason", ""), ""]
        lines += [a.get("stock_note") or "사업 관련성이 곧 주가 상승이나 투자 수익을 뜻하지는 않습니다.",
                  "※ 특정 종목의 매수·매도를 권유하는 글이 아닙니다.", ""]
    if pkg.get("blog") == "cinepark":
        d = pkg.get("date", "")
        lines += [f"※ 작성 기준: {d[:4]}년 {int(d[5:7])}월 {int(d[8:10])}일. 본문 이미지는 내용을 설명하기 위해 AI로 재구성한 가상 장면이며 "
                  "실제 행사·계약 사진이 아닙니다." if len(d) == 10 else "", ""]
    if a.get("sources") and not any(bl.get("type") == "source" for bl in a.get("blocks", [])):
        lines += ["참고 자료"] + [f"· {s.get('title', '')} {s.get('url', '')}" for s in a["sources"]] + [""]
    if a.get("tags"):
        lines.append(" ".join("#" + t.lstrip("#").replace(" ", "") for t in a["tags"]))
    return "\n".join(lines).strip()


def images_zip(pkg: dict) -> bytes:
    from . import storage
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        for im in pkg["article"].get("images", []):
            if im.get("r2_key"):
                ext = im["r2_key"].rsplit(".", 1)[-1]
                z.writestr(f"그림{im['no'] + 1:02d}_{im.get('role', '본문')}.{ext}", storage.get_bytes(im["r2_key"]))
        z.writestr("본문.txt", plain_text(pkg))
    return buf.getvalue()
