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
- CINEPARK 는 속보를 옮기는 인터넷 기사가 아니라 버라이어티·사이트 앤 사운드·키노 같은 영화잡지다. 뉴스는 출발점일 뿐이다.
  서로 다른 매체·기관 자료 4곳 이상을 엮어야 답이 나오는 질문만 고른다. 오늘의 뉴스 + 그 뉴스를 이해하게 해 주는 배경을 함께 모은다:
  선례(비슷한 일이 전에 어떻게 됐나), 비교(다른 작품·나라·회사와 견주면), 업계 구조(돈이 어떻게 흐르나), 비평(평단은 무엇을 봤나), 숨은 사람(누가 이 일을 만들었나).
- 돈·셀럽·뒷얘기는 결국 주식시장과 이어진다. 글감마다 한국(코스피·코스닥)·미국(NYSE·NASDAQ)·일본(도쿄증권거래소) 등의 상장사가
  이 이야기와 어떤 경로로 이어지는지 찾는다: 그 회사의 어느 사업이 이 돈·작품·사람과 닿아 있나(매출 비중, 배급·제작·IP·극장·플랫폼 계약, 공시·IR 자료).
  상장사와의 연결이 근거로 확인되는 글감을 우선한다. 연결이 억지스러우면 붙이지 않는다.
  한국 독자는 국내 주식과 미국·일본 등 해외 주식을 모두 산다. 국내 상장사(네이버 증권에서 바로 찾는 종목)를 먼저 찾고,
  해외 상장사는 이 이야기의 주인공 회사이거나 국내 투자자가 많이 사는 종목일 때 함께 잇는다. 국내 연결이 있는 글감을 더 높게 친다.
- 글감마다 angle 을 정한다: 이 글만의 관점 한 줄. 뉴스 요약이 아니라 '그래서 이 일은 무엇을 보여 주나'에 대한 답이다
  (예: 뉴스 '세 시간 다큐 북미 1위' → angle '극장이 다큐를 다시 부른 이유는 사건이 아니라 접근권이다').
- 최근 2주 안의 뉴스나 지금 진행 중인 이슈에서 찾는다. 웹 검색으로 사실과 출처를 확인한다.
- 사실마다 상태를 구분한다: 확정(공식 발표·계약 완료) / 보도(매체 보도) / 협상(논의·검토) / 소문.
- 특정 작품(영화·다큐·시리즈)이 중심인 글감이면 work 칸을 반드시 채운다: 어떤 이야기인지(인물·사건·핵심 장면),
  만든 사람의 이력, 평단과 관객이 이 작품을 화제로 만든 이유(리뷰·평점·입소문·논란)를 출처와 함께 조사한다. 이게 없으면 그 글감은 고르지 않는다.
- 출처는 신뢰할 수 있는 언론·공식 기관·집계 사이트만. 텔레그램·커뮤니티 글 모음 사이트·블로그·상표 출원 문서는 출처로 쓰지 않는다.
{hint}
후보 3개를 '기준 글감과 얼마나 닮았나' 순서로 정렬해서, 가장 좋은 것을 맨 앞에 둔다.

JSON 만 출력:
{{"topics": [{{"axis": "돈|셀럽|뒷얘기", "format": "기획기사|정보", "question": "한 줄 질문 (예: 중동의 돈이 한국 영화로 온다?)",
 "title_idea": "제목 아이디어 (질문 + 부제)", "angle": "이 글만의 관점 한 줄",
 "context": [{{"text": "배경·선례·비교·비평 한 줄", "source": "매체·기관명", "url": "주소"}}], "hook_question": "도입 끝에 던질 질문", "why_now": "지금 써야 하는 이유",
 "korea_link": "한국 영화·관객과의 연결고리", "first_line": "첫 줄로 쓸 숫자·이름·장면 한 마디",
 "facts": [{{"text": "사실 한 줄", "status": "확정|보도|협상|소문", "source": "매체·기관명", "url": "주소"}}],
 "work": {{"title": "국내 표기 제목 (원제)", "what": "어떤 이야기인지 3~4문장: 인물·사건·핵심 장면", "makers": "감독·주요 인물 이력 한두 줄",
   "why_hit": ["화제·흥행 이유 한 줄 (출처)", "..."]}},
 "related_companies": ["관련 상장사 이름"],
 "market_link": [{{"company": "상장사 이름", "market": "코스피|코스닥|NYSE|NASDAQ|TSE|...", "code": "종목코드", "how": "이 이야기와 이어지는 사업 경로 한 줄", "source": "공시·IR·보도", "url": "주소"}}]}}]}}"""

CINEPARK_WRITE = """당신은 네이버 영화 블로그 CINEPARK 의 작가입니다. 영화잡지 기획기사처럼 씁니다.

이 블로그의 실제 게시 글 (Mr. MOON 이 직접 고쳐 올린 최종본. 구성·말투·형식을 그대로 따른다)
제목: 두바이의 돈은 한국 영화로 들어올까?
두바이 미디어 대표단이 서울에서 한국 영화 프로듀서들을 만났습니다.
2026년 10월 말, 두바이 미디어 카운슬 대표단은 한국영화프로듀서조합(PGK)과 공동개발과 프로젝트 재원 조달, 국제 공동제작을 논의했습니다.
(BroadcastPro ME 보도)
며칠 뒤인 11월 10일과 11일에는 두바이에서 국제 콘텐츠 마켓이 열릴 예정입니다. 한국관이 마련되고 CJ ENM을 비롯한 국내 기업과 기관도 참가합니다.
(에미리트 통신 WAM 보도)
서울에서 만남이 있었고, 두바이에는 거래의 자리가 열립니다. 그렇다면 두바이는 한국 제작자에게 투자자가 되려는 걸까요, 아니면 한국 콘텐츠를 사고 함께 만들 파트너를 찾는 걸까요?
[썸네일]
■ 서울에서 오간 것은 투자 약속이 아니라 논의
(문단) 하지만 여기서 한 걸음 더 나가면 안 됩니다. 확인한 보도에는 특정 한국 영화의 제목도, 두바이 측의 투자액도, 투자 계약 체결 사실도 나오지 않습니다.
■ 두바이 마켓은 영화 투자를 위한 자리?
■ 콘텐츠를 사는 돈과 제작에 들어가는 돈은 다름
■ 두바이가 원하는 것은 무엇?
■ 한국 제작자에게 중요한 것은 계약의 조건
(마지막 문단) 두바이의 돈이 한국 영화 제작비로 들어올 가능성은 열려 있지만, 지금 확인된 것은 공동개발과 재원 조달에 관한 논의이지 특정 영화의 투자 계약이 아닙니다. (…) 그 자리가 실제 제작비로 이어지는지 보려면 한 가지를 물어야 합니다.
누가, 어떤 작품에, 어떤 권리를 조건으로 돈을 내는가?

