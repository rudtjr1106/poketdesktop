# AWS 로 서버 옮기기 — 처음부터 끝까지

AWS 를 한 번도 안 써 봤다는 전제로 쓴다. 순서대로 따라가면 된다.

**걸리는 시간: 손으로 하는 것 2~3시간.** 다만 계정 활성화가 최대 24시간
걸릴 수 있으니 **0~3단계는 하루 전에 해 두는 게 좋다.**

> 콘솔 화면은 바뀔 수 있다. 여기 적은 버튼 이름은 2026-09-02 에 공식 문서에서
> 확인한 것이다. 확인하지 못한 화면은 그렇다고 적어 두었다.

---

## 왜 옮기나

| | 지금 | 서울 한 대 |
|---|---|---|
| 한국에서 왕복 | 70ms (싱가포르) | **6ms** |
| 쿼리 하나 | 100~200ms (도쿄) | **0.1ms 미만** |
| `/api/me` | 약 1,000ms | **약 30ms** |
| 콜드 스타트 | 30~60초 | 없음 |
| 월 | $0 | $5 |

지역을 맞추는 길은 없다. **Turso 에 싱가포르가 없고**(아시아는 도쿄뿐),
**Render 에 도쿄가 없다.** 그래서 합치는 것이 답이다.

**서버 코드는 안 고친다.** `POKET_TURSO_URL` 을 비우면 `db.py` 가 알아서
`POKET_DB` 경로의 로컬 sqlite3 로 붙는다.

## 준비물

- **해외결제 되는 신용카드** (국내전용 체크카드는 거부 사례가 있다)
- SMS 받을 휴대폰
- 오래 쓸 이메일 (이게 로그인 ID 이자 계정 복구 수단이다)
- 휴대폰 인증앱 (Google Authenticator 등)

---

## 0. 코드를 GitHub 에 올린다

**이게 진짜 0번이다.** 서버에서 `git clone` 으로 받아 쓰기 때문에,
`deploy/` 가 GitHub 에 없으면 10단계에서 "그런 파일 없음" 으로 끝난다.

```bash
git push origin main
```

**✅ 확인:** 브라우저로 저장소에 들어가서 `deploy/` 폴더가 **눈에 보이는지**
본다. 그 안에 `setup-aws.sh` 와 `docker-compose.prod.yml` 이 있어야 한다.

---

## 1. AWS 계정 만들기

주소창에 **직접** 친다:

```
https://signin.aws.amazon.com/signup?request_type=register
```

> **첫 화면의 "Start free with AWS" 나 상단 "Sign up" 을 누르지 마라.**
> 그쪽은 새로 나온 가입 경험인데, **Lightsail 을 지원하지 않고** 한국 주소를
> 넣으면 리전이 **시드니**로 고정되어 바꿀 수 없다. 이 계획이 통째로 막힌다.
>
> 중간에 **project(프로젝트)** 를 만들라거나 **spend limit** 을 정하라거나
> 구글/애플 계정으로 로그인하라고 하면 그쪽이다. 멈추고 위 주소로 다시 시작하라.
> (요금제 Free/Paid 를 고르라는 화면은 정상이다. 그냥 진행하면 된다.)

순서:

1. 이메일과 계정 이름 → **Verify email address**
2. 메일로 온 코드 입력 → **Verify**
3. 루트 비밀번호 (8자 이상, 대문자·소문자·숫자·기호 중 3종류 이상)
4. **⚠️ 요금제에서 `Paid account plan` 을 고른다**
5. **Personal**, 국가는 **South Korea**, 약관 동의
6. 카드 등록
7. 휴대폰 인증 (+82) → **Send SMS** → 코드 입력
8. 지원 플랜은 **Basic** (무료)
9. **Complete sign up**

> ### Paid 를 골라야 하는 이유
> Free 플랜은 공식 문서에 이렇게 적혀 있다 — "Your free account plan ends
> after six months or when your credits are fully used", 그리고
> "your account closes automatically, and you lose access to your resources
> and data." **6개월 뒤 서버가 그냥 사라진다.**
> 크레딧 $100 은 **어느 쪽을 골라도 똑같이 받는다.** Free 를 고를 이유가 없다.

> **지원 플랜에서 Developer 를 고르면 월 $29 다.** Basic 이 맞다.

> **카드에 $1 쯤 가승인이 잡힌다.** 실제 청구가 아니고 며칠 뒤 사라진다.
> 놀라서 카드사에 이의제기하면 계정 활성화가 막힌다.

