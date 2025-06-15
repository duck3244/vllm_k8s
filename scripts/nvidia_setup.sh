#!/bin/bash
# scripts/nvidia_setup.sh
# NVIDIA 드라이버 및 CUDA 설치 스크립트

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

# 설정 변수
CUDA_VERSION=${CUDA_VERSION:-"12.4"}
DRIVER_VERSION=${DRIVER_VERSION:-"550"}
INSTALL_DOCKER_NVIDIA=${INSTALL_DOCKER_NVIDIA:-true}

# 도움말 함수
show_help() {
    cat << EOF
사용법: $0 [옵션]

옵션:
  --cuda-version VERSION    설치할 CUDA 버전 (기본값: 12.4)
  --driver-version VERSION  설치할 드라이버 버전 (기본값: 550)
  --no-docker-nvidia       NVIDIA Container Toolkit 설치 안 함
  --uninstall              기존 NVIDIA 드라이버 제거
  --check-only             GPU 및 드라이버 상태만 확인
  --help                   이 도움말 표시

예시:
  $0                                    # 기본 설정으로 설치
  $0 --cuda-version 11.8               # CUDA 11.8 설치
  $0 --driver-version 535              # 드라이버 535 설치
  $0 --uninstall                       # 기존 드라이버 제거
  $0 --check-only                      # 상태 확인만
EOF
}

# 명령행 인수 파싱
UNINSTALL=false
CHECK_ONLY=false

while [[ $# -gt 0 ]]; do
    case $1 in
        --cuda-version)
            CUDA_VERSION="$2"
            shift 2
            ;;
        --driver-version)
            DRIVER_VERSION="$2"
            shift 2
            ;;
        --no-docker-nvidia)
            INSTALL_DOCKER_NVIDIA=false
            shift
            ;;
        --uninstall)
            UNINSTALL=true
            shift
            ;;
        --check-only)
            CHECK_ONLY=true
            shift
            ;;
        --help)
            show_help
            exit 0
            ;;
        *)
            log_error "알 수 없는 옵션: $1"
            show_help
            exit 1
            ;;
    esac
done

# 시스템 정보 확인
detect_system() {
    log_step "🔍 시스템 정보 확인"
    
    if [ -f /etc/os-release ]; then
        . /etc/os-release
        OS=$NAME
        VERSION=$VERSION_ID
        CODENAME=${VERSION_CODENAME:-$VERSION_ID}
    else
        log_error "지원하지 않는 운영체제입니다."
        exit 1
    fi
    
    ARCH=$(uname -m)
    
    log_info "운영체제: $OS $VERSION"
    log_info "아키텍처: $ARCH"
    
    # 패키지 매니저 확인
    if command -v apt-get > /dev/null; then
        PACKAGE_MANAGER="apt"
    elif command -v yum > /dev/null; then
        PACKAGE_MANAGER="yum"
    elif command -v dnf > /dev/null; then
        PACKAGE_MANAGER="dnf"
    else
        log_error "지원하지 않는 패키지 매니저입니다."
        exit 1
    fi
    
    log_info "패키지 매니저: $PACKAGE_MANAGER"
}

# GPU 하드웨어 확인
check_gpu_hardware() {
    log_step "🔧 GPU 하드웨어 확인"
    
    # lspci로 NVIDIA GPU 확인
    if ! command -v lspci > /dev/null; then
        case $PACKAGE_MANAGER in
            apt) sudo apt-get update && sudo apt-get install -y pciutils ;;
            yum) sudo yum install -y pciutils ;;
            dnf) sudo dnf install -y pciutils ;;
        esac
    fi
    
    NVIDIA_GPUS=$(lspci | grep -i nvidia | grep -i vga)
    
    if [ -z "$NVIDIA_GPUS" ]; then
        log_error "NVIDIA GPU를 찾을 수 없습니다."
        log_info "lspci 출력:"
        lspci | grep -i vga
        exit 1
    fi
    
    log_success "NVIDIA GPU 감지:"
    echo "$NVIDIA_GPUS"
    
    # GPU 개수 확인
    GPU_COUNT=$(echo "$NVIDIA_GPUS" | wc -l)
    log_info "감지된 GPU 개수: $GPU_COUNT"
}

