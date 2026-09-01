# -*- coding: utf-8 -*-
r"""DB 를 다른 Turso 로 옮긴다.

    set POKET_FROM_URL=libsql://지금-쓰는-것...
    set POKET_FROM_TOKEN=...
    set POKET_TO_URL=libsql://새로-만든-것...
    set POKET_TO_TOKEN=...
    python tools/move_db.py

받는 쪽은 Turso 여도 되고 **그냥 파일 경로여도 된다.** 서버 한 대에
SQLite 로 내려앉힐 때 이걸 쓴다 - 뽑은 파일은 파이썬 기본 sqlite3 로
그대로 열리고, 비밀번호 해시(BLOB)도 그대로 넘어간다.

    set POKET_TO_URL=D:\poket.db
    set POKET_TO_TOKEN=아무거나

지역을 맞추려고 이걸 쓰지는 마라. **Turso 에는 싱가포르가 없다** -
도쿄·뭄바이·아일랜드·버지니아·오하이오·오리건뿐이고, 무료 등급은
group 이 하나라 위치를 바꿀 수도 없다. 자세한 건 docs/운영.md 를 보라.

이 도구가 하는 일:
  1. 지금 DB 에서 전부 떠낸다
  2. 새 DB 에 **표를 만든다** (서버를 먼저 띄울 필요가 없다)
  3. 떠낸 것을 넣는다
  4. 양쪽 행 수를 맞춰 본다

**지금 DB 는 건드리지 않는다.** 새 쪽이 잘못돼도 되돌아갈 곳이 남는다.
"""
import io
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "server"))


def main():
    src_url = os.environ.get("POKET_FROM_URL", "").strip()
    src_tok = os.environ.get("POKET_FROM_TOKEN", "").strip()
    dst_url = os.environ.get("POKET_TO_URL", "").strip()
    dst_tok = os.environ.get("POKET_TO_TOKEN", "").strip()
    miss = [k for k, v in [("POKET_FROM_URL", src_url),
                           ("POKET_FROM_TOKEN", src_tok),
                           ("POKET_TO_URL", dst_url),
                           ("POKET_TO_TOKEN", dst_tok)] if not v]
    if miss:
        print("이 값들이 필요합니다: %s" % ", ".join(miss))
        return 1
    if src_url == dst_url:
        print("보내는 곳과 받는 곳이 같습니다.")
        return 1
    try:
        import libsql
    except ImportError:
        print("libsql 이 필요합니다:  pip install libsql")
        return 1

    from app import db as appdb
    import importlib.util
    sp = importlib.util.spec_from_file_location(
        "bk", os.path.join(os.path.dirname(os.path.abspath(__file__)),
                           "backup_db.py"))
    bk = importlib.util.module_from_spec(sp)
    sp.loader.exec_module(bk)

    print("보내는 곳: %s" % src_url.split("//")[-1].split(".")[0])
    print("받는 곳  : %s" % dst_url.split("//")[-1].split(".")[0])
    src = libsql.connect(src_url, auth_token=src_tok)
    dst = libsql.connect(dst_url, auth_token=dst_tok)

    print("\n1. 지금 DB 를 떠냅니다")
    tmp = "move-backup.sql"
    with io.open(tmp, "w", encoding="utf-8", newline="\n") as f:
        n = bk.dump(src, f)
    print("   %d행  (%s 에 남겨 뒀습니다)" % (n, tmp))

    print("\n2. 새 DB 에 표를 만듭니다")
    # 서버가 뜰 때 만드는 것과 같은 스키마를 쓴다. 그래야 칸이 어긋나지 않는다.
    made = 0
    for stmt in appdb.SCHEMA.split(";"):
        t = stmt.strip()
        if not t or t.upper().startswith("PRAGMA"):
            continue
        try:
            dst.execute(t)
            made += 1
        except Exception as e:                              # noqa: BLE001
            print("   건너뜀: %s (%s)" % (t[:44], str(e)[:40]))
    # 나중에 더한 칸들(MIGRATIONS)도 같이 넣는다
    for table, col, sql in appdb.MIGRATIONS:
        try:
            dst.execute(sql)
        except Exception:                                   # noqa: BLE001
            pass                      # 이미 있으면 그만이다
    dst.commit()
    print("   문장 %d개 실행" % made)

    print("\n3. 넣습니다")
    bad = 0
    with io.open(tmp, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("--"):
                continue
            try:
                dst.execute(line)
            except Exception as e:                          # noqa: BLE001
                bad += 1
                if bad <= 5:
                    print("   실패: %s ... (%s)" % (line[:60], str(e)[:50]))
    dst.commit()
    print("   실패한 문장 %d개" % bad)

    print("\n4. 양쪽을 맞춰 봅니다")
    ok = True
    print("   %-16s %8s %8s" % ("표", "원래", "새 곳"))
    for t in bk.TABLES:
        try:
            a = src.execute("SELECT COUNT(*) FROM %s" % t).fetchone()[0]
        except Exception:                                   # noqa: BLE001
            continue
        try:
            b = dst.execute("SELECT COUNT(*) FROM %s" % t).fetchone()[0]
        except Exception:                                   # noqa: BLE001
            b = "(표 없음)"
        same = (a == b)
        ok = ok and same
        if a or not same:
            print("   %-16s %8s %8s %s" % (t, a, b, "" if same else "  <-- 다름"))

    print()
    if ok and not bad:
        print("옮겼습니다. 이제 Render 환경변수를 새 주소로 바꾸세요:")
        print("  POKET_TURSO_URL   = %s" % dst_url)
        print("  POKET_TURSO_TOKEN = (새 토큰)")
        print()
        print("바꾼 뒤 /api/health 가 200 이면 끝입니다.")
        print("**지금 DB 는 그대로 두세요.** 며칠 써 보고 문제가 없으면 그때 지우면 됩니다.")
        return 0
    print("맞지 않는 곳이 있습니다. 환경변수를 바꾸지 마세요.")
    print("지금 DB 는 건드리지 않았으니 그대로 쓰시면 됩니다.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
