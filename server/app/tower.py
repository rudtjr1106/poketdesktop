# -*- coding: utf-8 -*-
"""배틀타워 (시즌 7) — 1층부터 차례로 오르는 상시 PvE. 자료와 기록, 보상.

세븐나이츠 무한의 탑을 본떴다 (2026-11-24 사용자). 층마다 정해진 트레이너와 팀이 있고, 아래층을 이겨야
다음 층이 열린다. 보상은 **층마다 처음 이긴 한 번**뿐이고, 져도 잃는 것이 없어 몇 번이든 다시 도전한다.

## 얼개

    자료    data/tower.json (tools/build_tower.py 가 낸다 - 손으로 고치지 않는다)
            층마다 테마 이름 · 트레이너 · 팀 · 보상. **상대 팀은 같은 종 · 같은 도구가 겹쳐도 된다** (사용자 결정) -
            사람 팀에 거는 규칙(pvp.split_restricted · season.rules_v5)은 NPC 팀에 걸지 않는다.
    기록    tower_clear (이긴 층). 가장 높이 이긴 층 + 1 까지만 도전한다. 시즌이 바뀌어도 그대로다.
    판      관장 배틀과 **같은 판**이다 (common/trainer_battle, gym_battle 표, 같은 창). gym_battle.region 에
            "tower:<층>" 을 적어 두고, 끝났을 때 gym_routes.act 가 이쪽(on_win)으로 넘긴다 (악당 boss.py 와 같은 길).
    내 팀   관장과 같다 - 바탕화면 파티, 같은 종 · 전설은 한 마리씩, 도구는 겹쳐도 된다.

## 언제 열리나

config.TOWER_FROM (기본 7) 시즌부터. **부를 때마다** season.SEASON 과 견준다 - 시즌 번호를 import 때 복사해 두지
않는다 (검사가 SEASON 을 바꿔 본다, season.rules_v5 와 같은 약속). 앱은 서버보다 먼저 나가므로, 닫혀 있는 동안에는
개요가 {"open": False, "from": 7} 뿐이다.

## 보상

돈 · 도구 · 알. 칭호는 없다 (사용자). **tower_clear 에 줄이 새로 생겼을 때만** 준다 - 읽어 보고 쓰면 같은 층의 판 둘을
같은 순간에 끝냈을 때 둘 다 '아직 안 이겼다' 로 읽는다 (boss.on_win 과 같은 까닭). 하나를 넣다 오류가 나도 나머지는
넣고 판을 끝낸다 - 오류는 server_error 에 남긴다.
"""
import datetime
import json
import random

from common import trainer_battle as TB

from . import config, db, deps, eggs, errors, items, season

PREFIX = "tower:"
EGG_LINE = "전설의 포켓몬 알"

_DATA = None


def data():
    global _DATA
    if _DATA is None:
        with open(config.TOWER_PATH, encoding="utf-8") as f:
            raw = json.load(f)
        raw["_by_floor"] = dict((x["floor"], x) for x in raw["floors"])
        _DATA = raw
    return _DATA


def total():
    return len(data()["floors"])


def floor(n):
    return data()["_by_floor"].get(n)


# ---------------------------------------------------------------- 시즌 문
def is_open():
    """열렸나. 시즌 번호를 그때그때 본다 (머리말)."""
    return season.SEASON >= config.TOWER_FROM


def closed_text():
    return "배틀타워는 시즌 %d에 열립니다." % config.TOWER_FROM


# ---------------------------------------------------------------- 지역 코드
def region_of(n):
    return "%s%d" % (PREFIX, n)


def is_tower(region):
    return str(region or "").startswith(PREFIX)


def parse(region):
    """"tower:13" -> 13. 아니면 None."""
    if not is_tower(region):
        return None
    try:
        return int(str(region)[len(PREFIX):])
    except ValueError:
        return None


def busy_name(region):
    """다른 판을 열려는 사람에게 알릴 이름 ("배틀타워 13층 과(와)의 승부가 아직 ...")."""
    n = parse(region)
    return "배틀타워 %d층" % n if n else "배틀타워"