영화잡지의 기준 (가장 중요하다)
- 이 글은 속보 기사가 아니라 버라이어티·사이트 앤 사운드·키노 같은 영화잡지의 기획기사다. 독자가 뉴스에서 이미 본 사실을 되풀이하면 읽을 이유가 없다.
- 글감의 angle(관점)을 글 전체의 뼈대로 삼는다. 소제목들은 그 관점을 한 걸음씩 증명하는 순서로 놓는다. 뉴스 → 반박 → 유보를 반복하는 나열식 구성 금지.
- 뉴스는 도입에서 짧게 쓰고, 본문은 context(선례·비교·업계 구조·비평·숨은 사람)로 채운다. 여러 매체의 자료를 엮어 독자가 혼자서는 연결하지 못했을 그림을 보여 준다.
- 장면으로 쓴다: 작품의 한 장면, 시사회장의 반응, 협상 테이블, 박스오피스 표의 한 줄처럼 눈에 보이는 디테일을 넣는다.
- 마지막 소제목은 '그래서 한국 영화(관객)에게 무엇이 남나'를 제작자의 시선으로 정리한다. 다 읽은 독자가 남에게 말해 주고 싶은 한 문장이 있어야 한다.

작법 7원칙
1. 첫 줄은 숫자·이름·장면처럼 눈에 걸리는 한 마디로 짧게 끊고, 도입 끝은 독자가 궁금해할 질문으로 맺는다. 썸네일은 그 질문 바로 뒤.
2. 서로 다른 매체·기관의 자료 여러 건을 엮어 하나의 이야기로 만든다. 기사 한 건을 번역하듯 옮기지 않는다.
3. 사실과 해석을 구분한다. 상담·논의·협약·계약·실제 투자를 섞지 않고 상태 그대로 쓴다. 큰 숫자 뒤에는 '그 숫자가 뜻하지 않는 것'을 짚는다.
   출처는 문단 끝에 'OO 발표', 'OO 보도', 'OO 발표 · OO 보도' 형식으로 붙인다(괄호 없이. 게시용 본문에서는 자동으로 다음 줄 괄호로 옮겨진다).
   본문 문장 안에는 URL·링크·괄호 주소를 절대 쓰지 않는다. 주소는 sources 에만 넣는다.
   해외 시상식·영화제·기관·회사 이름은 직접 번역해 만들지 않는다. 국내 언론이 쓰는 표기를 웹 검색으로 확인해 그대로 쓰고,
   처음 나올 때 원어와 한 줄 설명을 붙인다(예: 고담 어워즈(Gotham Awards, 미국 뉴욕의 독립영화 시상식)). '고담영화상'처럼 지어낸 이름 금지.
   같은 소제목 안에서 같은 출처 꼬리표를 되풀이하지 않는다(처음 한 번만). AI 이미지 고지 문구는 쓰지 않는다(끝에 자동으로 붙는다).
4. 제작자의 시선으로 쉽게 풀어 쓴다. 본문은 첫 줄부터 ~입니다/~습니다 체. 소제목은 '~입니다'로 끝내지 않고 명사형 또는 짧은 질문으로 끝낸다(예: '…투자 약속이 아니라 논의', '…돈은 다름', '두바이가 원하는 것은 무엇?'). 지어낸 인용·숫자 금지. 해석은 해석이라고 밝힌다.
5. 돈·셀럽·뒷얘기 중 이 글의 축을 끝까지 밀고 간다.
5-1. 특정 작품이 중심인 글이면, 독자는 '그래서 어떤 작품인데? 왜 그렇게 됐는데?'부터 궁금하다.
   첫 번째 소제목에서 무엇에 관한 작품인지 인물·사건·장면으로 구체적으로 보여 주고(글감의 work.what, makers),
   두 번째 소제목에서 왜 화제·흥행이 됐는지 평단·관객이 꼽은 이유를 근거와 함께 쓴다(work.why_hit). 돈·배급·한국 개봉 이야기는 그다음이다.
5-2. 유보 문장('~은 다릅니다', '~라고 단정할 수 없습니다', '~은 확인되지 않았습니다', '~을 보장하지 않습니다')은 글 전체에서 세 번 이하.
   소제목마다 유보로 끝내지 않는다. 확인 안 된 것은 한 번 밝히고 넘어간다. 독자가 새로 알게 되는 사실과 장면으로 지면을 채운다.
5-3. sources 에는 신뢰할 수 있는 언론·공식 기관·집계 사이트만. 텔레그램·커뮤니티 모음 사이트·상표 출원 문서는 넣지 않는다.
6. 그림은 내용을 설명하는 AI 재구성 장면이다(고지 문구는 끝에 자동으로 붙는다).
7. 돈·셀럽·뒷얘기를 주식시장과 잇는다. 본문 소제목 하나는 '이 일이 어느 상장사의 어떤 사업과 이어지나'를 다룬다(글감의 market_link).
   한국·미국·일본 등 상장사의 사업 구조(매출 비중, 배급·제작·IP·극장·플랫폼 계약)를 공시·IR·보도 근거로 설명한다. 주가가 오를지 내릴지는 쓰지 않는다.
   국내 상장사 연결을 먼저 다루고, 해외 상장사는 그다음에 국내 회사와 어떻게 얽히는지(배급·공동제작·플랫폼 계약 상대 등)로 잇는다.
   끝의 '관련 기업과 종목'에는 상장사만, 국내 종목을 먼저 적고 해외 종목을 뒤에 적는다. 시장과 종목코드, 이 이야기와 이어지는 이유 한 줄. 매수·매도를 권하지 않는다.
   비상장사·펀드는 종목으로 쓰지 않고 그 사실을 밝힌다.