# 현재 드라이버 상태 확인
check_current_driver() {
    log_step "📋 현재 드라이버 상태 확인"
    
    # nvidia-smi 확인
    if command -v nvidia-smi > /dev/null; then
        log_info "현재 설치된 NVIDIA 드라이버:"
        nvidia-smi --query-gpu=name,driver_version,memory.total --format=csv,noheader,nounits
        
        CURRENT_DRIVER=$(nvidia-smi --query-gpu=driver_version --format=csv,noheader,nounits | head -1)
        log_info "현재 드라이버 버전: $CURRENT_DRIVER"
    else
        log_warning "NVIDIA 드라이버가 설치되지 않았습니다."
    fi
    
    # CUDA 확인
    if command -v nvcc > /dev/null; then
        CURRENT_CUDA=$(nvcc --version | grep release | sed 's/.*release //' | sed 's/,.*//')
        log_info "현재 CUDA 버전: $CURRENT_CUDA"
    else
        log_warning "CUDA가 설치되지 않았습니다."
    fi
    
    # 커널 모듈 확인
    if lsmod | grep -q nvidia; then
        log_info "NVIDIA 커널 모듈이 로드되어 있습니다:"
        lsmod | grep nvidia
    else
        log_warning "NVIDIA 커널 모듈이 로드되지 않았습니다."
    fi
}

