# -*- coding: utf-8 -*-
"""아르케 (2.4.0) 브라우저 창 제목 감시 검사 — 맨 앞 창 제목 하나만 · 맞을 때만 알림 · 같은 제목은 한 번.

    python client/test_arche_title.py

진짜 창 제목은 읽지 않는다 - 가짜 제목 함수(read=)를 넘긴다. 열쇠 · 소금은 이 검사가 지어낸 값이다
(진짜 답은 저장소 밖 비공개 답안지에만 있다). Tk 도 띄우지 않는다 - after 를 흉내 내는 가짜 root 로 돈다.
"""
import hashlib
import os
import sys
import tempfile

os.environ.setdefault("POKET_HOME", tempfile.mkdtemp(prefix="poket-test-arche-title-"))

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
sys.path.insert(0, ROOT)

from poketdesktop import arche_title as AT                  # noqa: E402
from poketdesktop import platform_os as PLAT                # noqa: E402

OK = FAIL = 0
SALT = "test-salt-1234"
WORD = "푸른 사과 열두 개"          # 지어낸 말 (수수께끼와 상관없다)


def chk(name, cond, got=""):
    global OK, FAIL
    if cond:
        OK += 1
        print("  OK   %s" % name)
    else:
        FAIL += 1
        print("  FAIL %s   %r" % (name, got))


def H(text):
    """common/arche.key_hash 로 만든 열쇠 해시 (늦게 불러온다 - 다른 사람이 같이 만드는 파일)."""
    from common import arche as CA
    return CA.key_hash(SALT, text)


class FakeRoot(object):
    """root.after 흉내. run() 이 예약된 것을 하나씩 돌린다."""

    def __init__(self):
        self.jobs = {}
        self.n = 0
        self.waits = []

    def after(self, ms, fn):
        self.n += 1
        key = "after#%d" % self.n
        self.jobs[key] = fn
        self.waits.append(ms)
        return key

    def after_cancel(self, key):
        self.jobs.pop(key, None)

    def run(self, times=1):
        for _ in range(times):
            if not self.jobs:
                return
            key = sorted(self.jobs, key=lambda k: int(k.split("#")[1]))[0]
            self.jobs.pop(key)()


class Titles(object):
    """가짜 맨 앞 창 제목. 몇 번 읽혔는지 센다."""

    def __init__(self, title=None):
        self.title = title
        self.reads = 0

    def __call__(self):
        self.reads += 1
        return self.title


def part_platform():
    print("=== 플랫폼 ===")
    t = PLAT.foreground_title()
    if sys.platform == "win32":
        chk("윈도우: 맨 앞 창 제목은 글자 또는 None", t is None or isinstance(t, str), t)
    else:
        chk("윈도우가 아니면 제목을 읽지 않는다 (None)", t is None, t)
    from poketdesktop import platform_base
    chk("기본 구현은 None", platform_base.foreground_title() is None)


