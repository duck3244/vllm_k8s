# ==============================================================================
# scripts/install_continue.sh - 재부팅 후 설치 계속
# ==============================================================================
#!/bin/bash
# scripts/install_continue.sh
# 재부팅 후 설치 계속 진행 스크립트

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

# 진행 상황 파일
PROGRESS_FILE="/tmp/vllm_install_progress"

main() {
    log_info "🔄 vLLM API 서버 설치 재개"

    # 진행 상황 확인
    if [ ! -f "$PROGRESS_FILE" ]; then
        log_error "진행 상황 파일을 찾을 수 없습니다."
        log_info "처음부터 설치를 시작하려면 install_master.sh를 실행하세요."
        exit 1
    fi

    CURRENT_STEP=$(cat "$PROGRESS_FILE")
    log_info "이전 설치 단계: $CURRENT_STEP"

    # NVIDIA 드라이버 확인
    if command -v nvidia-smi > /dev/null; then
        log_success "NVIDIA 드라이버가 정상적으로 설치되었습니다."
        nvidia-smi --query-gpu=name,driver_version --format=csv,noheader
    else
        log_warning "NVIDIA 드라이버를 확인할 수 없습니다."
    fi

    # 나머지 설치 계속
    log_info "설치를 계속 진행합니다..."
    exec bash scripts/install_master.sh
}

# 스크립트 실행 시작점
if [ "${BASH_SOURCE[0]}" = "${0}" ]; then
    case "${1:-main}" in
        "test")
            main
            ;;
        "main"|"")
            main "$@"
            ;;
        *)
            echo "사용법: $0 [test]"
            exit 1
            ;;
    esac
fi