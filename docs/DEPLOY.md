# Oracle Cloud 무료 VM 에 서버 올리기

내 PC 를 안 켜도 서버가 돌아가게 만드는 절차입니다. **돈은 안 듭니다.**

측정해보니 이 서버가 쓰는 트래픽은 **한 사람당 월 12MB** (하루 8시간 기준)라,
어떤 무료 티어를 쓰든 자원은 남아돕니다.

---

## 0. 먼저 알아둘 것

### 반드시 HTTPS 로 해야 합니다

지금 클라이언트는 아이디와 비밀번호를 그대로 서버에 보냅니다.
집에서 `127.0.0.1` 로 쓸 때는 괜찮지만, **공인 IP 에 HTTP 로 올리면
같은 와이파이를 쓰는 사람이 비밀번호를 그대로 볼 수 있습니다.**

그래서 이 문서는 Caddy 를 앞에 세웁니다. 도메인만 알려주면 인증서를
알아서 받고 갱신까지 합니다. 덤으로 **자동 로그인의 IP 확인 기능도
그때부터 제대로 동작합니다** (도커가 IP 를 가리는 문제가 풀립니다).

### shape 는 x86 을 고르세요

Oracle 은 **놀고 있는 무료 인스턴스를 회수**합니다.
7일 동안 CPU·네트워크·메모리가 전부 20% 미만이면 대상인데,
이 서버는 대부분 놀기 때문에 딱 걸립니다.

메모리 기준은 ARM(A1) shape 에만 적용되므로,
**`VM.Standard.E2.1.Micro` (x86, 1 OCPU / 1GB)** 로 만드는 편이 안전합니다.
이 서버에는 1GB 로도 충분합니다.

> 2026년 6월부터 ARM 무료 한도가 절반(2 OCPU / 12GB)으로 줄었습니다.

---

## 1. VM 만들기

Oracle Cloud 콘솔 → **Compute → Instances → Create Instance**

| 항목 | 값 |
|---|---|
| Image | Canonical Ubuntu 22.04 (또는 24.04) |
| Shape | **VM.Standard.E2.1.Micro** — "Always Free-eligible" 표시 확인 |
| SSH key | 공개키 붙여넣기 (없으면 새로 생성해서 개인키 저장) |

만들고 나면 **공인 IP (Public IP)** 를 적어둡니다.

---

## 2. 포트 열기 — 두 군데 다 해야 합니다

이게 Oracle 에서 제일 많이 막히는 지점입니다. **방화벽이 두 겹입니다.**

### (1) 콘솔 쪽

**Networking → Virtual Cloud Networks → (내 VCN) → Security Lists →
Default Security List → Add Ingress Rules**

| Source CIDR | Protocol | Destination Port |
|---|---|---|
| `0.0.0.0/0` | TCP | `80` |
| `0.0.0.0/0` | TCP | `443` |

### (2) 인스턴스 안쪽

Ubuntu 이미지는 자체 iptables 규칙으로 거의 다 막아둡니다.
**아래 설치 스크립트가 이걸 자동으로 해줍니다.**

콘솔만 열고 이걸 안 하면 "분명 열었는데 접속이 안 된다" 가 됩니다.

---

## 3. 도메인 만들기 (공짜)

인증서를 받으려면 도메인이 필요합니다. https://www.duckdns.org 에서
깃허브 계정으로 로그인하고 원하는 이름 하나를 만듭니다.

```
poketdesktop.duckdns.org   →   (1단계에서 적어둔 공인 IP)
```

IP 를 넣고 **update** 를 누르면 끝입니다.

---

## 4. 설치

SSH 로 들어가서:

```bash
ssh -i <개인키> ubuntu@<공인IP>
```

저장소가 **비공개**라서 먼저 인증이 필요합니다. 둘 중 하나:

