# -*- coding: utf-8 -*-
"""화면 테마 '디아루가·펄기아'(skins/dp) 검사 - 로그인 · 회원가입 · 비밀번호 다시 묻기.

    python client/test_skin_dp_login.py

**창을 진짜로 띄운다** (가짜 서버). DP 로그인 창은 짓는 고리만 바꾸고 동작은 기본 창(ui_login)의 것을
그대로 쓴다. 그래서 같은 동작 검사를 DP 로 한 번, 기본 테마로 한 번(따로 띄운 프로세스) 돌린다 -
테마는 켤 때 한 번 정해지므로 한 프로세스에서 둘을 다 볼 수 없다.

  1. DP 면 창 · 비밀번호 칸 · 카드가 DP 클래스로 뜬다. 기본은 ui_login 의 것 그대로.
  2. 로그인: 닉네임은 지난 세션에서 채워진다. 빈 닉네임 · 모자란 비밀번호는 서버에 안 묻고 글상자(상태 줄)에 알린다.
     틀린 비밀번호는 서버의 오류 글을 그대로 보이고 비밀번호 칸을 비운다. 맞으면 세션을 저장하고 창이 닫힌다.
     (DP) 화면 자판으로 친 숫자는 칸에 친 것과 같다 - 지움, 네 자리가 차면 로그인.
  3. 서버 칸: 누르면 펴지고, 주소를 바꾸면 그 주소로 묻고, 로그인하면 설정에 남는다.
  4. 회원가입: (DP) 탭을 눌러 넘어간다. 세대 1~9, 카드 셋, 첫 카드가 골라져 있고 단추 글이 그 포켓몬.
     닉네임 확인(못 쓰는 이름 · 쓰는 이름), 세대 바꾸기, 카드 누르기, 도트가 카드에 붙는다,
     모자란 비밀번호는 안 보내고, 다 채우면 서버에 그 이름 · 비밀번호 · 고른 포켓몬으로 간다.
  5. 비밀번호 다시 묻기(ask_password): 네 자리를 치면 그 숫자, 취소하면 None. (DP) 머리는 DP 띠, 창 폭은 기본과 같다.
  6. 그리는 중에 난 예외가 없다. (DP) 창이 작업 영역에 다 들어간다 (아래 글상자가 잘리지 않는다).
  (DP v2) 읽기를 막던 것이 없다: 아래 화면의 몬스터볼 무늬 · 글상자 오른쪽 줄무늬. 창 크기는 기본 창과 같다 (폭 460).
"""
import os
import subprocess
import sys
import tempfile
import time

os.environ["POKET_HOME"] = tempfile.mkdtemp(prefix="poket-test-skin-dp-login-")
SKIN = os.environ.get("POKET_LOGIN_SKIN", "dp")
os.environ["POKET_SKIN"] = SKIN

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.dirname(HERE))

import tkinter as tk                                        # noqa: E402

from PIL import Image                                       # noqa: E402

from poketdesktop import config                             # noqa: E402
from poketdesktop import platform_os as PLAT                # noqa: E402
from poketdesktop import skins                              # noqa: E402
from poketdesktop import sprite_cache                       # noqa: E402
from poketdesktop import ui_common as U                     # noqa: E402
from poketdesktop import ui_login                           # noqa: E402

OK = FAIL = 0
DP = SKIN == "dp"


def chk(name, cond, got=""):
    global OK, FAIL
    if cond:
        OK += 1
        print("  OK   %s" % name)
    else:
        FAIL += 1
        print("  FAIL %s   %r" % (name, got))


def wait(root, cond, sec=8.0):
    end = time.time() + sec
    while time.time() < end and not cond():
        root.update()
        time.sleep(0.005)
    return cond()


def settle(root, sec=0.25):
    end = time.time() + sec
    while time.time() < end:
        root.update()
        time.sleep(0.005)


