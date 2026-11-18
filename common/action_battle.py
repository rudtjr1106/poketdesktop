# -*- coding: utf-8 -*-
"""액션 배틀 판 (2.6.0) — 키보드로 움직여 피하고 때리는 실시간 대전 (3 대 3, 유저 vs 유저).

순수 파이썬. 서버(server/app/action_ws.py)가 방마다 30번/초 step() 을 부르고, 사람마다 snapshot(side) 에
drain_events() 를 붙여 보낸다. 판정은 전부 여기서 한다 - 웹 화면은 누른 키만 보낸다.

    ab = ActionBattle(dex, team_a, team_b, seed, names=("가", "나"))
    ab.pick("a", [0, 2, 3])                  # 고르기 (pick 단계)
    ab.set_move("a", 1.0, 0.0, seq)          # 이동 의도 (-1~1)
    ab.press("a", "m0", seq)                 # m0~m3 기술 · sw0~sw2 교체 (바쁘면 BUFFER_SEC 들고 있다)
    ab.step() ; ab.drain_events() ; ab.snapshot("a") ; ab.intro("a")

본가에서 그대로 가져오는 것: 능력치 (성격 · 개체값 · 노력치 · 도구 배율 - battle.Fighter) · 데미지 공식 (battle.damage
× DAMAGE_SCALE) · 상성 · 자속 · 급소 · 난수 · 화상 반감 · 날씨 · 필드 · 장막 (판이 field.Field 하나를 갖는다) ·
추가 효과 확률 (능력 랭크 · 상태이상 · 풀죽음 · 흡수 · 반동). 특성은 끈다 (Fighter.ability_on 그대로 False).
**명중률은 굴리지 않는다 - 걸어서 비키는 것이 명중률이다.** 명중 · 회피 랭크는 이렇게 바꿔 쓴다: 명중 랭크 = 내 탄의
빠르기, 회피 랭크 = 걷는 빠르기 (한 랭크에 EVA_WALK 6% · +6 이면 +36%, -6 이면 -36% - _walk_speed 의 공식 뒤에 곱한다).

피하기 없음 (2026-11-19 사용자: "회피 기능은 빼도 될 것 같아 너무 사기다")
    Space · Shift 대시 (무적 0.2초 · 대기 1.6초) 를 뺐다. 'dodge' 키는 없다 (모르는 키처럼 버린다). 걷기와 교체로만
    비킨다. 무적은 나올 때 (SPAWN_PROTECT) 뿐.

좌표 · 시간
    아레나 ARENA_W × ARENA_H (u), y 는 아래로. 판 시각 t = step 수 × TICK (초).
    각: 0 = 오른쪽, 아래쪽으로 돈다 (캔버스 회전 방향 그대로). 판 안에서는 도, 밖으로 보내는 ang (cast 이벤트 ·
    장판 Z) 은 라디안 (캔버스에 그대로, 소수 셋째 자리).
    방향 d 0~7: 0 아래 · 1 오른아래 · 2 오른 · 3 오른위 · 4 위 · 5 왼위 · 6 왼 · 7 왼아래 (도트 rowmap 순서).

장판 Z (snapshot "z")
    tele   내려찍기 · 뛰어내리기 표시: (x, y) 반지름 r
    beam   광선: (x, y) 에서 ang 쪽으로 길이 len, 굵기 w
    cone   부채꼴: (x, y) 에서 ang 쪽으로 반지름 r (= len), 끝에서의 너비 w (펼친 각 = 2·atan(w/2 / len))
    ring   쓴 쪽 둘레 고리: (x, y) 반지름 r
    haz    함정: (x, y) 반지름 r
    t0 · t1  생긴 시각 · 터지는 시각. 예고(tele · beam · cone · ring)는 준비 동안 보이고 t1 에 맞은 뒤
             발동 동안 잠깐 더 남는다 (now < t1 '곧 온다', now ≥ t1 '터졌다'). 함정(haz)은 t1 에 사라진다.

근접 · 돌진 (2026-11-18 사용자: "몸통박치기, 전광석화처럼 내가 가는 방향으로 이동하면서 범위 공격으로")
    방향: 쓰기 시작할 때 누르고 있는 쪽 (혼란이면 뒤집힌 쪽). 안 누르면 상대 쪽, 상대가 없으면 보는 쪽.
          반드시 맞는 근접(kit home > 0, 제비반환)은 늘 상대 쪽 (준비 동안 살짝 따라간다).
    발동: 그 각으로 kit range 만큼 달려든다 (근접 kit speed = range / 0.18초, 돌진 1500 u/s). 벽에 닿으면 그 자리에서
          멈춘다 (미끄러지지 않는다). 달리는 동안엔 방향키가 안 듣는다.
    맞음: 이번 틱에 달린 길(선분)에서 상대 가운데까지가 근접 kit w/2 + BODY_R, 돌진 2·BODY_R + DASH_REACH 안이면
          맞는다. 처음 맞힌 자리에서 멈춘다 (몸을 뚫고 지나가지 않는다). 무적인 상대에겐 몸이 닿는 자리에서 멈춘다.
          맞은 쪽은 BUMP_DIST 만큼 BUMP_SEC 동안 기술 방향으로 밀린다 (준비를 끊는 휘청 · 무적은 없다 - 경직은 아래
          '손맛', 벽에서 멈춘다. 쓴 쪽보다 뒤에 있었으면 쓴 쪽에서 멀어지는 쪽으로).
    연속 근접(n > 1): 첫 대를 맞힌 뒤 제자리에서 MULTI_GAP 마다 한 대씩, 상대가 w/2 + BODY_R 안에 있는 동안.
          밀어내기는 마지막 대에만.
    맞부딪힘: 둘 다 달리는 중(아직 안 맞힘) · 서로 마주 보고(각 90° 안) · 어느 한쪽 길이 상대에 닿으면.
    cast 이벤트 덧붙임: len 달려드는 거리 (벽까지 줄인 것, u) · r 길 가운데에서 맞는 너비의 반 (근접 w/2 ·
          돌진 DASH_REACH - 돌진은 몸 반지름 바깥으로 이만큼). x · y 는 쓰기 시작한 자리, ang 은 라디안.

손맛 · 빠르기 (2026-11-19 사용자: "손맛이 조금 부족한 것 같아 ... 전투가 좀 길어지는 것 같아서 약간 루즈해지는 감이")
    DAMAGE_SCALE 0.3 → 0.42 · FIGHT_SEC 180 → 120 · 대기 × 0.85 · 준비 × 0.75 (action_moves 의 CD_SCALE · FAST_WIND).
    밀림: 근접 · 돌진 BUMP_DIST 45 → 70 (BUMP_SEC 그대로). 탄도 맞히면 탄이 날던 쪽으로 SHOT_PUSH 를 SHOT_PUSH_SEC
          동안 민다 - 한 틱에 여러 발(연발)이 맞아도 한 번 (마지막 발의 쪽으로). 상성 0 · 막음 · 무적이면 안 밀고,
          이미 밀리는 중이거나 달려드는 중(근접 · 돌진 발동)이면 그대로 둔다 (탄 하나로 달리기를 끊지 않는다).
          근접 · 돌진도 상성 0 이면 안 민다.
    경직: 기술 데미지(상성 > 0, 1 이상)를 받으면 HITSTUN_SEC (급소 · 효과가 굉장하면 HITSTUN_BIG) 동안 못 걷고
          새로 못 한다 (기술 · 교체 - 누른 키는 BUFFER_SEC 동안 들고 있다가 풀리면 쓴다). 하던 기술은 그대로
          (준비도 안 끊긴다 - 끊는 것은 풀죽음의 휘청), 무적 없음. 독 · 화상 · 씨뿌리기 · 함정 · 반동 · 되돌림(카운터)은
          경직이 없다.
          겹쳐 맞으면 더하지 않고 새로 잰다 (끝 = 늦은 쪽). 어느 1초(HITSTUN_WINDOW) 창에서도 합쳐 HITSTUN_CAP 을
          넘지 않는다 (그만큼에서 자른다 - 연속기로 끝없이 묶지 못한다). 보이기: F.st "stun" (sp 는 그 진행) - 준비 중에
          맞아도 그동안은 "stun", sm 은 하던 기술 칸 그대로.

이벤트 (drain_events) 덧붙임
    hit            w 때린 쪽 · v 맞은 쪽. w == v 면 스스로 다친 것 (반동 · 발버둥은 k 가 그 기술, 화상 · 독은 brn psn tox).
                   씨뿌리기(k seed) · 함정 · 카운터로 되돌린 것은 w 가 그것을 건 쪽.
    status · cure  s 는 상태이상 (brn psn tox par slp frz) 또는 몸에 걸린 것 (cnf seed trap flinch)
F.team 의 slot 은 intro teams 의 칸. 상대 것은 한 번이라도 나온 마리만 (고른 셋을 미리 드러내지 않는다).

같은 시드 · 같은 입력 · 같은 틱이면 같은 판이다 (random.Random(seed) 하나만 쓴다).
"""
import collections
import math
import random

from . import action_moves as AM
from . import attackfx as AF
from . import battle as B
from . import field as FD
from . import held as H
from . import movecalc as MC
from . import pokelogic as P
from . import statusmoves as SM

# ---------------------------------------------------------------- 판 상수 (서버가 검사 때만 env 로 바꾼다)
TICK = 1.0 / 30
ARENA_W, ARENA_H = 1600, 900
BODY_R = 26
LEVEL = 50
TEAM = 3
DAMAGE_SCALE = 0.42         # 2026-11-19 0.3 → 0.42 (판이 늘어진다)
PICK_SEC = 15
READY_SEC = 3
FIGHT_SEC = 120             # 2026-11-19 180 → 120
KO_PICK_SEC = 5
SPAWN_PROTECT = 1.0
SWITCH_SEC = 0.6
SWITCH_CD = 6.0

# ---------------------------------------------------------------- 손맛
KEYS = ("m0", "m1", "m2", "m3", "sw0", "sw1", "sw2")
SPAWN = {"a": (320.0, 450.0), "b": (1280.0, 450.0)}
BUFFER_SEC = 0.25           # 바쁠 때 누른 키를 이만큼 들고 있다
REC_MOVE = 0.5              # 회복 중 이동 배율
EVA_WALK = 0.06             # 회피 랭크 하나에 걷는 빠르기 ± 이만큼 (±6 → ±36%)
CLASH_PUSH = 140            # 맞부딪히면 튕기는 거리
PUSH_SEC = 0.2              # 튕김 · 밀려남에 걸리는 시간
DASH_REACH = 30             # 돌진이 몸 바깥 이만큼 안을 지나면 맞는다 (2026-11-18 4 → 30)
BUMP_DIST = 70              # 근접 · 돌진에 맞으면 기술 방향으로 밀리는 거리 (2026-11-19 45 → 70)
BUMP_SEC = 0.12             #   그 시간 (틱으로 반올림 - 4틱)
SHOT_PUSH = 22              # 탄에 맞으면 탄이 날던 쪽으로 밀리는 거리 (2026-11-19)
SHOT_PUSH_SEC = 0.08        #   그 시간 (틱으로 반올림 - 2틱)
HITSTUN_SEC = 0.10          # 기술에 맞으면 경직 (못 걷고 새로 못 한다, 하던 기술은 그대로)
HITSTUN_BIG = 0.16          #   급소 · 효과가 굉장하면
HITSTUN_CAP = 0.35          #   어느 HITSTUN_WINDOW 창에서도 경직은 합쳐 이만큼까지
HITSTUN_WINDOW = 1.0
RUSH_KINDS = ("melee", "dash")
OHKO_FRAC = 0.45            # 일격기: 상대 최대 체력의 이만큼
STRUGGLE = "STRUGGLE"
EPS = 1e-6

