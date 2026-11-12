# -*- coding: utf-8 -*-
"""길드전 1:1 맞대결 화면 (시즌 7~) — 진짜 Tk 로 확인. 서버 없이 돈다.

    python3 client/test_guild_war_match_ui.py
    POKET_SKIN=dp python3 client/test_guild_war_match_ui.py
    GW1V1_SHOTS=<폴더> python3 client/test_guild_war_match_ui.py      # 맥: 전쟁 중 1:1 · 삼각형 창을 PNG 로

서버 흉내 · 창 여는 법은 test_guild_war_ui(지도전) 의 것을 그대로 쓰고, 응답은 구현 계획
(design-notes/2026-11-12-guild-war-1v1-plan.md '앱 ↔ 서버 약속') 의 꼴이다. 규칙(매칭 · 별 · 막기)은 서버 검사가 본다.
여기서는 **화면**을 본다:

  1. state 에 mode 가 없으면(옛 서버 · 시즌 6 까지) 지도전 화면 그대로 - 지도 캔버스가 나오고 /match 를 안 묻는다.
  2. 전쟁 중 1:1: 지도 자리에 맞대결 판 - [우리] 별 % · 쓰러뜨린 비율 · 남은 공격 vs [상대], 앞서는 쪽.
     상대 출전 명단 한 줄씩 (이름 · 앞 3마리 도트 · 받은 최고 별 ★☆☆ · 조커는 '???' · 내가 이미 쳤는지).
     오른쪽: 내 남은 공격(●● / ●○ / ○○) · 우리 명단(남은 공격 · 얻은 별 · 막아 낸 것) · 순위 · 보상(이긴 길드 ·
     그 밖 줄, 활약 2번) · 기록(별) · 별 규칙. /map 은 안 묻는다 (서버가 409 로 막는다).
  3. 줄을 누르면 미리보기(앞 3마리 + 가려진 수 · 받은 최고 별) + [공격] -> 서버로 target. 가려진 조커는 음수 userId
     그대로 보낸다. 관장 배틀 창을 닫으면 다시 받는다. 이미 친 상대 · 공격을 다 쓴 뒤에는 까닭이 적히고 단추가 죽는다.
  4. 삼각형: 별 판이 두 줄 - '우리가 칠 길드 [B]' · '우리를 치는 길드 [C]'.
  5. 전략 기간: 상대 발표 + 명단 (공격은 아직), 길드장은 출전 명단 고르기(상한에 맞아야 저장) · 조커 지정(꽉 차면 단추가
     죽는다). 일반 길드원에게는 그 단추가 없다.
  6. 끝: 결과(승리) · 순위의 승/패 · 보상 안내. 어디에도 글이 잘리지 않고 창 크기는 그대로, Tk 오류가 없다.
  7. 관전 카드 · 결과 줄: war.mode == 'match' 면 별로 적는다.
"""
import io
import os
import sys
import tempfile

os.environ["POKET_HOME"] = tempfile.mkdtemp(prefix="poket-gw1v1-ui-")

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.dirname(HERE))

import tkinter as tk                                        # noqa: E402

import test_guild_war_ui as GT                              # noqa: E402
from poketdesktop import platform_os as PLAT                # noqa: E402
from poketdesktop import skins                              # noqa: E402
from poketdesktop import ui_box, ui_common as U, ui_guild, ui_guild_war, ui_spectate as SP  # noqa: E402
from test_learn_dialog import squeezed, texts               # noqa: E402

TG = GT.TG
OK = FAIL = 0
SHOTS = os.environ.get("GW1V1_SHOTS")
NAMES = {1: "가람", 2: "나래", 3: "다솜", 4: "라온", 5: "마루", 6: "바다", 7: "사랑"}
STAR_RULES = ["상대 방어팀 절반 이상 쓰러뜨림", "이김", "이기고 내 팀 절반 이상 남음"]
STALE = "맞대결 판이 바뀌었습니다. 다시 불러와 주세요."


def chk(name, cond, got=""):
    global OK, FAIL
    if cond:
        OK += 1
        print("  OK   %s" % name)
    else:
        FAIL += 1
        print("  FAIL %s   %r" % (name, got))


def pm(num, kr, level=50):
    """미리보기 한 마리 (서버 tile_view 의 team 과 같은 꼴)."""
    return {"species": "X%d" % num, "num": num, "kr": kr, "level": level, "shiny": False, "tint": None}


def foes0():
    """상대 출전 명단 (로켓단). -1 = 조커로 가려진 사람의 자리 표시 (진짜 번호를 안 싣는다 - 명단 맨 끝)."""
    return [
        {"userId": 21, "name": "비주기", "joker": False, "hidden": False, "size": 6,
         "team": [pm(248, "마기라스"), pm(376, "메타그로스"), pm(373, "보만다")], "more": 3,
         "best": {"stars": 2, "ko": 6, "by": "나래"}, "tries": [{"by": "나래", "stars": 2, "ko": 6, "result": "win"}]},
        {"userId": 22, "name": "로사", "joker": False, "hidden": False, "size": 6,
         "team": [pm(445, "한카리아스"), pm(468, "토게키스"), pm(479, "로토무")], "more": 3,
         "best": {"stars": 1, "ko": 4, "by": "나래"}, "tries": [{"by": "다솜", "stars": 1, "ko": 3, "result": "lose"},
                                                             {"by": "나래", "stars": 1, "ko": 4, "result": "draw"}]},
        {"userId": 24, "name": "아주아주아주긴이름의트레이너님", "joker": False, "hidden": False, "size": 6,
         "team": [pm(94, "팬텀"), pm(448, "루카리오"), pm(149, "망나뇽")], "more": 3,
         "best": {"stars": 3, "ko": 6, "by": "다솜"}, "tries": [{"by": "다솜", "stars": 3, "ko": 6, "result": "win"}]},
        {"userId": 25, "name": "고오스", "joker": False, "hidden": False, "size": 6,
         "team": [pm(131, "라프라스"), pm(143, "잠만보"), pm(130, "갸라도스")], "more": 3, "best": None, "tries": []},
        # 가려진 조커는 명단 맨 끝에 온다 (서버 검토 11/12)
        {"userId": -1, "name": "???", "joker": True, "hidden": True, "size": 6, "team": [], "more": 6,
         "best": {"stars": 1, "ko": 3, "by": "다솜"}, "tries": [{"by": "다솜", "stars": 1, "ko": 3, "result": "lose"}]},
    ]


