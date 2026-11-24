# -*- coding: utf-8 -*-
"""이벤트 화면 띄우기 (설정 eventPopups, 2.5.7 - 11/24 게시판 #839 · #843 · #846 '업무 중에 이벤트 창 · 단서가 화면을 가린다')
- 화면 없이.

    python client/test_event_popups.py

  1. 기본은 켜짐 (예전과 같다) · config.events_shown
  2. 끄면 아르케 현상을 안 띄운다 - 대신 일지의 '내가 본 것' 에 적는다 (글자 · 별 · 유물 글 · 물방울 수 · 방향)
  3. 끄면 창 제목 떨림도 없다 · 일지를 저절로 안 연다 - 트레이 이름에 '봉인 풀림' · 다시 켜면 그때 연다
  4. 끈 순간 떠 있던 현상을 치운다 - 아직 '봤다' 가 안 된 것은 일지에 적고, 이미 본 것은 또 안 적는다
  5. 일지 글: 꺼 두어 적은 물방울 · 모래바람 · 흔들림은 수 · 방향까지
  6. 올림픽: 끄면 중계를 놓친 것으로 (다시 보기는 된다) · 말풍선도 없다 · 켜 두면 예전대로
  7. 설정 창 두 곳(기본 · DP 계열)에 같은 줄 · 끄면 저장하고 떠 있는 현상을 치운다
"""
import os
import sys
import tempfile
import time
import types

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
sys.path.insert(0, ROOT)
os.environ["POKET_HOME"] = tempfile.mkdtemp(prefix="poket-event-popups-")

from poketdesktop import config                             # noqa: E402

OK = FAIL = 0


def chk(name, cond, got=""):
    global OK, FAIL
    if cond:
        OK += 1
        print("  OK   %s" % name)
    else:
        FAIL += 1
        print("  FAIL %s   %r" % (name, got))


class Root(object):
    """after 는 바로 부르지 않고 모아 둔다 (시각이 된 현상은 _fire 를 직접 부른다)."""
    def __init__(self):
        self.jobs = []

    def after(self, ms, fn=None):
        self.jobs.append((ms, fn))
        return len(self.jobs)

    def after_cancel(self, j):
        pass


def app_with(on):
    a = types.SimpleNamespace(root=Root(), username="t%d" % int(time.time() * 1000), notes=[],
                              settings=dict(config.DEFAULTS, eventPopups=on), overlay=object(), airraid=None)
    a.notify = lambda text: a.notes.append(text)
    a.refresh_tray = lambda: None
    return a


PH = {
    "unown": {"id": "u1", "kind": "unown", "data": {"glyph": 7, "dir": 1}},
    "stars": {"id": "s1", "kind": "stars", "data": {"pts": [[0.5, 0.5, 1]], "band": [0, 0.2]}},
    "relic": {"id": "r1", "kind": "relic", "data": {"text": "불은 산에서 잠든다"}},
    "drip": {"id": "d1", "kind": "drip", "data": {"count": 4}},
    "sand": {"id": "a1", "kind": "sand", "data": {"dir": -1}},
    "tremor": {"id": "t1", "kind": "tremor", "data": {"dir": 1}},
}


