# -*- coding: utf-8 -*-
"""파티 대 파티 전투 — 유저끼리 붙일 때 쓴다.

battle.Battle 은 1:1 전용이다. 여기서는 그걸 **감싸기만** 한다. 고치지
않는다 — 야생 배틀이 그 위에서 돌고 있고, 그게 깨지는 게 제일 나쁘다.

진행은 본가의 배틀타워와 같다. 앞선 두 마리가 붙고, 쓰러진 쪽이 다음
포켓몬을 내보낸다. 한쪽이 전멸하면 끝난다. 사람이 개입하지 않는다 —
양쪽 다 기술을 알아서 고른다.

**결과는 시드 하나로 정해진다.** 같은 팀, 같은 시드면 언제 몇 번을
돌려도 같은 로그가 나온다. 그래서 서버가 매칭 순간 한 번만 계산해서
로그로 저장하고, 양쪽 클라이언트는 그 로그를 재생하기만 하면 된다.
턴마다 서버를 왕복할 필요가 없고, 재생 도중 앱이 꺼져도 승패는 이미
확정되어 있다.

로그에 담기는 이벤트는 Battle 이 내는 것 그대로에 세 가지를 더한다.

    {"t": "round", "n": 1, "me": {...}, "foe": {...}}   라운드 시작(선수 소개)
    {"t": "ko",    "side": "me"|"foe"|"both"}           라운드 끝
    {"t": "match", "winner": "me"|"foe"|"draw", ...}    판 끝

Battle 이 내는 "over" 는 1:1 기준이라(한 라운드가 끝날 때마다 나온다)
여기서 걸러낸다. 재생기는 "over" 를 몰라야 한다.

시점은 **항상 a 쪽 기준**이다. me = a, foe = b. b 쪽 화면에서는
클라이언트가 재생 직전에 한 번 뒤집는다.
"""
import random

from . import battle as B

# 한 라운드(1:1)에 쓸 수 있는 턴 수. 야생의 80 보다 훨씬 짧다.
# 6:6 이면 최대 여섯 라운드라, 라운드마다 80턴을 주면 한 판이 480턴까지
# 늘어난다. 그걸 도트로 재생하면 몇 분이 걸린다. 30턴이면 웬만한 라운드는
# 안에서 끝나고, 안 끝나면 양쪽 다 물러나는 것으로 친다.
ROUND_TURNS = 30
# 이미 나와 있는 선수에게 주는 웃돈. 이만큼 차이가 안 나면 안 바꾼다.
# 교체에도 한 턴이 드는 셈이라 조금 유리한 정도로는 바꾸지 않는다.
SWITCH_MARGIN = 1.5

# 판 전체의 안전장치. 라운드 수 × ROUND_TURNS 를 넘길 일은 없지만,
# 어딘가 잘못되어 라운드가 안 끝나면 여기서 멈춘다.
MAX_ROUNDS = 16


def _side_view(f):
    """선수 소개에 쓸 정보. 화면이 도트를 띄우는 데 필요한 것까지 담는다."""
    # 도감 번호는 mon 에 없을 수 있다(야생으로 뽑은 개체에는 없다).
    # Fighter 가 이미 도감 항목을 들고 있으니 거기서 가져온다 - 화면이
    # 도트를 찾을 때 쓰는 값이라 비면 아무것도 안 뜬다.
    sp = f.species or {}
    return {"name": f.name, "species": f.mon.get("species"),
            "num": f.mon.get("num") or sp.get("num"),
            "level": f.mon.get("level"),
            "shiny": bool(f.mon.get("shiny")), "hp": f.hp, "maxhp": f.maxhp,
            "gender": f.mon.get("gender")}


