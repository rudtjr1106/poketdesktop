# -*- coding: utf-8 -*-
"""한 번만 도는 자료 손질.

db.MIGRATIONS 는 '칸 추가' 만 한다. 없는 칸을 더하는 일이라 몇 번을 돌려도
결과가 같다. 여기 있는 것들은 다르다 — **값을 건드린다.** 두 번 돌면
돈을 두 번 주거나 없는 것을 또 지운다. 그래서 어디까지 끝냈는지 meta 에
적어 두고, 적혀 있으면 건너뛴다.

규칙 셋:
  1) 사용자에게 손해를 끼치지 않는다. 없앨 물건이 있으면 **먼저 값을
     치르고** 그다음에 지운다. 중간에 서버가 죽으면 돈은 줬는데 물건이
     남은 상태가 되는데, 그건 사용자에게 이득이라 괜찮다. 반대로는 안 된다.
  2) 자기 완결적이어야 한다. 지금 카탈로그를 쳐다보면 안 된다 — 물건을
     카탈로그에서 지우는 게 이 손질의 목적이라, 값을 카탈로그에서 찾으면
     이미 없다. 필요한 숫자는 여기 적어 둔다.
  3) 실패해도 서버는 떠야 한다. 손질 하나가 터졌다고 게임 전체가 안 되면
     더 나쁘다. 기록만 남기고 넘어간다.
"""
import datetime

from . import db

# 없앤 회복약과 그때의 매입가. 가방에 남아 있으면 이 값으로 사 준다.
#
# 이 게임에는 배틀 밖으로 체력이 이어지지 않아서 회복약을 쓸 데가 없었다.
# 팔아서 돈으로 바꾸는 물건일 뿐이었고, 상점 '회복' 탭만 차지하고 있었다.
# 그래서 통째로 없애되, 갖고 있던 사람은 팔았을 때와 같은 돈을 받는다.
HEAL_REFUND = {
    "POTION": 100, "SUPERPOTION": 350, "HYPERPOTION": 750,
    "MAXPOTION": 1250, "FULLRESTORE": 1500,
    "ANTIDOTE": 100, "BURNHEAL": 100, "ICEHEAL": 100,
    "AWAKENING": 100, "PARALYZEHEAL": 100, "FULLHEAL": 200,
    "REVIVE": 1000, "MAXREVIVE": 2000, "SACREDASH": 25000,
    "ETHER": 600,
}


def _refund_heals(conn):
    """가방에 남은 회복약을 사 주고 지운다.

    돈을 먼저 주고 물건을 나중에 지운다. 순서가 뒤집히면 중간에 죽었을 때
    사용자가 물건도 돈도 없이 끝난다.
    """
    keys = list(HEAL_REFUND)
    marks = ",".join("?" * len(keys))
    rows = conn.execute(
        "SELECT user_id, item, count FROM bag WHERE item IN (%s) AND count > 0"
        % marks, keys).fetchall()

    owed = {}
    for r in rows:
        uid = r["user_id"] if isinstance(r, dict) else r[0]
        item = r["item"] if isinstance(r, dict) else r[1]
        cnt = r["count"] if isinstance(r, dict) else r[2]
        owed[uid] = owed.get(uid, 0) + HEAL_REFUND.get(item, 0) * cnt

    for uid, money in sorted(owed.items()):
        if money > 0:
            conn.execute("UPDATE users SET money = money + ? WHERE id=?",
                         (money, uid))
    conn.execute("DELETE FROM bag WHERE item IN (%s)" % marks, keys)
    return "%d명에게 %d원" % (len(owed), sum(owed.values()))


# 순서대로 돈다. 이름은 한 번 정하면 바꾸지 않는다 — 이름이 곧 '이미
# 돌았다' 는 표시라서, 바꾸면 다시 돈다.
def _season1_reset(conn):
    """시즌 1 을 연다. 점수와 랜덤 배틀 승패를 처음으로 되돌린다.

    이 판에서 규칙이 바뀌었다 - 이제 **내가 건 판만** 점수와 승패에
    들어간다(pvp._settle). 그전 점수는 걸려온 판까지 섞여 있어서 새 규칙과
    같은 자로 잰 값이 아니다. 그대로 두면 자는 동안 많이 걸린 사람이
    불리한 채로 시즌 1 을 시작한다.

    **건드리지 않는 것 셋.**
      · 친구 배틀 전적(fr_*) - 애초에 점수에 안 들어가는 값이다
      · earned/earned_day - 하루 상금 상한이다. 여기서 지우면 오늘 이미
        받은 사람이 상한을 한 번 더 받는다
      · battle_record - 지난 판 목록은 기록이라 남긴다. 지우고 싶은
        사람은 대전 탭에서 직접 지울 수 있다
    """
    n = conn.execute("SELECT COUNT(*) FROM rank_stat").fetchone()[0]
    conn.execute(
        "UPDATE rank_stat SET rating=1000, best=1000, games=0, wins=0,"
        " losses=0, draws=0, streak=0, ranked=0, updated_at=?",
        (datetime.datetime.now(datetime.timezone.utc).isoformat(),))
    return "%d명 점수 초기화" % n


