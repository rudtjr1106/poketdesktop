# -*- coding: utf-8 -*-
"""잡기 모드 '고른 포켓몬만' 의 고르는 창 · 설정 줄 (진짜 Tk).

    python client/test_catch_pick_ui.py              기본 테마
    POKET_SKIN=dp python client/test_catch_pick_ui.py  DP 테마 (설정 창이 다르다 - 아래 설명 창의 단추)

판단(무엇을 서버에 보내나)은 test_catch_pick.py 가 본다. 여기서는

  1. 설정 창에 '고른 포켓몬만' 과 '고르기…' 가 있고, 누르면 고르는 창이 하나만 뜬다.
  2. 고르는 창: 1025종이어도 줄 위젯은 화면만큼 (U.VirtualList), 찾기(한글 조합 글자도 - trace),
     체크하면 바로 설정 파일에 적고 설정 창의 '고른 포켓몬 N종' 이 바뀐다.
  3. 굴려서 다시 쓰는 줄에 지난 체크가 남지 않는다. '고른 것만 보기' · '모두 풀기'.
  4. 창은 화면(작업 영역)보다 크지 않고, 닫으면 다시 열 수 있다.
"""
import os
import sys
import tempfile

os.environ["POKET_HOME"] = tempfile.mkdtemp(prefix="poket-test-catchpick-ui-")

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
sys.path.insert(0, ROOT)

import tkinter as tk                                        # noqa: E402

from common import pokelogic as P                           # noqa: E402
from poketdesktop import config                             # noqa: E402
from poketdesktop import platform_os as PLAT                # noqa: E402
from poketdesktop import skins                              # noqa: E402
from poketdesktop import ui_catch_pick as CP                # noqa: E402
from poketdesktop import ui_common as U                     # noqa: E402
from poketdesktop import ui_settings                        # noqa: E402
from test_learn_dialog import texts                         # noqa: E402

OK = FAIL = 0
DEX = P.Pokedex.load(os.path.join(ROOT, "server", "data", "pokedex.json"))


def chk(name, cond, got=""):
    global OK, FAIL
    if cond:
        OK += 1
        print("  OK   %s" % name)
    else:
        FAIL += 1
        print("  FAIL %s   %r" % (name, got))


def settle(root, n=6):
    for _ in range(n):
        root.update()


class App(object):
    """설정 창이 만지는 것만 갖춘 껍데기 (test_battle_zoom 의 것과 같은 꼴) + 도감."""
    wild = None
    boss_key_error = ""

    def __init__(self, root):
        self.root, self.overlay = root, self
        self.settings = dict(config.DEFAULTS)
        self.dex = DEX

    def apply_names(self):
        pass

    def apply_alpha(self):
        pass

    def refresh_tray(self):
        pass

    def set_size(self, px):
        pass

    def stealth_on(self):
        return False

    def boss_key(self):
        return ""

    def apply_boss_key(self, combo=None):
        return True, ""


def shown_rows(w):
    return [(row.sp["internal"], row.var.get()) for _i, row in w.vl.shown()]


