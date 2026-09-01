# AWS 로 서버 옮기기

Render(싱가포르) + Turso(도쿄) 를 **서울 한 대**로 합친다.

## 왜

재보니 이랬다.

| | |
|---|---|
| DB 를 안 쓰는 요청 | 220ms |
| 쿼리 하나당 | 100~200ms |
| `/api/me` | 약 1,000ms |

지역을 맞추는 길은 없다 - **Turso 에 싱가포르가 없고**(아시아는 도쿄뿐),
**Render 에 도쿄가 없다**(있는 서비스의 리전은 바꾸지도 못한다).

서울 한 대에 서버와 DB 를 같이 두면:

| | 지금 | 서울 한 대 |
|---|---|---|
| 한국에서 왕복 | 70ms (싱가포르) | **6ms** |
| 쿼리 하나 | 100~200ms | **0.1ms 미만** (같은 기계의 파일) |
| `/api/me` | 약 1,000ms | **약 30ms** |
| 콜드 스타트 | 있음 (30~60초) | 없음 |
| 월 비용 | $0 | $5 |

**코드는 안 고쳐도 된다.** `POKET_TURSO_URL` 을 비우면 `db.py` 가 알아서
`POKET_DB` 경로의 로컬 sqlite3 로 붙는다.

---

## 돈 이야기 — 시계가 세 개다

$100 크레딧이 있어도 **20개월이 아니라 12개월**이다.

| 시계 | 기한 |
|---|---|
| 크레딧 잔액 | $100 / $5 = 20개월 |
| **크레딧 만료** | 계정 만든 날 + 12개월. 남아도 소멸 |
| **무료 플랜 만료** | + 6개월에 **계정이 닫히고 데이터가 사라진다** |

**가입할 때 paid 플랜을 고를 것.** 남은 크레딧은 청구서에 그대로 적용된다.
free 플랜으로 두면 6개월 뒤 24/7 서버가 그냥 없어진다.

2025-07-15 이전에 만든 계정이면 크레딧이 아예 없다.

---

## 1. 인스턴스 만들기

Lightsail 콘솔:

1. **리전: 서울 (ap-northeast-2)**
2. Ubuntu, **$5 플랜**(512MB / 2 vCPU / 20GB SSD / 전송 1TB)
3. 만든 뒤 **Networking → Static IP 를 만들어 붙인다**
   안 붙이면 재부팅할 때마다 주소가 바뀐다
4. **Networking → IPv4 Firewall** 에 **HTTP(80)** 과 **HTTPS(443)** 추가
   기본은 22 만 열려 있다

> 512MB 는 빠듯하다. 설치 스크립트가 스왑 2GB 를 먼저 만든다 -
> 없으면 도커 빌드 중에 죽는다.

## 2. 도메인 붙이기

HTTPS 에는 도메인이 필요하다. 비밀번호가 오가므로 HTTPS 는 선택이 아니다.