# ---------------------------------------------------------------- 상태이상 (초)
DOT_SEC = 2.0
SLEEP_SEC = (2.0, 3.0)
WAKE_AFTER_HIT = 0.6
FREEZE_SEC, THAW_EVERY, THAW_CHANCE = 3.0, 1.0, 20
JOLT_EVERY, JOLT_CHANCE, JOLT_SEC = 2.0, 20, 0.6
CONFUSE_SEC = (4.0, 6.0)
FLINCH_SEC = 0.35
TRAP_SEC = 1.2
SEED_SEC = 10.0
SCREEN_SEC = 8.0            # 리플렉터 · 빛의장막 · 오로라베일
FIELD_SEC = 12.0            # 날씨 · 필드 · 방 · 순풍 · 신비의부적 · 흰안개
HAZARD_ARM, HAZARD_LIFE, HAZARD_MAX = 0.6, 25.0, 3

STATUS_CODE = {"burn": "brn", "poison": "psn", "paralysis": "par", "sleep": "slp", "freeze": "frz"}
AILS = AM.AILS + ("bad-poison",)            # 판이 거는 상태 (맹독은 독사슬 · 맹독 같은 기술일 때)
DOT_TYPE = {"brn": "FIRE", "psn": "POISON", "tox": "POISON"}
FIELD_SIDE = {"a": "me", "b": "foe"}        # Fighter.side_name - battle.damage 가 장막을 이것으로 찾는다
SCREEN_KEYS = tuple(SM.SCREENS.values())
STAGE_MSG = {"copy": "상대의 능력 변화를 베꼈다!", "swap": "서로의 능력 변화를 맞바꿨다!",
             "invert": "상대의 능력 변화가 뒤집혔다!"}

Push = collections.namedtuple("Push", "vx vy t0 t1")             # 튕김 · 밀려남 (t1 틱까지)
Stun = collections.namedtuple("Stun", "t0 t1 why")               # why: flinch 풀죽음 · jolt 저림 · knock 튕김
Swap = collections.namedtuple("Swap", "to t0 t1")


# ---------------------------------------------------------------- 셈
def _other(side):
    return "b" if side == "a" else "a"


def _r1(v):
    return round(v, 1)


def _rad(deg):
    """밖으로 보내는 각 (라디안, 소수 셋째 자리)."""
    return round(math.radians(deg), 3)


def _num(v):
    """믿을 수 없는 입력 → 유한한 float (아니면 0)."""
    try:
        v = float(v)
    except (TypeError, ValueError):
        return 0.0
    return v if math.isfinite(v) else 0.0


def _clamp(v, lo, hi):
    return lo if v < lo else hi if v > hi else v


def _dir(ang):
    """각(도) → 도트 방향 0~7."""
    return int(round((90.0 - ang) / 45.0)) % 8


def _facing(d):
    """도트 방향 0~7 → 각(도)."""
    return 90.0 - 45.0 * d


def _polar(ang, length):
    r = math.radians(ang)
    return math.cos(r) * length, math.sin(r) * length


def _turn(cur, want):
    """cur 에서 want 로 돌 각 (-180~180)."""
    return (want - cur + 180.0) % 360.0 - 180.0


def _seg_dist(px, py, ax, ay, bx, by):
    """점 (px, py) 와 선분 a-b 사이 거리."""
    dx, dy = bx - ax, by - ay
    ll = dx * dx + dy * dy
    u = 0.0 if ll <= 0 else _clamp(((px - ax) * dx + (py - ay) * dy) / ll, 0.0, 1.0)
    return math.hypot(px - ax - u * dx, py - ay - u * dy)


def _wall_frac(x, y, dx, dy):
    """(x, y) 에서 (dx, dy) 만큼 갈 때 마당 안에 머무는 몫 0~1 (벽에서 그 길 위에 멈춘다)."""
    f = 1.0
    for p, d, hi in ((x, dx, ARENA_W - BODY_R), (y, dy, ARENA_H - BODY_R)):
        if d > EPS:
            f = min(f, (hi - p) / d)
        elif d < -EPS:
            f = min(f, (BODY_R - p) / d)
    return _clamp(f, 0.0, 1.0)


def _touch(wx, wy, dx, dy, r):
    """(wx, wy) = 나 − 상대. (dx, dy) 쪽으로 갈 때 상대 가운데가 처음 r 안에 드는 몫 (0 = 이미 안). 안 들면 None.
    이미 r 안이어도 상대에게서 멀어지는 쪽이면 None - 등 뒤에 붙은 상대 때문에 멈추지 않는다."""
    a, b = dx * dx + dy * dy, wx * dx + wy * dy
    c0 = wx * wx + wy * wy - r * r
    if c0 <= 0:
        return 0.0 if b < 0 else None
    if a <= 0 or b >= 0:
        return None
    disc = b * b - a * c0
    if disc < 0:
        return None
    return (-b - math.sqrt(disc)) / a