# ---------------------------------------------------------------- 가짜 서버
STARTERS = [(1, ("BULBASAUR", "이상해씨", ["풀", "독"], ["GRASS", "POISON"]),
             ("CHARMANDER", "파이리", ["불꽃"], ["FIRE"]), ("SQUIRTLE", "꼬부기", ["물"], ["WATER"]))]
STARTERS += [(g, ("G%dA" % g, "풀%d" % g, ["풀"], ["GRASS"]), ("G%dB" % g, "불%d" % g, ["불꽃"], ["FIRE"]),
              ("G%dC" % g, "물%d" % g, ["물"], ["WATER"])) for g in range(2, 10)]
STARTERS[3] = (4, ("TURTWIG", "모부기", ["풀"], ["GRASS"]), ("CHIMCHAR", "불꽃숭이", ["불꽃"], ["FIRE"]),
               ("PIPLUP", "팽도리", ["물"], ["WATER"]))
CALLS = []


class FakeApi(object):
    def __init__(self, base):
        self.base = base

    def check_name(self, name):
        CALLS.append(("check", self.base, name))
        if name == "taken":
            return {"available": False, "reason": "이미 쓰고 있는 닉네임입니다."}
        return {"available": True, "reason": "쓸 수 있는 닉네임입니다."}

    def starters(self):
        out = []
        for row in STARTERS:
            out.append({"gen": row[0], "pokemon": [
                {"internal": k, "kr": kr, "num": 100 * row[0] + i, "gen": row[0], "types": t, "typeIds": ids}
                for i, (k, kr, t, ids) in enumerate(row[1:])]})
        return {"generations": out}

    def _user(self, name):
        return {"token": "tok-" + name, "user": {"username": name}, "expiresAt": None, "balls": 5}

    def login(self, name, pin):
        CALLS.append(("login", self.base, name, pin))
        if pin != "1234":
            raise Exception("비밀번호가 틀렸습니다.")
        return self._user(name)

    def register(self, name, pin, starter):
        CALLS.append(("register", self.base, name, pin, starter))
        return self._user(name)


GIF = os.path.join(os.environ["POKET_HOME"], "fake.gif")


def make_gif():
    frames = []
    for c in ((230, 80, 60, 255), (60, 120, 230, 255)):
        im = Image.new("RGBA", (24, 24), (0, 0, 0, 0))
        for x in range(6, 18):
            for y in range(4, 22):
                im.putpixel((x, y), c)
        frames.append(im)
    frames[0].save(GIF, save_all=True, append_images=frames[1:], duration=120, loop=0, disposal=2)


PINS = []
_pin_init = ui_login.PinEntry.__init__


def _record_pin(self, *a, **kw):
    _pin_init(self, *a, **kw)
    PINS.append(self)


class Ev(object):
    def __init__(self, keysym):
        self.keysym = keysym


def type_pin(pin, digits):
    """칸에 숫자를 친 것처럼 (칸에 넣고 KeyRelease 가 부르는 것을 부른다)."""
    for i, d in enumerate(digits):
        pin.entries[i].delete(0, "end")
        pin.entries[i].insert(0, d)
        pin._typed(Ev(d), i)


def status_text(lw):
    return lw.msg[0] if DP else lw.status._label.cget("text")


def status_color(lw):
    return lw.msg[1] if DP else lw.status._bar.cget("bg")


def btn_text(b):
    return b.text if hasattr(b, "text") else b.label.cget("text")


def hint_text(lw):
    return lw._fcv.itemcget(lw.name_hint, "text") if DP else lw.name_hint.cget("text")


def click_item(cv, tag):
    """캔버스의 그 꼬리표 도형 가운데를 누른다 (마우스를 옮겨 '지금 도형' 을 잡고 누른다)."""
    x1, y1, x2, y2 = cv.bbox(tag)
    x, y = int((x1 + x2) / 2), int((y1 + y2) / 2)
    cv.event_generate("<Motion>", x=x, y=y)
    cv.event_generate("<Button-1>", x=x, y=y)
    if cv.winfo_exists():                   # (누른 것이 칸을 새로 지으면 캔버스가 없어진다)
        cv.event_generate("<ButtonRelease-1>", x=x, y=y)