class MatchWar(object):
    """1:1 맞대결 시즌의 서버 흉내 (한 사람 - 가람(1)의 눈으로). 단계 · 모양은 검사가 바꾼다."""

    def __init__(self):
        self.phase = "war"
        self.kind = "pair"
        self.role = "master"
        self.members = 7
        self.entered = True
        self.entries = [{"guildId": 9, "name": "로켓단", "state": "applied"}]
        self.teams = {"def": {"fixed": True, "set": True, "mons": [GT.mon(1, "한카리아스"), GT.mon(2, "망나뇽")]},
                      "atk": {"fixed": True, "set": True, "mons": [GT.mon(1, "한카리아스"), GT.mon(2, "망나뇽")]}}
        self.team_of = {1: [2, 0], 2: [2, 1], 3: [2, 2]}       # 출전한 사람 -> [몫, 쓴 수]
        self.stars = {2: (2, 1), 3: (3, 1)}                     # 사람 -> (얻은 별, 이긴 판)
        self.bench = set()
        self.cap = None
        self.jokers = set()                                     # 우리 조커
        self.hits = set()                                       # 내가 친 상대
        self.foes = foes0()
        self.result = None
        self.battle = None
        self.calls, self.saved, self.rosters, self.joked = [], [], [], []

    # ---- state
    def my_left(self):
        a = self.team_of.get(1)
        return 0 if (a is None or 1 in self.bench) else a[0] - a[1]

    def mates(self):
        out = []
        for u, (a, used) in sorted(self.team_of.items()):
            bench = u in self.bench
            s, w = self.stars.get(u, (0, 0))
            out.append({"userId": u, "name": NAMES[u], "attacks": 0 if bench else a, "used": 0 if bench else used,
                        "bench": bench, "joker": u in self.jokers, "stars": s, "wins": w})
        return out

    def match(self):
        ph = self.phase
        target = {"guildId": 9, "name": "로켓단", "size": len(self.foes)}
        frm = {"guildId": 8, "name": "아주아주긴이름의길드", "size": 7} if self.kind == "tri" else target
        playing = [m for m in self.mates() if not m["bench"]]
        used = sum(m["used"] for m in playing)
        left = sum(m["attacks"] - m["used"] for m in playing)
        return {"kind": self.kind, "target": target, "from": frm, "cap": self.cap,
                "own": {"guildId": 1, "name": "피카단", "size": len(playing)},
                "us": {"stars": 13, "max": 3 * len(self.foes), "pct": 54.2, "ko": 61.3, "attacks": used, "left": left},
                "them": {"stars": 4, "max": 3 * len(playing), "pct": 40.0, "ko": 48.0, "attacks": 7, "left": 3},
                "lead": "even" if ph == "plan" else "us",
                "result": self.result if ph == "done" else None}

    def ranking(self):
        """from = 그 길드를 친 길드 (1:1 이면 vs 와 같다), vsPct = from 이 그 길드에게서 얻은 별 %."""
        done = self.phase == "done"
        tri = self.kind == "tri"
        rows = [{"guildId": 1, "name": "피카단", "result": "win" if done else None, "pct": 54.2, "ko": 61.3,
                 "vs": "로켓단", "from": "아주아주긴이름의길드" if tri else "로켓단", "vsPct": 40.0, "color": 1},
                {"guildId": 9, "name": "로켓단", "result": "lose" if done else None, "pct": 40.0, "ko": 48.0,
                 "vs": "아주아주긴이름의길드" if tri else "피카단", "from": "피카단", "vsPct": 54.2, "color": 0},
                {"guildId": 8, "name": "아주아주긴이름의길드", "result": "draw" if done else None, "pct": 33.3, "ko": 40.0,
                 "vs": "피카단" if tri else "솔플", "from": "로켓단" if tri else "솔플", "vsPct": 33.3, "color": 2}]
        for i, r in enumerate(rows, 1):
            r["rank"] = i
        return rows

    def state(self):
        ph = self.phase or "before"
        boss = self.role in ("master", "sub")
        st = {"season": 7, "mode": "match", "phase": ph,
              "phaseKr": {"before": "준비 중", "apply": "참가 신청", "plan": "전략", "war": "전쟁", "done": "끝"}[ph],
              "endsIn": {"before": 3600, "apply": 2 * 86400, "plan": 3 * 86400 + 120, "war": 3 * 3600 + 120,
                         "done": None}[ph],
              "applyDays": 3, "planDays": 4, "warDays": 6, "minMembers": 5, "shown": 3, "levelCap": 50,
              "each": 2, "capRatio": 1.2, "jokerMax": 3, "starRules": STAR_RULES,
              "rewards": [{"rank": 1, "coins": 300, "deco": "우승 꾸미기 묶음", "tm": 3},
                          {"rank": 2, "coins": 200, "deco": "준우승 꾸미기 묶음", "tm": 2},
                          {"rank": 3, "coins": 150, "deco": "3위 꾸미기 묶음", "tm": 1},
                          {"rank": None, "result": "win", "coins": 100, "deco": "참가 묶음 선택권", "tm": 0},
                          {"rank": None, "result": "other", "coins": 50, "deco": "참가 묶음 선택권", "tm": 0}],
              "tmActive": {"wins": 2, "count": 1}, "title": "시즌 7 길드전 우승",
              "contrib": {"win": 20, "joker": 20, "defend": 20, "max": 300, "earned": 40},
              "guild": {"id": 1, "members": self.members, "role": self.role},
              "entered": self.entered, "dropped": False,
              "can": {"apply": ph == "apply" and boss, "team": ph in ("apply", "plan"),
                      "attack": ph == "war" and self.entered and self.my_left() > 0,
                      "manage": ph == "plan" and self.entered and boss,
                      "roster": ph == "plan" and self.entered and boss and bool(self.cap)},
              "entries": list(self.entries) + ([{"guildId": 1, "name": "피카단", "state": "applied"}]
                                               if self.entered else []),
              "teams": self.teams, "match": None, "mates": [], "ranking": []}
        if ph in ("plan", "war", "done") and self.entered:
            a = self.team_of.get(1, [0, 0])
            total = 0 if 1 in self.bench else a[0]
            st["attacks"] = {"total": total, "used": a[1] if total else 0,
                             "left": self.my_left() if ph in ("plan", "war") else 0}
            st["mates"] = self.mates()
            st["match"] = self.match()
            if ph in ("war", "done"):
                st["ranking"] = self.ranking()
            if self.battle:
                st["battle"] = {"id": self.battle, "region": "u21"}
        return st

    # ---- match_view
    def why(self, f):
        if self.phase == "plan":
            return "아직 전략 기간이다 (공격은 전쟁이 시작되면)"
        if self.phase != "war":
            return "지금은 전쟁 중이 아니다"
        if self.my_left() <= 0:
            return "공격을 다 썼다"
        if f["userId"] in self.hits:
            return "이미 친 상대다 (같은 사람은 두 번 못 친다)"
        return None

    def view(self):
        m = self.match()
        foes = []
        for f in self.foes:
            why = self.why(f)
            foes.append(dict(f, mine=f["userId"] in self.hits, can=why is None, why=why))
        ours = [{"userId": 1, "name": "가람", "size": 6, "joker": 1 in self.jokers,
                 "worst": {"stars": 1, "ko": 3, "by": "비주기"}, "tries": 2, "defends": 1},
                {"userId": 2, "name": "나래", "size": 6, "joker": 2 in self.jokers, "worst": None, "tries": 0,
                 "defends": 0},
                {"userId": 3, "name": "다솜", "size": 6, "joker": 3 in self.jokers,
                 "worst": {"stars": 3, "ko": 6, "by": "로사"}, "tries": 3, "defends": 2}]
        return {"phase": self.phase, "kind": m["kind"], "target": m["target"], "from": m["from"], "own": m["own"],
                "us": m["us"],
                "them": m["them"], "lead": m["lead"], "foes": foes,
                "ours": [o for o in ours if o["userId"] in self.team_of and o["userId"] not in self.bench]}

    def log(self):
        return [{"id": 51, "ours": True, "atkName": "나래", "defName": "비주기", "atkGuild": "피카단", "defGuild": "로켓단",
                 "region": "u21", "regionName": "비주기", "result": "win", "good": True, "stars": 2, "ko": 6, "at": ""},
                {"id": 50, "ours": False, "atkName": "비주기", "defName": "가람", "atkGuild": "로켓단",
                 "defGuild": "피카단", "region": "u1", "regionName": "가람", "result": "lose", "good": True,
                 "stars": 1, "ko": 3, "at": ""},
                {"id": 49, "ours": True, "atkName": "다솜", "defName": "로사", "atkGuild": "피카단", "defGuild": "로켓단",
                 "region": "u22", "regionName": "로사", "result": "draw", "good": False, "stars": 1, "ko": 4, "at": ""}]


