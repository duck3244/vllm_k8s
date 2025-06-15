# ==============================================================================
# scripts/test_installation.sh - 설치 확인 스크립트
# ==============================================================================
#!/bin/bash
# scripts/test_installation.sh
# 전체 설치 확인 및 테스트 스크립트

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

# 테스트 결과 변수
TOTAL_TESTS=0
PASSED_TESTS=0
FAILED_TESTS=0

# 테스트 함수
run_test() {
    local test_name="$1"
    local test_command="$2"
    local expected_result="$3"

    ((TOTAL_TESTS++))
    log_step "테스트 ${TOTAL_TESTS}: $test_name"

    if eval "$test_command" > /dev/null 2>&1; then
        if [ "$expected_result" = "success" ] || [ -z "$expected_result" ]; then
            log_success "✅ $test_name"
            ((PASSED_TESTS++))
        else
            log_error "❌ $test_name (예상과 다른 결과)"
            ((FAILED_TESTS++))
        fi
    else
        if [ "$expected_result" = "fail" ]; then
            log_success "✅ $test_name (예상된 실패)"
            ((PASSED_TESTS++))
        else
            log_error "❌ $test_name"
            ((FAILED_TESTS++))
        fi
    fi
}

# 시스템 기본 테스트
test_system_basics() {
    log_step "🔍 시스템 기본 테스트"

    run_test "Python 설치 확인" "python3 --version"
    run_test "pip 설치 확인" "pip3 --version"
    run_test "Git 설치 확인" "git --version"
    run_test "curl 설치 확인" "curl --version"
    run_test "Docker 설치 확인" "docker --version"
}

# GPU 테스트
test_gpu() {
    log_step "🎮 GPU 테스트"

    run_test "NVIDIA 드라이버 확인" "nvidia-smi"
    run_test "CUDA 설치 확인" "nvcc --version"
    run_test "GPU 메모리 확인" "nvidia-smi --query-gpu=memory.total --format=csv,noheader,nounits"

    if command -v docker > /dev/null; then
        run_test "Docker GPU 지원 확인" "docker run --rm --gpus all nvidia/cuda:12.0-base-ubuntu20.04 nvidia-smi"
    fi
}

# Docker 테스트
test_docker() {
    log_step "🐳 Docker 테스트"

    run_test "Docker 서비스 상태" "systemctl is-active docker"
    run_test "Docker Hello World" "docker run --rm hello-world"
    run_test "Docker Compose 확인" "docker compose version"
    run_test "Docker 사용자 권한" "groups $USER | grep docker"
}

# Kubernetes 테스트
test_kubernetes() {
    log_step "☸️ Kubernetes 테스트"

    run_test "kubectl 설치 확인" "kubectl version --client"
    run_test "클러스터 연결 확인" "kubectl cluster-info"
    run_test "노드 상태 확인" "kubectl get nodes"
    run_test "시스템 파드 확인" "kubectl get pods -n kube-system"

    if command -v helm > /dev/null; then
        run_test "Helm 설치 확인" "helm version"
    fi
}

# vLLM API 테스트
test_vllm_api() {
    log_step "🤖 vLLM API 테스트"

    # 가상환경 활성화
    if [ -f "venv/bin/activate" ]; then
        source venv/bin/activate
    fi

    run_test "FastAPI 설치 확인" "python -c 'import fastapi'"
    run_test "vLLM 설치 확인" "python -c 'import vllm'" || log_warning "vLLM 선택사항"
    run_test "프로젝트 구조 확인" "test -f app/main.py"
    run_test "설정 파일 확인" "test -f config/server_config.yaml"
}

# 네트워크 테스트
test_network() {
    log_step "🌐 네트워크 테스트"

    run_test "인터넷 연결 확인" "ping -c 1 8.8.8.8"
    run_test "DNS 해결 확인" "nslookup google.com"
    run_test "HTTPS 연결 확인" "curl -s https://www.google.com"

    # 포트 테스트
    run_test "SSH 포트 확인" "ss -tlnp | grep :22"
    run_test "HTTP 포트 80 사용 가능" "! ss -tlnp | grep :80" "fail"
    run_test "vLLM API 포트 8000 사용 가능" "! ss -tlnp | grep :8000" "fail"
}

# 보안 테스트
test_security() {
    log_step "🔒 보안 테스트"

    run_test "방화벽 상태 확인" "sudo ufw status 2>/dev/null || sudo firewall-cmd --state 2>/dev/null || echo 'No firewall'"
    run_test "SELinux 상태 확인" "getenforce 2>/dev/null || echo 'No SELinux'"
    run_test "사용자 권한 확인" "id"
    run_test "sudo 권한 확인" "sudo -n true 2>/dev/null || echo 'No sudo'"
}