> **한국 주소면 모든 요금에 부가세 10% 가 붙는다.** 그리고 크레딧 약관상
> **세금은 크레딧으로 상쇄되지 않는다.** 크레딧이 남아 있어도 매달 부가세
> (약 $0.5)는 카드에서 실제로 빠진다. 카드가 만료되면 청구 실패가 난다.

**✅ 확인:** "your account is being activated" 가 뜨고, 몇 분~최대 24시간 뒤
활성화 메일이 온다. 활성화 전에는 인스턴스를 못 만든다.

---

## 2. 루트 계정에 MFA 걸기

결제수단이 붙은 계정이다. 가입 당일에 해라.

1. 콘솔 오른쪽 위 계정 이름 → **Security credentials**
2. **Multi-Factor Authentication (MFA)** → **Assign MFA device**
3. **Device name** 입력, **Authenticator app** 선택 → **Next**
4. **Show QR code** → 인증앱으로 스캔
5. **MFA code 1** 에 지금 코드, 30초 뒤 새 코드를 **MFA code 2** → **Add MFA**

> **QR 코드나 secret key 를 따로 백업해 둬라.** 휴대폰을 잃어버리고 복구도
> 안 되면 AWS 고객센터를 거쳐야 한다.

---

## 3. 크레딧 확인

`https://console.aws.amazon.com/billing/` → 왼쪽 **Credits**

**✅ 확인:** $100 이 보이고 만료일이 1년 뒤로 찍혀 있다.

> 입금 반영에 몇 시간 걸릴 수 있다. 바로 안 보인다고 당황하지 마라.

> **크레딧은 계정 만든 날로부터 12개월 뒤 소멸한다.** 남아도 사라진다.
> 그리고 **AWS Organizations 나 Control Tower 를 건드리면 즉시 만료될 수 있다.**
> 실습한다고 그쪽을 만지지 마라.

---

## 4. 예산 알림 걸기

1. `https://console.aws.amazon.com/cost-management/` → **Budgets**
2. **Create budget**
3. **Use a template (simplified)** → **Monthly cost budget**
4. 금액 **$10**, 알림 받을 이메일
5. **Create budget**

$5 + 부가세 = 약 $5.5 라, $10 이면 "뭔가 이상한 게 돌고 있다" 를 잡아낸다.

> **예산은 알리기만 하고 끄지는 않는다.** "예산 걸었으니 안전하다" 가 제일
> 위험한 착각이다.

---

## 5. 인스턴스 만들기

Lightsail 은 **일반 AWS 콘솔과 다른 별도 콘솔**이다. EC2 화면이 보이면 잘못 왔다.

`https://lightsail.aws.amazon.com/` → **Create instance**

> Lightsail 에는 오른쪽 위 리전 드롭다운이 **없다.** 리전은 이 화면 안에서 고른다.

1. **Change AWS Region and Availability Zone** → **Asia Pacific (Seoul)
   (ap-northeast-2)**. 가용영역은 기본값 그대로.
2. 플랫폼 **Linux**
3. **OS Only** 탭 → **Ubuntu** (목록에서 가장 높은 LTS 번호)
4. **dual-stack (IPv4 and IPv6)** 을 고른다
5. **$5 USD/mo** (0.5GB / 2 vCPU / 20GB SSD / 1TB 전송)
6. 이름 (영문·숫자·`.`·`-`·`_` 만. **공백과 한글 안 된다**)
7. **Create instance**

> ### $3.50 짜리를 고르면 안 된다
> 그건 **IPv6-only** 가격이다. **IPv6-only 에는 고정 IPv4 를 붙일 수 없고**,
> 한국 회선 상당수가 IPv6 를 안 써서 접속 자체가 안 된다. 나중에 못 고친다 —
> **처음부터 다시 만들어야 한다.**

> ### "Apps + OS" 를 고르면 안 된다
> WordPress/LAMP 이미지는 **Apache 나 Nginx 가 이미 80·443 을 잡고 있어서**
> Caddy 가 포트를 못 연다. 반드시 **OS Only**.

> **인스턴스를 Stop 해도 요금은 나간다.** EC2 감각으로 "껐으니 공짜" 가 아니다.
> 안 쓸 거면 **삭제**해야 한다.