def cv_texts(cv):
    return [cv.itemcget(i, "text") for i in cv.find_all() if cv.type(i) == "text"]


# ---------------------------------------------------------------- 검사
def login_flow(root):
    print("1. 테마 클래스 · 2. 로그인")
    config.save_session({"token": "", "username": "지우"})
    settings = {"server": "https://poket.example.com"}
    lw = ui_login.LoginWindow(root, settings)
    settle(root, 0.4)
    mod = "poketdesktop.skins.dp.login" if DP else "poketdesktop.ui_login"
    chk("로그인 창 클래스 (%s)" % SKIN, type(lw).__module__ == mod, type(lw).__module__)
    chk("비밀번호 칸 클래스", type(lw.li_pin).__module__ == mod, type(lw.li_pin).__module__)
    if DP:
        req, real = lw.win.winfo_reqheight(), lw.win.winfo_height()
        chk("창이 작업 영역에 다 들어간다 (잘리지 않는다)", req <= real + 1, (req, real))
        chk("(v2) 창 폭은 기본 창과 같다 (460)", lw.win.winfo_width() == 460, lw.win.winfo_width())
        chk("(v2) 아래 화면에 몬스터볼 무늬가 없다", not [i for i in lw._fcv.find_all() if lw._fcv.type(i) == "oval"])
        chk("(v2) 글상자에 줄무늬가 없다 (도형은 테 하나)",
            len([i for i in lw.status.find_all() if lw.status.type(i) in ("rectangle", "polygon")]) == 1,
            [lw.status.type(i) for i in lw.status.find_all()])
    chk("닉네임은 지난 세션에서", lw.li_name.get() == "지우", lw.li_name.get())

    lw.li_name.set("")
    lw.do_login()
    chk("빈 닉네임은 안 묻고 알린다", status_text(lw) == "닉네임을 입력해 주세요." and not CALLS, status_text(lw))
    if DP:
        chk("글상자에 그 글이 그려진다", "닉네임을 입력해 주세요." in cv_texts(lw.status), cv_texts(lw.status))
        chk("오류 글은 빨간 뜻 색", status_color(lw) == U.DANGER, status_color(lw))
    lw.li_name.set("지우")
    type_pin(lw.li_pin, "12")
    lw._enter()
    chk("모자란 비밀번호는 안 묻고 알린다", status_text(lw) == "비밀번호 4자리를 입력해 주세요." and not CALLS,
        status_text(lw))

    print("3. 서버 칸")
    lw._toggle_server()
    settle(root, 0.1)
    shown = (lw.top.itemcget(lw._srv_win, "state") in ("", "normal")) if DP else lw.server_box.winfo_ismapped()
    chk("누르면 서버 칸이 펴진다", lw.server_open and shown, (lw.server_open, shown))
    if DP:
        chk("펴진 칸에 지금 주소", lw.server_box.entry.get() == "https://poket.example.com", lw.server_box.entry.get())
    lw.server.set("http://127.0.0.1:8123/")
    lw._toggle_server()
    settle(root, 0.1)
    shown = " ".join(cv_texts(lw.top)) if DP else lw.server_label.cget("text")
    chk("접으면 바꾼 주소의 호스트가 보인다", "127.0.0.1:8123" in shown and not lw.server_open, shown)
    if DP:
        chk("접으면 입력칸이 숨는다", lw.top.itemcget(lw._srv_win, "state") == "hidden")

    # 틀린 비밀번호
    lw.li_pin.clear()
    type_pin(lw.li_pin, "1111")             # 넷째 칸이 차면 바로 로그인한다
    wait(root, lambda: not lw.busy and CALLS)
    settle(root, 0.1)
    chk("넷째 칸이 차면 로그인을 묻는다 (바꾼 서버로)", CALLS[-1:] == [("login", "http://127.0.0.1:8123/", "지우",
                                                                 "1111")], CALLS)
    chk("틀리면 서버의 글 그대로 · 칸을 비운다", status_text(lw) == "비밀번호가 틀렸습니다." and lw.li_pin.get() == "",
        (status_text(lw), lw.li_pin.get()))

    if DP:
        print("   화면 자판")
        for k in ("1", "2", "3"):
            lw.keys[k].invoke()
        chk("자판 1 2 3", lw.li_pin.get() == "123", lw.li_pin.get())
        lw.keys["BS"].invoke()
        chk("지움은 마지막 숫자를", lw.li_pin.get() == "12", lw.li_pin.get())
        lw.keys["3"].invoke()
        n = len(CALLS)
        lw.keys["4"].invoke()
    else:
        lw.li_pin.clear()
        type_pin(lw.li_pin, "123")
        n = len(CALLS)
        type_pin(lw.li_pin, "1234")
    wait(root, lambda: lw.result is not None)
    chk("네 자리가 차면 로그인 (1234)", CALLS[n:] == [("login", "http://127.0.0.1:8123/", "지우", "1234")], CALLS[n:])
    chk("로그인하면 결과 · 세션 · 설정", lw.result and lw.result["user"]["username"] == "지우"
        and config.load_session().get("token") == "tok-지우" and settings.get("server") == "http://127.0.0.1:8123/",
        (lw.result, settings))
    chk("환영 글 (초록 뜻 색)", status_text(lw).startswith("환영합니다") and status_color(lw) in (U.GOOD,),
        (status_text(lw), status_color(lw)))
    chk("조금 뒤 창이 닫힌다", wait(root, lambda: not lw.win.winfo_exists(), 3))