def fake_png(num):
    """도트 흉내. GW1V1_SHOTS 일 때(캡처)만 이 맥에 받아 둔 진짜 도트를 쓴다 (읽기만)."""
    if SHOTS:
        d = os.path.join(PLAT.data_dir("poketdesktop") or "", "sprites")
        for ext in (".gif", ".png"):
            p = os.path.join(d, "%04d%s" % (num, ext))
            if os.path.exists(p):
                with open(p, "rb") as f:
                    return f.read(), ext
    from PIL import Image, ImageDraw
    im = Image.new("RGBA", (32, 32), (0, 0, 0, 0))
    ImageDraw.Draw(im).ellipse((4, 4, 28, 28), fill=(40 + num % 200, 120, 200 - num % 150, 255))
    buf = io.BytesIO()
    im.save(buf, "PNG")
    return buf.getvalue(), ".png"


class Api(GT.Api):
    """길드전 검사의 가짜 api + 1:1 맞대결 (지도전 길은 그대로 물려받는다)."""

    def guild_war_map(self, have=None):
        w = self.s.war
        w.calls.append("map")
        if isinstance(w, MatchWar):
            self.s.fail("이번 시즌 길드전은 1:1 맞대결입니다", 409)
        return w.map(have)

    def guild_war_match(self):
        w = self.s.war
        w.calls.append("match")
        return w.view()

    def guild_war_attack(self, region=None, target=None):
        w = self.s.war
        if target is None:
            return GT.Api.guild_war_attack(self, region)
        w.calls.append("attack:t%s" % target)
        f = next((x for x in w.foes if x["userId"] == target), None)
        if f is None:                        # 낡은 자리 표시 (가려진 조커의 음수 번호가 바뀌었다)
            self.s.fail(STALE, 409)
        if w.why(f):
            self.s.fail("칠 수 없습니다: %s." % w.why(f), 409)
        w.team_of[1][1] += 1
        w.hits.add(target)
        w.battle = 80 + w.team_of[1][1]
        return {"id": w.battle, "region": "gw:7:u%s" % target, "rev": 0, "battle": {"trainer": {"name": f["name"]}},
                "events": [], "war": {"target": target, "name": f["name"], "mode": "match"}}

    def guild_war_roster(self, out):
        w = self.s.war
        w.rosters.append(list(out))
        w.bench = set(out)
        return w.state()

    def guild_war_joker(self, region=None, on=True, user_id=None):
        w = self.s.war
        if user_id is None:
            return GT.Api.guild_war_joker(self, region, on)
        w.joked.append((user_id, bool(on)))
        (w.jokers.add if on else w.jokers.discard)(user_id)
        return w.state()

    def sprite(self, num, shiny=False):
        return fake_png(num)