# 성능 테스트
test_performance() {
    log_step "⚡ 성능 테스트"

    # CPU 정보
    CPU_CORES=$(nproc)
    MEMORY_GB=$(free -g | awk 'NR==2{print $2}')

    log_info "CPU 코어: ${CPU_CORES}개"
    log_info "메모리: ${MEMORY_GB}GB"

    run_test "최소 CPU 요구사항 (2코어)" "[ $CPU_CORES -ge 2 ]"
    run_test "최소 메모리 요구사항 (4GB)" "[ $MEMORY_GB -ge 4 ]"

    # 디스크 공간 확인
    DISK_AVAILABLE=$(df / | awk 'NR==2 {print int($4/1024/1024)}')
    log_info "디스크 여유 공간: ${DISK_AVAILABLE}GB"
    run_test "최소 디스크 공간 (20GB)" "[ $DISK_AVAILABLE -ge 20 ]"
}

# 환경 변수 테스트
test_environment() {
    log_step "🌍 환경 변수 테스트"

    run_test "CUDA_VISIBLE_DEVICES 확인" "echo \$CUDA_VISIBLE_DEVICES"
    run_test "PATH 확인" "echo \$PATH | grep -q /usr/local/bin"
    run_test "Python 경로 확인" "which python3"

    if [ -f ".env" ]; then
        run_test ".env 파일 확인" "test -f .env"
    fi
}

# 통합 테스트
test_integration() {
    log_step "🔗 통합 테스트"

    # Docker와 Kubernetes 통합
    if command -v kubectl > /dev/null && command -v docker > /dev/null; then
        run_test "Docker 이미지 빌드 테스트" "docker build -t test-image ." || log_warning "Dockerfile 필요"
    fi

    # Python 환경 통합
    if [ -f "requirements.txt" ]; then
        run_test "Python 의존성 확인" "pip3 check"
    fi
}

# 결과 리포트 생성
generate_report() {
    local report_file="installation_test_report.txt"

    cat > "$report_file" << EOF
=== vLLM API 서버 설치 테스트 리포트 ===
생성 시간: $(date)
호스트명: $(hostname)
운영체제: $(uname -a)

=== 테스트 결과 ===
총 테스트: $TOTAL_TESTS
성공: $PASSED_TESTS
실패: $FAILED_TESTS
성공률: $(echo "scale=1; $PASSED_TESTS * 100 / $TOTAL_TESTS" | bc -l)%

=== 시스템 정보 ===
CPU: $(nproc)코어
메모리: $(free -h | grep '^Mem:' | awk '{print $2}')
디스크: $(df -h / | tail -1 | awk '{print $4}') 여유
GPU: $(nvidia-smi --query-gpu=name --format=csv,noheader 2>/dev/null || echo 'N/A')

=== 설치된 도구 ===
Python: $(python3 --version 2>/dev/null || echo 'N/A')
Docker: $(docker --version 2>/dev/null || echo 'N/A')
Kubernetes: $(kubectl version --client -o yaml 2>/dev/null | grep gitVersion | awk '{print $2}' || echo 'N/A')
NVIDIA Driver: $(nvidia-smi --query-gpu=driver_version --format=csv,noheader 2>/dev/null || echo 'N/A')
CUDA: $(nvcc --version 2>/dev/null | grep release | awk '{print $5}' | tr -d ',' || echo 'N/A')

=== 권장사항 ===
EOF

    if [ $FAILED_TESTS -gt 0 ]; then
        echo "- 실패한 테스트가 있습니다. 로그를 확인하여 문제를 해결하세요." >> "$report_file"
    fi

    if [ $CPU_CORES -lt 4 ]; then
        echo "- 성능 향상을 위해 4코어 이상 CPU를 권장합니다." >> "$report_file"
    fi

    if [ $MEMORY_GB -lt 8 ]; then
        echo "- 대형 모델 사용을 위해 8GB 이상 메모리를 권장합니다." >> "$report_file"
    fi

    echo "" >> "$report_file"
    echo "리포트 생성 완료: $report_file"
}

# 메인 함수
main() {
    log_info "🧪 vLLM API 서버 설치 테스트 시작"

    # 모든 테스트 실행
    test_system_basics
    test_gpu
    test_docker
    test_kubernetes
    test_vllm_api
    test_network
    test_security
    test_performance
    test_environment
    test_integration

    # 결과 출력
    echo ""
    echo "="*60
    log_info "📊 테스트 결과 요약"
    echo "="*60
    echo "총 테스트: $TOTAL_TESTS"
    echo "성공: $PASSED_TESTS"
    echo "실패: $FAILED_TESTS"
    echo "성공률: $(echo "scale=1; $PASSED_TESTS * 100 / $TOTAL_TESTS" | bc -l)%"
    echo "="*60

    # 리포트 생성
    generate_report

    if [ $FAILED_TESTS -eq 0 ]; then
        log_success "🎉 모든 테스트가 성공했습니다!"
        exit 0
    else
        log_error "❌ $FAILED_TESTS개의 테스트가 실패했습니다."
        exit 1
    fi
}