def signup_flow(root):
    print("4. 회원가입")
    del CALLS[:]
    settings = {"server": "https://poket.example.com"}
    lw = ui_login.LoginWindow(root, settings)
    settle(root, 0.3)
    if DP:
        click_item(lw.tabs, "tab_signup")
    else:
        lw.switch("signup")
    chk("회원가입 탭으로", lw.tab == "signup", lw.tab)
    wait(root, lambda: len(lw.genbtns) == 9 and len(lw.cards) == 3)
    chk("세대 아홉 · 카드 셋", len(lw.genbtns) == 9 and len(lw.cards) == 3, (len(lw.genbtns), len(lw.cards)))
    mod = "poketdesktop.skins.dp.login" if DP else "poketdesktop.ui_login"
    chk("카드 클래스", type(lw.cards[0]).__module__ == mod, type(lw.cards[0]).__module__)
    chk("첫 카드가 골라져 있다", lw.picked == "BULBASAUR", lw.picked)
    chk("단추 글이 그 포켓몬", btn_text(lw.btn_signup) == "이상해씨와 함께 시작하기", btn_text(lw.btn_signup))
    if DP:
        chk("고른 카드만 빨간 테", [c.sel for c in lw.cards] == [True, False, False], [c.sel for c in lw.cards])
    wait(root, lambda: all(c.photos for c in lw.cards))
    chk("도트가 카드에 붙는다", all(c.photos for c in lw.cards), [len(c.photos) for c in lw.cards])
    if DP:
        chk("카드 캔버스에 도트 그림", all(c.box.find_withtag("art") for c in lw.cards))
        req, real = lw.win.winfo_reqheight(), lw.win.winfo_height()
        chk("회원가입도 창이 작업 영역에 다 들어간다", req <= real + 1, (req, real))
        if lw.PANEL_H < lw.FORM_H:
            # 화면이 모자라면(작은 화면 · 글자 아주 크게) 칸 안을 굴린다 - 끝까지 굴리면 가입 단추가 다 보인다
            cv = lw._fcv
            cv.yview_moveto(1.0)
            root.update()
            bottom = cv.canvasy(cv.winfo_height())
            chk("  칸 안을 굴리면 가입 단추까지 보인다", bottom >= lw.btn_signup.box[3], (bottom, lw.btn_signup.box))
            cv.yview_moveto(0.0)                     # 아래 검사는 칸의 자리를 누른다 - 처음 자리로 되돌린다
            root.update()

    # 닉네임 확인
    lw.rg_name.set("taken")
    wait(root, lambda: "이미" in hint_text(lw), 4)
    chk("못 쓰는 닉네임", not lw.name_ok and hint_text(lw) == "✕ 이미 쓰고 있는 닉네임입니다.", hint_text(lw))
    if DP:
        chk("못 쓰는 닉네임이면 칸 테가 빨갛다", lw.name_box.cget("highlightbackground") == "#d02828",
            lw.name_box.cget("highlightbackground"))
    type_pin(lw.rg_pin, "4321")
    lw.do_register()
    chk("확인 안 된 닉네임은 안 보낸다", status_text(lw) == "쓸 수 있는 닉네임인지 확인해 주세요."
        and not [c for c in CALLS if c[0] == "register"], status_text(lw))
    lw.rg_name.set("웅이")
    wait(root, lambda: lw.name_ok, 4)
    chk("쓸 수 있는 닉네임", lw.name_ok and hint_text(lw) == "✓ 쓸 수 있는 닉네임입니다.", hint_text(lw))

    # 세대 · 카드
    if DP:
        click_item(lw._fcv, "gen_4")
    else:
        lw.genbtns[4].event_generate("<Button-1>")
    settle(root, 0.1)
    chk("세대 4 로", lw.gen == 4 and [c.mon["internal"] for c in lw.cards] == ["TURTWIG", "CHIMCHAR", "PIPLUP"],
        (lw.gen, [c.mon["internal"] for c in lw.cards]))
    lw.cards[1].box.event_generate("<Button-1>", x=10, y=10)
    settle(root, 0.1)
    chk("카드를 누르면 고른다", lw.picked == "CHIMCHAR" and btn_text(lw.btn_signup) == "불꽃숭이와 함께 시작하기",
        (lw.picked, btn_text(lw.btn_signup)))
    if DP:
        chk("고른 카드만 빨간 테 (둘째)", [c.sel for c in lw.cards] == [False, True, False], [c.sel for c in lw.cards])
        chk("도트가 움직인다", wait(root, lambda: any(c.i for c in lw.cards), 2), [c.i for c in lw.cards])

    # 가입
    lw.rg_pin.clear()
    type_pin(lw.rg_pin, "43")
    lw.do_register()
    chk("모자란 비밀번호는 안 보낸다", status_text(lw) == "비밀번호 4자리를 입력해 주세요.", status_text(lw))
    type_pin(lw.rg_pin, "4321")
    if DP:
        click_item(lw._fcv, lw.btn_signup.tag)
    else:
        lw._enter()
    wait(root, lambda: lw.result is not None)
    chk("가입은 그 이름 · 비밀번호 · 고른 포켓몬으로",
        [c for c in CALLS if c[0] == "register"] == [("register", "https://poket.example.com", "웅이", "4321",
                                                      "CHIMCHAR")], CALLS)
    chk("가입하면 결과", lw.result and lw.result["user"]["username"] == "웅이", lw.result)
    wait(root, lambda: not lw.win.winfo_exists(), 3)

    # 탭을 오가도 고른 세대를 기억하고, 닫기는 None
    lw = ui_login.LoginWindow(root, settings)
    settle(root, 0.2)
    lw.switch("signup")
    wait(root, lambda: len(lw.cards) == 3)
    lw.show_gen(7)
    settle(root, 0.15)                      # (칸을 짓고 80ms 뒤에 닉네임 칸에 손을 놓는다 - 그 전에 칸을 바꾸지 않는다)
    lw.switch("login")
    settle(root, 0.1)
    chk("로그인으로 돌아오면 로그인 칸", lw.tab == "login" and lw.li_pin is not None)
    if DP:
        click_item(lw._fcv, "link")
        chk("'회원가입' 글을 누르면 회원가입 탭", lw.tab == "signup", lw.tab)
    else:
        lw.switch("signup")
    wait(root, lambda: len(lw.cards) == 3)
    chk("고른 세대를 기억한다", lw.gen == 7 and lw.cards[0].mon["internal"] == "G7A", lw.gen)
    settle(root, 0.15)
    lw.cancel()
    chk("닫으면 None", lw.result is None and not lw.win.winfo_exists())