# 기존 NVIDIA 드라이버 제거
uninstall_nvidia() {
    log_step "🗑️ 기존 NVIDIA 드라이버 제거"
    
    # NVIDIA 프로세스 종료
    sudo pkill -f nvidia || true
    
    # 커널 모듈 언로드
    sudo rmmod nvidia_drm nvidia_modeset nvidia_uvm nvidia || true
    
    case $PACKAGE_MANAGER in
        apt)
            # 모든 NVIDIA 관련 패키지 제거
            sudo apt-get remove --purge -y '*nvidia*' '*cuda*' '*cublas*' '*curand*' '*cufft*' '*cufile*' '*cusparse*' '*npp*' '*nvjpeg*' || true
            sudo apt-get autoremove -y
            ;;
        yum)
            sudo yum remove -y '*nvidia*' '*cuda*' || true
            ;;
        dnf)
            sudo dnf remove -y '*nvidia*' '*cuda*' || true
            ;;
    esac
    
    # NVIDIA 설정 파일 제거
    sudo rm -rf /etc/nvidia
    sudo rm -rf /usr/local/cuda*
    sudo rm -rf /opt/nvidia
    
    # 부팅 설정에서 nvidia 모듈 제거
    sudo sed -i '/nvidia/d' /etc/modules-load.d/* 2>/dev/null || true
    
    log_success "기존 NVIDIA 드라이버 제거 완료"
    log_warning "시스템 재부팅이 권장됩니다."
}

# NVIDIA 드라이버 저장소 추가
add_nvidia_repo() {
    log_step "📦 NVIDIA 저장소 추가"
    
    case $PACKAGE_MANAGER in
        apt)
            # NVIDIA 저장소 키 추가
            wget -qO - https://developer.download.nvidia.com/compute/cuda/repos/ubuntu$(echo $VERSION | tr -d .)/x86_64/3bf863cc.pub | sudo apt-key add -
            
            # CUDA 저장소 추가
            echo "deb https://developer.download.nvidia.com/compute/cuda/repos/ubuntu$(echo $VERSION | tr -d .)/x86_64 /" | sudo tee /etc/apt/sources.list.d/cuda.list
            
            # Machine Learning 저장소 추가
            echo "deb https://developer.download.nvidia.com/compute/machine-learning/repos/ubuntu$(echo $VERSION | tr -d .)/x86_64 /" | sudo tee /etc/apt/sources.list.d/nvidia-ml.list
            
            sudo apt-get update
            ;;
        yum)
            # CUDA 저장소 추가
            sudo yum-config-manager --add-repo https://developer.download.nvidia.com/compute/cuda/repos/rhel$(echo $VERSION | cut -d. -f1)/x86_64/cuda-rhel$(echo $VERSION | cut -d. -f1).repo
            ;;
        dnf)
            # CUDA 저장소 추가
            sudo dnf config-manager --add-repo https://developer.download.nvidia.com/compute/cuda/repos/fedora$(echo $VERSION)/x86_64/cuda-fedora$(echo $VERSION).repo
            ;;
    esac
    
    log_success "NVIDIA 저장소 추가 완료"
}

# NVIDIA 드라이버 설치
install_nvidia_driver() {
    log_step "🚀 NVIDIA 드라이버 설치"
    
    case $PACKAGE_MANAGER in
        apt)
            # 추천 드라이버 확인
            if command -v ubuntu-drivers > /dev/null; then
                log_info "시스템 추천 드라이버:"
                ubuntu-drivers devices
                
                # 자동 설치 또는 특정 버전 설치
                if [ "$DRIVER_VERSION" = "auto" ]; then
                    sudo ubuntu-drivers autoinstall
                else
                    sudo apt-get install -y nvidia-driver-$DRIVER_VERSION
                fi
            else
                # ubuntu-drivers가 없는 경우 직접 설치
                sudo apt-get install -y nvidia-driver-$DRIVER_VERSION
            fi
            
            # 개발 헤더 설치
            sudo apt-get install -y nvidia-dkms-$DRIVER_VERSION
            ;;
        yum)
            # EPEL 저장소 활성화
            sudo yum install -y epel-release
            
            # NVIDIA 드라이버 설치
            sudo yum install -y nvidia-driver nvidia-dkms
            ;;
        dnf)
            # RPM Fusion 저장소 활성화
            sudo dnf install -y https://download1.rpmfusion.org/free/fedora/rpmfusion-free-release-$(rpm -E %fedora).noarch.rpm
            sudo dnf install -y https://download1.rpmfusion.org/nonfree/fedora/rpmfusion-nonfree-release-$(rpm -E %fedora).noarch.rpm
            
            # NVIDIA 드라이버 설치
            sudo dnf install -y akmod-nvidia xorg-x11-drv-nvidia-cuda
            ;;
    esac
    
    log_success "NVIDIA 드라이버 설치 완료"
}

# CUDA Toolkit 설치
install_cuda() {
    log_step "⚡ CUDA Toolkit 설치"
    
    local cuda_package="cuda-toolkit-$(echo $CUDA_VERSION | tr . -)"
    
    case $PACKAGE_MANAGER in
        apt)
            sudo apt-get install -y $cuda_package
            
            # CUDA 샘플 설치 (선택사항)
            sudo apt-get install -y cuda-samples-$(echo $CUDA_VERSION | tr . -)
            ;;
        yum)
            sudo yum install -y cuda-toolkit-$CUDA_VERSION
            ;;
        dnf)
            sudo dnf install -y cuda-toolkit-$CUDA_VERSION
            ;;
    esac
    
    # CUDA 환경 변수 설정
    local cuda_path="/usr/local/cuda-$CUDA_VERSION"
    
    if [ -d "$cuda_path" ]; then
        # bashrc에 환경 변수 추가
        cat << EOF >> ~/.bashrc

# CUDA Environment Variables
export CUDA_HOME=$cuda_path
export PATH=\$CUDA_HOME/bin:\$PATH
export LD_LIBRARY_PATH=\$CUDA_HOME/lib64:\$LD_LIBRARY_PATH
EOF
        
        # 시스템 전체 환경 변수 설정
        cat << EOF | sudo tee /etc/environment.d/cuda.conf
CUDA_HOME=$cuda_path
PATH=$cuda_path/bin:\$PATH
LD_LIBRARY_PATH=$cuda_path/lib64:\$LD_LIBRARY_PATH
EOF
        
        # ldconfig 업데이트
        echo "$cuda_path/lib64" | sudo tee /etc/ld.so.conf.d/cuda.conf
        sudo ldconfig
        
        log_success "CUDA 환경 변수 설정 완료"
    fi
    
    log_success "CUDA Toolkit 설치 완료"
}

# cuDNN 설치
install_cudnn() {
    log_step "🧠 cuDNN 설치"
    
    case $PACKAGE_MANAGER in
        apt)
            # cuDNN 라이브러리 설치
            sudo apt-get install -y libcudnn8 libcudnn8-dev
            ;;
        yum)
            sudo yum install -y libcudnn8 libcudnn8-devel
            ;;
        dnf)
            sudo dnf install -y libcudnn8 libcudnn8-devel
            ;;
    esac
    
    log_success "cuDNN 설치 완료"
}

# NVIDIA Container Toolkit 설치
install_nvidia_docker() {
    log_step "🐳 NVIDIA Container Toolkit 설치"
    
    if ! command -v docker > /dev/null; then
        log_warning "Docker가 설치되지 않았습니다. Docker를 먼저 설치해주세요."
        return
    fi
    
    case $PACKAGE_MANAGER in
        apt)
            # NVIDIA Container Toolkit 저장소 추가
            curl -fsSL https://nvidia.github.io/libnvidia-container/gpgkey | sudo gpg --dearmor -o /usr/share/keyrings/nvidia-container-toolkit-keyring.gpg
            
            curl -s -L https://nvidia.github.io/libnvidia-container/stable/deb/nvidia-container-toolkit.list | \
                sed 's#deb https://#deb [signed-by=/usr/share/keyrings/nvidia-container-toolkit-keyring.gpg] https://#g' | \
                sudo tee /etc/apt/sources.list.d/nvidia-container-toolkit.list
            
            sudo apt-get update
            sudo apt-get install -y nvidia-container-toolkit
            ;;
        yum)
            curl -s -L https://nvidia.github.io/libnvidia-container/stable/rpm/nvidia-container-toolkit.repo | \
                sudo tee /etc/yum.repos.d/nvidia-container-toolkit.repo
            
            sudo yum install -y nvidia-container-toolkit
            ;;
        dnf)
            curl -s -L https://nvidia.github.io/libnvidia-container/stable/rpm/nvidia-container-toolkit.repo | \
                sudo tee /etc/yum.repos.d/nvidia-container-toolkit.repo
            
            sudo dnf install -y nvidia-container-toolkit
            ;;
    esac
    
    # Docker 설정 업데이트
    sudo nvidia-ctk runtime configure --runtime=docker
    sudo systemctl restart docker
    
    log_success "NVIDIA Container Toolkit 설치 완료"
}

# 설치 검증
verify_installation() {
    log_step "✅ 설치 검증"
    
    # NVIDIA 드라이버 확인
    if command -v nvidia-smi > /dev/null; then
        log_success "NVIDIA 드라이버 설치 확인:"
        nvidia-smi
    else
        log_error "nvidia-smi를 찾을 수 없습니다."
        return 1
    fi
    
    # CUDA 확인
    if command -v nvcc > /dev/null; then
        log_success "CUDA 설치 확인:"
        nvcc --version
        
        # CUDA 샘플 컴파일 테스트 (있는 경우)
        local samples_dir="/usr/local/cuda/samples"
        if [ -d "$samples_dir" ]; then
            log_info "CUDA 샘플 컴파일 테스트..."
            cd "$samples_dir/1_Utilities/deviceQuery"
            sudo make > /dev/null 2>&1
            if [ -x "./deviceQuery" ]; then
                log_success "CUDA 샘플 컴파일 성공"
                ./deviceQuery | grep "CUDA Capability"
            fi
        fi
    else
        log_warning "nvcc를 찾을 수 없습니다. 환경 변수를 확인해주세요."
    fi
    
    # Docker GPU 테스트
    if [ "$INSTALL_DOCKER_NVIDIA" = true ] && command -v docker > /dev/null; then
        log_info "Docker GPU 테스트..."
        if docker run --rm --gpus all nvidia/cuda:12.0-base-ubuntu20.04 nvidia-smi > /dev/null 2>&1; then
            log_success "Docker GPU 지원 확인"
        else
            log_warning "Docker GPU 테스트 실패"
        fi
    fi
}

# GPU 상태 모니터링 설정
setup_gpu_monitoring() {
    log_step "📊 GPU 모니터링 설정"
    
    # nvidia-ml-py 설치 (Python GPU 모니터링)
    if command -v pip3 > /dev/null; then
        pip3 install nvidia-ml-py3 --user
        log_success "nvidia-ml-py3 설치 완료"
    fi
    
    # GPU 모니터링 스크립트 생성
    cat << 'EOF' > /usr/local/bin/gpu-monitor
#!/bin/bash
# GPU 모니터링 스크립트

while true; do
    clear
    echo "=== GPU 상태 모니터링 ==="
    date
    echo ""
    
    nvidia-smi --query-gpu=index,name,temperature.gpu,utilization.gpu,utilization.memory,memory.used,memory.total,power.draw --format=csv,noheader,nounits
    
    echo ""
    echo "=== 프로세스 정보 ==="
    nvidia-smi pmon -c 1
    
    sleep 5
done
EOF
    
    sudo chmod +x /usr/local/bin/gpu-monitor
    log_success "GPU 모니터링 스크립트 생성: /usr/local/bin/gpu-monitor"
    
    # GPU 상태 확인 alias 추가
    echo "alias gpu-status='nvidia-smi'" >> ~/.bashrc
    echo "alias gpu-top='nvidia-smi dmon'" >> ~/.bashrc
    
    log_success "GPU 모니터링 설정 완료"
}

# 성능 최적화 설정
optimize_gpu_performance() {
    log_step "⚡ GPU 성능 최적화"
    
    # 지속성 모드 활성화
    sudo nvidia-smi -pm 1
    
    # 최대 성능 모드 설정
    for i in $(seq 0 $((GPU_COUNT-1))); do
        sudo nvidia-smi -i $i -pl $(nvidia-smi -i $i --query-gpu=power.max_limit --format=csv,noheader,nounits | tr -d ' ')
        sudo nvidia-smi -i $i -ac $(nvidia-smi -i $i --query-gpu=clocks.max.memory,clocks.max.sm --format=csv,noheader,nounits | tr -d ' ' | tr ',' ' ')
    done
    
    # NVIDIA MIG 모드 비활성화 (해당하는 경우)
    sudo nvidia-smi -mig 0 > /dev/null 2>&1 || true
    
    log_success "GPU 성능 최적화 완료"
}

# 메인 함수
main() {
    log_info "🚀 NVIDIA 드라이버 및 CUDA 설치 시작"
    log_info "CUDA 버전: $CUDA_VERSION"
    log_info "드라이버 버전: $DRIVER_VERSION"
    
    # 시스템 정보 확인
    detect_system
    
    # GPU 하드웨어 확인
    check_gpu_hardware
    
    # 현재 상태 확인
    check_current_driver
    
    # 상태 확인만 하는 경우
    if [ "$CHECK_ONLY" = true ]; then
        log_info "상태 확인 완료"
        exit 0
    fi
    
    # 제거 모드
    if [ "$UNINSTALL" = true ]; then
        uninstall_nvidia
        exit 0
    fi
    
    # 기존 설치 확인
    if command -v nvidia-smi > /dev/null; then
        log_warning "기존 NVIDIA 드라이버가 설치되어 있습니다."
        read -p "기존 드라이버를 제거하고 재설치하시겠습니까? (y/N): " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            uninstall_nvidia
            log_info "시스템을 재부팅한 후 스크립트를 다시 실행해주세요."
            exit 0
        fi
    fi
    
    # NVIDIA 저장소 추가
    add_nvidia_repo
    
    # NVIDIA 드라이버 설치
    install_nvidia_driver
    
    # CUDA Toolkit 설치
    install_cuda
    
    # cuDNN 설치
    install_cudnn
    
    # NVIDIA Container Toolkit 설치
    if [ "$INSTALL_DOCKER_NVIDIA" = true ]; then
        install_nvidia_docker
    fi
    
    # GPU 모니터링 설정
    setup_gpu_monitoring
    
    log_success "🎉 NVIDIA 설정 완료!"
    
    # 재부팅 안내
    log_warning "⚠️  시스템 재부팅이 필요합니다."
    echo ""
    echo "재부팅 후 다음 명령어로 설치를 확인하세요:"
    echo "  nvidia-smi"
    echo "  nvcc --version"
    echo "  gpu-monitor"
    echo ""
    
    read -p "지금 재부팅하시겠습니까? (y/N): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        sudo reboot
    else
        log_info "수동으로 재부팅해주세요: sudo reboot"
    fi
}

# 스크립트 실행
main "$@"