def _dex_evolved(conn):
    """진화로 얻은 종을 도감에 채운다.

    1.2.3 전에는 진화해도 도감(seen)에 안 올라갔다 (evolution.apply). 잡을
    때만 올리고 있어서, 파이리를 키워 리자드가 돼도 리자드 칸이 비어 있었다.
    지금 가진 포켓몬의 종은 모두 '잡음' 이어야 한다 - 없는 줄은 그 종을
    처음 가진 시각으로 만들고, '봄' 으로만 있던 줄은 '잡음' 으로 올린다.

    잡음을 봄으로 내리는 일은 없어서 사용자에게 손해가 없다. 놓아준
    포켓몬은 행이 지워져서 되살릴 수 없다 - 가진 것만 채운다.
    """
    before = conn.execute(
        "SELECT COUNT(*) FROM seen WHERE caught=1").fetchone()[0]
    # WHERE true 는 지우면 안 된다. INSERT ... SELECT 뒤의 ON CONFLICT 를
    # SQLite 가 조인 조건으로 잘못 읽는다 (공식 문서의 UPSERT 주의 사항).
    conn.execute(
        "INSERT INTO seen (user_id, species, caught, first_at)"
        " SELECT user_id, species, 1, MIN(caught_at) FROM pokemon"
        " WHERE true GROUP BY user_id, species"
        " ON CONFLICT(user_id, species) DO UPDATE SET caught = 1")
    after = conn.execute(
        "SELECT COUNT(*) FROM seen WHERE caught=1").fetchone()[0]
    return "도감 잡음 %d -> %d" % (before, after)


# 시즌 1 보상표. **여기 숫자를 적는다** (규칙 2) - season.py 의 표가 나중에
# 바뀌어도 이미 끝난 시즌 1 의 보상은 그때 정한 그대로여야 한다.
#
# 급은 알로 가른다 (1위 전설, 2~5위 환상). 이로치사탕은 1~10위에 하나씩만 -
# 많이 뿌리면 이로치가 흔해진다. 31위부터는 보상이 없다.
# (첫 등수, 끝 등수, 칭호, 명패, 이로치사탕, 알)
S1_REWARDS = [
    (1, 1, "s1_champion", "gold", 1, "legendary"),
    (2, 5, "s1_elite", "silver", 1, "mythical"),
    (6, 10, "s1_top10", "bronze", 1, None),
    (11, 30, "s1_top30", None, 0, None),
]
S1_TITLE_KR = {
    "s1_champion": "시즌 1 챔피언", "s1_elite": "시즌 1 사천왕",
    "s1_top10": "시즌 1 TOP 10", "s1_top30": "시즌 1 상위권",
}
S1_EGG_KR = {"legendary": "전설의 포켓몬 알", "mythical": "환상의 포켓몬 알"}
S1_FRAME_KR = {"gold": "금빛 명패", "silver": "은빛 명패", "bronze": "동빛 명패"}
S1_GIFT_TITLE = "시즌 1 보상"


def _v(row, key, i):
    return row[key] if not isinstance(row, (tuple, list)) else row[i]


