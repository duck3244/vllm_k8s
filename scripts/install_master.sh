# ==============================================================================
# scripts/install_master.sh - 마스터 설치 스크립트
# ==============================================================================
#!/bin/bash
# scripts/install_master.sh
# 전체 환경 마스터 설치 스크립트

set -e

# 색깔 정의
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
PURPLE='\033[0;35m'
NC='\033[0m'

log_info() { echo -e "${BLUE}[INFO]${NC} $1"; }
log_success() { echo -e "${GREEN}[SUCCESS]${NC} $1"; }
log_warning() { echo -e "${YELLOW}[WARNING]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }
log_step() { echo -e "${PURPLE}[STEP]${NC} $1"; }

# 설치 단계 정의
STEPS=(
    "system_update"
    "nvidia_setup"
    "docker_setup"
    "kubernetes_setup"
    "vllm_environment"
    "test_installation"
)

# 설치 진행 상황 저장
PROGRESS_FILE="/tmp/vllm_install_progress"

# 진행 상황 저장
save_progress() {
    echo "$1" > "$PROGRESS_FILE"
}

# 진행 상황 로드
load_progress() {
    if [ -f "$PROGRESS_FILE" ]; then
        cat "$PROGRESS_FILE"
    else
        echo "0"
    fi
}

# 설치 단계 실행
run_installation_step() {
    local step_number=$1
    local step_name=$2
    local script_name=$3

    log_step "단계 ${step_number}: ${step_name}"

    if [ -f "scripts/${script_name}" ]; then
        if bash "scripts/${script_name}"; then
            save_progress "$step_number"
            log_success "단계 ${step_number} 완료: ${step_name}"
        else
            log_error "단계 ${step_number} 실패: ${step_name}"
            exit 1
        fi
    else
        log_warning "스크립트를 찾을 수 없습니다: scripts/${script_name}"
    fi
}

# 메인 설치 함수
main() {
    log_info "🚀 vLLM API 서버 마스터 설치 시작"

    # 시작 진행도 확인
    CURRENT_STEP=$(load_progress)
    log_info "현재 진행 단계: $CURRENT_STEP"

    # 시스템 업데이트
    if [ "$CURRENT_STEP" -lt 1 ]; then
        run_installation_step 1 "시스템 업데이트" "system_update.sh"
    fi

    # NVIDIA 설정
    if [ "$CURRENT_STEP" -lt 2 ]; then
        log_warning "⚠️ NVIDIA 드라이버 설치 후 재부팅이 필요할 수 있습니다."
        read -p "NVIDIA 설정을 진행하시겠습니까? (y/N): " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            run_installation_step 2 "NVIDIA 드라이버 설치" "nvidia_setup.sh"

            log_warning "시스템을 재부팅한 후 install_continue.sh를 실행하세요."
            save_progress 2
            exit 0
        else
            save_progress 2
        fi
    fi

    # Docker 설정
    if [ "$CURRENT_STEP" -lt 3 ]; then
        run_installation_step 3 "Docker 설치" "docker_setup.sh"
    fi

    # Kubernetes 설정
    if [ "$CURRENT_STEP" -lt 4 ]; then
        read -p "Kubernetes를 설치하시겠습니까? (y/N): " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            run_installation_step 4 "Kubernetes 설치" "kubernetes_setup.sh"
        else
            save_progress 4
        fi
    fi

    # vLLM 환경 설정
    if [ "$CURRENT_STEP" -lt 5 ]; then
        run_installation_step 5 "vLLM 환경 설정" "setup.sh"
    fi

    # 설치 테스트
    if [ "$CURRENT_STEP" -lt 6 ]; then
        run_installation_step 6 "설치 테스트" "test_installation.sh"
    fi

    # 설치 완료
    rm -f "$PROGRESS_FILE"

    log_success "🎉 vLLM API 서버 설치 완료!"
    echo ""
    echo "다음 명령어로 서버를 시작할 수 있습니다:"
    echo "  source venv/bin/activate"
    echo "  python scripts/start_server.py"
    echo ""
    echo "또는 Docker로 실행:"
    echo "  docker compose up -d"
    echo ""
}