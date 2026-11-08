"""SHIHO(총괄): GitHub Actions 가 부르는 입구.

python -m office.run produce   # 21시: 앞으로 3일치 재고 채우기
python -m office.run post      # 09:30/12:30/16:30/19:30: 지금 슬롯 게시
python -m office.run refresh   # 매주: Threads 토큰 갱신
python -m office.run selftest  # 연결 점검 (키·드라이브·R2·Threads·모델 목록)
python -m office.run skip 2026-11-05_1230   # 특정 게시물 빼고 다시 만들기
"""
from __future__ import annotations

import datetime as dt
import os
import sys
import traceback
from pathlib import Path

import yaml

from . import planner as P
from .staff import act

ROOT = Path(__file__).resolve().parent.parent
CFG = yaml.safe_load((ROOT / "config.yaml").read_text(encoding="utf-8"))


def log(msg: str) -> None:
    print(msg, flush=True)
    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        with open(summary, "a", encoding="utf-8") as f:
            f.write(msg + "\n\n")


def _state() -> dict:
    from . import storage
    st = storage.load_state()
    st.setdefault("history", list(CFG.get("seed_history", [])))
    st.setdefault("queue", {})
    st.setdefault("used_photos", [])
    st.setdefault("images_made", {})
    return st


def _token(st: dict) -> str:
    return st.get("threads_token") or os.environ["THREADS_ACCESS_TOKEN"].strip()


def eff_cfg(st: dict) -> dict:
    """config.yaml + SHIHO 가 받은 지시(설정 덮어쓰기) + Mr. MOON 이 고친 멘트(말투 예시)."""
    import copy
    c = copy.deepcopy(CFG)
    s = st.get("settings", {})
    ex = set(s.get("exclude_breeds", []))
    c["breeds"] = [b for b in c["breeds"] if b["id"] not in ex] or c["breeds"]
    c["caption"]["banned"] = c["caption"]["banned"] + s.get("banned_extra", [])
    edits = [e["after"] for e in st.get("caption_edits", [])[-20:]]
    c["caption"]["examples"] = c["caption"]["examples"] + s.get("examples_extra", []) + edits
    return c


def _travel_subject(city: str) -> str:
    return f"여행 그림. {city} 사진을 펜 수채화로 다시 그린 것. 그림 속 장소를 보고 멘트를 쓰세요. 연도나 햇수는 쓰지 마세요."


def recent_captions(st: dict, kind: str, exclude: str = "", n: int = 30) -> list[str]:
    """같은 종류(고양이/여행)의 최근 멘트. 게시된 것 + 대기 중인 것."""
    rows = [h for h in st.get("history", []) if h.get("kind") == kind and h.get("caption")]
    rows += [v for k, v in sorted(st.get("queue", {}).items())
             if k != exclude and v.get("kind") == kind and v.get("status") != "skipped" and v.get("caption")]
    seen, out = set(), []
    for r in rows:
        if r["caption"] not in seen and r.get("slot") != exclude:
            seen.add(r["caption"])
            out.append(r["caption"])
    return out[-n:]


def fix_caption(st: dict, key: str) -> bool:
    """게시 전 멘트를 현재 규칙으로 다시 검사. 어긋나면 다른 안으로, 없으면 멘트만 새로 쓴다.
    Mr. MOON 이 직접 고친 멘트는 건드리지 않는다. 바꿨으면 True."""
    item = st["queue"][key]
    cfg = eff_cfg(st)
    recent = recent_captions(st, item["kind"], exclude=key)
    if not P.caption_problems(item.get("caption", ""), cfg, recent):
        return False
    if any(e.get("slot") == key for e in st.get("caption_edits", [])):
        return False
    cap, probs = P.choose_caption(item.get("options", []), cfg, recent)
    if probs:
        from . import ai, storage
        subject = (_travel_subject(item.get("city", "")) if item["kind"] == "travel"
                   else f"고양이 그림. 품종: {item.get('breed_name', '')}. 장면: {item.get('scene_name', '')}.")
        act(st, "writer", f"{key} 규칙에 맞게 멘트 다시 쓰는 중", "working")
        options = ai.captions(cfg, subject, storage.get_bytes(item["r2_key"]), recent)
        cap, probs = P.choose_caption(options, cfg, recent)
        if probs:
            act(st, "review", f"{key} 새 멘트도 검사 주의: {', '.join(probs)}", "error")
            return False
        item["options"] = options
    old = item["caption"]
    item["caption"], item["problems"] = cap, []
    act(st, "review", f"{key} 멘트 교체 (규칙 위반: {old}) → {cap}", "done")
    return True


