# vLLM API Server 프로젝트 파일 구조

```
vllm-k8s-project/
├── 📁 app/                              # 메인 애플리케이션 코드
│   ├── 📄 __init__.py                   # 패키지 초기화
│   ├── 🚀 main.py                       # FastAPI 애플리케이션 진입점
│   │
│   ├── 📁 core/                         # 핵심 모듈
│   │   ├── 📄 __init__.py               # 패키지 초기화
│   │   ├── ⚙️ config.py                 # 설정 관리 (환경변수, vLLM 설정)
│   │   └── 📝 logging.py                # 로깅 시스템 (색상 포매터, 성능 로거)
│   │
│   ├── 📁 models/                       # 데이터 모델
│   │   ├── 📄 __init__.py               # 패키지 초기화
│   │   └── 📋 schemas.py                # Pydantic 스키마 (요청/응답 모델)
│   │
│   ├── 📁 services/                     # 비즈니스 로직 서비스
│   │   ├── 📄 __init__.py               # 패키지 초기화
│   │   ├── 🤖 vllm_engine.py            # vLLM 엔진 Ray Actor 및 관리
│   │   ├── ☁️ ray_service.py            # Ray 클러스터 연결 및 관리
│   │   └── 📊 model_monitor.py          # 모델 상태 모니터링 서비스
│   │
│   └── 📁 api/                          # API 레이어
│       ├── 📄 __init__.py               # 패키지 초기화
│       ├── 🔀 routes.py                 # API 엔드포인트 라우터
│       └── 🔗 dependencies.py          # FastAPI 의존성 주입
│
├── 📁 k8s/                              # Kubernetes 매니페스트
│   ├── 🎮 gpu-operator.yaml            # NVIDIA GPU Operator 설정
│   ├── ⚡ ray-cluster.yaml              # Ray Cluster 정의
│   ├── 🚀 vllm-deployment.yaml         # vLLM API 서버 배포
│   ├── ⚙️ configmap.yaml               # 설정 데이터
│   └── 📊 monitoring.yaml              # 모니터링 설정
│
├── 📁 docker/                           # Docker 관련 파일
│   ├── 🐳 Dockerfile                    # 멀티스테이지 컨테이너 이미지
│   └── 📦 requirements.txt             # Python 의존성
│
├── 📁 scripts/                          # 설치 및 배포 스크립트
│   ├── 🔧 setup.sh                     # 환경 설정 스크립트
│   ├── 🚀 deploy.sh                    # 배포 스크립트
│   ├── 🧪 test_api.sh                  # API 테스트 스크립트
│   ├── 💻 system_update.sh             # 시스템 업데이트
│   ├── 🎮 nvidia_setup.sh              # NVIDIA 드라이버 설치
│   ├── 🐳 docker_setup.sh              # Docker 설치
│   ├── ☸️ kubernetes_setup.sh          # Kubernetes 설치
│   ├── 🎯 k8s_cluster_init.sh          # 클러스터 초기화
│   ├── 🎮 gpu_operator_setup.sh        # GPU Operator 설치
│   ├── ⚡ ray_operator_setup.sh        # Ray Operator 설치
│   ├── 🤖 vllm_setup.sh                # vLLM 환경 설정
│   ├── ✅ test_installation.sh         # 설치 확인
│   ├── 🎯 install_master.sh            # 마스터 설치 스크립트
│   └── ➡️ install_continue.sh          # 재부팅 후 설치 계속
│
├── 📁 tests/                            # 테스트 코드 (선택사항)
│   ├── 📄 __init__.py                   # 패키지 초기화
│   ├── 🧪 test_api.py                  # API 테스트
│   ├── 🧪 test_vllm_service.py         # vLLM 서비스 테스트
│   ├── 🧪 test_ray_service.py          # Ray 서비스 테스트
│   └── 🧪 test_model_monitor.py        # 모델 모니터링 테스트
│
├── 📁 docs/                             # 문서 (선택사항)
│   ├── 📖 api.md                       # API 문서
│   ├── 🚀 deployment.md               # 배포 가이드
│   └── 🔧 troubleshooting.md          # 문제 해결 가이드
│
├── 📁 examples/                         # 사용 예제
│   ├── 🐍 model_status_example.py      # 모델 상태 체크 예제
│   ├── 🧪 api_client_example.py        # API 클라이언트 예제
│   └── 📊 monitoring_dashboard.py      # 모니터링 대시보드 예제
│
├── 📁 logs/                             # 로그 파일 (런타임 생성)
│   ├── 📝 app.log                      # 애플리케이션 로그
│   ├── 📝 error.log                    # 에러 로그
│   └── 📝 access.log                   # 액세스 로그
│
├── 📁 models/                           # 모델 저장소 (마운트 포인트)
│   └── 🤖 llama-3.2-3b-instruct/       # Llama 모델 디렉토리
│       ├── 📄 config.json              # 모델 설정
│       ├── 📄 tokenizer.json           # 토크나이저
│       └── 📦 pytorch_model.bin        # 모델 가중치
│
├── 📄 .env.example                     # 환경변수 설정 예제
├── 📄 .env                             # 실제 환경변수 (git에서 제외)
├── 📄 .gitignore                       # Git 무시 파일
├── 📄 README.md                        # 프로젝트 메인 문서
├── 📄 LICENSE                          # 라이선스 파일
├── 📄 pyproject.toml                   # Python 프로젝트 설정 (선택사항)
└── 📄 docker-compose.yml               # 로컬 개발용 Docker Compose (선택사항)
```

