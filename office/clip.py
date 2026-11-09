"""리뷰&리뷰 10초 클립: 패키지 썸네일 그림(글자 없는 원본)을 Gemini Omni Flash 로 움직이게 한다.

- 키: GEMINI_API_KEY (GitHub·Streamlit 비밀값). 없으면 클립 단계는 조용히 건너뛴다.
- 모델: gemini-omni-1.1-flash (Veo 3.1 미리보기 모델은 2026-10-22 종료됨, Gemini API 문서 기준)
- 세로 9:16, 720p, 소리 포함(방 안의 잔잔한 소리, 음악·대사 없음).
"""
from __future__ import annotations

import base64
import os

MODELS = ["gemini-omni-1.2-flash", "gemini-omni-1.1-flash"]  # 새 모델 먼저, 안 되면 이전 모델
MODEL = MODELS[0]

DEFAULT_MOTION = ("[0-10s] The cat in the picture makes one small natural movement: it blinks slowly, its ears twitch once "
                  "and its tail sways gently. The camera stays locked off. Soft ambient room sound, no music, no dialogue. "
                  "Keep the drawing style, colors and composition of the image exactly. No text, no letters.")


def ready() -> bool:
    return bool(os.environ.get("GEMINI_API_KEY", "").strip())


def make(image: bytes, motion: str = "", photo: bool = False) -> bytes:
    """그림 한 장 → 세로 10초 안팎 mp4 바이트."""
    from google import genai
    client = genai.Client(api_key=os.environ["GEMINI_API_KEY"].strip())
    mime = "image/jpeg" if image[:3] == b"\xff\xd8\xff" else "image/png"
    prompt = (motion.strip() or DEFAULT_MOTION)
    if "[0-" not in prompt:
        prompt = "[0-10s] " + prompt
    keep = ("Keep it a real photograph shot on a phone camera: true-to-life textures, natural light, real physics. No people, no hands."
            if photo else "Keep the drawing style exactly.")
    prompt += f" The camera stays locked off. {keep} No text, no letters, no music, no dialogue."
    last = None
    for m in MODELS:
        try:
            it = client.interactions.create(
                model=m,
                input=[{"type": "image", "data": base64.b64encode(image).decode("utf-8"), "mime_type": mime},
                       {"type": "text", "text": prompt}],
                response_format={"type": "video", "aspect_ratio": "9:16", "resolution": "720p"},
            )
            break
        except Exception as e:
            last = e
            if "404" not in str(e) and "not found" not in str(e).lower():
                raise
    else:
        raise RuntimeError("Gemini 영상 모델을 이 API 키로 쓸 수 없습니다(404). Google AI Studio에서 이 키의 프로젝트에 "
                           "결제(유료 등급)가 연결되어 있는지 확인해 주세요. Omni 영상 모델은 무료 등급에서 열리지 않습니다. "
                           f"원래 메시지: {str(last)[:120]}")
    return base64.b64decode(it.output_video.data)