def save_and_produce(state: dict) -> None:
    from . import storage
    storage.save_state(state)
    produce()
    state.clear()
    state.update(_state())


def _budget_ok(st: dict, today: str) -> bool:
    return st["images_made"].get(today, 0) < CFG["daily_image_limit"]


def make_item(st: dict, key: str, slot: dict) -> dict:
    """한 슬롯의 게시물(그림 + 멘트)을 만든다."""
    from . import ai, drive, storage
    date = dt.date.fromisoformat(key[:10])
    plan_history = st["history"] + [v for k, v in st["queue"].items() if k != key and v.get("status") != "skipped"]
    cfg = eff_cfg(st)
    try:
        if slot["kind"] == "cat":
            breed, scene = P.pick_cat(cfg, plan_history, date)
            want = st.get("settings", {}).pop("next_cat", None)  # SHIHO 가 받은 '다음 고양이' 지정
            if want:
                breed = next((b for b in CFG["breeds"] if b["id"] == want.get("breed")), breed)
                scene = next((x for x in CFG["scenes"] if x["id"] == want.get("scene")), scene)
            label = f"{breed['name']} · {scene['name']}"
            act(st, "shiho", f"{key} 고양이 배정: {label}", "done")
            act(st, "image", f"{label} 그리는 중", "working")
            refs = [drive.download(fid) for fid in CFG["google_drive"]["cat_reference_files"]]
            png = ai.draw(CFG, P.cat_prompt(CFG, breed, scene), refs)
            subject = f"고양이 그림. 품종: {breed['name']}. 장면: {scene['name']}."
            item = {"kind": "cat", "breed": breed["id"], "breed_name": breed["name"],
                    "scene": scene["id"], "scene_name": scene["name"]}
        else:
            photos = drive.travel_photos(CFG["google_drive"]["travel_root_folder"])
            used = set(st["used_photos"]) | {v.get("photo_id") for k, v in st["queue"].items() if k != key}
            photo = P.pick_travel(photos, plan_history, used)
            if not photo:
                raise RuntimeError("안 쓴 여행 원본 사진이 없습니다. 01.원본 사진 폴더에 사진을 추가해 주세요.")
            label = f"{photo['year']} {photo['city']}".strip()
            act(st, "shiho", f"{key} 여행 배정: {label} ({photo['name']})", "done")
            act(st, "image", f"{label} 사진을 펜 수채화로 바꾸는 중", "working")
            src = drive.download(photo["id"])
            refs = [drive.download(fid) for fid in CFG["google_drive"]["travel_reference_files"]]
            png = ai.draw(CFG, CFG["travel_style"], [src] + refs)
            subject = _travel_subject(photo["city"])
            item = {"kind": "travel", "city": photo["city"], "photo_id": photo["id"], "photo_name": photo["name"]}
        act(st, "image", f"{label} 그림 완성", "done")
        act(st, "writer", f"{label} 멘트 3안 쓰는 중", "working")
        recent = recent_captions(st, item["kind"], exclude=key)
        options = ai.captions(cfg, subject, png, recent)
        act(st, "writer", f"{label} 멘트 3안 완성", "done")
        if item["kind"] == "travel" and options:
            # 여행은 혼잣말 / 현지 공감 / 말 걸기를 날마다 번갈아 먼저 고른다
            n = (date.toordinal() * 2 + (0 if slot["time"] < "12:00" else 1)) % len(options)
            options = options[n:] + options[:n]
        caption, problems = P.choose_caption(options, cfg, recent)
        act(st, "review", f"{key} 멘트 검사 {'통과' if not problems else '주의: ' + ', '.join(problems)} — {caption}",
            "done" if not problems else "error")
    except Exception as e:
        act(st, "dev", f"{key} 생성 실패: {str(e)[:200]}", "error")
        act(st, "image", "작업 중단 (개발 담당 기록 참고)", "error")
        raise
    ext = "jpg" if png[:3] == b"\xff\xd8\xff" else "png"
    # 다시 만들 때마다 새 파일 이름 → 화면·브라우저가 예전 그림을 기억해 보여 주는 일이 없다
    r2_key = f"turnerbro-threads/queue/{key}_{P.now_kst():%H%M%S}.{ext}"
    storage.put_bytes(r2_key, png, "image/jpeg" if ext == "jpg" else "image/png")
    today = P.now_kst().date().isoformat()
    st["images_made"][today] = st["images_made"].get(today, 0) + 1
    item.update({"date": key[:10], "slot": key, "r2_key": r2_key, "caption": caption,
                 "options": options, "problems": problems, "status": "ready"})
    return item


