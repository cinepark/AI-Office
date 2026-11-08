"""리뷰&리뷰 10초 클립: 패키지 썸네일 그림(글자 없는 원본)을 Gemini Omni Flash 로 움직이게 한다.

- 키: GEMINI_API_KEY (GitHub·Streamlit 비밀값). 없으면 클립 단계는 조용히 건너뛴다.
- 모델: gemini-omni-1.1-flash (Veo 3.1 미리보기 모델은 2026-10-22 종료됨, Gemini API 문서 기준)
- 세로 9:16, 720p, 소리 포함(방 안의 잔잔한 소리, 음악·대사 없음).
"""
from __future__ import annotations

import base64
import os

MODEL = "gemini-omni-1.1-flash"

DEFAULT_MOTION = ("[0-10s] The cat in the picture makes one small natural movement: it blinks slowly, its ears twitch once "
                  "and its tail sways gently. The camera stays locked off. Soft ambient room sound, no music, no dialogue. "
                  "Keep the drawing style, colors and composition of the image exactly. No text, no letters.")


def ready() -> bool:
    return bool(os.environ.get("GEMINI_API_KEY", "").strip())


def make(image: bytes, motion: str = "") -> bytes:
    """그림 한 장 → 세로 10초 안팎 mp4 바이트."""
    from google import genai
    client = genai.Client(api_key=os.environ["GEMINI_API_KEY"].strip())
    mime = "image/jpeg" if image[:3] == b"\xff\xd8\xff" else "image/png"
    prompt = (motion.strip() or DEFAULT_MOTION)
    if "[0-" not in prompt:
        prompt = "[0-10s] " + prompt
    prompt += " The camera stays locked off. Keep the drawing style exactly. No text, no letters, no music, no dialogue."
    it = client.interactions.create(
        model=MODEL,
        input=[{"type": "image", "data": base64.b64encode(image).decode("utf-8"), "mime_type": mime},
               {"type": "text", "text": prompt}],
        response_format={"type": "video", "aspect_ratio": "9:16", "resolution": "720p"},
    )
    return base64.b64decode(it.output_video.data)
