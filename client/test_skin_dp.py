# -*- coding: utf-8 -*-
"""화면 테마 '디아루가·펄기아'(skins/dp) 검사 - 허브 · 가방.

    python client/test_skin_dp.py

**창을 진짜로 띄운다** (가짜 서버). 테마의 화면은 칠하기만 새로 하고 동작은 기본 화면의 것을 그대로
쓰므로, 여기서는 'DP 로 칠한 자리가 기본 동작과 맞물리나' 를 본다.

  1. POKET_SKIN=dp 면 허브 · 가방 탭 · 가방 칸이 DP 클래스로 뜬다 (skins.override). 기본은 그대로.
  2. 허브: X 메뉴로 탭을 오가고, 점(set_badge)을 찍고 지운다.
     **캔버스 단추에 마우스를 올리고 눌러도 그리기가 끝없이 돌지 않는다** (올릴 때 도형을 지우고 새로 그리면
     Tk 가 새 도형에 <Enter> 를 또 보내 root.update() 가 안 돌아왔다).
  3. 가방: 주머니를 고르면 그 분류만 보이고, 찾는 말을 넣으면 모든 주머니에서 찾는다.
  4. 도구를 고르면 설명 띠 · 단추 글씨가 바뀐다. 은색병뚜껑은 능력 칸, 노력치 도구는 노력치 칸.
  5. 포켓몬 판을 눌러 고르고, '쓰기' 를 누르면 서버에 그 도구 · 그 포켓몬으로 간다.
  6. 기술머신 주머니를 누르면 기술머신 칸(DP)으로 넘어간다. 가진 것만 · 전부, 기술머신을 고르면 배울 포켓몬,
     판을 골라 가르치기. 다른 주머니를 누르면 도구 칸의 그 주머니로 돌아간다.
  7. 포켓몬(PC 박스): 칸을 눌러 고르면 요약이 바뀐다. 박스 넘기기 · 찾기, 여러 마리 골라 옮기기,
     박스 것과 파티 것 맞바꾸기(끌기), 데리고 다니기.
  8. 상점(프렌들리숍): 분류 메뉴 · 찾기 · 고르기 · 개수(▲▼, 빠른 개수) · 사기는 서버에 그 도구 · 그 개수로.
  9. 도감: 세대 · 잡은 것 · 찾기로 거르고, 줄을 누르면 왼쪽 화면이 그 종. 업적 칸을 열고 닫는다.
 10. 마이페이지(트레이너 카드) · 설정: 게시판 활동 탭 · 쪽 넘기기, 설정의 ◀ ▶ 가 값을 바꾸고 저장한다.
 11. 관장 배틀(DS 두 화면): '싸운다' → 기술 넷 → 기술을 쓰면 서버에 그 기술. 기술에 올리면 글상자에 설명.
     포켓몬 → 교체 판 → 취소. Z기술을 켜도 기술 화면에 남는다. 창 크기를 바꿔도 보던 화면 그대로.
     끝까지 두면 결과 칸, '지도로 돌아가기' 로 닫힌다. 그리는 중에 난 예외가 없다.
 12. 실시간 배틀: 위 띠에 턴 · 남은 수 · 남은 시간. 기술을 보내면 '기다리는 중' 판(기권은 눌린다),
     상대가 고르면 턴이 돌고 다시 명령 화면. 끝나면 결과 칸과 '닫기'.
 13. 레이드 배틀: 보스 판(이름 · 체력 숫자), 참가자 판, 위 띠의 'N명 참가', 오른쪽 아래 단추는 '물러나기'.
     싸운다 → 기술 → 라운드가 돌고 다시 명령 화면. 교체 판은 '교체한 라운드에는 공격 못 한다' 고 말한다. 끝나면 '닫기'.
 14. 관장(타운맵): 전국 화면의 시·도 바로 가기 열여섯, 시·도로 들어가면 그 안의 트레이너 목록 · 거르기,
     줄에 올리면 지도의 그곳이 빨갛게, 줄을 누르면 카드와 '도전하기', '‹ 목록' 으로 돌아온다.
 15. 랭킹(배틀타워 기록판): 머리줄 · 내 티어 판 · 규칙 · 순위 줄 · 명예의 전당. '대전 기록' 으로 바꾸면 탭으로 거르고,
     '다시 보기' 를 누르면 그 대전을 연다.
 16. 친구(친구수첩): 받은 신청 · 친구 · 보낸 신청 · 차단 줄, 줄의 단추를 누르면 그 일이 서버로 간다.
     닉네임 찾기의 결과 줄과 '친구 신청'.
 17. 게시판: 공지가 맨 위, 종류 탭 · 찾기, 글을 열면 본문 · 좋아요 · 댓글, 좋아요 켜기, 댓글 · 답글 달기,
     새 글 쓰기 · 고치기.
 18. 탐험(포켓치): 탐험 칸 셋(나가 있는 것 · 빈 칸), 곳 · 시간을 고르면 목록이 다시 서고, 고른 포켓몬을 보내면
     서버로 간다. 남은 시간이 1초마다 준다. 불러들이기.
 19. 위젯 빛깔(widgets.py): 기본 화면의 코드가 만든 위젯은 밝은 바탕 · 진한 글자 · 갈무리 글꼴로 옮겨지고,
     DP 화면이 만든 위젯은 제 빛깔 그대로다. 단추 · 고르기 단추는 DP 것으로 바뀐다. 캔버스 도형은 그대로.
 20. 길드: 흙빛 머리(길드 이름 · 코인), 흰 길드 판, 칸을 오가고 채팅을 보내면 서버로 간다.
"""
import os
import sys
import tempfile

os.environ.setdefault("POKET_HOME", tempfile.mkdtemp(prefix="poket-test-skin-dp-"))
# 물려받는 테마(pt · gs …)도 같은 검사로 본다: POKET_SKIN=pt python3 test_skin_dp.py
os.environ["POKET_SKIN"] = os.environ.get("POKET_SKIN") or "dp"

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.dirname(HERE))

import json                                                 # noqa: E402
import tkinter as tk                                        # noqa: E402

import smoke_box_filter as SB                               # noqa: E402
import smoke_tms as ST                                      # noqa: E402
import test_big_lists as TBL                                # noqa: E402
from common import pokelogic as P                           # noqa: E402
from poketdesktop import platform_os as PLAT                # noqa: E402
from poketdesktop import skins                              # noqa: E402
from poketdesktop import ui_common as U                     # noqa: E402
from poketdesktop import ui_hub                             # noqa: E402

OK = FAIL = 0
ROOT = os.path.dirname(HERE)


def ours(mod, screen):
    """그 화면 클래스가 이번 테마의 것인가 - 그 테마가 따로 그렸거나, 물려받은 DP 의 것."""
    return any(mod.endswith("skins.%s.%s" % (k, screen)) for k in skins.chain())


def look(name, cond, got=""):
    """DP 의 빛깔 · 자리를 그대로 견주는 줄. 물려받은 테마(pt · gs …)는 제 빛깔 · 자리로 그리므로 DP 일 때만 본다."""
    if skins.active() == "dp":
        chk(name, cond, got)
    else:
        print("  --   %s  (DP 빛깔 · 자리 비교 - %s 테마는 건너뜀)" % (name, skins.active()))


def chk(name, cond, got=""):
    global OK, FAIL
    if cond:
        OK += 1
        print("  OK   %s" % name)
    else:
        FAIL += 1
        print("  FAIL %s   %r" % (name, got))


class Api(TBL.Api):
    def __init__(self, mons, items):
        TBL.Api.__init__(self, mons, items)
        self.tm = ST.FakeApi(ST.load_tms(), [
            {"id": 1000 + i, "name": n, "num": num, "level": 50, "shiny": False,
             "moves": ["TACKLE"], "known": i == 1}
            for i, (n, num) in enumerate([("리자몽", 6), ("한카리아스", 445), ("망나뇽", 149)])])
        self.used = []

    def tms(self):
        out = self.tm.tms()
        out["newCount"] = 0
        return out

    def tm_learners(self, no):
        return self.tm.tm_learners(no)

    def tms_seen(self, nos=None):
        return {"newCount": 0}

    def tm_use(self, no, pid, forget=""):
        return self.tm.tm_use(no, pid, forget)

    def dexbook(self):
        return {"seen": list(range(1, 200)), "caught": [n for n in range(1, 160) if n % 3],
                "gens": {"1": {"caught": 100, "total": 151}}, "total": 1025}

    def mypage(self):
        import test_mypage_ui as TM
        return TM.payload()

    def board_mine(self, what="posts", page=1):
        import test_mypage_ui as TM
        self.calls.append(("mine", what, page))
        return TM.mine_page(what, page)

    def buy(self, item_id, n):
        self.calls.append(("buy", item_id, n))
        return {"message": "샀다.", "money": 1000, "bag": dict(self.bag, **{item_id: self.bag.get(item_id, 0) + n})}

    def use_item(self, item_id, pid, stat="", hour=0, form="", tm_type=""):
        self.used.append((item_id, pid, stat))
        return {"message": "썼다."}


class App(TBL.App):
    def __init__(self, root, api, dex):
        TBL.App.__init__(self, root, api, dex)
        self.tm_new = 0
        self.hub = None
        self.overlay = None

    def note_tms(self, n, reload=True):
        self.tm_new = n

    def refresh_tray(self):
        pass

    def logout(self):
        pass

    def delete_account(self):
        pass

    def __getattr__(self, name):
        raise AttributeError(name)


def hover_no_loop(root):
    import threading
    from poketdesktop.skins.dp import kit
    top = tk.Toplevel(root)
    cv = tk.Canvas(top, width=300, height=120, bg="#ffffff")
    cv.pack()
    hits = []
    b = kit.CButton(cv, "도전하기", lambda: (hits.append(1), b.configure(text="눌렸다")), "red")
    b.layout(20, 20, 220, 80)
    top.update()
    # 끝없이 돌면 이 검사가 멈춘다 - 20초 지나면 실패로 끝낸다
    stuck = threading.Timer(20, lambda: (print("  FAIL 단추에 올리면 그리기가 끝없이 돈다"), os._exit(1)))
    stuck.start()
    try:
        cv.event_generate("<Motion>", x=100, y=50)
        TBL.settle(root, 0.2)
        lit = cv.itemcget(b._body_id, "fill")
        cv.event_generate("<ButtonPress-1>", x=100, y=50)
        cv.event_generate("<ButtonRelease-1>", x=100, y=50)
        TBL.settle(root, 0.2)
    finally:
        stuck.cancel()
    chk("단추에 올리면 밝아지고, 눌러도 그리기가 돌지 않는다", b._hover is False and hits == [1]
        and lit == kit.KINDS["red"][1], (lit, hits))
    top.destroy()