def _season2_open(conn):
    """시즌 1 을 닫고 시즌 2 를 연다.

    순서가 곧 안전장치다 (규칙 1 — 먼저 주고 나중에 지운다).
      1) 시즌 1 순위표를 season_result 에 옮긴다
      2) 순위대로 보상을 선물(gift)로 넣는다. 칭호·명패·이로치사탕은 사용자가
         다음에 켤 때 /api/me 가 지급하면서 '선물이 도착했습니다' 로 알린다
      3) 그다음에 점수를 비운다

    **숨은 점수(MMR)는 절반만 남긴다.** 1000 + (옛 점수 - 1000) x 0.5.
    전부 1000 으로 돌리면 시즌 초에 RP 가 실력과 상관없이 튄다. 그대로 두면
    시즌 1 의 인플레(판을 많이 건 사람이 높았다)가 그대로 넘어온다.
    RP 는 0 부터. 친구 전적·하루 상금 상한·전적 목록은 건드리지 않는다
    (시즌 1 초기화와 같은 이유).

    한 번에 커밋한다 - 중간에 터지면 run() 이 되돌리고 다음에 다시 한다.
    선물을 넣기 전에 같은 제목의 선물이 있는지 보므로 두 번 돌아도 두 번
    안 준다.
    """
    now = datetime.datetime.now(datetime.timezone.utc).replace(
        microsecond=0).isoformat()
    rows = conn.execute(
        "SELECT r.user_id, u.username, r.rating, r.games, r.wins, r.losses,"
        " r.draws FROM rank_stat r JOIN users u ON u.id=r.user_id"
        " WHERE r.ranked=1 ORDER BY r.rating DESC, r.wins DESC").fetchall()

    gifts = candies = n_eggs = 0
    for i, r in enumerate(rows, 1):
        uid = _v(r, "user_id", 0)
        title = frame = egg = None
        n = 0
        for lo, hi, t, f, c, e in S1_REWARDS:
            if lo <= i <= hi:
                title, frame, n, egg = t, f, c, e
                break
        conn.execute(
            "INSERT INTO season_result (season, user_id, rank, name, rating,"
            " rp, tier, games, wins, losses, draws, title, at)"
            " VALUES (1,?,?,?,?,0,NULL,?,?,?,?,?,?)"
            " ON CONFLICT(season, user_id) DO NOTHING",
            (uid, i, _v(r, "username", 1), _v(r, "rating", 2),
             _v(r, "games", 3), _v(r, "wins", 4), _v(r, "losses", 5),
             _v(r, "draws", 6), title, now))
        if title is None:
            continue            # 31위부터는 보관만 하고 보상은 없다
        if conn.execute("SELECT 1 FROM gift WHERE user_id=? AND title=?",
                        (uid, S1_GIFT_TITLE)).fetchone():
            continue
        bits = []
        if egg:
            bits.append(S1_EGG_KR[egg])
        bits.append("칭호 '%s'" % S1_TITLE_KR[title])
        if frame:
            bits.append(S1_FRAME_KR[frame])
        if n:
            bits.append("이로치사탕 %d개" % n)
        msg = "시즌 1 을 %d위로 마쳤습니다. %s을(를) 드립니다. %s은(는) 랭킹 탭에서 바꿀 수 있습니다." % (
            i, ", ".join(bits), "칭호와 명패" if frame else "칭호")
        if n:
            msg += " 이로치사탕은 가방에서 포켓몬에게 먹이면 이로치가 됩니다."
        if egg:
            msg += (" 알은 바탕화면에 나타나고, 게임을 켜 둔 시간만큼 자라서 "
                    "부화합니다.")
        # 한 창에 모여 뜬다. 창의 제목·말은 첫 줄 것을 쓰므로 모든 줄에 같은
        # 말을 적어 둔다. 알이 제일 큰 보상이라 맨 위에 둔다.
        lines = []
        if egg:
            lines.append(("egg", egg, 1))
            n_eggs += 1
        lines.append(("title", title, 1))
        if frame:
            lines.append(("frame", frame, 1))
        if n:
            lines.append(("item", "SHINYCANDY", n))
            candies += n
        for kind, rid, cnt in lines:
            conn.execute(
                "INSERT INTO gift (user_id, kind, item_id, count, title,"
                " message, created_at) VALUES (?,?,?,?,?,?,?)",
                (uid, kind, rid, cnt, S1_GIFT_TITLE, msg, now))
            gifts += 1

    n_all = conn.execute("SELECT COUNT(*) FROM rank_stat").fetchone()[0]
    conn.execute(
        "UPDATE rank_stat SET rating = 1000 + CAST((rating - 1000) / 2 AS INTEGER),"
        " games=0, wins=0, losses=0, draws=0, streak=0, ranked=0,"
        " rp=0, peak_rp=0, win_day='', updated_at=?", (now,))
    conn.execute("UPDATE rank_stat SET best = rating")
    return ("시즌 1 순위 %d명 보관, 선물 %d줄 (알 %d개, 이로치사탕 %d개), %d명 점수 전환"
            % (len(rows), gifts, n_eggs, candies, n_all))


