import sys, datetime, json
sys.path.insert(0, "/app")
from app import db, walk
db.init()
ok=fail=0
def chk(n,c,g=""):
    global ok,fail
    if c: ok+=1; print("  OK   %s"%n)
    else: fail+=1; print("  FAIL %s   %s"%(n,g))
def mkuser(name, n=3, happy=70, luxury=False):
    cur=db.run("INSERT INTO users (username,pw_hash,pw_salt,pw_iter,balls,money,"
               "created_at,last_login,last_ip) VALUES (?,?,?,1,10,0,?,?,'')",
               (name,b"x",b"x",walk._now().isoformat(),walk._now().isoformat()))
    uid=cur.lastrowid
    for i in range(n):
        db.run("INSERT INTO pokemon (user_id,species,level,exp,nature,ability,"
               "hidden_ability,gender,shiny,happiness,ivs,evs,moves,on_desktop,"
               "slot,met_level,caught_at,luxury) VALUES (?,?,?,?,?,?,0,?,0,?,?,?,?,?,?,?,?,?)",
               (uid,"EEVEE",30,0,"HARDY","RUNAWAY","M",happy,"{}","{}","[]",
                1 if i<2 else 0, i, 30, walk._now().isoformat(), int(luxury)))
    return uid
def happy(uid):
    return [r["happiness"] for r in db.q(
        "SELECT happiness FROM pokemon WHERE user_id=? ORDER BY id",(uid,))]
def back(uid, secs):
    t=(walk._now()-datetime.timedelta(seconds=secs)).isoformat()
    db.run("UPDATE wild_state SET walk_at=? WHERE user_id=?",(t,uid))

print("=== 처음에는 지금부터 센다 ===")
a=mkuser("zzw_a")
chk("첫 정산은 0", walk.settle(a)==0)
st=db.q1("SELECT walk_at FROM wild_state WHERE user_id=?",(a,))
chk("기준 시각이 생긴다", st and st["walk_at"], st)
chk("바로 다시 불러도 0", walk.settle(a)==0)

print("\n=== 시간이 흐르면 오른다 ===")
back(a, walk.TICK+5)
got=walk.settle(a)
chk("20분 지나면 +1", got==1, got)
h=happy(a)
chk("데리고 다니는 둘만 오른다", h[0]==71 and h[1]==71 and h[2]==70, h)

print("\n=== 폴링을 아무리 해도 안 오른다 ===")
before=happy(a)
for _ in range(50): walk.settle(a)
chk("50번 불러도 그대로", happy(a)==before, (before, happy(a)))

print("\n=== 오래 꺼 뒀다 켜도 몰아주지 않는다 ===")
back(a, walk.TICK*100)
got=walk.settle(a)
chk("한 번에 최대 %d칸"%walk.MAX_TICKS, got==walk.MAX_TICKS*walk.GAIN, got)

print("\n=== 럭셔리볼은 두 배 ===")
b=mkuser("zzw_b", 2, 70, luxury=True)
walk.settle(b); back(b, walk.TICK+5)
walk.settle(b)
chk("럭셔리볼 +2", happy(b)[0]==72, happy(b))

print("\n=== 상한 ===")
c=mkuser("zzw_c", 1, 254)
walk.settle(c); back(c, walk.TICK*3)
walk.settle(c)
chk("255를 안 넘는다", happy(c)[0]==255, happy(c))

print("\n=== 쓰러지면 깎인다 ===")
d=mkuser("zzw_d", 1, 70)
mid=db.q1("SELECT id FROM pokemon WHERE user_id=?",(d,))["id"]
walk.on_faint(d, mid)
chk("기절 -%d"%walk.FAINT_LOSS, happy(d)[0]==70-walk.FAINT_LOSS, happy(d))
e=mkuser("zzw_e", 1, 1)
mid=db.q1("SELECT id FROM pokemon WHERE user_id=?",(e,))["id"]
walk.on_faint(e, mid); chk("0 아래로 안 간다", happy(e)[0]==0, happy(e))

print("\n=== 걸리는 시간 ===")
print("  보통 종 70 -> 160 : %.1f시간 (하루 8시간이면 %.1f일)"
      % (walk.hours_to(70,160), walk.hours_to(70,160)/8))
print("  럭셔리볼          : %.1f시간 (%.1f일)"
      % (walk.hours_to(70,160,True), walk.hours_to(70,160,True)/8))
print("  이어롤 0 -> 160   : %.1f시간 (%.1f일)"
      % (walk.hours_to(0,160), walk.hours_to(0,160)/8))
chk("하루 만에 끝나지 않는다", walk.hours_to(70,160) > 24)
chik = walk.hours_to(0,160)/8
chk("제일 느린 것도 열흘 안", chik < 10, chik)
for n in ("zzw_a","zzw_b","zzw_c","zzw_d","zzw_e"):
    db.run("DELETE FROM users WHERE username=?",(n,))
print("\n합계  OK %d  FAIL %d"%(ok,fail))