# ---------------------------------------------------------------- 진행
def clears(uid):
    return dict((r["floor"], r) for r in db.q("SELECT * FROM tower_clear WHERE user_id=?", (uid,)))


def top(uid):
    """가장 높이 이긴 층. 아직이면 0."""
    r = db.q1("SELECT MAX(floor) m FROM tower_clear WHERE user_id=?", (uid,))
    return int(r["m"] or 0) if r else 0


def _state(n, high):
    return "cleared" if n <= high else ("next" if n == high + 1 else "locked")


def _locked_text(high):
    return "아직 오를 수 없는 층입니다. %d층부터 도전하세요." % (high + 1)


# ---------------------------------------------------------------- 보여주기
def reward_lines(reward):
    """보상을 화면에 적을 글줄로. 돈 -> 도구 -> 알 차례 (주는 차례와 같다)."""
    lines = []
    if reward.get("money"):
        lines.append("상금 %s원" % format(reward["money"], ","))
    for iid, n in reward.get("items") or []:
        lines.append("%s ×%d" % (items.name_of(iid), n))
    if reward.get("egg"):
        lines.append(EGG_LINE)
    return lines


def overview(uid):
    """탭에 그릴 것: 층 목록과 내가 어디까지 올랐나. 닫혀 있으면 언제 열리는지만.

    잠긴 층도 이름 · 레벨 · 마릿수 · 보상은 보인다 - 상대가 누구인지는 다음 층과 이긴 층의 카드(card)에서만.
    """
    if not is_open():
        return {"open": False, "from": config.TOWER_FROM}
    mine = clears(uid)
    high = max(mine) if mine else 0
    floors = []
    for f in data()["floors"]:
        n = f["floor"]
        row = mine.get(n)
        floors.append({"floor": n, "name": f["name"], "kind": f["kind"], "level": f["trainer"]["level"],
                       "size": len(f["trainer"]["team"]), "state": _state(n, high),
                       "reward": reward_lines(f["reward"]), "bestTurns": row["best_turns"] if row else None})
    return {"open": True, "from": config.TOWER_FROM, "total": total(), "top": high, "floors": floors}


def card(uid, n):
    """한 층의 트레이너와 팀(종 · 레벨)과 보상. 다음 층과 이미 이긴 층만 준다.

    기술 · 특성 · 도구는 보내지 않는다 - 붙어 보기 전에 다 알면 재미가 없다 (관장 카드 gym.public 과 같다).
    """
    f = floor(n)
    if not f:
        raise LookupError("그런 층이 없습니다.")
    if not is_open():
        raise ValueError(closed_text())
    mine = clears(uid)
    high = max(mine) if mine else 0
    if n > high + 1:
        raise ValueError(_locked_text(high))
    d = deps.dex()
    t = f["trainer"]
    team = []
    for m in t["team"]:
        sp = d.get(m["species"]) or {}
        team.append({"species": m["species"], "num": sp.get("num"), "kr": sp.get("kr"), "level": m["level"],
                     "types": [d.type_name(x) for x in sp.get("types", [])]})
    row = mine.get(n)
    return {"floor": n, "name": f["name"], "kind": f["kind"], "state": _state(n, high),
            "trainer": {"id": t["id"], "name": t["name"], "role": t["role"], "sprite": t["sprite"],
                        "level": t["level"]},
            "team": team, "reward": reward_lines(f["reward"]),
            "wins": row["wins"] if row else 0, "bestTurns": row["best_turns"] if row else None}


# ---------------------------------------------------------------- 싸우기
def trainer_for(n):
    """TrainerBattle 이 먹는 트레이너. 엔진에 넘길 깃발(noMega · keystone · zring · orb · ai)은 자료에 적혀 있다."""
    return dict(floor(n)["trainer"])


