#!/bin/bash
# scripts/setup.sh
# vLLM API 서버 환경 설정 스크립트

set -e

# 색깔 정의
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
PURPLE='\033[0;35m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# 로그 함수
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

log_step() {
    echo -e "${PURPLE}[STEP]${NC} $1"
}

# 프로젝트 루트 디렉토리
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_ROOT"

# 환경 변수 설정
export PYTHONPATH="$PROJECT_ROOT:$PYTHONPATH"
export CUDA_VISIBLE_DEVICES=${CUDA_VISIBLE_DEVICES:-"0"}

log_info "🚀 vLLM API 서버 환경 설정 시작"
log_info "프로젝트 루트: $PROJECT_ROOT"

# 시스템 정보 확인
log_step "📋 시스템 정보 확인"
echo "OS: $(uname -s)"
echo "Kernel: $(uname -r)"
echo "Architecture: $(uname -m)"
echo "Python: $(python3 --version 2>/dev/null || echo 'Not installed')"
echo "CUDA: $(nvcc --version 2>/dev/null | grep release || echo 'Not installed')"

# 필수 시스템 패키지 설치
log_step "📦 시스템 패키지 업데이트 및 설치"
if command -v apt-get > /dev/null; then
    sudo apt-get update
    sudo apt-get install -y \
        python3 \
        python3-pip \
        python3-venv \
        python3-dev \
        build-essential \
        cmake \
        git \
        wget \
        curl \
        htop \
        tree \
        vim \
        tmux \
        unzip \
        software-properties-common \
        ca-certificates \
        gnupg \
        lsb-release
elif command -v yum > /dev/null; then
    sudo yum update -y
    sudo yum groupinstall -y "Development Tools"
    sudo yum install -y \
        python3 \
        python3-pip \
        python3-devel \
        cmake \
        git \
        wget \
        curl \
        htop \
        tree \
        vim \
        tmux \
        unzip
elif command -v brew > /dev/null; then
    brew update
    brew install python3 cmake git wget curl htop tree vim tmux
else
    log_warning "지원하지 않는 패키지 매니저입니다. 수동으로 의존성을 설치해주세요."
fi

# Python 가상환경 생성
log_step "🐍 Python 가상환경 설정"
VENV_DIR="$PROJECT_ROOT/venv"

if [ ! -d "$VENV_DIR" ]; then
    log_info "Python 가상환경 생성 중..."
    python3 -m venv "$VENV_DIR"
    log_success "가상환경 생성 완료: $VENV_DIR"
else
    log_info "가상환경이 이미 존재합니다: $VENV_DIR"
fi

# 가상환경 활성화
log_info "가상환경 활성화 중..."
source "$VENV_DIR/bin/activate"

# pip 업그레이드
log_info "pip 업그레이드 중..."
pip install --upgrade pip setuptools wheel

# CUDA 버전 확인 및 PyTorch 설치
log_step "🔥 PyTorch 및 CUDA 설정"
if command -v nvcc > /dev/null; then
    CUDA_VERSION=$(nvcc --version | grep release | sed 's/.*release //' | sed 's/,.*//')
    log_info "CUDA 버전: $CUDA_VERSION"
    
    # CUDA 11.8 또는 12.x에 따른 PyTorch 설치
    if [[ "$CUDA_VERSION" == "11.8" ]]; then
        pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu118
    elif [[ "$CUDA_VERSION" =~ ^12\. ]]; then
        pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121
    else
        log_warning "지원하지 않는 CUDA 버전: $CUDA_VERSION"
        log_info "CPU 버전의 PyTorch를 설치합니다."
        pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cpu
    fi
else
    log_warning "CUDA가 설치되지 않았습니다. CPU 버전의 PyTorch를 설치합니다."
    pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cpu
fi

# 프로젝트 의존성 설치
log_step "📋 프로젝트 의존성 설치"
if [ -f "requirements.txt" ]; then
    log_info "requirements.txt에서 의존성 설치 중..."
    pip install -r requirements.txt
    log_success "의존성 설치 완료"
else
    log_warning "requirements.txt 파일을 찾을 수 없습니다."
    log_info "기본 의존성을 설치합니다..."
    
    pip install \
        fastapi \
        uvicorn[standard] \
        vllm \
        transformers \
        accelerate \
        datasets \
        pydantic \
        python-multipart \
        aiofiles \
        httpx \
        pytest \
        pytest-asyncio \
        pytest-cov \
        black \
        isort \
        flake8 \
        mypy \
        pre-commit
fi

# 개발용 의존성 설치
log_step "🛠️ 개발용 의존성 설치"
if [ -f "requirements-dev.txt" ]; then
    log_info "개발용 의존성 설치 중..."
    pip install -r requirements-dev.txt
