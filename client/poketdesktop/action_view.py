# -*- coding: utf-8 -*-
"""맥: 액션 배틀 창 (2.6.0) - 앱이 따로 띄우는 자식 프로세스.

앱(Tk 프로세스)이 `--action-view` 를 달아 자기를 한 번 더 띄우고, 주소를 stdin 한 줄로 넘긴다 (action_launch).
주소에는 한 번 쓰는 입장권이 #조각으로 붙어 있다 - 명령 줄에 남기지 않으려고 stdin 으로 받는다.

여기서는 NSApplication 하나에 창 하나, 그 안을 WKWebView 가 채운다. **Tk 를 쓰지 않는다** - tkinter ·
poketdesktop.app 를 불러오지 않는다. Tk 과 NSApplication 을 한 프로세스에서 같이 돌리면 부딪힌다 (tray_mac 의 첫 주석).

  · 창을 닫으면 끝난다. Cmd+Q · Cmd+W 도 이 창만 닫는다 (앱은 따로 돈다).
  · 부모(앱)가 죽으면 끝난다 - 1초마다 부모 pid 를 본다. 고아로 남아 판을 붙잡지 않게.
  · 키는 웹 화면이 받는다 (웹뷰를 첫 응답자로). 키를 누르고 있어도 악센트 고르기 창이 안 뜨게 한다.

AppKit · WebKit 은 main() 안에서만 불러온다. 앱이 FLAG 를 보려고 이 모듈을 불러도 웹뷰가 딸려 오지 않는다.
"""
import os

FLAG = "--action-view"
TITLE = "포스크탑 액션 배틀"
SIZE = (1280, 760)
MIN_SIZE = (640, 380)
PARENT_POLL = 1.0            # 초. 부모가 살아 있는지 보는 간격
URL_MAX = 8192               # stdin 에서 이보다 길게는 안 읽는다
CANCELLED = -999             # NSURLErrorCancelled - 오류가 아니다 (다른 주소로 넘어가며 앞의 것을 그만둔 것)
FAIL_HTML = ('<meta charset="utf-8"><body style="margin:0;height:100vh;display:grid;place-items:center;'
             'background:#14161c;color:#d8dbe4;font:16px -apple-system,sans-serif">'
             '액션 배틀 화면을 열지 못했습니다. 창을 닫고 다시 해 주세요.</body>')


def read_url(fd=0):
    """stdin(fd) 의 첫 줄 = 주소. 없으면 "".

    sys.stdin 을 쓰지 않는다 - 얼린 창 앱에서는 None 일 수 있다. 파일 번호에서 바로 읽는다.
    """
    buf = b""
    while b"\n" not in buf and len(buf) < URL_MAX:
        try:
            chunk = os.read(fd, 4096)
        except OSError:
            break
        if not chunk:
            break
        buf += chunk
    return buf.split(b"\n", 1)[0].decode("utf-8", "replace").strip()


def main():
    """주소를 받아 창을 띄우고 닫힐 때까지 돈다. 종료 코드를 돌려준다 (0 정상 · 1 오류 · 2 주소 없음).

    창이 닫히면 NSApplication 이 프로세스를 바로 끝내므로 정상으로는 여기로 돌아오지 않는다.
    """
    url = read_url()
    if not url:
        return 2
    ppid = os.getppid()
    if ppid == 1:
        return 0                      # 부모가 이미 없다 (띄운 앱이 그새 꺼졌다)
    try:
        _run(url, ppid)
    except Exception:                                       # noqa: BLE001
        import traceback
        from . import config
        config.log("액션 배틀 창 오류\n" + traceback.format_exc())
        return 1
    return 0


