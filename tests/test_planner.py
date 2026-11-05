import datetime as dt
import random
import unittest
from pathlib import Path

import yaml

from office import planner as P

CFG = yaml.safe_load((Path(__file__).resolve().parent.parent / "config.yaml").read_text(encoding="utf-8"))
KST = P.KST


class TestPlanner(unittest.TestCase):
    def test_slots(self):
        keys = P.upcoming_slot_keys(CFG, dt.date(2026, 11, 5), 3)
        self.assertEqual(len(keys), 12)
        self.assertEqual(keys[0][0], "2026-11-05_0930")
        self.assertEqual([s["kind"] for _, s in keys[:4]], ["travel", "cat", "travel", "cat"])

    def test_current_slot_early_and_late(self):
        early = dt.datetime(2026, 11, 5, 9, 10, tzinfo=KST)   # GitHub 09:10 실행
        key, slot, wait = P.current_slot(CFG, early)
        self.assertEqual(key, "2026-11-05_0930")
        self.assertAlmostEqual(wait, 20)
        late = dt.datetime(2026, 11, 5, 13, 40, tzinfo=KST)   # 70분 지연
        key, slot, wait = P.current_slot(CFG, late)
        self.assertEqual(key, "2026-11-05_1230")
        self.assertLess(wait, 0)
        self.assertIsNone(P.current_slot(CFG, dt.datetime(2026, 11, 5, 23, 0, tzinfo=KST)))

    def test_cat_no_repeat_breed_and_pair(self):
        rng = random.Random(1)
        hist = list(CFG["seed_history"])
        today = dt.date(2026, 11, 5)
        for i in range(40):
            b, s = P.pick_cat(CFG, hist, today, rng)
            cats = [h for h in hist if h["kind"] == "cat"]
            self.assertNotEqual(b["id"], cats[-1]["breed"], "직전 품종 반복")
            recent = {(h["breed"], h["scene"]) for h in cats[-14:]}
            self.assertNotIn((b["id"], s["id"]), recent)
            hist.append({"date": today.isoformat(), "kind": "cat", "breed": b["id"], "scene": s["id"]})

    def test_cat_prompt(self):
        b = CFG["breeds"][7]; s = CFG["scenes"][0]
        p = P.cat_prompt(CFG, b, s)
        self.assertTrue(p.startswith("Match the drawing style"))
        self.assertIn("A Russian Blue cat with a solid blue-grey coat and green eyes sits inside", p)
        import re
        for s in CFG["scenes"]:  # 모든 장면 문장: 'A or B'·흐린 표현 금지 (단정형 규칙)
            text = P.cat_prompt(CFG, b, s).lower()
            for bad in [r"\bor\b", r"\bslightly\b", r"\bmaybe\b", r"\bseems?\b", r"\bsomewhat\b"]:
                self.assertIsNone(re.search(bad, text), f"{s['id']}: {bad}")

    def test_travel_pick(self):
        photos = [{"id": f"t{i}", "name": "", "city": "Tokyo", "year": "2005"} for i in range(5)] + \
                 [{"id": "b1", "name": "", "city": "Barcelona", "year": "2006"}]
        hist = [{"kind": "travel", "city": "Tokyo"}]
        p = P.pick_travel(photos, hist, set(), random.Random(0))
        self.assertEqual(p["city"], "Barcelona")
        self.assertIsNone(P.pick_travel(photos, hist, {p["id"] for p in photos}))

    def test_city_folder(self):
        self.assertEqual(P.parse_city_folder("2006 Barcelona"), ("Barcelona", "2006"))
        self.assertEqual(P.parse_city_folder("LONDON"), ("LONDON", ""))

    def test_caption_check(self):
        self.assertEqual(P.caption_problems("목욕은 질색하면서 물방울은 못 참지.", CFG), [])
        self.assertTrue(P.caption_problems("햇살 가득한 창가에서 여유롭게 쉬는 고양이", CFG))
        self.assertTrue(P.caption_problems("귀엽다 🐱🐾", CFG))
        self.assertTrue(P.caption_problems("귀엽다 #고양이", CFG))
        c, probs = P.choose_caption(["포근한 오후의 고양이", "\"일 좀 하려면 꼭 여기 눕는다.\""], CFG)
        self.assertEqual(c, "일 좀 하려면 꼭 여기 눕는다.")
        self.assertEqual(probs, [])


if __name__ == "__main__":
    unittest.main()
