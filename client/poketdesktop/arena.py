# -*- coding: utf-8 -*-
"""투기장 — 서버가 계산해 둔 대전을 바탕화면에서 재생한다.

**아무것도 물어보지 않는다.** 판은 이미 서버에서 끝나 있고, 여기서는
이벤트 목록을 순서대로 그릴 뿐이다. 그래서 재생 도중 네트워크가 끊겨도,
앱을 꺼도, 두 사람이 다른 시각에 봐도 결과가 흔들리지 않는다.

진행:
    소집    내 팀이 자기 자리로 걸어 모인다
    입장    상대 팀이 화면 밖에서 한 마리씩 걸어 들어온다
    대결    앞선 둘이 링 가운데로 나와 싸운다. 쓰러지면 다음 선수가 나온다
    결과    이겼는지 졌는지
    해산    전부 원래 자리로 돌아가고, 상대는 화면 밖으로 나간다

**끝나면 반드시 원상 복귀해야 한다.** 사용자가 24시간 켜 두는 프로그램
이라, 여기서 화면을 망가뜨린 채 끝나면 재시작 말고는 푸는 방법이 없다.
그래서 cleanup() 은 몇 번을 불러도 안전하고, 중간에 무엇이 터지든
반드시 불린다.
"""
import traceback

from common import party_battle as PB

from . import arena_layout as L
from . import battle_fx as FX
from . import config
from . import fx_layer as FL
from . import platform_os as PLAT
from . import ui_common as U
from .overlay import Pet, work_area

# 단계별 시간(ms)
GATHER_MS = 1600           # 소집
ENTER_GAP = 130            # 상대가 한 마리씩 들어오는 간격
ENTER_MS = 1400            # 입장
GREET_MS = 700             # 마주 보고 인사
STEP_IN_MS = 700           # 링으로 걸어 나오기
RESULT_MS = 2000
LEAVE_MS = 1200

# 이벤트 하나당 기본 간격. 판이 길면 아래에서 줄인다.
EV_GAP = 240
HIT_GAP = 180
ROUND_GAP = 620

# 이벤트 재생을 이 시간 안에 끝내고 싶다(초). 넘치면 간격을 줄인다.
# 기술 이펙트가 도는 시간은 여기 안 들어간다 - 그것까지 더하면 실제로는
# 이보다 길어진다. 한 판이 1분을 넘으면 아무도 끝까지 안 본다.
TARGET_SECONDS = 26
MIN_SCALE = 0.35           # 아무리 길어도 이 아래로는 안 줄인다


class ArenaPet(Pet):
    """상대편 도트. overlay.pets 에 넣지 않는다.

    서버가 주는 '내 포켓몬 목록' 과 섞이면 sync 가 지워 버린다. 대신
    overlay.extra 에 넣어서 프레임만 같이 받는다.
    """

    def __init__(self, overlay, mon, anim=None):
        # Overlay.make 가 (overlay, mon, anim) 셋으로 부른다. 인자를 하나
        # 빠뜨렸더니 상대 도트가 통째로 안 만들어졌는데, 예외를 삼키고
        # 있어서 '상대가 안 나온다' 로만 보였다.
        Pet.__init__(self, overlay, mon, anim)
        self.battling = True          # 혼자 돌아다니지 않게
        self.state = "idle"
        self.down = False
        PLAT.raise_above(self.win)


# 못 움직인 이유를 머리 위에 짧게 띄운다. 원문은 문장이라 그대로 쓰면
# 도트를 다 가린다.
SKIP_TEXT = {
    "sleep": "쿨쿨...",
    "freeze": "얼었다!",
    "paralysis": "몸이 저리다!",
}


def _short(text):
    """'○○ 은(는) ...' 에서 뒷부분만. 이름은 도트를 보면 안다."""
    t = (text or "").split(" 은(는) ")[-1]
    return t[:14] if len(t) > 14 else t