def _run(url, ppid):
    import AppKit
    import Foundation
    import WebKit

    target = Foundation.NSURL.URLWithString_(url)
    if target is None:
        raise ValueError("주소를 읽지 못했습니다")
    # 이 프로세스 안에서만 (저장하지 않는다): 죽은 뒤 '창 복구' 를 묻지 않는다 (platform_mac.before_tk) ·
    # W A S D 를 누르고 있어도 악센트 고르기 창 대신 키가 계속 들어간다.
    Foundation.NSUserDefaults.standardUserDefaults().registerDefaults_(
        {"ApplePersistenceIgnoreState": True, "ApplePressAndHoldEnabled": False})
    app = AppKit.NSApplication.sharedApplication()
    # 얼린 앱은 Info.plist 의 LSUIElement 로 Dock 에 안 뜬다. 이 창은 Dock · Cmd+Tab 에 떠야 다시 찾는다.
    app.setActivationPolicy_(AppKit.NSApplicationActivationPolicyRegular)

    win = AppKit.NSWindow.alloc().initWithContentRect_styleMask_backing_defer_(
        Foundation.NSMakeRect(0, 0, SIZE[0], SIZE[1]),
        AppKit.NSWindowStyleMaskTitled | AppKit.NSWindowStyleMaskClosable
        | AppKit.NSWindowStyleMaskMiniaturizable | AppKit.NSWindowStyleMaskResizable,
        AppKit.NSBackingStoreBuffered, False)
    win.setTitle_(TITLE)
    win.setReleasedWhenClosed_(False)
    win.setRestorable_(False)
    win.setContentMinSize_(Foundation.NSMakeSize(*MIN_SIZE))
    win.center()

    view = WebKit.WKWebView.alloc().initWithFrame_configuration_(
        win.contentView().bounds(), WebKit.WKWebViewConfiguration.alloc().init())
    win.setContentView_(view)

    keeper = _keeper_class().alloc().init()
    keeper.win, keeper.view, keeper.ppid = win, view, ppid
    win.setDelegate_(keeper)
    view.setUIDelegate_(keeper)
    view.setNavigationDelegate_(keeper)
    app.setDelegate_(keeper)
    app.setMainMenu_(_menu(keeper))
    Foundation.NSTimer.scheduledTimerWithTimeInterval_target_selector_userInfo_repeats_(
        PARENT_POLL, keeper, "watchParent:", None, True)

    view.loadRequest_(Foundation.NSURLRequest.requestWithURL_(target))
    app.run()


def _menu(keeper):
    """메뉴 막대: Cmd+W · Cmd+Q 둘 다 이 창만 닫는다. 메뉴가 없으면 둘 다 아무 일도 안 한다."""
    import AppKit
    bar = AppKit.NSMenu.alloc().init()
    top = AppKit.NSMenuItem.alloc().init()
    bar.addItem_(top)
    menu = AppKit.NSMenu.alloc().initWithTitle_(TITLE)
    for title, key in (("창 닫기", "w"), ("액션 배틀 끝내기", "q")):
        item = menu.addItemWithTitle_action_keyEquivalent_(title, "closeWindow:", key)
        item.setTarget_(keeper)
    top.setSubmenu_(menu)
    return bar


_KEEPER = None


def _keeper_class():
    """창 · 웹뷰 · 앱의 대리인 (objc 클래스는 한 번만 만든다). AppKit 을 main 안에서만 부르려고 여기서 만든다."""
    global _KEEPER
    if _KEEPER is not None:
        return _KEEPER
    import AppKit

    class ActionViewKeeper(AppKit.NSObject):
        def applicationDidFinishLaunching_(self, _note):
            # 띄운 앱이 앞에 있다. 이 창을 앞으로 꺼내 키를 받게 한다 (거절당해도 창은 맨 앞에 보인다).
            self.win.makeKeyAndOrderFront_(None)
            self.win.orderFrontRegardless()
            self.win.makeFirstResponder_(self.view)
            AppKit.NSApp.activateIgnoringOtherApps_(True)

        def windowWillClose_(self, _note):
            AppKit.NSApp.terminate_(None)

        def closeWindow_(self, _sender):
            self.win.close()

        def webViewDidClose_(self, _view):
            self.win.close()                  # 웹 화면이 window.close() 를 불렀다 (결과의 '닫기')

        def webView_didFailProvisionalNavigation_withError_(self, view, _nav, err):
            if err is None or err.code() != CANCELLED:
                view.loadHTMLString_baseURL_(FAIL_HTML, None)

        def watchParent_(self, _timer):
            if os.getppid() != self.ppid:
                AppKit.NSApp.terminate_(None)

    _KEEPER = ActionViewKeeper
    return _KEEPER
