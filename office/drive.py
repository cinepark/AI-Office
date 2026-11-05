"""구글 드라이브 읽기 전용: 여행 원본 사진 목록, 기준 그림 내려받기.

서비스 계정(읽기 전용)을 씁니다. 드라이브의 '01.원본 사진' 폴더와 기준 그림 폴더를
서비스 계정 이메일에 '뷰어'로 공유해 두면 됩니다. 원본은 절대 수정·삭제하지 않습니다.
"""
from __future__ import annotations

import io
import json
import os

from .planner import parse_city_folder

IMAGE_TYPES = ("image/jpeg", "image/png", "image/webp")


def _service():
    from google.oauth2 import service_account
    from googleapiclient.discovery import build
    info = json.loads(os.environ["GOOGLE_SA_JSON"])
    creds = service_account.Credentials.from_service_account_info(
        info, scopes=["https://www.googleapis.com/auth/drive.readonly"])
    return build("drive", "v3", credentials=creds, cache_discovery=False)


def _list(svc, q: str) -> list[dict]:
    out, token = [], None
    while True:
        r = svc.files().list(q=q, fields="nextPageToken, files(id, name, mimeType, size)",
                             pageSize=1000, pageToken=token,
                             supportsAllDrives=True, includeItemsFromAllDrives=True).execute()
        out += r.get("files", [])
        token = r.get("nextPageToken")
        if not token:
            return out


def travel_photos(root_folder: str) -> list[dict]:
    """01.원본 사진 → 도시 폴더 → 사진. [{id, name, city, year}]"""
    svc = _service()
    folders = _list(svc, f"'{root_folder}' in parents and mimeType='application/vnd.google-apps.folder' and trashed=false")
    photos = []
    for f in folders:
        city, year = parse_city_folder(f["name"])
        for p in _list(svc, f"'{f['id']}' in parents and trashed=false"):
            if p.get("mimeType") in IMAGE_TYPES:
                photos.append({"id": p["id"], "name": p["name"], "city": city, "year": year})
    return photos


def download(file_id: str) -> bytes:
    from googleapiclient.http import MediaIoBaseDownload
    svc = _service()
    req = svc.files().get_media(fileId=file_id, supportsAllDrives=True)
    buf = io.BytesIO()
    dl = MediaIoBaseDownload(buf, req)
    done = False
    while not done:
        _, done = dl.next_chunk()
    return buf.getvalue()