class Arena(object):

    def __init__(self, app, view, on_done=None):
        self.app = app
        self.root = app.root
        self.view = view or {}
        self.plates = []          # 링 위에 적어 둔 이름표
        self.on_done = on_done
        self.closed = False
        self.jobs = []
        self.layer = None
        self.bars = {}
        self.texts = []
        self.fx = None
        self.foes = []                # ArenaPet 6마리
        self.mine = []                # 내 Pet 6마리 (이미 화면에 있는 것)
        self.home = {}                # 원래 자리 {id: (x, y)}
        self.active = {"me": None, "foe": None}
        self.slot = {"me": 0, "foe": 0}
        self.down = {"me": set(), "foe": set()}
        self.queue = []
        self.gap = EV_GAP
        self.bar_job = None

    # ---------------- 도구 ----------------
    def after(self, ms, fn):
        if self.closed:
            return None
        j = self.root.after(ms, fn)
        self.jobs.append(j)
        return j

    def _cancel_jobs(self):
        for j in self.jobs:
            try:
                self.root.after_cancel(j)
            except Exception:                               # noqa: BLE001
                pass
        self.jobs = []

    @property
    def cv(self):
        return self.layer.cv if self.layer else None

    def to_local(self, x, y):
        return self.layer.to_local(x, y) if self.layer else (x, y)

    def center(self, pet):
        sx = pet.x + pet.fw / 2.0
        sy = pet.y + pet.fh / 2.0
        return self.to_local(sx, sy)

    def find_move(self, ev):
        name = ev.get("move")
        dex = self.app.dex
        if dex and name:
            for m in (dex.moves or {}).values():
                if m.get("kr") == name:
                    return m
        return {"type": ev.get("moveType") or "NORMAL",
                "cat": ev.get("cat") or "physical", "flags": []}

    def float_over(self, pet, text, color):
        if not self.layer or not text or not pet:
            return
        self.texts.append(FL.FloatText(self.layer, pet.x + pet.fw / 2.0,
                                       pet.y - 6, text, color))

    # ---------------- 시작 ----------------
    def start(self):
        try:
            self._setup()
        except Exception as e:                              # noqa: BLE001
            config.log("투기장 준비 실패: %s\n%s" % (e, traceback.format_exc()))
            return self.cleanup()

    def _setup(self):
        ov = self.app.overlay
        if not ov:
            return self.cleanup()
        evs = list(self.view.get("events") or [])
        teams = next((e for e in evs if e.get("t") == "teams"), None)
        if not teams:
            config.log("투기장: 명단이 없는 로그다")
            return self.cleanup()

        # 화면을 빌린다. 이제부터 sync 가 도트를 재배치하지 않는다.
        ov.locked = True
        sw, sh = self.root.winfo_screenwidth(), self.root.winfo_screenheight()
        self.work = work_area(sw, sh)
        # 평소 걸어다니는 자리에서 싸운다. 화면 한가운데로 끌어오지 않는다.
        rect = L.stage_rect(ov.area(), self.work)
        self.ring = L.ring_of(rect, ov.settings["targetHeight"])
        # 클릭 통과를 못 걸면 레이어 없이 싸운다. 아래는 전부
        # self.layer 가 None 이어도 도는 길이 있다.
        self.layer = FL.open_layer(self.root, rect)

        # 내 팀 = 이미 걸어다니던 도트. 자리만 기억해 두면 복귀가 끝난다.
        self.mine = list(ov.pets.values())[:len(teams.get("me") or [])]
        for p in self.mine:
            self.home[id(p)] = (p.x, p.y)
            p.battling = True
        self.roster = {"me": teams.get("me") or [], "foe": teams.get("foe") or []}

        try:
            self._name_plates()
        except Exception as e:                              # noqa: BLE001
            config.log("투기장 이름표를 못 그렸습니다: %s" % e)
        self.queue = [e for e in evs if e.get("t") != "teams"]
        self._pace()
        self.bar_job = None
        self._tick_bars()
        self._gather()

    def _name_plates(self):
        """누구와 싸우는지 링 위에 적어 둔다.

        예전에는 끝난 뒤 알림에만 상대 이름이 떴다. 재생은 30초쯤 가는데
        그동안 누구랑 싸우는지 알 수가 없었다.

        투기장은 오른쪽 아래 활동 영역 안에서 벌어지고, 내 팀이 왼쪽·상대가
        오른쪽에 선다. 이름도 각자 자기 쪽 위에 둔다.
        """
        # 로그인 전이거나 시험용 앱이면 username 이 아예 없을 수 있다.
        # 이름표 때문에 재생 전체가 접히면 안 된다.
        # 내 이름은 안 적는다. 내가 누군지는 이미 알고 있다.
        foe = (self.view.get("foe") or {}).get("name") or "상대"
        _x1, _y1, x2, y2 = self.ring["rect"]
        self._plate(x2 - 10, y2 - 10, foe, "#ffb0b0", anchor="se")

    def _plate(self, sx, sy, text, color, anchor="center"):
        cv = self.cv
        if cv is None:
            return
        x, y = self.to_local(sx, sy)
        # 글자만 그리면 도트와 겹쳐 안 보인다. 뒤에 판을 깔고 그 위에 쓴다.
        t = cv.create_text(x, y, text=text, fill=color, anchor=anchor,
                           font=(U.FAMILY, 10, "bold"))
        bx = cv.bbox(t)
        if bx:
            pad = 6
            r = cv.create_rectangle(bx[0] - pad, bx[1] - 3, bx[2] + pad,
                                    bx[3] + 3, fill="#11141c", outline="#2a3040")
            cv.tag_lower(r, t)
            self.plates.extend([r, t])
        else:
            self.plates.append(t)

    def _pace(self):
        """판이 길면 간격을 줄인다. 짧으면 그대로 둔다.

        6:6 은 열 턴에 끝나기도 하고 백 턴을 가기도 한다. 같은 간격으로
        틀면 긴 판은 몇 분씩 걸려서 아무도 끝까지 안 본다.
        """
        n = max(1, len(self.queue))
        want = TARGET_SECONDS * 1000.0
        raw = n * EV_GAP
        self.scale = max(MIN_SCALE, min(1.0, want / raw)) if raw > want else 1.0
        self.gap = max(60, int(EV_GAP * self.scale))

    # ---------------- 소집 ----------------
    def _gather(self):
        n = len(self.mine)
        for i, p in enumerate(self.mine):
            sx, sy = L.seat_point(self.ring, "me", i, max(1, n))
            self._walk(p, sx, sy, GATHER_MS)
        self.after(GATHER_MS + 120, self._enter_foes)

    def _enter_foes(self):
        ov = self.app.overlay
        if self.closed or not ov:
            return
        team = self.roster["foe"]
        n = max(1, len(team))

        def one(i):
            if self.closed or i >= len(team):
                return self.after(ENTER_MS, self._greet)
            mon = team[i]
            try:
                # Pet 은 이름표와 툴팁을 mon["info"] 에서 읽는다.
                # id 는 음수로 둔다 - 서버가 준 내 포켓몬과 절대 안 겹친다.
                pet = ov.make({
                    "id": -1000 - i,
                    "num": mon.get("num"),
                    "shiny": bool(mon.get("shiny")),
                    "info": {"name": mon.get("name"),
                             "species": mon.get("species"),
                             "level": mon.get("level"),
                             "types": []},
                }, cls=ArenaPet)
            except Exception as e:                          # noqa: BLE001
                config.log("상대 도트 실패: %s / %s"
                           % (e, traceback.format_exc()))
                pet = None
            if pet is not None:
                ov.extra.append(pet)
                self.foes.append(pet)
                ex, ey = L.entry_point(self.ring, "foe", i, n)
                pet.x, pet.y = L.feet_to_topleft(ex, ey, pet.fw, pet.fh)
                pet.place()
                sx, sy = L.seat_point(self.ring, "foe", i, n)
                self._walk(pet, sx, sy, ENTER_MS)
            # 한 마리씩 만든다. 여섯을 한꺼번에 만들면 도트를 읽고 크기를
            # 바꾸느라 화면이 반 초쯤 얼어붙는데, 나눠 담으면 그 멈춤이
            # '한 마리씩 등장' 연출이 된다.
            self.after(ENTER_GAP, lambda: one(i + 1))
        one(0)

    def _greet(self):
        for p in self.mine:
            p.face_towards(self.ring["cx"] + 999)
        for p in self.foes:
            p.face_towards(self.ring["cx"] - 999)
        self.after(GREET_MS, self._next_round)

    # ---------------- 걷기 ----------------
    def _walk(self, pet, sx, sy, ms, done=None):
        """발밑 (sx, sy) 로 걸어간다.

        좌표를 옮기면서 걸은 거리를 같이 쌓아 준다. 도트는 시간이 아니라
        **걸은 거리**로 발을 바꾸기 때문에(overlay.Pet.advance), 이걸 안
        쌓으면 미끄러지듯 이동한다.
        """
        tx, ty = L.feet_to_topleft(sx, sy, pet.fw, pet.fh)
        x0, y0 = pet.x, pet.y
        steps = max(1, int(ms / 33))
        pet.state = "walk"

        def go(i):
            if self.closed:
                return
            k = min(1.0, i / float(steps))
            nx = x0 + (tx - x0) * k
            ny = y0 + (ty - y0) * k
            pet.walked += abs(nx - pet.x) + abs(ny - pet.y)
            if i == 1 or (i % 4 == 0 and k < 1.0):
                pet.turn_to(tx - pet.x, ty - pet.y)
            pet.x, pet.y = nx, ny
            pet.place()
            if k >= 1.0:
                pet.state = "idle"
                return done() if done else None
            self.after(33, lambda: go(i + 1))
        go(1)

    # ---------------- 라운드 ----------------
    def _seat_of(self, side, i):
        team = self.roster[side]
        return L.seat_point(self.ring, side, i, max(1, len(team)))

    def _pet_at(self, side, i):
        arr = self.mine if side == "me" else self.foes
        return arr[i] if 0 <= i < len(arr) else None

    def _next_round(self):
        """다음 round 이벤트까지 재생한다."""
        self._play()

    def _step_in(self, side, i, done):
        """반원에서 링 가운데로 걸어 나온다."""
        pet = self._pet_at(side, i)
        if pet is None:
            return done()
        mine_pt, foe_pt = L.duel_points(self.ring)
        sx, sy = mine_pt if side == "me" else foe_pt
        self.active[side] = pet
        self.slot[side] = i
        self._walk(pet, sx, sy, STEP_IN_MS,
                   lambda: (pet.face_towards(self.ring["cx"] + (
                       999 if side == "me" else -999)), done()))

    def _step_out(self, side):
        """링에 서 있던 애를 자기 자리로 돌려보낸다."""
        pet = self.active.get(side)
        if pet is None or getattr(pet, "down", False):
            return
        sx, sy = self._seat_of(side, self.slot[side])
        self._walk(pet, sx, sy, STEP_IN_MS)

    # ---------------- 재생 ----------------
    def _play(self):
        if self.closed:
            return
        if not self.queue:
            return self._finish()
        ev = self.queue.pop(0)
        try:
            self._render(ev, lambda: self.after(self.gap, self._play))
        except Exception as e:                              # noqa: BLE001
            config.log("투기장 재생 오류(%s): %s" % (ev.get("t"), e))
            self.after(self.gap, self._play)

    def _tick_bars(self):
        """체력바를 도트 위에 따라다니게 그린다.

        만들고 값만 넣어서는 화면에 아무것도 안 나온다 - HpBar 는
        draw() 를 불러야 그려진다. 싸우는 둘이 링 안에서 움직이므로
        매 프레임 자리를 다시 잡아야 누구 체력인지 헷갈리지 않는다.
        """
        if self.closed or not self.layer:
            return
        # 포켓몬 창도 '항상 위' 라 그냥 두면 체력바가 그 뒤로 숨는다.
        # 자주 올릴 필요는 없어서 몇 프레임에 한 번만 올린다.
        self._bar_n = getattr(self, "_bar_n", 0) + 1
        if self._bar_n % 15 == 1:
            try:
                self.layer.raise_above()
            except Exception:                               # noqa: BLE001
                pass
        for side in ("me", "foe"):
            bar = self.bars.get(side)
            pet = self.active.get(side)
            if bar is None:
                continue
            if pet is None or getattr(pet, "down", False):
                bar.clear()
                continue
            bar.ease()
            try:
                bar.draw(int(pet.x) + pet.fw // 2, int(pet.y))
            except Exception:                               # noqa: BLE001
                pass
        self.bar_job = self.root.after(33, self._tick_bars)

    def _bar_for(self, side):
        b = self.bars.get(side)
        if b is None and self.layer:
            b = FL.HpBar(self.layer, lift=18 if side == "foe" else 0)
            self.bars[side] = b
        return b

    def _apply_hp(self, ev):
        if "hp" not in ev:
            return
        side = ev.get("target") if ev.get("t") == "hit" else ev.get("who")
        if side in ("me", "foe"):
            bar = self._bar_for(side)
            if bar:
                bar.set(ev["hp"], ev.get("maxhp") or 1)

    def _render(self, ev, done):
        t = ev.get("t")
        who = ev.get("who")
        self._apply_hp(ev)

        if t == "round":
            return self._on_round(ev, done)
        if t == "ko":
            return self._on_ko(ev, done)
        if t == "match":
            self.result_ev = ev
            return done()

        src = self.active.get(who)
        dst = self.active.get("foe" if who == "me" else "me")
        if t == "move" and src and dst and self.layer:
            move = self.find_move(ev)
            self.fx = FX.Effect(self, move, self.center(src), self.center(dst),
                                lambda: self.after(int(140 * self.scale), done),
                                who=who)
            return self.fx.play()
        if t == "hit":
            side = self.active.get(ev.get("target"))
            if side:
                if ev.get("crit"):
                    self.float_over(side, "급소!", "#ffd447")
                eff = ev.get("eff", 1)
                if eff and eff > 1:
                    self.float_over(side, "효과가 굉장하다!", "#7bffa0")
                elif eff and eff < 1:
                    self.float_over(side, "효과가 별로...", "#b0b0c0")
                return self._shake(side, done)
        if t == "ailment" and src:
            self.float_over(src, (ev.get("text") or "").split(" 은(는) ")[-1]
                            .replace(" 상태가 되었다!", ""), "#ff9d55")
        if t in ("chip", "recoil") and src:
            self.float_over(src, "-%d" % (ev.get("damage")
                                          or ev.get("amount") or 0), "#ff8a8a")
        if t == "heal" and src:
            self.float_over(src, "+%d" % (ev.get("amount") or 0), "#7bffa0")
        # **못 움직인 턴을 보여준다.** 예전에는 이 셋을 그리지 않아서,
        # 잠들거나 마비돼서 한 턴을 쉬면 화면에는 아무것도 안 뜨고
        # 상대만 연달아 때리는 것처럼 보였다.
        if t in ("status", "msg") and src:
            self.float_over(src, SKIP_TEXT.get(ev.get("status"))
                            or _short(ev.get("text")), "#c9a0ff")
        if t == "cure" and src:
            self.float_over(src, _short(ev.get("text")), "#7bffa0")
        if t == "immune":
            side = self.active.get(who)
            if side:
                self.float_over(side, "효과가 없다...", "#9a9ab0")
        if t == "faint":
            side = self.active.get(who)
            if side:
                return self._faint(side, done)
        return self.after(max(60, int(self.gap * 0.7)), done)

    def _on_round(self, ev, done):
        """새 선수가 링으로 나온다. 이미 서 있는 쪽은 그대로 둔다(연전)."""
        for side in ("me", "foe"):
            bar = self._bar_for(side)
            info = ev.get(side) or {}
            if bar:
                bar.set(info.get("hp", 1), info.get("maxhp", 1))
                bar.shown = bar.ratio
        need = []
        for side in ("me", "foe"):
            cur = self.active.get(side)
            # **서버가 알려준 자리를 그대로 쓴다.** 예전에는 화면이
            # "쓰러지지 않은 첫 자리" 로 스스로 계산했는데, 서버가 상성을
            # 보고 순서를 바꿔 내보내면 다른 포켓몬이 나왔다. 오류도 안 났다.
            want = ev.get("mi" if side == "me" else "fi")
            if want is None:                    # 옛 로그에는 번호가 없다
                want = self._next_slot(side)
            elif not (0 <= want < len(self.roster[side])):
                want = self._next_slot(side)
            if want is None:
                continue
            # 이미 그 자리가 링에 서 있으면 그대로 둔다(연전).
            if cur is not None and not getattr(cur, "down", False)                     and self._pet_at(side, want) is cur:
                continue
            if cur is None or getattr(cur, "down", False)                     or self._pet_at(side, want) is not cur:
                need.append((side, want))
        if not need:
            return done()
        left = [len(need)]

        def one():
            left[0] -= 1
            if left[0] <= 0:
                self.after(int(GREET_MS * 0.6), done)
        for side, i in need:
            # 살아 있는데 바뀌는 경우(상성 교체)에는 먼저 자기 자리로
            # 물러난다. 쓰러졌으면 _step_out 이 알아서 아무것도 안 한다.
            self._step_out(side)
            self._step_in(side, i, one)

    def _next_slot(self, side):
        for i in range(len(self.roster[side])):
            if i not in self.down[side]:
                return i
        return None

    def _on_ko(self, ev, done):
        sides = ("me", "foe") if ev.get("side") == "both" else (ev.get("side"),)
        for side in sides:
            if side in ("me", "foe"):
                self.down[side].add(self.slot[side])
                self.active[side] = None
        return self.after(int(ROUND_GAP * self.scale), done)

    # ---------------- 작은 연출 ----------------
    def _shake(self, pet, done):
        hx = pet.x
        seq = [-7, 7, -5, 5, -3, 3, 0]

        def go(i):
            if self.closed:
                return
            if i >= len(seq):
                pet.x = hx
                pet.place()
                return done()
            pet.x = hx + seq[i]
            pet.place()
            self.after(max(14, int(30 * self.scale)), lambda: go(i + 1))
        go(0)

    def _faint(self, pet, done):
        hy = pet.y

        def go(i):
            if self.closed:
                return
            if i > 10:
                pet.down = True
                try:
                    pet.win.withdraw()
                    if getattr(pet, "name_win", None):
                        pet.name_win.withdraw()
                except Exception:                           # noqa: BLE001
                    pass
                pet.y = hy
                return done()
            pet.y = hy + i * 4
            pet.place()
            self.after(28, lambda: go(i + 1))
        go(0)

    def lunge(self, who, done):
        """battle_fx 가 접촉기에서 부른다.

        desktop_battle 의 것을 베끼면 안 된다. 저쪽은 self.mine / self.foe
        를 직접 보는데, 여기서는 링에 서 있는 둘이 라운드마다 바뀐다.
        """
        pet = self.active.get(who)
        other = self.active.get("foe" if who == "me" else "me")
        if not pet or not other:
            return done()
        hx, hy = pet.x, pet.y
        dx = 26 if other.x > pet.x else -26
        n = 5

        def go(i):
            if self.closed:
                return
            if i > n * 2:
                pet.x, pet.y = hx, hy
                pet.place()
                return self.after(60, done)
            k = i if i <= n else n * 2 - i
            pet.x = hx + dx * k / float(n)
            pet.place()
            self.after(22, lambda: go(i + 1))
        go(1)

    # ---------------- 끝 ----------------
    def _finish(self):
        if self.closed:
            return
        res = self.view.get("result")
        msg = {"win": "이겼습니다!", "lose": "졌습니다...",
               "draw": "비겼습니다."}.get(res, "대전이 끝났습니다.")
        foe = (self.view.get("foe") or {}).get("name") or "상대"
        bits = []
        if self.view.get("reward"):
            bits.append("%s원" % format(self.view["reward"], ","))
        self.app.notify("%s 와(과)의 대전 — %s%s"
                        % (foe, msg, ("  (" + " · ".join(bits) + ")")
                           if bits else ""))
        center = self.active.get("me") or (self.mine[0] if self.mine else None)
        if center:
            self.float_over(center, msg,
                            "#7bffa0" if res == "win" else "#ff8a8a")
        self.after(RESULT_MS, self._leave)

    def _leave(self):
        """상대는 화면 밖으로, 내 팀은 원래 자리로."""
        if self.closed:
            return
        n = max(1, len(self.foes))
        for i, p in enumerate(self.foes):
            if getattr(p, "down", False):
                continue
            ex, ey = L.entry_point(self.ring, "foe", i, n)
            self._walk(p, ex, ey, LEAVE_MS)
        for p in self.mine:
            hx, hy = self.home.get(id(p), (p.x, p.y))
            self._walk(p, hx + p.fw / 2.0, hy + p.fh, LEAVE_MS)
        self.after(LEAVE_MS + 120, self.cleanup)

    def cleanup(self):
        """원상 복귀. **몇 번을 불러도 안전해야 한다.**

        로그아웃·종료·세션만료·재생 중 예외 — 끝나는 길이 여럿이라
        그 전부가 여기로 온다. 하나라도 빠지면 바탕화면이 잠긴 채로 남고,
        사용자는 재시작 말고는 푸는 방법이 없다.
        """
        if self.closed:
            return
        self.closed = True
        if getattr(self, "bar_job", None):
            try:
                self.root.after_cancel(self.bar_job)
            except Exception:                               # noqa: BLE001
                pass
            self.bar_job = None
        self._cancel_jobs()

        ov = self.app.overlay
        for p in list(self.foes):
            try:
                if ov and p in ov.extra:
                    ov.extra.remove(p)
                p.destroy()
            except Exception:                               # noqa: BLE001
                pass
        self.foes = []

        for p in self.mine:
            try:
                p.battling = False
                p.state = "idle"
                p.down = False
                hx, hy = self.home.get(id(p), (p.x, p.y))
                p.x, p.y = hx, hy
                PLAT.show_again(p.win)
                if getattr(p, "name_win", None) and ov and not ov.hidden:
                    if ov.settings.get("showNames"):
                        PLAT.show_again(p.name_win)
                p.place()
            except Exception:                               # noqa: BLE001
                pass
        self.mine = []

        for b in self.bars.values():
            try:
                b.clear()
            except Exception:                               # noqa: BLE001
                pass
        self.bars = {}
        for t in self.texts:
            try:
                t.destroy()
            except Exception:                               # noqa: BLE001
                pass
        self.texts = []
        if self.layer:
            try:
                self.layer.destroy()
            except Exception:                               # noqa: BLE001
                pass
            self.layer = None
        if ov:
            ov.locked = False
        if self.on_done:
            try:
                self.on_done()
            except Exception:                               # noqa: BLE001
                pass


def flip_for_viewer(view):
    """서버가 a 시점으로 준 로그를 b 가 볼 때 뒤집는다.

    서버가 이미 뒤집어서 주므로 보통은 쓸 일이 없다. 저장해 둔 로그를
    파일에서 읽어 재생해 볼 때(스모크 테스트) 쓴다.
    """
    out = dict(view)
    out["events"] = PB.flip_log(view.get("events") or [])
    return out