class PartyBattle(object):
    """파티끼리 한 판.

        pb = PartyBattle(dex, a_mons, b_mons, seed=12345)
        out = pb.run()
        out["winner"]   "me"(a 승) / "foe"(b 승) / "draw"
        out["events"]   재생할 이벤트 목록
        out["turns"]    총 턴 수
    """

    def __init__(self, dex, a_mons, b_mons, seed=None):
        if not a_mons or not b_mons:
            # 엔진이 정책을 갖지는 않지만, 여기서 안 막으면 아래에서
            # team[0] 이 IndexError 를 내고 서버가 500 을 뱉는다.
            raise ValueError("양쪽 다 최소 한 마리는 있어야 합니다.")
        self.dex = dex
        self.seed = random.randrange(1 << 30) if seed is None else int(seed)
        self.rng = random.Random(self.seed)
        self.a = [B.Fighter(dex, m) for m in a_mons]
        self.b = [B.Fighter(dex, m) for m in b_mons]
        self.ia = self.ib = 0          # 지금 나와 있는 선수의 자리
        self.events = []
        self.turns = 0
        self.winner = None

    # ---------------- 도구 ----------------
    def _alive(self, team, start):
        """start 부터 살아 있는 첫 자리. 없으면 None."""
        for i in range(start, len(team)):
            if team[i].alive():
                return i
        return None

    def _matchup(self, mine, foe):
        """이 조합이 나에게 얼마나 유리한가. 클수록 좋다.

        공격 쪽 - 내 기술이 상대 타입에 얼마나 잘 박히나 (제일 잘 박히는 것)
        수비 쪽 - 상대 타입이 나를 얼마나 잘 때리나 (제일 아픈 것)
        둘을 나눈다. 2배로 때리고 0.5배로 맞으면 4, 반대면 0.25.

        기술을 실제로 보고 판단한다. 타입만 보면 '불꽃이 풀에게 유리' 인데
        정작 불꽃 기술이 하나도 없는 경우를 놓친다.
        """
        foe_types = (foe.species or {}).get("types", []) or []
        my_types = (mine.species or {}).get("types", []) or []

        atk = 0.0
        for key in mine.moves:
            md = self.dex.move(key) or {}
            if not md.get("power"):
                continue                       # 변화기는 상성과 무관하다
            e = B.effectiveness(self.dex, md.get("type"), foe_types)
            if e > atk:
                atk = e
        if atk <= 0:
            atk = 0.25                         # 때릴 수단이 없다시피 하다

        dfn = 0.0
        for key in foe.moves:
            md = self.dex.move(key) or {}
            if not md.get("power"):
                continue
            e = B.effectiveness(self.dex, md.get("type"), my_types)
            if e > dfn:
                dfn = e
        if dfn <= 0:
            dfn = 0.25

        # 체력이 많이 남은 쪽을 조금 더 쳐준다. 상성이 같으면 성한 애가 낫다.
        health = 0.6 + 0.4 * (mine.hp / float(mine.maxhp or 1))
        return (atk / dfn) * health

    def _pick_against(self, team, foe, cur=None):
        """상대에게 제일 잘 맞는 선수의 자리.

        같은 점수면 **앞자리를 고른다.** 무작위를 쓰지 않는다 - PVP 는
        서버가 계산한 로그를 그대로 재생하는 구조라, 여기에 rng 를 넣으면
        나중에 조건 하나만 고쳐도 이전 판들과 어긋난다.
        """
        best, best_score = None, None
        for i, f in enumerate(team):
            if not f.alive():
                continue
            sc = self._matchup(f, foe)
            # 이미 나와 있는 애는 조금 더 쳐준다. 점수가 비슷한데 굳이
            # 바꾸면 한 턴을 버리는 셈이다(교체에도 턴이 든다).
            if cur is not None and i == cur:
                sc *= SWITCH_MARGIN
            if best_score is None or sc > best_score:
                best, best_score = i, sc
        return best

    def _round_battle(self):
        """지금 선수 둘로 1:1 한 라운드를 만든다."""
        # ai="trainer" 를 반드시 준다. 기본값은 "wild" 라 상대가 기술을
        # 무작위로 고른다 - 내 쪽은 choose_mine 이 알아서 'trainer' 로
        # 고르기 때문에, 빠뜨리면 a 가 머리를 쓰고 b 는 아무 기술이나
        # 쓰는 판이 된다. 실제로 600판을 돌려 보니 a 가 69% 를 이겼다.
        bt = B.Battle(self.dex, self.a[self.ia], self.b[self.ib], self.rng,
                      ai="trainer")
        # 상대가 야생이 아니다. 문구에서 '야생' 을 뗀다.
        bt.foe_prefix = ""
        bt.max_turns = ROUND_TURNS
        return bt

    # ---------------- 진행 ----------------
    def run(self):
        # 명단을 맨 앞에 넣는다. 화면은 시작하자마자 양쪽 여섯 마리를
        # 다 세워야 하는데, 라운드 이벤트에는 실제로 링에 나온 애들만
        # 담긴다 - 일찍 끝나면 뒤쪽 선수는 로그에 아예 안 나온다.
        # me/foe 키라서 시점 뒤집기(flip)가 그대로 처리해 준다.
        self.events.append({"t": "teams",
                            "me": [_side_view(f) for f in self.a],
                            "foe": [_side_view(f) for f in self.b]})
        for n in range(1, MAX_ROUNDS + 1):
            # **자리 번호를 같이 보낸다.** 예전에는 화면이 "쓰러지지 않은
            # 첫 자리" 로 스스로 계산했는데, 그러면 서버가 순서를 바꿔
            # 내보내는 순간 다른 포켓몬이 나온다. 오류도 안 난다.
            self.events.append({"t": "round", "n": n,
                                "mi": self.ia, "fi": self.ib,
                                "me": _side_view(self.a[self.ia]),
                                "foe": _side_view(self.b[self.ib])})
            side = self._one_round()
            self.events.append({"t": "ko", "side": side})
            if self._advance(side):
                break
        if self.winner is None:
            # 라운드 상한까지 왔는데 양쪽 다 남아 있다. 머릿수로 가른다.
            self.winner = self._by_headcount()
        self.events.append({"t": "match", "winner": self.winner,
                            "turns": self.turns, "rounds": n})
        return {"winner": self.winner, "turns": self.turns,
                "events": self.events, "seed": self.seed}

    def _one_round(self):
        """한 라운드를 끝까지. 누가 쓰러졌는지("me"/"foe"/"both") 돌려준다."""
        bt = self._round_battle()
        while not bt.over:
            ev = bt.take_turn(bt.choose_mine())
            self.turns += 1
            # Battle 의 "over" 는 1:1 기준이라 라운드마다 나온다.
            # 그대로 흘리면 재생기가 판이 끝난 줄 안다.
            self.events.extend(e for e in ev if e.get("t") != "over")

        a_down = not self.a[self.ia].alive()
        b_down = not self.b[self.ib].alive()
        if a_down and b_down:
            return "both"
        if a_down:
            return "me"
        if b_down:
            return "foe"
        # 아무도 안 쓰러졌는데 라운드가 끝났다 = 턴 상한(무승부).
        # 양쪽 다 물러나는 것으로 친다. 한쪽만 물리면 화면에서 한 마리가
        # 링에 남은 채로 다음 선수와 겹친다.
        return "both"

    def _advance(self, side):
        """쓰러진 쪽의 다음 선수를 내보낸다. 판이 끝났으면 True.

        양쪽을 다 본 뒤에 판정한다. 한쪽을 보고 바로 돌아가면 둘이 동시에
        전멸했을 때 무승부가 아니라 한쪽 승리가 된다.
        """
        a_out = b_out = False
        # **상성이 유리한 쪽을 내보낸다.** 예전에는 무조건 살아 있는
        # 첫 자리였다. 순서대로 나가서 물 타입 앞에 불 타입이 계속
        # 나가는 일이 벌어졌다.
        #
        # 상대를 보고 고르므로 순서가 중요하다. 양쪽이 같이 쓰러졌을 때는
        # a 가 먼저 (지금 b 를 보고) 고르고, 그다음 b 가 (새 a 를 보고)
        # 고른다. 완전히 공평하진 않지만 **결정적**이고, 서로를 보고
        # 무한히 다시 고르는 것을 피한다.
        if side in ("me", "both"):
            nxt = self._pick_against(self.a, self.b[self.ib])
            if nxt is None:
                a_out = True
            else:
                self.ia = nxt
        if side in ("foe", "both"):
            nxt = self._pick_against(self.b, self.a[self.ia])
            if nxt is None:
                b_out = True
            else:
                self.ib = nxt

        if a_out and b_out:
            self.winner = "draw"
        elif a_out:
            self.winner = "foe"
        elif b_out:
            self.winner = "me"
        else:
            return False
        return True

    def _by_headcount(self):
        """상한까지 안 끝났을 때. 남은 마릿수 -> 남은 체력 비율 순으로."""
        na = sum(1 for f in self.a if f.alive())
        nb = sum(1 for f in self.b if f.alive())
        if na != nb:
            return "me" if na > nb else "foe"
        ra = sum(f.hp / float(f.maxhp or 1) for f in self.a)
        rb = sum(f.hp / float(f.maxhp or 1) for f in self.b)
        if abs(ra - rb) < 1e-9:
            return "draw"
        return "me" if ra > rb else "foe"


