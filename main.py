"""AI OFFICE — 담당자들이 실제로 일하는 사무실 화면.

로컬 실행: streamlit run main.py
배포: Streamlit Cloud (Secrets 에 GitHub Actions 와 같은 비밀값 7개)
화면을 닫아도 일은 GitHub Actions 가 정해진 시각에 담당자들을 깨워 계속합니다.
"""
from __future__ import annotations

import datetime as dt
import html
import os

import streamlit as st

st.set_page_config(page_title="AI OFFICE", page_icon="static/favicon.svg", layout="wide")

# Streamlit Secrets → 환경변수 (업무 코드는 환경변수를 읽음)
for k in ["OPENAI_API_KEY", "THREADS_ACCESS_TOKEN", "THREADS_USER_ID", "R2_ENDPOINT", "R2_ACCESS_KEY_ID",
          "R2_SECRET_ACCESS_KEY", "R2_BUCKET", "GOOGLE_SA_JSON", "GH_TOKEN"]:
    try:
        if k in st.secrets and not os.environ.get(k):
            os.environ[k] = str(st.secrets[k])
    except Exception:
        pass

from office import planner as P  # noqa: E402
from office import run as R  # noqa: E402
from office.staff import DEPARTMENTS, STAFF, STAFF_BY_ID, act  # noqa: E402

NAVY, YELLOW = "#191970", "#ffcb05"
st.markdown(f"""
<style>
@font-face {{font-family:Paperlogy;src:url(app/static/Paperlogy-4Regular.woff2) format('woff2');font-weight:400}}
@font-face {{font-family:Paperlogy;src:url(app/static/Paperlogy-6SemiBold.woff2) format('woff2');font-weight:600}}
@font-face {{font-family:Paperlogy;src:url(app/static/Paperlogy-8ExtraBold.woff2) format('woff2');font-weight:800}}
html, body, [class*="css"], .stMarkdown, button, input, textarea {{font-family:Paperlogy, sans-serif}}
.eyebrow {{letter-spacing:.18em;font-size:.72rem;color:#8a8aa3}}
.eyebrow:before {{content:'';display:inline-block;width:18px;height:2px;background:{YELLOW};margin-right:8px;vertical-align:middle}}
.hero h1 {{font-weight:800;color:{NAVY};margin:.1rem 0 .2rem;letter-spacing:-.03em}}
.kpi {{border:1px solid #e6e6f0;border-radius:14px;padding:14px 16px;background:#fff}}
.kpi b {{font-size:1.7rem;color:{NAVY}}} .kpi small {{color:#8a8aa3}}
.card {{border:1px solid #e6e6f0;border-radius:14px;padding:12px 14px;background:#fff;min-height:118px;margin-bottom:10px}}
.card .nm {{font-weight:600;color:{NAVY}}} .card .rl {{font-size:.75rem;color:#8a8aa3}}
.card .tx {{font-size:.86rem;margin-top:6px;color:#2b2b45}} .card .tm {{font-size:.7rem;color:#a0a0b5}}
.dot {{display:inline-block;width:9px;height:9px;border-radius:50%;margin-right:6px;vertical-align:middle}}
.working {{background:{YELLOW};box-shadow:0 0 0 4px #ffcb0533}} .done {{background:#2fbf71}}
.error {{background:#e5484d}} .idle {{background:#c9c9d6}}
.spin {{display:inline-block;width:18px;height:18px;border:3px solid #DBA12C33;border-top-color:#DBA12C;border-radius:50%;
animation:sp .8s linear infinite;vertical-align:-3px;margin-right:8px}}
@keyframes sp {{to{{transform:rotate(360deg)}}}}
.prog {{border:1px solid #C8D6DD;border-radius:12px;padding:12px 14px;background:#F7FBFC;margin:6px 0 10px}}
.prog .top {{font-weight:700;color:#0F3B59}} .prog .el {{float:right;font-weight:400;color:#5b7486;font-variant-numeric:tabular-nums}}
.steps {{display:flex;gap:6px;margin-top:10px}} .steps div {{flex:1;height:6px;border-radius:3px;background:#e3eaee}}
.steps div.on {{background:#DBA12C}} .steps div.now {{background:linear-gradient(90deg,#DBA12C 0,#f3d48a 50%,#DBA12C 100%);
background-size:200% 100%;animation:fl 1.2s linear infinite}}
@keyframes fl {{to{{background-position:-200% 0}}}}
.labels {{display:flex;gap:6px;margin-top:4px;font-size:.72rem;color:#8aa0ae}} .labels span {{flex:1}}
</style>""", unsafe_allow_html=True)