fi

# 디렉토리 구조 생성
log_step "📁 디렉토리 구조 생성"
mkdir -p logs
mkdir -p models/cache
mkdir -p config
mkdir -p tests/unit
mkdir -p tests/integration
mkdir -p tests/logs
mkdir -p tests/reports
mkdir -p data
mkdir -p docs
mkdir -p htmlcov

log_success "디렉토리 구조 생성 완료"

# 설정 파일 생성
log_step "⚙️ 기본 설정 파일 생성"

# 환경 변수 파일 생성
if [ ! -f ".env" ]; then
    cat > .env << EOF
# vLLM API 서버 환경 변수
DEBUG=True
LOG_LEVEL=INFO
SERVER_HOST=0.0.0.0
SERVER_PORT=8000
WORKERS=1

# 모델 설정
MODEL_NAME=microsoft/DialoGPT-medium
MODEL_CACHE_DIR=./models/cache
MAX_TOKENS=512
TEMPERATURE=0.7

# CUDA 설정
CUDA_VISIBLE_DEVICES=0

# 로그 설정
LOG_DIR=./logs
LOG_FILE=vllm_api.log
EOF
    log_success ".env 파일 생성 완료"
fi

# 기본 서버 설정 파일 생성
if [ ! -f "config/server_config.yaml" ]; then
    cat > config/server_config.yaml << EOF
# vLLM API 서버 설정
server:
  host: "0.0.0.0"
  port: 8000
  workers: 1
  reload: true
  log_level: "info"

model:
  name: "microsoft/DialoGPT-medium"
  cache_dir: "./models/cache"
  max_tokens: 512
  temperature: 0.7
  top_p: 0.9
  top_k: 50

vllm:
  tensor_parallel_size: 1
  gpu_memory_utilization: 0.9
  max_model_len: 2048
  trust_remote_code: false

logging:
  level: "INFO"
  format: "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
  file: "./logs/vllm_api.log"
  max_bytes: 10485760  # 10MB
  backup_count: 5
EOF
    log_success "서버 설정 파일 생성 완료"
fi

# Git hooks 설정
log_step "🔧 Git hooks 설정"
if [ -d ".git" ]; then
    if command -v pre-commit > /dev/null; then
        pre-commit install
        log_success "pre-commit hooks 설치 완료"
    else
        log_warning "pre-commit이 설치되지 않았습니다."
    fi
fi

# pytest 설정 파일 생성
if [ ! -f "pytest.ini" ]; then
    cat > pytest.ini << EOF
[tool:pytest]
testpaths = tests
python_files = test_*.py
python_classes = Test*
python_functions = test_*
addopts = 
    -v
    --tb=short
    --strict-markers
    --disable-warnings
markers =
    unit: Unit tests
    integration: Integration tests
    slow: Slow tests
    gpu: GPU tests
    ray: Ray tests
EOF
    log_success "pytest 설정 파일 생성 완료"
fi

# 권한 설정
log_step "🔐 스크립트 실행 권한 설정"
chmod +x scripts/*.sh
chmod +x scripts/*.py 2>/dev/null || true

# 환경 검증
log_step "✅ 환경 검증"
log_info "Python 버전: $(python --version)"
log_info "pip 버전: $(pip --version)"

# PyTorch 설치 확인
python -c "import torch; print(f'PyTorch 버전: {torch.__version__}')" 2>/dev/null && log_success "PyTorch 설치 확인" || log_error "PyTorch 설치 실패"

# CUDA 사용 가능 여부 확인
python -c "import torch; print(f'CUDA 사용 가능: {torch.cuda.is_available()}')" 2>/dev/null

# FastAPI 설치 확인
python -c "import fastapi; print(f'FastAPI 버전: {fastapi.__version__}')" 2>/dev/null && log_success "FastAPI 설치 확인" || log_error "FastAPI 설치 실패"

# vLLM 설치 확인 (선택사항)
python -c "import vllm; print(f'vLLM 설치 확인')" 2>/dev/null && log_success "vLLM 설치 확인" || log_warning "vLLM 설치 확인 실패 (선택사항)"

# 완료 메시지
echo ""
log_success "🎉 vLLM API 서버 환경 설정 완료!"
echo ""
echo "다음 명령어로 서버를 시작할 수 있습니다:"
echo "  source venv/bin/activate"
echo "  python scripts/start_server.py --mode dev"
echo ""
echo "또는 테스트를 실행할 수 있습니다:"
echo "  python tests/run_tests.py"
echo ""
echo "API 문서는 다음에서 확인할 수 있습니다:"
echo "  http://localhost:8000/docs"
echo ""

log_info "환경 설정이 완료되었습니다. 개발을 시작하세요! 🚀"