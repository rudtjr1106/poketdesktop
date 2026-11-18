# -*- coding: utf-8 -*-
"""액션 배틀 창 띄우기 (2.6.0).

판은 서버가 내보내는 웹 화면(/action/play)에서 한다. 앱은 입장권을 붙인 주소로 창만 띄운다.

  윈도우   Edge 앱 창 (`--app`). 새 의존성이 없다 - 예전에 웹뷰를 피한 까닭(백신 오탐 · WebView2 런타임 ·
           pythonnet)을 비켜 간다. 이 판 전용 프로필(data_dir/action-edge)이라 쓰던 Edge(로그인 · 탭)와 섞이지 않는다.
           입장권이 Edge 의 명령 줄에 보이지만 한 번 쓰고 60초면 끝나는 것이고, 페이지가 읽자마자 쓴다.
  맥       WKWebView 를 띄우는 자식 프로세스 (action_view). Tk 프로세스에 NSApplication · 웹뷰를 들이지 않는다.
           주소는 명령 줄이 아니라 stdin 한 줄로 넘긴다.
  그 밖 · 못 띄움  기본 브라우저 (webbrowser.open). 그때 Handle 은 붙잡은 프로세스가 없다 (alive() 가 늘 False).

    h = open(url)    h.alive()    h.close()
"""
import os
import subprocess
import sys
import webbrowser

from . import action_view, config

PLATFORM = sys.platform
EDGE_KEY = r"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\msedge.exe"
EDGE_IN = ("Microsoft", "Edge", "Application", "msedge.exe")      # Program Files 아래
WINDOW = (1280, 760)
EARLY_SEC = 1.5              # 띄운 것이 이 안에 오류로 끝나면 못 띄운 것으로 보고 기본 브라우저로 연다
CLOSE_WAIT = 2.0             # close() 가 프로세스가 끝나기를 기다리는 초 (넘으면 kill)
ASFW_ANY = -1                # AllowSetForegroundWindow: 어느 프로세스든


class Handle(object):
    """띄운 창 하나 (자식 프로세스). 기본 브라우저로 열었으면 proc 이 None 이다."""

    def __init__(self, proc=None):
        self.proc = proc

    def alive(self):
        return self.proc is not None and self.proc.poll() is None

    def close(self):
        """창을 닫는다 (프로세스를 끝낸다). 몇 번 불러도 되고 터지지 않는다."""
        p, self.proc = self.proc, None
        if p is None or p.poll() is not None:
            return
        try:
            p.terminate()
            p.wait(timeout=CLOSE_WAIT)
        except Exception:                                   # noqa: BLE001
            try:
                p.kill()
            except Exception:                               # noqa: BLE001
                pass


def open(url):                                              # noqa: A001 - 부르는 쪽은 action_launch.open(url)
    """액션 배틀 창을 띄운다. 못 띄우면 기본 브라우저로 연다. Handle 을 돌려준다.

    작업 스레드에서 부른다 - 띄운 것이 바로 오류로 끝나지 않는지 잠깐(EARLY_SEC) 지켜본다.
    """
    try:
        cmd, feed = command(url)
        if cmd:
            if PLATFORM == "win32":
                _allow_foreground()
            proc = _spawn(cmd, feed)
            if _started(proc):
                return Handle(proc)
            config.log("액션 배틀 창이 바로 끝났습니다 (%s). 기본 브라우저로 엽니다." % proc.returncode)
    except Exception as e:                                  # noqa: BLE001
        config.log("액션 배틀 창을 못 띄웠습니다: %s. 기본 브라우저로 엽니다." % e)
    try:
        webbrowser.open(url)
    except Exception as e:                                  # noqa: BLE001
        config.log("기본 브라우저도 못 열었습니다: %s" % e)
    return Handle()


def command(url):
    """이 컴퓨터에서 창을 띄울 (명령, stdin 으로 넘길 글). 띄울 길이 없으면 (None, None)."""
    if PLATFORM == "win32":
        edge = find_edge()
        return (edge_command(edge, url, config.data_dir()), None) if edge else (None, None)
    if PLATFORM == "darwin" and _has_webkit():
        return view_command(), url + "\n"
    return None, None


def edge_command(edge, url, data_dir):
    """Edge 앱 창 (주소 막대 · 탭 없는 창 하나)."""
    return [edge, "--app=" + url,
            "--user-data-dir=" + os.path.join(data_dir, "action-edge"),
            "--no-first-run", "--no-default-browser-check",
            "--window-size=%d,%d" % WINDOW]


def view_command():
    """맥 웹뷰 자식 프로세스. 얼린 앱이면 앱 실행 파일을, 개발 중이면 run.pyw 를 이 파이썬으로 다시 부른다."""
    if getattr(sys, "frozen", False):
        return [sys.executable, action_view.FLAG]
    return [sys.executable, os.path.join(config.CLIENT_DIR, "run.pyw"), action_view.FLAG]


def find_edge():
    """msedge.exe 의 자리. 레지스트리(App Paths) → Program Files(x86) → Program Files. 없으면 None."""
    found = _registry_edge()
    if found:
        return found
    for env in ("ProgramFiles(x86)", "ProgramFiles"):
        base = os.environ.get(env)
        path = os.path.join(base, *EDGE_IN) if base else None
        if path and os.path.isfile(path):
            return path
    return None


def _registry_edge():
    """레지스트리 App Paths 가 가리키는 msedge.exe (사용자 → 컴퓨터). 없거나 그 파일이 없으면 None."""
    try:
        import winreg
    except ImportError:
        return None
    for hive in (winreg.HKEY_CURRENT_USER, winreg.HKEY_LOCAL_MACHINE):
        try:
            with winreg.OpenKey(hive, EDGE_KEY) as key:
                path = (winreg.QueryValue(key, None) or "").strip().strip('"')
        except OSError:
            continue
        if path and os.path.isfile(path):
            return path
    return None


def _has_webkit():
    """맥 웹뷰(pyobjc-framework-WebKit)가 깔려 있나. **불러오지는 않는다** - 찾기만 한다."""
    import importlib.util
    try:
        return importlib.util.find_spec("WebKit") is not None
    except (ImportError, ValueError):
        return False


def _allow_foreground():
    """윈도우: 띄운 Edge 창이 앞으로 나올 수 있게 한다 (안 하면 작업 표시줄에서 깜박이기만 한다)."""
    try:
        import ctypes
        ctypes.windll.user32.AllowSetForegroundWindow(ASFW_ANY)
    except Exception:                                       # noqa: BLE001
        pass


def _spawn(cmd, feed=None):
    """띄운다. feed 가 있으면 stdin 에 쓰고 닫는다 (맥 자식이 주소를 한 줄 읽는다)."""
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE if feed else subprocess.DEVNULL,
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, close_fds=True)
    if feed:
        try:
            proc.stdin.write(feed.encode("utf-8"))
            proc.stdin.close()
        except OSError:
            pass                      # 벌써 끝났다 - _started 가 알아챈다
    return proc


def _started(proc):
    """바로 오류로 끝나지 않았나. Edge 는 이미 떠 있는 Edge 에 창을 넘기고 0 으로 끝나기도 한다 - 그것도 띄운 것이다."""
    try:
        return proc.wait(timeout=EARLY_SEC) == 0
    except subprocess.TimeoutExpired:
        return True
