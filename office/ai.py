"""OpenAI 호출: 그림(참고 이미지 포함)과 멘트 3안.

크레딧이 떨어지면 config 의 모델만 바꾸면 됩니다 (Gemini 전환은 다음 단계).
"""
from __future__ import annotations

import base64
import io
import json
import os
import re

from PIL import Image, ImageOps


def _client():
    from openai import OpenAI
    return OpenAI(api_key=os.environ["OPENAI_API_KEY"])


def _shrink(data: bytes, max_side: int = 1536) -> bytes:
    """참고 이미지는 1536px 이하 PNG 로 줄여 보낸다 (입력 비용·업로드 크기 절약)."""
    im = Image.open(io.BytesIO(data))
    im = ImageOps.exif_transpose(im)  # 휴대폰 사진의 방향 정보(EXIF)대로 바로 세운다
    im = im.convert("RGB")
    im.thumbnail((max_side, max_side))
    out = io.BytesIO()
    im.save(out, "PNG")
    return out.getvalue()


def render(cfg: dict, prompt: str, images: list[bytes], size: str) -> bytes:
    """블로그 그림: 참고 이미지가 있으면 편집, 없으면 새로 그리기. 크기를 지원하지 않으면 정사각으로."""
    o = cfg["openai"]
    c = _client()
    for sz in dict.fromkeys([size, "1024x1024"]):
        try:
            if images:
                files = [(f"ref{i}.png", _shrink(b), "image/png") for i, b in enumerate(images)]
                r = c.images.edit(model=o["image_model"], image=files, prompt=prompt, size=sz, quality=o["image_quality"])
            else:
                r = c.images.generate(model=o["image_model"], prompt=prompt, size=sz, quality=o["image_quality"])
            return base64.b64decode(r.data[0].b64_json)
        except Exception as e:
            if "size" not in str(e).lower() or sz == "1024x1024":
                raise
    raise RuntimeError("그림 생성 실패")


def draw(cfg: dict, prompt: str, images: list[bytes]) -> bytes:
    """참고 이미지들 + 프롬프트 → PNG bytes"""
    o = cfg["openai"]
    files = [(f"ref{i}.png", _shrink(b), "image/png") for i, b in enumerate(images)]
    r = _client().images.edit(model=o["image_model"], image=files, prompt=prompt,
                              size=o["image_size"], quality=o["image_quality"])
    png = base64.b64decode(r.data[0].b64_json)
    # Threads 는 JPEG/PNG 8MB 이하. 넘으면 JPEG 로 줄인다.
    if len(png) > 7_500_000:
        im = Image.open(io.BytesIO(png)).convert("RGB")
        out = io.BytesIO()
        im.save(out, "JPEG", quality=90)
        return out.getvalue()
    return png


_RULES = """당신은 Threads 계정 'Turner Bro'(turnerbro.32)의 멘트 담당입니다.
그림 한 장에 붙일 한국어 멘트를 씁니다.

규칙
- 그림에 보이는 것을 설명하지 않는다. 그림 밖의 한마디를 쓴다.
- 한두 문장, {max_chars}자 이내. 해시태그 금지. 이모지는 0~1개.
- 고양이: SNS 집사들이 "우리 애도 그래" 하고 공감할 순간. 집사의 혼잣말이나 뒤틀기 한 줄.
  (예: 귀엽다 → 목욕은 싫어하면서)
- 여행: 세 안을 서로 다른 유형으로, 아래 순서대로 쓴다.
  1안 혼잣말: 그곳을 다녀온 사람의 짧은 기억이나 감상. (예: 신주쿠역. 참 많이 다녔는데)
  2안 현지 공감: 그 도시에 가 본 사람이면 "맞아" 할 사소한 디테일 한 줄. (예: 런던 날씨는 우산을 챙기면 맑다)
  3안 말 걸기: 읽는 사람에게 그 도시에 대해 가볍게 묻는 한 줄. (예: 후쿠오카 가면 다들 첫 끼 뭐 먹어요?)
  지어낸 구체적 사건(누구와 갔다, 무엇을 먹었다)은 쓰지 않는다.
  연도, 날짜, '몇 년 전', '20년이 넘었다' 같은 시간·햇수 표현은 쓰지 않는다.
- 금지어: {banned}
- 말투 예시(이 계정의 실제 게시 문구):
{examples}

서로 다른 3안을 JSON 으로만 출력: {{"options": ["...", "...", "..."]}}"""


