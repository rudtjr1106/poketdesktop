# -*- coding: utf-8 -*-
"""챔피언리그 (독도) 화면 검사.

    python client/test_champion_ui.py
    python client/run_as_windows.py client/test_champion_ui.py

**창을 진짜로 띄운다.** 관장 화면 검사의 가짜 api 에 리그 길만 얹었다 - 응답 모양은 server/app/champion.py 와 같다.

## 무엇을 못 박나

  1. 관장 전국 지도에 독도가 있다 (실제 자리 - 울릉도 동남쪽, 지도 칸 안). 참가자면 금빛, 아니면 땅 빛깔. 누르면 독도 창.
     시·도 지도에는 없다.
  2. 독도 창: 열리기 전 / 자격이 없는 사람 / 참가자 - 위쪽 한 줄과 [상대 찾기] (못 하면 까닭과 함께 흐림).
     접속 중인 참가자 [도전] · 진행 중인 판 [관전] · 순위(내 줄 강조, 몇전 몇승 몇패) · 최근 판(전적 제외 표시).
     창은 화면 안이고, 순위가 길면 안에서 굴린다. 가로로 눌린 글이 없다.
  3. [상대 찾기]: 기다리면 남은 시간이 제자리에서 줄고, 짝이 나면 배틀 창을 띄운다. 모습이 같으면 다시 그리지 않는다.
  4. [도전]: 기다리던 사람이면 바로 배틀 창, 아니면 상대가 받을 때까지 실시간 초대처럼 기다린다.
  5. 알림: 누가 기다리면 오른쪽 아래에 '챔피언리그 · 독도' 알림 [도전]. 설정을 끄거나 독도 창을 보고 있거나
     배틀 중이면 안 띄운다. ask · match 는 앱이 /api/live 를 묻게 한다. 놀러 가기 소켓이 넘겨준다.
  6. 관전 (길드전처럼, 참가자만): 다른 참가자들의 판이 열리면 알림 [관전]. 누르면 바탕화면에서 보고, 서버에
     '본다' 를 알리고(그만 보면 '그만'), 밀려온 턴을 장면에 넘긴다. 끝난 판(404)이면 닫는다. 내 판을 보는 사람
     수가 밀려오면 배틀 창의 '관전 N명' 을 고친다. 참가자가 아니면 [관전] 단추가 없다.
"""
import json
import os
import sys
import tempfile
import time
import types

os.environ.setdefault("POKET_HOME", os.path.join(tempfile.gettempdir(), "poket-test-champion"))

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
sys.path.insert(0, ROOT)

import tkinter as tk                                        # noqa: E402

import test_gym_ui as TG                                    # noqa: E402
from common import pokelogic as P                           # noqa: E402
from poketdesktop import platform_os as PLAT                # noqa: E402
from poketdesktop import ui_champion as UC                  # noqa: E402
from poketdesktop import ui_common as U                     # noqa: E402
from poketdesktop import ui_gym                             # noqa: E402
from poketdesktop import ui_spectate                        # noqa: E402
from poketdesktop import visit as VISIT                     # noqa: E402
from test_learn_dialog import squeezed                      # noqa: E402

OK = FAIL = 0
DATA = os.path.join(ROOT, "server", "data")
ME = 7


def chk(name, cond, got=""):
    global OK, FAIL
    if cond:
        OK += 1
        print("  OK   %s" % name)
    else:
        FAIL += 1
        print("  FAIL %s   %r" % (name, got))


class ApiError(Exception):
    def __init__(self, message, status=409):
        Exception.__init__(self, message)
        self.message = message
        self.status = status


def ranking(n):
    names = ["가람", "나래", "다솜", "라온", "마루", "바다", "사랑", "아라", "자람", "차미", "카이", "타라", "파랑", "하늘"]
    out = []
    for i in range(n):
        uid = ME if i == 2 else 100 + i
        name = "나여조경석이름긴사람" if i == 1 else (names[i % len(names)] + ("" if i < len(names) else str(i)))
        w = max(0, 20 - i)
        out.append({"id": uid, "name": name, "played": w + i, "wins": w, "losses": i, "draws": 1 if i == 4 else 0,
                    "rank": i + 1})
    return out


