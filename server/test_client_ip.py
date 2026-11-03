# -*- coding: utf-8 -*-
"""접속자 IP 읽기 검사 (2.1.1, auth.client_ip). 서버를 띄우지 않는다.

    python server/test_client_ip.py

운영은 Caddy 가 바로 앞에 있다 (Cloudflare 없음). Caddy 는 X-Real-IP · X-Forwarded-For 만 덮어쓰고 다른 헤더는
그대로 넘긴다. 예전에는 cf-connecting-ip 를 먼저 믿어서, 그 헤더를 지어 보내면 IP 를 마음대로 바꿀 수 있었다 -
로그인 5번 제한('이름|ip', 숫자 4자리 비밀번호의 유일한 방어선)이 풀렸다. 못 박는 것:

  1. TRUST_CF 를 안 켜면 cf-connecting-ip 는 무시하고 X-Real-IP 를 쓴다.
  2. TRUST_CF 를 켜면(Cloudflare 가 앞에 있는 곳) 그 헤더를 믿는다.
  3. TRUST_PROXY 가 꺼져 있으면 헤더를 하나도 안 믿고 접속한 주소를 쓴다.
"""
import os
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.dirname(HERE))
os.environ["POKET_DB"] = os.path.join(tempfile.mkdtemp(prefix="poket-ip-"), "t.db")
os.environ.pop("POKET_TURSO_URL", None)

from app import auth, config                                      # noqa: E402

OK = FAIL = 0


def chk(name, cond, got=""):
    global OK, FAIL
    if cond:
        OK += 1
        print("  OK   %s" % name)
    else:
        FAIL += 1
        print("  FAIL %s   %r" % (name, got))


class Req(object):
    def __init__(self, host, headers):
        self.headers = headers
        self.client = type("C", (), {"host": host})()


def main():
    rq = Req("172.18.0.5", {"cf-connecting-ip": "6.6.6.6", "x-real-ip": "1.2.3.4"})
    real = (config.TRUST_PROXY, config.TRUST_CF)
    try:
        config.TRUST_PROXY, config.TRUST_CF = True, False
        chk("Cloudflare 가 없으면(기본) cf-connecting-ip 는 무시하고 X-Real-IP", auth.client_ip(rq) == "1.2.3.4",
            auth.client_ip(rq))
        chk("  cf-connecting-ip 만 지어 보내도 접속한 주소 그대로",
            auth.client_ip(Req("9.9.9.9", {"cf-connecting-ip": "6.6.6.6"})) == "9.9.9.9")
        config.TRUST_CF = True
        chk("TRUST_CF 를 켜면 cf-connecting-ip 를 믿는다", auth.client_ip(rq) == "6.6.6.6", auth.client_ip(rq))
        config.TRUST_PROXY, config.TRUST_CF = False, True
        chk("TRUST_PROXY 가 꺼져 있으면 헤더를 안 믿는다", auth.client_ip(rq) == "172.18.0.5", auth.client_ip(rq))
    finally:
        config.TRUST_PROXY, config.TRUST_CF = real
    chk("기본값: TRUST_CF 꺼짐", real[1] is False or os.environ.get("POKET_TRUST_CF"), real)
    print("\n%d개 통과, %d개 실패" % (OK, FAIL))
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