```bash
# 방법 A — GitHub CLI (제일 간단)
sudo apt-get update && sudo apt-get install -y gh git
gh auth login          # 브라우저로 인증
gh repo clone rudtjr1106/poketdesktop ~/poketdesktop

# 방법 B — SSH 키를 GitHub 에 등록해두고
git clone git@github.com:rudtjr1106/poketdesktop.git ~/poketdesktop
```

그 다음 스크립트를 돌립니다.

```bash
bash ~/poketdesktop/deploy/setup-oracle.sh
```

스크립트가 하는 일:

```
스왑 2GB 만들기        1GB 짜리 VM 에서 도커 빌드가 죽는 걸 막는다
도커 + compose 설치
iptables 에 80/443 열기   재부팅해도 남도록 저장
도메인/이메일 물어보기     .env 로 저장
빌드하고 실행
https 로 확인
```

도메인과 이메일을 물어보면 3단계에서 만든 값을 넣으세요.

마지막에 이렇게 나오면 성공입니다:

```
   OK  https://poketdesktop.duckdns.org 정상 동작
{"ok":true,"version":"0.2.0","species":1025,...}
```

---

## 5. 클라이언트 연결

로그인 창의 **서버 주소** 칸에 넣습니다.

```
https://poketdesktop.duckdns.org
```

한 번 넣으면 `%APPDATA%\poketdesktop\settings.json` 에 저장돼서
다음부터는 안 넣어도 됩니다. 친구들에게도 이 주소만 알려주면 됩니다.

---

## 운영

```bash
cd ~/poketdesktop/deploy

docker compose -f docker-compose.prod.yml ps          # 상태
docker compose -f docker-compose.prod.yml logs -f     # 로그
docker compose -f docker-compose.prod.yml restart     # 재시작

# 코드를 고친 뒤 반영
git pull && docker compose -f docker-compose.prod.yml up -d --build
```

### 백업

계정과 포켓몬은 전부 `poketdata` 볼륨의 SQLite 파일 하나에 들어 있습니다.

```bash
docker run --rm -v deploy_poketdata:/data -v "$PWD":/out alpine \
  tar czf /out/poket-backup-$(date +%Y%m%d).tar.gz -C /data .
```

되돌릴 때:

```bash
docker compose -f docker-compose.prod.yml down
docker run --rm -v deploy_poketdata:/data -v "$PWD":/in alpine \
  sh -c "rm -rf /data/* && tar xzf /in/poket-backup-YYYYMMDD.tar.gz -C /data"
docker compose -f docker-compose.prod.yml up -d
```

---

## 안 될 때

| 증상 | 원인 |
|---|---|
| 접속 자체가 안 됨 | 콘솔 보안 목록 **또는** 인스턴스 iptables 둘 중 하나가 안 열림 |
| 인증서 발급 실패 | 도메인이 이 VM 의 공인 IP 를 안 가리킴 / 80 포트가 막힘 |
| 빌드 중 죽음 | 메모리 부족 — 스왑이 켜졌는지 `swapon --show` 로 확인 |
| 인스턴스가 사라짐 | ARM(A1) 유휴 회수. x86 micro 로 다시 만드세요 |
| 자동 로그인이 자꾸 풀림 | 집 IP 가 바뀐 것. 정상 동작입니다 (비밀번호로 다시 로그인) |

확인용:

```bash
curl https://<도메인>/api/health     # 서버 상태
curl https://<도메인>/api/whoami     # 서버가 내 IP 를 뭘로 보는지
```

`whoami` 의 `ip` 가 진짜 내 공인 IP 로 나오면 프록시 설정이 제대로 된 것입니다.

---

## 비용

전부 Always Free 범위 안입니다.

| | 무료 한도 | 우리가 쓰는 양 |
|---|---|---|
| VM | 1 OCPU / 1GB (x86 2대까지) | 1대 |
| 디스크 | 200GB | 5GB 미만 |
| 송신 | 10TB / 월 | 사람당 월 12MB |

**단, Oracle 계정에 결제수단을 넣어두면 실수로 유료 자원을 만들 수 있으니
인스턴스를 만들 때 "Always Free-eligible" 표시를 꼭 확인하세요.**
