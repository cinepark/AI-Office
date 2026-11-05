"""SHIHO: Mr. MOON 의 지시를 받아 담당자 업무로 바꾸고 나눠 맡긴다.

Mr. MOON 은 SHIHO 에게만 말합니다. SHIHO 는 지시를 아래 정해진 업무 목록 중 하나 이상으로 바꿉니다.
목록에 없는 일은 지어내 실행하지 않고, '다음 단계 업무'로 접수만 합니다.
"""
from __future__ import annotations

import json
import re

ACTIONS = """
- produce: 게시 재고 채우기. args 없음.
- remake: 특정 게시물을 빼고 새로 만들기. args: {"slot": "YYYY-MM-DD_HHMM"}
- post_now: 특정 게시물을 지금 게시. args: {"slot": "YYYY-MM-DD_HHMM"}
- next_cat: 다음 고양이 품종·장면 지정. args: {"breed": 품종id 또는 null, "scene": 장면id 또는 null}
- exclude_breed: 품종 빼기/되살리기. args: {"breed": 품종id, "on": true(빼기)|false(되살리기)}
- ban_word: 멘트 금지어 추가. args: {"word": "..."}
- add_example: 멘트 말투 예시 추가. args: {"text": "..."}
- note: 위에 없는 일. 실행하지 않고 접수만. args: {"to": 담당자id, "text": "..."}
"""

SYSTEM = """당신은 MY AI OFFICE 의 총괄 매니저 SHIHO 입니다. Mr. MOON 의 지시를 업무로 바꿉니다.
가능한 업무(이 목록 밖의 업무는 만들지 않음):
{actions}
품종 id: {breeds}
장면 id: {scenes}
담당자 id: shiho, strategy, design, dev, security, research, writer, image, video, review, channel, cinepark
오늘 날짜: {today}. 게시 슬롯 시각: {slots}. '내일 12시반' 같은 말은 슬롯 키로 바꾸세요.

JSON 만 출력: {{"reply": "Mr. MOON 에게 할 짧은 답 (~합니다체, 질문으로 끝내지 않음)",
 "actions": [{{"type": "...", "args": {{...}}}}]}}"""


def interpret(cfg: dict, order: str, today: str) -> dict:
    from . import ai
    system = SYSTEM.format(actions=ACTIONS, today=today,
                           breeds=", ".join(f"{b['id']}({b['name']})" for b in cfg["breeds"]),
                           scenes=", ".join(f"{s['id']}({s['name']})" for s in cfg["scenes"]),
                           slots=", ".join(s["time"] for s in cfg["slots"]))
    r = ai._client().responses.create(model=cfg["openai"]["text_model"],
                                      input=[{"role": "system", "content": system},
                                             {"role": "user", "content": order}])
    m = re.search(r"\{.*\}", r.output_text or "", re.S)
    try:
        data = json.loads(m.group(0)) if m else {}
    except json.JSONDecodeError:
        data = {}
    data.setdefault("reply", "지시를 접수했습니다.")
    data.setdefault("actions", [{"type": "note", "args": {"to": "shiho", "text": order}}])
    return data


WHO = {"produce": "shiho", "remake": "image", "post_now": "channel", "next_cat": "image",
       "exclude_breed": "image", "ban_word": "review", "add_example": "writer", "note": "shiho"}


def execute(state: dict, cfg: dict, actions: list[dict], run_module) -> list[str]:
    """업무 실행. run_module = office.run (순환 import 방지용 주입). 실행 결과 문장 목록을 돌려준다."""
    from .staff import STAFF_BY_ID, act
    done = []
    breed_ids = {b["id"] for b in cfg["breeds"]}
    scene_ids = {s["id"] for s in cfg["scenes"]}
    s = state.setdefault("settings", {})
    for a in actions:
        t, args = a.get("type"), a.get("args") or {}
        who = WHO.get(t, "shiho")
        try:
            if t == "produce":
                act(state, "shiho", "Mr. MOON 지시: 재고 채우기 → 이미지·작가 담당", "done")
                run_module.save_and_produce(state)
                done.append("재고를 채웠습니다.")
            elif t in ("remake", "post_now"):
                slot = args.get("slot", "")
                if slot not in state.get("queue", {}):
                    done.append(f"{slot} 게시물을 찾지 못했습니다.")
                    continue
                act(state, "shiho", f"Mr. MOON 지시: {slot} {'다시 만들기' if t == 'remake' else '지금 게시'} → {STAFF_BY_ID[who][1]}", "done")
                if t == "remake":
                    state["queue"][slot]["status"] = "skipped"
                    sl = next(x for x in cfg["slots"] if x["time"].replace(":", "") == slot[-4:])
                    state["queue"][slot] = run_module.make_item(state, slot, sl)
                    done.append(f"{slot} 게시물을 새로 만들었습니다.")
                else:
                    run_module.publish_item(state, slot)
                    done.append(f"{slot} 게시물을 올렸습니다.")
            elif t == "next_cat":
                b = args.get("breed") if args.get("breed") in breed_ids else None
                sc = args.get("scene") if args.get("scene") in scene_ids else None
                s["next_cat"] = {"breed": b, "scene": sc}
                act(state, "image", f"다음 고양이 지정 접수: {b or '자동'} / {sc or '자동'}", "done")
                done.append("다음 고양이 그림에 반영합니다.")
            elif t == "exclude_breed" and args.get("breed") in breed_ids:
                ex = set(s.get("exclude_breeds", []))
                (ex.add if args.get("on", True) else ex.discard)(args["breed"])
                s["exclude_breeds"] = sorted(ex)
                act(state, "image", f"품종 목록 조정: 제외 {s['exclude_breeds'] or '없음'}", "done")
                done.append("품종 목록을 조정했습니다.")
            elif t == "ban_word" and args.get("word"):
                s.setdefault("banned_extra", []).append(args["word"])
                act(state, "review", f"금지어 추가: {args['word']}", "done")
                done.append(f"'{args['word']}'를 금지어에 넣었습니다.")
            elif t == "add_example" and args.get("text"):
                s.setdefault("examples_extra", []).append(args["text"])
                act(state, "writer", f"말투 예시 추가: {args['text']}", "done")
                done.append("말투 예시에 추가했습니다.")
            else:
                to = args.get("to") if args.get("to") in STAFF_BY_ID else "shiho"
                state.setdefault("orders", []).append({"to": to, "text": args.get("text", ""), "status": "접수"})
                act(state, to, f"지시 접수(다음 단계 업무): {args.get('text', '')[:40]}", "idle")
                done.append(f"{STAFF_BY_ID[to][1]}에게 접수해 두었습니다. 아직 자동 실행되는 업무는 아닙니다.")
        except Exception as e:
            act(state, "dev", f"지시 실행 실패({t}): {str(e)[:150]}", "error")
            done.append(f"'{t}' 실행 중 문제가 생겼습니다: {str(e)[:120]}")
    return done
