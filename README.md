# MY AI OFFICE

Mr. MOON 의 AI 사무실. 담당자 12명이 실제 업무를 하고, 사무실 화면에 지금 하는 일이 말풍선으로 뜹니다.
지시는 **SHIHO 메신저**에서 SHIHO 에게만 하면 됩니다. SHIHO 가 업무로 바꿔 담당자에게 나눕니다.

## 구성
| 부분 | 하는 일 | 돌아가는 곳 |
|---|---|---|
| 사무실 화면 `main.py` | 01층(총괄·IT·보안) · 02층(콘텐츠 제작·채널 운영) 말풍선, 활동 기록, Threads·CINEPARK·리뷰&리뷰 데스크, SHIHO 메신저 | Streamlit Cloud |
| 퇴근 후 업무 `office/` + `.github/workflows/office.yml` | 21:00 재고 생성, 09:30·12:30·16:30·19:30 Threads 게시, 월요일 토큰 갱신 | GitHub Actions |
| 사무실 기록 | 업무 일지·게시 예정·게시 기록·지시 (state.json), 그림 | Cloudflare R2 |

## 지금 하는 업무 (1단계)
- Threads turnerbro.32 하루 4회 자동 게시 (여행 → 고양이 → 여행 → 고양이), 승인 없이 진행, 데스크에서 빼기·고치기·지금 게시 가능
- 다음 단계: CINEPARK 데스크(영화잡지형 글 패키지), 리뷰&리뷰 데스크(쿠팡파트너스)

## 실행
```
streamlit run main.py
```
Streamlit Cloud Secrets 와 GitHub Actions Secrets 에 같은 비밀값 7개를 넣습니다. 연결 방법은 `docs_설치_Threads연결.md`.