공짜로 하려면 [DuckDNS](https://www.duckdns.org) 에서 하나 만들고
아까 만든 **고정 IP** 를 넣는다. (예: `poketdesktop.duckdns.org`)

붙었는지 확인:

```bash
dig +short poketdesktop.duckdns.org
```

고정 IP 가 나와야 한다.

## 3. 서버 올리기

SSH 로 들어가서:

```bash
git clone https://github.com/rudtjr1106/poketdesktop.git
bash poketdesktop/deploy/setup-aws.sh
```

스왑, 도커, 방화벽, 코드, 인증서까지 한 번에 한다. 도메인과 이메일을 물어본다.
처음 빌드는 512MB 에서 5~10분쯤 걸린다.

끝나면 이렇게 나와야 한다:

```bash
curl https://poketdesktop.duckdns.org/api/health
```

## 4. 자료 옮기기

**옮기는 동안 게임을 켜지 마라.** 그 사이에 쓴 것은 사라진다.

내 PC 에서 Turso 를 파일로 뽑는다:

```bat
set POKET_FROM_URL=libsql://지금-쓰는-것...
set POKET_FROM_TOKEN=지금-토큰
set POKET_TO_URL=poket.db
set POKET_TO_TOKEN=아무거나
python tools/move_db.py
```

끝에 양쪽 행 수를 나란히 보여준다. **하나라도 다르면 멈춰라.**

받는 쪽에 `libsql://` 이 아니라 그냥 파일 이름을 주면 평범한 SQLite 파일이
나온다. 서버가 쓰는 것과 같은 형식이다.

서버로 올리고 갈아끼운다. (`scp` 에 `D:\...` 같은 경로를 주면 `D` 를
서버 이름으로 잘못 알아듣는다. 파일이 있는 폴더에서 이름만 주는 게 안전하다.)

```bash
scp poket.db ubuntu@고정IP:~/poket.db
```

```bash
docker stop poketdesktop-server
docker run --rm --volumes-from poketdesktop-server busybox sh -c "rm -f /data/poket.db-wal /data/poket.db-shm"
docker cp ~/poket.db poketdesktop-server:/data/poket.db
docker start poketdesktop-server
```

WAL 을 지우는 이유: 옛 WAL 이 남아 있으면 새 본체 위에 옛 변경분이 덧씌워진다.

다 되면 내 PC 에 남은 `poket.db` 와 `move-backup.sql` 을 지워라.
**닉네임과 비밀번호 해시가 들어 있다.**

확인:

```bash
curl https://poketdesktop.duckdns.org/api/health
```

## 5. 백업 켜기 — 건너뛰지 마라

**여기서는 SQLite 파일 하나가 유일본이다.** Turso 를 쓸 때는 그쪽이 들고
있었지만 이제는 아니다.

```bash
echo "POKET_BACKUP_KEY=$(openssl rand -base64 36)" >> ~/poketdesktop/deploy/.env
bash ~/poketdesktop/deploy/backup.sh --install
bash ~/poketdesktop/deploy/backup.sh
```

**POKET_BACKUP_KEY 를 따로 적어 두어라.** 잃어버리면 백업을 영영 못 연다.

살아 있는 DB 를 그냥 복사하면 반쪽이 나온다. 이 스크립트는 sqlite3 의
온라인 백업으로 온전한 사본을 뜬 뒤 잠그고, **매번 다시 열어 본다.**

인스턴스가 죽으면 거기 있는 백업도 같이 죽는다. **Lightsail 자동 스냅샷**
(콘솔 → Snapshots, 월 $1쯤)도 같이 켜라. 가끔 내 PC 로도 내려받아 두면 좋다:

```bash
scp ubuntu@고정IP:~/poket-backups/poket-*.db.enc .
```

## 6. 클라이언트가 새 주소를 보게 하기

`client/poketdesktop/config.py`:

```python
SERVER = os.environ.get("POKET_SERVER") or "https://poketdesktop.duckdns.org"

OLD_SERVERS = (
    "http://127.0.0.1:8787",
    "http://localhost:8787",
    "https://desktop-kb3pg3b.taile9bd90.ts.net:10000",
    "https://poketdesktop.onrender.com",      # <- 이 줄을 더한다
)
```

`OLD_SERVERS` 에 넣으면 저장된 설정이 그 주소인 사용자는 **새 주소로 자동으로
옮겨진다.** 일부러 고쳐 넣은 주소는 안 건드린다.

그다음 판올림해서 릴리스한다.

> **옛 서버를 꺼도 안전하다.** 클라이언트는 시작할 때 게임 서버보다
> 업데이트를 먼저 확인하고(`app.py` 의 `boot()`), 업데이트는 GitHub 만
> 쓴다. 서버가 죽어 있어도 새 버전을 받아서 새 주소로 붙는다.

## 7. 뒷정리

| 무엇 | 어떻게 |
|---|---|
| Render 서비스 | 며칠 켜 둔다. 되돌아갈 곳이다. 다 옮겼으면 Suspend |
| Turso DB | 며칠 그대로. 문제 없으면 삭제 |
| `keepalive` 워크플로 | 저장소 Variables 의 `POKET_SERVER` 를 새 주소로. VM 은 안 자지만 오류 감시는 계속 쓸모 있다 |
| **`backup` 워크플로** | **꺼라.** Turso 를 뜨는 것이라 이제 실패한다. 5번의 cron 이 대신한다 |
| `render.yaml` | 남겨 둔다. 되돌릴 때 쓴다 |

## 되돌리려면

클라이언트 `SERVER` 를 Render 주소로 되돌리고 릴리스하면 끝이다.
Render 와 Turso 를 며칠 살려 두는 이유가 이것이다.

## 과금 사고 막기

1. **AWS Budgets** 에 월 $10 예산 + 80% / 100% 알림
2. 캘린더에 두 개: **계정 생성일 + 5개월**(paid 전환 마감),
   **+ 11개월**(크레딧 만료)
3. 인스턴스를 지울 때 **고정 IP 도 같이 지워라.** 안 붙은 고정 IP 는
   월 $3.72 가 계속 나간다
4. **꺼놔도 과금된다.** 안 쓸 거면 삭제해야 한다
