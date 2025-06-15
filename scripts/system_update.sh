#!/bin/bash
# scripts/system_update.sh
# 시스템 업데이트 및 기본 패키지 설치 스크립트

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

# 시스템 정보 확인
detect_system() {
    log_step "🔍 시스템 정보 확인"
    
    if [ -f /etc/os-release ]; then
        . /etc/os-release
        OS=$NAME
        VERSION=$VERSION_ID
        CODENAME=${VERSION_CODENAME:-$VERSION_ID}
    else
        OS=$(uname -s)
        VERSION=$(uname -r)
    fi
    
    ARCH=$(uname -m)
    
    log_info "운영체제: $OS $VERSION"
    log_info "아키텍처: $ARCH"
    log_info "커널: $(uname -r)"
    
    # 패키지 매니저 확인
    if command -v apt-get > /dev/null; then
        PACKAGE_MANAGER="apt"
    elif command -v yum > /dev/null; then
        PACKAGE_MANAGER="yum"
    elif command -v dnf > /dev/null; then
        PACKAGE_MANAGER="dnf"
    elif command -v pacman > /dev/null; then
        PACKAGE_MANAGER="pacman"
    elif command -v brew > /dev/null; then
        PACKAGE_MANAGER="brew"
    else
        log_error "지원하지 않는 패키지 매니저입니다."
        exit 1
    fi
    
    log_info "패키지 매니저: $PACKAGE_MANAGER"
}

# 시스템 업데이트
update_system() {
    log_step "📦 시스템 패키지 업데이트"
    
    case $PACKAGE_MANAGER in
        apt)
            log_info "APT 패키지 목록 업데이트..."
            sudo apt-get update
            
            log_info "설치된 패키지 업그레이드..."
            sudo apt-get upgrade -y
            
            log_info "불필요한 패키지 제거..."
            sudo apt-get autoremove -y
            sudo apt-get autoclean
            ;;
        yum)
            log_info "YUM 패키지 업데이트..."
            sudo yum update -y
            
            log_info "불필요한 패키지 제거..."
            sudo yum autoremove -y
            sudo yum clean all
            ;;
        dnf)
            log_info "DNF 패키지 업데이트..."
            sudo dnf update -y
            
            log_info "불필요한 패키지 제거..."
            sudo dnf autoremove -y
            sudo dnf clean all
            ;;
        pacman)
            log_info "Pacman 패키지 업데이트..."
            sudo pacman -Syu --noconfirm
            
            log_info "불필요한 패키지 제거..."
            sudo pacman -Rns $(pacman -Qtdq) --noconfirm || true
            ;;
        brew)
            log_info "Homebrew 업데이트..."
            brew update
            brew upgrade
            brew cleanup
            ;;
    esac
    
    log_success "시스템 업데이트 완료"
}

# 기본 개발 도구 설치
install_basic_tools() {
    log_step "🛠️ 기본 개발 도구 설치"
    
    case $PACKAGE_MANAGER in
        apt)
            sudo apt-get install -y \
                curl \
                wget \
                git \
                vim \
                nano \
                htop \
                tree \
                unzip \
                zip \
                tar \
                gzip \
                build-essential \
                software-properties-common \
                apt-transport-https \
                ca-certificates \
                gnupg \
                lsb-release \
                cmake \
                pkg-config \
                tmux \
                screen \
                jq \
                rsync \
                net-tools \
                iftop \
                iotop \
                ncdu \
                mc
            ;;
        yum)
            sudo yum groupinstall -y "Development Tools"
            sudo yum install -y \
                curl \
                wget \
                git \
                vim \
                nano \
                htop \
                tree \
                unzip \
                zip \
                tar \
                gzip \
                cmake \
                pkgconfig \
                tmux \
                screen \
                jq \
                rsync \
                net-tools \
                iftop \
                iotop \
                ncdu \
                mc
            ;;
        dnf)
            sudo dnf groupinstall -y "Development Tools"
            sudo dnf install -y \
                curl \
                wget \
                git \
                vim \
                nano \
                htop \
                tree \
                unzip \
                zip \
                tar \
                gzip \
                cmake \
                pkgconf-pkg-config \
                tmux \
                screen \
                jq \
                rsync \
                net-tools \
                iftop \
                iotop \
                ncdu \
                mc
            ;;
        pacman)
            sudo pacman -S --noconfirm \
                curl \
                wget \
                git \
                vim \
                nano \
                htop \
                tree \
                unzip \
                zip \
                tar \
                gzip \
                base-devel \
                cmake \
                pkg-config \
                tmux \
                screen \
                jq \
                rsync \
                net-tools \
                iftop \
                iotop \
                ncdu \
                mc
            ;;
        brew)
            brew install \
                curl \
                wget \
                git \
                vim \
                nano \
                htop \
                tree \
                unzip \
                zip \
                tar \
                gzip \
                cmake \
                pkg-config \
                tmux \
                screen \
                jq \
                rsync \
                mc
            ;;
    esac
    
    log_success "기본 개발 도구 설치 완료"
}