def captions(cfg: dict, subject: str, image_png: bytes | None = None, recent: list[str] | tuple = ()) -> list[str]:
    c = cfg["caption"]
    system = _RULES.format(max_chars=c["max_chars"], banned=", ".join(c["banned"]),
                           examples="\n".join(f"  - {e}" for e in c["examples"]))
    if c.get("style_notes"):
        system += "\n\nMr. MOON 말투 노트(대표님이 직접 고친 멘트에서 뽑은 규칙. 위 규칙보다 우선):\n" + "\n".join(f"  - {x}" for x in c["style_notes"])
    if c.get("edits"):
        system += ("\n\nMr. MOON 이 고친 실제 사례(고치기 전 → 고친 뒤). 고친 방향을 따라 처음부터 '고친 뒤'처럼 쓰세요:\n"
                   + "\n".join(f"  - {b} → {a}" for b, a in c["edits"][-15:]))
    if recent:
        system += ("\n\n최근에 이미 올린 멘트입니다. 같은 생각(예: 낮잠·밤잠, 방해, 자리 뺏기), 같은 문장 구조, "
                   "같은 끝맺음을 되풀이하지 말고 다른 순간을 고르세요:\n" + "\n".join(f"  - {r}" for r in recent))
    content = [{"type": "input_text", "text": subject}]
    if image_png:
        b64 = base64.b64encode(_shrink(image_png, 768)).decode()
        content.append({"type": "input_image", "image_url": f"data:image/png;base64,{b64}"})
    r = _client().responses.create(model=cfg["openai"]["text_model"],
                                   input=[{"role": "system", "content": system},
                                          {"role": "user", "content": content}])
    text = r.output_text or ""
    m = re.search(r"\{.*\}", text, re.S)
    try:
        return [str(x) for x in json.loads(m.group(0))["options"]][:3] if m else []
    except (json.JSONDecodeError, KeyError, TypeError):
        return [line.strip("-• ").strip() for line in text.splitlines() if line.strip()][:3]


STUDY_RULES = """당신은 Threads 계정 'Turner Bro'의 멘트 편집장입니다. 대표님(Mr. MOON)이 AI 멘트를 직접 고친 기록(고치기 전 → 고친 뒤)을 봅니다.
종류(고양이 cat / 여행 travel)마다, 대표님이 무엇을 바꾸는지 구체적인 규칙 5~8줄로 정리하세요.
- 길이, 끝맺음(어미), 시점(누가 말하는가), 고양이 말투 여부, 질문형 비율, 빼 버린 표현, 자주 쓰는 단어처럼 실제로 확인되는 것만.
- 규칙마다 기록 속 실제 예를 짧게 붙이세요(예: '…다' 대신 '…냥?'처럼 고양이가 말하게 함 — 예: 뭘보냥?).
- 기록이 없는 종류는 빈 목록.
JSON 만 출력: {"cat": ["규칙", ...], "travel": ["규칙", ...]}"""


def study_captions(cfg: dict, pairs: dict) -> dict:
    """pairs: {"cat": [(before, after)], "travel": [...]} → 종류별 말투 규칙."""
    lines = []
    for k, rows in pairs.items():
        lines.append(f"[{k}]")
        lines += [f"- {b or '(없음)'} → {a}" for b, a in rows]
    r = _client().responses.create(model=cfg["openai"]["text_model"],
                                   input=[{"role": "system", "content": STUDY_RULES},
                                          {"role": "user", "content": "\n".join(lines)}])
    m = re.search(r"\{.*\}", r.output_text or "", re.S)
    d = json.loads(m.group(0)) if m else {}
    return {k: [str(x) for x in d.get(k, [])][:8] for k in ("cat", "travel")}


PICK_RULES = """당신은 Threads 사진 편집자입니다. 같은 도시의 여행 원본 사진 후보 가운데, 펜 수채화로 바꿔 Threads 에 올릴 한 장을 고릅니다.
가설(Mr. MOON): 사람들은 누구나 찍는 명소보다 여행 속 일상적인 공간에 더 관심을 갖는다.
실제 성적(2026-11): 이탈리아 골목길 2,300회, 도쿄역 안 인파 1,200회 / 타이베이 중앙역 건물 정면·뤼미에르 극장 간판·프라하 건물 정면은 250회 안팎.
그래서 아래 순서를 반드시 지킨다.
 1순위: 눈높이에서 본 생활 장면 — 사람이 오가는 골목, 역 안·개찰구·플랫폼, 지하철, 시장·상점가, 동네 식당·카페 안, 버스 정류장, 주택가 계단.
 2순위: 그 도시 사람의 일상이 보이는 풍경 — 강변 산책로, 공원 벤치, 창밖 거리, 노천 테이블.
 3순위: 탁 트인 전망·스카이라인.
 마지막: 건물 정면을 꽉 채운 사진, 간판·현판이 주인공인 사진, 기념물·명소를 엽서처럼 찍은 사진. 1~3순위 후보가 하나라도 있으면 절대 고르지 않는다.
'나도 거기서 헤맸는데', '저기 가 봤어' 하고 말을 걸고 싶어지는 장면이면 더 좋다.
같은 순위 안에서는 최근에 올린 장면과 다른 것을 고른다: 골목만 이어지지 않게 역, 시장, 카페, 강변처럼 공간의 성격이 바뀌는 쪽을 먼저 본다. 글자(신문·포스터)가 화면 대부분을 채운 사진은 고르지 않는다.
먼저 후보마다 바로 선 사진인지 본다(하늘·천장이 위, 사람·건물이 똑바로 서 있음). 옆으로 눕거나 거꾸로 된 사진은 sideways 에 번호를 넣고 고르지 않는다.
JSON 만 출력: {"pick": 0, "why": "고른 이유 한 줄(몇 순위인지 포함)", "sideways": []}"""