def member_state(**kw):
    st = {"open": True, "startsAt": "2026-11-16T00:00:00+09:00", "opens": "11월 16일 0시", "total": 256,
          "cleared": 256, "member": True, "members": 14, "why": None, "seeking": False, "waitLeft": 0,
          "waitSec": 600, "waiting": [{"id": 101, "name": "나래"}],
          "online": [{"id": 101, "name": "나래", "waiting": True, "busy": False},
                     {"id": 103, "name": "라온", "waiting": False, "busy": True},
                     {"id": 104, "name": "마루", "waiting": False, "busy": False}],
          "fights": [{"id": 55, "turn": 3, "a": {"id": 103, "name": "라온"}, "b": {"id": 105, "name": "바다"},
                      "watchers": 2}],
          "ranking": ranking(14), "pairMax": 3,
          "recent": [{"id": 9, "foeId": 101, "foeName": "나래", "outcome": "win", "reason": "forfeit", "turns": 4,
                      "at": "2026-11-16T12:00:00+00:00", "counted": False},
                     {"id": 8, "foeId": 104, "foeName": "마루", "outcome": "lose", "reason": "ko", "turns": 21,
                      "at": "2026-11-16T11:00:00+00:00", "counted": True}]}
    st["me"] = dict(next(r for r in st["ranking"] if r["id"] == ME))
    st.update(kw)
    return st


class LeagueApi(TG.FakeApi):
    def __init__(self, *a):
        TG.FakeApi.__init__(self, *a)
        self.member = True
        self.st = member_state()
        self.seek_result = None          # 다음 seek 에 돌려줄 판 (None 이면 기다린다)
        self.challenge_result = None
        self.fight_result = None
        self.got = []

    def gym(self):
        out = TG.FakeApi.gym(self)
        out["champion"] = {"member": self.member, "open": True, "opens": "11월 16일 0시"}
        return out

    def champion(self):
        self.got.append("state")
        return json.loads(json.dumps(self.st))

    def champion_seek(self, on=True):
        self.got.append(("seek", on))
        if not on:
            self.st.update(seeking=False, waitLeft=0)
            out = self.champion()
            out["match"] = None
            return out
        m = self.seek_result
        self.st.update(seeking=m is None, waitLeft=0 if m else 600)
        out = self.champion()
        out["match"] = m
        return out

    def champion_challenge(self, uid):
        self.got.append(("challenge", uid))
        if isinstance(self.challenge_result, Exception):
            raise self.challenge_result
        return {"match": self.challenge_result}

    def champion_watch(self, mid, on=True):
        self.got.append(("watch", mid, on))
        return {"id": mid, "n": 1 if on else 0}

    def champion_fight(self, mid):
        self.got.append(("fight", mid))
        if isinstance(self.fight_result, Exception):
            raise self.fight_result
        return self.fight_result


class LeagueApp(TG.FakeApp):
    def __init__(self, root, api, dex):
        TG.FakeApp.__init__(self, root, api, dex)
        self.user_id = ME
        self.live_battle = None
        self.friendly = None
        self.visit = None
        self.opened = []
        self.watched = []
        self.checked = 0
        self.live_pending = None
        self.notes = []
        self.league = UC.League(self)

    def notify(self, text, *_a):
        self.notes.append(text)

    def open_league(self, parent=None):
        return self.league.open_window(parent)

    def on_champion(self, ev):
        return self.league.on_event(ev)

    def open_live_battle(self, m):
        self.opened.append(m)

    def check_live(self):
        self.checked += 1

    def live_watch(self, ms=3000):
        self.watched.append(ms)


def label_texts(w):
    out = []
    for c in w.winfo_children():
        try:
            if c.winfo_class() == "Label":
                out.append(c.cget("text"))
        except tk.TclError:
            pass
        out.extend(label_texts(c))
    return out


