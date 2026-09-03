# -*- coding: utf-8 -*-
"""1.0.13 에서 들어온 것들 — 풀숲 끄기, 알림, 패치노트.

    python client/test_new_settings.py

창을 안 만든다. tk 가 필요한 자리(창 띄우기, 타이머)만 가짜로 바꿔 끼우고
판단하는 코드는 진짜를 그대로 돌린다.

## 왜 이 검사가 있나

세 가지 다 **안 해야 할 때 안 하는 것**이 요점이다. 그런 건 손으로
확인하기가 제일 어렵다 - 풀숲을 껐는데 서버를 계속 두드리는지, 같은
친구 요청으로 알림이 두 번 뜨는지, 처음 켠 사람에게 변경 내역이 뜨는지는
한참 켜 두고 지켜봐야 알 수 있다.

    풀숲 끄기   화면에서 걷어내는 것으로 끝이 아니다. **서버에 묻는
                것도 멈춰야** 한다. 안 쓸 답을 받으려고 90초마다 남의
                서버를 두드릴 이유가 없다. 다만 배틀 중에 걷어내면
                상대 도트만 사라지고 배틀은 계속 돈다.

    알림        게임 안에서 벌어지는 일은 절대 띄우지 않는다. 잡을
                때마다 화면 구석에서 튀어나오면 결국 프로그램을 끈다.
                띄우는 것은 화면에 자국이 안 남는 둘뿐이다.

    패치노트    처음 켠 사람에게는 안 띄운다. 그리고 한 번 본 판을
                켤 때마다 또 띄우면 안 된다.
"""
import os
import sys
import tempfile

TMP = os.path.join(tempfile.gettempdir(), "poket-test-newsettings")
os.environ.setdefault("POKET_HOME", TMP)

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.dirname(HERE))

from common import patchnotes                              # noqa: E402
from common.version import VERSION                         # noqa: E402
from poketdesktop import config, ui_update, wild_ui        # noqa: E402
from poketdesktop.app import App                           # noqa: E402

OK = FAIL = 0


def chk(name, cond, got=""):
    global OK, FAIL
    if cond:
        OK += 1
    else:
        FAIL += 1
        print("  FAIL %s   %s" % (name, got))


# ---------------------------------------------------------------- 가짜들
class FakeRoot(object):
    """after 로 걸린 일을 쌓아만 둔다. 부르고 싶을 때 fire() 로 돌린다."""

    def __init__(self):
        self.jobs = []
        self.n = 0

    def after(self, ms, fn=None, *a):
        self.n += 1
        if fn is not None:
            self.jobs.append((ms, fn, a))
        return self.n

    def after_cancel(self, job):
        pass

    def fire(self):
        jobs, self.jobs = self.jobs, []
        for _ms, fn, a in jobs:
            fn(*a)


class FakeApi(object):
    def __init__(self):
        self.wild_calls = 0

    def wild(self, force=False):
        self.wild_calls += 1
        return {"wild": None, "nextInSeconds": 60, "balls": 3}


class FakeTray(object):
    def __init__(self):
        self.toasts = []

    def toast(self, title, message):
        self.toasts.append((title, message))
        return True

    def refresh(self):
        pass


class FakeBattle(object):
    def __init__(self, closed=False):
        self.closed = closed


class FakeApp(object):
    """WildController 와 App 의 메서드 몇 개가 만지는 것만 갖춘 껍데기."""

    def __init__(self, **over):
        self.root = FakeRoot()
        self.api = FakeApi()
        self.settings = dict(config.DEFAULTS)
        self.battle = None
        self.tray = FakeTray()
        self.overlay = None
        self.wild = None
        self.said = []
        self.balls = 0
        self.friend_unseen = 0
        self._friend_seen = set()
        self._friend_first = True
        self.autostarted = False
        self.notes_shown = []
        self.__dict__.update(over)

    def notify(self, message):
        self.said.append(message)

    def refresh_tray(self):
        pass

    # App 의 실제 메서드를 빌려 쓴다 (가짜로 다시 쓰지 않는다)
    toast = App.toast
    announce_friends = App.announce_friends
    _tell_patchnotes_once = App._tell_patchnotes_once

    def show_patchnotes(self, greet=False):
        self.notes_shown.append(greet)