def produce() -> None:
    from . import storage
    st = _state()
    today = P.now_kst().date()
    made = 0
    act(st, "shiho", f"{CFG['stock_days']}일치 재고 점검 시작", "working")
    for k in sorted(k for k, v in st["queue"].items() if v.get("status") == "ready"):
        try:
            if fix_caption(st, k):
                storage.save_state(st)
        except Exception as e:
            act(st, "dev", f"{k} 멘트 재검사 실패: {str(e)[:150]}", "error")
    for key, slot in P.upcoming_slot_keys(CFG, today + dt.timedelta(days=1), CFG["stock_days"]):
        if key in st["queue"] and st["queue"][key].get("status") in ("ready", "posted"):
            continue
        if not _budget_ok(st, today.isoformat()):
            log(f"오늘 이미지 생성 상한({CFG['daily_image_limit']}장)에 도달해 멈춥니다.")
            break
        try:
            st["queue"][key] = make_item(st, key, slot)
            made += 1
            q = st["queue"][key]
            log(f"✔ {key} {q['kind']}" + (f"  (검사: {', '.join(q['problems'])})" if q["problems"] else ""))
            storage.save_state(st)  # 한 장마다 저장 → 중간에 실패해도 만든 것은 남음
        except Exception as e:
            log(f"✘ {key} 생성 실패: {e}")
            traceback.print_exc()
    ready = sum(1 for v in st['queue'].values() if v.get('status') == 'ready')
    act(st, "shiho", f"재고 점검 끝 — 새로 {made}건, 게시 대기 {ready}건", "done")
    log(f"새로 만든 게시물 {made}건. 대기 중 {ready}건.")
    _gallery(st)
    storage.save_state(st)
    # 네이버 블로그 예약 패키지: 내일이 예약 요일이면 미리 만든다
    try:
        from . import blog
        for r in blog.scheduled(CFG, today + dt.timedelta(days=1)):
            log(f"블로그 예약 패키지: {r[:80]}")
    except Exception as e:
        log(f"✘ 블로그 예약 패키지 실패: {e}")


def save_and_rebuild(state: dict) -> str:
    """화면(SHIHO)에서 직접 실행할 때: 화면 기록을 먼저 저장 → 다시 만들기 → 화면 기록을 새로 읽는다."""
    from . import storage
    storage.save_state(state)
    r = rebuild()
    state.clear()
    state.update(_state())
    return r