def _part(maxhp, num, den):
    """최대 체력의 num/den (정수 셈, 적어도 1)."""
    return max(1, maxhp * num // den)


def _hpr(f):
    """체력 비율 0~1000 (살아 있으면 적어도 1)."""
    return 0 if f.hp <= 0 else max(1, int(round(f.hp * 1000.0 / f.maxhp)))


def _progress(t, t0, t1):
    return 1.0 if t1 <= t0 else _r1(_clamp((t - t0) / (t1 - t0), 0.0, 1.0))


def _type_blocks(ail, types):
    """타입 때문에 안 걸리는 상태이상 (불꽃-화상 · 독/강철-독 · 전기-마비 · 얼음-얼음)."""
    base = "poison" if ail == "bad-poison" else ail
    return B.TYPE_STATUS_IMMUNE.get(base) in types or (base == "poison" and "STEEL" in types)


def _swinging(c):
    """근접 · 돌진이 발동 중이고 아직 안 맞혔다 (맞부딪힐 수 있다)."""
    return c is not None and c.stage == "act" and c.kind in RUSH_KINDS and not c.hits


def _reach(c):
    """근접 · 돌진이 지나는 길에서 상대 가운데까지 이만큼 안이면 맞는다."""
    return c.kit["w"] / 2.0 + BODY_R if c.kind == "melee" else 2 * BODY_R + DASH_REACH


def _meet(p, q):
    """두 탄이 이번 틱 동안 닿았나 (움직인 길까지 본다 - 빠른 탄끼리 건너뛰지 않게)."""
    rx = (p.x - p.vx * TICK) - (q.x - q.vx * TICK)
    ry = (p.y - p.vy * TICK) - (q.y - q.vy * TICK)
    dvx, dvy = p.vx - q.vx, p.vy - q.vy
    vv = dvx * dvx + dvy * dvy
    u = 0.0 if vv <= 0 else _clamp(-(rx * dvx + ry * dvy) / vv, 0.0, TICK)
    return math.hypot(rx + dvx * u, ry + dvy * u) <= p.r + q.r


# ---------------------------------------------------------------- 판 위의 것들
class Mon(object):
    """고른 한 마리: battle.Fighter 위에 이 판의 PP · 쿨타임 · 상태이상 시계를 얹는다."""

    def __init__(self, dex, raw, slot, side, fld):
        f = B.Fighter(dex, raw)
        f.field, f.side_name = fld, FIELD_SIDE[side]
        self.f = f
        self.side = side
        self.slot = slot                        # 원래 팀 칸 (intro teams 의 칸)
        self.keys = list(f.moves)[:4]
        self.kits = [AM.kit(dex, k) for k in self.keys]
        self.pp = [kt["pp"] for kt in self.kits]
        self.ready = [0.0] * 4                  # 칸마다 다시 쓸 수 있는 시각 (발버둥은 네 칸을 같이 막는다)
        self.ko = False
        self.seen = False                       # 마당에 한 번이라도 나왔다 (상대에게 slot 을 보인다)
        self.tox = 0                            # 맹독 몇 번째 (0 = 보통 독)
        self.dot_at = self.jolt_at = self.thaw_at = 0.0     # 다음 독 · 화상 · 저림 · 녹음 판정
        self.sleep_until = self.frz_until = 0.0

    def out_of_moves(self):
        """쓸 수 있는 기술이 하나도 안 남았다 → 발버둥."""
        return not any(kt["ok"] and pp > 0 for kt, pp in zip(self.kits, self.pp))

    def code(self):
        """상태이상 글자 (snapshot s): brn psn tox par slp frz, 없으면 None."""
        if self.f.status == "poison" and self.tox:
            return "tox"
        return STATUS_CODE.get(self.f.status)


class Side(object):
    """한 사람의 자리: 팀 · 마당 위치 · 지금 하는 일 · 몸에 걸린 것."""

    def __init__(self, name, team):
        self.name = name
        self.team = [P.at_level(m, LEVEL) for m in team]
        self.picked = None
        self.mons = []
        self.cur = 0
        self.x, self.y = SPAWN[name]
        self.px, self.py = self.x, self.y       # 이번 틱 움직이기 전 자리 (돌진 맞음)
        self.vx = self.vy = 0.0                 # 이번 틱 속도 (걷는 모습)
        self.d = 2 if name == "a" else 6
        self.mx = self.my = 0.0                 # 이동 의도
        self.ack = 0
        self.buf = None                         # (키, 버릴 시각)
        self.cast = None
        self.push = None
        self.stun = None
        self.hs = []                            # 경직 구간 [(시작, 끝)..] - 지난 HITSTUN_WINDOW 안의 것, 끝이 마지막
        self.swap = None
        self.inv_until = 0.0
        self.swap_ready = 0.0
        self.need_until = None                  # 쓰러진 뒤 다음을 고를 때까지
        self.cnf_until = self.trap_until = 0.0
        self.seed = None                        # [끝, 다음 빨림, 심은 쪽]
        self.conds = {}                         # Fighter.cond 에 건 것 -> 끝 (0 = 물러날 때까지)

    @property
    def mon(self):
        return self.mons[self.cur] if self.mons else None


class Cast(object):
    """쓰고 있는 기술 하나: 준비(wind) → 발동(act) → 회복(rec).

    근접 · 돌진의 발동: rush 남은 달릴 거리 (None = 안 달린다 · 끝을 정했다, 0 = 이번 틱에 다 달렸다) ·
    lane 이번 틱에 달린 길 (x0, y0, x1, y1) · next 연속 근접의 다음 한 대 시각. 둘 중 하나가 남아 있으면 발동이 이어진다."""
    __slots__ = ("slot", "key", "mv", "kit", "ty", "by", "ang", "stage", "start", "end", "zone", "hits", "rush",
                 "lane", "next")

    def __init__(self, slot, key, mv, kit, by, ang, t):
        self.slot, self.key, self.mv, self.kit, self.by, self.ang = slot, key, mv, kit, by, ang
        self.ty = B.shown_type(mv, by.f)
        self.stage, self.start, self.end = "wind", t, t + kit["wind"]
        self.zone = None
        self.hits = 0
        self.rush = self.lane = self.next = None

    def busy(self):
        """발동이 아직 안 끝났다 (달리는 중 · 연속 근접이 남았다)."""
        return self.rush is not None or self.next is not None

    @property
    def kind(self):
        return self.kit["kind"]


class Shot(object):
    """날아가는 탄 (날리기 · 상태 걸기)."""
    __slots__ = ("id", "o", "by", "k", "ty", "sty", "mv", "x", "y", "vx", "vy", "r", "power", "base", "left",
                 "home", "dead")

    def __init__(self, sid, c, x, y, ang, speed):
        kt = c.kit
        self.id, self.o, self.by, self.k, self.ty, self.sty, self.mv = (sid, c.by.side, c.by, c.key, c.ty, kt["sty"],
                                                                       c.mv)
        self.x, self.y = x, y
        self.vx, self.vy = _polar(ang, speed)
        self.r = kt["w"] / 2.0
        self.power = self.base = AM.nominal_power(c.mv)        # 힘겨루기에서 깎인다
        self.left = kt["range"]
        self.home = kt["home"]
        self.dead = False

    def view(self):
        return {"id": self.id, "o": self.o, "k": self.k, "ty": self.ty, "sty": self.sty, "x": _r1(self.x),
                "y": _r1(self.y), "vx": _r1(self.vx), "vy": _r1(self.vy), "r": _r1(self.r)}


class Zone(object):
    """바닥에 그리는 것: 예고(tele · beam · cone · ring) 와 함정(haz). 모듈 설명의 '장판 Z'."""
    __slots__ = ("id", "o", "by", "k", "ty", "sty", "mv", "kind", "x", "y", "r", "ang", "len", "w", "t0", "t1",
                 "until")

    def __init__(self, zid, c, kind, x, y, t0, t1, until, r=0.0, ang=0.0, length=0.0, w=0.0):
        self.id, self.o, self.by, self.k, self.ty, self.sty, self.mv = (zid, c.by.side, c.by, c.key, c.ty,
                                                                       c.kit["sty"], c.mv)
        self.kind, self.x, self.y, self.r, self.ang, self.len, self.w = kind, x, y, r, ang, length, w
        self.t0, self.t1, self.until = t0, t1, until

    def end(self):
        """광선의 끝점."""
        dx, dy = _polar(self.ang, self.len)
        return self.x + dx, self.y + dy

    def view(self):
        return {"id": self.id, "o": self.o, "k": self.k, "ty": self.ty, "sty": self.sty, "kind": self.kind,
                "x": _r1(self.x), "y": _r1(self.y), "r": _r1(self.r), "ang": _rad(self.ang), "len": _r1(self.len),
                "w": _r1(self.w), "t0": round(self.t0, 3), "t1": round(self.t1, 3)}


# ---------------------------------------------------------------- 판
class ActionBattle(object):
    """판 하나. 모듈 설명 참고."""

    def __init__(self, dex, team_a, team_b, seed, names=("A", "B"), pick_sec=PICK_SEC, ready_sec=READY_SEC,
                 fight_sec=FIGHT_SEC):
        self.dex = dex
        self.rng = random.Random(seed)
        self.names = {"a": names[0], "b": names[1]}
        self.limits = {"pick": pick_sec, "ready": ready_sec, "fight": fight_sec, "koPick": KO_PICK_SEC}
        self.field = FD.Field()
        self.sides = {"a": Side("a", team_a), "b": Side("b", team_b)}
        self.phase = "pick"
        self.t = 0.0
        self.tick = 0
        self.phase_end = float(pick_sec)
        self.result = None
        self.fight_t0 = None            # 싸움이 시작된 판 시각 · 끝난 판 시각 (fight_secs - 전적에 남긴다)
        self.fight_t1 = None
        self.shots = []
        self.zones = []
        self.timed = {}                 # 판에 건 것 ("weather" · "room:gravity" · "a:reflect" ...) -> (끝, 건 쪽)
        self._ev = []
        self._ids = 0
        self._struck = 0                # 마지막 _hit 에서 들어간 기술 데미지의 상성 (안 들어갔으면 0)

    # ---- 밖에서 부르는 것 ----
    def pick(self, side, slots):
        """서로 다른 칸 TEAM 개 (팀이 그보다 적으면 전부). 고르기 단계에서 한 번만."""
        s = self.sides[side]
        if self.phase != "pick" or s.picked is not None:
            return False
        try:
            slots = [int(x) for x in slots]
        except (TypeError, ValueError):
            return False
        need = min(TEAM, len(s.team))
        if len(slots) != need or len(set(slots)) != need or not all(0 <= x < len(s.team) for x in slots):
            return False
        s.picked = slots
        return True

    def set_move(self, side, x, y, seq):
        """이동 의도 (-1~1, 길이 1 이 넘으면 줄인다)."""
        s = self.sides[side]
        s.ack = max(s.ack, int(_num(seq)))
        x, y = _num(x), _num(y)
        n = math.hypot(x, y)
        if n > 1:
            x, y = x / n, y / n
        s.mx, s.my = x, y

    def press(self, side, key, seq):
        """키 하나. 다음 step 에서 해 보고, 바쁘면 BUFFER_SEC 동안 들고 있다 (새로 누르면 바뀐다)."""
        s = self.sides[side]
        s.ack = max(s.ack, int(_num(seq)))
        if key in KEYS and self.phase == "fight":
            s.buf = (key, self.t + BUFFER_SEC)

    def forfeit(self, side):
        if self.phase != "over":
            self._finish(_other(side), "forfeit")

    def step(self):
        """TICK 만큼 판을 굴린다 (단계 시계 포함)."""
        if self.phase == "over":
            return
        self.tick += 1
        self.t = self.tick * TICK
        if self.phase == "pick":
            self._pick_step()
        elif self.phase == "ready":
            if self._past(self.phase_end):
                self._set_phase("fight", self.limits["fight"])
        else:
            self._fight_step()

    def drain_events(self):
        ev, self._ev = self._ev, []
        return ev

    def left(self, side):
        """안 쓰러진 마리 수 (고르기 전엔 0)."""
        return sum(1 for m in self.sides[side].mons if not m.ko)

    def hp_ratio(self, side):
        """고른 마리들의 체력 비율 합 (0~TEAM)."""
        return sum(m.f.hp / float(m.f.maxhp) for m in self.sides[side].mons)

    def intro(self, side):
        return {"t": "hello", "you": side, "arena": [ARENA_W, ARENA_H], "tick": TICK, "names": dict(self.names),
                "limits": dict(self.limits),
                "teams": dict((w, [self._mon_view(m, w == side) for m in s.team]) for w, s in self.sides.items())}

    def snapshot(self, side):
        out = {"t": "s", "n": self.tick, "ts": round(self.t, 3), "ph": self.phase,
               "pt": _r1(max(0.0, self.phase_end - self.t)), "ack": self.sides[side].ack,
               "pick": dict((w, s.picked is not None) for w, s in self.sides.items()),
               "f": {}, "p": [p.view() for p in self.shots], "z": [z.view() for z in self.zones]}
        if all(s.mons for s in self.sides.values()):
            out["f"] = dict((w, self._fighter_view(s, w == side)) for w, s in self.sides.items())
        return out

    # ---- 시각 · 이벤트 ----
    def _past(self, at):
        """at 이 지났다 (그 틱 포함)."""
        return self.t + EPS >= at

    def _before(self, until):
        """until 까지 아직 남았다."""
        return self.t + EPS < until

    def _emit(self, e, **kw):
        kw["e"] = e
        self._ev.append(kw)

    def _next_id(self):
        self._ids += 1
        return self._ids

    def _set_phase(self, ph, sec):
        self.phase = ph
        self.phase_end = self.t + sec
        if ph == "fight":
            self.fight_t0 = self.t
        self._emit("phase", ph=ph)

    def fight_secs(self):
        """싸움이 이어진 초 (반올림). 싸움이 열리기 전에 끝났으면 0."""
        if self.fight_t0 is None:
            return 0
        end = self.t if self.fight_t1 is None else self.fight_t1
        return max(0, int(round(end - self.fight_t0)))

    def _finish(self, winner, reason):
        self.result = {"winner": winner, "reason": reason}
        if self.fight_t0 is not None:
            self.fight_t1 = self.t
        self._set_phase("over", 0)
        self._emit("over", winner=winner, reason=reason)

    # ---- 단계 ----
    def _pick_step(self):
        a, b = self.sides["a"], self.sides["b"]
        if (a.picked is None or b.picked is None) and not self._past(self.phase_end):
            return
        for s in (a, b):
            if s.picked is None:
                s.picked = list(range(min(TEAM, len(s.team))))
            s.mons = [Mon(self.dex, s.team[i], i, s.name, self.field) for i in s.picked]
            s.mons[0].seen = True
        self._set_phase("ready", self.limits["ready"])

    def _fight_step(self):
        order = [self.sides["a"], self.sides["b"]]
        if self.tick % 2:
            order.reverse()                     # 먼저 하는 쪽을 번갈아 (한쪽만 늘 먼저 맞히지 않게)
        for s in order:
            self._tick_side(s)
        for s in order:
            self._walk(s)
        self._separate()
        self._melee_clash()
        for s in order:
            self._cast_tick(s)
        self._fly()
        self._tick_zones()
        self._tick_field()
        self._check_end()
        if self.phase == "fight" and self._past(self.phase_end):
            self._timeout()

    def _check_end(self):
        la, lb = self.left("a"), self.left("b")
        if la and lb:
            return
        self._finish("draw" if not (la or lb) else ("a" if la else "b"), "ko")

    def _timeout(self):
        """남은 마리 수 → 남은 체력 비율 합 → 무승부."""
        la, lb = self.left("a"), self.left("b")
        if la != lb:
            winner = "a" if la > lb else "b"
        else:
            ra, rb = self.hp_ratio("a"), self.hp_ratio("b")
            winner = "draw" if abs(ra - rb) < 1e-9 else ("a" if ra > rb else "b")
        self._finish(winner, "timeout")

    # ---- 자리 ----
    def _foe(self, s):
        return self.sides[_other(s.name)]

    def _present(self, s):
        """마당에 서 있는 한 마리가 있다 (쓰러져 다음을 고르는 중이 아니다)."""
        m = s.mon
        return m is not None and not m.ko and s.need_until is None

    def _hidden(self, s):
        """뛰어올라 숨어 있다 (공중날기 · 구멍파기 준비)."""
        c = s.cast
        return c is not None and c.kind == "leap" and c.stage == "wind"

    def _solid(self, s):
        return self._present(s) and not self._hidden(s)

    def _held(self, s):
        """저림 · 풀죽음 · 튕김 · 잠듦 · 얼음 · 경직 - 걷지도 새로 하지도 못한다."""
        return s.stun is not None or self._staggered(s) or s.mon.f.status in ("sleep", "freeze")

    def _staggered(self, s):
        """맞아서 경직 중 (HITSTUN_SEC). 하던 기술은 그대로 간다."""
        return bool(s.hs) and self._before(s.hs[-1][1])

    def _side_has(self, s, name):
        return bool(self.field.side(FIELD_SIDE[s.name]).get(name))

    def _in_circle(self, s, x, y, r):
        """원 안에 서 있다 (몸 가운데가 반지름 + 몸 절반 안)."""
        return self._solid(s) and math.hypot(s.x - x, s.y - y) <= r + BODY_R / 2.0

    def _in_cone(self, s, foe, ang, reach, spread):
        """s 에서 ang 쪽 부채꼴 (반지름 reach, 펼친 각 spread) 에 foe 의 몸이 걸린다."""
        if not self._solid(foe):
            return False
        dx, dy = foe.x - s.x, foe.y - s.y
        d = math.hypot(dx, dy)
        if d - BODY_R > reach:
            return False
        if d <= BODY_R:
            return True
        half = spread / 2.0 + math.degrees(math.asin(BODY_R / d))
        return abs(_turn(ang, math.degrees(math.atan2(dy, dx)))) <= half

    # ---- 자리의 시계 · 키 ----
    def _tick_side(self, s):
        """한 자리의 시계: 밀려남 · 휘청 · 상태이상 · 몸에 걸린 것 · 교체 · 기술 단계 · 누른 키."""
        if s.push is not None and self.t > s.push.t1 + EPS:
            s.push = None
        if s.stun is not None and self._past(s.stun.t1):
            s.stun = None
        if s.need_until is not None:
            if self._past(s.need_until):
                self._send_in(s, next(i for i, m in enumerate(s.mons) if not m.ko), forced=True)
            else:
                self._try_buffer(s)
            return
        m = s.mon
        if m.ko:
            return
        self._tick_status(s, m)
        self._tick_volatile(s, m)
        if m.ko:
            return
        if s.swap is not None and self._past(s.swap.t1):
            self._send_in(s, s.swap.to, forced=False)
        self._advance(s)
        self._try_buffer(s)

    def _try_buffer(self, s):
        if s.buf is None:
            return
        key, until = s.buf
        if self._try(s, key) or self._past(until):
            s.buf = None

    def _try(self, s, key):
        """키 하나를 지금 해 본다. 했으면 True."""
        if key.startswith("sw"):
            return self._switch(s, int(key[2]))
        return self._free(s) and self._use(s, int(key[1]))

    def _free(self, s):
        """아무것도 안 하고 있다."""
        m = s.mon
        if m is None or m.ko or s.need_until is not None or s.swap or s.push or self._held(s):
            return False
        return s.cast is None

    def _use(self, s, slot):
        m = s.mon
        if not 0 <= slot < 4 or not self._past(m.ready[slot]):
            return False
        if m.out_of_moves():
            key = STRUGGLE
        elif slot < len(m.keys) and m.kits[slot]["ok"] and m.pp[slot] > 0:
            key = m.keys[slot]
            m.pp[slot] -= 1
        else:
            return False
        kt = AM.kit(self.dex, key)
        if key == STRUGGLE:
            m.ready = [self.t + kt["cd"]] * 4    # 칸을 바꿔 가며 몰아 쓰지 못하게
        else:
            m.ready[slot] = self.t + kt["cd"]
        self._start(s, slot, key, AM.move_of(self.dex, key), kt)
        return True

    def _switch(self, s, i):
        if not 0 <= i < len(s.mons) or i == s.cur or s.mons[i].ko:
            return False
        if s.need_until is not None:
            self._send_in(s, i, forced=True)
            return True
        if not self._free(s) or not self._past(s.swap_ready) or self._before(s.trap_until):
            return False
        s.swap = Swap(i, self.t, self.t + SWITCH_SEC)
        s.swap_ready = self.t + SWITCH_CD
        return True

    def _send_in(self, s, i, forced):
        """i 번째를 내보낸다. 쓰러져서 나오면(forced) 제자리에서."""
        old = s.cur
        self._cancel(s)
        self._leave(s, s.mon)
        s.cur = i
        s.swap = s.push = s.stun = s.need_until = None
        s.hs = []
        if forced:
            s.x, s.y = SPAWN[s.name]
        s.inv_until = self.t + SPAWN_PROTECT
        m = s.mon
        m.seen = True
        m.dot_at, m.jolt_at, m.thaw_at = self.t + DOT_SEC, self.t + JOLT_EVERY, self.t + THAW_EVERY
        self._emit("swap", w=s.name, fr=old, to=i)

    def _leave(self, s, m):
        """물러날 때 풀리는 것: 능력 랭크 · 몸에 건 것 · 혼란 · 묶임 · 씨뿌리기. 맹독은 처음부터."""
        m.f.stages = dict((k, 0) for k in B.STAGE_KEYS)
        m.f.cond = {}
        if m.tox:
            m.tox = 1
        s.cnf_until = s.trap_until = 0.0
        s.seed = None
        s.conds = {}

    # ---- 기술: 준비 → 발동 → 회복 ----
    def _start(self, s, slot, key, mv, kt):
        foe = self._foe(s)
        ang = self._aim(s, kt, foe)
        c = Cast(slot, key, mv, kt, s.mon, ang, self.t)
        s.cast = c
        s.d = _dir(ang)
        extra = {}
        if c.kind in RUSH_KINDS:
            dx, dy = _polar(ang, kt["range"])
            extra = {"len": _r1(kt["range"] * _wall_frac(s.x, s.y, dx, dy)),
                     "r": _r1(kt["w"] / 2.0 if c.kind == "melee" else float(DASH_REACH))}
        self._emit("cast", w=s.name, m=slot, k=key, kind=kt["kind"], ty=c.ty, sty=kt["sty"], x=_r1(s.x), y=_r1(s.y),
                   ang=_rad(ang), **extra)
        c.zone = self._telegraph(s, c, foe)

    def _aim(self, s, kt, foe):
        """쓰기 시작할 때의 각. 근접 · 돌진은 누르고 있는 쪽 (반드시 맞는 것은 빼고), 그 밖엔 상대 쪽 · 보는 쪽."""
        if kt["kind"] in RUSH_KINDS and not kt["home"]:
            ix, iy = self._intent(s)
            if ix or iy:
                return math.degrees(math.atan2(iy, ix))
        if self._present(foe):
            return math.degrees(math.atan2(foe.y - s.y, foe.x - s.x))
        return _facing(s.d)

    def _telegraph(self, s, c, foe):
        """준비 동안 상대에게 보이는 예고 장판. 없는 꼴이면 None."""
        kt, kind = c.kit, c.kind
        t1, until = c.end, c.end + kt["act"]
        if kind == "beam":
            return self._zone(c, "beam", s.x, s.y, t1, until, ang=c.ang, length=kt["range"], w=kt["w"])
        if kind == "cone":
            width = 2 * kt["range"] * math.tan(math.radians(kt["spread"] / 2.0))
            return self._zone(c, "cone", s.x, s.y, t1, until, r=kt["range"], ang=c.ang, length=kt["range"], w=width)
        if kind == "burst":
            return self._zone(c, "ring", s.x, s.y, t1, until, r=kt["range"])
        if kind in ("strike", "leap"):
            x, y = self._target_point(s, foe, kt["range"])
            return self._zone(c, "tele", x, y, t1, until, r=kt["w"] / 2.0)
        return None

    def _zone(self, c, kind, x, y, t1, until, **geo):
        z = Zone(self._next_id(), c, kind, x, y, self.t, t1, until, **geo)
        self.zones.append(z)
        return z

    def _target_point(self, s, foe, reach):
        """상대 발밑 (멀면 reach 까지, 상대가 없으면 앞쪽)."""
        if self._present(foe):
            tx, ty = foe.x, foe.y
        else:
            dx, dy = _polar(_facing(s.d), reach)
            tx, ty = s.x + dx, s.y + dy
        dx, dy = tx - s.x, ty - s.y
        d = math.hypot(dx, dy)
        if d > reach:
            tx, ty = s.x + dx / d * reach, s.y + dy / d * reach
        return _clamp(tx, BODY_R, ARENA_W - BODY_R), _clamp(ty, BODY_R, ARENA_H - BODY_R)

    def _advance(self, s):
        """단계 시각이 지났으면 다음 단계로 (한 틱에 여러 단계를 건널 수 있다)."""
        c = s.cast
        while c is not None and self._past(c.end):
            if c.stage == "wind":
                c.stage, c.start, c.end = "act", c.end, c.end + c.kit["act"]
                self._activate(s, c)
            elif c.stage == "act":
                if c.busy():
                    break                       # 달리기 · 연속 근접이 끝을 정할 때까지
                c.stage, c.start, c.end = "rec", c.end, c.end + c.kit["rec"]
            else:
                s.cast = None
            c = s.cast if s.cast is c else None

    def _activate(self, s, c):
        """준비가 끝나 기술이 나가는 순간: 꼴마다 _on_<꼴>. 근접 · 돌진 · 광선은 발동 동안 _cast_tick 이 더 하고,
        방어 · 카운터는 발동 중인지를 _hit 이 본다."""
        on = getattr(self, "_on_" + c.kind, None)
        if on is not None:
            on(s, c)
        if c.key in AF.SELF_HALF and c.key != "CHLOROBLAST" and s.mon is c.by and not c.by.ko:
            self._self_half(s, c.by, c.key, c.ty)       # 빅뱅 · 철거빔: 빗나가도 깎인다 (본가 그대로)

    def _self_half(self, s, m, key, ty):
        """빅뱅 · 철거빔 · 클로로블래스트의 값: 본가는 최대 체력의 절반 (올림). 데미지처럼 DAMAGE_SCALE 을 곱한다
        (발버둥 값과 같은 셈 - 준 데미지와 치르는 값의 비가 본가와 같다)."""
        self._chip(s, m, max(1, int(math.ceil(m.f.maxhp / 2.0) * DAMAGE_SCALE)), key, ty, s.name)

    def _cancel(self, s):
        """하던 기술을 끊는다. 아직 안 터진 예고도 지운다."""
        c = s.cast
        if c is None:
            return
        if c.zone is not None and c.stage == "wind" and c.zone in self.zones:
            self.zones.remove(c.zone)
        s.cast = None

    def _on_proj(self, s, c):
        kt = c.kit
        n = kt["n"]
        speed = kt["speed"] * B.stage_mult(c.by.f.stages["acc"], "acc")     # 명중 랭크 = 탄 빠르기
        gap = BODY_R + kt["w"] / 2.0 + 2
        for i in range(n):
            ang = c.ang + (kt["spread"] * (i / (n - 1.0) - 0.5) if n > 1 else 0.0)
            dx, dy = _polar(ang, gap)
            self.shots.append(Shot(self._next_id(), c, s.x + dx, s.y + dy, ang, speed))

    _on_status = _on_proj

    def _on_melee(self, s, c):
        """달려들기 시작. 반드시 맞는 근접(제비반환 ...)은 준비하는 동안 상대 쪽으로 살짝 돈다."""
        foe = self._foe(s)
        if c.kit["home"] and self._solid(foe):
            lim = c.kit["home"] * c.kit["wind"]
            c.ang += _clamp(_turn(c.ang, math.degrees(math.atan2(foe.y - s.y, foe.x - s.x))), -lim, lim)
        c.rush = float(c.kit["range"])

    def _on_dash(self, s, c):
        c.rush = float(c.kit["range"])

    def _on_beam(self, s, c):
        z, foe = c.zone, self._foe(s)
        ex, ey = z.end()
        if _seg_dist(foe.x, foe.y, z.x, z.y, ex, ey) <= z.w / 2.0 + BODY_R:
            for _ in range(c.kit["n"]):
                if self._hit(c.by, foe, c.key, c.mv) != "hit":
                    break

    def _on_burst(self, s, c):
        foe = self._foe(s)
        if self._in_circle(foe, s.x, s.y, c.kit["range"]):
            self._hit(c.by, foe, c.key, c.mv)
        if c.key in AF.SELF_KO and not c.by.ko:
            self._faint(s)                      # 대폭발 · 자폭

    def _on_cone(self, s, c):
        foe = self._foe(s)
        if self._in_cone(s, foe, c.ang, c.kit["range"], c.kit["spread"]):
            self._hit(c.by, foe, c.key, c.mv)

    def _on_strike(self, s, c):
        z, foe = c.zone, self._foe(s)
        if self._in_circle(foe, z.x, z.y, z.r):
            self._hit(c.by, foe, c.key, c.mv)

    def _on_leap(self, s, c):
        z = c.zone
        s.x, s.y = z.x, z.y
        self._on_strike(s, c)

    def _on_self(self, s, c):
        m = c.by
        cost = self._self_cost(m, c.key, c.mv)
        if cost is None:
            self._emit("txt", w=s.name, msg="하지만 실패했다!")      # PP · 대기는 쓴 채로 (본가처럼)
            return
        if cost:
            self._chip(s, m, cost, c.key, c.mv.get("type"), s.name)     # 먼저 깎고 올린다 (본가 순서)
        if c.key in AM.FIELD_MOVES:
            self._set_field(s, c.key)
        stats = c.mv.get("stat") or []
        if stats:
            self._boost_all(s, m, stats, by_foe=False)
        self._self_effects(s, m, c.key, c.mv)

    _on_heal = _on_self

    def _self_cost(self, m, key, mv):
        """체력을 깎아 올리는 기술 (배북 · 살을깎다 · 소울비트)이 깎을 체력. 없으면 0. 모자라면 None - 본가처럼 실패한다
        (statusmoves.h_bellydrum · h_filletaway · attackfx 의 소울비트 검사). 본가처럼 DAMAGE_SCALE 없이 깎는다."""
        f = m.f
        heal = SM.heal_percent(key, mv, f)
        if heal >= 0:
            return 0
        if key == "CLANGOROUSSOUL":
            cost, short = max(1, f.maxhp // 3), f.hp * 3 <= f.maxhp
        else:
            cost = max(1, int(f.maxhp * -heal / 100.0))
            short = f.hp <= cost
        if short or (key == "BELLYDRUM" and f.stages["atk"] >= B.STAGE_MAX):
            return None
        return cost

    def _on_hazard(self, s, c):
        x, y = self._target_point(s, self._foe(s), c.kit["range"])
        mine = [z for z in self.zones if z.kind == "haz" and z.o == s.name]
        if len(mine) >= HAZARD_MAX:
            self.zones.remove(mine[0])
        end = self.t + HAZARD_LIFE
        self._zone(c, "haz", x, y, end, end, r=c.kit["w"] / 2.0)

    def _cast_tick(self, s):
        """발동 동안 틱마다: 근접 · 돌진이 지난 길 위를 치기 · 연속 근접 · 광선이 탄 지우기."""
        c = s.cast
        if c is None or c.stage != "act":
            return
        if c.kind in RUSH_KINDS:
            self._rush_tick(s, c)
        elif c.kind == "beam":
            self._beam_sweep(s, c)

    def _rush_tick(self, s, c):
        """이번 틱에 달린 길에 상대가 닿았으면 친다 (처음 맞힌 자리에서 멈춘다). 다 달렸으면 끝을 정한다.
        연속 근접은 그 뒤 MULTI_GAP 마다 제자리에서 한 대씩, 상대가 닿는 데 있는 동안."""
        foe = self._foe(s)
        if c.rush is not None:
            lane, c.lane = c.lane, None
            if lane is not None and not c.hits and self._lane_hits(s, c, foe, lane):
                res = self._hit(c.by, foe, c.key, c.mv)
                if res != "pass":
                    c.hits, c.rush = 1, 0.0
                    if res == "hit" and self._struck and c.kit["n"] == 1:
                        self._bump(foe, c.ang, s)
            if c.rush <= EPS:
                c.rush = None
                if c.hits and c.kit["n"] > 1:
                    c.next = self.t + AM.MULTI_GAP
                else:
                    c.end = self.t              # 다 달렸다 · 맞혔다 → 다음 틱에 회복
            return
        if c.next is None or not self._past(c.next):
            return
        c.hits += 1
        last = c.hits >= c.kit["n"]
        near = self._solid(foe) and math.hypot(foe.x - s.x, foe.y - s.y) <= _reach(c) + 0.01
        if near and self._hit(c.by, foe, c.key, c.mv) == "hit" and self._struck and last:
            self._bump(foe, c.ang, s)
        if last or not near:
            c.next, c.end = None, self.t        # 다 쳤다 · 상대가 멀어졌다
        else:
            c.next += AM.MULTI_GAP

    def _lane_hits(self, s, c, foe, lane=None):
        """이번 틱에 달린 길(없으면 지금 자리)이 foe 의 가운데에 닿는다. 길 시작보다 몸 반 넘게 뒤에 있는 상대는
        안 맞는다 - 앞으로 달려 나가는 기술이 등 뒤를 치지 않게."""
        x0, y0, x1, y1 = lane or c.lane or (s.x, s.y, s.x, s.y)
        if not self._solid(foe):
            return False
        ux, uy = _polar(c.ang, 1.0)
        if (foe.x - x0) * ux + (foe.y - y0) * uy < -BODY_R:
            return False
        return _seg_dist(foe.x, foe.y, x0, y0, x1, y1) <= _reach(c) + 0.01

    def _beam_sweep(self, s, c):
        z = c.zone
        ex, ey = z.end()
        for p in self.shots:
            if p.o != s.name and not p.dead and _seg_dist(p.x, p.y, z.x, z.y, ex, ey) <= p.r + z.w / 2.0:
                p.dead = True
                self._emit("clash", x=_r1(p.x), y=_r1(p.y), k1=c.key, k2=p.k)

    # ---- 이동 ----
    def _walk(self, s):
        s.px, s.py = s.x, s.y
        c = s.cast
        if c is not None and c.rush:
            if s.push is None and self._present(s):
                self._rush_step(s, c)
                return
            c.rush = 0.0                        # 밀려나면 달리기가 끊긴다
        vx, vy = self._velocity(s)
        s.vx, s.vy = vx, vy
        if vx or vy:
            s.x = _clamp(s.x + vx * TICK, BODY_R, ARENA_W - BODY_R)
            s.y = _clamp(s.y + vy * TICK, BODY_R, ARENA_H - BODY_R)
            if s.cast is None and s.push is None:
                s.d = _dir(math.degrees(math.atan2(vy, vx)))
        c = s.cast
        if c is not None and c.stage == "wind" and c.zone is not None and c.zone.kind in ("cone", "ring"):
            c.zone.x, c.zone.y = s.x, s.y       # 부채꼴 · 고리 예고는 쓰는 쪽을 따라간다

    def _rush_step(self, s, c):
        """근접 · 돌진이 한 틱 달린다: 고정한 각으로 kit speed (남은 거리까지). 벽에 닿으면 그 길 위에서 멈추고,
        상대에게 닿을 자리(맞는 거리, 무적이면 몸이 닿는 거리)에서 멈춘다 - 맞았는지는 _rush_tick 이 본다."""
        step = min(c.kit["speed"] * TICK, c.rush)
        dx, dy = _polar(c.ang, step)
        f = _wall_frac(s.x, s.y, dx, dy)
        stop = f < 1.0 - EPS
        foe = self._foe(s)
        if self._solid(foe):
            open_ = not self._before(foe.inv_until)
            u = _touch(s.x - foe.x, s.y - foe.y, dx, dy, _reach(c) if open_ else 2 * BODY_R)
            if u is not None and u <= f:
                f = u
                stop = stop or not open_        # 무적인 몸에 부딪히면 멈춘다
        x = _clamp(s.x + dx * f, BODY_R, ARENA_W - BODY_R)
        y = _clamp(s.y + dy * f, BODY_R, ARENA_H - BODY_R)
        s.vx, s.vy = (x - s.x) / TICK, (y - s.y) / TICK
        c.lane = (s.x, s.y, x, y)
        s.x, s.y = x, y
        c.rush = 0.0 if stop else max(0.0, c.rush - step * f)

    def _velocity(self, s):
        if not self._present(s):
            return 0.0, 0.0
        if s.push is not None:
            return s.push.vx, s.push.vy
        sp = self._walk_speed(s) * self._walk_mult(s)
        ix, iy = self._intent(s)
        return ix * sp, iy * sp

    def _walk_mult(self, s):
        """지금 걷기 배율 (0 = 못 걷는다)."""
        if (self.phase != "fight" or not self._present(s) or s.swap or s.push or self._held(s)
                or self._before(s.trap_until)):
            return 0.0
        c = s.cast
        if c is None:
            return 1.0
        return c.kit["lock"] if c.stage == "wind" else REC_MOVE if c.stage == "rec" else 0.0

    def _walk_speed(self, s):
        """(180 + 0.9 × clamp(스피드, 20, 250)) × (1 + EVA_WALK × 회피 랭크). 순풍이면 스피드 2배, 트릭룸이면 느린 쪽이
        빠르다. 회피 랭크는 ±6 에서 멈춘다 (±36% - 그림자분신 · 작아지기 ...)."""
        spe = s.mon.f.stat("spe") * (2 if self._side_has(s, "tailwind") else 1)
        spe = _clamp(spe, 20, 250)
        if self.field.room("trickroom"):
            spe = 270 - spe
        eva = _clamp(s.mon.f.stages.get("eva", 0), B.STAGE_MIN, B.STAGE_MAX)
        return (180 + 0.9 * spe) * (1 + EVA_WALK * eva)

    def _intent(self, s):
        """이동 의도. 혼란이면 반대."""
        if self._before(s.cnf_until):
            return -s.mx, -s.my
        return s.mx, s.my

    def _separate(self):
        """몸끼리 겹치지 않게 반씩 밀어낸다."""
        a, b = self.sides["a"], self.sides["b"]
        if not (self._solid(a) and self._solid(b)):
            return
        dx, dy = b.x - a.x, b.y - a.y
        d = math.hypot(dx, dy)
        if d >= 2 * BODY_R:
            return
        if d < EPS:
            dx, dy, d = 1.0, 0.0, 1.0
        half = (2 * BODY_R - d) / 2.0
        for s, sign in ((a, -1.0), (b, 1.0)):
            s.x = _clamp(s.x + sign * dx / d * half, BODY_R, ARENA_W - BODY_R)
            s.y = _clamp(s.y + sign * dy / d * half, BODY_R, ARENA_H - BODY_R)

    def _melee_clash(self):
        """근접(돌진)끼리 둘 다 달리는 중에 마주 보고 부딪히면 (어느 한쪽 길이 상대에 닿으면) 둘 다 튕긴다 - 데미지 없음."""
        a, b = self.sides["a"], self.sides["b"]
        ca, cb = a.cast, b.cast
        if not (_swinging(ca) and _swinging(cb)):
            return
        ang = math.degrees(math.atan2(b.y - a.y, b.x - a.x))
        if abs(_turn(ca.ang, ang)) > 90 or abs(_turn(cb.ang, ang + 180)) > 90:
            return                              # 등지고 달린다
        if not (self._lane_hits(a, ca, b) or self._lane_hits(b, cb, a)):
            return
        self._emit("clash", x=_r1((a.x + b.x) / 2), y=_r1((a.y + b.y) / 2), k1=ca.key, k2=cb.key)
        self._knock(a, ang + 180, CLASH_PUSH)
        self._knock(b, ang, CLASH_PUSH)

    def _knock(self, s, ang, dist):
        """ang 쪽으로 dist 만큼 밀려난다 (그동안 휘청)."""
        self._stun(s, PUSH_SEC, "knock")
        vx, vy = _polar(ang, dist / PUSH_SEC)
        s.push = Push(vx, vy, self.t, self.t + PUSH_SEC)

    def _bump(self, s, ang, by):
        """근접 · 돌진에 맞아 ang 쪽으로 BUMP_DIST 를 BUMP_SEC 동안 밀린다.
        쓴 쪽(by)보다 뒤에 있었으면 by 에서 멀어지는 쪽으로."""
        away = math.degrees(math.atan2(s.y - by.y, s.x - by.x))
        if abs(_turn(ang, away)) > 90:
            ang = away
        self._shove(s, ang, BUMP_DIST, BUMP_SEC)

    def _shove(self, s, ang, dist, sec):
        """ang 쪽으로 dist 를 sec (틱으로 반올림) 동안 밀린다 - 무적 없음, 벽에서 멈춘다 (_walk 가 막는다), 밀리는 동안은
        새로 못 한다 (_free). 이미 밀리는 중(밀어내기 기술 · 튕김)이면 그대로 둔다."""
        if not self._present(s) or s.push is not None:
            return
        n = max(1, int(round(sec / TICK)))
        vx, vy = _polar(ang, dist / (n * TICK))
        s.push = Push(vx, vy, self.t, self.t + n * TICK)

    def _stun(self, s, sec, why):
        self._cancel(s)
        s.stun = Stun(self.t, self.t + sec, why)

    def _hitstun(self, s, sec):
        """기술에 맞아 sec 동안 경직 (모듈 설명 '손맛'). 하던 기술은 안 끊는다. 겹치면 끝을 늦은 쪽으로 새로 잴 뿐
        더하지 않고, 이 끝에서 끝나는 HITSTUN_WINDOW 창 안의 경직이 HITSTUN_CAP 을 넘으면 그만큼에서 자른다.
        (구간을 시간 순으로만 늘리므로 그 창이 가장 무겁다 - 어느 창에서도 CAP 을 넘지 않는다.)"""
        t = self.t
        spans = [sp for sp in s.hs if sp[1] > t - HITSTUN_WINDOW + EPS]
        start = max(t, spans[-1][1]) if spans else t        # 지금 경직 중이면 그 끝에서부터 늘린다
        end = t + sec
        if end > start + EPS:

            def load(e):
                """e 에서 끝나는 창 안의 경직 (start ~ e 로 늘릴 몫 포함). e 가 늘면 줄지 않는다."""
                lo = e - HITSTUN_WINDOW
                return sum(max(0.0, min(b, start) - max(a, lo)) for a, b in spans) + (e - start)

            if load(end) > HITSTUN_CAP:
                lo_e, hi_e = start, end
                for _ in range(30):
                    mid = (lo_e + hi_e) / 2.0
                    if load(mid) <= HITSTUN_CAP:
                        lo_e = mid
                    else:
                        hi_e = mid
                end = lo_e
            if end > start + EPS:
                if spans and spans[-1][1] >= start - EPS:
                    spans[-1] = (spans[-1][0], end)             # 이어서 늘린다
                else:
                    spans.append((start, end))
        s.hs = spans

    # ---- 탄 · 장판 ----
    def _fly(self):
        for p in self.shots:
            if p.dead:
                continue
            vic = self.sides[_other(p.o)]
            if p.home and self._solid(vic):
                self._steer(p, vic)
            p.x += p.vx * TICK
            p.y += p.vy * TICK
            p.left -= math.hypot(p.vx, p.vy) * TICK
            if p.left <= 0 or not (0 <= p.x <= ARENA_W and 0 <= p.y <= ARENA_H):
                p.dead = True
        self._clash_shots()
        shove = {}                              # 맞은 쪽 -> 이번 틱에 데미지를 준 마지막 탄 (연발이어도 한 번만 민다)
        for p in self.shots:
            if p.dead:
                continue
            vic = self.sides[_other(p.o)]
            if _seg_dist(vic.x, vic.y, p.x - p.vx * TICK, p.y - p.vy * TICK, p.x, p.y) <= p.r + BODY_R:
                scale = p.power / p.base if p.base else 1.0
                res = self._hit(p.by, vic, p.k, p.mv, scale)
                if res != "pass":
                    p.dead = True
                if res == "hit" and self._struck:
                    shove[vic.name] = p
        for name, p in sorted(shove.items()):
            vic = self.sides[name]
            if not (vic.cast is not None and vic.cast.rush):        # 달려드는 중이면 안 민다 (달리기를 안 끊는다)
                self._shove(vic, math.degrees(math.atan2(p.vy, p.vx)), SHOT_PUSH, SHOT_PUSH_SEC)
        self.shots = [p for p in self.shots if not p.dead]

    def _steer(self, p, vic):
        """상대 쪽으로 home 도/초 만큼 꺾는다."""
        cur = math.degrees(math.atan2(p.vy, p.vx))
        lim = p.home * TICK
        ang = cur + _clamp(_turn(cur, math.degrees(math.atan2(vic.y - p.y, vic.x - p.x))), -lim, lim)
        p.vx, p.vy = _polar(ang, math.hypot(p.vx, p.vy))

    def _clash_shots(self):
        """탄 vs 탄: 위력이 센 쪽의 20% 이내면 둘 다, 아니면 약한 쪽만 사라지고 센 쪽은 약한 쪽 × 0.5 만큼 깎인다."""
        ours = [p for p in self.shots if p.o == "a" and not p.dead]
        theirs = [q for q in self.shots if q.o == "b" and not q.dead]
        for p in ours:
            for q in theirs:
                if p.dead:
                    break
                if q.dead or not _meet(p, q):
                    continue
                hi, lo = (p, q) if p.power >= q.power else (q, p)
                if hi.power - lo.power <= 0.2 * hi.power:
                    hi.dead = lo.dead = True
                else:
                    lo.dead = True
                    hi.power -= lo.power * 0.5
                self._emit("clash", x=_r1((p.x + q.x) / 2), y=_r1((p.y + q.y) / 2), k1=p.k, k2=q.k)

    def _tick_zones(self):
        keep = []
        for z in self.zones:
            if self._past(z.until):
                continue
            if z.kind == "haz" and self._past(z.t0 + HAZARD_ARM) and self._spring(z):
                continue
            keep.append(z)
        self.zones = keep

    def _spring(self, z):
        """함정을 밟았나. 밟았으면 터뜨리고 True."""
        vic = self.sides[_other(z.o)]
        if self._before(vic.inv_until) or not self._in_circle(vic, z.x, z.y, z.r):
            return False
        m = vic.mon
        f = m.f
        if z.k == "STEALTHROCK":
            eff = B.effectiveness(self.dex, "ROCK", f.types())
            self._chip(vic, m, max(1, int(f.maxhp * eff / 8)), z.k, z.ty, z.o)
        elif not SM.grounded(f):
            return False                        # 떠 있으면 압정 · 독압정 · 끈적끈적네트를 안 밟는다
        elif z.k == "SPIKES":
            self._chip(vic, m, _part(f.maxhp, 1, 8), z.k, z.ty, z.o)
        elif z.k == "TOXICSPIKES":
            self._inflict(vic, "poison", z.by)
        else:
            self._boost_all(vic, m, [["spe", -1]], by_foe=True)
        return True

    # ---- 맞음 ----
    def _hit(self, by, vic, key, mv, scale=1.0):
        """by(때린 한 마리)의 기술이 vic(자리)에 닿았다. "pass" 지나감 · "block" 막힘 · "hit" 맞음.

        무적(등장) · 숨음 · 쓰러짐이면 지나간다. 방어는 막고, 카운터 류는 막고 되돌린다.
        부른 뒤 self._struck 는 이번에 기술 데미지가 들어갔으면 상성 (> 0), 아니면 0 - 밀어내기가 본다."""
        self._struck = 0
        if not self._solid(vic) or self._before(vic.inv_until):
            return "pass"
        vc = vic.cast
        if vc is not None and vc.stage == "act":
            if vc.kind == "guard":
                self._emit("guard", w=vic.name)
                return "block"
            if vc.kind == "counter" and mv.get("cat") in ("physical", "special") \
                    and AM.COUNTERS[vc.key][0] in (None, mv.get("cat")):
                self._counter(vic, vc, by, key, mv)
                return "block"
        att = self.sides[by.side]
        if MC.attacks(mv):
            self._wound(by, att, vic, key, mv, scale)
        elif self._immune(by, vic.mon, key, mv):
            self._emit("txt", w=vic.name, msg="효과가 없는 것 같다...")
        elif not self._effects(by, att, vic, key, mv, 0):
            self._emit("txt", w=vic.name, msg="하지만 실패했다!")      # 이미 상태이상 · 랭크 끝 · 신비의부적
        return "hit"

    def _counter(self, vic, vc, by, key, mv):
        """카운터 류: 맞았을 데미지 × 배율을 때린 쪽에게 (멀리서 쏜 것도)."""
        dmg = self._roll(by, vic.mon, key, mv, 1.0)[0]
        self._emit("counter", w=vic.name)
        vc.end = self.t                         # 되돌리고 나면 회복으로
        att = self.sides[by.side]
        back = int(dmg * AM.COUNTERS[vc.key][1])
        if back and att.mon is by and not by.ko:
            if self._chip(att, by, back, vc.key, vc.ty, vic.name) and not by.ko:
                self._pop_balloon(att, by)      # 되돌려 받은 것도 데미지다

    def _roll(self, by, dst, key, mv, scale):
        """(데미지, 급소, 상성). 본가 공식 × DAMAGE_SCALE (맞았으면 적어도 1), 일격기는 최대 체력의 OHKO_FRAC."""
        if key in MC.OHKO:
            eff = B.type_eff(self.dex, mv, mv.get("type"), by.f, dst.f, False)
            return (int(math.ceil(dst.f.maxhp * OHKO_FRAC)) if eff else 0), False, eff
        if key == STRUGGLE:
            mv = dict(mv, type=None)            # 발버둥은 타입이 없다 (본가 5세대부터) - PP 가 다 떨어져도 고스트를 친다
        dmg, crit, eff = B.damage(self.dex, mv, by.f, dst.f, self.rng)
        if dmg <= 0:
            return 0, crit, eff
        return max(1, int(round(dmg * DAMAGE_SCALE * scale))), crit, eff

    def _wound(self, by, att, vic, key, mv, scale):
        """때리는 기술이 맞았다: 데미지 → 깨기 · 녹이기 → 추가 효과 → 쓰러짐."""
        dst = vic.mon
        dmg, crit, eff = self._roll(by, dst, key, mv, scale)
        lost = min(dst.f.hp, dmg)
        dst.f.hp -= lost
        ty = B.shown_type(mv, by.f)
        self._emit("hit", w=att.name, v=vic.name, k=key, ty=ty, dmg=lost, hpr=_hpr(dst.f), eff=eff, crit=bool(crit),
                   x=_r1(vic.x), y=_r1(vic.y))
        if lost:
            self._pop_balloon(vic, dst)
            by.f.cond.pop("laserfocus", None)
            if dst.f.status == "sleep":
                dst.sleep_until = min(dst.sleep_until, self.t + WAKE_AFTER_HIT)
            elif dst.f.status == "freeze" and ty == "FIRE":
                self._cure(vic, dst)            # 불꽃 기술에 녹는다
        if eff:
            self._effects(by, att, vic, key, mv, lost)
        if dst.f.hp <= 0 and not dst.ko:
            self._faint(vic)
        self._struck = eff if (lost and eff) else 0
        if self._struck and not dst.ko and vic.mon is dst:
            self._hitstun(vic, HITSTUN_BIG if (crit or eff >= 2) else HITSTUN_SEC)
        if eff and att.mon is by and not by.ko:
            if key == "CHLOROBLAST":
                self._self_half(att, by, key, ty)       # 맞혔을 때만 깎인다 (본가 그대로)
            elif key == "FINALGAMBIT":
                self._faint(att)                        # 목숨걸기: 데미지는 내 체력 × DAMAGE_SCALE (대폭발처럼 줄인 그대로)

    def _pop_balloon(self, s, m):
        """풍선은 데미지를 받으면 터진다 (본가 held.on_each_hit). 함정 · 독 · 반동으로는 안 터진다."""
        if m.f.held == "AIRBALLOON" and not m.f.used:
            m.f.used = True
            self._emit("txt", w=s.name, msg="풍선이 터졌다!")

    def _effects(self, by, att, vic, key, mv, lost):
        """추가 효과 (도감 확률 그대로): 능력 랭크 · 상태이상 · 풀죽음 · 체력 나누기 · 밀어내기 · 흡수 · 반동.
        무엇이든 일어났으면 True (변화기가 헛돌았는지 본다)."""
        dst = vic.mon
        alive = dst.f.hp > 0
        mine = att.mon is by and not by.ko     # 때린 쪽이 아직 나와 있다 (내 랭크 · 흡수 · 반동)
        done = False
        stats = mv.get("stat") or []
        if stats and self._chance(mv.get("statChance")):
            if mv.get("statSelf"):
                done = mine and self._boost_all(att, by, stats, by_foe=False)
            elif alive:
                done = self._boost_all(vic, dst, stats, by_foe=True)
        ail = mv.get("ail")
        if ail == "poison" and key in AF.BAD_POISON:
            ail = "bad-poison"
        if alive and ail in AILS and self._chance(mv.get("ailChance")):
            done = self._inflict(vic, ail, by) or done
        if alive and (mv.get("flinch") or 0) and self.rng.uniform(0, 100) < mv["flinch"]:
            self._stun(vic, FLINCH_SEC, "flinch")
            self._emit("status", w=vic.name, s="flinch")
            done = True
        if alive and mine and mv.get("split"):
            avg = (by.f.hp + dst.f.hp) // 2
            by.f.hp, dst.f.hp = min(by.f.maxhp, avg), min(dst.f.maxhp, avg)
            self._emit("txt", w=att.name, msg="서로의 체력을 나눠 가졌다!")
            done = True
        if alive and mv.get("push"):
            self._knock(vic, math.degrees(math.atan2(vic.y - att.y, vic.x - att.x)), mv["push"])
            done = True
        if mine:
            self._drain(att, by, key, mv, lost)
        return done

    def _drain(self, att, by, key, mv, lost):
        """흡수 · 반동 (준 데미지의 몇 %) · 발버둥 (쓸 때마다 최대 체력의 1/4 × DAMAGE_SCALE)."""
        drain = mv.get("drain") or 0
        if drain and lost:
            amount = max(1, int(lost * abs(drain) / 100.0))
            if drain > 0:
                self._heal(att, by, amount)
            else:
                self._chip(att, by, amount, key, mv.get("type"), att.name)
        cost = -(mv.get("heal") or 0)
        if cost > 0 and not by.ko:
            self._chip(att, by, max(1, int(by.f.maxhp * cost / 100.0 * DAMAGE_SCALE)), key, mv.get("type"), att.name)

    def _chance(self, pct):
        """도감 확률 (0 이면 반드시 - battle 과 같다)."""
        return not pct or self.rng.uniform(0, 100) < pct

    def _immune(self, by, dst, key, mv):
        """변화기가 타입 때문에 안 통한다 (풀 타입에게 가루 · 땅 타입에게 전기자석파 · 불꽃 타입에게 도깨비불 ...)."""
        types = dst.f.types()
        if "powder" in (mv.get("flags") or ()) and "GRASS" in types:
            return True
        if key in B.TYPE_CHECKED_STATUS and B.type_eff(self.dex, mv, mv.get("type"), by.f, dst.f, False) == 0:
            return True
        return not mv.get("stat") and _type_blocks(mv.get("ail"), types)

    def _inflict(self, vic, ail, by):
        """상태이상을 건다. 걸렸으면 True. 이미 있음 · 타입(강철 독 포함) · 신비의부적이면 안 걸린다."""
        m = vic.mon
        f = m.f
        if ail in ("confusion", "trap", "leech-seed"):
            return self._volatile(vic, m, ail, by)
        base = "poison" if ail == "bad-poison" else ail
        guarded = by.side != vic.name and self._side_has(vic, "safeguard")
        if f.status or guarded or _type_blocks(base, f.types()):
            return False
        f.status = base
        m.tox = 1 if ail == "bad-poison" else 0
        if base in ("burn", "poison"):
            m.dot_at = self.t + DOT_SEC
        elif base == "paralysis":
            m.jolt_at = self.t + JOLT_EVERY
        elif base == "sleep":
            m.sleep_until = self.t + self.rng.uniform(*SLEEP_SEC)
            self._cancel(vic)
        elif base == "freeze":
            m.frz_until, m.thaw_at = self.t + FREEZE_SEC, self.t + THAW_EVERY
            self._cancel(vic)
        self._emit("status", w=vic.name, s=m.code())
        return True

    def _volatile(self, vic, m, ail, by):
        """물러나면 풀리는 것: 혼란 · 묶임 · 씨뿌리기."""
        if ail == "confusion":
            if self._before(vic.cnf_until) or (by.side != vic.name and self._side_has(vic, "safeguard")):
                return False
            vic.cnf_until = self.t + self.rng.uniform(*CONFUSE_SEC)
            code = "cnf"
        elif ail == "trap":
            vic.trap_until = self.t + TRAP_SEC
            code = "trap"
        else:
            if vic.seed is not None or "GRASS" in m.f.types():
                return False
            vic.seed = [self.t + SEED_SEC, self.t + DOT_SEC, by.side]
            code = "seed"
        self._emit("status", w=vic.name, s=code)
        return True

    def _boost_all(self, s, m, stats, by_foe):
        """능력 랭크 (±6 에서 멈춘다). 상대가 내리는 것은 흰안개가 막는다. 바뀌었으면 True."""
        changed = False
        for stat, change in stats:
            if by_foe and change < 0 and self._side_has(s, "mist"):
                continue
            cur = m.f.stages.get(stat, 0)
            new = _clamp(cur + change, B.STAGE_MIN, B.STAGE_MAX)
            if new != cur:
                m.f.stages[stat] = new
                self._emit("stat", w=s.name, st=stat, d=new - cur)
                changed = True
        return changed

    def _chip(self, s, m, amount, key, ty, src):
        """공식 없이 깎는다 (반동 · 독 · 함정 · 되돌림). 깎은 만큼을 돌려준다."""
        lost = min(m.f.hp, amount)
        m.f.hp -= lost
        self._emit("hit", w=src, v=s.name, k=key, ty=ty, dmg=lost, hpr=_hpr(m.f), eff=1.0, crit=False,
                   x=_r1(s.x), y=_r1(s.y))
        if m.f.hp <= 0 and not m.ko and s.mon is m:
            self._faint(s)
        return lost

    def _heal(self, s, m, amount):
        gain = min(amount, m.f.maxhp - m.f.hp)
        if gain > 0:
            m.f.hp += gain
            self._emit("heal", w=s.name, hpr=_hpr(m.f))

    def _cure(self, s, m):
        code = m.code()
        m.f.status, m.tox = None, 0
        if s.mon is m:
            self._emit("cure", w=s.name, s=code)

    def _faint(self, s):
        m = s.mon
        if m.ko:
            return
        m.ko, m.f.hp = True, 0
        self._cancel(s)
        s.swap = s.push = s.stun = s.buf = None
        s.hs = []
        self._emit("ko", w=s.name, i=s.cur)
        if self.left(s.name):
            s.need_until = self.t + KO_PICK_SEC
            self._emit("need", w=s.name)

    # ---- 강화 · 회복 · 판에 거는 것 ----
    def _self_effects(self, s, m, key, mv):
        """강화 · 회복 꼴의 나머지: 회복 · 잠자기 · 상태 고치기 · cond · 흑안개 · 랭크 베끼기 · 순간이동.
        체력을 깎는 쪽(배북 ...)은 _on_self 가 먼저 깎았다 (_self_cost)."""
        f = m.f
        heal = SM.heal_percent(key, mv, f)              # 날씨로 바뀌는 회복 (달빛 · 아침햇살 · 광합성 ...)
        if heal > 0:
            self._heal(s, m, max(1, int(f.maxhp * heal / 100.0)))
        if mv.get("selfAil"):
            if f.status:
                self._cure(s, m)
            self._inflict(s, mv["selfAil"], m)
        if mv.get("cure"):
            for x in s.mons:
                if x.f.status and not x.ko:
                    self._cure(s, x)
        if mv.get("cond"):
            name, sec = mv["cond"]
            f.cond[name] = True
            s.conds[name] = self.t + sec if sec else 0.0
        if mv.get("haze"):
            for x in self.sides.values():
                if self._present(x):
                    x.mon.f.stages = dict((k, 0) for k in B.STAGE_KEYS)
            self._emit("txt", w=s.name, msg="모든 능력 변화가 원래대로 돌아왔다!")
        if mv.get("stages"):
            self._stages(s, m, mv["stages"])
        if mv.get("blink"):
            ix, iy = self._intent(s)
            dx, dy = _polar(math.degrees(math.atan2(iy, ix)) if (ix or iy) else _facing(s.d), mv["blink"])
            s.x = _clamp(s.x + dx, BODY_R, ARENA_W - BODY_R)
            s.y = _clamp(s.y + dy, BODY_R, ARENA_H - BODY_R)

    def _stages(self, s, m, how):
        """자기암시 copy · 하트스왑 swap · 뒤집어엎기 invert."""
        foe = self._foe(s)
        if not self._present(foe):
            return
        theirs = foe.mon.f
        if how == "copy":
            m.f.stages = dict(theirs.stages)
        elif how == "swap":
            m.f.stages, theirs.stages = dict(theirs.stages), dict(m.f.stages)
        else:
            theirs.stages = dict((k, -v) for k, v in theirs.stages.items())
        self._emit("txt", w=s.name, msg=STAGE_MSG[how])

    def _set_field(self, s, key):
        """날씨 · 필드 · 방 · 진영. 판의 Field 하나에 건다 - battle.damage 와 Fighter.stat 이 그대로 본다."""
        f = self.field
        if key in SM.WEATHER_MOVES:
            f.weather = SM.WEATHER_MOVES[key]
            slot, sec, msg = "weather", FIELD_SEC, FD.WEATHER_START[f.weather]
        elif key in SM.TERRAIN_MOVES:
            f.terrain = SM.TERRAIN_MOVES[key]
            slot, sec, msg = "terrain", FIELD_SEC, FD.TERRAIN_START[f.terrain]
        elif key in SM.ROOM_MOVES:
            room = SM.ROOM_MOVES[key]
            f.rooms[room] = 1
            slot, sec, msg = "room:" + room, FIELD_SEC, FD.ROOM_START[room]
        else:
            name, sec = (SM.SCREENS[key], SCREEN_SEC) if key in SM.SCREENS else (SM.SIDE_MOVES[key][0], FIELD_SEC)
            f.side(FIELD_SIDE[s.name])[name] = 1
            slot, msg = s.name + ":" + name, "%s 효과가 생겼다!" % FD.SIDE_KR[name]
        self.timed[slot] = (self.t + sec, s.name)
        self._emit("txt", w=s.name, msg=msg)

    def _tick_field(self):
        f = self.field
        for slot, (end, who) in list(self.timed.items()):
            if not self._past(end):
                continue
            del self.timed[slot]
            if slot == "weather":
                msg, f.weather = FD.WEATHER_END[f.weather], None
            elif slot == "terrain":
                msg, f.terrain = FD.TERRAIN_END[f.terrain], None
            elif slot.startswith("room:"):
                room = slot[5:]
                f.rooms.pop(room, None)
                msg = FD.ROOM_END.get(room)
            else:
                side, name = slot.split(":")
                f.side(FIELD_SIDE[side]).pop(name, None)
                msg = "%s 효과가 사라졌다!" % FD.SIDE_KR[name]
            if msg:
                self._emit("txt", w=who, msg=msg)

    # ---- 상태이상 시계 ----
    def _tick_status(self, s, m):
        f = m.f
        if f.status in ("burn", "poison") and self._past(m.dot_at):
            m.dot_at += DOT_SEC
            code = m.code()
            if f.status == "burn":
                amount = _part(f.maxhp, 1, 32)
            elif m.tox:
                amount = _part(f.maxhp, m.tox, 48)
                m.tox += 1
            else:
                amount = _part(f.maxhp, 1, 24)
            self._chip(s, m, amount, code, DOT_TYPE[code], s.name)
        elif f.status == "sleep" and self._past(m.sleep_until):
            self._cure(s, m)
        elif f.status == "freeze" and self._past(m.thaw_at):
            m.thaw_at += THAW_EVERY
            if self._past(m.frz_until) or self.rng.uniform(0, 100) < THAW_CHANCE:
                self._cure(s, m)
        elif f.status == "paralysis" and self._past(m.jolt_at):
            m.jolt_at += JOLT_EVERY
            if self.rng.uniform(0, 100) < JOLT_CHANCE:
                self._stun(s, JOLT_SEC, "jolt")
                self._emit("txt", w=s.name, msg="몸이 저려서 움직일 수 없다!")

    def _tick_volatile(self, s, m):
        if s.cnf_until and self._past(s.cnf_until):
            s.cnf_until = 0.0
            self._emit("cure", w=s.name, s="cnf")
        if s.trap_until and self._past(s.trap_until):
            s.trap_until = 0.0
            self._emit("cure", w=s.name, s="trap")
        if s.seed is not None:
            end, nxt, by = s.seed
            if self._past(nxt):
                s.seed[1] = nxt + DOT_SEC
                got = self._chip(s, m, _part(m.f.maxhp, 1, 24), "seed", "GRASS", by)
                seeder = self.sides[by]
                if self._present(seeder):
                    self._heal(seeder, seeder.mon, got)
            if self._past(end) and not m.ko:
                s.seed = None
                self._emit("cure", w=s.name, s="seed")
        for name, end in list(s.conds.items()):
            if end and self._past(end):
                del s.conds[name]
                m.f.cond.pop(name, None)

    # ---- 보이는 것 ----
    def _fighter_view(self, s, mine):
        m, c = s.mon, s.cast
        st, sp = self._state(s)
        v = {"i": s.cur, "x": _r1(s.x), "y": _r1(s.y), "d": s.d, "st": st, "sm": c.slot if c else -1, "sp": sp,
             "s": m.code(), "c": self._conds(s), "stg": dict((k, x) for k, x in m.f.stages.items() if x),
             "inv": self._before(s.inv_until), "hpr": _hpr(m.f),
             "team": [{"slot": x.slot if (mine or x.seen) else None, "hpr": _hpr(x.f), "s": x.code(), "ko": x.ko}
                      for x in s.mons]}
        if mine:
            t = self.t
            v.update(hp=m.f.hp, mhp=m.f.maxhp, cd=[_r1(max(0.0, r - t)) for r in m.ready[:len(m.keys)]],
                     pp=list(m.pp), scd=_r1(max(0.0, s.swap_ready - t)),
                     spd=_r1(self._walk_speed(s) * self._walk_mult(s)), need=s.need_until is not None)
        return v

    def _state(self, s):
        """(st, sp): 지금 모습과 그 단계의 진행 (0~1)."""
        m, c, t = s.mon, s.cast, self.t
        if m.ko or s.need_until is not None:
            return "ko", 0.0
        if s.swap is not None:
            return "swap", _progress(t, s.swap.t0, s.swap.t1)
        if self._hidden(s):
            return "hide", _progress(t, c.start, c.end)
        if m.f.status == "freeze":
            return "frz", 0.0
        if m.f.status == "sleep":
            return "sleep", 0.0
        if s.stun is not None:
            return "stun", _progress(t, s.stun.t0, s.stun.t1)
        if self._staggered(s):                  # 경직도 stun - 하던 기술은 sm 에 그대로
            return "stun", _progress(t, s.hs[-1][0], s.hs[-1][1])
        if c is not None:
            if c.stage == "act" and c.kind in ("guard", "counter"):
                return "guard", _progress(t, c.start, c.end)
            return c.stage, _progress(t, c.start, c.end)
        return ("walk" if (s.vx or s.vy) else "idle"), 0.0

    def _conds(self, s):
        out = []
        if self._before(s.cnf_until):
            out.append("cnf")
        if s.seed is not None:
            out.append("seed")
        if self._before(s.trap_until):
            out.append("trap")
        if s.stun is not None and s.stun.why == "flinch":
            out.append("flinch")
        if any(self._side_has(s, k) for k in SCREEN_KEYS):
            out.append("scr")
        return out

    def _mon_view(self, raw, mine):
        """intro 의 한 마리. 상대 것에는 기술 · 도구 · 체력을 넣지 않는다."""
        f = B.Fighter(self.dex, raw)
        look = f.species or {}
        v = {"key": raw["species"], "num": look.get("num"), "kr": (self.dex.get(raw["species"]) or look).get("kr"),
             "shiny": bool(raw.get("shiny")), "tint": raw.get("tint") if raw.get("shiny") else None,
             "types": f.types()}
        if mine:
            v.update(lv=f.level, mhp=f.maxhp, item=H.name(f.held) if f.held else None,
                     moves=[self._move_view(k, f) for k in f.moves[:4]])
        return v

    def _move_view(self, key, f):
        mv = AM.move_of(self.dex, key) or {}
        kt = AM.kit(self.dex, key)
        return {"key": key, "kr": self.dex.move_name(key), "type": B.shown_type(mv, f) if mv else None,
                "cat": mv.get("cat"), "power": mv.get("power"), "pp": kt["pp"], "kind": kt["kind"], "ok": kt["ok"],
                "why": kt["why"], "desc": mv.get("desc", ""), "sty": kt["sty"], "cd": kt["cd"], "range": kt["range"]}