> **무료 체험이 뜰 수도 있고 안 뜰 수도 있다.** AWS 문서끼리 내용이 다르다.
> 월 $5 나간다고 보고 계획해라. 뜨면 이득이다.

**✅ 확인:** 몇 분 뒤 인스턴스 카드가 **Running** 이 되고 Seoul 로 표시된다.

---

## 6. 고정 IP 붙이기

1. 왼쪽 **Networking** → **Create static IP**
2. 리전 **Seoul (ap-northeast-2)**
3. 5단계에서 만든 인스턴스 선택
4. 이름 입력 → **Create**

이 화면 하나에서 만들기와 붙이기가 같이 끝난다.

> ### 안 붙이면 재부팅할 때마다 주소가 바뀐다
> 공식 문서 원문: "The default dynamic public IP address ... changes every
> time you stop and restart the instance." 주소가 바뀌면 도메인이 죽고
> 인증서 갱신도 실패한다. **도메인을 걸기 전에** 반드시 붙여라.

> **고정 IP 는 붙어 있는 동안만 무료다.** 인스턴스를 지우면 자동으로 떨어지는데
> **계정에는 남아서 시간당 $0.005(월 약 $3.6)가 계속 나간다.** 크레딧이 조용히
> 새는 1순위 경로다. 인스턴스를 지울 때 고정 IP 도 같이 지워라.

**✅ 확인:** 인스턴스 **Networking** 탭의 공인 IP 옆에 **파란 압정** 표시가
생긴다. **이 IP 를 적어 둔다.**

---

## 7. 방화벽에서 443 열기 — 제일 많이 빠뜨린다

1. **Instances** → 인스턴스 이름 클릭 → **Networking** 탭
2. **IPv4 Firewall** → **Add rule**
3. **Application** 드롭다운에서 **HTTPS** (포트 443 이 자동으로 채워진다)
4. **Restrict to IP address** 는 **체크하지 않는다**
5. **Create**

**HTTP(80) 은 이미 열려 있다.** 추가할 것은 443 하나뿐이다.

> **80 을 닫지 마라.** 인증서 발급 검증에 필요하다.
> **443 을 안 열면** 인증서는 정상 발급됐는데 브라우저로는 안 열리는,
> 제일 오래 헤매는 증상이 나온다.

> 서버 안쪽 방화벽(`ufw`)은 별개다. **켜지 마라** — `sudo ufw allow 22` 를
> 먼저 안 하면 SSH 가 끊겨서 못 들어간다.

**✅ 확인:** IPv4 Firewall 에 규칙 세 개(SSH 22 / HTTP 80 / HTTPS 443).

---

## 8. 도메인 받기

HTTPS 에는 도메인이 필요하다. 비밀번호가 오가므로 선택이 아니다.

### 공짜 — DuckDNS (이 규모에 권한다)

1. `https://www.duckdns.org/` 접속
2. **Google** 또는 **GitHub** 로 로그인 (Persona 는 오래전에 없어진 서비스다)
3. 원하는 이름을 추가한다 (이 프로젝트는 `posktop` 을 써서 `posktop.duckdns.org` 가 됐다).
   같은 화면의 **token** 을 복사해 둔다.
   *(이 화면은 로그인이 필요해 직접 확인하지 못했다. 도메인 입력칸과 추가
   버튼을 찾으면 된다.)*
4. 6단계의 **고정 IP** 를 등록한다. 화면에서 넣어도 되고 이 주소를 한 번
   열어도 된다:

```
https://www.duckdns.org/update?domains=posktop&token=토큰&ip=고정IP&verbose=true
```

`domains` 에는 `.duckdns.org` 를 빼고 이름만 넣는다. 성공하면 `OK` 가 뜬다.

### 확인 (건너뛰지 마라)

```powershell
nslookup posktop.duckdns.org 8.8.8.8
```

**✅ 확인:** 나오는 IP 가 6단계의 고정 IP 와 **정확히 같다.**
TTL 이 60초라 보통 1분이면 반영된다.
**다르면 다음으로 넘어가지 마라. 인증서 발급은 무조건 실패한다.**

> 돈을 좀 써도 된다면 Route 53 에서 `.click` 을 연 $3 에 살 수 있다.
> 다만 **도메인 값은 크레딧으로 못 낸다** — 약관에 명시돼 있다. 카드에서 빠진다.

---

## 9. 서버에 접속하기

### 쉬운 쪽 — 브라우저 SSH