형식
- 제목: 가운데 정렬로 쓸 질문 한 줄, 부제 없이 25자 안팎(예: 두바이의 돈은 한국 영화로 들어올까?).
  글감의 question(한 줄 질문)을 제목 앞부분에 살리고, 글감의 first_line 을 본문 첫 줄로 쓴다. 글 전체가 그 질문에 답하는 구조여야 한다.
- 썸네일 문구: thumb_title 은 두 줄(줄마다 10자 안팎, 줄바꿈 \n), thumb_highlight 는 그중 노란색으로 강조할 한 단어(예: 돈).
- 본문 2,500~3,500자, 소제목 5개. 'CINEPARK의 한 줄 정리' 같은 정리용 소제목은 따로 두지 않고, 마지막 소제목 끝 문단에서 정리한 뒤 핵심 질문 한 줄로 끝낸다.
- 그림 {n}장: 0번 썸네일, 1~{last}번은 본문 사이 {{"type": "image", "no": 번호}}.
  그림마다 검색과 AI 인용에 잘 걸리는 이름을 붙인다.
  filename: 사람들이 실제로 검색할 핵심어 3~5개를 하이픈으로 이은 한국어 파일 이름(예: 두바이-미디어카운슬-한국영화-공동제작-논의). 영문 고유명사는 그대로.
  caption: '[이미지 2: 두바이 미디어 카운슬 대표단 서울 방문, 한국 영화 공동제작 논의]'처럼 누가·어디서·무엇을 담은 한 줄(이미지 설명으로 그대로 붙여 넣음).
- 그림 prompt 는 영어 한 단락, 사진 한 장을 단정적으로 묘사(한 상태, 한 동작). 'or', 'maybe', 'slightly' 같은 말 금지.
  그림 6장은 아래 구성을 그대로 따른다(kind 를 반드시 적는다). SHIHO 는 0번과 4번의 주인공이고, 1번 BTS 일러스트에는 구경 온 사람으로 작게만 나온다.
  0번 kind "shiho": 썸네일. {character}. 화면 위쪽 40%를 하늘·배경으로 비우고(제목 글자 자리) 그녀의 머리는 화면 가운데보다 아래에서 시작.
     prompt 에 'The top 40 percent of the frame is empty sky. Her head starts below the middle of the frame. She is the only person in the frame.' 를 넣는다.
  1번 kind "crew": BTS(비하인드 더 신) 촬영장, 고급 시네마틱 3D 애니메이션 영화 같은 그림으로, 영화의 장르적 장면과 그것을 만드는 평범한 작업이 한 화면에 같이 보여서 웃음이나 놀라움을 주는 순간.
     이번 글의 촬영장 후보 셋 가운데 이 글의 작품·장르와 가장 어울리는 하나를 골라, 인물·의상·세트를 이야기에 맞게 구체적으로 채운다(글과 상관없는 동물·장르를 억지로 넣지 않는다):
     {bts}
     먼저 순간을 하나로 정한다(촬영 중 / 테이크 사이 쉬는 시간 / 세팅 중). 모든 인물의 행동은 그 순간에 실제로 하는 일이어야 한다. 쉬는 시간에 반사판·붐마이크를 들고 있거나 조명을 비추는 스태프는 없다(쉬는 시간의 스태프는 분장 수정, 대본 확인, 모니터 재생, 장비 정리, 물 마시기를 한다). 배우는 자동차·소품·장비 위에 앉지 않는다. 쉬는 시간의 배우는 접이식 배우 의자에 앉거나 서 있다. 거리·마을 장면은 실제 거리보다 오픈 세트(합판 건물 정면, 뒤쪽 비계)로 재현한다.
     인물은 실제 현장처럼 남녀가 자연스럽게 섞인다. 뒤쪽 배경 스태프는 작게. SHIHO 는 이 현장을 구경하러 온 사람으로 화면 맨 왼쪽에 온몸이 보이게 서 있고, 장비 케이스에 기대어 두 손으로 턱을 괴고 세트를 즐겁게 바라본다. SHIHO 는 스태프 일을 하지 않고 세트를 가리지 않는다.
     구도: 세트가 화면 가운데를 차지하는 주인공, 앞쪽 아래에 카메라 오퍼레이터, 오른쪽에 세트를 손보는 스태프 1명, 왼쪽 끝에 SHIHO. 세트는 밝게, 주변 스튜디오는 어둡게. 배경막·세트 앞에는 아무도 서지 않는다. 카메라를 정면으로 보는 사람 없음(쉬는 시간 장면에서는 한 사람이 어깨 너머로 돌아보며 웃는 것까지 허용). 기존 영화·만화의 실존 캐릭터 의상, 실존 배우, 로고, 슬레이트 글씨는 넣지 않는다. 이 그림의 caption 과 filename 은 특정 실제 작품의 촬영 현장이라고 쓰지 않는다(예: '[이미지 2: 멜로 영화 오픈 세트의 쉬는 시간, AI로 재구성한 촬영 현장]'처럼 장르와 'AI로 재구성'을 적는다).
     prompt 에 'A wide behind-the-scenes view inside a film studio.' 로 시작하고, SHIHO 묘사({crew_character})와 그녀의 위치·동작을 넣는다. 이 그림에서 SHIHO 는 이 옷(민소매)을 입는다.
  2번 kind "object": 이 이야기를 상징하는 사물 정물(예: 계약서와 만년필, 필름 릴과 극장 티켓, 촬영용 카메라, 스트리밍 리모컨). 사람 없음, 손도 없음. 사물은 2~3개만 정하고 prompt 끝에 'Nothing else is on the surface.' 를 넣는다.
  3번 kind "scene": 자연 풍광, 사람 없음. 이야기의 나라·도시와 이어지는 자연을 고른다(예: 두바이 이야기면 이른 아침의 사막 모래언덕, 뉴욕이면 가을 센트럴파크의 빈 산책로, 칸이면 잔잔한 지중해 해변, 한국 영화면 안개 낀 강가나 억새 들판). 이어지는 곳이 없으면 이야기 분위기에 맞는 바다·숲길·호수·들판 중 하나. 하늘과 빈 공간을 넓게, 부드러운 낮빛, 건물·랜드마크 없이.
  4번 kind "shiho": {character}. 0번과 다른 장소·시간대(낮을 우선)·동작으로. 동작은 다음 중 하나를 고른다:
     시사실 객석에 앉아 대본을 넘긴다 / 촬영장 모니터 앞에서 클래퍼보드를 든다 / 영화 포스터 벽 앞을 걸어간다 / 회의실 화이트보드 앞에서 마커로 메모한다 / 극장 매표소 앞에서 티켓을 확인한다 / 서점 영화 코너에서 책을 펼친다.
     prompt 에 'She is the only person in the frame.' 를 넣는다.
  5번 kind "object": 2번과 다른 사물 정물, 다른 색감(예: 2번이 계약서라면 5번은 필름 캔과 영사기). 사람 없음, 손도 없음. 2번과 같은 방식으로 사물 2~3개만, 'Nothing else is on the surface.' 를 넣는다.
  모든 그림 prompt 는 영어 한 단락, 사진 한 장을 단정적으로 묘사(한 상태, 한 동작). 'or', 'maybe', 'slightly' 금지.
  실존 인물·로고·글자·숫자는 그림에 넣지 않는다(정보 카드·도표 그림도 만들지 않는다). 같은 랜드마크(남산서울타워, 엠파이어스테이트빌딩, 에펠탑 등)는 6장 중 많아야 1장. 기본은 흰 벽·베이지·밝은 원목 톤에 창으로 들어오는 부드러운 낮의 자연광, 화면의 절반 가까이를 빈 공간으로 둔다. 저녁·밤 장면은 6장 중 많아야 1장. 황금빛 조명·샹들리에·꽃 장식 금지. 16:9 가로 구도.
