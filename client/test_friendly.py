# -*- coding: utf-8 -*-
"""길드 친선전의 계산 검사 (1.10.3). 창을 만들지 않는다.

    python client/test_friendly.py

  1. 알림·구경 창의 계산: 오른쪽 아래 자리, 진행 중인 판 목록에 새 모습 끼우기, 새로 상대를 구하는 사람.
  2. 구경 장면의 계산: 바탕화면 오른쪽 아래의 자리, 던진 볼의 포물선, 흰 빛이 커지는 단계,
     일마다 기다리는 시간, 떠오르는 글씨로 줄이기, 도트를 한 칸에 맞춰 넣기.
  3. 구경 장면의 포켓몬은 **바탕화면의 걷는 도트**다 (맞는 쪽을 보고, 두 배 크기로, 큰 종은 줄여서).
  4. 배틀 창이 뜰 때 장면을 덮는 띠 (enter_fx).
  5. **채팅에서 하는 친선전**: 채팅에 친 글이 명령인지 풀기(/친선전), 채팅에 놓인 카드가 지금 어떻게
     보여야 하는지 (단추는 지금 모습에 그 줄이 있을 때만 붙는다).
"""
import json
import os
import sys
import tempfile

# **이 검사는 걷는 도트 폴더에 시험용 그림을 쓴다. 반드시 임시 폴더에.** 이 줄 없이 돌렸다가 실제 앱의
# 데이터 폴더(~/Library/Application Support/poketdesktop/walk)의 그림을 덮어쓴 적이 있다.
os.environ["POKET_HOME"] = tempfile.mkdtemp(prefix="poket-test-friendly-")

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.dirname(HERE))

from poketdesktop import duel_scene as F                     # noqa: E402
from poketdesktop import ui_spectate as SP                   # noqa: E402

OK = FAIL = 0


def chk(name, cond, got=""):
    global OK, FAIL
    if cond:
        OK += 1
        print("  OK   %s" % name)
    else:
        FAIL += 1
        print("  FAIL %s   %r" % (name, got))