# ---------------------------------------------------------------- 풀숲
def test_grass():
    print("풀숲 띄우기")

    # 켜져 있으면 서버에 묻는다
    app = FakeApp()
    w = wild_ui.WildController(app)
    app.wild = w
    w.start()
    app.root.fire()
    chk("켜져 있으면 물어본다", app.api.wild_calls == 1,
        "calls=%d" % app.api.wild_calls)

    # 꺼 두면 start() 가 아무것도 안 한다
    app = FakeApp()
    app.settings["showGrass"] = False
    w = wild_ui.WildController(app)
    app.wild = w
    w.start()
    app.root.fire()
    chk("꺼 두면 물어보지 않는다", app.api.wild_calls == 0,
        "calls=%d" % app.api.wild_calls)
    chk("꺼 두면 다음 확인을 예약하지도 않는다", w._job is None,
        "_job=%r" % w._job)

    # 꺼 놓고 check() 를 직접 불러도(배틀 끝난 뒤 desktop_battle 이 부른다)
    # 서버를 두드리지 않는다. 여기서 예약을 다시 걸면 영원히 돈다.
    w.check()
    app.root.fire()
    chk("껐으면 check() 도 서버를 안 부른다", app.api.wild_calls == 0,
        "calls=%d" % app.api.wild_calls)
    chk("껐으면 check() 가 예약을 안 남긴다", w._job is None)

    # 직접 눌렀으면(force) 왜 아무 일도 없는지는 말해준다
    app.said = []
    w.check(force=True)
    chk("직접 눌렀으면 껐다고 알려준다",
        any("풀숲" in m for m in app.said), "said=%r" % app.said)

    # 끄면 이미 돋은 풀숲을 걷어낸다
    app = FakeApp()
    w = wild_ui.WildController(app)
    app.wild = w
    gone = []

    class FakeGrass(object):
        def destroy(self):
            gone.append(True)

    w.grass = FakeGrass()
    w.wild_id = 7
    app.settings["showGrass"] = False
    w.set_enabled(False)
    chk("끄면 풀숲을 걷어낸다", gone == [True] and w.grass is None,
        "gone=%r grass=%r" % (gone, w.grass))

    # **배틀 중에는 걷어내지 않는다.** 상대 도트만 사라지고 배틀은 계속 돈다.
    app = FakeApp()
    app.battle = FakeBattle(closed=False)
    w = wild_ui.WildController(app)
    app.wild = w
    kept = []

    class KeptPet(object):
        def destroy(self):
            kept.append("destroyed")

    w.pet = KeptPet()
    app.settings["showGrass"] = False
    w.set_enabled(False)
    chk("배틀 중이면 야생을 그대로 둔다", kept == [] and w.pet is not None,
        "kept=%r" % kept)

    # 배틀이 끝난 뒤 부르는 check() 에서 정리된다
    app.battle = FakeBattle(closed=True)
    w.check()
    chk("배틀이 끝난 뒤 정리된다", w.pet is None and kept == ["destroyed"],
        "kept=%r pet=%r" % (kept, w.pet))

    # 다시 켜면 묻기 시작한다
    app.settings["showGrass"] = True
    w.set_enabled(True)
    app.root.fire()
    chk("다시 켜면 물어본다", app.api.wild_calls == 1,
        "calls=%d" % app.api.wild_calls)

    # 물어본 뒤 답이 오는 사이에 껐으면, 화면은 건드리지 않는다
    app = FakeApp()
    w = wild_ui.WildController(app)
    app.wild = w
    app.settings["showGrass"] = False
    w.apply({"balls": 9, "wild": {"id": 1, "state": "grass"}})
    chk("답이 늦게 와도 풀숲을 안 만든다", w.grass is None, "grass=%r" % w.grass)
    chk("볼 개수는 그래도 챙긴다", app.balls == 9, "balls=%r" % app.balls)