- 관련 종목은 상장사만. stock_note 는 본문에 나온 비상장사 안내 한 줄만(예: 'SLL은 비상장사입니다.'). 없으면 빈 문자열.

JSON 만 출력:
{{"title": "...", "thumb_title": "첫 줄\n둘째 줄", "thumb_highlight": "...",
 "blocks": [{{"type": "p", "text": "261억 원."}}, {{"type": "p", "text": "..."}}, {{"type": "image", "no": 0}}, {{"type": "h", "text": "소제목"}}, {{"type": "p", "text": "..."}}, {{"type": "image", "no": 1}}],
 "images": [{{"no": 0, "kind": "shiho", "role": "썸네일", "filename": "...", "prompt": "...", "caption": "[이미지 1: ...]"}},
            {{"no": 1, "kind": "scene", "role": "장면", "filename": "...", "prompt": "...", "caption": "[이미지 2: ...]"}}],
 "stocks": [{{"name": "...", "market": "코스피|코스닥|NASDAQ|NYSE|TSE|Tadawul|...", "code": "...", "reason": "..."}}], "stock_note": "...",
 "sources": [{{"title": "...", "url": "..."}}], "tags": ["...", "..."]}}"""

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
  filename: 검색 핵심어 3~5개를 하이픈으로 이은 한국어 파일 이름(예: 고양이-겨울-잠자리-외풍-위치). caption: 그림을 설명하는 검색어 중심 한 줄(예: 외풍이 들지 않는 벽 쪽 방석에서 자는 고양이).
  0번 label 은 글 주제(예: '고양이 겨울 잠자리'). 본문 그림 label 은 바로 뒤 소제목의 핵심어.
- 그림 prompt 는 영어 한 단락, 사진 한 장을 단정적으로 묘사(한 상태, 한 동작). 고양이 주제면 고양이가 그 장면 속에서 한 동작을 하고,
  생활용품 주제면 그 물건이 놓인 집 안 장면. 화면 위쪽 1/4 은 글자를 얹을 수 있게 벽·하늘처럼 단순하게 비운다. 그림 속 글자·로고·숫자 금지.
- 그림끼리 겹치지 않게 한다: 그림마다 장소(거실 창가·주방·현관·침실 등), 거리(클로즈업·전신·방 전체), 고양이 동작을 서로 다르게 정한다. 같은 구도·같은 동작·같은 소품 배치를 되풀이하지 않는다.
  본문 그림 가운데 1장은 고양이 없이 물건만 크게 보여 준다(예: 정수기 클로즈업, 물그릇 두 개를 나란히 놓은 바닥).
- 태그 6개 안팎, 해시태그 없이 단어만.

JSON 만 출력:
{{"title": "...", "blocks": [{{"type": "image", "no": 0}}, {{"type": "p", "text": "도입"}}, {{"type": "image", "no": 1}}, {{"type": "h", "text": "소제목"}},
 {{"type": "p", "text": "..."}}, {{"type": "source", "text": "출처: 기관 안내 이름 (주소)"}}, {{"type": "h", "text": "오늘 밤 확인할 세 가지"}},
 {{"type": "check", "items": ["...", "...", "..."]}}, {{"type": "p", "text": "마무리"}}],
 "images": [{{"no": 0, "role": "썸네일", "label": "...", "filename": "...", "prompt": "...", "caption": "..."}}],
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
    """사무실 활동 기록(Threads 와 같은 상태 파일)에 짧게 남긴다. CINEPARK 글이면 블로그실 칸도 함께."""
    from . import storage
    try:
        st = storage.load_state()
        act(st, agent, text, status)
        if text.startswith("CINEPARK"):
            act(st, "cinepark", text, "working" if status == "working" else ("error" if status == "error" else "done"))
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
def _on_topic(hint: str, topic: dict) -> bool:
    """지정 주제의 핵심어(단어 앞 3글자)가 글감에 들어 있는지."""
    text = json.dumps(topic, ensure_ascii=False)
    keys = [w[:3] for w in re.split(r"\s+", hint.strip()) if len(w) >= 2]
    return not keys or keys[0] in text  # 첫 단어(주제의 중심)가 반드시 들어 있어야 함


def research(cfg: dict, blog: str, hint: str = "", avoid: list[str] | None = None) -> list[dict]:
    av = f"\n최근에 이미 쓴 글(같은 주제 피하기): {' / '.join(avoid[-20:])}\n" if avoid else ""
    fmt = {"hint": (f"\n★ Mr. MOON 지정 주제: \"{hint}\"\n이 지정 주제가 최우선이다. 세 글감 모두 이 주제 안에서 고른다. 다른 주제로 바꾸지 않는다.\n"
                    f"최근 2주 뉴스가 부족하면 기간을 넓혀(최근 1년 안의 발표·보도와 진행 중인 흐름) 이 주제를 다룬다.\n"
                    f"위의 기준 글감과 같은 주제여도 괜찮다. 지금 시점의 새 자료로 다시 쓴다.\n") if hint else ""}
    if "{avoid}" in PROMPTS[blog][0]:
        fmt["avoid"] = av
    else:
        fmt["hint"] += av
    sys_r = PROMPTS[blog][0].format(**fmt)
    data = _ask(cfg, sys_r, f"오늘은 {_now():%Y년 %m월 %d일}입니다. 글감 3개를 찾아 주세요.", search=True)
    return data.get("topics", [])[:3]


BTS_SCENES = [
    "오픈 세트로 지은 옛 거리(합판 건물 정면, 화면 가장자리로 뒤를 받친 나무 비계)에서 테이크 사이, 의상을 입은 배우 둘이 접이식 배우 의자에 앉아 대본을 보고, 분장팀이 한 배우의 앞머리를 고쳐 주며, 뒤에 모니터 카트",
    "실내 스튜디오의 아파트 세트에서 촬영 중, 세트 벽 하나를 떼어 낸 자리로 카메라와 달리가 들어가 있고 모니터 앞에 감독과 스크립터가 헤드폰을 끼고 앉아 있다",
    "그린스크린 스튜디오에서 세팅 중, 와이어 하네스를 찬 배우가 매트 위에서 스턴트 팀과 동작을 맞추고 크로마키 벽 앞에 조명 스탠드",
    "미니어처 세트 촬영 중, 큰 작업대 위의 정교한 마을 모형(이야기의 나라에 맞는 거리) 뒤로 하늘과 바다를 그린 대형 배경막이 지지대와 클램프에 걸려 있고, 카메라가 낮은 달리 레일에서 거리 높이로 찍으며 미술팀이 붓으로 작은 집을 칠한다",
    "비 내리는 밤 장면 세팅 중, 살수차가 골목 오픈 세트 위로 인공 비를 뿌리고 우비를 입은 스태프들이 카메라에 비닐 커버를 씌운다",
    "대형 수조 스튜디오에서 바다 장면 세팅 중, 파도 기계가 만든 물결 위에 작은 목선 한 척이 떠 있고 뒤로 거대한 하늘 배경막, 수조 가장자리에서 스태프가 물결 높이를 맞춘다",
    "사극 세트(기와 지붕 관아 마당)의 점심시간, 갑옷과 한복을 입은 배우들이 세트 뒤편 그늘에서 도시락을 먹고 투구가 의자 위에 놓여 있다",
    "LED 월 스튜디오에서 차량 촬영 중, 거대한 LED 벽에 밤의 고속도로 풍경이 흐르고 그 앞 회전판 위의 승용차 안에서 배우 둘이 연기하며 차 앞에 카메라 리그",
    "동물 배우 촬영 중, 세트 소파 위의 고양이 한 마리를 향해 트레이너가 간식을 든 손을 내밀고 카메라맨과 붐 오퍼레이터가 숨죽여 기다린다",
    "스튜디오 안에 지은 설산 세트에서 촬영 직전, 인공 눈 기계가 하얀 눈을 뿌리고 스티로폼 바위와 눈 덮인 산장 세트 뒤로 설산 배경막, 스태프가 빈 슬레이트를 든다",
    "모션캡처 스튜디오에서 촬영 중, 마커가 붙은 슈트를 입은 배우가 회색 격자 바닥 위에서 괴물 동작을 크게 하고 주변에 카메라 수십 대가 둘러서 있다",
    "야간 오픈 세트의 시장 골목에서 세팅 중, 조명팀이 대형 풍선 조명을 크레인으로 띄우고 엑스트라들이 의상을 입은 채 줄지어 대기한다",
]


def pick_bts() -> str:
    """BTS 촬영장 후보 셋을 무작위로 고른다(최근 5번 쓴 상황은 피함). 작가가 글에 맞는 하나를 고른다."""
    import random
    from . import storage
    key = "blog/bts_recent.json"
    try:
        recent = json.loads(storage._client().get_object(Bucket=storage._bucket(), Key=key)["Body"].read())
    except Exception:
        recent = []
    choices = [i for i in range(len(BTS_SCENES)) if i not in recent] or list(range(len(BTS_SCENES)))
    picks = random.sample(choices, min(3, len(choices)))
    try:
        storage.put_bytes(key, json.dumps((recent + picks[:1])[-5:]).encode(), "application/json")
    except Exception:
        pass
    return " / ".join(f"({n + 1}) {BTS_SCENES[i]}" for n, i in enumerate(picks))


def write(cfg: dict, blog: str, topic: dict) -> dict:
    bc = cfg["blog"]["blogs"][blog]
    n = bc["images"]
    extra = {"bts": pick_bts()} if "{bts}" in PROMPTS[blog][1] else {}
    if "{crew_character}" in PROMPTS[blog][1]:
        extra["crew_character"] = (bc.get("crew_character") or bc.get("character", "")).strip()
    sys_w = PROMPTS[blog][1].format(n=n, last=n - 1, character=bc.get("character", "").strip(), **extra)
    user = (f"오늘은 {_now():%Y년 %m월 %d일}입니다. 아래 글감으로 원고를 쓰세요. 필요하면 웹 검색으로 사실을 다시 확인하세요.\n"
            + ("편집장이 돌려보낸 원고입니다. editor_fix 의 지적을 모두 고쳐 새로 쓰세요.\n" if topic.get("editor_fix") else "")
            + json.dumps(topic, ensure_ascii=False))
    art = _ask(cfg, sys_w, user, search=True)
    art["images"] = sorted(art.get("images", []), key=lambda x: x.get("no", 0))[:n]
    return art


_MDLINK = re.compile(r"\s*\(?\[([^\]]+)\]\((https?://[^)]+)\)\)?")
_URL = re.compile(r"\s*\(?https?://\S+\)?")


def clean_url(u: str) -> str:
    """검색 도구가 붙이는 utm 꼬리표를 뗀다."""
    return re.sub(r"[?&]utm_[^&#]+", "", u or "").rstrip("?&")


_TAG = re.compile(r"\s((?:[^.!?\s][^.!?]{0,38}?(?:보도|발표|공고|공시))(?:\s·\s[^.!?]{1,38}?(?:보도|발표|공고|공시))*)$")
_AINOTE = re.compile(r"AI\s?로? ?재구성")


def tidy(art: dict) -> dict:
    """본문에 섞여 들어온 [사이트](주소) 링크와 맨 주소를 지우고, 출처 주소를 정리한다.
    한 소제목 안에서 같은 출처 꼬리표가 되풀이되면 첫 번째만 남긴다. AI 이미지 고지는 본문에서 빼고 끝에 한 번만 둔다."""
    seen: set[str] = set()
    keep = []
    for bl in art.get("blocks", []):
        if bl.get("type") == "h":  # 소제목 앞 ■ 는 게시용 텍스트에서 한 번만 붙인다
            bl["text"] = re.sub(r"^[■\s]+", "", bl.get("text", ""))
        if bl.get("type") == "h":
            seen = set()
        if bl.get("type") in ("p", "h", "memo"):
            t = _MDLINK.sub("", bl.get("text", ""))
            t = re.sub(r"\s{2,}", " ", _URL.sub("", t)).strip()
            if bl.get("type") == "p":
                if _AINOTE.search(t) and ("이미지" in t or "장면" in t) and len(t) < 120:
                    continue  # 고지 문구는 plain_text 끝에서 한 번만
                m = _TAG.search(t)
                if m:
                    tag = m.group(1).strip()
                    if tag in seen:
                        t = t[:m.start()].rstrip()
                    seen.add(tag)
            bl["text"] = t
        keep.append(bl)
    art["blocks"] = keep
    for x in art.get("sources", []):
        x["url"] = clean_url(x.get("url", ""))
    for x in art.get("stocks", []):
        x["reason"] = re.sub(r"\s{2,}", " ", _URL.sub("", _MDLINK.sub("", x.get("reason", "")))).strip()
    if art.get("stock_note"):
        art["stock_note"] = _URL.sub("", _MDLINK.sub("", art["stock_note"])).strip()
    return art


VERIFY = """당신은 CINEPARK 의 검수 담당입니다. 아래 기업 목록의 상장 여부, 거래소, 종목코드를 웹 검색으로 하나씩 확인해 고칩니다.
- 합병·사명 변경이 있었으면 지금 이름과 지금 코드로 고친다(예: 합병 후 새 법인).
- 한국 거래소는 '코스피' 또는 '코스닥', 해외는 NASDAQ, NYSE, TSE(도쿄증권거래소), Tadawul 처럼 쓴다.
- 비상장이거나 확인되지 않으면 listed 를 false 로 둔다.
JSON 만 출력: {"stocks": [{"name": "...", "market": "...", "code": "...", "listed": true, "fixed": "고친 점(없으면 빈 문자열)"}]}"""


def verify_stocks(cfg: dict, art: dict) -> list[str]:
    """관련 종목의 거래소·코드를 웹 검색으로 다시 확인. 고친 내용을 돌려준다."""
    stocks = art.get("stocks") or []
    if not stocks:
        return []
    data = _ask(cfg, VERIFY, json.dumps([{k: x.get(k) for k in ("name", "market", "code")} for x in stocks], ensure_ascii=False),
                search=True)
    checked = {i: v for i, v in enumerate(data.get("stocks", []))}
    out, notes = [], []
    for i, x in enumerate(stocks):
        v = checked.get(i)
        if not v:
            out.append(x)
            continue
        if not v.get("listed", True):
            notes.append(f"{x.get('name')} 비상장/미확인 → 제외")
            continue
        if v.get("fixed"):
            notes.append(f"{x.get('name')}: {v['fixed']}")
        x.update({"name": v.get("name") or x.get("name"), "market": v.get("market") or x.get("market"),
                  "code": v.get("code") or x.get("code")})
        out.append(x)
    art["stocks"] = sorted(out, key=lambda x: 0 if x.get("market") in ("코스피", "코스닥", "KOSPI", "KOSDAQ", "코넥스") else 1)  # 국내 종목 먼저
    return notes


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
    if art.get("editor_fix"):
        probs.append("편집장 반려: " + "; ".join(art["editor_fix"])[:200])
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
        _set_step(blog, f"그림 그리는 중 {im['no'] + 1}/{len(art['images'])}")
        try:
            kind = im.get("kind", "shiho" if refs else "scene")
            if kind == "card" or not im.get("prompt", "").strip():  # 정보 카드는 대표님이 에디터로 직접 만든다
                continue
            if kind == "crew":  # BTS 촬영장 일러스트: 구경 온 SHIHO 가 작게 나오므로 기준 그림을 함께 보낸다
                cstyle = bc.get("crew_style", "").strip()
                png = ai.render(cfg, im["prompt"] + (f" {cstyle}" if cstyle else ""), refs, cfg["blog"]["image_size"])
            elif kind == "shiho" or bc.get("labels"):
                prompt = im["prompt"] + (f" {style}" if style else "")
                png = ai.render(cfg, prompt, refs, cfg["blog"]["image_size"])
            else:  # 사람 없는 장소·사물: 캐릭터 기준 그림을 넣지 않아야 인물이 끼어들지 않는다
                sstyle = bc.get("scene_style", "").strip()
                png = ai.render(cfg, im["prompt"] + (f" {sstyle}" if sstyle else ""), [], cfg["blog"]["image_size"])
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


EDITOR = """당신은 네이버 영화 블로그 CINEPARK 의 편집장입니다. 그림을 그리기 전에 원고를 검토합니다(그림 비용이 크므로 부족한 원고는 여기서 돌려보냅니다).
아래 여섯 가지를 보고 하나라도 걸리면 ok=false.
1. 특정 작품이 중심인 글인데, 무엇에 관한 작품인지(인물·사건·장면)가 본문에 구체적으로 없다.
2. 제목·도입이 던진 질문('왜 1위?', '어떤 돈?')에 본문이 답하지 않는다.
3. '~은 다릅니다', '단정할 수 없습니다', '확인되지 않았습니다' 같은 유보 문장이 네 번 이상이거나, 소제목마다 유보로 끝난다.
4. 출처에 텔레그램·커뮤니티 모음 사이트·상표 출원 문서 같은 믿기 어려운 자료가 있다.
5. 영화잡지 기획기사가 아니라 속보 기사처럼 읽힌다: 뉴스 사실의 나열뿐이고, 관점(angle)과 배경(선례·비교·업계 구조·비평)이 없다.
6. 상장사와의 연결이 근거 없이 억지스럽거나(사업 경로 설명 없이 이름만 나열), 주가 전망·매수 권유처럼 읽히는 문장이 있다.
JSON 만 출력: {"ok": true|false, "fix": ["고칠 점 한 줄", "..."]}"""


def edit_check(cfg: dict, art: dict) -> dict:
    """편집장 검토. 웹 검색 없이 원고만 본다."""
    body = {"title": art.get("title"), "blocks": [b for b in art.get("blocks", []) if b.get("type") in ("p", "h")],
            "sources": art.get("sources", [])}
    try:
        return _ask(cfg, EDITOR, json.dumps(body, ensure_ascii=False), search=False)
    except Exception:
        return {"ok": True, "fix": []}


def make_package(cfg: dict, blog: str, hint: str = "", topic: dict | None = None,
                 mode: str = "실시간", for_date: str | None = None) -> str:
    """글감 → 원고 → 그림 → 점검 → 보관. 패키지 id 를 돌려준다."""
    name = cfg["blog"]["blogs"][blog]["name"]
    pid = f"{blog}_{_now():%Y%m%d_%H%M%S}"
    with _lock:
        b = load()
        t0 = _now().isoformat(timespec="seconds")
        b["running"][blog] = {"t": t0, "u": t0, "step": "글감 찾는 중", "mode": mode}
        save(b)
    try:
        if topic is None:
            _log("research", f"{name} 글감 찾는 중" + (f" (지정: {hint[:20]})" if hint else ""), "working")
            prev = [p["article"].get("title", "") for p in sorted(load()["packages"].values(), key=lambda x: x["made"])
                    if p["blog"] == blog]
            topics = research(cfg, blog, hint, prev)
            if hint and topics and not _on_topic(hint, topics[0]):
                _log("research", f"{name} 지정 주제와 다른 글감 → 다시 찾는 중", "working")
                topics = research(cfg, blog, hint + " (반드시 이 주제로)", prev) or topics
            if not topics:
                raise RuntimeError("글감을 찾지 못했습니다.")
            topic, others = topics[0], topics[1:]
            _log("research", f"{name} 글감 {len(topics)}개 → '{topic.get('title_idea', '')[:30]}'", "done")
        else:
            others = []
        _set_step(blog, "원고 쓰는 중")
        _log("writer", f"{name} 원고 쓰는 중: {topic.get('title_idea', '')[:30]}", "working")
        art = tidy(write(cfg, blog, topic))
        _log("writer", f"{name} 원고 완성: {art.get('title', '')[:30]}", "done")
        if blog == "cinepark":
            ed = edit_check(cfg, art)
            if not ed.get("ok", True):
                fix = ed.get("fix", [])
                _log("review", f"{name} 편집장 반려 → 다시 쓰기: {'; '.join(fix)[:120]}", "working")
                art = tidy(write(cfg, blog, dict(topic, editor_fix=fix)))
                ed = edit_check(cfg, art)
            if not ed.get("ok", True):
                art["editor_fix"] = ed.get("fix", [])
                _log("review", f"{name} 편집장 2차 반려 — 그림은 그리지 않습니다: {'; '.join(art['editor_fix'])[:120]}", "error")
            else:
                _log("review", f"{name} 편집장 통과", "done")
        if art.get("stocks"):
            _set_step(blog, "원고 쓰는 중 · 종목 확인")
            _log("review", f"{name} 관련 종목 거래소·코드 확인 중", "working")
            try:
                fixes = verify_stocks(cfg, art)
                art["stock_fixes"] = fixes
                _log("review", f"{name} 종목 확인 끝" + (f" — 고침: {'; '.join(fixes)[:80]}" if fixes else " — 이상 없음"), "done")
            except Exception as e:
                art["stock_fixes"] = [f"확인 실패: {str(e)[:80]}"]
        _set_step(blog, "그림 그리는 중")
        b = load()
        if art.get("editor_fix"):
            for im in art.get("images", []):
                im["error"] = "편집장 반려로 그림을 그리지 않음"
        else:
            draw_images(cfg, blog, pid, art, b)
        ok = sum(1 for im in art["images"] if im.get("r2_key"))
        _log("image", f"{name} 그림 {ok}/{len(art['images'])}장 완성", "done" if ok == len(art["images"]) else "error")
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
            b["running"][blog]["u"] = _now().isoformat(timespec="seconds")
            save(b)


def clear_running(blog: str) -> None:
    """멈춘 작업 표시 지우기 (화면 서버가 다시 시작되며 작업이 끊긴 경우)."""
    with _lock:
        b = load()
        b["running"].pop(blog, None)
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


def info_card(im: dict) -> bytes:
    """CINEPARK 정보·비교 카드: 짙은 남색 바탕, 흰 제목, 금색 숫자. 글자는 코드가 쓰므로 깨지지 않는다."""
    from PIL import Image, ImageDraw, ImageFont
    W, H = 1600, 900
    img = Image.new("RGB", (W, H), "#0F3B59")
    d = ImageDraw.Draw(img)
    f = lambda w, s: ImageFont.truetype(str(STATIC / f"Paperlogy-{w}.woff2"), s)

    def center(t, font, y, fill):
        d.text(((W - d.textlength(t, font=font)) / 2, y), t, font=font, fill=fill)

    d.rectangle((0, 0, W, 14), fill="#DBA12C")
    center("CINEPARK", f("7Bold", 34), 70, "#9fb4c2")
    head = (im.get("headline") or "").strip()
    rows = im.get("rows") or []
    if rows:
        center(head, f("8ExtraBold", 76), 150, "white")
        n = min(len(rows), 3)
        top, rh = 300, 170
        for i, r in enumerate(rows[:3]):
            y = top + i * rh
            d.rounded_rectangle((120, y, W - 120, y + rh - 26), radius=22, fill="#173f5f")
            left, right = (str(r[0]), str(r[1]) if len(r) > 1 else "")
            fl = f("8ExtraBold", 60)
            d.text((170, y + (rh - 26 - 70) / 2), left, font=fl, fill="#DBA12C")
            fr = f("6SemiBold", 44)
            while d.textlength(right, font=fr) > W - 640 and fr.size > 26:
                fr = f("6SemiBold", fr.size - 2)
            d.text((560, y + (rh - 26 - fr.size) / 2 - 4), right, font=fr, fill="white")
        _ = n
    else:
        center(head, f("7Bold", 64), 210, "white")
        big = (im.get("big") or "").strip()
        fb = f("8ExtraBold", 230)
        while d.textlength(big, font=fb) > W - 200 and fb.size > 80:
            fb = f("8ExtraBold", fb.size - 10)
        center(big, fb, 330, "#DBA12C")
        sub = (im.get("sub") or "").strip()
        fs = f("6SemiBold", 48)
        while d.textlength(sub, font=fs) > W - 200 and fs.size > 28:
            fs = f("6SemiBold", fs.size - 2)
        center(sub, fs, 660, "#F7FBFC")
    out = io.BytesIO()
    img.save(out, "JPEG", quality=92)
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
    y = h * 0.07  # 맨 위 띠에 둔다 (인물 얼굴은 그 아래)
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
        elif t == "p" and pkg.get("blog") == "cinepark":
            txt = bl.get("text", "")
            m = _TAG.search(txt)
            lines += [txt[:m.start()].rstrip(), f"({m.group(1).strip()})", ""] if m else [txt, ""]
        elif t in ("p", "memo", "link", "source"):
            lines += [bl.get("text", ""), ""]
        elif t == "check":
            lines += [f"□ {x}" for x in bl.get("items", [])] + [""]
    if pkg.get("blog") == "cinepark":
        lines += ["※ 이 글의 이미지는 기사 내용을 설명하기 위해 AI로 재구성한 장면입니다. 실제 행사나 계약 현장을 촬영한 사진이 아닙니다.", ""]
    if a.get("stocks"):
        lines += ["■ 관련 기업과 종목"]
        lines += [f"• {x.get('name', '')} | {x.get('market', '')} {x.get('code', '')}" for x in a["stocks"]]
        lines += [""]
        if a.get("stock_note"):
            lines += [a["stock_note"], ""]
        lines += ["※ 특정 종목의 매수·매도를 권유하는 글이 아닙니다.", ""]
    if a.get("sources") and not any(bl.get("type") == "source" for bl in a.get("blocks", [])):
        lines += ["참고 자료"] + [f"· {s.get('title', '')} {s.get('url', '')}" for s in a["sources"]] + [""]
    if a.get("tags"):
        tags = [t for t in a["tags"] if t.lstrip("#").upper() != "CINEPARK"] if pkg.get("blog") == "cinepark" else a["tags"]
        lines.append(" ".join("#" + t.lstrip("#").replace(" ", "") for t in tags))
    return "\n".join(lines).strip()


def safe_name(im: dict) -> str:
    """검색어 파일 이름 정리: 한글·영문·숫자·하이픈만, 60자 이내."""
    n = im.get("filename") or im.get("label") or im.get("role", "그림")
    n = re.sub(r"[\s_]+", "-", n.strip())
    n = re.sub(r"[^0-9A-Za-z가-힣\-]", "-", n)
    return re.sub(r"-{2,}", "-", n).strip("-")[:60] or "그림"


def images_zip(pkg: dict) -> bytes:
    from . import storage
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        for im in pkg["article"].get("images", []):
            if im.get("r2_key"):
                ext = im["r2_key"].rsplit(".", 1)[-1]
                z.writestr(f"{im['no'] + 1:02d}_{safe_name(im)}.{ext}", storage.get_bytes(im["r2_key"]))
        z.writestr("본문.txt", plain_text(pkg))
    return buf.getvalue()
