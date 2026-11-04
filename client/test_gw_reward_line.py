# -*- coding: utf-8 -*-
"""길드전 보상 글 (2.0.2) - ui_guild_war.reward_line 과 ui_bag.item_desc 의 기술머신 뽑기권 설명. Tk 창 없이 함수만 본다.

    python3 client/test_gw_reward_line.py

서버(server/test_gw_rewards.py)는 시즌 5 에만 rewards[i] 에 deco · tm 을, 맨 위에 tmActive 를 싣는다. 화면은
  · 새 칸이 있으면: 순위마다 '1위 코인 300 · 금관 · ... · 뽑기권 2장' (뽑기권 0 이면 안 적는다) + 둘째 줄에 활약 보상
    (tmActive 의 수, 없으면 3번 · 1장) + 기여 보상 줄은 그 뒤
  · 옛 서버 꼴(rank · coins 만 - 시즌 4 거나 2.0.2 전 서버): 예전 글 '보상(길드 코인, ...' 그대로
  · 가방: 랜덤 뽑기권은 '길드전 보상' 으로도 받는다고, 타입 확정은 '랭크 시즌 보상으로만'
"""
import os
import sys
import tempfile

os.environ["POKET_HOME"] = tempfile.mkdtemp(prefix="poket-test-gw-reward-")

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.dirname(HERE))

from poketdesktop import ui_bag                             # noqa: E402
from poketdesktop import ui_guild_war as W                  # noqa: E402

OK = FAIL = 0
TITLE = "시즌 5 길드전 우승"

# 서버 guild_war.state() 가 시즌 5 에 싣는 꼴 (server/test_gw_rewards.py 의 V5_REWARDS 와 같다)
V5_REWARDS = [{"rank": 1, "coins": 300, "deco": "금관 · 금빛 별가루 · 발밑 빛", "tm": 2},
              {"rank": 2, "coins": 200, "deco": "은관 · 은빛 별가루", "tm": 1},
              {"rank": 3, "coins": 150, "deco": "동관 · 동빛 별가루", "tm": 1},
              {"rank": None, "coins": 50, "deco": "참가 묶음 선택권", "tm": 0}]
OLD_REWARDS = [{"rank": 1, "coins": 300}, {"rank": 2, "coins": 200}, {"rank": 3, "coins": 150},
               {"rank": None, "coins": 50}]
CONTRIB = {"win": 20, "joker": 20, "defend": 20, "max": 300, "earned": 40}

NEW_FIRST = ("보상(한 번이라도 공격한 길드원): 1위 코인 300 · 금관 · 금빛 별가루 · 발밑 빛 · 뽑기권 2장 / "
             "2위 코인 200 · 은관 · 은빛 별가루 · 뽑기권 1장 / 3위 코인 150 · 동관 · 동빛 별가루 · 뽑기권 1장 / "
             "그 밖 코인 50 · 참가 묶음 선택권 / 1위 길드에는 칭호 '%s'" % TITLE)
NEW_ACTIVE = ("뽑기권은 랜덤 기술머신 뽑기권 - 공격에서 이긴 길드원만 받습니다. 활약 보상: 공격에서 3번 이상 이기면 "
              "순위와 상관없이 1장 (순위 몫이 있으면 거기에 더)")
OLD_TEXT = "보상(길드 코인, 한 번이라도 공격한 길드원): 1위 300 · 2위 200 · 3위 150 · 그 밖 50 · 1위 길드에는 칭호 '%s'" % TITLE
CONTRIB_TEXT = ("기여 보상(판이 끝나면 바로): 공격에서 이기면 20 · 조커를 이기면 40 · 내 칸이 상대를 다 쓰러뜨려 막으면 20 "
                "(기권 · 시간 초과는 없음, 한 시즌 300개까지, 지금 40개)")


def chk(name, cond, got=""):
    global OK, FAIL
    if cond:
        OK += 1
        print("  OK   %s" % name)
    else:
        FAIL += 1
        print("  FAIL %s   %r" % (name, got))