def password(root):
    print("5. 비밀번호 다시 묻기")
    host = tk.Toplevel(root)
    host.geometry("400x300+40+40")
    seen = {}

    def newest():
        found = []

        def walk(w):
            for c in w.winfo_children():
                if isinstance(c, tk.Toplevel):
                    found.append(c)
                walk(c)
        walk(host)
        return found[-1] if found else None

    def answer():
        win = newest()
        if win is None:
            return root.after(50, answer)
        seen["kids"] = [type(c).__name__ for c in win.winfo_children()]
        if DP:
            seen["dp"] = hasattr(win, "pin") and type(win.pin).__module__.endswith("skins.dp.login")
            seen["bar"] = any(isinstance(c, tk.Canvas) and c.cget("bg") == "#d6f3fb" for c in win.winfo_children())
            seen["w"] = win.winfo_width()
        type_pin(PINS[-1], "1357")

    root.after(300, answer)
    got = ui_login.ask_password(host, "회원탈퇴", "정말 탈퇴하려면 비밀번호 4자리를 입력해 주세요. 되돌릴 수 없습니다.")
    chk("네 자리를 치면 그 숫자", got == "1357", got)
    if DP:
        chk("DP 비밀번호 창 (DP 칸)", seen.get("dp"), seen)
        chk("머리는 DP 띠 (dialog_bar)", seen.get("bar"), seen)
        chk("(v2) 창 폭은 기본 창과 같다 (360)", seen.get("w") == 360, seen.get("w"))

    def cancel():
        win = newest()
        if win is None:
            return root.after(50, cancel)
        if DP:
            win.buttons[1].invoke()
        else:
            win.destroy()

    root.after(300, cancel)
    got = ui_login.ask_password(host, "회원탈퇴", "비밀번호를 입력해 주세요.")
    chk("취소하면 None", got is None, got)
    host.destroy()