def rebuild() -> str:
    """게시 예정 재고를 전부 빼고 새 규칙으로 다시 만든다 (오늘 남은 시간 + 3일치).
    빠진 게시물의 여행 사진은 다시 뽑지 않는다. 한 번에 만드는 일이라 하루 이미지 상한 대신 16장 상한을 쓴다."""
    from . import storage
    st = _state()
    now = P.now_kst()
    today = now.date()
    targets = []
    for key, slot in P.upcoming_slot_keys(CFG, today, CFG["stock_days"] + 1):
        when = dt.datetime.strptime(key, "%Y-%m-%d_%H%M").replace(tzinfo=now.tzinfo)
        if when < now + dt.timedelta(minutes=20):
            continue  # 곧 게시될 것·지난 것은 건드리지 않는다
        if st["queue"].get(key, {}).get("status") == "posted":
            continue
        targets.append((key, slot))
    for key, _ in targets:
        if key in st["queue"]:
            st["queue"][key]["status"] = "skipped"
    act(st, "shiho", f"Mr. MOON 지시: 예약 {len(targets)}건 전부 새로 만들기 → 이미지·작가 담당", "done")
    storage.save_state(st)
    made = 0
    for key, slot in targets[:16]:
        try:
            st["queue"][key] = make_item(st, key, slot)
            made += 1
            log(f"✔ {key} 새로 만듦")
            storage.save_state(st)
        except Exception as e:
            log(f"✘ {key} 실패: {e}")
            traceback.print_exc()
    act(st, "shiho", f"예약 전부 새로 만들기 끝 — {made}/{len(targets)}건", "done" if made == len(targets) else "error")
    storage.save_state(st)
    return f"예약 {made}/{len(targets)}건 새로 만듦"


def work(lane_name: str = "work") -> None:
    """업무 지시서 처리 (python -m office.run work | blogwork). 남은 지시서가 없거나 38분이 지나면 끝낸다."""
    import time
    from . import jobs
    t0 = time.time()
    try:  # 설계·개발·보안 책상: 새로 반영된 변경 알림 + 하루 한 번 보안 점검
        from . import changelog, storage
        st = _state()
        if changelog.announce(st) | changelog.security_check(st):
            storage.save_state(st)
    except Exception as e:
        log(f"보안 점검을 건너뜁니다: {type(e).__name__}")
    n = jobs.recover_stale()
    if n:
        log(f"멈춰 있던 지시서 {n}건을 다시 대기로 돌렸습니다.")
    done = 0
    while time.time() - t0 < 38 * 60:
        job = jobs.claim(lane_name)
        if not job:
            break
        log(f"▶ 지시서 {job['id']} {job['label']} 시작")
        try:
            result = _do_job(job)
            jobs.finish(job["id"], True, result)
            log(f"✔ 지시서 {job['id']} 완료")
        except Exception as e:
            jobs.finish(job["id"], False, f"{type(e).__name__}: {e}")
            log(f"✘ 지시서 {job['id']} 실패: {type(e).__name__}")
            traceback.print_exc()
        done += 1
    log(f"지시서 처리 {done}건 ({lane_name}).")


def _do_job(job: dict) -> str:
    from . import storage
    t, a = job["type"], job.get("args") or {}
    if t == "produce":
        produce()
        return "재고 채우기 완료"
    if t == "remake":
        st = _state()
        key = a["slot"]
        if key not in st["queue"]:
            raise KeyError(f"{key} 게시물이 없습니다")
        st["queue"][key]["status"] = "skipped"
        slot = next(x for x in CFG["slots"] if x["time"].replace(":", "") == key[-4:])
        act(st, "shiho", f"지시서: {key} 다시 만들기 → 이미지·작가 담당", "done")
        st["queue"][key] = make_item(st, key, slot)
        storage.save_state(st)
        return f"{key} 새로 만듦"
    if t == "rebuild":
        return rebuild()
    if t == "post_now":
        st = _state()
        publish_item(st, a["slot"])
        return f"{a['slot']} 게시함"
    if t == "blog_clip":
        from . import blog
        return blog.make_clip(CFG, a["pid"])
    if t == "blog_draw":
        from . import blog
        return blog.draw_later(CFG, a["pid"])
    if t == "blog_make":
        from . import blog
        pid = blog.make_package(CFG, a.get("blog", "cinepark"), a.get("hint", ""), a.get("topic"), mode="실시간",
                                kind=a.get("kind", "feature"))
        return f"패키지 {pid}"
    raise ValueError(f"모르는 지시서 종류: {t}")


