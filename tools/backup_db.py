# -*- coding: utf-8 -*-
"""운영 DB 를 파일 하나로 떠낸다.

    set POKET_TURSO_URL=libsql://...
    set POKET_TURSO_TOKEN=...
    python tools/backup_db.py --out backup.sql

**이 파일에는 닉네임과 비밀번호 해시가 들어 있다.** 아무 데나 두면 안 된다.
비밀번호가 숫자 네 자리라 해시가 새어 나가면 오프라인에서 만 번만 돌려도
뚫린다. 그래서 자동 백업(.github/workflows/backup.yml)은 이 결과를
**암호로 잠근 뒤에** 보관한다.

되살릴 때는 restore_db.py 를 쓴다.
"""
import argparse
import io
import os
import sys

# 떠낼 표. 순서가 곧 되살리는 순서다 - 참조하는 쪽이 뒤에 와야 한다.
TABLES = [
    "meta", "users", "sessions", "pokemon", "wild", "wild_state",
    "battle", "bag", "seen", "login_fail",
    "friend", "friend_block",
    "pvp_match", "battle_record", "rank_stat",
    "server_error",
]


def quote(v):
    if v is None:
        return "NULL"
    if isinstance(v, (int, float)):
        return repr(v)
    if isinstance(v, (bytes, bytearray)):
        return "X'%s'" % v.hex()
    return "'" + str(v).replace("'", "''") + "'"


def dump(conn, out):
    total = 0
    for t in TABLES:
        try:
            cur = conn.execute("SELECT * FROM %s" % t)
            rows = cur.fetchall()
        except Exception as e:                              # noqa: BLE001
            out.write("-- %s: 건너뜀 (%s)\n" % (t, str(e)[:60]))
            continue
        cols = [d[0] for d in cur.description]
        out.write("-- %s: %d행\n" % (t, len(rows)))
        out.write("DELETE FROM %s;\n" % t)
        for r in rows:
            vals = ", ".join(quote(v) for v in r)
            out.write("INSERT INTO %s (%s) VALUES (%s);\n"
                      % (t, ", ".join(cols), vals))
        total += len(rows)
    return total


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="backup.sql")
    args = ap.parse_args()

    url = os.environ.get("POKET_TURSO_URL", "").strip()
    token = os.environ.get("POKET_TURSO_TOKEN", "").strip()
    if not url or not token:
        print("POKET_TURSO_URL 과 POKET_TURSO_TOKEN 이 필요합니다.")
        return 1
    try:
        import libsql
    except ImportError:
        print("libsql 이 필요합니다:  pip install libsql")
        return 1

    conn = libsql.connect(url, auth_token=token)
    with io.open(args.out, "w", encoding="utf-8", newline="\n") as f:
        f.write("-- 포스크탑 백업\n")
        f.write("-- 되살리기: python tools/restore_db.py --in <이 파일>\n")
        n = dump(conn, f)
    size = os.path.getsize(args.out)
    print("%s  (%d행, %.1f KB)" % (args.out, n, size / 1024.0))
    print("주의: 닉네임과 비밀번호 해시가 들어 있습니다. 잠그지 않은 채로"
          " 아무 데나 두지 마세요.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