# Python 설치 및 설정
install_python() {
    log_step "🐍 Python 설치 및 설정"
    
    case $PACKAGE_MANAGER in
        apt)
            sudo apt-get install -y \
                python3 \
                python3-pip \
                python3-venv \
                python3-dev \
                python3-setuptools \
                python3-wheel
            ;;
        yum)
            sudo yum install -y \
                python3 \
                python3-pip \
                python3-devel \
                python3-setuptools \
                python3-wheel
            ;;
        dnf)
            sudo dnf install -y \
                python3 \
                python3-pip \
                python3-devel \
                python3-setuptools \
                python3-wheel
            ;;
        pacman)
            sudo pacman -S --noconfirm \
                python \
                python-pip \
                python-setuptools \
                python-wheel
            ;;
        brew)
            brew install python3
            ;;
    esac
    
    # pip 업그레이드
    python3 -m pip install --upgrade pip setuptools wheel
    
    log_success "Python 설치 및 설정 완료"
    log_info "Python 버전: $(python3 --version)"
    log_info "pip 버전: $(pip3 --version)"
}

# Node.js 설치
install_nodejs() {
    log_step "📦 Node.js 설치"
    
    if command -v node > /dev/null; then
        log_info "Node.js가 이미 설치되어 있습니다: $(node --version)"
        return
    fi
    
    # NodeSource 저장소 추가 및 설치
    case $PACKAGE_MANAGER in
        apt)
            curl -fsSL https://deb.nodesource.com/setup_lts.x | sudo -E bash -
            sudo apt-get install -y nodejs
            ;;
        yum)
            curl -fsSL https://rpm.nodesource.com/setup_lts.x | sudo bash -
            sudo yum install -y nodejs npm
            ;;
        dnf)
            curl -fsSL https://rpm.nodesource.com/setup_lts.x | sudo bash -
            sudo dnf install -y nodejs npm
            ;;
        pacman)
            sudo pacman -S --noconfirm nodejs npm
            ;;
        brew)
            brew install node
            ;;
    esac
    
    log_success "Node.js 설치 완료"
    log_info "Node.js 버전: $(node --version)"
    log_info "npm 버전: $(npm --version)"
}

# Docker 저장소 추가 (설치는 별도 스크립트에서)
add_docker_repo() {
    log_step "🐳 Docker 저장소 추가"
    
    case $PACKAGE_MANAGER in
        apt)
            # Docker의 공식 GPG 키 추가
            curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /usr/share/keyrings/docker-archive-keyring.gpg
            
            # Docker 저장소 추가
            echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/docker-archive-keyring.gpg] https://download.docker.com/linux/ubuntu $(lsb_release -cs) stable" | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null
            
            sudo apt-get update
            ;;
        yum)
            sudo yum install -y yum-utils
            sudo yum-config-manager --add-repo https://download.docker.com/linux/centos/docker-ce.repo
            ;;
        dnf)
            sudo dnf install -y dnf-plugins-core
            sudo dnf config-manager --add-repo https://download.docker.com/linux/fedora/docker-ce.repo
            ;;
    esac
    
    log_success "Docker 저장소 추가 완료"
}

