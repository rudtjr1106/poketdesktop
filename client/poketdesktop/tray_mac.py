# -*- coding: utf-8 -*-
"""맥 메뉴 막대 아이콘.

## NSMenu 를 쓰지 않는다 — 쓰면 앱이 죽는다

맥에서 `NSMenu` 가 열리면 macOS 가 **중첩 런루프**(메뉴 트래킹)를 돌린다.
그 동안에도 Tk 의 `after` 타이머는 계속 발화하는데, 그 경로가 깨져 있다.
파이썬이 통째로 죽는다.

    Fatal Python error: PyEval_RestoreThread: the function must be called
    with the GIL held ... (the current Python thread state is NULL)

**메뉴를 열기만 해도 죽는다.** 항목을 안 눌러도 그렇다. 이 게임은 도트를
움직이려고 `after` 를 쉬지 않고 도니, 메뉴를 여는 순간이 곧 마지막이다.
실제로 그렇게 죽는 것을 재현했다.

그래서 메뉴 막대에는 **아이콘(단추)만** 올리고, 메뉴는 tkinter 로 직접
그린다. 이 게임은 원래 창을 전부 tkinter 로 그리므로 생김새도 오히려
잘 맞는다. 단추만 있고 NSMenu 가 없으면 중첩 런루프가 없어서 멀쩡하다
(도트가 도는 중에 여러 번 눌러도 안 죽는 것까지 확인했다).

## 그 밖에 지켜야 할 것

1. **`tkinter.Tk()` 를 무조건 먼저 만든다.** 그 전에
   `NSApplication.sharedApplication()` 이 불리면 Tk 이 abort 한다.
2. **objc 콜백 안에서 tkinter 를 부르지 않는다.** 단추가 눌렸다는 것만
   적어 두고(`pending`), 꺼내 쓰는 것은 Tk 쪽에서 도는 `_pump` 가 한다.
3. 아이콘 그림은 보통 화면과 레티나 두 벌을 넣는다.

메뉴에 무엇이 들어가는지는 `tray.TrayBase.spec()` 한 곳에만 있다.
여기서는 그걸 tkinter 위젯으로 그리기만 한다.
"""
import io
import traceback

import AppKit
import Foundation
import objc

from . import config
from . import ui_common as U
from .tray import SEP, TrayBase, make_icon_image, val

class _Target(AppKit.NSObject):
    """메뉴 막대 단추가 눌렸을 때 받아 줄 objc 객체.

    **여기서는 tkinter 를 절대 부르지 않는다.** 눌렸다는 것만 적어 둔다.
    """

    def initWithTray_(self, tray):
        self = objc.super(_Target, self).init()
        if self is None:
            return None
        self._tray = tray
        return self

    def clicked_(self, sender):
        self._tray.pending_toggle = True