def images_in(w):
    """그 틀 안에서 그림이 붙은 라벨 수."""
    n = 0
    for c in w.winfo_children():
        n += images_in(c)
        if c.winfo_class() == "Label" and str(c.cget("image")):
            n += 1
    return n


def no_clip(war, top):
    bad = (squeezed(top)[:4], GT.clipped(war.inner)[:4], GT.clipped(war.board)[:4])
    return not any(bad), bad


def reload(root, war, cond, sec=6.0):
    done = []
    war.reload(after=lambda: done.append(1))
    TG.wait(root, lambda: done and cond(), sec)
    TG.settle(root, 0.25)
    return bool(done) and cond()


def click(root, widget):
    """그 위젯을 누른 것처럼 (줄에 건 <Button-1>)."""
    widget.event_generate("<Button-1>", x=2, y=2)
    TG.settle(root, 0.1)


def shoot(top, path):
    """그 창 하나만 PNG 로 (맥 · Quartz). 이 맥은 screencapture 가 막혀 있어도 자기 프로세스 창은 찍힌다.
    화면이 잠겼거나 꺼져 있으면 흰 그림만 나오므로 안 찍는다 (False - 앞서 찍은 것을 덮지 않는다)."""
    try:
        import Quartz
    except ImportError:
        return False
    d = Quartz.CGSessionCopyCurrentDictionary() or {}
    if d.get("CGSSessionScreenIsLocked") or Quartz.CGDisplayIsAsleep(Quartz.CGMainDisplayID()):
        print("  (화면이 잠겨 있거나 꺼져 있어 캡처를 건너뜁니다: %s)" % path)
        return False
    top.update()
    pid = os.getpid()
    infos = Quartz.CGWindowListCopyWindowInfo(Quartz.kCGWindowListOptionOnScreenOnly, Quartz.kCGNullWindowID) or []
    best = None
    for i in infos:
        if i.get("kCGWindowOwnerPID") != pid or i.get("kCGWindowLayer") != 0:
            continue
        b = i.get("kCGWindowBounds") or {}
        area = float(b.get("Width", 0)) * float(b.get("Height", 0))
        if best is None or area > best[0]:
            best = (area, i.get("kCGWindowNumber"))
    if best is None:
        return False
    img = Quartz.CGWindowListCreateImage(Quartz.CGRectNull, Quartz.kCGWindowListOptionIncludingWindow, best[1],
                                         Quartz.kCGWindowImageBoundsIgnoreFraming)
    if img is None:
        return False
    raw = path.encode("utf-8")
    url = Quartz.CFURLCreateFromFileSystemRepresentation(None, raw, len(raw), False)
    dest = Quartz.CGImageDestinationCreateWithURL(url, "public.png", 1, None)
    Quartz.CGImageDestinationAddImage(dest, img, None)
    return bool(Quartz.CGImageDestinationFinalize(dest))


