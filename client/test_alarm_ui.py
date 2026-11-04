# -*- coding: utf-8 -*-
"""포켓몬 알림 타이머 화면 검사.

    python client/test_alarm_ui.py
    python client/run_as_windows.py client/test_alarm_ui.py

**진짜 Overlay 와 도트 창을 띄운다.** 서버는 필요 없다 (알림은 이 PC 에만 있다). 설계: design-notes/2026-11-04-focus-timer.md

못 박는 것:

  1. 걸기: 몇 분 뒤 / 몇 시에(지났으면 내일) + 메모. 이 PC 설정에 저장된다. 1분 미만 · 빈 것은 거절, 10개까지.
  2. 울리기: 알림을 건 포켓몬 위에 말풍선 (소리 없음). **누를 때까지 안 사라진다**, 누르면 닫힌다.
     집중 중이면 집중 포켓몬 위에 바로 (사용자 결정 11/04). 도트가 숨어 있으면 보일 때까지 기다린다.
  3. 꺼져 있던 사이 지난 알림은 켤 때 '놓친 알림' 으로 한 번 띄우고 지운다.
  4. 창과 메뉴 줄.
"""
import os
import sys
import tempfile
import time

os.environ["POKET_HOME"] = tempfile.mkdtemp(prefix="poket-test-alarm-")

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.dirname(HERE))

import tkinter as tk                                        # noqa: E402

import test_focus_ui as TF                                  # noqa: E402  (도트 · 가짜 앱 틀을 같이 쓴다)
from poketdesktop import alarm                              # noqa: E402
from poketdesktop import config, overlay, sprite_cache, walk_cache  # noqa: E402
from poketdesktop import platform_os as PLAT                # noqa: E402
from poketdesktop import ui_common as U                     # noqa: E402
from test_learn_dialog import squeezed, texts               # noqa: E402

OK = FAIL = 0


def chk(name, cond, got=""):
    global OK, FAIL
    if cond:
        OK += 1
        print("  OK   %s" % name)
    else:
        FAIL += 1
        print("  FAIL %s   %r" % (name, got))


def raises(fn, *a, **kw):
    try:
        fn(*a, **kw)
    except ValueError as e:
        return str(e) or True
    return None


def past_hhmm():
    t = time.localtime(time.time() - 120)
    return "%02d:%02d" % (t.tm_hour, t.tm_min)


def live(ac):
    return [b for b in ac.bubbles if not b.dead]


def over(ac, pet):
    return [b for b in live(ac) if b.pet is pet]