def main():
    PLAT.before_tk()
    root = tk.Tk()
    root.withdraw()
    U.init_fonts(root)
    U.apply_theme(root)
    errors = []

    def on_err(exc, val, tb):
        import traceback
        errors.append("".join(traceback.format_exception(exc, val, tb))[-500:])
    root.report_callback_exception = on_err
    dp = skins.active() == "dp"
    print("테마: %s" % skins.active())

    app = App(root)
    sw = ui_settings.SettingsWindow(app)
    app.settings_win = sw
    settle(root)
    if dp:
        row = next(r for r in sw.rows if r["label"] == "야생 배틀에서 잡기")
        chk("DP: 잡기 줄에 '고른 포켓몬만'", ("pick", "고른 포켓몬만") in row["choices"])
        sw._pick_row(sw.rows.index(row))
        settle(root)
        b = sw.btns.get("act:고르기…")
        chk("DP: 그 줄을 고르면 아래 설명 창에 '고르기…' 단추", b is not None and b.box is not None,
            [k for k in sw.btns if isinstance(k, str)])
        chk("DP: 몇 종 골랐는지 적는다", "아직 고른 포켓몬이 없습니다" in row["value"](), row["value"]())
        row["put"]("pick")
        chk("DP: ◀ ▶ 로 '고른 포켓몬만' 을 고르면 저장한다", config.load_settings()["catchMode"] == "pick")
        skin_row = next((r for r in sw.rows if r.get("action") and r["action"][0] == "다시 켜서 적용"), None)
        if skin_row is not None:
            sw.skin_pick = "__other__"          # 다시 켜서 적용 단추가 보이게
            sw._pick_row(sw.rows.index(skin_row))
            settle(root)
            chk("DP: 다른 줄로 옮기면 '고르기…' 는 숨고 그 줄의 단추가 따로 뜬다",
                sw.btns["act:고르기…"].box is None and sw.btns.get("act:다시 켜서 적용") is not None
                and sw.btns["act:다시 켜서 적용"].box is not None)
            sw.skin_pick = skins.active()
            sw._pick_row(sw.rows.index(row))
            settle(root)
    else:
        seen = texts(sw.win)
        chk("설정 창에 '고른 포켓몬만' 과 '고르기…'", "고른 포켓몬만" in seen and "고르기…" in seen, seen[:0])
        chk("아직 고른 것이 없다고 적는다", sw.catch_pick_note.cget("text") == "아직 고른 포켓몬이 없습니다")
        sw.catch.set("pick")
        sw._set_catch()
        chk("'고른 포켓몬만' 을 고르면 저장한다", config.load_settings()["catchMode"] == "pick")

    sw._open_catch_pick()
    settle(root, 10)
    w = app.catch_pick_window
    chk("고르는 창이 뜬다", w is not None and w.alive())
    sw._open_catch_pick()
    settle(root)
    chk("두 번 눌러도 하나만", app.catch_pick_window is w)
    x1, y1, x2, y2 = U._work_area(w.win)
    chk("창이 작업 영역보다 크지 않다", w.win.winfo_height() <= y2 - y1 and w.win.winfo_width() <= x2 - x1,
        (w.win.winfo_width(), w.win.winfo_height()))
    chk("1025종 목록", len(w.vl.entries) == 1025, len(w.vl.entries))
    chk("줄 위젯은 화면만큼 (%d개)" % w.vl.made, 0 < w.vl.made < 60, w.vl.made)
    first = shown_rows(w)
    chk("도감 순서로 이름만 (No.0001 이상해씨)", first and first[0][0] == "BULBASAUR"
        and w.vl.shown()[0][1].chk.cget("text") == "No.0001  이상해씨", first[:2])

    # 체크 - 설정 파일 · 설정 창의 글
    row = w.vl.shown()[0][1]
    row.chk.invoke()
    settle(root)
    chk("체크하면 바로 저장한다", config.load_settings()["catchPick"] == ["BULBASAUR"],
        config.load_settings().get("catchPick"))
    if dp:
        chk("설정 창의 글이 바뀐다", "고른 포켓몬 1종" in next(
            r for r in sw.rows if r["label"] == "야생 배틀에서 잡기")["value"]())
    else:
        chk("설정 창의 글이 바뀐다", sw.catch_pick_note.cget("text") == "고른 포켓몬 1종",
            sw.catch_pick_note.cget("text"))
    chk("창의 고른 수", w.count.cget("text") == "고른 포켓몬 1종", w.count.cget("text"))
    chk("기본값 리스트는 그대로", config.DEFAULTS["catchPick"] == [])

    # 굴려서 다시 쓴 줄에 체크가 안 남는다
    w.vl.canvas.yview_moveto(0.5)
    w.vl.sync()
    settle(root)
    mid = shown_rows(w)
    chk("굴린 줄에 지난 체크가 안 남는다", mid and not any(v for _k, v in mid), mid[:3])
    w.vl.canvas.yview_moveto(0)
    w.vl.sync()
    settle(root)
    chk("돌아오면 고른 것은 체크로", shown_rows(w)[0] == ("BULBASAUR", 1), shown_rows(w)[:1])

    # 찾기 (한글 · 번호)
    w.q.set("피카")
    settle(root)
    chk("한글로 찾는다", [k for k, _v in shown_rows(w)] == ["PIKACHU"], shown_rows(w))
    w.vl.shown()[0][1].chk.invoke()
    w.q.set("0133")
    settle(root)
    chk("번호로 찾는다", [k for k, _v in shown_rows(w)] == ["EEVEE"], shown_rows(w))
    w.vl.shown()[0][1].chk.invoke()
    w.q.set("없는포켓몬")
    settle(root)
    chk("없으면 빈 목록 + 알림", not w.vl.entries and w.empty.winfo_ismapped()
        and w.empty.cget("text") == "찾는 포켓몬이 없습니다.")
    w.q.set("")
    settle(root)
    chk("도감 순서로 적는다", config.load_settings()["catchPick"] == ["BULBASAUR", "PIKACHU", "EEVEE"],
        config.load_settings()["catchPick"])

    # 고른 것만 보기 - 풀면 그 줄이 빠진다
    w.only.set(True)
    w.redraw(top=True)
    settle(root)
    chk("고른 것만 보기", shown_rows(w) == [("BULBASAUR", 1), ("PIKACHU", 1), ("EEVEE", 1)], shown_rows(w))
    w.vl.shown()[1][1].chk.invoke()
    settle(root)
    chk("고른 것만 보는 중에 풀어도 줄은 남는다 (다음 줄이 안 밀린다)",
        shown_rows(w) == [("BULBASAUR", 1), ("PIKACHU", 0), ("EEVEE", 1)], shown_rows(w))
    # (테마가 색을 바꿔 칠하므로 값이 아니라 '다른 줄과 다르다' 로 본다)
    normal_fg = w.vl.shown()[0][1].chk.cget("fg")
    chk("푼 줄은 흐리게", w.vl.shown()[1][1].chk.cget("fg") != normal_fg, w.vl.shown()[1][1].chk.cget("fg"))
    w.vl.shown()[2][1].chk.invoke()
    settle(root)
    chk("이어 푼 것은 EEVEE", config.load_settings()["catchPick"] == ["BULBASAUR"]
        and shown_rows(w) == [("BULBASAUR", 1), ("PIKACHU", 0), ("EEVEE", 0)], shown_rows(w))
    w.vl.shown()[1][1].chk.invoke()
    settle(root)
    chk("흐린 줄을 다시 체크하면 원래대로", shown_rows(w)[1] == ("PIKACHU", 1)
        and w.vl.shown()[1][1].chk.cget("fg") == normal_fg and "PIKACHU" not in w.dim)
    w.vl.shown()[1][1].chk.invoke()
    settle(root)
    w.only.set(True)
    w.redraw(top=True)                      # 보기를 다시 고르면 흐린 줄을 정리한다
    settle(root)
    chk("보기를 바꾸면 푼 줄이 정리된다", shown_rows(w) == [("BULBASAUR", 1)], shown_rows(w))
    w.vl.shown()[0][1].chk.invoke()
    w.q.set("바")                            # 찾기를 바꿔도 정리된다
    settle(root)
    chk("찾기를 바꾸면 푼 줄이 정리된다", not w.dim and "BULBASAUR" not in [k for k, _v in shown_rows(w)],
        (w.dim, shown_rows(w)[:3]))
    w.q.set("")
    w.only.set(False)
    w.redraw(top=True)
    settle(root)
    for k in ("BULBASAUR", "PIKACHU", "EEVEE"):
        w.picked.add(k)
    w._save()
    w.only.set(True)
    w.redraw(top=True)
    settle(root)
    w.vl.shown()[1][1].chk.invoke()
    settle(root)
    w.clear()
    settle(root)
    chk("모두 풀기", config.load_settings()["catchPick"] == [] and not w.vl.entries
        and w.empty.cget("text") == "고른 포켓몬이 없습니다.")
    w.only.set(False)
    w.redraw(top=True)
    settle(root)

    # 모드가 pick 이 아니면 창이 알려 준다
    app.settings["catchMode"] = "new"
    w.focus()
    chk("'고른 포켓몬만' 이 아니면 알려 준다", "적용됩니다" in w.note.cget("text"), w.note.cget("text"))

    # 닫고 다시 열기 (화면 안에서 없앤다 - 맥 Tk 8.6.17 은 화면 밖에서 없애면 update 가 돈다)
    w.close()
    settle(root)
    chk("닫으면 비운다", app.catch_pick_window is None)
    app.settings["catchPick"] = ["MEW"]
    sw._open_catch_pick()
    settle(root, 10)
    w2 = app.catch_pick_window
    chk("다시 열면 저장된 것을 읽는다", w2 is not None and w2 is not w and w2.picked == {"MEW"})
    w2.close()

    # 모드를 바꾸면 열린 고르는 창의 안내 글도 바뀐다 / 기본값으로
    app.settings["catchPick"] = ["MEW"]
    sw.catch.set("pick")
    sw._set_catch()
    sw._open_catch_pick()
    settle(root, 10)
    w5 = app.catch_pick_window
    chk("모드가 pick 이면 안내에 '적용됩니다' 가 없다", "적용됩니다" not in w5.note.cget("text"), w5.note.cget("text"))
    sw.catch.set("new")
    sw._set_catch()
    chk("설정에서 모드를 바꾸면 열린 창의 안내가 바로 바뀐다", "적용됩니다" in w5.note.cget("text"), w5.note.cget("text"))
    sw.catch.set("pick")
    sw._set_catch()
    chk("다시 pick 으로 하면 안내가 사라진다", "적용됩니다" not in w5.note.cget("text"))
    real_status = U.set_status
    U.set_status = lambda *a, **k: None
    try:
        sw.reset()
    finally:
        U.set_status = real_status
    settle(root)
    chk("기본값으로 하면 열린 창의 안내도 바뀐다 (모드 new)", "적용됩니다" in w5.note.cget("text"),
        w5.note.cget("text"))
    chk("기본값으로 해도 고른 것은 남는다", w5.picked == {"MEW"}, w5.picked)

    # 설정 창을 닫았다 다시 열어도 고르는 창이 새 설정 창에 알린다
    sw.close()
    settle(root)
    sw2 = ui_settings.SettingsWindow(app)
    app.settings_win = sw2
    settle(root)
    w5.vl.shown()[0][1].chk.invoke()
    settle(root)
    n = len(config.catch_pick(app.settings))
    if dp:
        chk("새 설정 창에 고른 수가 바뀐다 (DP)", ("고른 포켓몬 %d종" % n) in next(
            r for r in sw2.rows if r["label"] == "야생 배틀에서 잡기")["value"](), n)
    else:
        chk("새 설정 창에 고른 수가 바뀐다", sw2.catch_pick_note.cget("text") == "고른 포켓몬 %d종" % n,
            (sw2.catch_pick_note.cget("text"), n))
    # 같은 창을 다시 '고르기…' 로 눌러도 하나만
    sw2._open_catch_pick()
    settle(root)
    chk("새 설정 창에서 눌러도 같은 고르는 창", app.catch_pick_window is w5)
    w5.close()
    sw = sw2

    # 도감이 오기 전에 열었다 - 다음에 '고르기…' 를 누를 때 종 목록을 다시 읽는다
    app.dex = None
    sw._open_catch_pick()
    settle(root)
    w4 = app.catch_pick_window
    chk("도감 전: 빈 목록", not w4.vl.entries and "도감" in w4.note.cget("text"))
    app.dex = DEX
    sw._open_catch_pick()
    settle(root, 10)
    chk("도감이 온 뒤 다시 누르면 같은 창이 종 목록을 읽는다", app.catch_pick_window is w4 and len(w4.vl.entries) == 1025,
        len(w4.vl.entries))
    chk("안내의 '도감을 못 받았습니다' 가 사라진다", "도감" not in w4.note.cget("text"), w4.note.cget("text"))
    w4.close()

    # 로그아웃·계정 전환 때 닫힌다 (app.close_windows)
    from poketdesktop.app import App as RealApp
    sw._open_catch_pick()
    settle(root)
    w6 = app.catch_pick_window

    class Fake(object):
        hub = None
        _live_job = None
        close_arena = lambda self: None            # noqa: E731
        _drop_pillar = lambda self: None           # noqa: E731
    fk = Fake()
    fk.catch_pick_window = w6
    RealApp.close_windows(fk)
    settle(root)
    chk("close_windows 가 고르는 창을 닫는다", fk.catch_pick_window is None and not w6.alive())
    app.catch_pick_window = None
    app.dex = DEX

    # 도감이 없을 때
    app.dex = None
    sw._open_catch_pick()
    settle(root)
    w3 = app.catch_pick_window
    chk("도감이 없으면 빈 목록 + 안내", not w3.vl.entries and "도감" in w3.note.cget("text"))
    w3.close()

    try:
        sw.close()
    except Exception:                                       # noqa: BLE001
        pass
    settle(root)
    chk("도는 동안 오류 없음", not errors, errors[:2])
    root.destroy()
    print()
    print("======================================================")
    print("  합계  OK %d   FAIL %d" % (OK, FAIL))
    print("======================================================")
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
