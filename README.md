# ♠️ 8인 텍사스 홀덤 포커 (Texas Hold'em Poker)

최대 8명이 함께 즐길 수 있는 실시간 멀티플레이어 웹 기반 텍사스 홀덤 포커 게임입니다. Python FastAPI와 Socket.IO를 사용하여 구현되었습니다.

## 📌 주요 기능

*   **실시간 멀티플레이**: 최대 8명까지 한 방에서 게임 참여 가능
*   **관전 모드**: 게임 진행 중 입장 시 자동으로 관전 모드로 대기하며, 다음 라운드부터 참여
*   **자동 진행**: 프리플롭 -> 플롭 -> 턴 -> 리버 -> 쇼다운 순서로 게임 진행
*   **족보 확인**: 게임 중 언제든지 포커 족보(Ranking) 확인 가능
*   **반응형 UI**: 플레이어 위치에 따라 시점이 자동 정렬되어 자신의 카드가 항상 하단 중앙에 위치

## 🛠️ 기술 스택

*   **Backend**: Python 3.13, FastAPI, python-socketio, Uvicorn
*   **Frontend**: HTML5, CSS3, JavaScript (Socket.IO Client)
*   **Environment**: Conda, uv (패키지 관리)

## 🚀 설치 및 실행 방법

이 프로젝트는 `conda` 가상환경과 `uv` 패키지 매니저를 사용하여 실행하는 것을 권장합니다.

### 1. 환경 설정

```bash
# 1. Conda 가상환경 생성 (Python 3.13)
conda create --name pk python=3.13 -y

# 2. 가상환경 활성화
conda activate pk

# 3. uv 설치 (고속 패키지 설치)
pip install uv

# 4. 프로젝트 폴더로 이동
cd /home/pps-nipa/NIQ/fish/side/g/poker

# 5. 의존성 패키지 설치
uv pip install -r backend/requirements.txt
```

### 2. 서버 실행

다음 명령어 중 하나를 사용하여 서버를 실행합니다.

**방법 A (권장): Python 스크립트로 실행**
```bash
python backend/main.py
```

**방법 B: Uvicorn 직접 실행 (개발 모드)**
```bash
uvicorn backend.main:socket_app --host 0.0.0.0 --port 8092 --reload
```

### 3. 게임 접속

브라우저를 열고 다음 주소로 접속하세요.

*   URL: `http://localhost:8092`

## 🎮 게임 규칙 (약식)

1.  **참여**: 닉네임을 입력하고 방을 생성하거나 코드를 입력해 참가합니다. (최소 2명 필요)
2.  **시작**: 방장이 [게임 시작] 버튼을 누르면 게임이 시작됩니다.
3.  **진행**: 각 단계별로 커뮤니티 카드가 오픈되며, 최종 쇼다운에서 가장 높은 족보를 가진 플레이어가 승리합니다.
4.  **관전**: 게임 도중 입장한 플레이어는 해당 판이 끝날 때까지 관전 상태가 되며, 다음 판부터 카드를 받습니다.

## 📂 프로젝트 구조

```
poker/
├── backend/
│   ├── main.py          # Socket.IO 서버 설정 및 API 엔드포인트
│   ├── game_logic.py    # 포커 게임 로직 (덱, 핸드 평가, 상태 관리)
│   └── requirements.txt # 파이썬 의존성 목록
├── frontend/
│   ├── index.html       # 게임 클라이언트 UI (HTML/JS/CSS 통합)
│   └── image/           # (이미지 리소스 폴더)
└── README.md            # 프로젝트 설명서
```
