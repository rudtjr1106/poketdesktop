# -*- coding: utf-8 -*-
"""도구 — 목록, 드랍, 가방, 돈, 사용 효과.

가격과 이름은 items.json 이 들고 있고, 그건 PokeAPI CSV 에서 만든다
(tools/build_items.py). 여기서는 그걸 읽어 쓰기만 한다.

드랍은 **등급 안에서 균등 추첨** 이 아니라 도구마다 가중치를 준다.
진화의 돌만 41종이라, 등급 균등으로 뽑으면 특정 돌 하나가 병뚜껑보다
귀해지는 이상한 일이 생기기 때문이다.

돈과 가방을 깎는 쿼리는 전부 `AND ... >= ?` 를 붙인다. 그래야 두 요청이
동시에 들어와도 잔고가 음수로 내려가지 않는다.
"""
import io
import json
import os
import threading

from common import pokelogic as P

from . import config, db

_lock = threading.Lock()
_data = None

STATS = ("hp", "atk", "def", "spa", "spd", "spe")


# ---------------------------------------------------------------- 목록
def data():
    global _data
    if _data is None:
        with _lock:
            if _data is None:
                path = config.ITEMS_PATH
                if not os.path.exists(path):
                    raise RuntimeError("도구 목록이 없습니다: %s" % path)
                with io.open(path, encoding="utf-8") as f:
                    _data = json.load(f)
    return _data


def catalog():
    return data()["items"]


def get(item_id):
    return catalog().get((item_id or "").upper())


def name_of(item_id):
    it = get(item_id)
    return it["kr"] if it else item_id


def sell_price(item_id):
    it = get(item_id)
    return int(it.get("sell", 0)) if it else 0


def buy_price(item_id):
    it = get(item_id)
    if not it or it.get("buyable") is False:
        return 0
    return int(it.get("cost", 0))


def public_list():
    """상점/가방 화면에 뿌릴 목록."""
    out = []
    for it in catalog().values():
        out.append({
            "id": it["id"], "kr": it["kr"], "en": it["en"],
            "cat": it["cat"], "cost": it["cost"], "sell": it["sell"],
            "buyable": it.get("buyable", True) and it["cost"] > 0,
            "rarity": it.get("rarity"),
            "effect": it["effect"],
            "evolves": it.get("evolves", []),
        })
    out.sort(key=lambda x: (x["cat"], x["cost"], x["kr"]))
    return out


# ---------------------------------------------------------------- 드랍
def roll_drop(rng, shiny=False):
    """도구 하나를 뽑는다. 이로치면 여러 번 뽑아 가장 귀한 것을 준다."""
    table = data()["dropTable"]
    total = data()["dropTotal"]

    def once():
        x = rng.random() * total
        for item_id, w in table:
            x -= w
            if x <= 0:
                return item_id
        return table[-1][0]

    picks = [once()]
    if shiny:
        for _ in range(max(0, config.DROP_SHINY_BONUS - 1)):
            picks.append(once())
        cat = catalog()
        picks.sort(key=lambda i: cat[i].get("weight", 999))
    return picks[0]


def drop_public(item_id):
    it = get(item_id)
    return {"id": item_id, "kr": it["kr"] if it else item_id,
            "rarity": (it or {}).get("rarity"),
            "sell": (it or {}).get("sell", 0)}


# ---------------------------------------------------------------- 가방
# 몬스터볼만 예외다. 가방이 생기기 전부터 users.balls 로 따로 세고 있었고,
# 화면 여러 곳(트레이, 도트 우클릭, 관리 창)이 그 값을 본다. 두 군데에
# 나눠 두면 "상점에서 산 볼을 못 쓰는" 일이 생기므로, 몬스터볼은 가방에
# 넣지 않고 항상 users.balls 로 보낸다.
BALL_ITEM = "POKEBALL"


def bag_get(uid):
    out = dict((r["item"], r["count"])
               for r in db.q("SELECT item, count FROM bag WHERE user_id=? AND count>0",
                             (uid,)))
    r = db.q1("SELECT balls FROM users WHERE id=?", (uid,))
    if r and r["balls"]:
        out[BALL_ITEM] = r["balls"]
    return out


def bag_count(uid, item_id):
    if item_id == BALL_ITEM:
        r = db.q1("SELECT balls FROM users WHERE id=?", (uid,))
        return r["balls"] if r else 0
    r = db.q1("SELECT count FROM bag WHERE user_id=? AND item=?", (uid, item_id))
    return r["count"] if r else 0


def bag_add(uid, item_id, n=1):
    if n <= 0:
        return
    if item_id == BALL_ITEM:
        db.run("UPDATE users SET balls = balls + ? WHERE id=?", (n, uid))
        return
    db.run("INSERT INTO bag (user_id, item, count) VALUES (?,?,?)"
           " ON CONFLICT(user_id, item) DO UPDATE SET count = count + ?",
           (uid, item_id, n, n))


def bag_take(uid, item_id, n=1):
    """가진 만큼 있을 때만 뺀다. 뺐으면 True."""
    if item_id == BALL_ITEM:
        cur = db.run("UPDATE users SET balls = balls - ? WHERE id=? AND balls >= ?",
                     (n, uid, n))
        return cur.rowcount > 0
    cur = db.run("UPDATE bag SET count = count - ? WHERE user_id=? AND item=? AND count >= ?",
                 (n, uid, item_id, n))
    return cur.rowcount > 0