UPRIGHT_RULES = """여행 원본 사진 점검 담당입니다. 사진마다 두 가지를 봅니다.
1) 방향: 하늘·천장이 위, 땅·바닥이 아래, 사람·건물·글자가 똑바로 서 있으면 바로 선 사진.
   옆으로 누운 사진(90도 돌아감)이나 거꾸로 된 사진(180도)은 sideways 에 번호(0부터)를 넣는다. 애매하면 넣지 않는다.
2) 종류: 사진마다 하나만 고른다.
   daily  = 눈높이의 생활 장면(사람이 오가는 골목, 역 안·플랫폼, 지하철, 시장·상점가, 식당·카페 안, 정류장, 주택가)
   scene  = 일상이 보이는 풍경(강변 산책로, 공원, 창밖 거리, 노천 테이블)
   view   = 탁 트인 전망·스카이라인·자연 풍경
   facade = 건물 정면을 꽉 채운 사진, 간판·현판이 주인공, 기념물·명소를 엽서처럼 찍은 사진
   person = 사람 얼굴이 화면을 크게 채운 사진(셀카·인물 사진)
   text   = 글자·포스터·안내판이 화면 대부분
   food   = 음식·음료가 주인공
JSON 만 출력: {"sideways": [번호, ...], "tags": ["daily", "facade", ...]}  (tags 는 사진 순서대로, 사진 수만큼)"""

TAGS = ("daily", "scene", "view", "facade", "person", "text", "food")


def check_upright(cfg: dict, images: list[bytes]) -> list[int]:
    """사진 묶음(최대 8장) 가운데 눕거나 거꾸로 된 사진 번호."""
    return check_photos(cfg, images)[0]


def check_photos(cfg: dict, images: list[bytes]) -> tuple[list[int], list[str]]:
    """사진 묶음(최대 8장): (눕거나 거꾸로 된 번호, 사진별 종류 태그)."""
    content = [{"type": "input_text", "text": f"사진 {len(images)}장, 0번부터 순서대로입니다."}]
    for b in images:
        b64 = base64.b64encode(_shrink(b, 384)).decode()
        content.append({"type": "input_image", "image_url": f"data:image/png;base64,{b64}"})
    r = _client().responses.create(model=cfg["openai"]["text_model"],
                                   input=[{"role": "system", "content": UPRIGHT_RULES},
                                          {"role": "user", "content": content}])
    m = re.search(r"\{.*\}", r.output_text or "", re.S)
    d = json.loads(m.group(0)) if m else {}
    side = sorted({int(x) for x in d.get("sideways", []) if 0 <= int(x) < len(images)})
    tags = [t if t in TAGS else "" for t in (d.get("tags") or [])][:len(images)]
    tags += [""] * (len(images) - len(tags))
    return side, tags


RESORT_NOTE = ("\n이번 도시는 휴양지입니다. 휴양지에서는 바다·해변·숲·온천 풍경과 탁 트인 전망도 1순위로 봅니다. "
               "'저기 가고 싶다'는 마음이 드는 장면을 고르되, 리조트 간판·호텔 건물 정면은 여전히 마지막입니다.")


def pick_photo(cfg: dict, city: str, images: list[bytes], resort: bool = False) -> tuple[int, str, list[int]]:
    """여행 사진 후보 가운데 한 장을 고른다. 눕거나 거꾸로 된 후보 번호도 함께. 실패하면 0번."""
    content = [{"type": "input_text", "text": f"도시: {city}. 후보 {len(images)}장, 0번부터 순서대로입니다."}]
    for b in images:
        b64 = base64.b64encode(_shrink(b, 512)).decode()
        content.append({"type": "input_image", "image_url": f"data:image/png;base64,{b64}"})
    try:
        r = _client().responses.create(model=cfg["openai"]["text_model"],
                                       input=[{"role": "system", "content": PICK_RULES + (RESORT_NOTE if resort else "")},
                                              {"role": "user", "content": content}])
        m = re.search(r"\{.*\}", r.output_text or "", re.S)
        d = json.loads(m.group(0)) if m else {}
        side = sorted({int(x) for x in d.get("sideways", []) if 0 <= int(x) < len(images)})
        i = int(d.get("pick", 0))
        i = i if 0 <= i < len(images) else 0
        if i in side:
            ok = [j for j in range(len(images)) if j not in side]
            i = ok[0] if ok else -1
        return i, str(d.get("why", "")), side
    except Exception:
        return 0, "", []