인스턴스 카드의 **Connect** (또는 관리 페이지의 **Connect** 탭 →
**Connect using SSH**). 키 파일이 필요 없다.

> 브라우저 SSH 는 **다른 키를 쓴다.** .pem 을 잃어버려도 여기로는 들어갈 수
> 있다. 최후의 비상구다.

### 편한 쪽 — 내 PC 의 PowerShell

키 받기: Lightsail 상단 계정 → **Account** → **SSH keys** 탭 → 서울 리전
기본키 다운로드. (기본키는 언제든 다시 받을 수 있다. **Create custom key**
로 만든 키는 그때 한 번만 받을 수 있으니 초보는 기본키를 써라.)

`.pem` 을 `%USERPROFILE%\.ssh\` 로 옮긴 뒤 권한을 좁힌다:

```powershell
icacls "$env:USERPROFILE\.ssh\LightsailDefaultKey-ap-northeast-2.pem" /inheritance:r /grant:r "$($env:USERNAME):(R)"
```

```powershell
ssh -i "$env:USERPROFILE\.ssh\LightsailDefaultKey-ap-northeast-2.pem" ubuntu@고정IP
```

> **윈도우에서 `chmod 400` 은 아무 효과가 없다.** 위 `icacls` 를 안 하면
> `UNPROTECTED PRIVATE KEY FILE` 로 거부된다.

> **.pem 을 OneDrive 가 동기화하는 폴더(바탕화면·문서)에 두지 마라.**
> 개인키가 클라우드로 올라가고 권한도 되돌아간다.

> **사용자 이름은 `ubuntu` 다.** `ec2-user` 로 하면 거부당한다.

**✅ 확인:** 프롬프트가 `ubuntu@ip-...:~$` 가 된다.

---

## 10. 배포 — 여기부터는 서버 안이다

```bash
cd ~
git clone https://github.com/rudtjr1106/poketdesktop.git
bash poketdesktop/deploy/setup-aws.sh
```

도메인과 이메일을 물어보면 넣는다. 스왑·도커·방화벽·인증서까지 한 번에 한다.

> `curl ... | bash` 로 돌리지 마라. 도메인을 물어보는데 파이프로 넣으면
> 읽기가 스크립트의 나머지 줄을 답으로 먹어 버린다.
> 물어보는 게 싫으면 미리 넣어 주면 된다:
> `POKET_DOMAIN=x.duckdns.org ACME_EMAIL=me@example.com bash poketdesktop/deploy/setup-aws.sh`

> **도커를 처음 깔면 그룹이 지금 셸에 반영되지 않는다.** 스크립트가 `sg` 로
> 알아서 넘어가지만, 그것도 안 되면 한 번 나갔다 들어와서 다시 돌리면 된다.
> **여러 번 돌려도 안전하다** — 이미 된 것은 건너뛴다.

> 512MB 에서 빌드는 된다. 의존성 네 개가 전부 미리 만들어진 휠이라 컴파일이
> 없다. 스크립트가 만드는 스왑 2GB 는 그대로 두면 된다.
> 시간은 대부분 이미지 받는 데 쓴다 (5~10분).

**✅ 확인:**

```bash
curl https://posktop.duckdns.org/api/health
```

그리고 브라우저로 열어서 **자물쇠**를 본다.

> ### 자물쇠에 경고가 뜨면 그건 실패다
> 인증서 발급이 실패하면 Caddy 가 시험용(staging) 인증서로 넘어간다.
> 사이트는 열리는데 "신뢰할 수 없음" 이 뜬다. 성공이 아니다.
>
> ```bash
> cd ~/poketdesktop && docker compose -f deploy/docker-compose.prod.yml logs -f caddy
> ```
>
> 이 순서로 확인하라: ① 도메인이 고정 IP 를 가리키나 ② 방화벽에 443 이 있나
> ③ 80 을 지우지 않았나 ④ 고정 IP 가 붙어 있나(파란 압정)

---

## 11. 자료 옮기기

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

올린다. (`scp` 에 드라이브 문자가 붙은 경로를 주면 그걸 서버 이름으로
오해한다. 파일이 있는 폴더에서 이름만 줘라.)

```bash
scp poket.db ubuntu@고정IP:~/poket.db
```

갈아끼운다:

```bash
docker stop poketdesktop-server
docker run --rm --volumes-from poketdesktop-server busybox sh -c "rm -f /data/poket.db-wal /data/poket.db-shm"
docker cp ~/poket.db poketdesktop-server:/data/poket.db
docker start poketdesktop-server
```

WAL 을 지우는 이유: 옛 WAL 이 남으면 새 본체 위에 옛 변경분이 덧씌워진다.

다 되면 내 PC 의 `poket.db` 와 `move-backup.sql` 을 지워라.
**닉네임과 비밀번호 해시가 들어 있다.**

---

## 12. 백업 켜기 — 건너뛰지 마라

**여기서는 SQLite 파일 하나가 유일본이다.** Turso 때는 그쪽이 들고 있었다.

```bash
echo "POKET_BACKUP_KEY=$(openssl rand -base64 36)" >> ~/poketdesktop/deploy/.env
bash ~/poketdesktop/deploy/backup.sh --install
bash ~/poketdesktop/deploy/backup.sh
```

**POKET_BACKUP_KEY 를 서버 밖에 따로 적어 둬라.** 잃어버리면 백업을 영영 못 연다.

살아 있는 DB 를 그냥 복사하면 반쪽이 나온다. 이 스크립트는 sqlite3 의 온라인
백업으로 온전한 사본을 뜨고, 잠그고, **매번 다시 열어 본다.**

인스턴스가 죽으면 거기 있는 백업도 같이 죽는다. **Lightsail 자동 스냅샷**도
켜라 (월 $1쯤). 가끔 내 PC 로도 내려받아 둬라:

```bash
scp ubuntu@고정IP:~/poket-backups/poket-*.db.enc .
```

되살리기:

```bash
bash ~/poketdesktop/deploy/backup.sh --restore <파일>
```

## 13. 재부팅해도 살아나는지 본다

Lightsail 관리 페이지에서 **Reboot** 을 누르고, 다시 들어와서:

```bash
docker ps
```

컨테이너 두 개가 다시 떠 있어야 한다.

> 직접 `docker compose stop` 으로 세워 둔 것은 재부팅해도 안 뜬다.
> 그게 `restart: unless-stopped` 의 뜻이다.

---

## 14. 클라이언트가 새 주소를 보게 하기

`client/poketdesktop/config.py`:

```python
SERVER = os.environ.get("POKET_SERVER") or "https://posktop.duckdns.org"