# 시스템 최적화
optimize_system() {
    log_step "⚡ 시스템 최적화"
    
    # 스왑 설정 확인 및 최적화
    if [ -f /proc/swaps ]; then
        SWAP_SIZE=$(free -h | grep Swap | awk '{print $2}')
        if [ "$SWAP_SIZE" != "0B" ]; then
            log_info "현재 스왑 크기: $SWAP_SIZE"
            
            # vm.swappiness 설정 (기본값 60을 10으로 변경)
            echo "vm.swappiness=10" | sudo tee -a /etc/sysctl.conf
            sudo sysctl -p
            
            log_info "스왑 사용 빈도 최적화 (swappiness=10)"
        fi
    fi
    
    # 파일 디스크립터 제한 증가
    echo "* soft nofile 65536" | sudo tee -a /etc/security/limits.conf
    echo "* hard nofile 65536" | sudo tee -a /etc/security/limits.conf
    
    # 커널 파라미터 최적화
    cat << EOF | sudo tee -a /etc/sysctl.conf

# 네트워크 최적화
net.core.rmem_max = 16777216
net.core.wmem_max = 16777216
net.ipv4.tcp_rmem = 4096 12582912 16777216
net.ipv4.tcp_wmem = 4096 12582912 16777216
net.core.netdev_max_backlog = 5000

# 파일 시스템 최적화
fs.file-max = 2097152
fs.inotify.max_user_watches = 524288
EOF
    
    log_success "시스템 최적화 완료"
}

# 방화벽 기본 설정
configure_firewall() {
    log_step "🔥 방화벽 기본 설정"
    
    # UFW 설치 및 설정 (Ubuntu/Debian)
    if command -v ufw > /dev/null || [ "$PACKAGE_MANAGER" = "apt" ]; then
        if ! command -v ufw > /dev/null; then
            sudo apt-get install -y ufw
        fi
        
        # 기본 정책 설정
        sudo ufw --force reset
        sudo ufw default deny incoming
        sudo ufw default allow outgoing
        
        # SSH 허용
        sudo ufw allow ssh
        
        # HTTP/HTTPS 허용
        sudo ufw allow 80/tcp
        sudo ufw allow 443/tcp
        
        # vLLM API 포트 허용 (기본값: 8000)
        sudo ufw allow 8000/tcp
        
        # 방화벽 활성화
        sudo ufw --force enable
        
        log_success "UFW 방화벽 설정 완료"
        
    # firewalld 설정 (CentOS/RHEL/Fedora)
    elif command -v firewalld > /dev/null || [ "$PACKAGE_MANAGER" = "yum" ] || [ "$PACKAGE_MANAGER" = "dnf" ]; then
        if ! command -v firewalld > /dev/null; then
            case $PACKAGE_MANAGER in
                yum) sudo yum install -y firewalld ;;
                dnf) sudo dnf install -y firewalld ;;
            esac
        fi
        
        sudo systemctl enable firewalld
        sudo systemctl start firewalld
        
        # 기본 서비스 허용
        sudo firewall-cmd --permanent --add-service=ssh
        sudo firewall-cmd --permanent --add-service=http
        sudo firewall-cmd --permanent --add-service=https
        
        # vLLM API 포트 허용
        sudo firewall-cmd --permanent --add-port=8000/tcp
        
        sudo firewall-cmd --reload
        
        log_success "firewalld 설정 완료"
    else
        log_warning "지원하는 방화벽 도구를 찾을 수 없습니다."
    fi
}

