# -*- coding: utf-8 -*-
"""백업 파일로 DB 를 되살린다. **지금 들어 있는 것을 덮어쓴다.**

    set POKET_TURSO_URL=libsql://...
    set POKET_TURSO_TOKEN=...
    python tools/restore_db.py --in backup.sql

백업은 표마다 DELETE 를 먼저 하고 INSERT 를 넣는 모양이라, 돌리면 지금
내용이 백업 시점으로 통째로 바뀐다. 되살리기 전에 무엇을 넣을지 세어
보여주고 한 번 더 묻는다.

**스키마는 만들지 않는다.** 표가 없으면 서버를 한 번 띄워서 만들게 한 뒤
돌려야 한다 - 백업이 스키마까지 들고 있으면 그 사이 바뀐 칸을 놓친다.
"""
import argparse
import collections
import io
import os
import re
import sys


def read(path):
    stmts, counts = [], collections.Counter()
    with io.open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("--"):
                continue
            stmts.append(line)
            m = re.match(r"INSERT INTO (\w+)", line)
            if m:
                counts[m.group(1)] += 1
    return stmts, counts


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--in", dest="src", required=True)
    ap.add_argument("--yes", action="store_true", help="묻지 않고 진행")
    args = ap.parse_args()

    if not os.path.exists(args.src):
        print("그런 파일이 없습니다: %s" % args.src)
        return 1
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

    stmts, counts = read(args.src)
    print("백업 안에 든 것")
    for t, n in sorted(counts.items()):
        print("  %-16s %d행" % (t, n))
    if not stmts:
        print("넣을 것이 없습니다.")
        return 1

    conn = libsql.connect(url, auth_token=token)
    print("\n지금 DB")
    for t in sorted(counts):
        try:
            n = conn.execute("SELECT COUNT(*) FROM %s" % t).fetchone()[0]
        except Exception:                                   # noqa: BLE001
            n = "(표 없음 - 서버를 한 번 띄워 스키마를 만들어 주세요)"
        print("  %-16s %s" % (t, n))

    if not args.yes:
        print("\n**지금 들어 있는 것을 덮어씁니다.**")
        if input('계속하려면 "되살립니다" 를 그대로 입력하세요: ').strip() \
                != "되살립니다":
            print("취소했습니다.")
            return 0

    bad = 0
    for i, st in enumerate(stmts):
        try:
            conn.execute(st)
        except Exception as e:                              # noqa: BLE001
            bad += 1
            if bad <= 5:
                print("  실패: %s ... (%s)" % (st[:70], str(e)[:60]))
    conn.commit()
    print("\n%d 문장 중 %d 실패" % (len(stmts), bad))
    for t in sorted(counts):
        try:
            n = conn.execute("SELECT COUNT(*) FROM %s" % t).fetchone()[0]
            print("  %-16s %d행" % (t, n))
        except Exception:                                   # noqa: BLE001
            pass
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
