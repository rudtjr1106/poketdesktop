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

### shape 는 ARM(A1) 을 먼저 노리세요

| | ARM `VM.Standard.A1.Flex` | x86 `VM.Standard.E2.1.Micro` |
|---|---|---|
| 무료 한도 | 합쳐서 **2 OCPU / 12GB** | 1대당 **1/8 OCPU / 1GB**, 2대까지 |
| 잡기 | 자주 "용량 없음" 이 뜬다 | 거의 항상 된다 |
| 유휴 회수 | **덜 걸린다** (아래 설명) | 더 잘 걸린다 |

성능이 비교가 안 됩니다. x86 micro 는 1 OCPU 가 아니라 **1/8 OCPU** 예요.
이 서버는 1GB 로도 돌아가지만, A1 을 잡을 수 있으면 A1 이 낫습니다.

> **2026-08-18 부터 집행 중**: ARM 무료 한도가 4 OCPU / 24GB 에서
> **2 OCPU / 12GB** 로 줄었고, 한도를 넘는 인스턴스는 **자동으로 종료**됩니다.
> 옛날 안내글을 보고 4/24 로 만들면 나중에 통째로 사라집니다.
> 반드시 **2 OCPU / 12GB 이하**로 만드세요.

**A1 이 안 잡히면** (`Out of host capacity`) — 흔한 일입니다.
Availability Domain 을 AD-1 / AD-2 / AD-3 으로 바꿔가며 다시 눌러 보세요.
그래도 안 되면 x86 micro 로 가도 이 서버는 충분히 돕니다.

#### 유휴 회수 — 문서가 흔히 거꾸로 설명합니다

Oracle 은 놀고 있는 무료 인스턴스를 회수합니다. 7일 동안

- CPU 95퍼센타일 20% 미만 **그리고**
- 네트워크 20% 미만 **그리고**
- 메모리 20% 미만 (**A1 shape 에만 해당**)

이 전부 참일 때입니다. **and 조건**이라는 게 핵심이에요.
조건이 적을수록 전부 참이 되기 쉽습니다.

- x86: 통과할 조건이 2개 → **더 잘 걸린다**
- A1: 조건이 3개 → 메모리만 좀 잡고 있어도 안 걸린다

A1 은 12GB 중 2.5GB 정도만 붙잡고 있으면 메모리 조건이 깨져서 회수를 면합니다.
(예: `/etc/fstab` 에 `tmpfs /mnt/keepalive tmpfs size=3G 0 0` 를 넣고
3GB 짜리 파일을 하나 만들어 두면 됩니다.)

### ARM 에서 도커가 그대로 도나요

**됩니다.** 확인해 뒀습니다.

- 베이스 이미지 `python:3.12-slim` 은 arm64 판이 함께 나옵니다.
- 서버가 쓰는 건 fastapi · uvicorn · pydantic 셋뿐이고 전부 aarch64 휠이 있습니다.
- Pillow 같은 무거운 네이티브 패키지는 **클라이언트에만** 있고 서버에는 없습니다.

그러니 크로스빌드(buildx)를 준비할 필요가 없습니다.
**VM 위에서 그냥 `docker compose build`** 하면 그 자리에서 arm64 이미지가 만들어집니다.

---

## 1. VM 만들기

> **지름길**: VM 을 만들고 SSH 로 들어간 다음
> `bash deploy/setup-oracle.sh` 를 돌리면 스왑 · 도커 · compose · iptables 를
> 한 번에 잡아 줍니다. 아래는 그 스크립트가 무엇을 왜 하는지에 대한 설명입니다.
>
> 한 가지 주의: 스크립트가 도커를 처음 설치한 직후에는 `usermod -aG docker` 가
> **지금 로그인한 세션에는 반영되지 않습니다.** 그 자리에서 `docker` 를 부르면
> permission denied 로 멈춥니다. 로그아웃 후 다시 접속해서 한 번 더 돌리세요.

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
| VM | ARM 2 OCPU / 12GB, 또는 x86 1/8 OCPU / 1GB 2대 | 1대 |
| 디스크 | 200GB | 5GB 미만 |
| 송신 | 10TB / 월 | 사람당 월 12MB |

**단, Oracle 계정에 결제수단을 넣어두면 실수로 유료 자원을 만들 수 있으니
인스턴스를 만들 때 "Always Free-eligible" 표시를 꼭 확인하세요.**