def main():
    print("=== 이벤트 화면 띄우기 (#839 · #843 · #846)")
    chk("1. 기본은 켜짐", config.DEFAULTS.get("eventPopups") is True)
    chk("   events_shown: 설정 없음 · 켬 → True, 끔 → False",
        config.events_shown(types.SimpleNamespace()) and config.events_shown(app_with(True))
        and not config.events_shown(app_with(False)))

    from poketdesktop import arche as AR
    played = []

    def fake_play(app_, ph, on_seen):
        played.append(ph["id"])
        return types.SimpleNamespace(closed=False, cleanup=lambda: None, kind=ph.get("kind"))
    fake = types.ModuleType("poketdesktop.arche_desktop")
    fake.play = fake_play
    sys.modules["poketdesktop.arche_desktop"] = fake
    import poketdesktop
    poketdesktop.arche_desktop = fake

    app = app_with(False)
    ctl = AR.ArcheController(app)
    now = time.time()
    for ph in PH.values():
        ctl._fire(dict(ph, at=AR.datetime.datetime.fromtimestamp(now, AR.datetime.timezone.utc).isoformat(),
                       until=AR.datetime.datetime.fromtimestamp(now + 600, AR.datetime.timezone.utc).isoformat()))
    rows = {r["id"]: r for r in ctl.seen}
    chk("2. 끄면 현상을 안 띄운다", not played, played)
    chk("   여섯 가지 다 일지에 적고 다시 안 뜨게 표시", set(rows) == {p["id"] for p in PH.values()}
        and set(ctl.local["done"]) >= set(rows), (sorted(rows), ctl.local["done"]))
    chk("   글자 · 별 · 유물 글은 그대로", rows["u1"]["glyph"] == 7 and rows["s1"]["pts"] == [[0.5, 0.5, 1]]
        and rows["r1"]["text"] == "불은 산에서 잠든다", rows)
    chk("   물방울 수 · 모래바람과 흔들림 방향도 적는다 (화면으로 셌을 것)", rows["d1"]["count"] == 4
        and rows["a1"]["dir"] == -1 and rows["t1"]["dir"] == 1 and all(r.get("quiet") for r in rows.values()), rows)

    app_on = app_with(True)
    ctl_on = AR.ArcheController(app_on)
    ctl_on.blocked = lambda: None
    ctl_on._fire(dict(PH["drip"], id="d-on"))
    chk("   켜 두면 예전대로 띄운다 (조용히 적지 않는다)", played == ["d-on"]
        and not any(r.get("id") == "d-on" for r in ctl_on.seen), (played, ctl_on.seen))

    ctl.blocked = lambda: None
    ctl._react()
    chk("3. 끄면 창 제목이 맞아도 떨지 않는다", played == ["d-on"], played)
    ctl.state = {"chapter": 2, "chapters": [{"n": 2, "ritual": True, "encounters": [{"state": "ready"}]}]}
    opened = []
    ctl.open_window = lambda n=None: opened.append(n)
    ctl._rituals()
    chk("   봉인이 풀려도 일지를 저절로 안 연다 · 알림 한 줄", not opened and 2 not in ctl.local["entered"]
        and any("트레이 메뉴" in n for n in app.notes), (opened, app.notes))
    chk("   트레이 이름에 '봉인 풀림'", ctl.label() == "아르케의 일지 (제2장) · 봉인 풀림", ctl.label())
    app.settings["eventPopups"] = True
    chk("   켜면 트레이 이름은 예전대로", ctl.label() == "아르케의 일지 (제2장)", ctl.label())
    ctl._rituals()
    chk("   다시 켜면 그때 연다", opened == [2] and 2 in ctl.local["entered"], (opened, ctl.local["entered"]))
    app.settings["eventPopups"] = False

    cleaned = []
    seen_star = types.SimpleNamespace(closed=False, seen_done=False, on_seen=ctl._seen, ph=dict(PH["stars"], id="s-up"),
                                      cleanup=lambda: cleaned.append("s-up"))
    seen_drip = types.SimpleNamespace(closed=False, seen_done=True, on_seen=ctl._seen, ph=dict(PH["drip"], id="d-up"),
                                      cleanup=lambda: cleaned.append("d-up"))
    shut = types.SimpleNamespace(closed=True, seen_done=False, on_seen=ctl._seen, ph=dict(PH["unown"], id="u-shut"),
                                 cleanup=lambda: cleaned.append("u-shut"))
    ctl.shows = [seen_star, seen_drip, shut]
    ctl.hide_shows()
    ids = [r["id"] for r in ctl.seen]
    chk("4. 끈 순간 떠 있던 현상을 치운다 (이미 닫힌 것은 그대로)", cleaned == ["s-up", "d-up"], cleaned)
    chk("   아직 안 본 별은 일지에 적고, 이미 본 물방울 · 닫힌 것은 또 안 적는다",
        "s-up" in ids and "d-up" not in ids and "u-shut" not in ids, ids)

    from poketdesktop import ui_arche as UA
    chk("5. 일지 글: 물방울 수", UA.quiet_text(rows["d1"]) == "어디선가 물방울이 4번 떨어졌다. (이벤트 화면을 꺼 두어 일지에만 적었다)",
        UA.quiet_text(rows["d1"]))
    chk("   모래바람 방향", UA.quiet_text(rows["a1"]).startswith("모래바람이 바탕화면을 왼쪽으로"), UA.quiet_text(rows["a1"]))
    chk("   흔들림 방향", UA.quiet_text(rows["t1"]).startswith("포켓몬들이 무언가에 놀라 몸을 떨더니 오른쪽을"),
        UA.quiet_text(rows["t1"]))
    chk("   화면으로 본 줄은 예전 글 그대로 (수를 알려 주지 않는다)", UA.quiet_text({"kind": "drip", "count": 4}) is None)
    blocks = UA.left_blocks({"journal": []}, [rows["d1"]], 300)
    chk("   일지 쪽에 그 글이 들어간다", any("4번" in " ".join(b[1][1]) for b in blocks if b[0] == "seen"), blocks)

    from poketdesktop import olympics as OL
    oapp = app_with(False)
    oc = OL.OlympicsController(oapp)
    oc.blocked = lambda: None
    played_o = []
    oc._play = lambda heat, replay=False, ready=None, waited=0: played_o.append((heat, replay))
    bubbles = []
    import poketdesktop.visit as V
    old_bubble = V.Bubble
    V.Bubble = lambda *a, **k: bubbles.append(a)
    oc._target = lambda: object()
    try:
        oc.loaded = "d1"
        oc._due({"round": 3})
        chk("6. 끄면 중계를 안 열고 놓친 것으로 (올림픽 창에서 다시 보기)", not played_o and oc.missed == [{"round": 3}],
            (played_o, oc.missed))
        chk("   말풍선도 없다 (기록에는 남는다)", not bubbles and any("이벤트 화면을 꺼 두어" in s for s in oc.said),
            (bubbles, oc.said))
        oapp.settings["eventPopups"] = True
        oc._due({"round": 4})
        oc._tell("안내")
        chk("   켜 두면 예전대로 중계 · 말풍선", played_o == [({"round": 4}, False)] and len(bubbles) == 1,
            (played_o, bubbles))
    finally:
        V.Bubble = old_bubble
    # 다시 보기(replay=True)는 꺼 두어도 연다 - _play 안의 막힘 판정
    src = open(os.path.join(HERE, "poketdesktop", "olympics.py"), encoding="utf-8").read()
    chk("   다시 보기는 꺼 두어도 연다 (replay 면 events 로 막지 않는다)",
        'None if replay or config.events_shown(self.app) else "events"' in src)

    for rel in ("poketdesktop/ui_settings.py", "poketdesktop/skins/dp/settings.py"):
        s = open(os.path.join(HERE, rel), encoding="utf-8").read()
        chk("7. 설정 창 %s: '이벤트 화면 띄우기' · eventPopups · _toggle_events" % rel.split("/")[-2 if "skins" in rel else -1],
            "이벤트 화면 띄우기" in s and '"eventPopups"' in s and "self._toggle_events" in s)
    from poketdesktop import ui_settings as US
    w = US.SettingsWindow.__new__(US.SettingsWindow)
    sapp = app_with(True)
    hid = []
    sapp.arche = types.SimpleNamespace(hide_shows=lambda: hid.append(1))
    w.app = sapp
    saved = []
    w._save = lambda: saved.append(dict(sapp.settings))
    w._toggle_events("eventPopups", types.SimpleNamespace(get=lambda: False))
    chk("   끄면 저장하고 떠 있는 현상을 치운다", saved and saved[-1]["eventPopups"] is False and hid == [1], (saved, hid))
    w._toggle_events("eventPopups", types.SimpleNamespace(get=lambda: True))
    chk("   켜면 저장만", saved[-1]["eventPopups"] is True and hid == [1], (saved, hid))

    print("\n%d개 통과, %d개 실패" % (OK, FAIL))
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