def blog_now(which: str = "cinepark") -> None:
    """수동 실행용: python -m office.run blog cinepark"""
    from . import blog
    log(f"블로그 패키지 완료: {blog.make_package(CFG, which, mode='실시간')}")


def _gallery(st: dict) -> None:
    """게시 예정 목록을 HTML 로 만들어 R2 에 올리고 7일짜리 링크를 남긴다."""
    from . import storage
    rows = []
    for key in sorted(st["queue"]):
        v = st["queue"][key]
        if v.get("status") != "ready":
            continue
        url = storage.signed_url(v["r2_key"], 604800)
        label = v.get("breed") or v.get("city") or ""
        rows.append(f"<div style='display:inline-block;width:260px;margin:8px;vertical-align:top;font-family:sans-serif'>"
                    f"<img src='{url}' style='width:260px;border-radius:8px'><br><b>{key}</b> · {v['kind']} · {label}"
                    f"<br>{v['caption']}<br><small style='color:#888'>예비: {' / '.join(v.get('options', [])[1:])}</small></div>")
    html = "<meta charset='utf-8'><h2>Turner Bro 게시 예정</h2>" + "".join(rows)
    storage.put_bytes("turnerbro-threads/queue.html", html.encode("utf-8"), "text/html; charset=utf-8")
    # 공개 저장소의 실행 기록은 누구나 볼 수 있으므로 링크는 남기지 않는다 (사무실 화면 Threads 데스크에서 확인)


def post() -> None:
    from . import storage, threads
    st = _state()
    now = P.now_kst()
    cur = P.current_slot(CFG, now)
    if not cur:
        log(f"{now:%H:%M} — 게시 시각이 아닙니다.")
        return
    key, slot, wait_min = cur
    item = st["queue"].get(key)
    if item and item.get("status") == "posted":
        log(f"{key} 이미 게시됨: {item.get('permalink')}")
        return
    if not item or item.get("status") != "ready":
        log(f"{key} 재고 없음 → 지금 만듭니다.")
        item = make_item(st, key, slot)
        st["queue"][key] = item
        storage.save_state(st)
    if wait_min > 0:  # 일찍 깨어났으면 예약 시각까지 기다린다
        import time
        act(st, "channel", f"{slot['time']} 게시 대기 중", "working")
        storage.save_state(st)
        log(f"예약 시각까지 {wait_min:.0f}분 대기")
        time.sleep(wait_min * 60)
    publish_item(st, key)


def publish_item(st: dict, key: str) -> dict:
    """한 게시물을 지금 Threads 에 올린다 (예약 실행·오피스 '지금 게시' 공용)."""
    from . import storage, threads
    try:
        if fix_caption(st, key):
            storage.save_state(st)
    except Exception as e:  # 재검사가 실패해도 게시는 계속
        act(st, "dev", f"{key} 멘트 재검사 실패: {str(e)[:150]}", "error")
    item = st["queue"][key]
    token = _token(st)
    user_id = os.environ.get("THREADS_USER_ID", "").strip() or threads.me(token)["id"]
    url = storage.signed_url(item["r2_key"], 3600)
    act(st, "channel", f"{key} Threads 게시 중", "working")
    try:
        res = threads.publish_image(user_id, token, url, item["caption"])
    except Exception as e:
        item["status"] = "ready"
        item["last_error"] = str(e)[:500]
        act(st, "channel", f"{key} 게시 실패 (개발 담당 기록 참고)", "error")
        act(st, "dev", f"{key} 게시 실패: {str(e)[:200]}", "error")
        storage.save_state(st)
        log(f"✘ {key} 게시 실패: {e}")
        raise
    item.update({"status": "posted", "posted_at": P.now_kst().isoformat(), **res})
    st["history"].append({k: item.get(k) for k in ("date", "slot", "kind", "breed", "scene", "city", "photo_id", "caption", "permalink")})
    if item.get("photo_id"):
        st["used_photos"].append(item["photo_id"])
    act(st, "channel", f"{key[-4:-2]}:{key[-2:]} 게시 완료 — {item['caption']}", "done")
    storage.save_state(st)
    log(f"✔ {key} 게시 완료 — {item['caption']}\n{res.get('permalink')}")
    return item