# ---------------------------------------------------------------- 알림
def test_toast():
    print("알림")

    app = FakeApp()
    chk("새 버전은 띄운다", app.toast("새 버전", "받으세요", kind="update"))
    chk("친구 요청은 띄운다", app.toast("친구", "요청", kind="friend"))
    n = len(app.tray.toasts)

    # **게임 안에서 벌어지는 일은 여기로 오면 안 된다.** 나중에 누가
    # "잡았다" 알림을 여기로 보내려 할 때 그 자리에서 막혀야 한다.
    chk("모르는 종류는 안 띄운다",
        app.toast("잡았다!", "피카츄를 잡았다", kind="caught") is False)
    chk("모르는 종류는 트레이까지 안 간다", len(app.tray.toasts) == n,
        "toasts=%d" % len(app.tray.toasts))

    app.settings["notifyImportant"] = False
    chk("설정에서 끄면 안 띄운다",
        app.toast("새 버전", "받으세요", kind="update") is False)

    app = FakeApp(tray=None)
    chk("트레이가 없으면 조용히 넘어간다",
        app.toast("새 버전", "받으세요", kind="update") is False)

    # 알림을 못 띄우는 판(리눅스 일부)에서 터지지 않아야 한다
    class BadTray(object):
        def toast(self, title, message):
            raise RuntimeError("알림을 못 띄웁니다")

    app = FakeApp(tray=BadTray())
    chk("트레이가 실패해도 터지지 않는다",
        app.toast("새 버전", "받으세요", kind="update") is False)

    chk("띄우는 종류는 둘뿐이다",
        set(patchnotes.TOAST_KINDS) == {"update", "friend"},
        "kinds=%r" % (patchnotes.TOAST_KINDS,))


# ---------------------------------------------------------------- 친구 요청
def test_friends():
    print("친구 요청")

    app = FakeApp()
    # 켤 때 이미 두 건 쌓여 있었다. 한 사람씩 띄우면 화면이 덮인다.
    app.announce_friends({"incoming": [{"id": 1, "name": "가"},
                                       {"id": 2, "name": "나"}]})
    chk("처음에는 개수만 한 번", len(app.tray.toasts) == 1,
        "toasts=%r" % (app.tray.toasts,))
    chk("개수가 제목에 있다", "2" in app.tray.toasts[0][0],
        "title=%r" % app.tray.toasts[0][0])
    chk("트레이에 셀 수가 남는다", app.friend_unseen == 2,
        "unseen=%r" % app.friend_unseen)

    # 같은 응답이 다시 와도 또 띄우지 않는다
    app.announce_friends({"incoming": [{"id": 1, "name": "가"},
                                       {"id": 2, "name": "나"}]})
    chk("같은 요청은 다시 안 띄운다", len(app.tray.toasts) == 1,
        "toasts=%d" % len(app.tray.toasts))

    # 새로 온 것은 누가 보냈는지 알려준다
    app.announce_friends({"incoming": [{"id": 1, "name": "가"},
                                       {"id": 2, "name": "나"},
                                       {"id": 3, "name": "다람쥐"}]})
    chk("새 요청은 이름으로 알린다", len(app.tray.toasts) == 2
        and "다람쥐" in app.tray.toasts[1][0],
        "toasts=%r" % (app.tray.toasts,))
    chk("셀 수가 늘어난다", app.friend_unseen == 3,
        "unseen=%r" % app.friend_unseen)

    # 받아주면 줄어든다
    app.announce_friends({"incoming": []})
    chk("받아주면 셀 수가 줄어든다", app.friend_unseen == 0,
        "unseen=%r" % app.friend_unseen)

    # 못 받아왔으면(None) 아무것도 건드리지 않는다
    app.friend_unseen = 5
    app.announce_friends(None)
    chk("못 받아오면 그대로 둔다", app.friend_unseen == 5,
        "unseen=%r" % app.friend_unseen)

    # 여럿이 한꺼번에 새로 오면 묶어서 한 번
    app = FakeApp()
    app.announce_friends({"incoming": []})          # 첫 응답은 비어 있었다
    app.announce_friends({"incoming": [{"id": 4, "name": "라"},
                                       {"id": 5, "name": "마"}]})
    chk("여럿이 오면 한 번에 묶는다", len(app.tray.toasts) == 1,
        "toasts=%r" % (app.tray.toasts,))
    chk("몇 건인지 제목에 있다", "2" in app.tray.toasts[0][0],
        "title=%r" % app.tray.toasts[0][0])

    # id 가 없는 줄이 섞여 와도 터지지 않는다
    app.announce_friends({"incoming": [{"name": "이름만"}]})
    chk("id 없는 줄은 건너뛴다", app.friend_unseen == 0,
        "unseen=%r" % app.friend_unseen)