def gym_battle(root, dex, errors):
    import test_gym_ui as TG
    from poketdesktop import ui_gym_battle as GB
    gyms = json.load(open(os.path.join(TG.DATA, "gyms.json"), encoding="utf-8"))
    kmap = {"sido": [], "sgg": []}
    # 앞 포켓몬이 한 방에 쓰러지지 않아야 '스스로 교체' 를 볼 수 있다 (뮤츠가 앞)
    party = [TG.mon(dex, "MEWTWO", 100, ["PSYSTRIKE", "FLAMETHROWER", "ICEBEAM", "RECOVER"], "PRESSURE", 13),
             TG.mon(dex, "CHARIZARD", 50, ["FLAMETHROWER", "DRAGONCLAW", "AIRSLASH", "ROOST"], "BLAZE", 11),
             TG.mon(dex, "GARCHOMP", 62, ["EARTHQUAKE", "DRAGONCLAW", "STONEEDGE", "SWORDSDANCE"], "ROUGHSKIN", 12)]
    api = TG.FakeApi(dex, gyms, kmap, party)
    app = TG.FakeApp(root, api, dex)
    app.settings = {}
    orig_later = GB.GymBattleWindow.later
    GB.GymBattleWindow.later = lambda self, ms, fn: orig_later(self, max(1, ms // 10), fn)
    try:
        region = next(t["region"] for t in gyms["trainers"] if t["name"] == "난천")
        b = GB.GymBattleWindow(app, api.gym_start(region))
        chk("관장 배틀은 DP", ours(type(b).__module__, "gym_battle"), type(b).__module__)
        TG.pump(root, lambda: not b.busy, 30)
        TBL.settle(root, 0.3)
        chk("처음부터 기술 넷 + 포켓몬 · 기권 (싸운다 단계 없음, 취소 없음)", b._page == "moves"
            and len(b._move_btns) == 4 and b.switch_btn.box and b.forfeit_btn.box and not b.cancel_btn.box
            and b.switch_btn.enabled and b.forfeit_btn.enabled, (b._page, len(b._move_btns)))
        chk("말은 '무엇을 할까?'", "무엇을 할까" in b._said, b._said)
        mv = b._move_btns[0]
        b.lower._motion(type("E", (), {"x": (mv.box[0] + mv.box[2]) // 2, "y": (mv.box[1] + mv.box[3]) // 2})())
        said = b.mcv.itemcget(b.mcv.find_withtag("msg")[-1], "text").replace("\n", " ")
        chk("기술에 올리면 글상자에 설명", (mv.move.get("desc") or "")[:8] in said, said)
        b.lower._leave(None)
        said = b.mcv.itemcget(b.mcv.find_withtag("msg")[-1], "text")
        chk("내려 놓으면 하던 말로", "무엇을 할까" in said, said)
        w, h = b._lower_wh()
        inside = all(0 <= x.box[0] and x.box[2] <= w and x.box[3] <= h
                     for x in b._move_btns + [b.switch_btn, b.forfeit_btn])
        chk("기술 · 포켓몬 · 기권 단추가 아래 화면 안에 있다", inside, [x.box for x in b._move_btns])
        # Z기술: 켜도 기술 화면에 남고 이름이 바뀐다
        b.view["gimmick"] = {"zMoves": [{"key": "FLAMETHROWER", "name": "다이내믹풀플레임", "power": 175}]}
        b.show_commands()
        b.gim.z.toggle()
        TBL.settle(root, 0.1)
        chk("Z기술을 켜도 기술 화면, 이름이 Z기술로", b._page == "moves"
            and b._moves[1].get("kr") == "다이내믹풀플레임", (b._page, b._moves[1].get("kr")))
        b.gim.z.toggle()
        b.view["gimmick"] = None
        # 메가진화: 알약이 아랫줄 왼쪽에 서고, 켜도 기술 화면 그대로
        b.view["canMega"] = True
        b.show_commands()
        b.mega.toggle()
        TBL.settle(root, 0.1)
        look("메가진화를 켜도 기술 화면, 알약이 포켓몬 단추 왼쪽", b._page == "moves" and b.mega.on and b.mega.shown
            and b.tbar.winfo_x() + b.tbar.winfo_reqwidth() < b.switch_btn.box[0],
            (b._page, b.mega.on, b.tbar.winfo_x() + b.tbar.winfo_reqwidth(), b.switch_btn.box))
        b.mega.toggle()
        b.view["canMega"] = False
        b.show_commands()
        # 기술 쓰기 (마우스로 누른다)
        mv = b._move_btns[1]
        e = type("E", (), {"x": mv.box[0] + 20, "y": mv.box[1] + 20})()
        turn0 = b.view.get("turn", 0)
        b.lower._press(e)
        b.lower._release(e)
        chk("기술을 누르면 보내고 아래 화면은 빈다", b.busy and b._page == "busy", (b.busy, b._page))
        TG.pump(root, lambda: not b.busy, 30)
        chk("한 턴이 돈다", b.view.get("turn", 0) > turn0, b.view.get("turn"))
        if b.view.get("needSwitch"):
            chk("쓰러졌으면 교체 화면, 취소 없음", b._page == "switch" and not b.cancel_btn.box, b._page)
        else:
            chk("턴이 끝나면 다시 기술 화면", b._page == "moves", b._page)
            b.switch_btn.invoke()
            chk("포켓몬 → 교체 판 (파티 수) + 취소", b._page == "switch"
                and len(b._plate_hits) == len(b.view["me"]["team"]) and b.cancel_btn.box,
                (b._page, len(b._plate_hits)))
            chk("나와 있는 포켓몬 판은 못 누른다", not b._plate_hits[b.view["me"]["slot"]].enabled)
            b.cancel_btn.invoke()
            chk("취소 → 기술 화면 (포켓몬 다시 눌린다)", b._page == "moves" and b.switch_btn.enabled
                and not b.cancel_btn.box, b._page)
        # 창 크기를 바꿔도 보던 화면
        page = b._page
        b.win.geometry("%dx%d" % (int(b.ww * 0.86), int(b.win.winfo_height() * 0.86)))
        TBL.settle(root, 0.5)
        b.zoom_apply()
        TBL.settle(root, 0.2)
        chk("창 크기를 바꿔도 같은 화면", b._page == page and len(b._move_btns) == 4 if page == "moves"
            else b._page == page,
            (page, b._page))
        # 끝까지
        for _ in range(60):
            if b.view.get("over"):
                break
            if b.view.get("needSwitch"):
                side = b.view["me"]
                b.do_switch(next(i for i, m in enumerate(side["team"]) if not m.get("fainted") and i != side["slot"]))
            else:
                side = b.view["me"]
                b.use_move(side["team"][side["slot"]]["moves"][0]["key"])
            TG.pump(root, lambda: not b.busy, 30)
        TBL.settle(root, 0.3)
        chk("끝나면 결과 칸 + '지도로 돌아가기'", b._page == "result" and b.done_btn.box
            and b.done_btn.text == "지도로 돌아가기", (b._page, b.view.get("result")))
        b.done_btn.invoke()
        chk("'지도로 돌아가기' 로 닫힌다", not b.alive)
    finally:
        GB.GymBattleWindow.later = orig_later


def live_battle(root, dex):
    import test_live_ui as TL
    from poketdesktop import ui_live_battle as LUI
    api = TL.FakeApi(dex)
    app = TL.FakeApp(root, api, dex)
    w = LUI.LiveBattleWindow(app, api.match())
    chk("실시간 배틀은 DP", ours(type(w).__module__, "live_battle"), type(w).__module__)
    TL.pump(root, lambda: not w.busy and w._page == "moves", 30)
    chk("처음부터 기술 + 포켓몬 · 기권", w._page == "moves" and len(w._move_btns) == len(w.view["me"]["moves"][:4])
        and w.switch_btn.box and w.forfeit_btn.box and w.forfeit_btn.enabled, (w._page, len(w._move_btns)))
    strip = " ".join(w.bcv.itemcget(i, "text") for i in w.bcv.find_withtag("strip") if w.bcv.type(i) == "text")
    chk("위 띠에 턴 · 남은 수 · 남은 시간", "턴" in strip and "2 : 2" in strip and "초" in strip, strip)
    chk("이름표에 '나' / 상대 이름", "나" == w._plate_note("me", {}) and "상대" in w._plate_note("foe", {}))
    api.auto_foe = False
    w._move_btns[0].invoke()
    TL.pump(root, lambda: w._page == "wait", 10)
    chk("보내면 '기다리는 중' 판, 기권은 눌린다", w._page == "wait" and w.forfeit_btn.enabled and w.forfeit_btn.box
        and "기다리는 중" in w._wait[0], (w._page, getattr(w, "_wait", None)))
    sent = [c for c in api.calls if c.startswith("act:")]
    chk("기술은 한 번만 간다", len(sent) == 1, sent)
    # 상대가 고른다 → 폴링이 턴을 받아 재생 → 다시 기술 화면
    api.lb.choose("b", *api.lb.auto_choice("b"))
    api.events = api.lb.resolve()
    api.turn = api.lb.turn
    TL.pump(root, lambda: not w.busy and w._page in ("moves", "switch") and w.view.get("turn", 0) >= 1, 30)
    chk("상대가 고르면 턴이 돌고 다시 고른다", w.view.get("turn", 0) >= 1 and w._page in ("moves", "switch"),
        (w.view.get("turn"), w._page))
    api.auto_foe = True
    for _ in range(80):
        if w._result_shown:
            break
        if not w.busy and not w.sent and w.view.get("canAct"):
            me = w.view.get("me") or {}
            if w.view.get("phase") == "switch":
                w.do_switch((me.get("switches") or [0])[0])
            else:
                w.use_move(me["moves"][0]["key"])
        TL.rest(root, 0.2)
    TL.pump(root, lambda: w._page == "result", 10)
    chk("끝나면 결과 칸 + '닫기'", w._page == "result" and w.done_btn.text == "닫기" and w.done_btn.box,
        (w._page, w.done_btn.text))
    w.done_btn.invoke()
    chk("'닫기' 로 닫힌다", not w.alive)


def raid_battle(root, dex):
    import test_raid_ui as TR
    from poketdesktop import ui_raid_battle as RUI
    api = TR.FakeApi(dex, n=5, revealed=True)
    room = api.begin(rounds=3)                  # (세 라운드면 끝난다 - 결과 칸까지 본다)
    app = TR.FakeApp(root, api, dex)
    w = RUI.RaidBattleWindow(app, room)
    chk("레이드 배틀은 DP", ours(type(w).__module__, "raid_battle"), type(w).__module__)
    TR.pump(root, lambda: not w.busy and w._page == "moves", 30)
    chk("처음부터 기술 화면, 오른쪽 아래는 '물러나기'", w._page == "moves" and w._move_btns and w.leave_btn is w.forfeit_btn
        and w.leave_btn.text == "물러나기" and w.leave_btn.box, (w._page, w.forfeit_btn.text))
    chk("보스 판에 이름 · 체력 숫자", "뮤츠" in w.cv.itemcget(w.boss_name, "text")
        and "/" in w.cv.itemcget(w.hp_text, "text"),
        (w.cv.itemcget(w.boss_name, "text"), w.cv.itemcget(w.hp_text, "text")))
    names = [w.cv.itemcget(w.slots[i]["name"], "text") for i in range(5)]
    chk("참가자 판 다섯 (내 것은 '(나)')", len(names) == 5 and "(나)" in names[0], names)
    def strip():
        return " ".join(w.bcv.itemcget(i, "text") for i in w.bcv.find_withtag("strip") if w.bcv.type(i) == "text")
    TR.pump(root, lambda: "초" in strip(), 5)        # (남은 시간은 폴링이 적는다 - 기본 창도 같다)
    chk("위 띠에 'N명 참가' · 남은 시간", "명 참가" in strip() and "초" in strip(), strip())
    w.switch_btn.invoke()
    said = w.mcv.itemcget(w.mcv.find_withtag("msg")[-1], "text").replace("\n", " ")
    chk("교체 판: 교체한 라운드에는 공격 못 한다", w._page == "switch" and "공격하지 못합니다" in said
        and w.cancel_btn.box, (w._page, said))
    w.cancel_btn.invoke()
    chk("취소 → 기술 화면 (물러나기는 같은 자리)", w._page == "moves" and w.leave_btn.box and w.switch_btn.enabled,
        w._page)
    rnd = w.view.get("round", 0)
    w._move_btns[0].invoke()
    TR.pump(root, lambda: not w.busy and w.view.get("round", 0) > rnd and w._page == "moves", 30)
    chk("기술 → 라운드가 돌고 다시 기술 화면", w.view.get("round", 0) > rnd and w._page == "moves",
        (w.view.get("round"), w._page))
    for _ in range(80):
        if w._result_shown:
            break
        me = w.view.get("me") or {}
        if not w.busy and not w.sent and me.get("canAct"):
            w.use_move(me["moves"][0]["key"])
        TR.rest(root, 0.2)
    TR.pump(root, lambda: w._page == "result", 10)
    chk("끝나면 결과 칸 + '닫기'", w._page == "result" and w.done_btn.text == "닫기", (w._page, w.done_btn.text))
    w.done_btn.invoke()
    chk("'닫기' 로 닫힌다", not w.alive)


def gym_map(root, dex):
    import test_gym_ui as TG
    from poketdesktop import ui_gym
    gyms = json.load(open(os.path.join(TG.DATA, "gyms.json"), encoding="utf-8"))
    kmap = json.load(open(os.path.join(TG.DATA, "korea_map.json"), encoding="utf-8"))
    api = TG.FakeApi(dex, gyms, kmap, [TG.mon(dex, "MEWTWO", 100, ["PSYSTRIKE"], "PRESSURE", 11)])
    name_of = {t["name"]: t["region"] for t in gyms["trainers"]}
    api.cleared.add(name_of["난천"])
    app = TG.FakeApp(root, api, dex)
    app.settings = {}
    gw = ui_gym.GymWindow(root, app)
    gw.win.geometry("1040x700+20+20")
    chk("관장 탭은 DP", ours(type(gw).__module__, "gym"), type(gw).__module__)
    TG.pump(root, lambda: gw.data is not None and gw.map is not None, 20)
    TBL.settle(root, 0.5)
    cells = [i for i in gw.scv.find_withtag("sdcell") if gw.scv.type(i) == "text"]
    chk("전국: 시·도 바로 가기 열여섯", len(cells) == 32, len(cells))
    chk("머리에 이긴 곳 수", "이긴 곳 1 / 256" in gw.sub.text, gw.sub.text)
    gw.enter_sido("41")
    TBL.settle(root, 0.4)
    n41 = len([d for d in kmap["sgg"] if d["sido"] == "41"])
    chk("경기: 트레이너 %d줄" % n41, len(gw.vl.rows) == n41 and gw._mode == "list", len(gw.vl.rows))
    gw.set_filter("new")
    TBL.settle(root, 0.2)
    chk("미도전으로 거르기", gw.which == "new" and all(not d[0].get("cleared") for _h, d in gw.vl.rows),
        len(gw.vl.rows))
    gw.set_filter("all")
    data = gw.vl.rows[0][1]
    code = data[0]["region"]
    gw._row_hover(data)
    chk("줄에 올리면 지도의 그곳이 빨갛다", gw.cv.itemcget("g%s" % code, "outline") == gw.MAP["hot"],
        gw.cv.itemcget("g%s" % code, "outline"))
    gw._row_hover(None)
    gw.pick_row(code)
    TG.pump(root, lambda: isinstance(gw._card, tuple), 10)
    TBL.settle(root, 0.3)
    chk("줄을 누르면 카드와 '도전하기'", gw._mode == "card" and gw.go_btn.box and gw.go_btn.text == "도전하기"
        and gw.list_btn.box, (gw._mode, gw.go_btn.text))
    texts_ = [gw.ccv.itemcget(i, "text") for i in gw.ccv.find_all() if gw.ccv.type(i) == "text"]
    chk("카드에 이름 · 데리고 있는 포켓몬", data[0]["name"] in texts_ and "데리고 있는 포켓몬" in texts_, texts_[:6])
    gw.list_btn.invoke()
    TBL.settle(root, 0.2)
    chk("'‹ 목록' 으로 목록에 돌아온다", gw._mode == "list" and gw.sido == "41" and not gw.go_btn.box, gw._mode)
    gw.jump(name_of["난천"])
    TG.pump(root, lambda: isinstance(gw._card, tuple), 10)
    chk("이긴 곳 카드: 이긴 기록", "✓ 이긴 곳" in gw._card[1]["record"], gw._card[1]["record"])
    gw.close()


def rank_board(root):
    import smoke_season as SS
    from poketdesktop import ui_rank
    app = SS.FakeApp(root)
    rw = ui_rank.RankWindow(app)
    chk("랭킹은 DP", ours(type(rw).__module__, "rank"), type(rw).__module__)
    TBL.wait(root, lambda: bool(rw._items) and not rw.busy, 10)
    TBL.settle(root, 0.4)
    kinds = [k for k, _d in rw._items]
    chk("내 티어 판 · 규칙 · 순위 줄 둘 · 명예의 전당", kinds[:2] == ["me", "rules"] and kinds.count("rank") == 2
        and kinds.count("hall") == 1, kinds)
    chk("머리줄: 시즌 · 순위 · 오늘 몇 판", rw._head[0] == "랭킹  ·  시즌 2" and "2위" in rw._head[1]
        and "오늘 12판 가능" in rw._head[1], rw._head)
    mine = [d for k, d in rw._items if k == "rank" and d["mine"]]
    chk("내 줄 표시", len(mine) == 1 and mine[0]["name"] == "나", mine)
    rw.mode_btn.invoke()
    TBL.wait(root, lambda: rw.mode == "records" and not rw.busy and any(k == "rec" for k, _d in rw._items), 10)
    chk("대전 기록: 세 판, 단추 글은 '랭킹'", [k for k, _d in rw._items].count("rec") == 3
        and rw.mode_btn.text == "랭킹", [k for k, _d in rw._items])
    rw._pick_filter("defend")
    recs = [d for k, d in rw._items if k == "rec"]
    chk("공격받은 판만", len(recs) == 1 and not recs[0]["attack"], recs)
    rw._pick_filter("all")
    i = next(n for n, (k, d) in enumerate(rw._items) if k == "rec" and d["watch"])
    w = rw.vl.cv.winfo_width()
    rw._click_row(rw._items[i], w - U.h(30), 20, w)
    chk("'다시 보기' 를 누르면 그 대전을 연다", getattr(app, "watched", []) == [5], getattr(app, "watched", None))
    rw.close()


def friends_pad(root):
    import importlib.util
    spec = importlib.util.spec_from_file_location("friendfake", os.path.join(HERE, "test_skin_dp_friends.py"))
    FF = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(FF)
    from poketdesktop import ui_friends
    app = FF.App(root)
    fw = ui_friends.FriendsWindow(app)
    chk("친구는 DP", ours(type(fw).__module__, "friends"), type(fw).__module__)
    TBL.wait(root, lambda: bool(fw._items) and not fw.busy, 10)
    TBL.settle(root, 0.4)
    kinds = [k for k, _d in fw._items]
    chk("받은 신청 · 친구 넷 · 보낸 신청 · 차단", kinds.count("request") == 1 and kinds.count("friend") == 4
        and kinds.count("pending") == 1 and kinds.count("blocked") == 1, kinds)
    chk("머리에 몇 명 · 접속 중", fw.count.text == "4 / 30명  ·  접속 중 2명", fw.count.text)

    def press(kind, name, label):
        i = next(n for n, (k, d) in enumerate(fw._items) if k == kind and d.get("name") == name)
        fw.vl.see(i)
        TBL.settle(root, 0.2)
        hits = fw._hits.get((kind, id(fw._items[i][1])), [])
        acts = {"friend": fw._friend_actions, "request": lambda d: [("button",) + a for a in fw._request_actions(d)],
                "blocked": lambda d: [("button",) + a for a in fw._blocked_actions(d)]}[kind](fw._items[i][1])
        texts_ = [a[1] for a in acts if a[0] == "button"]
        x1, x2, y1, y2, _fn = hits[texts_.index(label)]
        fw._click_row(fw._items[i], (x1 + x2) // 2, (y1 + y2) // 2, fw.vl.cv.winfo_width())
    press("friend", "지우", "배틀")
    chk("친구 줄의 '배틀' → 그 친구에게 배틀", app.challenged == [2], app.challenged)
    press("request", "로켓단", "수락")
    TBL.wait(root, lambda: ("accept", 9) in app.api.calls, 5)
    chk("받은 신청의 '수락' → 서버로", ("accept", 9) in app.api.calls, app.api.calls)
    TBL.wait(root, lambda: not fw.busy, 5)
    press("blocked", "스팸", "차단 해제")
    TBL.wait(root, lambda: ("unblock", 11) in app.api.calls, 5)
    chk("차단 해제 → 서버로", ("unblock", 11) in app.api.calls, app.api.calls)
    TBL.wait(root, lambda: not fw.busy, 5)
    fw.q.set("빛나")
    fw.do_search()
    TBL.wait(root, lambda: bool(fw._found_hits), 5)
    x1, x2, y1, y2, _fn = fw._found_hits[0]
    fw._found_click(type("E", (), {"x": (x1 + x2) // 2, "y": (y1 + y2) // 2})())
    TBL.wait(root, lambda: ("request", "빛나") in app.api.calls, 5)
    chk("찾은 사람에게 '친구 신청'", ("request", "빛나") in app.api.calls, app.api.calls)
    fw.close()


def board(root):
    import test_board_ui as TB
    from poketdesktop import ui_board
    api = TB.FakeApi("지우", 2)
    n1, n2, talk, c1 = TB.seed(api)
    app = TB.FakeApp(root, api)
    w = ui_board.BoardWindow(app)
    chk("게시판은 DP", ours(type(w).__module__, "board"), type(w).__module__)
    TBL.wait(root, lambda: w.data is not None and bool(w._rows), 10)
    TBL.settle(root, 0.3)
    pins = [p["title"] for _k, p, pinned in w._rows if pinned]
    chk("공지 둘이 맨 위", pins == ["점검 안내", "시즌 3 안내"], pins)
    chk("머리에 글 수 · 쪽", w.count.text.startswith("글 ") and w._page_text == "1 / 2", (w.count.text, w._page_text))
    w.pick_kind("notice")
    TBL.wait(root, lambda: w.data.get("kind") == "notice", 5)
    chk("공지 탭", all(p["kind"] == "notice" for _k, p, _pin in w._rows), [p["kind"] for _k, p, _ in w._rows])
    w.pick_kind("all")
    TBL.wait(root, lambda: w.data.get("kind") == "all", 5)
    w.q_var.set("레이드")
    w.search()
    TBL.wait(root, lambda: (w.data or {}).get("q") == "레이드", 5)
    chk("찾기: 그 말이 든 글만, '전체 보기' 단추", [p["title"] for _k, p, _ in w._rows] == ["레이드 같이 하실 분"]
        and w.clear_btn.box, [p["title"] for _k, p, _ in w._rows])
    w.clear_search()
    TBL.wait(root, lambda: not (w.data or {}).get("q"), 5)
    w.open_post(talk)
    TBL.wait(root, lambda: w.view == "post" and w.post is not None and w.post.get("id") == talk, 5)
    TBL.settle(root, 0.3)
    texts_ = [w.pcv.itemcget(i, "text") for i in w.pcv.find_all() if w.pcv.type(i) == "text"]
    chk("글: 제목 · 본문 · '댓글 N' · 댓글", "레이드 같이 하실 분" in texts_ and any(t.startswith("댓글 ") for t in texts_)
        and "저요!" in texts_, texts_[:8])
    w.toggle_like()
    TBL.wait(root, lambda: w.post.get("liked") is True, 5)
    like = [w.pcv.itemcget(i, "text") for i in w.pcv.find_withtag("like") if w.pcv.type(i) == "text"]
    chk("좋아요를 누르면 단추가 켜진다 (♥)", "♥ 좋아요 1" in like, like)
    c = w.post["commentList"][0]
    w.set_reply(c)
    chk("답글 달기: 단추 글이 '답글 등록'", w.send_btn.text == "답글 등록" and w.reply_to is c, w.send_btn.text)
    w.input.insert("1.0", "저도 갈게요")
    w.send_comment()
    TBL.wait(root, lambda: any(r.get("body") == "저도 갈게요" for cc in w.post.get("commentList") or []
                               for r in cc.get("replies") or []), 5)
    chk("답글이 그 댓글 밑에 달린다", any(r.get("body") == "저도 갈게요" for r in
                                       next(cc for cc in w.post["commentList"] if cc["id"] == c["id"])["replies"]))
    w.show_write()
    TBL.settle(root, 0.3)
    chk("쓰기: 종류 · 제목 · 내용 · 등록", w.view == "write" and w.post_btn.box and w.post_btn.text == "등록",
        (w.view, w.post_btn.text))
    w.title_var.set("새 글 제목")
    w.text.insert("1.0", "새 글 내용")
    w._pick_post_kind("qna")
    w.submit_post()
    TBL.wait(root, lambda: w.view == "post" and w.post and w.post.get("title") == "새 글 제목", 5)
    chk("새 글을 올리면 그 글이 열린다 (Q&A)", w.post.get("kind") == "qna", w.post and w.post.get("kind"))
    w.close()


def expedition(root, dex):
    import test_expedition_ui as TE
    from poketdesktop import expedition_ui as XU
    from poketdesktop import ui_box
    from poketdesktop import ui_expedition as UE
    api = TE.FakeApi(dex, 40)
    box = [m for m in api.mons if not m.get("onDesktop")]
    api.expedition_send(box[0]["id"], "forest", 2)
    app = TE.FakeApp(root, api, dex)
    app.expedition = XU.Desk(app)
    w = UE.ExpeditionWindow(app)
    chk("탐험은 DP", ours(type(w).__module__, "expedition"), type(w).__module__)
    TBL.wait(root, lambda: w.state is not None and w._wait is None and bool(w.vl.rows), 10)
    TBL.settle(root, 0.5)
    chk("탐험 칸: 하나는 나가 있고 둘은 비었다", [o is not None for o, _d in w._slot_rows] == [True, False, False]
        and w._slot_note.startswith("1 / 3"), (w._slot_note, [o is not None for o, _d in w._slot_rows]))
    t0 = w.cv.itemcget(w.live[0][1][1], "text")
    api.now += 70
    w._t0 -= 70
    TBL.settle(root, 1.3)
    t1 = w.cv.itemcget(w.live[0][1][1], "text")
    chk("남은 시간이 흐른다", t0 != t1 and "남음" in t1, (t0, t1))
    w.set_place("sea")
    first = w.vl.rows[0][1]
    good = set(X_place_types("sea"))
    chk("곳을 바꾸면 그곳에서 잘할 포켓몬이 맨 위", bool(set(UE.types_of(dex, first[0])) & good) and w.pick == first[0]["id"],
        (UE.types_of(dex, first[0]), w.pick))
    w.set_hours(8)
    chk("8시간", w.hours == 8 and "물건" in w.hours_text())
    pick = w.vl.rows[2][1][0]["id"]
    w.vl.on_click(w.vl.rows[2][1])
    chk("줄을 누르면 그 포켓몬을 고른다", w.pick == pick, w.pick)
    w.send_btn.invoke()
    TBL.wait(root, lambda: ("send", pick, "sea", 8) in api.calls, 5)
    chk("보내기 → 서버로 그 포켓몬 · 곳 · 시간", ("send", pick, "sea", 8) in api.calls, api.calls[-3:])
    TBL.wait(root, lambda: sum(1 for o, _d in w._slot_rows if o) == 2, 5)
    chk("칸이 둘 찬다", sum(1 for o, _d in w._slot_rows if o) == 2)
    real = ui_box.confirm
    ui_box.confirm = lambda *a, **kw: True
    try:
        o = next(o for o, _d in w._slot_rows if o)
        w.recall(o)
        TBL.wait(root, lambda: sum(1 for x, _d in w._slot_rows if x) == 1, 5)
    finally:
        ui_box.confirm = real
    chk("불러들이기 → 칸이 빈다", sum(1 for x, _d in w._slot_rows if x) == 1)
    w.close()


def X_place_types(pid):
    from common import expedition as X
    return (X.place(pid) or {}).get("types") or ()


def widget_colors(root):
    from poketdesktop.skins.dp import widgets as W
    top = tk.Toplevel(root)
    lb = tk.Label(top, text="기본", bg=U.BG, fg=U.FG, font=U.FONT_B)
    look("기본 코드의 위젯: 밝은 바탕 · 진한 글자 · 갈무리", lb.cget("bg") == W.BG_MAP[U.BG] and lb.cget("fg") == W.FG_MAP[U.FG]
        and "Galmuri11" in str(lb.cget("font")), (lb.cget("bg"), lb.cget("fg"), lb.cget("font")))
    lb.configure(bg=U.BG4)
    look("configure 로 바꿔도 옮긴다 (마우스를 올렸을 때 칠하는 것)", lb.cget("bg") == W.BG_MAP[U.BG4], lb.cget("bg"))
    red = tk.Label(top, bg=U.RED, fg="#14141a")
    chk("빨간 바탕 · 어두운 글자는 그대로", red.cget("bg") == U.RED and red.cget("fg") == "#14141a",
        (red.cget("bg"), red.cget("fg")))
    from poketdesktop.skins.dp import kit
    box = kit.entry(top, tk.StringVar())
    look("DP 화면이 만든 위젯은 제 빛깔", box.cget("bg") == "#ffffff" and box.entry.cget("fg") == kit.INK,
        (box.cget("bg"), box.entry.cget("fg")))
    b = U.ghost_button(top, "단추", lambda: None)
    chk("단추는 DP 단추", ours(type(b).__module__, "widgets"), type(b).__module__)
    seg = U.Segmented(top, [("a", "가"), ("b", "나")], "a", None)
    from poketdesktop.skins.dp import CUR
    look("고르기 단추는 DP (고른 칸은 흰 바탕 · 빨간 글씨)", seg.cells["a"].cget("bg") == "#ffffff"
        and seg.cells["a"].cget("fg") == CUR, (seg.cells["a"].cget("bg"), seg.cells["a"].cget("fg")))
    cv = tk.Canvas(top, bg=U.BG)
    i = cv.create_rectangle(0, 0, 5, 5, fill=U.BG)
    look("캔버스 도형은 그대로 (캔버스 바탕만 옮긴다)", cv.itemcget(i, "fill") == U.BG and cv.cget("bg") == W.BG_MAP[U.BG],
        (cv.itemcget(i, "fill"), cv.cget("bg")))
    t = tk.Text(top)
    t.tag_configure("me", foreground=U.ACCENT)
    look("글 칸의 태그 빛깔도 옮긴다 (길드 채팅)", t.tag_cget("me", "foreground") == W.FG_MAP[U.ACCENT],
        t.tag_cget("me", "foreground"))
    top.destroy()


def click_item(cv, tag):
    """캔버스의 그 꼬리표 도형 가운데를 누른다 (마우스를 옮겨 '지금 도형' 을 잡고 누른다)."""
    x1, y1, x2, y2 = cv.bbox(tag)
    x = int((x1 + x2) / 2 - cv.canvasx(0))
    y = int((y1 + y2) / 2 - cv.canvasy(0))
    cv.event_generate("<Motion>", x=x, y=y)
    cv.event_generate("<Button-1>", x=x, y=y)
    cv.event_generate("<ButtonRelease-1>", x=x, y=y)


def cv_texts(cv):
    return [cv.itemcget(i, "text") for i in cv.find_all() if cv.type(i) == "text"]


def guild(root):
    import test_guild_ui as TG
    from poketdesktop import ui_guild
    srv = TG.FakeServer()
    A, B, C = TG.Api(srv, 1), TG.Api(srv, 2), TG.Api(srv, 3)
    A.guild_create("포켓탐험대", "매일 미션 같이 해요!", "open")
    B.guild_join(A.guild()["guild"]["id"])
    srv.say("안녕하세요!", uid=2)
    app = TG.FakeApp(root, A)
    w = ui_guild.GuildWindow(app)
    if U.TEXT_SIZE:
        # 앱에서는 허브 탭 안이라 글자를 키우면 창도 같이 커진다 (ui_hub.sizes) - 따로 띄운 창도 그만큼
        w.win.winfo_toplevel().geometry("%dx%d" % (U.wide(ui_guild.W), U.wide(ui_guild.H)))
    chk("길드는 DP", ours(type(w).__module__, "guild"), type(w).__module__)
    TBL.wait(root, lambda: w.data is not None and w.mode == "guild", 10)
    TBL.settle(root, 0.6)
    chk("머리: 길드 이름 · 코인", w.h_name.text == "포켓탐험대" and w.h_coin.text.startswith("길드 코인"),
        (w.h_name.text, w.h_coin.text))
    # 왼쪽 기둥: 깃발 판 + 방 단추
    rooms = [k for k, _lb in w.tabs()]
    chk("기둥에 방 단추가 칸마다", all(w.side_cv.find_withtag("room_" + k) for k in rooms), rooms)
    chk("깃발 판: 길드 이름 · 길드원 수 · 소개", {"포켓탐험대", "길드원 2 / 15명", "매일 미션 같이 해요!"}
        <= set(cv_texts(w.side_cv)), cv_texts(w.side_cv))
    click_item(w.side_cv, "room_members")
    TBL.settle(root, 0.4)
    chk("기둥의 방을 누르면 그 칸으로", w.tab == "members" and w.seg.current == "members", (w.tab, w.seg.current))
    w.unread = 3
    w._paint_unread()
    chk("안 읽은 채팅 수가 채팅 단추에", w.seg.cells["chat"].text == "채팅 3", w.seg.cells["chat"].text)
    w.unread = 0
    app.guild_unseen = True
    w._paint_unread()
    chk("세어 둔 수가 없으면 빨간 점", w.seg.has_badge("chat") and w.seg.cells["chat"].text == "채팅")
    app.guild_unseen = False
    w._paint_unread()
    # 길드원: 트레이너 카드
    cv = w.dpage.cv
    names = cv_texts(cv)
    btns = [b.text for b in cv.dp_btns]
    chk("길드원 판에 두 사람", "가람" in names and "나래" in names, names)
    chk("관리 단추는 남의 판에만 (나는 마스터)", btns.count("관리") == 1 and btns.count("프로필") == 2, btns)
    for _ in range(3):
        cv.event_generate("<Configure>", width=cv.winfo_width() - 1, height=cv.winfo_height())
        w.dpage.redraw()
    chk("다시 그려도 단추가 쌓이지 않는다", len(cv.dp_btns) == 3, len(cv.dp_btns))
    # 미션
    w.show_tab("mission")
    TBL.settle(root, 0.4)
    t = cv_texts(w.dpage.cv)
    chk("미션: 오늘의 점수 · 단계 다섯 · 내 미션", "오늘의 길드 점수" in t and "5단계" in t and "내 미션" in t
        and "길드에 출석하기" in t, t[:12])
    # 코인 상점: 코인 12개
    srv.coin[1] = 12
    w.shop = None
    w.show_tab("shop")
    TBL.wait(root, lambda: w.shop is not None and w.shop_btns, 5)
    TBL.settle(root, 0.3)
    sb = w.shop_btns
    chk("코인 12개: 살 수 있는 단추만 켜진다", sb[("POKEBALL", 1)].enabled and sb[("POKEBALL", 10)].enabled
        and sb[("ULTRABALL", 1)].enabled and not sb[("ULTRABALL", 10)].enabled and not sb[("RARECANDY", 1)].enabled,
        dict((k, b.enabled) for k, b in sb.items()))
    sb[("POKEBALL", 1)].invoke()
    TBL.wait(root, lambda: srv.coin[1] == 11 and w.shop is not None and w.shop.get("coin") == 11, 5)
    TBL.settle(root, 0.3)
    chk("사면 코인이 줄고 머리의 숫자도", w.h_coin.text == "길드 코인 11개", w.h_coin.text)
    w.shop_q.set("사탕")
    TBL.settle(root, 0.2)
    shown = [it["id"] for it in w.shop_shown()]
    chk("도구 찾기: 적는 대로 걸러진다", shown == ["RARECANDY"] and "이상한사탕" in cv_texts(w.dpage.cv)
        and "몬스터볼" not in cv_texts(w.dpage.cv), shown)
    chk("찾는 동안 입력칸은 그대로 (목록만 다시)", w.shop_box.winfo_exists() and w.shop_q.get() == "사탕")
    # 다른 길드
    w.show_tab("guilds")
    TBL.wait(root, lambda: w.found is not None, 5)
    TBL.settle(root, 0.3)
    chk("다른 길드: 내 길드 꼬리표", "내 길드" in cv_texts(w.dpage.cv), cv_texts(w.dpage.cv))
    # 관리: 가입 방식을 누르면 서버로
    w.show_tab("manage")
    TBL.settle(root, 0.4)
    w.dpage.cv.yview_moveto(0)
    w.v_intro.set("새 소개")
    TBL.settle(root, 0.1)
    w.dpage.redraw()
    chk("다시 그려도 쓰던 소개는 남는다", w.v_intro.get() == "새 소개" and w.intro_box.winfo_exists())
    click_item(w.dpage.cv, "mode_approve")
    TBL.wait(root, lambda: srv.g["mode"] == "approve", 5)
    chk("가입 방식 칸을 누르면 바뀐다", srv.g["mode"] == "approve", srv.g["mode"])
    TBL.wait(root, lambda: w.dpage is not None and "approve" == ((w.data or {}).get("guild") or {}).get("joinMode"), 5)
    TBL.settle(root, 0.4)
    labels = [b.text for b in w.dpage.cv.dp_btns]
    chk("마스터(둘 이상): 나가기 단추 없이 해산만", "길드 해산" in labels and "길드 나가기" not in labels, labels)
    # 채팅
    w.show_tab("chat")
    TBL.wait(root, lambda: w.chat_var is not None, 5)
    chk("채팅: 이름은 글씨만 - 이름판 없음",
        w.chat_box.tag_cget("name", "background") == "" and w.chat_box.tag_cget("mine", "background") == "",
        (w.chat_box.tag_cget("name", "background"), w.chat_box.tag_cget("mine", "background")))
    look("채팅: 남의 이름은 파랑", w.chat_box.tag_cget("name", "foreground") == "#2a56b8",
         w.chat_box.tag_cget("name", "foreground"))
    w.chat_var.set("반가워요")
    w.send_chat()
    TBL.wait(root, lambda: any(m.get("body") == "반가워요" for m in srv.chat), 5)
    chk("채팅을 보내면 서버로", any(m.get("body") == "반가워요" for m in srv.chat), [m.get("body") for m in srv.chat])
    w.close()
    # 길드가 없을 때
    app3 = TG.FakeApp(root, C)
    w3 = ui_guild.GuildWindow(app3)
    TBL.wait(root, lambda: w3.mode == "none" and w3.found is not None, 10)
    TBL.settle(root, 0.6)
    chk("길드 없음: 길드 만들기 단추", w3.b_create is not None and w3.b_create.enabled)
    labels = [b.text for b in w3.dpage.cv.dp_btns]
    chk("길드 찾기: 가입 신청 단추 (방금 승인 필요로 바꿨다)", labels == ["가입 신청"] and "포켓탐험대" in cv_texts(w3.dpage.cv),
        (labels, cv_texts(w3.dpage.cv)))
    lo, hi = w3.dpage.cv.yview()
    chk("목록이 짧으면 굴릴 게 없다 (위 판의 높이가 바뀐 뒤에도)", hi - lo >= 0.999, (lo, hi))
    w3.close()


def guild_war(root):
    import test_guild_ui as TG
    import test_guild_war_ui as TW
    from poketdesktop import ui_guild, ui_guild_war
    from poketdesktop.skins.dp import war_map
    opened = []
    real = ui_guild_war.WarTab._open_battle
    ui_guild_war.WarTab._open_battle = lambda self, data: opened.append(data)    # 관장 배틀 창 대신 적어 둔다
    srv = TG.FakeServer()
    srv.war = TW.War()
    srv.war.phase = "war"
    srv.war.entered = True
    srv.g = {"name": "피카단", "intro": "같이 이겨요", "mode": "open", "master": 1, "points": 0}
    srv.roles = {1: "master", 2: "member", 3: "member"}
    app = TW.App(root, TW.Api(srv, 1))
    w = ui_guild.GuildWindow(app)
    w.win.winfo_toplevel().geometry("1000x680")
    TBL.wait(root, lambda: w.data is not None and w.mode == "guild", 10)
    TBL.settle(root, 0.4)
    side = w.side_cv
    bottom = max(side.bbox("room_" + k)[3] for k in w.seg.order)
    chk("방이 일곱(길드전 포함)이어도 기둥 안에 다 든다", len(w.seg.order) == 7 and bottom <= side.winfo_height(),
        (len(w.seg.order), bottom, side.winfo_height()))
    war = TW.open_war(root, w)
    TBL.wait(root, lambda: war.wide and war.map.items, 5)
    TBL.settle(root, 0.4)
    chk("길드전 칸 · 지도는 DP", ours(type(war).__module__, "guild_war")
        and ours(type(war.map).__module__, "war_map"), (type(war).__module__, type(war.map).__module__))
    cv = war.map.cv
    look("지도: 무늬 없는 바다 바탕 (v2)", cv.cget("bg") == war_map.SEA and len(cv.find_withtag("bg")) <= 1,
        (cv.cget("bg"), len(cv.find_withtag("bg"))))
    w_ = cv.winfo_width()
    out = [cv.itemcget(i, "text") for i in cv.find_withtag("label") if cv.type(i) == "text"
           and (cv.bbox(i)[0] < 0 or cv.bbox(i)[2] > w_)]
    chk("길드 이름이 지도 밖으로 안 나간다", not out, out[:3])
    cards = [c for c in war.inner.winfo_children() if isinstance(c, tk.Frame)]
    from poketdesktop.skins.dp.guild import GLINE
    look("오른쪽은 가는 테의 흰 판 한 겹 (v2)", cards and all(
        c.cget("bg") == "#ffffff" and c.cget("highlightbackground") == GLINE and int(c.cget("highlightthickness")) == 1
        for c in cards), [(c.cget("bg"), c.cget("highlightbackground"), c.cget("highlightthickness")) for c in cards][:3])
    foe = srv.war.hit()[0]                   # 우리 칸과 맞닿은 남의 칸
    TW.pick(root, war, foe)
    TBL.wait(root, lambda: "attack" in war.buttons, 5)
    b = war.buttons.get("attack")
    chk("맞닿은 남의 칸을 고르면 공격 단추 (DP 단추, 켜짐)", b is not None and b.enabled
        and ours(type(b).__module__, "widgets"), type(b).__module__ if b else None)
    if b is not None and b.enabled:
        b.command()                      # (기본 단추처럼 command 를 부른다 - 단추 모양만 DP)
    TBL.wait(root, lambda: opened, 5)
    chk("공격 단추를 누르면 승부를 연다", len(opened) == 1, opened)
    w.close()
    ui_guild_war.WarTab._open_battle = real


def dialogs(root):
    from poketdesktop import ui_box
    host = tk.Toplevel(root)
    host.geometry("400x300+40+40")

    def newest():
        found = []

        def walk(w):
            for c in w.winfo_children():
                if isinstance(c, tk.Toplevel):
                    found.append(c)
                walk(c)
        walk(host)
        return found[-1] if found else None

    def later(fn, ms=250):
        def go():
            w = newest()
            try:
                fn(w)
            except Exception as e:                       # noqa: BLE001 (실패해도 창은 닫아 모달을 푼다)
                print("   (작은 창 검사 중 예외: %r)" % (e,))
                if w is not None:
                    w.destroy()
        root.after(ms, go)

    seen = {}

    def look(w):
        seen["mod"] = type(w.choice).__module__
        seen["cur"] = w.choice.items[w.choice.cur][1]
        seen["title"] = [c for c in w.winfo_children() if isinstance(c, tk.Canvas)][0].find_all() != ()
        w.choice.pick()
    later(look)
    got = ui_box.confirm(host, "기권", "이 승부를 포기할까요?", danger=True, ok_text="기권")
    chk("묻는 창은 DP (예 / 아니오 상자 · 제목표)", ours(seen.get("mod", ""), "dialogs") and seen.get("title"),
        seen)
    chk("되돌릴 수 없는 일은 커서가 '취소' 에서 시작 - 그대로 Enter 면 아니오", seen.get("cur") == "취소" and got is False,
        (seen.get("cur"), got))

    def click_ok(w):
        cv = w.choice.cv
        x1, y1, x2, _y2 = w.choice.box
        y = y1 + U.h(8) + w.choice.row_h // 2
        cv.event_generate("<Motion>", x=int(x1 + 30), y=int(y))
        cv.event_generate("<Button-1>", x=int(x1 + 30), y=int(y))
    later(click_ok)
    got = ui_box.confirm(host, "길드 가입", "들어갈까요?", danger=False, ok_text="가입")
    chk("예 줄을 누르면 True", got is True, got)

    def down_pick(w):
        w.choice.move(1)
        w.choice.pick()
    later(down_pick)
    got = ui_box.ask_choice(host, "어느 박스로", "옮길까요?", [("1", "박스 1", "12 / 30"), ("2", "박스 2", None)])
    chk("고르는 창: 아래로 한 칸 → 둘째 열쇠", got == "2", got)
    later(lambda w: (w.choice.move(-1), w.choice.pick()))
    got = ui_box.ask_choice(host, "어느 박스로", "옮길까요?", [("1", "박스 1", None)])
    chk("  맨 아래 '그만두기' 는 None", got is None, got)

    def many(w):
        seen["h"] = w.winfo_height()
        for _ in range(20):
            w.choice.move(1)
        seen["key"] = w.choice.items[w.choice.cur][0]
        w.choice.pick()
    later(many)
    got = ui_box.ask_choice(host, "많다", "고르세요.", [(i, "포켓몬 %d" % i, "Lv.%d" % i) for i in range(30)])
    chk("  30줄이어도 창은 상한 안 · 고른 것을 돌려준다", 0 < seen.get("h", 0) <= U.h(520) + 4 and got == 20,
        (seen.get("h"), got))

    def typed(w):
        w.entry_box.entry.insert(0, "  잘 부탁해요 ")
        w.buttons[0].invoke()
    later(typed)
    got = ui_box.ask_text(host, "가입 신청", "가입 신청을 넣습니다.", "한마디")
    chk("글 묻는 창: 적은 글(앞뒤 빈칸 뺌)", got == "잘 부탁해요", got)
    later(lambda w: w.buttons[1].invoke())
    got = ui_box.ask_text(host, "가입 신청", "가입 신청을 넣습니다.")
    chk("  취소는 None", got is None, got)
    host.destroy()


def boss(root, dex):
    import test_boss_ui as TBo
    import test_gym_ui as TG
    from poketdesktop import ui_gym
    gyms = json.load(open(os.path.join(TG.DATA, "gyms.json"), encoding="utf-8"))
    kmap = json.load(open(os.path.join(TG.DATA, "korea_map.json"), encoding="utf-8"))
    party = [TG.mon(dex, "GARCHOMP", 100, ["EARTHQUAKE", "DRAGONCLAW"], "ROUGHSKIN", 12)]
    api = TBo.BossApi(dex, gyms, kmap, party)
    api.on, api.stage = True, 1
    app = TG.FakeApp(root, api, dex)
    app.settings = {}
    gw = ui_gym.GymWindow(root, app)
    gw.win.geometry("1040x700+20+20")
    TG.pump(root, lambda: gw.data is not None and gw.map is not None, 20)
    TBL.settle(root, 0.4)
    chk("관장 지도: 악당 단추가 뜬다", gw._boss_on and gw.boss_btn.box is not None, gw.boss_btn.box)
    gw.open_boss()
    bw = gw.boss_win
    TBL.wait(root, lambda: bw.card is not None and bw.rows, 5)
    TBL.settle(root, 0.3)
    chk("악당 창은 DP", ours(type(bw).__module__, "boss"), type(bw).__module__)
    states = [r["state"] for r in bw.rows]
    chk("간부 셋 (이김 · 도전 · 잠김) + 전설 '???'", states == ["won", "next", "locked", "locked"]
        and bw.rows[-1]["name"] == "???", (states, bw.rows[-1]["name"]))
    chk("승부 단추: 지금 상대 이름", bw.go_btn is not None and bw.go_btn.enabled and "주피터" in bw.go_btn.text,
        bw.go_btn.text if bw.go_btn else None)
    TBL.wait(root, lambda: bw.cv.find_withtag("pic0"), 5)
    chk("간부 도트가 도트 칸에 붙는다", bool(bw.cv.find_withtag("pic0")))
    chk("단추를 누르면 승부 (기본 창의 challenge)", bw.go_btn.command == bw.challenge, bw.go_btn.command)
    bw.close()
    gw.close()


def learn_dialogs(root, dex):
    from poketdesktop import ui_learn, ui_remember
    from poketdesktop.skins.dp import CUR
    host = tk.Toplevel(root)
    host.geometry("300x200+20+20")
    seen = {}

    def pick_ok(d, mv):
        def go():
            seen["cls"] = type(d).__module__
            seen["badges"] = sum(1 for f, parts, *_ in d.rows.values() for w in parts if isinstance(w, tk.Canvas))
            d._ok()                                  # 고르기 전에 결정 - 까닭을 적고 안 닫힌다
            seen["hint"] = d.hint.cget("text")
            d._pick(mv)
            f = d.rows[mv][0]
            seen["line"] = f.cget("highlightbackground")
            others = [r[0].cget("highlightbackground") for m, r in d.rows.items() if m != mv]
            seen["others"] = others
            d._ok()
        root.after(400, go)
    d = ui_learn.ForgetAsk(host, "피카츄", "THUNDERBOLT", ["QUICKATTACK", "THUNDERSHOCK", "TAILWHIP", "GROWL"], dex)
    pick_ok(d, "TAILWHIP")
    got = d.show()
    chk("배우기 창은 DP (기술 판마다 타입 표)", ours(seen.get("cls", ""), "learn") and seen.get("badges") == 5,
        (seen.get("cls"), seen.get("badges")))
    chk("고르기 전에 결정하면 까닭을 적는다", "고르세요" in seen.get("hint", ""), seen.get("hint"))
    chk("고른 판은 빨간 테, 나머지는 타입 빛깔 테", seen.get("line") == CUR and CUR not in seen.get("others", [CUR]),
        (seen.get("line"), seen.get("others")))
    chk("고른 기술을 잊는다", got == "TAILWHIP", got)
    d = ui_learn.ForgetAsk(host, "피카츄", "THUNDERBOLT", ["QUICKATTACK", "THUNDERSHOCK", "TAILWHIP", "GROWL"], dex)
    pick_ok(d, "THUNDERBOLT")
    chk("  새 기술을 고르면 안 배운다 ('')", d.show() == "", None)
    ents = [{"move": "THUNDER", "level": 0}, {"move": "SURF", "level": 0, "free": True}]
    d = ui_remember.RememberAsk(host, "피카츄", ents, 1000, 0, dex)
    seen.clear()

    def poor():
        seen["cls"] = type(d).__module__
        d._pick("THUNDER")
        d._ok()
        seen["hint"] = d.hint.cget("text")
        d._pick("SURF")
        d._ok()
    root.after(400, poor)
    got = d.show()
    chk("떠올리기 창도 DP 기술 판", ours(seen.get("cls", ""), "remember"), seen.get("cls"))
    chk("  돈이 모자라면 까닭을 적고, 무료는 떠올린다", "모자랍니다" in seen.get("hint", "") and got == "SURF",
        (seen.get("hint"), got))
    host.destroy()


def main():
    dex = P.Pokedex(json.load(open(os.path.join(ROOT, "server", "data", "pokedex.json"), encoding="utf-8")))
    raw = json.load(open(os.path.join(ROOT, "server", "data", "items.json"), encoding="utf-8"))["items"]
    items = [dict(i, buyable=True) for i in raw.values()]
    mons = [SB.mon(dex, n, 1000 + i, on=(i < 6)) for i, n in enumerate([6, 445, 149, 25, 94, 282])]
    mons += [SB.mon(dex, n, 2000 + i) for i, n in enumerate([1, 4, 7, 133, 143, 150, 151, 248])]
    for m in mons:
        m["level"] = 60

    PLAT.before_tk()
    skins.register_fonts()
    root = tk.Tk()
    root.withdraw()
    U.init_fonts(root)
    U.apply_theme(root)
    api = Api(mons, items)
    app = App(root, api, dex)

    # 고친 구역만 돌린다: python3 test_skin_dp.py 22 24 (번호를 안 주면 전부). 1~10 은 허브 하나로 이어져 있다.
    want = set(int(a) for a in sys.argv[1:] if a.isdigit())
    errors = []
    root.report_callback_exception = lambda e, v, tb: errors.append("%s: %s" % (e.__name__, v))
    hub = None
    if not want or want & set(range(1, 11)):
        print("1. 테마 클래스")
        chk("이번 실행의 테마는 %s" % os.environ["POKET_SKIN"], skins.active() == os.environ["POKET_SKIN"], skins.active())
        hub = ui_hub.make(app)
        app.hub = hub
        chk("허브는 DP 허브", ours(type(hub).__module__, "hub"), type(hub).__module__)
        # 글자 크기(2.0): 허브는 글자 배율만큼 커진다 (화면을 넘지 않게) - 가방 판이 옆으로 넘치지 않게 (사용자 결정)
        r = U.text_ratio()
        ww, wh = U.work_size(hub.win)
        sz = ui_hub.sizes(hub.win)
        chk("허브 크기 = 1040x700 · 가장 작게 980x620, 글자 배율만큼 (가장 작은 크기는 화면까지)",
            sz == (int(round(1040 * r)), int(round(700 * r)), min(ww, int(round(980 * r))), min(wh, int(round(620 * r)))),
            (sz, r))
        if U.TEXT_SIZE:
            hub.win.geometry("%dx%d+20+20" % (min(sz[0], ww), min(sz[1], wh)))      # 그 글자 크기의 기본 크기
        else:
            hub.win.geometry("1120x720+20+20")
        hub.show("bag")
        tabs = hub.panes.get("bag")
        chk("가방 탭은 DP 가방 탭", ours(type(tabs).__module__, "bag_tabs"), type(tabs).__module__)
        bag = tabs.bag
        chk("도구 칸은 DP 가방", ours(type(bag).__module__, "bag"), type(bag).__module__)
        TBL.wait(root, lambda: bool(bag.items) and bag._wait is None, 15)
        TBL.settle(root, 0.5)
        if U.TEXT_SIZE:
            real = tk.Canvas.winfo_width(bag.cv)
            chk("  글자를 키워도 가방 판이 옆으로 넘치지 않는다 (허브가 같이 커진다)",
                real >= getattr(bag.cv, "min_w", 0), (real, getattr(bag.cv, "min_w", 0)))

        print("2. 허브 메뉴")
        chk("지금 탭은 가방", hub.current == "bag", hub.current)
        hub.set_badge("board", True)
        chk("게시판 점이 찍힌다", "board" in hub.badges)
        hub.set_badge("board", False)
        chk("점이 지워진다", "board" not in hub.badges)
        hub.show("dex")
        chk("메뉴로 탭을 옮긴다 (도감)", hub.current == "dex" and "dex" in hub.panes, hub.current)
        # 탭 묶음 (2026-10-25): 위 탭은 묶음 여섯 개, 여럿 든 묶음만 하위 탭 줄
        TBL.settle(root, 0.2)
        chk("위 탭은 묶음 여섯 개 (도구 그림 + 이름)", list(hub._boxes) == [g[0] for g in ui_hub.GROUPS]
            and len(hub.bar.find_withtag("all")) > 0, list(hub._boxes))
        chk("  '포켓몬' 묶음만 보이고 그 안의 도감 칸만 붙는다", hub.gframes["pokemon"].winfo_ismapped()
            and not hub.gframes["bag"].winfo_manager() and hub.frames["dex"].winfo_ismapped()
            and not hub.frames["box"].winfo_manager(), hub.current)
        chk("  하위 탭 줄은 탭이 여럿인 묶음에만", sorted(hub.subs) == ["adventure", "community", "pokemon"]
            and [k for k, _b in hub._sub_boxes.get("pokemon", [])] == ["box", "dex"], sorted(hub.subs))
        hub.set_badge("guild", True)
        chk("  길드에 점을 켜면 '커뮤니티' 위 탭에도 점", "guild" in hub.badges
            and any(hub.bar.type(i) == "oval" for i in hub.bar.find_all()))
        hub.set_badge("guild", False)
        chk("  끄면 위 탭 점도 사라진다", not any(hub.bar.type(i) == "oval" for i in hub.bar.find_all()))
        x1, x2 = hub._boxes["pokemon"]
        hub._click(type("E", (), {"x": (x1 + x2) // 2})())
        chk("  위 탭을 누르면 그 묶음에서 마지막에 본 탭 (도감)", hub.current == "dex", hub.current)
        hub.show("bag")
        TBL.settle(root, 0.3)
        chk("  가방 묶음은 하위 탭 줄 없이 가방 칸만", hub.current == "bag" and hub.gframes["bag"].winfo_ismapped()
            and not hub.gframes["pokemon"].winfo_manager(), hub.current)
        chk("  묶음 탭 줄 높이는 46 을 넘지 않는다", hub.bar.winfo_height() <= U.h(46), hub.bar.winfo_height())

        hover_no_loop(root)

        print("3. 주머니 · 찾기")
        bag._pick_pocket("held")
        TBL.settle(root, 0.2)
        cats = set(v.get("cat") for k, v in bag._entries if k == "item")
        chk("지닌 도구 주머니는 지닌 도구만", cats == {"held"}, cats)
        bag.item_q.set("병뚜껑")
        TBL.settle(root, 0.2)
        found = [v["id"] for k, v in bag._entries if k == "item"]
        chk("찾는 말은 모든 주머니에서 찾는다", "BOTTLECAP" in found, found)
        bag.item_q.set("")
        TBL.settle(root, 0.2)

        print("4. 도구 고르기")
        bag._pick_pocket("iv")
        bag.pick_item("BOTTLECAP")
        TBL.settle(root, 0.3)
        chk("은색병뚜껑 - 능력을 골라야 한다", bag.stat_needed and bag._stat is not None)
        chk("쓰기 단추는 능력을 고르기 전엔 꺼져 있다", not bag.use_btn.enabled)
        bag.pick_stat("spe")
        chk("능력을 고르면 쓰기 단추가 켜진다", bag.use_btn.enabled and "은색병뚜껑" in bag.use_btn.text,
            bag.use_btn.text)
        bag._pick_pocket("ev")
        bag.pick_item("CARBOS")
        TBL.settle(root, 0.3)
        chk("노력치 도구 - 노력치 칸", bag._ev is not None and any(on for _k, _l, _v, on in bag._ev[0]))

        print("5. 포켓몬 판 · 쓰기")
        target = bag._view[2]["id"]
        bag.pick_mon(target)
        TBL.settle(root, 0.2)
        chk("판을 고른다", bag.mon_id == target, bag.mon_id)
        chk("보이는 판이 있다", len(bag.shown_mons()) >= 2, bag.shown_mons())
        bag.use_btn.invoke()
        TBL.wait(root, lambda: bool(api.used), 5)
        chk("쓰기 - 그 도구 · 그 포켓몬으로 간다", api.used and api.used[-1][:2] == ("CARBOS", target), api.used)
        TBL.settle(root, 0.5)

        print("6. 기술머신 주머니")
        bag._pick_pocket("tms")
        TBL.settle(root, 0.5)
        chk("기술머신 칸으로 넘어간다", tabs.current == "tms" and tabs.tms is not None, tabs.current)
        tm = tabs.tms
        chk("기술머신 칸은 DP", ours(type(tm).__module__, "tms"), type(tm).__module__)
        TBL.wait(root, lambda: bool(tm.tms) and tm._wait is None, 10)
        TBL.settle(root, 0.3)
        have = [t for t in tm.tms if t.get("have")]
        chk("가진 것만 보인다", len(tm._tm_rows) == len(have) and have, (len(tm._tm_rows), len(have)))
        tm._toggle_filter()
        chk("전부 보기", len(tm._tm_rows) == len(tm.tms), len(tm._tm_rows))
        tm._toggle_filter()
        if U.TEXT_SIZE and tm._tab_boxes.get("type"):
            # 글자를 키워 판이 굴러가 있어도 타입 드롭다운은 탭 바로 아래에 뜬다 (굴린 만큼 어긋나 떴다)
            spots = []
            real_popup = U.PopupMenu
            U.PopupMenu = lambda _root, _rows, x, y, **_kw: spots.append((x, y))
            try:
                tm.cv.yview_moveto(0.0)
                tm.cv.xview_moveto(0.0)
                root.update()
                tm._menu(tm.type_btn, [])
                tm.cv.yview_moveto(1.0)
                tm.cv.xview_moveto(1.0)
                root.update()
                dx, dy = int(tm.cv.canvasx(0)), int(tm.cv.canvasy(0))
                tm._menu(tm.type_btn, [])
            finally:
                U.PopupMenu = real_popup
                tm.cv.yview_moveto(0.0)
                tm.cv.xview_moveto(0.0)
                root.update()
            chk("  판을 굴린 만큼 드롭다운도 따라 옮겨 뜬다 (굴린 양 %d, %d)" % (dx, dy),
                len(spots) == 2 and spots[1] == (spots[0][0] - dx, spots[0][1] - dy), spots)
        no = have[0]["no"]
        tm.pick(no)
        TBL.wait(root, lambda: tm._learners is not None, 5)
        TBL.settle(root, 0.3)
        chk("고른 기술머신의 배울 포켓몬이 판으로", len(tm._plate_rows_src) == 3, tm._plate_rows_src)
        tm._plate_click(tm._plate_rows_src[1])
        chk("이미 배운 포켓몬은 안 골라진다", tm.mon_id is None, tm.mon_id)
        tm._plate_click(tm._plate_rows_src[0])
        chk("판을 고른다", tm.mon_id == 1000, tm.mon_id)
        tm.use_btn.invoke()
        TBL.wait(root, lambda: any(c[0] == "use" for c in api.tm.calls if isinstance(c, tuple)), 5)
        chk("가르치기 - 그 기술머신 · 그 포켓몬으로 간다",
            ("use", no, 1000, "") in api.tm.calls, [c for c in api.tm.calls if isinstance(c, tuple)])
        TBL.settle(root, 0.5)
        tm._pocket_click("held")
        TBL.settle(root, 0.3)
        chk("다른 주머니를 누르면 도구 칸의 그 주머니로", tabs.current == "items" and bag.pocket == "held",
            (tabs.current, bag.pocket))

        print("7. 포켓몬 (PC 박스)")
        hub.show("box")
        bx = hub.panes.get("box")
        chk("박스는 DP", ours(type(bx).__module__, "box"), type(bx).__module__)
        TBL.wait(root, lambda: bool(bx.mons) and bx._wait is None, 10)
        TBL.settle(root, 0.5)
        chk("파티 여섯 · 박스 여덟", len(bx._party_list) == 6 and len(bx._page_mons) == 8,
            (len(bx._party_list), len(bx._page_mons)))
        pid = bx._page_mons[3]["id"]
        bx.select(pid)
        TBL.settle(root, 0.3)
        chk("칸을 고르면 요약이 그 포켓몬", bx.sel == pid and bx._d and bx._d["m"]["id"] == pid)
        chk("요약에 기술 넷", len(bx._d["moves"]) <= 4)
        bx._page(1)
        TBL.settle(root, 0.2)
        chk("다음 박스는 비어 있다", bx.box_no == 1 and not bx._page_mons, (bx.box_no, len(bx._page_mons)))
        bx._page(-1)
        bx.f_query.set(bx._page_mons[0]["info"]["name"])
        TBL.settle(root, 0.3)
        chk("찾기 - 이름이 맞는 것만", len(bx._page_mons) == 1, len(bx._page_mons))
        bx.f_query.set("")
        TBL.settle(root, 0.3)
        bx.enter_multi()
        for m in bx._page_mons[:2]:
            bx.toggle_check(m["id"])
        chk("여러 마리 고르기 - 둘", len(bx.checked) == 2 and "2마리" in bx.btn_multi_move.text,
            (bx.checked, bx.btn_multi_move.text))
        ids = sorted(bx.checked)
        bx._do_move_many(ids, 3)
        TBL.wait(root, lambda: any(c[0] == "boxes" for c in api.calls if isinstance(c, tuple)), 5)
        chk("고른 것을 박스 4로", ("boxes", ids, 3) in api.calls, [c for c in api.calls if isinstance(c, tuple)][-3:])
        TBL.settle(root, 0.5)
        bx.exit_multi()
        TBL.wait(root, lambda: bx._wait is None, 5)
        TBL.settle(root, 0.3)
        src, dst = bx._page_mons[0]["id"], bx._party_list[0]["id"]
        bx._apply_drop(src, dst)
        TBL.wait(root, lambda: ("order",) in [c[:1] for c in api.calls if isinstance(c, tuple)], 5)
        chk("박스 것을 파티 자리로 끌면 맞바꾼다",
            ("desktop", dst, False) in api.calls and ("desktop", src, True) in api.calls,
            [c for c in api.calls if isinstance(c, tuple)][-4:])
        TBL.settle(root, 0.5)
        bx.select(bx._page_mons[0]["id"])
        n = len(api.calls)
        bx.btn_party.invoke()
        TBL.wait(root, lambda: len(api.calls) > n, 5)
        chk("데리고 다니기 단추", any(c[0] == "desktop" for c in api.calls[n:] if isinstance(c, tuple)), api.calls[n:])
        TBL.settle(root, 0.5)

        print("8. 상점")
        hub.show("shop")
        sh = hub.panes.get("shop")
        chk("상점은 DP", ours(type(sh).__module__, "shop"), type(sh).__module__)
        TBL.wait(root, lambda: bool(sh.items) and sh._wait is None, 10)
        TBL.settle(root, 0.3)
        sh.set_cat("ball")
        TBL.settle(root, 0.2)
        chk("분류 - 몬스터볼만", sh._shown and all(it.get("cat") == "ball" for it in sh._shown), len(sh._shown))
        sh.q.set("몬스터볼")
        TBL.settle(root, 0.2)
        chk("찾기", any(it["id"] == "POKEBALL" for it in sh._shown), [it["id"] for it in sh._shown][:5])
        sh.select("POKEBALL")
        sh.add_qty(1)
        sh.btn_q[1].invoke()
        chk("개수 - 빠른 개수 10", sh.qty == 10, sh.qty)
        sh.btn_buy.invoke()
        TBL.wait(root, lambda: any(c[0] == "buy" for c in api.calls if isinstance(c, tuple)), 5)
        chk("사기 - 그 도구 · 그 개수로", ("buy", "POKEBALL", 10) in api.calls, [c for c in api.calls if isinstance(c, tuple)][-2:])
        TBL.settle(root, 0.3)

        print("9. 도감")
        hub.show("dex")
        dx = hub.panes.get("dex")
        chk("도감은 DP", ours(type(dx).__module__, "dex"), type(dx).__module__)
        TBL.wait(root, lambda: dx.total and not dx.busy, 10)
        TBL.settle(root, 0.3)
        dx.set_gen(1)
        chk("1세대만", dx.rows and all(sp.get("gen") == 1 for sp in dx.rows), len(dx.rows))
        dx.set_mode("caught")
        chk("잡은 것만", dx.rows and all(sp["num"] in dx.caught for sp in dx.rows), len(dx.rows))
        dx.set_mode("all")
        dx.set_gen(0)
        dx.qv.set("리자몽")
        TBL.settle(root, 0.2)
        chk("찾기", [sp["num"] for sp in dx.rows] == [6], [sp["num"] for sp in dx.rows][:5])
        chk("찾은 것을 고른다", dx._sel == 6, dx._sel)
        dx.qv.set("")
        dx.pick(25)
        chk("줄을 누르면 그 종", dx._sel == 25)
        dx.toggle_achievements()
        TBL.settle(root, 0.3)
        chk("업적 칸을 열면 몸이 빠진다", not dx.cv.winfo_manager() and dx.ach_btn.text == "도감으로", dx.ach_btn.text)
        dx.toggle_achievements()
        chk("다시 누르면 도감으로", bool(dx.cv.winfo_manager()))

        print("10. 마이페이지 · 설정")
        from poketdesktop import config
        app.settings = dict(config.DEFAULTS)
        hub.show("my")
        my = hub.panes.get("my")
        chk("마이페이지는 DP", ours(type(my).__module__, "mypage"), type(my).__module__)
        TBL.wait(root, lambda: my.data is not None, 10)
        TBL.settle(root, 0.3)
        chk("처음 쪽은 알림", my.b_what == "notify" and my.b_items, my.b_what)
        my.pick_tab("posts")
        TBL.wait(root, lambda: my.b_what == "posts" and my.b_pages > 1, 5)
        my.turn(1)
        TBL.wait(root, lambda: my.b_page == 2, 5)
        chk("내 글 2쪽", my.b_what == "posts" and my.b_page == 2, (my.b_what, my.b_page))
        my.show_settings()
        TBL.settle(root, 0.3)
        st = my.settings
        chk("설정은 DP", ours(type(st).__module__, "settings"), type(st).__module__)
        row = next(r for r in st.rows if r["label"] == "걷는 속도")
        before = app.settings["walkSpeed"]
        st._step(row, 1)
        chk("▶ 로 걷는 속도가 오른다", abs(app.settings["walkSpeed"] - (before + 0.1)) < 1e-6,
            (before, app.settings["walkSpeed"]))
        chk("설정 파일에도 적힌다", abs(config.load_settings()["walkSpeed"] - app.settings["walkSpeed"]) < 1e-6)
        row = next(r for r in st.rows if r["label"] == "이름표 보이기")
        st._step(row, 1)
        chk("이름표 켜기/끄기", app.settings["showNames"] is True, app.settings["showNames"])
        my.show_page()
        chk("마이페이지로 돌아온다", my.view == "page")

    sections = (
        (11, "관장 배틀", lambda: gym_battle(root, dex, errors)),
        (12, "실시간 배틀", lambda: live_battle(root, dex)),
        (13, "레이드 배틀", lambda: raid_battle(root, dex)),
        (14, "관장 (타운맵)", lambda: gym_map(root, dex)),
        (15, "랭킹", lambda: rank_board(root)),
        (16, "친구", lambda: friends_pad(root)),
        (17, "게시판", lambda: board(root)),
        (18, "탐험", lambda: expedition(root, dex)),
        (19, "위젯 빛깔", lambda: widget_colors(root)),
        (20, "길드", lambda: guild(root)),
        (21, "길드전", lambda: guild_war(root)),
        (22, "작은 창 (묻는 창 · 고르는 창 · 글 묻는 창)", lambda: dialogs(root)),
        (23, "악당 출현", lambda: boss(root, dex)),
        (24, "기술 배우기 · 떠올리기", lambda: learn_dialogs(root, dex)),
    )
    for n, title, run in sections:
        if not want or n in want:
            print("%d. %s" % (n, title))
            run()
    chk("그리는 중에 난 예외가 없다", not errors, errors[:3])

    if hub is not None:
        hub.close()
    root.destroy()
    print("\n합계  OK %d   FAIL %d" % (OK, FAIL))
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