def reward_part():
    print("=== reward_line: 새 서버 (시즌 5, deco · tm · tmActive) ===")
    out = W.reward_line({"rewards": V5_REWARDS, "tmActive": {"wins": 3, "count": 1}, "title": TITLE})
    lines = out.split("\n")
    chk("두 줄 (보상 · 활약)", len(lines) == 2, lines)
    chk("  첫 줄: 순위마다 코인 · 꾸미기 · 뽑기권, 1위 칭호", lines[0] == NEW_FIRST, lines[0])
    chk("  '코인 300 · 금관 · 금빛 별가루 · 발밑 빛 · 뽑기권 2장'",
        "1위 코인 300 · 금관 · 금빛 별가루 · 발밑 빛 · 뽑기권 2장" in lines[0], lines[0])
    chk("  뽑기권이 0 인 '그 밖' 은 뽑기권을 안 적는다", "뽑기권 0장" not in out
        and "그 밖 코인 50 · 참가 묶음 선택권 /" in lines[0], lines[0])
    chk("  둘째 줄: 활약 보상 (이긴 길드원만 · 3번 · 1장)", len(lines) > 1 and lines[1] == NEW_ACTIVE,
        lines[1:])
    chk("  옛 글('길드 코인, ...')은 안 나온다", "보상(길드 코인" not in out, out)
    out = W.reward_line({"rewards": V5_REWARDS, "tmActive": {"wins": 4, "count": 2}, "title": TITLE})
    chk("tmActive 의 수를 그대로 쓴다 (4번 · 2장)", out.split("\n")[1]
        == "뽑기권은 랜덤 기술머신 뽑기권 - 공격에서 이긴 길드원만 받습니다. 활약 보상: 공격에서 4번 이상 이기면 "
        "순위와 상관없이 2장 (순위 몫이 있으면 거기에 더)", out)
    for what, st in (("tmActive 가 없으면", {"rewards": V5_REWARDS, "title": TITLE}),
                     ("tmActive 가 None 이면", {"rewards": V5_REWARDS, "tmActive": None, "title": TITLE})):
        out = W.reward_line(st)
        chk("%s 3번 · 1장으로" % what, out == NEW_FIRST + "\n" + NEW_ACTIVE, out)
    out = W.reward_line({"rewards": V5_REWARDS, "tmActive": {"wins": 3, "count": 1}, "title": TITLE,
                         "contrib": CONTRIB})
    chk("기여 보상 줄은 활약 줄 뒤 (세 줄)", out.split("\n") == [NEW_FIRST, NEW_ACTIVE, CONTRIB_TEXT], out.split("\n"))
    one = [{"rank": 1, "coins": 300, "deco": "금관 · 금빛 별가루 · 발밑 빛", "tm": 3}]
    chk("순위 몫이 바뀌면 그대로 (1위 3장)", "1위 코인 300 · 금관 · 금빛 별가루 · 발밑 빛 · 뽑기권 3장 / 1위 길드에는"
        in W.reward_line({"rewards": one, "tmActive": {"wins": 3, "count": 1}, "title": TITLE}))

    print("\n=== reward_line: 옛 서버 꼴 (rank · coins 만) ===")
    out = W.reward_line({"rewards": OLD_REWARDS, "title": TITLE})
    chk("예전 글 그대로 (한 줄)", out == OLD_TEXT, out)
    chk("  뽑기권 · 꾸미기 · 활약 얘기가 없다", "뽑기권" not in out and "활약" not in out and "금관" not in out, out)
    out = W.reward_line({"rewards": OLD_REWARDS, "tmActive": None, "title": TITLE})
    chk("새 서버의 시즌 4 꼴 (deco 없음, tmActive None) 도 예전 글", out == OLD_TEXT, out)
    out = W.reward_line({"rewards": OLD_REWARDS, "title": TITLE, "contrib": CONTRIB})
    chk("2.0.2 전 시즌 5 서버 (contrib 만 있음): 예전 글 + 기여 보상 줄", out == OLD_TEXT + "\n" + CONTRIB_TEXT, out)
    out = W.reward_line({"rewards": OLD_REWARDS, "tmActive": {"wins": 3, "count": 1}, "title": TITLE})
    chk("rewards 에 deco 가 없으면 tmActive 가 와도 예전 글 (새 칸은 deco 로 가른다)", out == OLD_TEXT, out)


def item_part():
    print("\n=== item_desc: 기술머신 뽑기권 ===")
    rnd = {"id": "RANKTICKETTM", "kr": "랜덤 기술머신 뽑기권",
           "desc": "아직 없는 기술머신 가운데 하나가 무작위로 나오는 표. 포켓몬을 고르지 않아도 된다.",
           "effect": {"kind": "tmticket"}}
    typed = {"id": "RANKTICKETTMTYPE", "kr": "타입 확정 기술머신 뽑기권",
             "desc": "쓸 때 타입을 고르면, 그 타입 기술머신 가운데 아직 없는 것 하나가 무작위로 나오는 표. 포켓몬을 고르지 않아도 된다.",
             "effect": {"kind": "tmticket", "pickType": True}}
    d = ui_bag.item_desc(rnd)
    chk("랜덤: 본가 설명 다음에 '랭크 시즌 보상과 길드전 보상으로 받는다'", d.startswith(rnd["desc"] + "\n\n")
        and "랭크 시즌 보상과 길드전 보상으로 받는다." in d, d)
    chk("  '보상으로만' 이라고 하지 않는다", "보상으로만" not in d, d)
    chk("  가진 기술머신은 안 나온다 · 표는 남는다 (예전 그대로)", "가진 기술머신은 나오지 않는다" in d
        and "표는 남는다" in d, d)
    d = ui_bag.item_desc(typed)
    chk("타입 확정: '랭크 시즌 보상으로만 받는다' · 길드전 얘기 없음", d.startswith(typed["desc"] + "\n\n")
        and "랭크 시즌 보상으로만 받는다." in d and "길드전" not in d, d)
    d = ui_bag.item_desc({"effect": {"kind": "tmticket"}})
    chk("설명이 없으면 기본 문장 + 길드전 보상", d.startswith("아직 없는 기술머신 하나가 나온다.\n\n")
        and "길드전 보상" in d, d)
    d = ui_bag.item_desc({"effect": {"kind": "tmticket", "pickType": True}})
    chk("  타입 확정도 기본 문장 + 랭크 시즌 보상으로만", d.startswith("아직 없는 기술머신 하나가 나온다.\n\n")
        and "랭크 시즌 보상으로만" in d and "길드전" not in d, d)
    d = ui_bag.item_desc({"effect": {"kind": "shiny"}})
    chk("이로치사탕은 그대로 '랭크 시즌 보상으로만'", "랭크 시즌 보상으로만" in d and "길드전" not in d, d)


def main():
    reward_part()
    item_part()
    print("\n" + "=" * 54)
    print("  합계  OK %d   FAIL %d" % (OK, FAIL))
    print("=" * 54)
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