def main():
    make_gif()
    ui_login.Api = FakeApi
    sprite_cache.ensure = lambda api, num, shiny=False: True
    sprite_cache.ensure_many = lambda api, want: dict(((num, shiny), GIF) for num, shiny in want)
    ui_login.PinEntry.__init__ = _record_pin

    PLAT.before_tk()
    skins.register_fonts()
    root = tk.Tk()
    root.withdraw()
    U.init_fonts(root)
    U.apply_theme(root)
    errors = []
    root.report_callback_exception = lambda e, v, tb: errors.append("%s: %s" % (e.__name__, v))
    print("== 테마: %s" % SKIN)
    chk("이번 실행의 테마", skins.active() == SKIN, skins.active())
    login_flow(root)
    signup_flow(root)
    password(root)
    print("6. 예외")
    chk("그리는 중에 난 예외가 없다", not errors, errors[:3])
    root.destroy()


if __name__ == "__main__":
    main()
    if DP:
        # 같은 동작 검사를 기본 테마로 (따로 띄운다 - 테마는 프로세스마다 한 번 정해진다)
        env = dict(os.environ, POKET_LOGIN_SKIN="default")
        env.pop("POKET_HOME", None)
        out = subprocess.run([sys.executable, os.path.abspath(__file__)], env=env, capture_output=True, text=True)
        for line in out.stdout.splitlines():
            if line.startswith("  ") or line.startswith("=="):
                print("  " + line if not line.startswith("==") else line)
            if line.startswith("합계"):
                bits = line.split()
                OK += int(bits[2])
                FAIL += int(bits[4])
        if out.returncode != 0 or "합계" not in out.stdout:
            FAIL += 1
            print("  FAIL 기본 테마 검사가 끝나지 않았다\n%s" % out.stderr[-1500:])
    print("합계 OK %d FAIL %d" % (OK, FAIL))
    sys.exit(1 if FAIL else 0)