def main():
    home = config.data_dir()
    if not os.path.realpath(home).startswith(os.path.realpath(tempfile.gettempdir())):
        print("POKET_HOME 이 임시 폴더가 아닙니다 - 멈춥니다: %s" % home)
        return 1
    PLAT.before_tk()
    root = tk.Tk()
    root.withdraw()
    U.init_fonts(root)
    U.apply_theme(root)
    errors = []

    def on_err(exc, val, tb):
        import traceback
        errors.append("".join(traceback.format_exception(exc, val, tb))[-400:])
    root.report_callback_exception = on_err
    for n, col in ((4, (230, 110, 40, 255)), (7, (80, 140, 220, 255)), (1, (60, 160, 90, 255))):
        TF.SHEETS[n] = TF.make_sheet("s%d.png" % n, 32, col)
        TF.FILES[n] = TF.make_dot("d%d.png" % n, col)
    sprite_cache.ensure = lambda api, num, shiny=False: TF.FILES.get(num)
    walk_cache.ensure = lambda api, num, name="Walk", shiny=False: (
        TF.SHEETS.get(num) if name == "Walk" and TF.SHEETS.get(num) else (None, None))
    settings = dict(config.DEFAULTS)
    settings["megaWalk"] = []
    ov = overlay.Overlay(root, settings)
    ov.paths.update(dict(((n, False), p) for n, p in TF.FILES.items()))
    ov.walks.update(dict(TF.SHEETS))
    ov.sync([TF.mon(1, 4, 0, "파이리"), TF.mon(2, 7, 1, "꼬부기"), TF.mon(3, 1, 2, "이상해씨")], {}, {})
    ov.start()
    TF.settle(root, 0.3)
    app = TF.MiniApp(root, ov)
    alarm.RETRY_MS = 400
    try:
        print("=== 걸기 ===")
        ac = alarm.AlarmController(app)
        app.alarms = ac
        chk("기본값에 알림 칸", config.DEFAULTS.get("alarms") == [])
        a = ac.add(minutes=1, memo="회의", pet_id=2)
        chk("저장된다", config.load_settings()["alarms"][0]["memo"] == "회의"
            and abs(a["at"] - (time.time() + 60)) < 5, config.load_settings()["alarms"])
        b = ac.add(clock=past_hhmm())
        chk("시각: 지난 시각은 내일", b["at"] > time.time() + 20 * 3600, b)
        chk("시각: 앞으로 올 시각은 오늘", ac.add(clock=time.strftime("%H:%M", time.localtime(time.time() + 3600)))["at"]
            < time.time() + 3700)
        chk("1분 미만은 거절", raises(ac.add, minutes=0))
        chk("빈 것은 거절", raises(ac.add))
        chk("이상한 시각은 거절", raises(ac.add, clock="25:99"))
        chk("메모는 40자까지", len(ac.add(minutes=5, memo="가" * 60)["memo"]) == 40)
        while len(ac.items()) < alarm.MAX:
            ac.add(minutes=30)
        chk("10개까지", "10" in str(raises(ac.add, minutes=30)), raises(ac.add, minutes=30))
        chk("이른 순", [x["at"] for x in ac.items()] == sorted(x["at"] for x in ac.items()))
        ac.remove(b["id"])
        chk("지우기", all(x["id"] != b["id"] for x in ac.items()) and len(config.load_settings()["alarms"]) == alarm.MAX - 1)
        for x in list(ac.items()):
            ac.remove(x["id"])

        print("\n=== 울리기 ===")
        a = ac.add(minutes=1, memo="회의", pet_id=2)
        ac.fire(a)
        TF.settle(root, 0.4)
        chk("알림을 건 포켓몬 위에 말풍선", len(over(ac, ov.pets[2])) == 1 and "회의" in ac.said[-1], ac.said)
        chk("울린 알림은 목록에서 빠진다", all(x["id"] != a["id"] for x in ac.items()))
        TF.settle(root, 5.0)
        chk("누를 때까지 안 사라진다", len(live(ac)) == 1)
        bub = live(ac)[0]
        bub.label.event_generate("<Button-1>", x=2, y=2)
        TF.settle(root, 0.4)
        chk("누르면 닫힌다", len(live(ac)) == 0)
        ac.add(minutes=1, pet_id=2)
        ac.add(minutes=1, pet_id=2)
        for x in list(ac.items()):
            ac.fire(x)
        TF.settle(root, 0.8)
        two = over(ac, ov.pets[2])
        chk("두 개면 위로 쌓인다", len(two) == 2 and two[1].offset > two[0].offset, [b.offset for b in two])
        for x in live(ac):
            x.close()

        app.focus.begin(TF.run_view(pet=3, stat="spa"))
        TF.settle(root, 0.3)
        ac.fire(ac.add(minutes=5, pet_id=2))
        TF.settle(root, 0.3)
        chk("집중 중이면 집중 포켓몬 위에 바로", len(over(ac, ov.pets[3])) == 1 and not over(ac, ov.pets[2]))
        app.focus.clear()
        for x in live(ac):
            x.close()

        ov.set_hidden(True)
        ac.fire(ac.add(minutes=5, memo="숨김"))
        TF.settle(root, 1.0)
        chk("숨어 있으면 기다린다", len(live(ac)) == 0)
        ov.set_hidden(False)
        TF.pump(root, lambda: len(live(ac)) == 1, 3.0)
        chk("보이면 띄운다", len(live(ac)) == 1 and "숨김" in ac.said[-1], ac.said)
        for x in live(ac):
            x.close()

        settings["alarms"] = [{"id": 99, "at": time.time() - 600, "memo": "점심", "pet": 1}]
        config.save_settings(settings)
        ac2 = alarm.AlarmController(app)
        ac2.start()
        TF.settle(root, 0.4)
        chk("놓친 알림은 켤 때 한 번", len(live(ac2)) == 1 and "놓친 알림" in ac2.said[-1] and "점심" in ac2.said[-1],
            ac2.said)
        chk("놓친 알림은 지운다", config.load_settings()["alarms"] == [])
        for x in live(ac2):
            x.close()
        ac2.stop()

        a = ac.add(minutes=1, memo="저절로")
        for x in settings["alarms"]:
            if x["id"] == a["id"]:
                x["at"] = time.time() + 1          # 1분을 기다리지 않는다 - 1초 뒤로 당겨 다시 예약
        ac._schedule()
        TF.pump(root, lambda: any("저절로" in s for s in ac.said), 5.0)
        chk("때가 되면 저절로 울린다", any("저절로" in s for s in ac.said), ac.said)
        for x in live(ac):
            x.close()

        print("\n=== 창 · 메뉴 줄 ===")
        ac.add(minutes=30, memo="물 마시기")
        w = alarm.AlarmWindow(app, ov.pets[2])
        TF.settle(root, 0.4)
        t = " ".join(texts(w.win))
        chk("창: 두 방식 · 메모 · 걸어 둔 목록", "몇 분 뒤" in t and "몇 시에" in t and "메모" in t and "물 마시기" in t, t)
        chk("창: 조사가 자연스럽다 ('꼬부기가 알려 줄게요')", "꼬부기가 알려 줄게요" in t and "이(가)" not in t, t)
        chk("창 글자가 눌리지 않는다", not squeezed(w.win), squeezed(w.win))
        w.amount.delete(0, "end")
        w.amount.insert(0, "15")
        w.memo.insert(0, "스트레칭")
        w.submit()
        TF.settle(root, 0.3)
        chk("창에서 걸기", any(x["memo"] == "스트레칭" and x["pet"] == 2 for x in ac.items())
            and "스트레칭" in " ".join(texts(w.win)), ac.items())
        w.amount.delete(0, "end")
        w.amount.insert(0, "0")
        w.submit()
        TF.settle(root, 0.2)
        chk("거절되면 까닭을 창에", "1분" in w.err.cget("text"), w.err.cget("text"))
        w.pick_mode("clock")
        w.amount.delete(0, "end")
        w.amount.insert(0, "7:05")
        w.submit()
        TF.settle(root, 0.2)
        chk("몇 시에 걸기", any(time.strftime("%H:%M", time.localtime(x["at"])) == "07:05" for x in ac.items()))
        w.close()
        chk("메뉴 줄", (alarm.menu_row(app, ov.pets[2]) or {}).get("text") == "알림 맞추기...")
        chk("야생 · 남의 포켓몬엔 없다", alarm.menu_row(app, type("P", (), {"id": -3})()) is None)
        ac.stop()
    finally:
        ov.stop()
        ov.clear()
        TF.settle(root, 0.2)
    chk("콜백에서 난 예외가 없다", not errors, errors[:2])
    root.destroy()
    print("\n%d개 통과, %d개 실패" % (OK, FAIL))
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