## 📂 **주요 디렉토리 설명**

### **🚀 `app/` - 메인 애플리케이션**
애플리케이션의 핵심 코드가 위치하는 디렉토리입니다.

- **`main.py`**: FastAPI 애플리케이션 진입점, 라이프사이클 관리
- **`core/`**: 설정 관리와 로깅 시스템
- **`models/`**: Pydantic 데이터 모델 및 스키마
- **`services/`**: 비즈니스 로직 (vLLM, Ray, 모니터링)
- **`api/`**: REST API 엔드포인트와 의존성 주입

### **☸️ `k8s/` - Kubernetes 매니페스트**
Kubernetes 클러스터 배포를 위한 YAML 파일들입니다.

- **`ray-cluster.yaml`**: Ray 클러스터 정의
- **`vllm-deployment.yaml`**: API 서버 배포 설정
- **`gpu-operator.yaml`**: NVIDIA GPU 리소스 관리
- **`configmap.yaml`**: 환경변수 및 설정 데이터

### **🐳 `docker/` - 컨테이너 설정**
Docker 이미지 빌드와 관련된 파일들입니다.

- **`Dockerfile`**: 멀티스테이지 빌드로 최적화된 이미지
- **`requirements.txt`**: Python 의존성 명세

### **🔧 `scripts/` - 설치 및 배포 스크립트**
시스템 설치부터 배포까지의 자동화 스크립트들입니다.

- **`install_master.sh`**: 전체 설치 프로세스 관리
- **`setup.sh`**: 개발 환경 설정
- **`deploy.sh`**: Kubernetes 배포 자동화

## 🏗️ **파일별 역할**

### **핵심 애플리케이션 파일**

| 파일 | 역할 | 주요 기능 |
|------|------|-----------|
| `app/main.py` | 애플리케이션 진입점 | FastAPI 앱, 라이프사이클, 미들웨어 |
| `app/core/config.py` | 설정 관리 | 환경변수, vLLM 설정, 검증 |
| `app/core/logging.py` | 로깅 시스템 | 구조화된 로깅, 성능 추적 |
| `app/models/schemas.py` | 데이터 모델 | Pydantic 스키마, 검증 |
| `app/services/vllm_engine.py` | vLLM 엔진 | Ray Actor, 텍스트 생성 |
| `app/services/ray_service.py` | Ray 관리 | 클러스터 연결, 리소스 관리 |
| `app/services/model_monitor.py` | 모델 모니터링 | 헬스체크, 메트릭 수집 |
| `app/api/routes.py` | API 엔드포인트 | REST API, 라우팅 |
| `app/api/dependencies.py` | 의존성 주입 | 인증, Rate Limiting |

### **배포 관련 파일**

| 파일 | 역할 | 설명 |
|------|------|------|
| `k8s/ray-cluster.yaml` | Ray 클러스터 | Head + Worker 노드 정의 |
| `k8s/vllm-deployment.yaml` | API 서버 배포 | Pod, Service, 리소스 할당 |
| `docker/Dockerfile` | 컨테이너 이미지 | 멀티스테이지 빌드 |
| `.env.example` | 환경변수 템플릿 | 설정 값 예제 |

## 🚀 **개발 워크플로우**

### **1. 로컬 개발**
```bash
# 1. 프로젝트 클론
git clone <repository>
cd vllm-k8s-project

# 2. 환경 설정
cp .env.example .env
# .env 파일 수정

# 3. Python 환경 설정
python3.9 -m venv vllm-env
source vllm-env/bin/activate
pip install -r docker/requirements.txt

# 4. 로컬 실행
python -m app.main
```

### **2. 컨테이너 개발**
```bash
# Docker 이미지 빌드
docker build -f docker/Dockerfile -t vllm-api:dev .

# 컨테이너 실행
docker run -p 8000:8000 --env-file .env vllm-api:dev
```

### **3. Kubernetes 배포**
```bash
# 클러스터 배포
./scripts/deploy.sh

# 상태 확인
kubectl get pods
kubectl get svc
```

## 📝 **파일 생성 순서**

프로젝트를 처음부터 구성할 때의 권장 순서입니다:

1. **기본 구조 생성**
   ```bash
   mkdir -p app/{core,models,services,api}
   mkdir -p k8s docker scripts tests docs examples
   touch app/__init__.py app/{core,models,services,api}/__init__.py
   ```

2. **핵심 파일 생성**
   - `app/core/config.py` (설정)
   - `app/core/logging.py` (로깅)
   - `app/models/schemas.py` (데이터 모델)

3. **서비스 레이어**
   - `app/services/ray_service.py` (Ray 연결)
   - `app/services/vllm_engine.py` (vLLM 엔진)
   - `app/services/model_monitor.py` (모니터링)

4. **API 레이어**
   - `app/api/dependencies.py` (의존성)
   - `app/api/routes.py` (엔드포인트)
   - `app/main.py` (메인 앱)

5. **배포 설정**
   - `docker/Dockerfile`, `docker/requirements.txt`
   - `k8s/*.yaml` 파일들
   - `.env.example`

이 구조는 확장 가능하고 유지보수하기 쉬운 마이크로서비스 아키텍처를 제공합니다! 🎯