# ---------------------------------------------------------------- 패치노트
def test_patchnotes():
    print("패치노트")

    # **이번에 내는 버전의 패치노트를 안 적었으면 여기서 걸린다.**
    # 안 적으면 갈아탄 사람이 아무 안내도 못 받고, 릴리스 본문의
    # '바뀐 것' 도 비어서 나간다. 버전을 올리는 사람이 같이 적어야 한다.
    e = patchnotes.entry(VERSION)
    chk("이번 버전(%s) 패치노트를 적어 두었다" % VERSION, e is not None,
        "common/patchnotes.py 의 NOTES 에 %s 를 넣어야 한다" % VERSION)
    chk("항목이 하나 이상", e and len(e["items"]) > 0)
    chk("항목마다 (제목, 설명) 두 짝",
        e and all(len(x) == 2 for x in e["items"]))
    chk("최신이 맨 위", patchnotes.latest()["version"] == VERSION,
        "latest=%r VERSION=%r" % (patchnotes.latest()["version"], VERSION))
    chk("없는 버전은 None", patchnotes.entry("0.0.1") is None)
    md = patchnotes.as_markdown(VERSION)
    chk("릴리스 본문 꼴로도 나온다", bool(md) and "- **" in md)
    chk("없는 버전은 빈 글", patchnotes.as_markdown("0.0.1") == "")
    if e is None:
        # 아래 둘은 이번 버전 묶음이 있어야 뜻이 있는 검사다. 없는 것을
        # 두고 또 실패시키면 진짜 원인(위 한 줄)이 묻힌다.
        return

    # 처음 켠 사람에게는 안 띄운다
    app = FakeApp()
    app.settings["lastRunVersion"] = ""
    app._tell_patchnotes_once()
    app.root.fire()
    chk("처음 켠 사람에게는 안 띄운다", app.notes_shown == [],
        "shown=%r" % app.notes_shown)
    chk("그래도 버전은 적어 둔다",
        app.settings["lastRunVersion"] == patchnotes.latest()["version"]
        or app.settings["lastRunVersion"] != "",
        "last=%r" % app.settings["lastRunVersion"])

    # 갈아탄 사람에게는 띄운다
    app = FakeApp()
    app.settings["lastRunVersion"] = "1.0.11"
    app._tell_patchnotes_once()
    app.root.fire()
    chk("갈아탄 사람에게는 띄운다", app.notes_shown == [True],
        "shown=%r" % app.notes_shown)

    # 같은 버전을 다시 켜면 안 띄운다
    app.notes_shown = []
    app._tell_patchnotes_once()
    app.root.fire()
    chk("같은 버전은 다시 안 띄운다", app.notes_shown == [],
        "shown=%r" % app.notes_shown)

    # 부팅으로 켜졌으면 한참 미룬다 (켜자마자 창이 포커스를 뺏으면 안 된다)
    app = FakeApp(autostarted=True)
    app.settings["lastRunVersion"] = "1.0.11"
    app._tell_patchnotes_once()
    delays = [ms for ms, _fn, _a in app.root.jobs]
    chk("부팅으로 켜졌으면 늦게 띄운다", delays and delays[0] >= 10000,
        "delays=%r" % delays)