def main():
    PLAT.before_tk()
    skins.register_fonts()
    root = tk.Tk()
    root.withdraw()
    U.init_fonts(root)
    U.apply_theme(root)
    errors = []
    root.report_callback_exception = lambda *a: errors.append(a)
    ui_guild.CHAT_MS = 150
    ui_box.confirm = lambda *a, **k: True
    ui_guild_war.POLL_MS = 400
    opened = []
    ui_guild_war.WarTab._open_battle = lambda self, data: opened.append(data)    # 관장 배틀 창 대신 적어 둔다
    print("테마 %s · 글꼴 %s / 본문 %dpt" % (skins.active(), U.FAMILY, U.FONT[1]))

    srv = TG.FakeServer()
    srv.names.update(NAMES)
    srv.g = {"name": "피카단", "intro": "", "mode": "open", "master": 1, "points": 0}
    srv.roles = {1: "master", 2: "member", 3: "member"}
    app = GT.App(root, Api(srv, 1))

    def open_window():
        w = ui_guild.GuildWindow(app)
        top = w.win.winfo_toplevel()
        top.deiconify()
        top.geometry("1000x680+60+40")
        TG.wait(root, lambda: w.data is not None and w.mode == "guild")
        return w, top, GT.open_war(root, w)

    print("=== mode 가 없으면 (옛 서버 · 시즌 6 까지) 지도전 화면 그대로 ===")
    srv.war = GT.War()
    srv.war.phase, srv.war.entered = "war", True
    w, top, war = open_window()
    TG.wait(root, lambda: war.wide and len(war.map.items) == 45)
    TG.settle(root, 0.2)
    chk("지도 캔버스가 왼쪽에 나오고 맞대결 판은 안 담긴다", war.wide and war.map.cv.winfo_ismapped()
        and not war.board.winfo_ismapped() and len(war.map.items) == 45)
    chk("  /map 을 묻고 /match 는 안 묻는다", "map" in srv.war.calls and "match" not in srv.war.calls, srv.war.calls)
    chk("  지도전 규칙 글 그대로 (원형 지도 · 칸)", any("원형 지도를 같은 모양으로" in x for x in texts(war.inner)))
    w.close()
    root.update()

    print("\n=== 1:1 전쟁 중: 맞대결 판 ===")
    srv.war = MW = MatchWar()
    w, top, war = open_window()
    TG.wait(root, lambda: war._board_on and len(war.foe_rows) == 5)
    TG.wait(root, lambda: images_in(war.foe_rows[21]) == 3, 4)
    TG.settle(root, 0.3)
    size0 = (top.winfo_width(), top.winfo_height())
    bx, tx = texts(war.board), texts(war.inner)
    chk("지도 자리에 맞대결 판 (지도 캔버스는 안 담긴다)", war.wide and war.board.winfo_ismapped()
        and not war.map.cv.winfo_ismapped() and war.board.winfo_rootx() < war.right.winfo_rootx())
    chk("  /map 은 안 묻고 /match 를 묻는다", "map" not in MW.calls and "match" in MW.calls, MW.calls)
    chk("위: [우리] 별 % · 쓰러뜨린 비율 · 남은 공격 (우리 이름 · 출전 인원은 match.own)", "우리 [피카단]" in bx
        and "출전 3명" in bx and "54.2%" in bx
        and any("별 13 / 15개 · 쓰러뜨린 비율 61.3%" in x for x in bx) and any("공격 3번 · 남은 공격 3번" in x for x in bx), bx[:14])
    chk("  vs [상대] 같은 것", "vs" in bx and "[로켓단]" in bx and "40%" in bx
        and any("쓰러뜨린 비율 48%" in x for x in bx) and any("남은 공격 3번" in x for x in bx))
    chk("  앞서는 쪽 (lead us)", "지금은 우리가 이기고 있습니다." in bx, bx)
    chk("  1:1 이라고 적힌다 (삼각형 두 줄은 없다)", "1:1 맞대결" in bx and not any("우리를 치는 길드" in x for x in bx))
    chk("아래: 상대 출전 명단 한 줄씩 (5명)", len(war.foe_rows) == 5 and any("상대 [로켓단] 의 출전 명단 5명" in x for x in bx))
    r21 = texts(war.foe_rows[21])
    chk("  줄: 이름 · 앞 3마리 도트 · +가려진 수 · 받은 최고 별 ★★☆", "비주기" in r21 and images_in(war.foe_rows[21]) == 3
        and "+3" in r21 and "★★" in r21 and "☆" in r21, r21)
    chk("  ★★★ · ☆☆☆ (아직 아무도 안 침)", "★★★" in texts(war.foe_rows[24]) and "☆☆☆" in texts(war.foe_rows[25])
        and any("아직 아무도 안 침" in x for x in texts(war.foe_rows[25])))
    rj = texts(war.foe_rows[-1])
    chk("  조커는 '???' (음수 userId 자리 표시, 도트 없음)", -1 in war.foe_rows and rj.count("???") >= 2
        and any(x.startswith("조커") for x in rj) and images_in(war.foe_rows[-1]) == 0, rj)
    chk("  가려진 조커는 명단 맨 끝 (서버 순서 그대로)", list(war.foe_rows)[-1] == -1, list(war.foe_rows))
    chk("  내가 친 상대가 없으면 '내가 이미 쳤음' 도 없다", not any("내가 이미 쳤음" in x for x in bx))
    chk("오른쪽: 내 남은 공격 ●● · 남은 공격 2번", "●●" in tx and "남은 공격 2번" in tx, tx[:8])
    mx = texts(war.mates_box)
    chk("우리 명단: 길드원마다 남은 공격 ●● / ●○ / ○○", "가람  (나)" in mx and mx.count("●●") == 1
        and "●○" in mx and "○○" in mx, mx)
    chk("  얻은 별 · 이긴 판 · 막아 낸 것 · 내준 별", any("얻은 별 3 · 이김 1판 · 막아 냄 2 / 3번 · 내준 별 ★★★" in x for x in mx)
        and any("받은 공격 없음" in x for x in mx) and any("아직 한 번도 안 친 사람 1명" in x for x in mx), mx)
    rk = texts(war.rank_box)
    chk("순위: 별 % · vs 상대 · 결과는 아직 '-'", "피카단" in rk and "54.2%" in rk and "vs [로켓단] 40%" in rk
        and "-" in rk and "아주아주긴이름의길드" in rk, rk)
    chk("보상: 1~3위 · 그 밖에 이긴 길드 · 비기거나 진 길드 · 활약 2번", any("1위: 길드 코인 300" in x for x in tx)
        and any("그 밖에 이긴 길드: 길드 코인 100 · 참가 묶음 선택권" in x for x in tx)
        and any("비기거나 진 길드: 길드 코인 50" in x for x in tx)
        and any("활약 보상: 공격 2번을 다 이기면" in x for x in tx), [x for x in tx if "코인" in x or "활약" in x])
    chk("별 규칙: ★☆☆ 절반 · ★★☆ 이김 · ★★★ 절반 남기고", all(r in tx for r in STAR_RULES)
        and any("방어자 한 명마다 가장 잘한 공격 하나만" in x for x in tx))
    chk("기록: 공격마다 별", any("나래 → [로켓단] 비주기 · ★★☆ (6마리 쓰러뜨림)" in x for x in tx)
        and any("[로켓단] 비주기 → 가람 · ★☆☆" in x for x in tx)
        and any("다솜 → [로켓단] 로사 · ★☆☆ (4마리 쓰러뜨림)" in x for x in tx) and "비김" in tx,
        [x for x in tx if "→" in x])
    chk("규칙: 1:1 맞대결 글 (지도 · 칸 말이 없다)", any("1:1 로 맞붙습니다" in x and "한 사람이 2번" in x for x in tx)
        and not any("원형 지도" in x for x in tx))
    chk("고른 상대: 처음에는 안내", any("왼쪽 명단에서 상대를 누르세요" in x for x in texts(war.foe_box)))
    ok, bad = no_clip(war, top)
    chk("글이 잘리지 않는다 (판 · 오른쪽 칸)", ok, bad)
    chk("판 안쪽이 굴러가는 틀 안에 들어 있다", GT.body_fits(war)
        and war.binner.winfo_width() <= war.bcv.winfo_width() + 2)

    print("\n=== 줄 누르기 -> 미리보기 · [공격] ===")
    war.pick_foe(22)
    TG.settle(root, 0.1)
    ft = texts(war.foe_box)
    chk("도전 기록의 비긴 판 (result draw)", any("나래 ★☆☆ · 4마리 쓰러뜨림 · 비김" in x for x in ft)
        and any("다솜 ★☆☆ · 3마리 쓰러뜨림" == x for x in ft), ft)
    click(root, war.foe_rows[21].winfo_children()[-1].winfo_children()[0])         # 줄의 이름 글자
    TG.wait(root, lambda: war.foe_sel == 21 and "attack" in war.buttons)
    TG.wait(root, lambda: images_in(war.foe_box) == 3, 3)
    TG.settle(root, 0.2)
    ft = texts(war.foe_box)
    chk("누르면 고른다 (테두리가 금색)", war.foe_sel == 21
        and str(war.foe_rows[21].cget("highlightbackground")).lower() == str(U.ACCENT).lower(),
        war.foe_rows[21].cget("highlightbackground"))
    chk("미리보기: 이름 · 앞 3마리(도트+이름) · 가려진 3마리", "비주기" in ft and "마기라스  Lv.50" in ft
        and "메타그로스  Lv.50" in ft and "보만다  Lv.50" in ft and images_in(war.foe_box) == 3
        and any("+ 가려진 3마리" in x for x in ft), ft)
    chk("  받은 최고 별과 도전 기록", "받은 최고 별" in ft and any("나래 · 6마리 쓰러뜨림" in x for x in ft)
        and any("나래 ★★☆ · 6마리 쓰러뜨림 · 이김" in x for x in ft), ft)
    chk("  [공격] 단추가 산다", war.buttons["attack"].enabled and "관장 배틀" in war.buttons["attack"].label.cget("text"))
    if SHOTS:
        os.makedirs(SHOTS, exist_ok=True)
        p = os.path.join(SHOTS, "gw1v1_war_pair.png")
        shoot(top, p) and chk("캡처: 전쟁 중 1:1 (%s)" % p, os.path.getsize(p) > 0)
    war.buttons["attack"].command()
    TG.wait(root, lambda: len(opened) == 1)
    chk("[공격] -> 서버로 target 21, 관장 배틀 창", "attack:t21" in MW.calls and opened[0]["id"] == 81
        and opened[0]["war"] == {"target": 21, "name": "비주기", "mode": "match"}, (MW.calls[-3:], opened[:1]))
    MW.battle = None
    war._battle_closed()
    TG.wait(root, lambda: "남은 공격 1번" in texts(war.inner) and war.foe_sel == 21 and war._foe(21).get("mine"))
    TG.settle(root, 0.2)
    tx = texts(war.inner)
    chk("창을 닫으면 다시 받는다: ●○ · 남은 공격 1번", "●○" in tx and "남은 공격 1번" in tx, tx[:8])
    chk("  친 상대 줄에 '내가 이미 쳤음'", "내가 이미 쳤음" in texts(war.foe_rows[21]))
    ft = texts(war.foe_box)
    chk("막힌 줄(이미 친 상대): 까닭이 적히고 단추가 죽는다", not war.buttons["attack"].enabled
        and "칠 수 없음: 이미 친 상대다 (같은 사람은 두 번 못 친다)" in ft, ft)
    war.pick_foe(-1)
    TG.settle(root, 0.15)
    ft = texts(war.foe_box)
    chk("가려진 조커를 누르면: ??? · 숨겨져 있다 · 마릿수만", war.foe_sel == -1 and "???" in ft
        and any("조커 - 이름과 방어팀이 숨겨져 있습니다" in x for x in ft)
        and any("방어팀 6마리 (싸워 봐야 압니다)" in x for x in ft) and not any("Lv.50" in x for x in ft), ft)
    chk("  앞서 고른 줄은 원래 테두리로", str(war.foe_rows[21].cget("highlightbackground")).lower()
        != str(U.ACCENT).lower())
    # 그사이 서버의 판이 바뀌어 가려진 조커의 자리 표시가 -1 -> -2 가 됐다 (앱은 아직 -1 을 들고 있다)
    MW.foes[-1] = dict(MW.foes[-1], userId=-2)
    n_match = MW.calls.count("match")
    said, real_say = [], w.say
    w.say = lambda text, color=None: (said.append(text), real_say(text, color))     # 알림 줄은 테마마다 그리는 법이 달라 말한 것을 적어 둔다
    war.buttons["attack"].command()
    TG.wait(root, lambda: MW.calls.count("match") > n_match and -2 in war.foe_rows and not war.busy)
    TG.settle(root, 0.2)
    chk("낡은 자리 표시로 공격 -> 409: 서버 글을 띄우고 맞대결 판을 다시 받는다", "attack:t-1" in MW.calls
        and len(opened) == 1 and STALE in said and -2 in war.foe_rows and -1 not in war.foe_rows,
        (MW.calls[-4:], said[-3:]))
    chk("  사라진 자리 표시는 고른 상대에서 풀린다", war.foe_sel is None
        and any("왼쪽 명단에서 상대를 누르세요" in x for x in texts(war.foe_box)))
    war.pick_foe(-2)
    TG.settle(root, 0.1)
    war.buttons["attack"].command()
    TG.wait(root, lambda: len(opened) == 2)
    chk("  조커 [공격] -> 음수 userId 그대로 target 으로", "attack:t-2" in MW.calls and opened[1]["war"]["target"] == -2,
        MW.calls[-3:])
    MW.battle = None
    war._battle_closed()
    TG.wait(root, lambda: "남은 공격 0번" in texts(war.inner))
    TG.settle(root, 0.2)
    tx = texts(war.inner)
    chk("남은 공격 0: ○○ · 다 썼다는 안내", "○○" in tx and "남은 공격 0번" in tx
        and any("공격을 다 썼습니다 (2번)" in x for x in tx), tx[:8])
    war.pick_foe(25)
    TG.settle(root, 0.15)
    chk("  아무 줄이나 눌러도 단추가 죽고 까닭이 적힌다", not war.buttons["attack"].enabled
        and "칠 수 없음: 공격을 다 썼다" in texts(war.foe_box), texts(war.foe_box))
    ok, bad = no_clip(war, top)
    chk("글이 잘리지 않는다", ok, bad)

    print("\n=== 가끔 다시 받는다 (판 · 명단만 고친다) ===")
    f25 = next(f for f in MW.foes if f["userId"] == 25)
    f25["best"] = {"stars": 2, "ko": 6, "by": "나래"}
    f25["tries"] = [{"by": "나래", "stars": 2, "ko": 6, "result": "win"}]
    inner0 = war.inner.winfo_children()[0]
    TG.wait(root, lambda: "★★" in texts(war.foe_rows[25]), 4)
    chk("남이 친 별이 판에 들어온다 (오른쪽 칸은 새로 만들지 않는다)", "★★" in texts(war.foe_rows[25])
        and war.inner.winfo_children()[0] is inner0 and war.foe_sel == 25
        and any("나래 ★★☆" in x for x in texts(war.foe_box)))

    print("\n=== 삼각형: 별 판이 두 줄 ===")
    MW.kind = "tri"
    MW.team_of[1] = [2, 0]
    MW.hits = set()
    war.foe_sel = 21
    chk("다시 받는다", reload(root, war, lambda: any("우리를 치는 길드" in x for x in texts(war.board))))
    TG.wait(root, lambda: images_in(war.foe_box) == 3, 3)
    TG.settle(root, 0.3)
    bx = texts(war.board)
    chk("'우리가 칠 길드 [B]' · '우리를 치는 길드 [C]'", "우리가 칠 길드 [로켓단] · 출전 5명" in bx
        and "우리를 치는 길드 [아주아주긴이름의길드] · 출전 7명" in bx, bx[:12])
    chk("  두 줄에 각각 별 % 와 성적 (우리 · [C])", "54.2%" in bx and "40%" in bx
        and any(x.startswith("우리 성적 · 별 13 / 15개") for x in bx)
        and any(x.startswith("[아주아주긴이름의길드] 성적 · 별 4 / 9개") for x in bx), bx[:12])
    chk("  돌아가는 순서와 견주는 법", any("우리 → [로켓단] → [아주아주긴이름의길드] → 우리" in x for x in bx)
        and any("우리가 [로켓단] 에게서 얻은 성적" in x for x in bx))
    chk("  명단은 우리가 칠 길드의 것", any("우리가 칠 길드 [로켓단] 의 출전 명단 5명" in x for x in bx))
    rk = texts(war.rank_box)
    chk("  순위 줄: 상대 % 는 우리를 친 길드(from) 와 짝지어", "친 길드 [로켓단] · 맞은 길드 [아주아주긴이름의길드] 40%" in rk
        and "친 길드 [아주아주긴이름의길드] · 맞은 길드 [피카단] 54.2%" in rk and not any(x.startswith("vs ") for x in rk), rk)
    ok, bad = no_clip(war, top)
    chk("글이 잘리지 않는다 (삼각형)", ok, bad)
    chk("창 크기는 그대로다", (top.winfo_width(), top.winfo_height()) == size0, (top.winfo_width(), top.winfo_height()))
    if SHOTS:
        p = os.path.join(SHOTS, "gw1v1_war_tri.png")
        shoot(top, p) and chk("캡처: 삼각형 (%s)" % p, os.path.getsize(p) > 0)
    MW.kind = "pair"

    print("\n=== 전략 기간: 상대 발표 · 출전 명단 고르기 · 조커 (길드장) ===")
    MW.phase = "plan"
    MW.team_of = dict((u, [2, 0]) for u in range(1, 8))
    MW.stars = {}
    MW.cap, MW.bench, MW.jokers = 6, {7}, set()
    war.foe_sel = 21
    chk("다시 받는다", reload(root, war, lambda: "roster" in war.buttons and "joker_1" in war.buttons))
    bx, tx = texts(war.board), texts(war.inner)
    chk("상대 발표 + 상대 명단 (조커 가림)", "상대가 발표됐습니다. 전쟁이 시작되면 별이 쌓입니다." in bx
        and "[로켓단]" in bx and len(war.foe_rows) == 5 and "???" in texts(war.foe_rows[-2]), bx[:10])
    chk("  출전 상한이 적힌다", any("출전 상한 6명 (작은 쪽 인원 x 1.2)" in x for x in bx))
    chk("  아직 칠 수 없다 - 까닭 · 단추 죽음", not war.buttons["attack"].enabled
        and "칠 수 없음: 아직 전략 기간이다 (공격은 전쟁이 시작되면)" in texts(war.foe_box))
    chk("내 공격: ●● 공격 2번 (전쟁이 시작되면)", "●●" in tx and "공격 2번" in tx
        and any("전쟁이 시작되면 상대 출전 명단에서 골라" in x for x in tx))
    chk("출전 명단 고르기: 상한 6 · 처음엔 서버가 뺀 사람 그대로 (6 / 6 저장 가능)", any("출전 6 / 6명" == x for x in tx)
        and war.buttons["roster"].enabled and "사랑  ·  빠짐" in tx and "가람  ·  출전" in tx, [x for x in tx if "출전" in x])
    war.buttons["roster_7"].command()
    TG.settle(root, 0.05)
    tx = texts(war.inner)
    chk("  한 명 넣으면 7 / 6 - 저장 단추가 죽고 빨갛게", not war.buttons["roster"].enabled
        and "출전 7 / 6명 - 1명을 더 빼 주세요" in tx and war.buttons["roster_7"].label.cget("text") == "빼기",
        [x for x in tx if "출전" in x])
    war.buttons["roster_3"].command()
    TG.settle(root, 0.05)
    chk("  다른 한 명을 빼면 다시 산다", war.buttons["roster"].enabled and "출전 6 / 6명" in texts(war.inner))
    war.buttons["roster"].command()
    TG.wait(root, lambda: MW.rosters and "joker_3" not in war.buttons and "roster" in war.buttons)
    TG.settle(root, 0.2)
    chk("  저장하면 뺄 사람을 서버로 (out)", MW.rosters[-1] == [3], MW.rosters)
    chk("  우리 명단에 '빠짐'", any("이번 판에는 빠짐 (인원 상한)" in x for x in texts(war.mates_box)))
    b = war.buttons["joker_1"]
    chk("조커: '조커로' 단추 · 0 / 3명", b.label.cget("text") == "조커로" and b.enabled
        and any("조커 0 / 3명" in x for x in texts(war.mates_box)))
    b.command()
    TG.wait(root, lambda: MW.joked and "joker_1" in war.buttons
            and war.buttons["joker_1"].label.cget("text") == "조커 풀기")
    TG.settle(root, 0.2)
    mx = texts(war.mates_box)
    chk("  누르면 서버로 {userId, on} · '조커 풀기' · 1 / 3명 · 조커 표시", MW.joked[-1] == (1, True)
        and any("조커 1 / 3명" in x for x in mx) and "조커" in mx, (MW.joked, mx[:6]))
    MW.jokers = {1, 2, 4}
    chk("  3명이 차면 다른 사람의 '조커로' 가 죽는다 (푸는 단추는 산다)",
        reload(root, war, lambda: "joker_5" in war.buttons and not war.buttons["joker_5"].enabled)
        and war.buttons["joker_1"].enabled and war.buttons["joker_1"].label.cget("text") == "조커 풀기")
    ok, bad = no_clip(war, top)
    chk("글이 잘리지 않는다 (전략 기간)", ok, bad)
    MW.role = "member"
    chk("일반 길드원: 출전 명단 고르기 · 조커 단추가 없다",
        reload(root, war, lambda: war.st.get("guild", {}).get("role") == "member")
        and "roster" not in war.buttons and not any(k.startswith("joker_") for k in war.buttons), list(war.buttons))
    MW.role = "master"

    print("\n=== 끝: 결과 · 순위 · 보상 ===")
    MW.phase, MW.result = "done", "win"
    MW.bench = set()
    MW.team_of = {1: [2, 2], 2: [2, 1], 3: [2, 2]}
    MW.stars = {1: (4, 2), 2: (2, 1), 3: (3, 1)}
    war.foe_sel = 21
    chk("다시 받는다", reload(root, war, lambda: war.st.get("phase") == "done" and war._board_on))
    bx, tx = texts(war.board), texts(war.inner)
    chk("결과: 승리", "승리! 우리 길드가 이겼습니다." in bx, bx)
    rk = texts(war.rank_box)
    chk("순위: 승 · 패 · 비김", "승" in rk and "패" in rk and "비김" in rk, rk)
    chk("보상 안내 · 끝났다고", any("선물함에 있습니다" in x for x in tx)
        and any("이번 시즌의 길드전이 끝났습니다" in x for x in tx))
    chk("  칠 수는 없다", not war.buttons["attack"].enabled and "칠 수 없음: 지금은 전쟁 중이 아니다" in texts(war.foe_box))
    chk("  우리 명단: 얻은 별 · 이김 (가람 4 · 2판)", any("얻은 별 4 · 이김 2판" in x for x in texts(war.mates_box)))
    ok, bad = no_clip(war, top)
    chk("글이 잘리지 않는다 (끝)", ok, bad)

    print("\n=== 신청 단계 (1:1 시즌) ===")
    MW.phase = "apply"
    chk("다시 받는다", reload(root, war, lambda: war.st.get("phase") == "apply"))
    tx = texts(war.inner)
    chk("판 없이 한 칸, 규칙은 1:1 (상대가 발표된다)", not war.wide and not war.board.winfo_ismapped()
        and any("1:1 로 맞붙습니다" in x for x in tx) and any("상대가 발표됩니다" in x for x in tx)
        and any("맞대결 판이 나타납니다" in x for x in tx), tx[:6])
    chk("  별 규칙도 보인다", all(r in tx for r in STAR_RULES))
    ok, bad = no_clip(war, top)
    chk("글이 잘리지 않는다 (신청)", ok, bad)
    w.close()
    TG.settle(root, 0.3)

    print("\n=== 관전 카드 · 결과 줄 ===")
    card = {"k": "guildwar", "s": "over", "result": "a", "a": {"id": 1, "name": "가람"}, "b": {"id": 21, "name": "비주기"},
            "war": {"mode": "match", "name": "비주기", "guild": "로켓단", "stars": 2}}
    v = SP.chat_card(card, 7, {"seeking": [], "fights": []}, 2)
    chk("끝난 1:1 공격: '★★☆' (승수 대신 별)", v["text"].endswith("·   ★★☆") and "[로켓단]" in v["text"]
        and "3승 중" not in v["text"], v["text"])
    chk("  별이 안 실린 카드는 이겼는지만", SP.war_tail({"mode": "match"}, "a") == "승리"
        and SP.war_tail({"mode": "match"}, "b") == "막혔다")
    chk("  지도전 카드는 그대로 (3승 중 1승)", SP.war_tail({"name": "로켓단 3번", "wins": 1, "need": 3}, "a")
        == "승리 (3승 중 1승)")
    going = {"seeking": [], "fights": [{"id": "w81", "card": 7, "a": {"id": 1, "name": "가람"},
                                        "b": {"id": 21, "name": "비주기"}}]}
    v = SP.chat_card(dict(card, s="fight"), 7, going, 2)
    chk("  진행 중인 1:1 공격: 이름 -> 이름 · [길드]", v["text"] == "가람  →  비주기  ·  [로켓단]" and v["act"] == "watch",
        v)
    chk("문구: 별 % · 남은 공격", ui_guild_war.pct_text(54.2) == "54.2%" and ui_guild_war.pct_text(40.0) == "40%"
        and ui_guild_war.dots(1, 2) == "●○" and ui_guild_war.dots(0, 2) == "○○" and ui_guild_war.dots(2, 2) == "●●")

    chk("Tk 콜백에서 난 오류가 없다", not errors, errors[:2])
    root.destroy()
    print("\n%d개 통과, %d개 실패" % (OK, FAIL))
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