@st.cache_data(ttl=30, show_spinner=False)
def load_state_cached() -> dict:
    if os.environ.get("OFFICE_DEMO"):  # 화면 점검용 데모 기록
        import json
        return json.load(open("tests/demo_state.json", encoding="utf-8"))
    try:
        return R._state()
    except Exception as e:
        return {"_error": str(e)}


def fresh_state() -> dict:
    load_state_cached.clear()
    return R._state()


def save(state: dict) -> None:
    from office import storage
    storage.save_state(state)
    load_state_cached.clear()


@st.cache_data(ttl=3000, show_spinner=False)
def img_url(key: str) -> str:
    from office import storage
    return storage.signed_url(key, 3600)


def ago(iso: str | None) -> str:
    if not iso:
        return ""
    t = dt.datetime.fromisoformat(iso)
    m = int((P.now_kst() - t).total_seconds() // 60)
    return "방금" if m < 1 else f"{m}분 전" if m < 60 else f"{m // 60}시간 전" if m < 1440 else t.strftime("%m/%d %H:%M")


state = load_state_cached()
connected = "_error" not in state

with st.sidebar:
    st.markdown(f"<div style='font-weight:800;font-size:1.4rem;color:{NAVY}'>AI<br>OFFICE<span style='color:{YELLOW}'>.</span></div>",
                unsafe_allow_html=True)
    st.caption("Mr. MOON · 개인 워크스페이스")
    page = st.radio("WORKSPACE", ["오피스", "Threads 데스크", "CINEPARK 데스크", "리뷰&리뷰 데스크", "설정 · 연결"],
                    label_visibility="collapsed")
    st.divider()
    st.caption("🟡 작업 중  🟢 완료  🔴 문제  ⚪ 대기")
    if st.button("새로고침", use_container_width=True):
        load_state_cached.clear()
        st.rerun()

if not connected:
    st.error(f"사무실 기록(R2)에 연결하지 못했습니다. '설정 · 연결'에서 비밀값을 확인해 주세요.\n\n{state['_error']}")
    state = {"history": [], "queue": {}, "agent_now": {}, "agent_log": []}

queue = state.get("queue", {})
today = P.now_kst().date().isoformat()


# ───────────────────────── 업무 지시서 ─────────────────────────
def server_ready() -> bool:
    return bool(os.environ.get("GH_TOKEN", "").strip())


def give_order(job_type: str, args: dict, who: str, label: str) -> None:
    """버튼 → 지시서 → GitHub 서버. 창을 닫아도 서버가 끝까지 처리한다."""
    from office import jobs
    job, kicked = jobs.order(job_type, args, "Mr. MOON")
    s0 = fresh_state()
    act(s0, "shiho", f"지시서 {job['id']}: {label} → {STAFF_BY_ID[who][1]}", "done")
    act(s0, who, f"{label} 대기 (지시서 {job['id']})", "working")
    save(s0)
    jobs_cached.clear()
    st.toast(f"지시서를 넘겼습니다: {label}. 창을 닫으셔도 서버가 처리합니다." if kicked else
             f"지시서를 남겼습니다: {label}. 서버 신호가 닿지 않아 한 시간 안의 순찰 때 처리됩니다.")


@st.cache_data(ttl=10, show_spinner=False)
def jobs_cached() -> list[dict]:
    from office import jobs
    if os.environ.get("OFFICE_DEMO"):
        return []
    try:
        return jobs.recent(12)
    except Exception:
        return []


@st.fragment(run_every=10)
def jobs_panel() -> None:
    """오른쪽 SHIHO 대화창 아래: 업무 지시서 현황 (10초마다 새로 고침)."""
    jobs_cached.clear()
    rows = jobs_cached()
    st.markdown("<div class='eyebrow'>업무 지시서</div>", unsafe_allow_html=True)
    if not rows:
        st.caption("아직 지시서가 없습니다. 데스크 버튼이나 SHIHO에게 지시하면 여기에 쌓이고, 서버가 처리합니다.")
        return
    mark = {"pending": "<span class='spin'></span>대기", "running": "<span class='spin'></span>진행 중",
            "done": "✅ 완료", "error": "⚠️ 실패"}
    html_rows = []
    for j in rows[:8]:
        arg = j["args"].get("slot") or j["args"].get("hint") or j["args"].get("blog") or ""
        html_rows.append(f"<div style='display:flex;justify-content:space-between;gap:8px;padding:6px 0;border-bottom:1px solid #eef3f5;font-size:.84rem'>"
                         f"<span><b>{html.escape(j['label'])}</b> <span style='color:#8aa0ae'>{html.escape(str(arg))[:24]}</span><br>"
                         f"<span style='color:#8aa0ae;font-size:.74rem'>{j['created'][5:16].replace('T', ' ')} · {html.escape(j.get('result') or j.get('step', ''))[:40]}</span></span>"
                         f"<span style='white-space:nowrap'>{mark.get(j['status'], j['status'])}</span></div>")
    st.markdown("".join(html_rows), unsafe_allow_html=True)


# ───────────────────────── SHIHO 대화 ─────────────────────────
def shiho_chat(box_height: int) -> None:
    """Mr. MOON 은 SHIHO 에게만 지시합니다. 오피스 화면 오른쪽에 붙어 있습니다."""
    st.markdown("<div class='eyebrow'>SHIHO · 대표 비서</div>", unsafe_allow_html=True)
    box = st.container(height=box_height)
    msgs = state.get("messages", [])[-30:]
    with box:
        if not msgs:
            st.caption("지시는 SHIHO에게만 하시면 됩니다. 업무로 바꿔 담당자에게 나눠 맡기고 결과를 알려 드립니다.")
        for m in msgs:
            with st.chat_message("user" if m["from"] == "moon" else "assistant",
                                 avatar="🧑‍💼" if m["from"] == "moon" else "📋"):
                st.write(m["text"])
    order = st.chat_input("SHIHO에게 지시 (예: 다음 고양이는 랙돌로)")
    if order:
        from office import shiho
        s = fresh_state()
        s.setdefault("messages", []).append({"t": P.now_kst().isoformat(), "from": "moon", "text": order})
        act(s, "shiho", f"Mr. MOON 지시 확인: {order[:40]}", "working")
        with st.spinner("SHIHO가 지시를 확인하고 담당자에게 나누는 중입니다…"):
            try:
                plan = shiho.interpret(R.eff_cfg(s), order, today)
                results = shiho.execute(s, R.CFG, plan["actions"], R)
                reply = plan["reply"] + ("\n\n" + "\n".join(f"- {r}" for r in results) if results else "")
            except Exception as e:
                reply = f"지시를 처리하지 못했습니다. 개발 담당에게 기록을 남겼습니다. ({str(e)[:150]})"
                act(s, "dev", f"SHIHO 지시 처리 실패: {str(e)[:150]}", "error")
        s["messages"].append({"t": P.now_kst().isoformat(), "from": "shiho", "text": reply})
        act(s, "shiho", f"지시 처리 완료: {order[:30]}", "done")
        save(s)
        st.rerun()


@st.fragment(run_every=15)
def office_view() -> None:
    """사무실 그림: 15초마다 최신 기록으로 다시 그림 (작업 중 표시가 살아 움직임)."""
    from office import floorplan
    load_state_cached.clear()
    s_now = load_state_cached()
    if "_error" in s_now:
        s_now = state
    office_html = floorplan.render(s_now, R.CFG["slots"])
    if hasattr(st, "iframe"):
        st.iframe(office_html, height="content")
    else:  # 예전 Streamlit
        import streamlit.components.v1 as components
        components.html(office_html, height=1250, scrolling=True)


# ───────────────────────── 오피스 ─────────────────────────
if page == "오피스":
    st.markdown("<div class='hero'><div class='eyebrow'>BLUE JEANS PICTURES</div><h1>AI OFFICE</h1></div>",
                unsafe_allow_html=True)
    left, right = st.columns([2.3, 1], gap="medium")
    with left:
        office_view()
    with right:
        shiho_chat(520)
        jobs_panel()


# ───────────────────────── Threads 데스크 ─────────────────────────
elif page == "Threads 데스크":
    st.markdown("<div class='hero'><div class='eyebrow'>TURNER BRO · THREADS</div><h1>Threads 데스크</h1></div>", unsafe_allow_html=True)
    st.caption("승인 없이 정해진 시각에 자동 게시됩니다. 마음에 안 드는 것만 고치거나 빼면 됩니다.")
    t1, t2 = st.tabs(["게시 예정", "게시 기록"])
    with t1:
        keys = sorted(k for k, v in queue.items() if v.get("status") == "ready")
        if not keys:
            st.info("게시 예정 재고가 없습니다. 아래 버튼이나 매일 21시 자동 생성으로 채워집니다.")
        if st.button("지금 3일치 재고 채우기 (SHIHO에게 지시)", type="primary"):
            if server_ready():
                give_order("produce", {}, "image", "Threads 재고 채우기")
            else:
                with st.spinner("담당자들이 그림과 멘트를 만드는 중입니다. 한 건에 1~2분 걸립니다."):
                    R.produce()
            load_state_cached.clear()
            st.rerun()
        cols = st.columns(3)
        for i, k in enumerate(keys):
            v = queue[k]
            with cols[i % 3]:
                with st.container(border=True):
                    try:
                        st.image(img_url(v["r2_key"]), use_container_width=True)
                    except Exception:
                        st.caption("이미지를 불러오지 못했습니다.")
                    label = v.get("breed_name") or v.get("breed") or v.get("city") or ""
                    extra = f" · {v.get('scene_name')}" if v.get("scene_name") else ""
                    st.markdown(f"**{k[5:10].replace('-', '/')} {k[-4:-2]}:{k[-2:]}** · {'고양이' if v['kind'] == 'cat' else '여행'} · {label}{extra}")
                    if v.get("problems"):
                        st.warning("검수 주의: " + ", ".join(v["problems"]))
                    opts = [v["caption"]] + [o for o in v.get("options", []) if o != v["caption"]]
                    pick = st.radio("멘트", opts, key=f"r_{k}", label_visibility="collapsed")
                    new = st.text_area("고치기", value=pick, key=f"t_{k}", height=70, label_visibility="collapsed")
                    b1, b2, b3 = st.columns(3)
                    if b1.button("저장", key=f"s_{k}"):
                        s = fresh_state()
                        it = s["queue"][k]
                        if new.strip() != it["caption"]:
                            s.setdefault("caption_edits", []).append({"t": P.now_kst().isoformat(), "slot": k,
                                                                      "before": it["caption"], "after": new.strip()})
                            it["caption"] = new.strip()
                            act(s, "writer", f"{k} 멘트를 Mr. MOON 수정본으로 교체", "done")
                            save(s)
                        st.rerun()
                    if b2.button("빼고 새로", key=f"x_{k}") and server_ready():
                        give_order("remake", {"slot": k}, "image", f"{k[5:10]} {k[-4:-2]}:{k[-2:]} 다시 만들기")
                        st.rerun()
                    elif st.session_state.get(f"x_{k}") and not server_ready():
                        with st.spinner("새로 만드는 중…"):
                            s = fresh_state()
                            s["queue"][k]["status"] = "skipped"
                            slot = next(sl for sl in R.CFG["slots"] if sl["time"].replace(":", "") == k[-4:])
                            s["queue"][k] = R.make_item(s, k, slot)
                            save(s)
                        st.rerun()
                    if b3.button("지금 게시", key=f"p_{k}") and server_ready():
                        give_order("post_now", {"slot": k}, "channel", f"{k[5:10]} {k[-4:-2]}:{k[-2:]} 지금 게시")
                        st.rerun()
                    elif st.session_state.get(f"p_{k}") and not server_ready():
                        with st.spinner("Threads에 올리는 중…"):
                            s = fresh_state()
                            R.publish_item(s, k)
                        st.rerun()
    with t2:
        for h in reversed(state.get("history", [])[-40:]):
            if h.get("permalink"):
                st.markdown(f"`{h.get('slot', h.get('date'))}` {h.get('caption', '')} — [게시물]({h['permalink']})")
        if not any(h.get("permalink") for h in state.get("history", [])):
            st.caption("아직 이 사무실에서 게시한 기록이 없습니다.")


# ───────────────────────── 블로그 데스크 (CINEPARK · 리뷰&리뷰) ─────────────────────────
DAYS = ["월", "화", "수", "목", "금", "토", "일"]


@st.cache_data(ttl=20, show_spinner=False)
def blog_state_cached() -> dict:
    from office import blog
    if os.environ.get("OFFICE_DEMO"):  # 화면 점검용
        import json
        if os.path.exists("tests/demo_blog.json"):
            return json.load(open("tests/demo_blog.json", encoding="utf-8"))
        return {"packages": {}, "schedule": {}, "running": {}}
    try:
        return blog.load()
    except Exception as e:
        return {"_error": str(e), "packages": {}, "schedule": {}, "running": {}}


@st.cache_data(ttl=600, show_spinner=False)
def blog_zip(pid: str, blog_id: str) -> bytes:
    from office import blog
    return blog.images_zip(blog_state_cached()["packages"][pid])


STEPS = ["글감 찾는 중", "원고 쓰는 중", "그림 그리는 중"]


def progress_html(run: dict) -> str:
    step = run.get("step", "")
    idx = next((i for i, x in enumerate(STEPS) if step.startswith(x)), 0)
    t0 = dt.datetime.fromisoformat(run["t"])
    sec = int((P.now_kst() - t0).total_seconds())
    bars = "".join(f"<div class='{'on' if i < idx else 'now' if i == idx else ''}'></div>" for i in range(len(STEPS)))
    return (f"<div class='prog'><div class='top'><span class='spin'></span>{html.escape(step)}"
            f"<span class='el'>{sec // 60}분 {sec % 60:02d}초째</span></div>"
            f"<div class='steps'>{bars}</div><div class='labels'>" + "".join(f"<span>{x}</span>" for x in STEPS) + "</div></div>")


@st.fragment(run_every=8)
def progress_box(blog_id: str) -> None:
    """만드는 동안 8초마다 스스로 새로 고침. 끝나면 데스크 전체를 다시 그려 패키지를 보여 준다."""
    blog_state_cached.clear()
    run = blog_state_cached().get("running", {}).get(blog_id)
    jobs_cached.clear()
    waiting = [j for j in jobs_cached() if j["type"] == "blog_make" and j["args"].get("blog") == blog_id
               and j["status"] in ("pending", "running")]
    if not run and waiting:
        st.session_state[f"was_{blog_id}"] = True
        st.markdown(f"<div class='prog'><div class='top'><span class='spin'></span>서버가 지시서를 받는 중"
                    f"<span class='el'>지시서 {waiting[0]['id']}</span></div></div>", unsafe_allow_html=True)
        st.caption("보통 1분 안에 서버가 일을 시작합니다. 창을 닫으셔도 됩니다.")
        return
    if run:
        st.session_state[f"was_{blog_id}"] = True
        st.markdown(progress_html(run), unsafe_allow_html=True)
        idle = (P.now_kst() - dt.datetime.fromisoformat(run.get("u") or run["t"])).total_seconds()
        if idle > 720:  # 12분 넘게 단계가 그대로면 끊긴 작업
            st.warning(f"{int(idle // 60)}분째 단계가 바뀌지 않습니다. 화면 서버가 다시 시작되면서 작업이 끊긴 것입니다.")
            if st.button("멈춘 작업 정리", key=f"clr_{blog_id}"):
                from office import blog
                blog.clear_running(blog_id)
                st.session_state.pop(f"was_{blog_id}", None)
                blog_state_cached.clear()
                st.rerun(scope="app")
        else:
            st.caption("자동으로 새로 고쳐집니다. 서버에서 처리 중이라 창을 닫으셔도 됩니다.")
    elif st.session_state.pop(f"was_{blog_id}", False):
        st.rerun()


def blog_desk(blog_id: str, eyebrow: str, title: str, intro: str) -> None:
    from office import blog
    bc = R.CFG["blog"]["blogs"][blog_id]
    st.markdown(f"<div class='hero'><div class='eyebrow'>{eyebrow}</div><h1>{title}</h1></div>", unsafe_allow_html=True)
    st.caption(intro)
    b = blog_state_cached()
    if "_error" in b:
        st.error(f"패키지 보관소를 읽지 못했습니다: {b['_error']}")

    c1, c2 = st.columns([1.3, 1], gap="large")
    with c1:
        st.markdown("**실시간** · 지금 바로 만들기")
        hint = st.text_input("주제 지정 (비우면 리서치 담당이 고릅니다)", key=f"hint_{blog_id}",
                             placeholder="예: 넷플릭스 한국 오리지널 제작비" if blog_id == "cinepark" else "예: 겨울 전기요")
        run = b.get("running", {}).get(blog_id)
        waiting = [j for j in jobs_cached() if j["type"] == "blog_make" and j["args"].get("blog") == blog_id
                   and j["status"] in ("pending", "running")]
        if run or waiting:
            progress_box(blog_id)
        elif st.button(f"지금 {bc['name']} 패키지 만들기", type="primary", key=f"go_{blog_id}"):
            s0 = fresh_state()
            act(s0, "shiho", f"Mr. MOON 지시: {bc['name']} 패키지 지금 만들기", "done")
            save(s0)
            if server_ready():
                give_order("blog_make", {"blog": blog_id, "hint": hint.strip()}, "research", f"{bc['name']} 패키지")
            else:
                blog.start_background(R.CFG, blog_id, hint.strip())
            blog_state_cached.clear()
            st.rerun()
    with c2:
        st.markdown("**예약** · 전날 21:00에 미리 만들어 둡니다")
        sc = blog.schedule_of(b, R.CFG, blog_id)
        on = st.toggle("예약 켜기", value=sc.get("on", True), key=f"on_{blog_id}")
        days = st.multiselect("요일", DAYS, default=[DAYS[d] for d in sc.get("days", [])], key=f"d_{blog_id}")
        if st.button("예약 저장", key=f"sv_{blog_id}"):
            fresh = blog.load()
            fresh["schedule"][blog_id] = {"on": on, "days": sorted(DAYS.index(d) for d in days)}
            blog.save(fresh)
            blog_state_cached.clear()
            st.success("예약을 저장했습니다.")

    errs = [e for e in b.get("errors", []) if e.get("blog") == blog_id][-1:]
    if errs and not b.get("running", {}).get(blog_id):
        st.warning(f"최근 실패 ({errs[0]['t'][5:16]}): {errs[0]['error'][:200]}")

    st.divider()
    pkgs = sorted((p for p in b.get("packages", {}).values() if p["blog"] == blog_id), key=lambda p: p["made"], reverse=True)
    if not pkgs:
        st.caption("아직 만든 패키지가 없습니다.")
    for i, p in enumerate(pkgs[:15]):
        a = p["article"]
        with st.expander(f"{p['date'][5:].replace('-', '/')} · {p['mode']} · {a.get('title', '(제목 없음)')}", expanded=(i == 0)):
            st.markdown(f"<h3 style='text-align:center;color:{NAVY}'>{html.escape(a.get('title', ''))}</h3>", unsafe_allow_html=True)
            if p.get("problems"):
                st.warning("검수 주의: " + ", ".join(p["problems"]))
            if a.get("stock_fixes"):
                st.caption("검수 담당 종목 확인: " + " / ".join(a["stock_fixes"]))
            ims = [im for im in a.get("images", [])]
            cols = st.columns(3)
            for j, im in enumerate(ims):
                with cols[j % 3]:
                    if im.get("r2_key"):
                        try:
                            st.image(img_url(im["r2_key"]), use_container_width=True)
                        except Exception:
                            st.caption("그림을 불러오지 못했습니다.")
                    else:
                        st.caption(f"그림 없음: {im.get('error', '')[:80]}")
                    st.caption(f"그림 {im['no'] + 1} · {im.get('role', '본문')} — {im.get('caption', '')}")
            st.markdown("**본문** (오른쪽 위 복사 버튼 → 네이버 에디터에 붙여 넣기, 【그림 n】 자리에 그림을 넣으시면 됩니다)")
            st.code(blog.plain_text(p), language=None, wrap_lines=True)
            try:
                st.download_button("그림 + 본문 묶음 받기 (ZIP)", data=blog_zip(p["id"], blog_id),
                                   file_name=f"{bc['name']}_{p['id']}.zip", mime="application/zip", key=f"z_{p['id']}")
            except Exception as e:
                st.caption(f"묶음을 만들지 못했습니다: {e}")
            if p.get("others"):
                st.markdown("**다른 글감**")
                for k, t in enumerate(p["others"]):
                    oc1, oc2 = st.columns([4, 1])
                    oc1.markdown(f"[{t.get('axis', '')}] **{t.get('question') or t.get('title_idea', '')}** — {t.get('why_now') or t.get('hook_question', '')}")
                    if oc2.button("이걸로 만들기", key=f"o_{p['id']}_{k}"):
                        if server_ready():
                            give_order("blog_make", {"blog": blog_id, "hint": "", "topic": t}, "research",
                                       f"{bc['name']} 패키지 (다른 글감)")
                        else:
                            blog.start_background(R.CFG, blog_id, "", t)
                        blog_state_cached.clear()
                        st.rerun()


if page == "CINEPARK 데스크":
    blog_desk("cinepark", "CINEPARK · 영화잡지", "CINEPARK 데스크",
              "리서치 담당이 최근 세계 영화계 뉴스로 글감을 고르고, 작가가 작법 7원칙대로 원고를, 이미지 담당이 썸네일 1장과 본문 그림 5장을 만듭니다. 업로드는 대표님이 직접 하십니다.")
elif page == "리뷰&리뷰 데스크":
    blog_desk("review", "리뷰&리뷰 · 쿠팡파트너스", "리뷰&리뷰 데스크",
              "지금 많이 찾는 생활 상품군을 골라 비교 정보형 원고와 그림 3장을 만듭니다. 첫 줄에 쿠팡파트너스 대가성 문구가 들어가고, 쿠팡 링크와 대표님 실사용 메모 자리는 비워 둡니다.")


# ───────────────────────── 설정 · 연결 ─────────────────────────
if page == "설정 · 연결":
    st.markdown("<div class='hero'><div class='eyebrow'>SETTINGS</div><h1>설정 · 연결</h1></div>", unsafe_allow_html=True)
    if st.button("연결 점검 실행", type="primary"):
        import contextlib
        import io
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            try:
                R.selftest()
            except SystemExit:
                pass
        st.code(buf.getvalue() or "결과 없음")
    cfg = R.CFG
    st.subheader("Threads 예약표")
    st.table([{"시각": s["time"], "내용": "여행" if s["kind"] == "travel" else "고양이"} for s in cfg["slots"]])
    st.subheader("고양이 품종")
    st.write(" · ".join(b["name"] for b in cfg["breeds"]))
    st.subheader("장면 (집사 공감 순간)")
    st.write(" · ".join(s["name"] for s in cfg["scenes"]))
    st.subheader("멘트 금지어")
    st.write(", ".join(cfg["caption"]["banned"]))
    st.caption("바꾸려면 GitHub 의 config.yaml 을 고치면 다음 작업부터 반영됩니다.")