# 시간 동기화 설정
setup_time_sync() {
    log_step "🕐 시간 동기화 설정"
    
    case $PACKAGE_MANAGER in
        apt)
            sudo apt-get install -y ntp
            sudo systemctl enable ntp
            sudo systemctl start ntp
            ;;
        yum|dnf)
            if [ "$PACKAGE_MANAGER" = "yum" ]; then
                sudo yum install -y ntp
            else
                sudo dnf install -y ntp
            fi
            sudo systemctl enable ntpd
            sudo systemctl start ntpd
            ;;
        pacman)
            sudo pacman -S --noconfirm ntp
            sudo systemctl enable ntpd
            sudo systemctl start ntpd
            ;;
    esac
    
    # 시간대 설정 (UTC 또는 로컬 시간대)
    if [ -z "${TIMEZONE:-}" ]; then
        TIMEZONE="UTC"
    fi
    
    sudo timedatectl set-timezone "$TIMEZONE"
    
    log_success "시간 동기화 설정 완료"
    log_info "현재 시간: $(date)"
    log_info "시간대: $(timedatectl show --property=Timezone --value)"
}

# 로그 로테이션 설정
setup_log_rotation() {
    log_step "📋 로그 로테이션 설정"
    
    # vLLM API 로그를 위한 logrotate 설정
    cat << EOF | sudo tee /etc/logrotate.d/vllm-api
/var/log/vllm-api/*.log {
    daily
    missingok
    rotate 30
    compress
    delaycompress
    notifempty
    create 644 $USER $USER
    postrotate
        systemctl reload vllm-api 2>/dev/null || true
    endscript
}
EOF
    
    # 로그 디렉토리 생성
    sudo mkdir -p /var/log/vllm-api
    sudo chown $USER:$USER /var/log/vllm-api
    
    log_success "로그 로테이션 설정 완료"
}

# 시스템 모니터링 도구 설치
install_monitoring_tools() {
    log_step "📊 시스템 모니터링 도구 설치"
    
    case $PACKAGE_MANAGER in
        apt)
            sudo apt-get install -y \
                htop \
                iotop \
                iftop \
                nethogs \
                ncdu \
                glances \
                sysstat \
                dstat
            ;;
        yum)
            sudo yum install -y \
                htop \
                iotop \
                iftop \
                nethogs \
                ncdu \
                glances \
                sysstat \
                dstat
            ;;
        dnf)
            sudo dnf install -y \
                htop \
                iotop \
                iftop \
                nethogs \
                ncdu \
                glances \
                sysstat \
                dstat
            ;;
        pacman)
            sudo pacman -S --noconfirm \
                htop \
                iotop \
                iftop \
                nethogs \
                ncdu \
                glances \
                sysstat \
                dstat
            ;;
        brew)
            brew install \
                htop \
                iftop \
                ncdu \
                glances
            ;;
    esac
    
    log_success "모니터링 도구 설치 완료"
}

# 성능 프로파일 설정
setup_performance_profile() {
    log_step "⚡ 성능 프로파일 설정"
    
    # tuned 설치 및 설정 (Linux만)
    if [ "$OS" != "Darwin" ]; then
        case $PACKAGE_MANAGER in
            apt)
                sudo apt-get install -y tuned
                ;;
            yum|dnf)
                if [ "$PACKAGE_MANAGER" = "yum" ]; then
                    sudo yum install -y tuned
                else
                    sudo dnf install -y tuned
                fi
                ;;
        esac
        
        if command -v tuned-adm > /dev/null; then
            sudo systemctl enable tuned
            sudo systemctl start tuned
            
            # 처리량 성능 프로파일 적용
            sudo tuned-adm profile throughput-performance
            
            log_success "성능 프로파일 설정 완료"
            log_info "활성 프로파일: $(sudo tuned-adm active)"
        fi
    fi
}

# 보안 업데이트 자동화
setup_auto_updates() {
    log_step "🔒 보안 업데이트 자동화 설정"
    
    case $PACKAGE_MANAGER in
        apt)
            sudo apt-get install -y unattended-upgrades
            
            # 자동 업데이트 설정
            cat << EOF | sudo tee /etc/apt/apt.conf.d/50unattended-upgrades
Unattended-Upgrade::Allowed-Origins {
    "\${distro_id}:\${distro_codename}-security";
    "\${distro_id}ESMApps:\${distro_codename}-apps-security";
    "\${distro_id}ESM:\${distro_codename}-infra-security";
};

Unattended-Upgrade::AutoFixInterruptedDpkg "true";
Unattended-Upgrade::MinimalSteps "true";
Unattended-Upgrade::Remove-Unused-Kernel-Packages "true";
Unattended-Upgrade::Remove-Unused-Dependencies "true";
Unattended-Upgrade::Automatic-Reboot "false";
EOF
            
            cat << EOF | sudo tee /etc/apt/apt.conf.d/20auto-upgrades
APT::Periodic::Update-Package-Lists "1";
APT::Periodic::Unattended-Upgrade "1";
APT::Periodic::AutocleanInterval "7";
EOF
            
            log_success "자동 보안 업데이트 설정 완료"
            ;;
        yum)
            sudo yum install -y yum-cron
            sudo systemctl enable yum-cron
            sudo systemctl start yum-cron
            log_success "yum-cron 자동 업데이트 설정 완료"
            ;;
        dnf)
            sudo dnf install -y dnf-automatic
            sudo systemctl enable dnf-automatic.timer
            sudo systemctl start dnf-automatic.timer
            log_success "dnf-automatic 자동 업데이트 설정 완료"
            ;;
    esac
}

# 시스템 정보 표시
show_system_info() {
    log_step "📋 시스템 정보 요약"
    
    echo ""
    echo "==================== 시스템 정보 ===================="
    echo "운영체제: $OS $VERSION"
    echo "아키텍처: $ARCH"
    echo "커널: $(uname -r)"
    echo "CPU: $(nproc) 코어"
    echo "메모리: $(free -h | grep '^Mem:' | awk '{print $2}')"
    echo "디스크 사용량:"
    df -h / | tail -1 | awk '{print "  루트 파티션: " $3 "/" $2 " (" $5 " 사용)"}'
    echo ""
    echo "==================== 설치된 도구 ===================="
    echo "Python: $(python3 --version 2>/dev/null || echo '설치되지 않음')"
    echo "pip: $(pip3 --version 2>/dev/null | cut -d' ' -f2 || echo '설치되지 않음')"
    echo "Git: $(git --version 2>/dev/null || echo '설치되지 않음')"
    echo "Docker: $(docker --version 2>/dev/null || echo '설치되지 않음')"
    echo "Node.js: $(node --version 2>/dev/null || echo '설치되지 않음')"
    echo "=================================================="
    echo ""
}

# 재부팅 필요 여부 확인
check_reboot_required() {
    if [ -f /var/run/reboot-required ]; then
        log_warning "⚠️  시스템 재부팅이 필요합니다."
        echo "다음 명령어로 재부팅하세요: sudo reboot"
        return 1
    fi
    return 0
}

# 메인 함수
main() {
    log_info "🚀 시스템 업데이트 및 최적화 시작"
    
    # 시스템 정보 확인
    detect_system
    
    # 시스템 업데이트
    update_system
    
    # 기본 도구 설치
    install_basic_tools
    
    # Python 설치
    install_python
    
    # Node.js 설치 (선택사항)
    read -p "Node.js를 설치하시겠습니까? (y/N): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        install_nodejs
    fi
    
    # Docker 저장소 추가
    add_docker_repo
    
    # 시스템 최적화
    optimize_system
    
    # 방화벽 설정
    read -p "방화벽을 설정하시겠습니까? (y/N): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        configure_firewall
    fi
    
    # 시간 동기화
    setup_time_sync
    
    # 로그 로테이션
    setup_log_rotation
    
    # 모니터링 도구
    install_monitoring_tools
    
    # 성능 프로파일
    setup_performance_profile
    
    # 자동 업데이트
    read -p "자동 보안 업데이트를 설정하시겠습니까? (y/N): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        setup_auto_updates
    fi
    
    # 시스템 정보 표시
    show_system_info
    
    # 재부팅 확인
    if ! check_reboot_required; then
        read -p "지금 재부팅하시겠습니까? (y/N): " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            log_info "시스템을 재부팅합니다..."
            sudo reboot
        fi
    fi
    
    log_success "🎉 시스템 업데이트 및 최적화 완료!"
}

# 스크립트 실행
main "$@"