def part_watch():
    print("=== 제목 감시 ===")
    root = FakeRoot()
    hits = []
    tt = Titles("%s - Google Chrome" % WORD)
    state = {"hashes": [H(WORD)], "on": True}
    w = AT.TitleWatch(root, lambda: (SALT, state["hashes"]), hits.append, every_ms=3000,
                      read=tt, enabled=lambda: state["on"])
    w.start()
    chk("시작하면 3초 뒤로 예약", root.waits and root.waits[-1] == 3000, root.waits)
    root.run()
    chk("브라우저 꼬리를 떼고 맞으면 on_hit 한 번 (맞은 말을 넘긴다)", hits == [WORD], hits)
    chk("  돌면 다음 3초를 또 예약", len(root.jobs) == 1 and root.waits[-1] == 3000, root.waits)
    root.run(4)
    chk("같은 제목이 계속이면 다시 안 부른다", hits == [WORD], hits)
    tt.title = "아무 상관 없는 문서 - Microsoft Edge"
    root.run()
    chk("안 맞는 제목은 on_hit 을 안 부른다", hits == [WORD], hits)
    chk("  안 맞는 제목은 감시가 들고 있지 않다 (글자 그대로 남기지 않음)",
        tt.title not in repr(vars(w)), [k for k, v in vars(w).items() if v == tt.title])
    tt.title = "%s - Google Chrome" % WORD
    root.run()
    chk("제목이 바뀌었다가 돌아오면 다시 한 번", hits == [WORD, WORD], hits)
    tt.title = "  %s!!  " % WORD.replace(" ", "   ")
    root.run()
    chk("공백 · 문장부호 차이는 같은 말로 (정규화)", len(hits) == 3, hits)
    tt.title = "%s - 지어낸 백과사전 - Whale" % WORD
    root.run()
    chk("사이트 이름이 붙은 제목도 조각마다 본다 (' - ' 로 나눈 앞 조각)", len(hits) == 4 and hits[-1].strip() == WORD,
        hits)
    # hashes 가 비면 읽지도 않는다
    state["hashes"] = []
    tt.title = "또 다른 제목"
    r0 = tt.reads
    root.run(3)
    chk("열쇠 해시가 비면 제목을 읽지도 않는다", tt.reads == r0, (tt.reads, r0))
    chk("  그래도 감시는 이어진다 (다음 장 · 다음 폴링을 위해)", len(root.jobs) == 1)
    # 설정 꺼짐이면 안 읽는다
    state["hashes"] = [H(WORD)]
    state["on"] = False
    tt.title = WORD
    r0 = tt.reads
    root.run(3)
    chk("설정 '브라우저 단서 찾기' 가 꺼져 있으면 읽지 않는다", tt.reads == r0 and len(hits) == 4, (tt.reads, hits))
    state["on"] = True
    root.run()
    chk("  다시 켜면 읽는다", tt.reads == r0 + 1 and len(hits) == 5, (tt.reads, hits))
    # 제목을 못 읽음 (None) · 예외
    tt.title = None
    root.run()
    chk("제목이 없으면(None) 조용히 넘어간다", len(hits) == 5)

    def boom():
        raise OSError("user32 없음")
    w2 = AT.TitleWatch(root, lambda: (SALT, [H(WORD)]), hits.append, read=boom)
    w2.tick()
    chk("제목 읽기가 터져도 감시는 죽지 않는다", len(hits) == 5)
    bad = AT.TitleWatch(root, lambda: 1 / 0, hits.append, read=tt)
    bad.tick()
    chk("해시 받기가 터져도 죽지 않는다", len(hits) == 5)
    # on_hit 이 터져도 다음 틱은 돈다
    tt.title = WORD + " - Google Chrome"
    w3root = FakeRoot()
    w3 = AT.TitleWatch(w3root, lambda: (SALT, [H(WORD)]), lambda s: 1 / 0, read=tt)
    w3.start()
    w3root.run()
    chk("on_hit 이 터져도 다음 틱을 예약한다", len(w3root.jobs) == 1)
    w3.stop()
    # on_hit 안에서 stop (의식을 마쳐 컨트롤러가 감시를 끈다) - 다시 예약하지 않는다
    sroot = FakeRoot()
    holder = []
    ws = AT.TitleWatch(sroot, lambda: (SALT, [H(WORD)]), lambda s: holder[0].stop(), read=tt)
    holder.append(ws)
    ws.start()
    sroot.run()
    chk("on_hit 안에서 stop 하면 다시 예약하지 않는다", not sroot.jobs and not ws.running(), sroot.jobs)
    # stop
    w.stop()
    chk("stop: 예약을 지운다", not root.jobs or all(k not in root.jobs for k in [w.job]) and w.job is None, root.jobs)
    w.stop()
    chk("  두 번 불러도 안전", w.job is None)
    w.start()
    w.start()
    chk("start 를 두 번 불러도 예약은 하나", len(root.jobs) == 1, root.jobs)
    w.stop()


def part_salt():
    print("=== 소금 ===")
    root = FakeRoot()
    hits = []
    tt = Titles(WORD)
    w = AT.TitleWatch(root, lambda: ("other-salt", [H(WORD)]), hits.append, read=tt)
    w.tick()
    chk("소금이 다르면 같은 말이어도 안 맞는다", hits == [], hits)
    w2 = AT.TitleWatch(root, lambda: None, hits.append, read=tt)
    w2.tick()
    chk("get_hashes 가 None 이어도 괜찮다 (읽지 않는다)", hits == [] and tt.reads == 1, tt.reads)
    chk("지난 제목은 글자가 아니라 지문으로만 들고 있다",
        isinstance(w._last, (bytes, str, type(None))) and w._last != WORD
        and w._last == hashlib.sha256(WORD.encode("utf-8")).hexdigest(), w._last)


def part_chapters():
    """컨트롤러(arche.py)가 쓰는 꼴: 열린 장마다 (장 번호, 소금, 해시들) 목록 -> on_hit(장 번호, 말)."""
    print("=== 장마다 ===")
    from common import arche as CA
    root = FakeRoot()
    hits = []
    other = "초록 바나나 세 송이"
    groups = [(2, "salt-two", {CA.key_hash("salt-two", other)}), (1, SALT, {H(WORD)})]
    tt = Titles("%s - Google Chrome" % WORD)
    w = AT.TitleWatch(root, lambda: groups, lambda n, s: hits.append((n, s)), read=tt)
    w.tick()
    chk("목록 꼴: 맞은 장 번호와 말을 넘긴다", hits == [(1, WORD)], hits)
    tt.title = other + " - Microsoft Edge"
    w.tick()
    chk("  장마다 제 소금으로 견준다", hits[-1] == (2, other), hits)
    tt.title = "어느 장에도 없는 말"
    w.tick()
    chk("  안 맞으면 안 부른다", len(hits) == 2, hits)
    r0 = tt.reads
    w2 = AT.TitleWatch(root, lambda: [], hits.append, read=tt)
    w2.tick()
    chk("  빈 목록이면 읽지도 않는다", tt.reads == r0)


def main():
    part_platform()
    part_watch()
    part_salt()
    part_chapters()
    print("\n%d개 통과, %d개 실패" % (OK, FAIL))
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