# ---------------------------------------------------------------- 릴리스 본문
def test_highlights():
    print("새 버전 창의 줄거리")

    entry = patchnotes.latest()
    body = ("## 받는 법\n\nzip 을 받아 푸세요.\n\n"
            "## 바뀐 것\n\n" + patchnotes.as_markdown(entry["version"]))
    got = ui_update.highlights(body)
    chk("항목을 다 뽑는다", len(got) == len(entry["items"]),
        "got=%d want=%d" % (len(got), len(entry["items"])))
    chk("받는 법은 섞지 않는다", not any("zip" in x for x in got),
        "got=%r" % got[:1])
    chk("마크다운 표시를 뗀다", not any("**" in x for x in got))

    # 한 항목이 여러 줄로 접혀 있어도 한 항목이다
    folded = ("## 바뀐 것\n\n- **첫째** 는 이런 것인데\n  줄이 접혀 있다.\n\n"
              "- **둘째** 도 있다.\n")
    got = ui_update.highlights(folded)
    chk("접힌 줄을 합친다", len(got) == 2, "got=%r" % got)
    chk("합친 내용이 이어진다", got and "접혀 있다" in got[0], "got0=%r" % got[0])

    chk("본문이 없어도 안 터진다", ui_update.highlights(None) == []
        and ui_update.highlights("") == [])
    chk("'바뀐 것' 대목이 없으면 빈 목록",
        ui_update.highlights("## 받는 법\n\n- 그냥 받으세요\n") == [])


# ---------------------------------------------------------------- 트레이 메뉴
def test_tray_menu():
    print("트레이 메뉴")
    from poketdesktop import tray as traymod

    app = FakeApp()
    app.username = "나"
    app.pvp_unseen = 2
    app.friend_unseen = 3
    app.balls = 5
    t = traymod.TrayBase(app)

    def walk(items, out):
        for it in items:
            if it is traymod.SEP:
                continue
            # **메뉴의 글자와 체크 표시는 함수로 적혀 있다.** 메뉴를 열
            # 때마다 다시 물어보기 때문이다. 여기서 한 번 다 불러 본다 -
            # 하나가 터지면 진짜 메뉴는 열리지도 않는다.
            text = traymod.val(it.text)
            traymod.val(it.checked)
            traymod.val(it.enabled)
            out.append(text)
            if it.submenu:
                walk(it.submenu, out)
        return out

    labels = walk(t.spec(), [])
    chk("메뉴가 터지지 않고 만들어진다", len(labels) > 8,
        "labels=%d" % len(labels))
    chk("친구 요청 줄에 개수가 붙는다",
        any("친구 요청" in x and "3" in x for x in labels),
        "labels=%r" % [x for x in labels if "친구" in x])
    chk("풀숲 줄이 있다", any("풀숲" in x for x in labels))
    chk("새로운 기능 줄이 있다", any("새로운 기능" in x for x in labels))

    # 요청이 없으면 숫자를 붙이지 않는다 (괄호 안에 0 이 뜨면 이상하다)
    app.friend_unseen = 0
    labels = walk(t.spec(), [])
    chk("요청이 없으면 숫자를 안 붙인다",
        any(x == "친구 요청 보기" for x in labels),
        "labels=%r" % [x for x in labels if "친구" in x])

    # 풀숲 체크 표시가 설정을 따라간다
    def grass_checked():
        for it in t.spec():
            if it is not traymod.SEP and it.submenu:
                for sub_it in it.submenu:
                    if sub_it is traymod.SEP:
                        continue
                    if "풀숲" in traymod.val(sub_it.text):
                        return traymod.val(sub_it.checked)
        return None

    app.settings["showGrass"] = True
    chk("켜져 있으면 체크", grass_checked() is True)
    app.settings["showGrass"] = False
    chk("껐으면 체크 해제", grass_checked() is False)

    # 로그인 전 메뉴도 만들어져야 한다 (부팅 직후 인터넷을 기다리는 중)
    app.api = None
    labels = walk(t.spec(), [])
    chk("로그인 전 메뉴도 만들어진다", any("종료" in x for x in labels),
        "labels=%r" % labels)

    # 기본 껍데기는 알림을 못 띄운다고 답해야 한다 (맥/윈도우가 각자 덮는다)
    chk("기본 toast 는 False", t.toast("제목", "내용") is False)


def main():
    os.makedirs(TMP, exist_ok=True)
    test_grass()
    test_toast()
    test_friends()
    test_patchnotes()
    test_highlights()
    test_tray_menu()
    print()
    print("통과 %d, 실패 %d" % (OK, FAIL))
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