def start(uid, party, n, zring=False, keystone=False, orb=False, rng=None):
    """새 판을 만든다. (region, trainer id, TrainerBattle, 시작 이벤트)

    없는 층은 LookupError, 닫혀 있거나 아직 못 오르는 층은 ValueError.
    """
    if not floor(n):
        raise LookupError("그런 층이 없습니다.")
    if not is_open():
        raise ValueError(closed_text())
    high = top(uid)
    if n > high + 1:
        raise ValueError(_locked_text(high))
    trainer = trainer_for(n)
    tb = TB.TrainerBattle(deps.dex(), party, trainer, rng or random.Random())
    tb.keystone["me"] = keystone
    tb.zring["me"] = zring
    tb.tera_orb["me"] = orb
    return region_of(n), trainer["id"], tb, tb.start()


def _pay(uid, n, reward):
    """보상을 넣고, **실제로 넣은 것만** 글줄로 돌려준다. 하나가 실패해도 나머지는 넣는다.

    못 넣은 것은 둘 다 한다 (검토 11/24): **누구의 몇 층 무엇인지** server_error 에 적고(48시간 남는다), 사람에게도 한 줄로
    알린다. 층 기록은 이미 생겨서 그 보상은 다시 받을 길이 없다 - 말없이 줄만 빠지면 사람은 모르고 운영자는 찾을 수 없다.
    """
    lines, missed = [], []

    def step(give, line, what):
        try:
            give()
            lines.append(line)
        except Exception as e:                                # noqa: BLE001
            missed.append(line)
            errors.record("TOWER", "tower.on_win", e, detail="uid=%s floor=%s %s" % (uid, n, what))

    money = int(reward.get("money") or 0)
    if money:
        step(lambda: items.money_add(uid, money), "상금 %s원" % format(money, ","), "money=%d" % money)
    for iid, cnt in reward.get("items") or []:
        step(lambda iid=iid, cnt=cnt: items.bag_add(uid, iid, cnt), "%s ×%d" % (items.name_of(iid), cnt),
             "item=%s x%d" % (iid, cnt))
    if reward.get("egg"):
        step(lambda: eggs.give(uid, reward["egg"]), EGG_LINE, "egg=%s" % reward["egg"])
    if missed:
        lines.append("일부 보상을 넣지 못했습니다: %s - 게시판 문의에 남겨 주세요." % " · ".join(missed))
    return lines


def on_win(uid, region, turns, now=None):
    """이긴 뒤. 처음 이긴 층이면 보상을 주고, 화면에 띄울 것을 돌려준다 ({"lines": [...]} - 악당 · 아르케와 같은 꼴).

    **같은 층을 두 번 이겨도 한 번만 준다** - tower_clear 에 줄이 새로 생겼을 때만이다 (머리말).
    자료에 없는 층(층 자료를 고치는 배포 사이에 하던 판)은 적지도 주지도 않고 끝낸다.
    """
    n = parse(region)
    f = floor(n) if n else None
    out = {"lines": [], "tower": True, "floor": n, "first": False}
    if not f:
        out["lines"] = ["이 층은 지금 배틀타워에 없다."]
    else:
        stamp = now or datetime.datetime.now(datetime.timezone.utc).replace(microsecond=0).isoformat()
        cur = db.run("INSERT INTO tower_clear (user_id, floor, wins, best_turns, first_at, last_at)"
                     " VALUES (?,?,1,?,?,?) ON CONFLICT(user_id, floor) DO NOTHING",
                     (uid, n, turns, stamp, stamp))
        if getattr(cur, "rowcount", 1) == 1:
            out["first"] = True
            out["lines"] = _pay(uid, n, f["reward"])
            out["lines"].append("%d층이 열렸다." % (n + 1) if floor(n + 1)
                                else "지금 열린 층을 모두 올랐다! 다음 층을 기다려 주세요.")
        else:
            db.run("UPDATE tower_clear SET wins=wins+1, best_turns=MIN(COALESCE(best_turns, ?), ?), last_at=?"
                   " WHERE user_id=? AND floor=?", (turns, turns, stamp, uid, n))
            out["lines"] = ["이미 오른 층이다. 보상은 처음 한 번뿐이다."]
    out.update({"top": top(uid), "total": total(), "money": items.money(uid)})
    return out