def main():
    print("=== 알림·구경 창의 계산 ===")
    chk("작업 영역의 오른쪽 아래에 놓는다 (가장자리에서 조금 띄워서)", SP.corner((0, 25, 1440, 860), 340, 230, 14) == (1440 - 340 - 14, 860 - 230 - 14))
    chk("  화면이 창보다 작아도 화면 밖(왼쪽·위)으로 나가지 않는다", SP.corner((0, 0, 300, 200), 340, 230) == (0, 0))
    f1 = {"id": 7, "turn": 1, "over": False, "a": {"id": 2, "name": "가람"}, "b": {"id": 3, "name": "나래"}}
    chk("판의 제목과 두 사람", SP.title_of(f1) == "가람 vs 나래" and SP.players(f1) == (2, 3) and SP.title_of({}) == "? vs ?")
    fs = SP.merge_fights([], f1)
    chk("진행 중인 판 목록: 새 판은 더한다", [f["id"] for f in fs] == [7])
    fs = SP.merge_fights(fs, dict(f1, turn=2))
    chk("  같은 판의 새 모습은 갈아 끼운다 (늘지 않는다)", len(fs) == 1 and fs[0]["turn"] == 2)
    chk("  끝난 판은 뺀다", SP.merge_fights(fs, dict(f1, over=True)) == [])
    old = [{"id": 2, "name": "가람"}]
    new = [{"id": 2, "name": "가람"}, {"id": 3, "name": "나래"}, {"id": 9, "name": "나"}]
    chk("새로 상대를 구하기 시작한 남만 알린다 (이미 알던 사람·나 자신은 빼고)", [s["id"] for s in SP.fresh_seekers(old, new, 9)] == [3]
        and SP.fresh_seekers(new, new, 9) == [] and SP.fresh_seekers(None, None, 1) == [])

    print("\n=== 바탕화면의 자리 ===")
    area = (0, 25, 1440, 860)
    sp = F.spots(area)
    chk("두 포켓몬은 작업 영역의 **오른쪽 아래**에 마주 선다 (a 가 왼쪽)", sp["b"] == (1440 - F.EDGE, 860 - F.LIFT)
        and sp["a"] == (1440 - F.EDGE - F.GAP, 860 - F.LIFT), sp)
    chk("  발은 작업 표시줄(독) 바로 위에 닿는다 - 바탕화면의 포켓몬이 걷는 그 높이", sp["a"][1] == sp["b"][1] == 860 - F.LIFT)
    narrow = F.spots((0, 0, 260, 400))
    chk("  화면이 좁아도 왼쪽 포켓몬이 화면 밖으로 나가지 않는다", narrow["a"][0] >= 0 and narrow["b"][0] - narrow["a"][0] == F.GAP, narrow)
    from PIL import Image
    small, tall = Image.new("RGBA", (20, 30), (9, 9, 9, 255)), Image.new("RGBA", (40, 48), (9, 9, 9, 255))
    box = F.box_of([small, tall])
    put = F.fit(small, box)
    chk("도트는 한 칸에 **아래 가운데**로 맞춰 넣는다 (창 크기를 안 바꾸고 발이 늘 같은 자리에 닿게)", box == (40, 48)
        and put.size == box and put.getpixel((20, 47))[3] == 255 and put.getpixel((20, 5))[3] == 0
        and put.getpixel((2, 47))[3] == 0)
    grow = F.grow_frames(tall, box)

    def filled(im):
        return sum(im.getchannel("A").histogram()[1:])
    chk("볼에서 나올 때의 흰 빛: 같은 칸 안에서 점점 커져 제 크기가 된다", len(grow) == len(F.GROW)
        and all(g.size == box for g in grow) and [filled(g) for g in grow] == sorted(filled(g) for g in grow)
        and filled(grow[-1]) == 40 * 48 and grow[0].getpixel((20, 47))[:3] == (255, 255, 255)
        and grow[0].getpixel((20, 2))[3] == 0, [filled(g) for g in grow])
    chk("떠오르는 글씨는 짧게: '○○ 은(는) ...' 은 뒷부분만 (누구인지는 뜬 자리를 보면 안다)",
        F.short_text("파이리 은(는) 풀이 죽어 움직이지 못했다!") == "풀이 죽어 움직이지 못했다!"
        and F.short_text("파이리 의 공격이 떨어졌다!") == "공격이 떨어졌다!" and F.short_text(None) == "")
    long = F.short_text("파이리 은(는) 상대의 기세에 눌려 아무것도 하지 못한 채 서 있었다!")
    chk("  길면 줄인다", len(long) == F.SHORT and long.endswith("…"), long)
    chk("  조사를 맞춘다 ('회피율 이(가) 올랐다' 로 뜨지 않는다)", F.short_text("개굴닌자 의 회피율 이(가) 올랐다!") == "회피율이 올랐다!",
        F.short_text("개굴닌자 의 회피율 이(가) 올랐다!"))

    print("\n=== 구경 장면의 계산 ===")
    chk("던진 볼은 포물선을 그린다 (양 끝은 제자리, 가운데가 가장 높다)", F.arc((0, 100), (100, 100), 0.0, 30) == (0, 100)
        and F.arc((0, 100), (100, 100), 1.0, 30) == (100, 100) and F.arc((0, 100), (100, 100), 0.5, 30) == (50, 70))
    chk("커지는 단계: 0..1 을 고르게 나눈다 (끝에서는 마지막 단계)", [F.stage_of(t, 5) for t in (0, 0.19, 0.2, 0.5, 0.99, 1.0)]
        == [0, 0, 1, 2, 4, 4])
    chk("볼에서 나오는 흰 빛은 점점 커져서 제 크기가 된다", list(F.GROW) == sorted(F.GROW) and F.GROW[-1] == 1.0 and F.GROW[0] < 0.3)
    chk("내보내는 일은 볼이 날아가 열리고 다 커질 때까지 기다린다", F.wait_of({"t": "switch"}) > F.THROW_S + F.OPEN_S + F.GROW_S
        and F.wait_of({"t": "recall"}) > F.RECALL_S + F.BEAM_S)
    chk("기술은 연출이 끝나야 넘어간다 (정해진 시간이 없다)", F.wait_of({"t": "move", "text": "방전!"}) is None)
    chk("글이 있는 일은 읽을 시간을 준다, 아무것도 없는 일은 바로 넘어간다", F.wait_of({"t": "stat", "text": "공격이 떨어졌다"}) == F.STEP_S
        and F.wait_of({"t": "nothing"}) < 0.1 and F.wait_of({"t": "_result"}) == F.RESULT_S)
    chk("체력 막대 색: 절반 넘게 초록, 5분의 1 아래 빨강", F.hp_color(0.8) != F.hp_color(0.4) != F.hp_color(0.1))
    fight = {"a": {"id": 2, "name": "가람"}, "b": {"id": 3, "name": "나래"}, "result": "a"}
    chk("끝난 판의 한 줄", F.result_text(fight) == "가람 님이 이겼습니다!" and F.result_text({"result": "draw"}) == "비겼습니다."
        and F.result_text({"result": "expired"}) == "배틀이 끝났습니다.")
    chk("체력 막대는 바탕화면 야생 배틀의 것과 같은 크기다", (F.BAR_W, F.BAR_H) == (46, 5))

    print("\n=== 구경 장면의 포켓몬 = 바탕화면의 걷는 도트 ===")
    from PIL import Image
    from poketdesktop import sprites, walk_cache
    if not os.path.realpath(walk_cache.walk_dir()).startswith(os.path.realpath(os.environ["POKET_HOME"])):
        raise SystemExit("걷는 도트 폴더가 임시 폴더가 아니다 - 실제 데이터를 덮어쓰지 않으려고 멈춘다: %s" % walk_cache.walk_dir())
    d = os.path.join(walk_cache.walk_dir(), "0999")
    os.makedirs(d, exist_ok=True)
    sheet = Image.new("RGBA", (32 * 4, 40 * 8), (0, 0, 0, 0))
    tone = {2: (200, 40, 40, 255), 6: (40, 40, 200, 255)}       # 오른쪽 줄은 빨강, 왼쪽 줄은 파랑
    for row in range(8):
        for i in range(4):
            sheet.paste(tone.get(row, (90, 90, 90, 255)), (i * 32 + 8, row * 40 + 10 + (i % 2), i * 32 + 24, row * 40 + 34))
    sheet.save(os.path.join(d, "Walk.png"))
    json.dump({"ok": True, "frameW": 32, "frameH": 40, "durations": [8, 10, 8, 10], "frames": 4, "rows": 8, "src": "ow",
               "rowmap": {"down": 0, "downright": 1, "right": 2, "upright": 3, "up": 4, "upleft": 5, "left": 6, "downleft": 7}},
              open(os.path.join(d, "Walk.json"), "w"))
    fa, da = F.walk_frames(None, 999, False, "a")
    fb, _db = F.walk_frames(None, 999, False, "b")
    chk("**걷는 도트로 선다**: 왼쪽에 선 쪽은 오른쪽을 보는 그림, 오른쪽에 선 쪽은 왼쪽을 보는 그림",
        fa[0].getpixel((fa[0].width // 2, fa[0].height // 2))[:3] == (200, 40, 40)
        and fb[0].getpixel((fb[0].width // 2, fb[0].height // 2))[:3] == (40, 40, 200))
    chk("  맵과 같은 두 배 크기다 (16 x 24 로 그린 몸이 32 x 48)", fa[0].size == (32, 48), fa[0].size)
    chk("  걷기밖에 없는 종은 제자리에서 걷는다 (걷는 그림 넉 장, 한 장에 1/60초 x 8~10)", len(fa) == 4 and da == [133, 167, 133, 167], da)
    chk("  걷는 도트가 없는 종이면 None (배틀 도트로 대신한다)", F.walk_frames(None, 998, False, "a") is None)
    big = Image.new("RGBA", (96 * 2, 96 * 8), (0, 0, 0, 0))
    for row in range(8):
        for i in range(2):
            big.paste((90, 160, 90, 255), (i * 96 + 8, row * 96 + 6, i * 96 + 88, row * 96 + 90))
    d2 = os.path.join(walk_cache.walk_dir(), "0997")
    os.makedirs(d2, exist_ok=True)
    big.save(os.path.join(d2, "Walk.png"))
    json.dump({"ok": True, "frameW": 96, "frameH": 96, "durations": [10, 10], "frames": 2, "rows": 8, "src": "ow"},
              open(os.path.join(d2, "Walk.json"), "w"))
    fbig, _d = F.walk_frames(None, 997, False, "a")
    chk("  덩치가 큰 종은 칸을 넘지 않게 줄인다", fbig[0].height <= F.MON_MAX_H and fbig[0].width <= F.MON_W
        and fbig[0].height >= F.MON_MAX_H - 2, fbig[0].size)

    print("\n=== 배틀 창이 뜰 때 장면을 덮었다 걷는 띠 ===")
    from poketdesktop import enter_fx as EF
    w, h = 876, 306

    def area(k):
        return sum((x1 - x0) * (y1 - y0) for x0, y0, x1, y1 in EF.blinds(w, h, k)) / float(w * h)
    chk("다 걷혔을 때는 아무것도 안 덮는다, 다 닫혔을 때는 화면을 빈틈없이 덮는다", area(0.0) == 0.0 and area(1.0) == 1.0
        and area(-3) == 0.0 and area(9) == 1.0)
    chk("  띠는 늘 같은 수다 (세로로 화면을 빈틈없이 나눈다)", len(EF.blinds(w, h, 0.5)) == EF.ROWS
        and [b[1] for b in EF.blinds(w, h, 0.5)][1:] == [b[3] for b in EF.blinds(w, h, 0.5)][:-1]
        and EF.blinds(w, h, 0.5)[0][1] == 0 and EF.blinds(w, h, 0.5)[-1][3] == h)
    chk("  닫힐수록 덮는 넓이가 는다", [round(area(k / 10.0), 3) for k in range(11)] == sorted(round(area(k / 10.0), 3) for k in range(11))
        and 0.2 < area(0.5) < 0.8)
    half = EF.blinds(w, h, 0.6)
    chk("  줄마다 번갈아 왼쪽·오른쪽에서 자란다", all(b[0] == 0 for b in half[0::2]) and all(b[2] == w for b in half[1::2])
        and half[0][2] > 0 and half[1][0] < w)
    chk("  위 줄이 먼저 닫힌다 (물결치듯)", half[0][2] - half[0][0] >= half[2][2] - half[2][0] >= half[8][2] - half[8][0])


    print("\n=== 채팅에 친 명령 ===")
    members = [{"id": 1, "name": "가람", "me": True}, {"id": 2, "name": "나래"}, {"id": 3, "name": "Dasom"}]
    cmd = lambda t: SP.command(t, members, 1)               # noqa: E731
    chk("보통 말은 명령이 아니다 (그대로 보낸다)", cmd("안녕하세요") is None and cmd("친선전 할 사람?") is None
        and cmd("1/2 확률") is None and cmd("") is None and cmd(None) is None)
    chk("/친선전 = 상대를 구한다 (앞뒤 빈칸은 안 가린다)", cmd("/친선전") == ("seek",) and cmd("  /친선전  ") == ("seek",))
    chk("  짧게 쳐도 된다 (/친선, /배틀)", cmd("/친선") == ("seek",) and cmd("/배틀") == ("seek",))
    chk("/친선전 취소 = 그만둔다 (그만·끝 도)", [cmd("/친선전 %s" % x) for x in ("취소", "그만", "끝")] == [("cancel",)] * 3)
    chk("/친선전 닉네임 = 그 길드원에게 직접 신청한다", cmd("/친선전 나래") == ("ask", 2, "나래") and cmd("/친선전   나래 ") == ("ask", 2, "나래"))
    chk("  영문 이름은 대소문자를 안 가린다", cmd("/친선전 dasom") == ("ask", 3, "Dasom"))
    chk("  길드원이 아닌 이름은 까닭을 준다", cmd("/친선전 마루") == ("error", "'마루' 님은 길드원이 아닙니다."))
    chk("  자기 자신에게는 안 된다", cmd("/친선전 가람")[0] == "error" and "자기 자신" in cmd("/친선전 가람")[1])
    bad = cmd("/춤")
    chk("모르는 명령은 쓸 수 있는 것을 알려 준다 (말로 보내지 않는다)", bad[0] == "error" and "모르는 명령" in bad[1] and SP.CMD_HELP in bad[1]
        and cmd("/")[0] == "error")
    chk("  안내 글에 세 가지가 다 있다", all(x in SP.CMD_HELP for x in ("/친선전", "닉네임", "취소")) and "/친선전" in SP.CMD_HINT)

    print("\n=== 채팅에 놓인 카드의 모습 ===")
    A, B = {"id": 2, "name": "나래"}, {"id": 3, "name": "다솜"}
    seek_c = {"k": "friendly", "s": "seek", "a": A}
    chk("카드인 줄만 카드다 (모르는 종류의 카드는 보통 알림 줄로 그린다)", SP.is_card({"card": seek_c}) and not SP.is_card({"body": "말"})
        and not SP.is_card({"card": {"k": "raid"}}) and not SP.is_card({"card": "x"}) and not SP.is_card(None))
    live = {"seeking": [{"id": 2, "name": "나래", "left": 100, "card": 7}], "fights": [], "limit": 3}
    v = SP.chat_card(seek_c, 7, live, 1)
    chk("남이 구한다: 누가 구하는지와 [배틀] (누르면 그 사람의 것을 받는다). **상태 글은 없다** - 본문이 이미 그 말이다",
        (v["tag"], v["text"], v["button"], v["act"], v["arg"], v["tone"])
        == ("", "나래 님이 친선전 상대를 구합니다.", "배틀", "accept", 2, "seek"), v)
    v = SP.chat_card(seek_c, 7, live, 2)
    chk("내가 구한다: '구하는 중' 이라는 말과 [취소]", (v["tag"], v["text"], v["button"], v["act"])
        == ("", "친선전 상대를 구하는 중입니다.", "취소", "cancel"), v)
    v = SP.chat_card(seek_c, 7, {"seeking": [], "fights": []}, 1)
    chk("**지금 모습에 그 줄이 없으면 단추가 없다** (카드에는 '구함' 이라 적혀 있어도 - 서버가 다시 떴다)", (v["tag"], v["button"], v["act"], v["tone"])
        == ("마감", None, None, "off") and "나래" in v["text"], v)
    v = SP.chat_card(seek_c, 7, {"seeking": [{"id": 2, "name": "나래", "left": 100, "card": 8}], "fights": []}, 1)
    chk("  같은 사람이 새로 놓은 카드가 따로 있으면 옛 카드는 닫힌 것이다 (줄 번호로 본다)", v["tag"] == "마감" and v["button"] is None)
    v = SP.chat_card({"k": "friendly", "s": "closed", "a": A}, 7, live, 1)
    chk("  닫혔다가 되살아난 카드: 카드 소식을 놓쳐도 지금 모습대로 그린다 (폴링 화면)", v["button"] == "배틀" and v["act"] == "accept")
    fight_c = {"k": "friendly", "s": "fight", "a": A, "b": B, "mid": 50}
    going = {"seeking": [], "fights": [{"id": 50, "card": 7, "a": A, "b": B, "over": False}], "limit": 3}
    v = SP.chat_card(fight_c, 7, going, 1)
    chk("진행 중인 판: '진행 중' · [관전] (누르면 그 판을 본다)", (v["tag"], v["text"], v["button"], v["act"], v["arg"], v["tone"])
        == ("진행 중", "나래  vs  다솜", "관전", "watch", 50, "fight"), v)
    v = SP.chat_card(fight_c, 7, going, 1, watching=50)
    chk("  내가 보고 있는 판: '관전 중' · [그만 보기]", (v["tag"], v["button"], v["act"]) == ("관전 중", "그만 보기", "unwatch"), v)
    v = SP.chat_card(fight_c, 7, going, 1, watching=51)
    chk("  다른 판을 보고 있으면 [관전] 그대로", v["button"] == "관전")
    v = SP.chat_card(fight_c, 7, going, 3)
    chk("  내가 싸우는 판: [내 배틀]", (v["tag"], v["button"], v["act"]) == ("진행 중", "내 배틀", "mine"), v)
    v = SP.chat_card(seek_c, 7, going, 1)
    chk("  카드에 아직 '구함' 이라 적혀 있어도 판이 열렸으면 [관전] 이다 (카드 소식을 놓쳤다)", v["button"] == "관전" and v["text"] == "나래  vs  다솜")
    v = SP.chat_card(fight_c, 7, {"seeking": [], "fights": []}, 1)
    chk("끝난 판(결과를 아직 모른다): '끝' · 단추 없음", (v["tag"], v["text"], v["button"], v["tone"]) == ("끝", "나래  vs  다솜", None, "done"), v)
    over = dict(fight_c, s="over")
    got = [SP.chat_card(dict(over, result=r), 7, {}, 1)["text"] for r in ("a", "b", "draw", None)]
    chk("끝난 판: 누가 이겼는지 적는다 (비겼으면 무승부, 승패 없이 끝났으면 이름만)", got == ["나래  vs  다솜   ·   나래 님 승리",
        "나래  vs  다솜   ·   다솜 님 승리", "나래  vs  다솜   ·   무승부", "나래  vs  다솜"], got)
    v = SP.chat_card(dict(over, result="a"), 7, {"fights": [{"id": 50, "card": 7, "a": A, "b": B, "over": True}]}, 1)
    chk("  끝났다고 온 판에는 단추가 붙지 않는다", v["button"] is None and v["tag"] == "끝")
    v = SP.chat_card({"k": "friendly"}, 7, None, None)
    chk("빠진 것이 있어도 죽지 않는다", v["button"] is None and "?" in v["text"])

    print("\n%d개 통과, %d개 실패" % (OK, FAIL))
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