def find_buttons(w, text):
    """PushButton 의 라벨 (글이 text 인 것)."""
    return [c for c in w.winfo_children() if c.winfo_class() == "Label" and c.cget("text") == text] + \
        [b for c in w.winfo_children() for b in find_buttons(c, text)]


def press(label):
    """PushButton 의 라벨을 누른다 (누르고 떼기)."""
    label.event_generate("<ButtonPress-1>")
    label.event_generate("<ButtonRelease-1>")


def cramped(w):
    """크기를 다 못 받은 위젯 (굴러가는 칸 안까지 본다 - 가로만. 세로는 굴려서 본다)."""
    out = []
    for c in w.winfo_children():
        try:
            if c.winfo_ismapped() and c.winfo_width() > 1 and c.winfo_width() + 1 < c.winfo_reqwidth():
                out.append((c.winfo_class(), c.cget("text") if c.winfo_class() == "Label" else "",
                            c.winfo_width(), c.winfo_reqwidth()))
        except tk.TclError:
            pass
        out.extend(cramped(c))
    return out


def main():
    with open(os.path.join(DATA, "pokedex.json"), encoding="utf-8") as f:
        dex = P.Pokedex(json.load(f))
    with open(os.path.join(DATA, "gyms.json"), encoding="utf-8") as f:
        gyms = json.load(f)
    with open(os.path.join(DATA, "korea_map.json"), encoding="utf-8") as f:
        kmap = json.load(f)

    PLAT.before_tk()
    root = tk.Tk()
    root.withdraw()
    U.init_fonts(root)
    U.apply_theme(root)
    errors = []

    def on_err(exc, val, tb):
        import traceback
        errors.append("".join(traceback.format_exception(exc, val, tb))[-600:])
    root.report_callback_exception = on_err
    print("글꼴 %s / 본문 %dpt (BASE_PT=%d)" % (U.FAMILY, U.FONT[1], U.BASE_PT))

    api = LeagueApi(dex, gyms, kmap, [])
    app = LeagueApp(root, api, dex)

    print("=== 관장 지도의 독도 ===")
    gw = ui_gym.GymWindow(root, app)
    gw.win.geometry("1100x720")
    TG.pump(root, lambda: gw.data is not None and gw.map is not None)
    root.update()
    gw.redraw()
    root.update()
    items = gw.cv.find_withtag("dokdo")
    chk("전국 지도에 독도가 있다", len(items) >= 4, items)
    texts = [gw.cv.itemcget(i, "text") for i in items if gw.cv.type(i) == "text"]
    chk("  '독도' · '챔피언리그' 글", texts == ["독도", "챔피언리그"], texts)
    bb = gw.cv.bbox("dokdo")
    chk("  지도 칸 안에 들어간다", bb and bb[0] >= 0 and bb[2] <= gw.cv.winfo_width() and bb[3] <= gw.cv.winfo_height(),
        (bb, gw.cv.winfo_width(), gw.cv.winfo_height()))
    tf = gw.nation_fit()
    dx, dy = tf(ui_gym.DOKDO_AT)
    ul = [tf(p) for p in gw._sgg["47940"]["rings"][0]]           # 울릉도
    land = [i for i in items if gw.cv.type(i) == "polygon"]
    chk("  섬 둘 (서도 · 동도)", len(land) == 2, land)
    chk("  참가자면 금빛", all(gw.cv.itemcget(i, "fill").lower() == ui_gym.CLEAR.lower() for i in land),
        [gw.cv.itemcget(i, "fill") for i in land])
    lb = gw.cv.bbox(*land)
    chk("  섬은 실제 자리 (동경 131.865 · 북위 37.242)", abs((lb[0] + lb[2]) / 2.0 - dx) <= U.h(2) + 1
        and lb[1] < dy < lb[3] + U.h(6), (lb, dx, dy))
    chk("  울릉도보다 동쪽 · 남쪽", dx > max(p[0] for p in ul) and dy > max(p[1] for p in ul), (dx, dy))
    chk("  참가자에게 상태줄 안내", "독도를 누르면 챔피언리그" in gw.status.cget("text"), gw.status.cget("text"))
    api.member = False
    gw.reload()
    TG.pump(root, lambda: not gw.champion.get("member") and not gw._loading)
    root.update()
    land = [i for i in gw.cv.find_withtag("dokdo") if gw.cv.type(i) == "polygon"]
    chk("  아직 자격이 없으면 땅 빛깔", land and all(gw.cv.itemcget(i, "fill").lower() != ui_gym.CLEAR.lower()
                                               for i in land), [gw.cv.itemcget(i, "fill") for i in land])
    gw.enter_sido("47")
    root.update()
    chk("시·도 지도에는 독도가 없다", not gw.cv.find_withtag("dokdo"))
    gw.to_nation()
    root.update()

    print("=== 독도를 누르면 창 ===")
    api.st = member_state(open=False, why="챔피언리그는 11월 16일 0시에 열립니다.", online=[], fights=[],
                          waiting=[], recent=[])
    gw._click_dokdo()
    lw = app.league.win
    TG.pump(root, lambda: lw is not None and lw.st is not None)
    root.update()
    chk("독도 창이 뜬다", lw is not None and lw.alive)
    t = label_texts(lw.body)
    chk("  열리기 전: 열리는 때", "11월 16일 0시에 열립니다." in t, t[:6])
    chk("  [상대 찾기] 는 흐리다", lw.seek_btn is not None and not lw.seek_btn.enabled)
    chk("  까닭이 옆에 적힌다", lw.seek_note.cget("text") == "챔피언리그는 11월 16일 0시에 열립니다.")
    lw.close()

    api.st = member_state(member=False, cleared=231, me=None, recent=[], why="관장 256곳을 전부 이겨야 챔피언리그에 나갈 수 "
                          "있습니다 (지금 231곳).")
    app.open_league()
    lw = app.league.win
    TG.pump(root, lambda: lw.st is not None)
    root.update()
    t = label_texts(lw.body)
    chk("자격이 없으면: 관장 몇 곳", "관장 231 / 256 · 전부 이기면 참가할 수 있습니다." in t, t[:6])
    dj = find_buttons(lw.body, "도전")
    chk("  [도전] 도 흐리다", dj and all(b.cget("cursor") == "" for b in dj), [b.cget("cursor") for b in dj])
    chk("  순위는 본다", any("20전 20승 0패" == x for x in t), [x for x in t if "전" in x][:3])
    chk("  관전은 참가자만 - [관전] 단추가 없다", not find_buttons(lw.body, "관전") and "라온  vs  바다 · 3턴" in t)
    lw.close()

    print("=== 관장 창을 닫은 뒤에도 독도가 다시 열린다 (2.5.0, 게시판 #542) ===")
    # 독도 창은 관장 창의 자식이다. 관장 창을 닫으면 같이 사라지는데, 예전에는 alive 가 남아서 그 뒤로 독도를
    # 누르면 없는 창을 앞으로 꺼내려다 조용히 끝났다 (앱을 다시 켤 때까지 '독도에 안 들어가져요').
    gym = tk.Toplevel(root)
    gym.geometry("300x200+40+40")
    root.update()
    app.open_league(gym)
    old = app.league.win
    TG.pump(root, lambda: old.st is not None)
    gym.destroy()                                   # 관장 창을 닫았다 - 독도 창도 같이 사라진다
    root.update()
    chk("부모와 같이 사라지면 스스로 정리한다 (alive · League.win)", not old.alive and app.league.win is None,
        (old.alive, app.league.win))
    app.open_league()
    new = app.league.win
    TG.pump(root, lambda: new is not None and new.st is not None)
    root.update()
    chk("  다시 누르면 새 창이 뜬다", new is not None and new is not old and new.alive and new.exists()
        and new.top.winfo_viewable(), (new, new and new.exists()))
    stale = new
    stale.top.unbind("<Destroy>")                   # 예전 코드처럼 정리 없이 사라진 경우 (alive 만 남았다)
    stale.top.destroy()
    root.update()
    app.open_league()
    again = app.league.win
    TG.pump(root, lambda: again.st is not None)
    chk("  정리가 안 된 채 사라졌어도 open_window 가 알아채고 새로 띄운다", again is not stale and again.exists()
        and not stale.alive, (again is stale, stale.alive))
    again.close()

    print("=== 참가자 ===")
    api.st = member_state()
    app.open_league()
    lw = app.league.win
    TG.pump(root, lambda: lw.st is not None)
    root.update()
    root.update_idletasks()
    t = label_texts(lw.body)
    chk("내 전적 · 등수", "내 전적  20전 18승 2패 · 3위" in t, [x for x in t if "내 전적" in x])
    chk("[상대 찾기] 를 누를 수 있다", lw.seek_btn.enabled)
    chk("접속 중인 참가자 3명", "접속 중인 참가자 3명" in t or any("접속 중인 참가자 3명" in x for x in t), t[:12])
    chk("  기다리는 사람 · 배틀 중 표시", "기다리는 중" in t and "배틀 중" in t)
    dojeon = find_buttons(lw.body, "도전")
    chk("  [도전] 셋", len(dojeon) == 3, len(dojeon))
    chk("진행 중인 판 [관전]", "라온  vs  바다 · 3턴" in t and len(find_buttons(lw.body, "관전")) == 1)
    chk("  관전 N명", "관전 2명" in t, [x for x in t if "관전" in x])
    chk("순위: 몇전 몇승 몇패 (무가 있으면 무)", "20전 16승 4패 1무" in t, [x for x in t if "무" in x])
    chk("  긴 닉네임도 나온다", "나여조경석이름긴사람" in t)
    chk("최근 판: 전적 제외 표시", any("전적 제외" in x and x.startswith("승 · 나래 · 기권") for x in t),
        [x for x in t if x.startswith("승") or x.startswith("패")])
    chk("  KO 는 까닭을 안 붙인다", "패 · 마루" in t, [x for x in t if x.startswith("패")])
    lw._fit()
    root.update()
    work = U.work_size(lw.top)
    chk("창은 화면 안", lw.top.winfo_height() <= work[1] + 2, (lw.top.winfo_height(), work))
    chk("창 머리 · 바닥에 눌린 것이 없다", not squeezed(lw.top), squeezed(lw.top)[:3])
    chk("가로로 눌린 글이 없다", not cramped(lw.body), cramped(lw.body)[:4])
    lo, hi = lw._scroll[0].yview()
    chk("순위가 길면 안에서 굴린다", hi - lo < 0.999 or lw.top.winfo_height() >= lw.body.winfo_reqheight(), (lo, hi))

    print("=== 모습이 같으면 다시 안 그린다 ===")
    first = lw.seek_btn
    lw.apply(json.loads(json.dumps(api.st)))
    chk("같은 모습이면 단추가 그대로", lw.seek_btn is first)
    st2 = json.loads(json.dumps(api.st))
    st2["online"].pop()
    lw.apply(st2)
    chk("바뀌면 다시 그린다", lw.seek_btn is not first)
    lw.apply(json.loads(json.dumps(api.st)))
    root.update()

    print("=== 상대 찾기 ===")
    api.seek_result = None
    lw.toggle_seek()
    TG.pump(root, lambda: (lw.st or {}).get("seeking"))
    root.update()
    chk("기다린다: 단추가 '그만 찾기'", lw.seek_btn.label.cget("text") == "그만 찾기")
    note0 = lw.seek_note.cget("text")
    chk("  남은 시간이 보인다", note0.startswith("상대를 찾는 중 · 10:00") or note0.startswith("상대를 찾는 중 · 9:5"),
        note0)
    lw._wait_until = time.monotonic() + 65
    lw._tick()
    chk("  제자리에서 센다", lw.seek_note.cget("text") == "상대를 찾는 중 · 1:05 남음", lw.seek_note.cget("text"))
    lw.toggle_seek()
    TG.pump(root, lambda: not (lw.st or {}).get("seeking"))
    root.update()
    chk("그만 찾으면 원래대로", lw.seek_btn.label.cget("text") == "상대 찾기" and lw._wait_until is None)
    match = {"id": 77, "state": "fighting", "kind": "champion", "foeName": "나래"}
    api.seek_result = match
    lw.toggle_seek()
    TG.pump(root, lambda: app.opened)
    chk("짝이 나면 배틀 창", app.opened and app.opened[-1]["id"] == 77, app.opened)
    api.seek_result = None

    print("=== 도전 ===")
    api.challenge_result = {"id": 78, "state": "invited", "kind": "champion", "foeName": "마루", "mine": True}
    press(find_buttons(lw.body, "도전")[-1])
    TG.pump(root, lambda: app.watched)
    chk("초대를 걸면 받을 때까지 자주 묻는다", app.watched and app.live_pending and app.live_pending["id"] == 78,
        (app.watched, app.live_pending))
    chk("  누구에게 걸었는지 알린다", any("마루 님에게 도전했습니다" in n for n in app.notes), app.notes)
    chk("  서버에 마루 번호로", ("challenge", 104) in api.got, api.got[-3:])
    api.challenge_result = {"id": 79, "state": "fighting", "kind": "champion", "foeName": "나래"}
    n0 = len(app.opened)
    app.league.challenge(101, "나래")
    TG.pump(root, lambda: len(app.opened) > n0)
    chk("기다리던 사람이면 바로 배틀 창", app.opened[-1]["id"] == 79)
    api.challenge_result = ApiError("상대가 다른 배틀을 하고 있습니다.")
    app.league.challenge(103, "라온")
    TG.pump(root, lambda: "다른 배틀" in lw.status.cget("text"))
    chk("막히면 창 아래에 까닭", "다른 배틀" in lw.status.cget("text"), lw.status.cget("text"))
    lw.close()
    root.update()

    print("=== 알림 ===")
    lg = app.league
    lg.on_event({"t": "champion", "s": "wait", "id": 101, "name": "나래"})
    root.update()
    chk("누가 기다리면 오른쪽 아래 알림", lg.card is not None and lg.card.alive)
    chk("  제목 '챔피언리그 · 독도'", lg.card.title.cget("text") == UC.TITLE)
    chk("  글 · [도전]", lg.card.note_text == "나래 님이 독도에서 상대를 기다립니다." and
        lg.card.note_btn.label.cget("text") == "도전", lg.card.note_text)
    api.challenge_result = {"id": 80, "state": "fighting", "kind": "champion", "foeName": "나래"}
    lg.card.note_btn.command()
    TG.pump(root, lambda: app.opened[-1]["id"] == 80)
    chk("  [도전] 을 누르면 알림이 닫히고 바로 붙는다", lg.card is None and app.opened[-1]["id"] == 80)
    lg.on_event({"t": "champion", "s": "wait", "id": ME, "name": "나"})
    chk("내가 기다리는 것은 안 알린다", lg.card is None)
    app.settings["championNotify"] = False
    lg.on_event({"t": "champion", "s": "wait", "id": 101, "name": "나래"})
    chk("설정을 끄면 안 알린다", lg.card is None)
    app.settings["championNotify"] = True
    app.live_battle = object()
    lg.on_event({"t": "champion", "s": "wait", "id": 101, "name": "나래"})
    chk("배틀 중이면 안 알린다", lg.card is None)
    app.live_battle = None
    app.open_league()
    TG.pump(root, lambda: lg.win.st is not None)
    lg.on_event({"t": "champion", "s": "wait", "id": 101, "name": "나래"})
    chk("독도 창을 보고 있으면 안 알린다 (창이 다시 묻는다)", lg.card is None)
    lg.win.close()
    c0 = app.checked
    lg.on_event({"t": "champion", "s": "ask", "id": 81, "name": "가람"})
    lg.on_event({"t": "champion", "s": "match", "id": 81})
    chk("도전이 왔다 · 판이 열렸다 -> 앱이 /api/live 를 묻는다", app.checked == c0 + 2, app.checked)
    fake_visit = types.SimpleNamespace(app=app, active=False)
    c0 = app.checked
    VISIT.Visit.on_event(fake_visit, {"t": "champion", "s": "match", "id": 82})
    chk("놀러 가기 소켓이 리그 알림을 넘긴다 (놀러 가 있지 않아도)", app.checked == c0 + 1, app.checked)

    print("=== 구경 ===")
    made = []

    class Duel(object):
        def __init__(self, ctl, fight):
            self.ctl, self.mid, self.alive, self.fed = ctl, fight.get("id"), True, []
            made.append(self)

        def feed(self, f, replay=True):
            self.fed.append(f)

        def close(self):
            self.alive = False
    orig = ui_spectate.DesktopDuel
    ui_spectate.DesktopDuel = Duel
    try:
        fight = {"id": 55, "turn": 3, "step": 5, "a": {"name": "라온"}, "b": {"name": "바다"}, "events": [],
                 "over": False}
        api.fight_result = fight
        app.settings["championNotify"] = True
        lg.on_event({"t": "champion", "s": "fight", "id": 55, "a": "라온", "b": "바다"})
        root.update()
        chk("다른 참가자들의 판이 열리면 알림", lg.card is not None
            and lg.card.note_text == "라온  vs  바다 · 챔피언리그 배틀이 시작됐습니다."
            and lg.card.note_btn.label.cget("text") == "관전", lg.card and lg.card.note_text)
        lg.card.note_btn.command()
        TG.pump(root, lambda: made)
        chk("[관전] 하면 바탕화면 구경이 뜬다", made and made[0].mid == 55 and lg.watching())
        TG.pump(root, lambda: ("watch", 55, True) in api.got)
        chk("  서버에 '본다' 를 알린다 (밀어 주고 '관전 N명' 이 간다)", ("watch", 55, True) in api.got, api.got[-3:])
        lg.on_event({"t": "champion", "s": "turn", "fight": dict(fight, turn=7)})
        chk("  밀려온 턴을 장면에 넘긴다", made[0].fed and made[0].fed[-1]["turn"] == 7)
        chk("  밀려온 때를 적는다 (끊기면 스스로 묻는다)", time.monotonic() - lg.pushed < 2)
        lg.on_event({"t": "champion", "s": "turn", "fight": dict(fight, id=99, turn=9)})
        chk("  다른 판의 턴은 안 넘긴다", made[0].fed[-1]["turn"] == 7)
        api.fight_result = dict(fight, turn=4)
        lg.refresh()
        TG.pump(root, lambda: made[0].fed and made[0].fed[-1]["turn"] == 4 and not lg._asking)
        chk("  스스로 다시 묻고 넘겨준다", made[0].fed and made[0].fed[-1]["turn"] == 4)
        api.fight_result = ApiError("그런 챔피언리그 판이 없습니다.", 404)
        lg.refresh()
        TG.pump(root, lambda: not lg.watching())
        chk("  판이 사라지면 닫는다", not lg.watching() and not made[0].alive)
        TG.pump(root, lambda: ("watch", 55, False) in api.got)
        chk("  그만 보면 서버에 '그만'", ("watch", 55, False) in api.got, api.got[-3:])
        app.visit = types.SimpleNamespace(guest=True)
        n = len(made)
        lg.watch(55)
        root.update()
        chk("놀러 가 있으면 구경하지 않는다", len(made) == n and any("놀러 가" in x for x in app.notes))
        app.visit = None
    finally:
        ui_spectate.DesktopDuel = orig

    print("=== 내 판의 관전 N명 ===")
    shown = []
    app.live_battle = types.SimpleNamespace(alive=True, set_watchers=lambda mid, n: shown.append((mid, n)))
    lg.on_event({"t": "champion", "s": "watchers", "id": 81, "n": 3})
    chk("내 배틀 창의 '관전 N명' 을 고친다", shown == [(81, 3)], shown)
    app.live_battle = None

    lg.close()
    gw.close()
    root.update()
    chk("화면 오류 없음", not errors, errors[:2])
    print("\n%d OK, %d FAIL" % (OK, FAIL))
    try:
        root.destroy()
    except tk.TclError:
        pass
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