def simulate(dex, a_mons, b_mons, seed=None):
    """한 줄로 쓰는 입구."""
    return PartyBattle(dex, a_mons, b_mons, seed).run()


# 시점 뒤집기 --------------------------------------------------------
# 저장된 로그는 항상 a 시점이다. b 쪽 화면에서는 이걸 통과시켜 뒤집는다.
# 뒤집을 것을 한 군데 모아 둔다 - 흩어 놓으면 하나를 빠뜨리고, 그러면
# 진 쪽 화면에서만 체력바가 반대로 나오는 식으로 조용히 어긋난다.
_FLIP = {"me": "foe", "foe": "me"}


def flip(ev):
    """이벤트 하나를 상대 시점으로."""
    out = dict(ev)
    for k in ("who", "side", "target", "winner"):
        if out.get(k) in _FLIP:
            out[k] = _FLIP[out[k]]
    if "me" in out or "foe" in out:
        me, foe = out.get("me"), out.get("foe")
        if me is not None:
            out["foe"] = me
        if foe is not None:
            out["me"] = foe
    # 자리 번호도 같이 뒤집는다. 안 그러면 상대 화면에서 엉뚱한 자리의
    # 포켓몬이 링으로 나온다.
    if "mi" in out or "fi" in out:
        mi, fi = out.get("mi"), out.get("fi")
        if mi is not None:
            out["fi"] = mi
        if fi is not None:
            out["mi"] = fi
    return out


def flip_log(events):
    return [flip(e) for e in events]