class Tray(TrayBase):
    """맥 메뉴 막대 아이콘. 윈도우판과 같은 API 를 쓴다."""

    def __init__(self, app):
        TrayBase.__init__(self, app)
        self.item = None
        self._target = None
        self._image = None          # 참조를 놓으면 아이콘이 사라진다
        self.pending_toggle = False  # 단추가 눌렸다 (objc 쪽에서 켠다)
        self._pump_job = None
        self.popup = None           # 떠 있는 메뉴 (U.PopupMenu)

    # ---------------------------------------------------------- 수명
    def start(self):
        bar = AppKit.NSStatusBar.systemStatusBar()
        self.item = bar.statusItemWithLength_(AppKit.NSVariableStatusItemLength)
        self._target = _Target.alloc().initWithTray_(self)

        pt = max(16, int(bar.thickness()) - 4)      # 22pt 막대에 18pt 그림
        self._image = self._nsimage(pt)
        btn = self.item.button()
        btn.setImage_(self._image)
        btn.setImagePosition_(AppKit.NSImageOnly)
        btn.setToolTip_(self._title())
        btn.setTarget_(self._target)
        btn.setAction_(b"clicked:")
        # **setMenu_ 를 부르지 않는다.** 위의 첫 주석을 보라.
        self._pump()

    def _pump(self):
        """objc 쪽에서 적어 둔 것을 **Tk 쪽에서** 꺼내 실행한다."""
        try:
            if self.pending_toggle:
                self.pending_toggle = False
                self.toggle()
        except Exception:                                   # noqa: BLE001
            config.log("트레이 처리 실패\n" + traceback.format_exc())
        finally:
            if self.item is not None:
                self._pump_job = self.app.root.after(60, self._pump)

    def refresh(self):
        if not self.item:
            return
        try:
            self.item.button().setToolTip_(self._title())
            if self.popup is not None:
                self.open()          # 열려 있으면 내용을 새로 그린다
        except Exception:                                   # noqa: BLE001
            config.log("트레이 갱신 실패\n" + traceback.format_exc())

    def stop(self):
        self.close()
        if self._pump_job is not None:
            try:
                self.app.root.after_cancel(self._pump_job)
            except Exception:                               # noqa: BLE001
                pass
            self._pump_job = None
        if self.item:
            try:
                AppKit.NSStatusBar.systemStatusBar().removeStatusItem_(self.item)
            except Exception:                               # noqa: BLE001
                pass
        self.item = None
        self._target = None
        self._image = None

    # ---------------------------------------------------------- 그림
    def _nsimage(self, points):
        """보통 화면과 레티나 양쪽에 맞는 아이콘.

        1배와 2배 그림을 둘 다 넣어 둔다. 2배짜리 하나만 넣으면 보통
        화면에서 그걸 줄여 쓰는데, appicon 이 작은 크기에만 쓰는 단순한
        구도(받침대 없는 몬스터볼)를 못 쓰게 된다.
        """
        ns = AppKit.NSImage.alloc().initWithSize_(
            AppKit.NSMakeSize(points, points))
        for scale in (1, 2):
            b = io.BytesIO()
            make_icon_image(points * scale).save(b, "png")
            raw = b.getvalue()
            data = Foundation.NSData.dataWithBytes_length_(raw, len(raw))
            rep = AppKit.NSBitmapImageRep.imageRepWithData_(data)
            if rep is None:
                continue
            rep.setSize_(AppKit.NSMakeSize(points, points))
            ns.addRepresentation_(rep)
        # 몬스터볼은 빨간색이 살아야 한다. template 로 두면 단색 실루엣이 된다.
        ns.setTemplate_(False)
        return ns

    # ---------------------------------------------------------- 메뉴
    def toggle(self):
        if self.popup is not None and self.popup.alive():
            self.close()
        else:
            self.open()

    def close(self):
        if self.popup is not None:
            self.popup.close()
        self.popup = None

    def open(self):
        """메뉴를 tkinter 로 그린다 (ui_common.PopupMenu)."""
        try:
            rows = self._rows(self.spec(), 0)
        except Exception:                                   # noqa: BLE001
            config.log("트레이 메뉴를 만들지 못했습니다\n"
                       + traceback.format_exc())
            return
        self.close()
        x, y = self._anchor()
        try:
            self.popup = U.PopupMenu(self.app.root, rows, x, y, anchor="ne")
        except Exception:                                   # noqa: BLE001
            self.popup = None
            config.log("트레이 메뉴를 띄우지 못했습니다\n"
                       + traceback.format_exc())

    def _anchor(self):
        """메뉴 막대 아이콘 바로 아래, 오른쪽 끝에 맞춘다."""
        root = self.app.root
        sw = root.winfo_screenwidth()
        try:
            fr = self.item.button().window().frame()
            return int(fr.origin.x + fr.size.width), 30
        except Exception:                                   # noqa: BLE001
            return sw - 8, 30

    def _rows(self, items, depth):
        """spec() 이 준 것을 PopupMenu 가 받는 줄 목록으로 바꾼다.

        하위 메뉴는 따로 띄우지 않고 제목 + 들여쓰기로 편다. 작은 창
        하나에 다 보이는 편이 여기서는 낫다.
        """
        out = []
        for it in items:
            if it is SEP:
                out.append(None)
                continue
            text = val(it.text)
            if it.submenu is not None:
                out.append({"text": text, "header": True, "indent": depth})
                out.extend(self._rows(it.submenu, depth + 1))
                continue
            out.append({
                "text": text,
                "command": (self._wrap(it.action) if it.action is not None
                            else None),
                "enabled": bool(val(it.enabled)),
                "checked": (None if it.checked is None
                            else bool(val(it.checked))),
                "bold": bool(it.default),
                "indent": depth,
            })
        return out

    def _wrap(self, fn):
        def run():
            # 창을 앞으로 꺼내 준다. Dock 에 안 뜨는 앱이라 그냥 열면
            # 다른 프로그램 뒤에서 뜰 수 있다.
            try:
                AppKit.NSApplication.sharedApplication(
                    ).activateIgnoringOtherApps_(True)
            except Exception:                               # noqa: BLE001
                pass
            fn()
        return run