def refresh() -> None:
    from . import storage, threads
    st = _state()
    act(st, "security", "Threads 토큰 갱신 중", "working")
    try:
        r = threads.refresh(_token(st))
    except Exception as e:
        act(st, "security", f"토큰 갱신 실패: {str(e)[:150]}", "error")
        storage.save_state(st)
        raise
    st["threads_token"] = r["access_token"]
    st["threads_token_refreshed"] = P.now_kst().isoformat()
    st["threads_token_expires_in"] = r.get("expires_in")
    days = int(r.get("expires_in", 0)) // 86400
    act(st, "security", f"Threads 토큰 갱신 완료 (약 {days}일 유효)", "done")
    storage.save_state(st)
    log(f"✔ Threads 토큰 갱신 완료 (약 {days}일 유효)")


def skip(key: str) -> None:
    from . import storage
    st = _state()
    v = st["queue"].get(key)
    if not v:
        log(f"{key} 없음")
        return
    v["status"] = "skipped"
    storage.save_state(st)
    log(f"{key} 를 뺐습니다. 다음 생성 때 새로 만듭니다.")
    produce()


def selftest() -> None:
    ok = True

    def step(name, fn):
        nonlocal ok
        try:
            res = fn()
            log(f"✔ {name}: {res}")
        except Exception as e:
            ok = False
            log(f"✘ {name}: {e}")

    from . import ai, drive, storage, threads
    need = ["OPENAI_API_KEY", "THREADS_ACCESS_TOKEN", "R2_ENDPOINT", "R2_ACCESS_KEY_ID",
            "R2_SECRET_ACCESS_KEY", "R2_BUCKET", "GOOGLE_SA_JSON"]
    missing = [k for k in need if not os.environ.get(k, "").strip()]
    log(f"{'✘' if missing else '✔'} 비밀값: {'빠짐 ' + ', '.join(missing) if missing else '7개 모두 있음'}")
    step("R2 상태 파일", lambda: f"{len(_state()['history'])}건 기록")
    step("드라이브 여행 원본", lambda: f"{len(drive.travel_photos(CFG['google_drive']['travel_root_folder']))}장")
    step("드라이브 고양이 기준 그림", lambda: [len(drive.download(f)) for f in CFG["google_drive"]["cat_reference_files"]])
    step("Threads 계정", lambda: threads.me(os.environ["THREADS_ACCESS_TOKEN"].strip()))

    def models():
        names = sorted(m.id for m in ai._client().models.list().data)
        want = [CFG["openai"]["image_model"], CFG["openai"]["text_model"]]
        miss = [w for w in want if w not in names]
        hint = [n for n in names if n.startswith(("gpt-6", "gpt-image"))]
        if miss:
            raise RuntimeError(f"설정한 모델 {miss} 없음. 사용 가능: {hint}")
        return f"설정 모델 확인 ({', '.join(want)})"
    step("OpenAI 모델", models)
    if not ok:
        sys.exit(1)


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "selftest"
    {"produce": produce, "post": post, "refresh": refresh, "selftest": selftest,
     "skip": lambda: skip(sys.argv[2]),
     "rebuild": rebuild,
     "blog": lambda: blog_now(sys.argv[2] if len(sys.argv) > 2 else "cinepark"),
     "work": lambda: work("work"), "blogwork": lambda: work("blogwork")}[cmd]()