# ---------------------------------------------------------------- 돈
def money(uid):
    r = db.q1("SELECT money FROM users WHERE id=?", (uid,))
    return r["money"] if r else 0


def money_add(uid, n):
    if n:
        db.run("UPDATE users SET money = money + ? WHERE id=?", (n, uid))


def money_take(uid, n):
    if n <= 0:
        return True
    cur = db.run("UPDATE users SET money = money - ? WHERE id=? AND money >= ?",
                 (n, uid, n))
    return cur.rowcount > 0


# ---------------------------------------------------------------- 도감(잡아본 종)
def mark_seen(uid, species, caught, now):
    db.run("INSERT INTO seen (user_id, species, caught, first_at) VALUES (?,?,?,?)"
           " ON CONFLICT(user_id, species) DO UPDATE SET caught = MAX(caught, ?)",
           (uid, species, int(bool(caught)), now, int(bool(caught))))


def has_caught(uid, species):
    r = db.q1("SELECT caught FROM seen WHERE user_id=? AND species=?", (uid, species))
    return bool(r and r["caught"])


# ---------------------------------------------------------------- 볼 보정
# 본가처럼 상황을 보고 배율이 달라지는 볼들.
def ball_bonus(item_id, dex, wild, mine=None, turn=0, uid=None, hour=None):
    """이 볼을 지금 던지면 배율이 얼마인지."""
    it = get(item_id)
    if not it or it["effect"].get("kind") != "ball":
        return 1.0
    eff = it["effect"]
    base = float(eff.get("mult", 1.0))
    cond = eff.get("cond")
    if not cond:
        return base

    sp = dex.get(wild["species"]) or {}
    lv = int(wild.get("level", 1))

    if cond == "water_or_bug":
        types = sp.get("types", [])
        return base if ("WATER" in types or "BUG" in types) else 1.0

    if cond == "low_level":
        # 본가 네스트볼: (41 - 상대레벨) / 10, 1 미만이면 1
        return max(1.0, min(base, (41.0 - lv) / 10.0))

    if cond == "many_turns":
        # 본가 타이머볼: 1 + 턴 * 0.3, 최대 4
        return max(1.0, min(base, 1.0 + turn * 0.3))

    if cond == "first_turn":
        return base if turn <= 0 else 1.0

    if cond == "night":
        h = hour if hour is not None else _server_hour()
        return base if (h >= 20 or h < 4) else 1.0

    if cond == "level_gap":
        # 본가 레벨볼
        my = int((mine or {}).get("level", 0))
        if my >= lv * 4:
            return 8.0
        if my >= lv * 2:
            return 4.0
        if my > lv:
            return 2.0
        return 1.0

    if cond == "moon_family":
        return base if _uses_stone(dex, wild["species"], "MOONSTONE") else 1.0

    if cond == "fast_species":
        return base if sp.get("base", {}).get("spe", 0) >= 100 else 1.0

    if cond == "heavy":
        # 본가 헤비볼은 포획률에 더한다. 여기서는 곱으로 근사한다.
        w = sp.get("weight", 0)
        rate = max(1, sp.get("catch", 45))
        add = -20 if w < 100 else (0 if w < 200 else (20 if w < 300 else 30))
        return max(0.1, (rate + add) / float(rate))

    if cond == "same_species_other_gender":
        m = mine or {}
        if m.get("species") != wild.get("species"):
            return 1.0
        g1, g2 = m.get("gender", "N"), wild.get("gender", "N")
        return base if (g1 in "MF" and g2 in "MF" and g1 != g2) else 1.0

    if cond == "asleep":
        return base if (wild.get("status") == "SLP") else 1.0

    if cond == "already_caught":
        return base if (uid and has_caught(uid, wild["species"])) else 1.0

    return base


def _server_hour():
    import datetime
    return datetime.datetime.now().hour


def _uses_stone(dex, species, stone_id):
    sp = dex.get(species) or {}
    return any(b.get("item") == stone_id for b in sp.get("evo", []))


def ball_extra(item_id):
    """잡은 뒤에 걸리는 부가 효과. (완전회복은 이 게임에 의미 없음)"""
    it = get(item_id)
    note = (it or {}).get("effect", {}).get("note", "")
    ident = (it or {}).get("ident", "")
    if ident == "friend-ball":
        return {"happiness": 200}
    if ident == "luxury-ball":
        return {"happinessRate": 2}
    return {}


# ---------------------------------------------------------------- 사용
def clamp_evs(evs):
    """스탯당 252, 총합 510 을 넘지 않게 자른다."""
    out = {}
    for s in STATS:
        out[s] = max(0, min(config.EV_STAT_MAX, int(evs.get(s, 0))))
    over = sum(out.values()) - config.EV_TOTAL_MAX
    if over > 0:
        for s in STATS:
            take = min(out[s], over)
            out[s] -= take
            over -= take
            if over <= 0:
                break
    return out


def add_evs(evs, gain):
    """노력치를 더한다. 총합 상한에 걸리면 걸린 만큼만 들어간다."""
    cur = clamp_evs(evs)
    total = sum(cur.values())
    for s in STATS:
        g = int(gain.get(s, 0))
        if not g:
            continue
        room_stat = config.EV_STAT_MAX - cur[s]
        room_total = config.EV_TOTAL_MAX - total
        if g > 0:
            g = min(g, room_stat, room_total)
        else:
            g = max(g, -cur[s])
        cur[s] += g
        total += g
    return cur
