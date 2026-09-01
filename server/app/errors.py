# -*- coding: utf-8 -*-
"""서버 오류를 남기고 세어 본다.

예전에는 예외가 나도 print 뿐이라, Render 대시보드를 직접 열어 봐야
알 수 있었다. 사용자는 "가끔 오류가 뜬다" 고만 말할 수 있고 그 사이
무슨 일이 있었는지는 아무도 모른다.

여기 남겨 두면 **이미 5분마다 도는 keepalive 가 대신 봐 준다.** 감시
장치를 새로 두지 않아도 되고, 많이 나면 워크플로가 실패해서 GitHub 이
알아서 메일을 보낸다.

**오류를 남기다가 오류가 나면 안 된다.** 여기서 예외가 새어 나가면
원래 응답까지 망가뜨린다. 그래서 전부 감싸 두고, 실패하면 조용히 넘어간다.
"""
import datetime

from . import db

# 이만큼 지난 기록은 지운다. 진단용이지 보관용이 아니다.
KEEP_HOURS = 48

# 한 번에 남기는 자세한 내용의 길이. 역추적 전체를 넣으면 표가 금방 커진다.
DETAIL_MAX = 1200


def _now():
    return datetime.datetime.now(datetime.timezone.utc)


def record(method, path, exc, detail=""):
    """오류 하나를 남긴다. 실패해도 조용히 넘어간다."""
    try:
        db.run("INSERT INTO server_error (at, path, method, kind, detail)"
               " VALUES (?,?,?,?,?)",
               (_now().isoformat(), (path or "")[:200], (method or "")[:10],
                type(exc).__name__[:60], (detail or str(exc))[:DETAIL_MAX]))
    except Exception:                                       # noqa: BLE001
        pass


def sweep():
    """오래된 기록을 치운다. 서버가 뜰 때 한 번."""
    try:
        cut = (_now() - datetime.timedelta(hours=KEEP_HOURS)).isoformat()
        db.run("DELETE FROM server_error WHERE at < ?", (cut,))
    except Exception:                                       # noqa: BLE001
        pass


def summary(minutes=60):
    """최근 얼마 동안 오류가 몇 번 났는지. /api/health 에 실어 보낸다.

    자세한 내용은 넣지 않는다. health 는 인증 없이 누구나 볼 수 있어서,
    역추적이 그대로 나가면 서버 안쪽 구조가 드러난다. 숫자와 어디서
    났는지 정도만 준다.
    """
    try:
        cut = (_now() - datetime.timedelta(minutes=minutes)).isoformat()
        n = db.q1("SELECT COUNT(*) c FROM server_error WHERE at >= ?",
                  (cut,))["c"]
        last = db.q1("SELECT at, path, kind FROM server_error"
                     " ORDER BY id DESC LIMIT 1")
        out = {"count": n, "windowMinutes": minutes}
        if last:
            out["last"] = {"at": last["at"], "path": last["path"],
                           "kind": last["kind"]}
        return out
    except Exception:                                       # noqa: BLE001
        return {"count": 0, "windowMinutes": minutes}


def recent(limit=50):
    """자세한 내용까지. 인증된 사람만 볼 수 있는 곳에서 쓴다."""
    rows = db.q("SELECT * FROM server_error ORDER BY id DESC LIMIT ?",
                (limit,))
    return [{"at": r["at"], "method": r["method"], "path": r["path"],
             "kind": r["kind"], "detail": r["detail"]} for r in rows]
