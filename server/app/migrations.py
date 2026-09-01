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
ONCE = [
    ("0140-refund-heals", _refund_heals),
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
            print("[migrate] %s 실패: %s" % (name, e))
            return
