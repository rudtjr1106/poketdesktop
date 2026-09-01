# -*- coding: utf-8 -*-
"""운영 DB 를 비운다. **되돌릴 수 없다.**

    set POKET_TURSO_URL=libsql://...
    set POKET_TURSO_TOKEN=...
    python tools/wipe_db.py

토큰은 환경변수로만 받는다. 명령줄 인자로 받으면 명령 기록에 남고,
파일에 적어 두면 실수로 커밋된다.

지우기 전에 무엇이 몇 개 있는지 보여주고 한 번 더 묻는다. 계정 수가
예상과 다르면 거기서 멈추면 된다.

표를 하나씩 비운다. 외래키의 ON DELETE CASCADE 에 맡기지 않는 이유는,
연결이 어떻게 잡히느냐에 따라 외래키가 꺼져 있을 수 있고 그러면 주인
없는 행이 조용히 남기 때문이다.

meta 만 남긴다. '어떤 자료 손질까지 끝냈는가' 를 적어 두는 표라, 지우면
다음에 서버가 뜰 때 이미 끝난 손질을 다시 돌린다.
"""
import os
import sys

# 지우는 순서. 참조하는 쪽부터 지운다.
TABLES = [
    "battle", "wild", "wild_state",
    "bag", "seen",
    "pvp_match", "battle_record", "rank_stat",
    "friend", "friend_block",
    "login_fail", "sessions",
    "pokemon",
    "users",
]
KEEP = ["meta"]


def main():
    url = os.environ.get("POKET_TURSO_URL", "").strip()
    token = os.environ.get("POKET_TURSO_TOKEN", "").strip()
    if not url or not token:
        print("POKET_TURSO_URL 과 POKET_TURSO_TOKEN 을 환경변수로 넣어 주세요.")
        print()
        print("  윈도우 (cmd):")
        print("    set POKET_TURSO_URL=libsql://...")
        print("    set POKET_TURSO_TOKEN=...")
        print("    python tools/wipe_db.py")
        return 1

    try:
        import libsql
    except ImportError:
        print("libsql 이 필요합니다:  pip install libsql")
        return 1

    print("붙는 중: %s" % url.split("//")[-1].split(".")[0])
    conn = libsql.connect(url, auth_token=token)

    print("\n지금 들어 있는 것")
    print("  %-16s %s" % ("표", "행 수"))
    print("  " + "-" * 26)
    counts = {}
    for t in TABLES + KEEP:
        try:
            n = conn.execute("SELECT COUNT(*) FROM %s" % t).fetchone()[0]
        except Exception as e:                              # noqa: BLE001
            n = "(없음: %s)" % str(e)[:24]
        counts[t] = n
        mark = "  (남김)" if t in KEEP else ""
        print("  %-16s %s%s" % (t, n, mark))

    users = counts.get("users", 0)
    if not isinstance(users, int) or users == 0:
        print("\n지울 계정이 없습니다.")
        return 0

    print("\n계정 %d개와 거기 딸린 것을 전부 지웁니다." % users)
    print("**되돌릴 수 없습니다.** 백업은 없습니다.")
    ans = input('계속하려면 "지웁니다" 를 그대로 입력하세요: ').strip()
    if ans != "지웁니다":
        print("취소했습니다. 아무것도 건드리지 않았습니다.")
        return 0

    print()
    for t in TABLES:
        try:
            conn.execute("DELETE FROM %s" % t)
            print("  비움: %s" % t)
        except Exception as e:                              # noqa: BLE001
            print("  건너뜀: %s (%s)" % (t, str(e)[:40]))
    conn.commit()

    print("\n남은 행 수")
    for t in TABLES + KEEP:
        try:
            n = conn.execute("SELECT COUNT(*) FROM %s" % t).fetchone()[0]
            print("  %-16s %s" % (t, n))
        except Exception:                                   # noqa: BLE001
            pass
    print("\n끝났습니다. 친구들은 다시 가입하면 됩니다.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