def _egg_slots(conn):
    """1.4.0 에 받은 알에 파티 자리를 준다.

    1.4.0 의 알은 파티 자리와 상관없이 늘 바탕화면에 있었다. 1.4.1 부터 알이
    한 자리를 차지하므로, 자리가 남는 사람은 빈 자리를 주고, 이미 여섯 마리를
    데리고 다니는 사람의 알은 박스로 옮긴다 (누구를 억지로 내리지 않는다).
    """
    rows = conn.execute("SELECT id, user_id FROM egg WHERE hatched_at IS NULL"
                        " ORDER BY id").fetchall()
    party = box = 0
    for r in rows:
        eid, uid = r[0], r[1]
        used = set(x[0] for x in conn.execute(
            "SELECT slot FROM pokemon WHERE user_id=? AND on_desktop=1", (uid,)))
        used |= set(x[0] for x in conn.execute(
            "SELECT slot FROM egg WHERE user_id=? AND on_desktop=1 AND hatched_at IS NULL"
            " AND slot IS NOT NULL AND id<>?", (uid, eid)))
        n = conn.execute("SELECT COUNT(*) FROM pokemon WHERE user_id=? AND on_desktop=1",
                         (uid,)).fetchone()[0]
        n += conn.execute("SELECT COUNT(*) FROM egg WHERE user_id=? AND on_desktop=1"
                          " AND hatched_at IS NULL AND slot IS NOT NULL AND id<>?",
                          (uid, eid)).fetchone()[0]
        free = next((i for i in range(6) if i not in used), None)
        if n < 6 and free is not None:
            conn.execute("UPDATE egg SET on_desktop=1, slot=? WHERE id=?", (free, eid))
            party += 1
        else:
            conn.execute("UPDATE egg SET on_desktop=0, slot=NULL WHERE id=?", (eid,))
            box += 1
    return "알 %d개 파티, %d개 박스" % (party, box)


def _mmr_recenter(conn):
    """숨은 점수를 1000 으로 맞춘다 (기대 승률에 전력을 넣으면서).

    지금까지의 숨은 점수는 전력을 모르는 Elo 라 **전력 우위가 이미 쌓여 있다**
    (운영 76명: 숨은 점수와 팀 전력의 상관 0.59). 이제 기대 승률이 숨은 점수에
    전력비를 따로 곱하므로(season.expected), 그대로 두면 센 팀은 전력을 두 번
    세어 이겨도 거의 못 받고 지면 크게 잃는다. 1000 에서 다시 쌓으면 숨은
    점수에는 전력으로 설명 안 되는 팀 실력만 남는다 (K=32 라 며칠이면 자리 잡는다).

    **건드리지 않는 것.** RP·최고 RP·티어·승패·연승 - 보이는 것은 그대로다.
    best 는 시즌 1 까지 쓰던 칸이라 같이 맞춘다.
    """
    n = conn.execute("SELECT COUNT(*) FROM rank_stat WHERE rating<>1000").fetchone()[0]
    conn.execute("UPDATE rank_stat SET rating=1000, best=1000")
    return "%d명 숨은 점수 1000" % n


ONCE = [
    ("0140-refund-heals", _refund_heals),
    ("0190-season1-reset", _season1_reset),
    ("0250-dex-evolved", _dex_evolved),
    ("0260-season2-open", _season2_open),
    ("0270-egg-slots", _egg_slots),
    ("0280-mmr-recenter", _mmr_recenter),
]


def run():
    """아직 안 끝난 손질을 돈다. db.init() 다음에 부른다."""
    conn = db.connect()
    for name, fn in ONCE:
        key = "mig:" + name
        try:
            done = conn.execute("SELECT v FROM meta WHERE k=?", (key,)).fetchone()
        except Exception as e:                              # noqa: BLE001
            print("[migrate] meta 를 읽지 못했습니다: %s" % e)
            return
        if done:
            continue
        try:
            note = fn(conn)
            conn.execute("INSERT INTO meta (k, v) VALUES (?, ?)",
                         (key, datetime.datetime.now(
                             datetime.timezone.utc).isoformat()))
            conn.commit()
            print("[migrate] %s 완료 (%s)" % (name, note or ""))
        except Exception as e:                              # noqa: BLE001
            # 손질 하나가 터졌다고 서버가 안 뜨면 더 나쁘다. 다음에 다시 해본다.
            # **반쯤 한 것은 되돌린다.** 커밋 안 한 쓰기가 이 연결에 남아
            # 있으면 다음 db.run 의 커밋에 딸려 들어간다 - 선물은 넣었는데
            # '끝냈다' 는 표시가 없어서 다음에 또 넣는 일이 생긴다.
            try:
                conn.rollback()
            except Exception:                               # noqa: BLE001
                pass
            print("[migrate] %s 실패: %s" % (name, e))
            return