OLD_SERVERS = (
    "http://127.0.0.1:8787",
    "http://localhost:8787",
    "https://desktop-kb3pg3b.taile9bd90.ts.net:10000",
    "https://poketdesktop.onrender.com",      # <- 더한다
)
```

`OLD_SERVERS` 에 넣으면 저장된 설정이 그 주소인 사용자는 **새 주소로 저절로
옮겨진다.** 일부러 고쳐 넣은 주소는 안 건드린다.

그다음 판올림해서 릴리스한다.

> **옛 서버를 꺼도 된다.** 클라이언트는 시작할 때 게임 서버보다 업데이트를
> 먼저 확인하고(`app.py` 의 `boot()`), 업데이트는 GitHub 만 쓴다.
> 서버가 죽어 있어도 새 버전을 받아서 새 주소로 붙는다.

---

## 15. 뒷정리

| 무엇 | 어떻게 |
|---|---|
| Render 서비스 | 며칠 켜 둔다. 되돌아갈 곳이다. 그 뒤 Suspend |
| Turso DB | 며칠 그대로. 문제 없으면 삭제 |
| `keepalive` 워크플로 | Variables 의 `POKET_SERVER` 를 새 주소로. VM 은 안 자지만 오류 감시는 계속 쓸모 있다 |
| **`backup` 워크플로** | **꺼라.** Turso 를 뜨는 것이라 이제 실패한다. 12단계의 cron 이 대신한다 |
| `render.yaml` | 남겨 둔다. 되돌릴 때 쓴다 |

**되돌리려면** 클라이언트 `SERVER` 를 Render 주소로 되돌리고 릴리스하면 끝이다.

## 요금이 새지 않게

1. 캘린더에 두 개: **계정 생성일 + 5개월**(혹시 Free 로 만들었다면 전환 마감),
   **+ 11개월**(크레딧 만료)
2. 인스턴스를 지울 때 **고정 IP 도 같이 지워라.** 안 붙은 고정 IP 는 월 $3.72 다
3. **꺼놔도 과금된다.** 안 쓸 거면 삭제해야 한다
4. 스냅샷도 별도 과금이다 ($0.05/GB-월)
