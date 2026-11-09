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


PICK_RULES = """당신은 Threads 사진 편집자입니다. 같은 도시의 여행 원본 사진 후보 가운데, 펜 수채화로 바꿔 Threads 에 올릴 한 장을 고릅니다.
가설(Mr. MOON): 사람들은 누구나 찍는 명소보다 여행 속 일상적인 공간에 더 관심을 갖는다.
그래서 그 도시 사람들이 매일 지나는 곳을 먼저 고른다: 역 개찰구·출구, 지하철, 편의점, 동네 식당·시장, 골목, 버스 정류장, 빨래방, 주택가 계단.
'나도 거기서 헤맸는데', '저기 가 봤어' 하고 말을 걸고 싶어지는 장면이면 더 좋다. 엽서·관광 안내에 나오는 정면 명소 사진은 뒤로 미룬다.
일상 공간 사진이 없으면, 명소라도 사람이 오가는 생활의 순간이 담긴 사진을 고른다. 글자(신문·포스터)가 화면 대부분을 채운 사진은 고르지 않는다.
JSON 만 출력: {"pick": 0, "why": "고른 이유 한 줄"}"""


def pick_photo(cfg: dict, city: str, images: list[bytes]) -> tuple[int, str]:
    """여행 사진 후보 가운데 Threads 미리보기에서 눈에 띌 한 장을 고른다. 실패하면 0번."""
    content = [{"type": "input_text", "text": f"도시: {city}. 후보 {len(images)}장, 0번부터 순서대로입니다."}]
    for b in images:
        b64 = base64.b64encode(_shrink(b, 512)).decode()
        content.append({"type": "input_image", "image_url": f"data:image/png;base64,{b64}"})
    try:
        r = _client().responses.create(model=cfg["openai"]["text_model"],
                                       input=[{"role": "system", "content": PICK_RULES},
                                              {"role": "user", "content": content}])
        m = re.search(r"\{.*\}", r.output_text or "", re.S)
        d = json.loads(m.group(0)) if m else {}
        i = int(d.get("pick", 0))
        return (i if 0 <= i < len(images) else 0), str(d.get("why", ""))
    except Exception:
        return 0, ""
