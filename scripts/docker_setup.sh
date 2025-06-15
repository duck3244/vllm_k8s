#!/bin/bash
# scripts/docker_setup.sh
# Docker 및 Docker Compose 설치 스크립트

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

# 기본 설정
DOCKER_COMPOSE_VERSION=${DOCKER_COMPOSE_VERSION:-"v2.24.0"}
INSTALL_PORTAINER=${INSTALL_PORTAINER:-false}
CONFIGURE_LOGGING=${CONFIGURE_LOGGING:-true}
SETUP_REGISTRY=${SETUP_REGISTRY:-false}

# 도움말 함수
show_help() {
    cat << EOF
사용법: $0 [옵션]

옵션:
  --compose-version VERSION  Docker Compose 버전 (기본값: v2.24.0)
  --with-portainer          Portainer 설치
  --with-registry           Docker Registry 설정
  --no-logging              로깅 설정 안 함
  --uninstall               Docker 완전 제거
  --user-only               현재 사용자만 Docker 그룹에 추가
  --help                    이 도움말 표시

예시:
  $0                              # 기본 설치
  $0 --with-portainer            # Portainer와 함께 설치
  $0 --compose-version v2.25.0   # 특정 Compose 버전 설치
  $0 --uninstall                 # Docker 제거
EOF
}

# 명령행 인수 파싱
UNINSTALL=false
USER_ONLY=false

while [[ $# -gt 0 ]]; do
    case $1 in
        --compose-version)
            DOCKER_COMPOSE_VERSION="$2"
            shift 2
            ;;
        --with-portainer)
            INSTALL_PORTAINER=true
            shift
            ;;
        --with-registry)
            SETUP_REGISTRY=true
            shift
            ;;
        --no-logging)
            CONFIGURE_LOGGING=false
            shift
            ;;
        --uninstall)
            UNINSTALL=true
            shift
            ;;
        --user-only)
            USER_ONLY=true
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

# 기존 Docker 제거
uninstall_docker() {
    log_step "🗑️ 기존 Docker 제거"
    
    # Docker 서비스 중지
    sudo systemctl stop docker docker.socket containerd 2>/dev/null || true
    
    case $PACKAGE_MANAGER in
        apt)
            # 기존 Docker 패키지 제거
            sudo apt-get remove -y docker docker-engine docker.io containerd runc docker-ce docker-ce-cli containerd.io docker-compose-plugin 2>/dev/null || true
            sudo apt-get purge -y docker-ce docker-ce-cli containerd.io docker-compose-plugin 2>/dev/null || true
            sudo apt-get autoremove -y
            ;;
        yum)
            sudo yum remove -y docker docker-client docker-client-latest docker-common docker-latest docker-latest-logrotate docker-logrotate docker-engine docker-ce docker-ce-cli containerd.io 2>/dev/null || true
            ;;
        dnf)
            sudo dnf remove -y docker docker-client docker-client-latest docker-common docker-latest docker-latest-logrotate docker-logrotate docker-selinux docker-engine-selinux docker-engine docker-ce docker-ce-cli containerd.io 2>/dev/null || true
            ;;
    esac
    
    # Docker 데이터 디렉토리 제거
    sudo rm -rf /var/lib/docker
    sudo rm -rf /var/lib/containerd
    sudo rm -rf /etc/docker
    sudo rm -rf /etc/containerd
    
    # Docker 그룹 제거
    sudo groupdel docker 2>/dev/null || true
    
    # Docker 저장소 제거
    sudo rm -f /etc/apt/sources.list.d/docker.list
    sudo rm -f /etc/yum.repos.d/docker-ce.repo
    
    log_success "Docker 제거 완료"
}

# 필수 패키지 설치
install_prerequisites() {
    log_step "📦 필수 패키지 설치"
    
    case $PACKAGE_MANAGER in
        apt)
            sudo apt-get update
            sudo apt-get install -y \
                apt-transport-https \
                ca-certificates \
                curl \
                gnupg \
                lsb-release \
                software-properties-common
            ;;
        yum)
            sudo yum install -y \
                yum-utils \
                device-mapper-persistent-data \
                lvm2 \
                curl
            ;;
        dnf)
            sudo dnf install -y \
                dnf-plugins-core \
                device-mapper-persistent-data \
                lvm2 \
                curl
            ;;
    esac
    
    log_success "필수 패키지 설치 완료"
}

# Docker 저장소 추가
add_docker_repo() {
    log_step "📋 Docker 공식 저장소 추가"
    
    case $PACKAGE_MANAGER in
        apt)
            # Docker GPG 키 추가
            curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /usr/share/keyrings/docker-archive-keyring.gpg
            
            # Docker 저장소 추가
            echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/docker-archive-keyring.gpg] https://download.docker.com/linux/ubuntu $(lsb_release -cs) stable" | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null
            
            sudo apt-get update
            ;;
        yum)
            sudo yum-config-manager --add-repo https://download.docker.com/linux/centos/docker-ce.repo
            ;;
        dnf)
            sudo dnf config-manager --add-repo https://download.docker.com/linux/fedora/docker-ce.repo
            ;;
    esac
    
    log_success "Docker 저장소 추가 완료"
}

# Docker Engine 설치
install_docker_engine() {
    log_step "🐳 Docker Engine 설치"
    
    case $PACKAGE_MANAGER in
        apt)
            sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-compose-plugin
            ;;
        yum)
            sudo yum install -y docker-ce docker-ce-cli containerd.io docker-compose-plugin
            ;;
        dnf)
            sudo dnf install -y docker-ce docker-ce-cli containerd.io docker-compose-plugin
            ;;
    esac
    
    # Docker 서비스 시작 및 활성화
    sudo systemctl start docker
    sudo systemctl enable docker
    
    log_success "Docker Engine 설치 완료"
    log_info "Docker 버전: $(docker --version)"
}

# Docker 그룹 설정
setup_docker_group() {
    log_step "👥 Docker 그룹 설정"
    
    # docker 그룹 생성
    sudo groupadd docker 2>/dev/null || true
    
    if [ "$USER_ONLY" = true ]; then
        # 현재 사용자만 추가
        sudo usermod -aG docker $USER
        log_success "사용자 $USER를 docker 그룹에 추가했습니다."
    else
        # 모든 관리자 사용자 추가
        for user in $(getent group sudo | cut -d: -f4 | tr ',' ' '); do
            if [ -n "$user" ]; then
                sudo usermod -aG docker $user
                log_info "사용자 $user를 docker 그룹에 추가했습니다."
            fi
        done
    fi
    
    log_warning "변경사항을 적용하려면 로그아웃 후 다시 로그인하세요."
}

# Docker Compose 설치
install_docker_compose() {
    log_step "🔧 Docker Compose 설치"
    
    # Docker Compose V2는 이미 플러그인으로 설치됨
    if docker compose version > /dev/null 2>&1; then
        log_success "Docker Compose 플러그인이 이미 설치되어 있습니다."
        log_info "버전: $(docker compose version)"
        return
    fi
    
    # 독립 실행형 Docker Compose 설치
    log_info "독립 실행형 Docker Compose 설치 중..."
    
    sudo curl -L "https://github.com/docker/compose/releases/download/${DOCKER_COMPOSE_VERSION}/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
    sudo chmod +x /usr/local/bin/docker-compose
    
    # 심볼릭 링크 생성
    sudo ln -sf /usr/local/bin/docker-compose /usr/bin/docker-compose
    
    log_success "Docker Compose 설치 완료"
    log_info "버전: $(docker-compose --version)"
}

# Docker 로깅 설정
configure_docker_logging() {
    log_step "📝 Docker 로깅 설정"
    
    # Docker 데몬 설정 디렉토리 생성
    sudo mkdir -p /etc/docker
    
    # Docker 데몬 설정 파일 생성
    cat << EOF | sudo tee /etc/docker/daemon.json
{
  "log-driver": "json-file",
  "log-opts": {
    "max-size": "100m",
    "max-file": "3"
  },
  "storage-driver": "overlay2",
  "storage-opts": [
    "overlay2.override_kernel_check=true"
  ],
  "exec-opts": ["native.cgroupdriver=systemd"],
  "live-restore": true,
  "userland-proxy": false,
  "experimental": false,
  "metrics-addr": "127.0.0.1:9323",
  "default-runtime": "runc"
}
EOF
    
    # Docker 서비스 재시작
    sudo systemctl restart docker
    
    log_success "Docker 로깅 설정 완료"
}

# Docker 시스템 정리 cronjob 설정
setup_docker_cleanup() {
    log_step "🧹 Docker 시스템 정리 설정"
    
    # 정리 스크립트 생성
    cat << 'EOF' | sudo tee /usr/local/bin/docker-cleanup
#!/bin/bash
# Docker 시스템 정리 스크립트

# 사용하지 않는 컨테이너 제거
docker container prune -f

# 사용하지 않는 이미지 제거
docker image prune -a -f

# 사용하지 않는 볼륨 제거
docker volume prune -f

# 사용하지 않는 네트워크 제거
docker network prune -f

# 시스템 전체 정리
docker system prune -f

echo "Docker 시스템 정리 완료: $(date)"
EOF
    
    sudo chmod +x /usr/local/bin/docker-cleanup
    
    # 주간 정리 cronjob 추가
    (crontab -l 2>/dev/null; echo "0 3 * * 0 /usr/local/bin/docker-cleanup >> /var/log/docker-cleanup.log 2>&1") | crontab -
    
    log_success "Docker 자동 정리 설정 완료 (매주 일요일 03:00)"
}

# Portainer 설치
install_portainer() {
    log_step "🎛️ Portainer 설치"
    
    # Portainer 볼륨 생성
    docker volume create portainer_data
    
    # Portainer 컨테이너 실행
    docker run -d \
        --name portainer \
        --restart unless-stopped \
        -p 9000:9000 \
        -p 9443:9443 \
        -v /var/run/docker.sock:/var/run/docker.sock \
        -v portainer_data:/data \
        portainer/portainer-ce:latest
    
    log_success "Portainer 설치 완료"
    log_info "Portainer 웹 인터페이스: https://localhost:9443"
}

# Docker Registry 설정
setup_docker_registry() {
    log_step "📦 Docker Registry 설정"
    
    # Registry 디렉토리 생성
    sudo mkdir -p /opt/docker-registry/{data,certs,auth}
    
    # 기본 레지스트리 설정
    cat << EOF | sudo tee /opt/docker-registry/config.yml
version: 0.1
log:
  fields:
    service: registry
storage:
  cache:
    blobdescriptor: inmemory
  filesystem:
    rootdirectory: /var/lib/registry
http:
  addr: :5000
  headers:
    X-Content-Type-Options: [nosniff]
health:
  storagedriver:
    enabled: true
    interval: 10s
    threshold: 3
EOF
    
    # Registry 컨테이너 실행
    docker run -d \
        --name docker-registry \
        --restart unless-stopped \
        -p 5000:5000 \
        -v /opt/docker-registry/data:/var/lib/registry \
        -v /opt/docker-registry/config.yml:/etc/docker/registry/config.yml \
        registry:2
    
    log_success "Docker Registry 설치 완료"
    log_info "Registry 주소: http://localhost:5000"
}

# Docker 네트워크 설정
setup_docker_networks() {
    log_step "🌐 Docker 네트워크 설정"
    
    # 사용자 정의 브리지 네트워크 생성
    docker network create \
        --driver bridge \
        --subnet=172.20.0.0/16 \
        --ip-range=172.20.240.0/20 \
        vllm-network 2>/dev/null || true
    
    log_success "vllm-network 네트워크 생성 완료"
    
    # 네트워크 목록 표시
    log_info "생성된 Docker 네트워크:"
    docker network ls
}

# Docker 보안 설정
configure_docker_security() {
    log_step "🔒 Docker 보안 설정"
    
    # Docker 소켓 권한 설정
    sudo chmod 660 /var/run/docker.sock
    
    # AppArmor 프로파일 설정 (Ubuntu/Debian)
    if command -v aa-status > /dev/null; then
        sudo systemctl enable apparmor
        sudo systemctl start apparmor
        log_info "AppArmor 보안 프로파일 활성화"
    fi
    
    # SELinux 설정 (CentOS/RHEL/Fedora)
    if command -v getenforce > /dev/null; then
        if [ "$(getenforce)" = "Enforcing" ]; then
            # Docker SELinux 모듈 설치
            case $PACKAGE_MANAGER in
                yum) sudo yum install -y container-selinux ;;
                dnf) sudo dnf install -y container-selinux ;;
            esac
            log_info "SELinux 보안 정책 설정"
        fi
    fi
    
    log_success "Docker 보안 설정 완료"
}

# Docker 성능 최적화
optimize_docker_performance() {
    log_step "⚡ Docker 성능 최적화"
    
    # 현재 데몬 설정 백업
    if [ -f /etc/docker/daemon.json ]; then
        sudo cp /etc/docker/daemon.json /etc/docker/daemon.json.backup
    fi
    
    # 최적화된 데몬 설정
    cat << EOF | sudo tee /etc/docker/daemon.json
{
  "log-driver": "json-file",
  "log-opts": {
    "max-size": "100m",
    "max-file": "3"
  },
  "storage-driver": "overlay2",
  "storage-opts": [
    "overlay2.override_kernel_check=true"
  ],
  "exec-opts": ["native.cgroupdriver=systemd"],
  "live-restore": true,
  "userland-proxy": false,
  "experimental": false,
  "metrics-addr": "127.0.0.1:9323",
  "default-runtime": "runc",
  "max-concurrent-downloads": 10,
  "max-concurrent-uploads": 10,
  "default-shm-size": "128M",
  "no-new-privileges": true
}
EOF
    
    # Docker 서비스 재시작
    sudo systemctl restart docker
    
    log_success "Docker 성능 최적화 완료"
}

# Docker 상태 확인
verify_docker_installation() {
    log_step "✅ Docker 설치 확인"
    
    # Docker 버전 확인
    log_info "Docker 버전:"
    docker --version
    
    # Docker Compose 버전 확인
    if command -v docker-compose > /dev/null; then
        log_info "Docker Compose 버전:"
        docker-compose --version
    fi
    
    # Docker 서비스 상태 확인
    if systemctl is-active --quiet docker; then
        log_success "Docker 서비스가 실행 중입니다."
    else
        log_error "Docker 서비스가 실행되지 않습니다."
        return 1
    fi
    
    # Hello World 테스트
    log_info "Docker Hello World 테스트..."
    if docker run --rm hello-world > /dev/null 2>&1; then
        log_success "Docker가 정상적으로 작동합니다."
    else
        log_error "Docker 테스트 실패"
        return 1
    fi
    
    # 사용자 권한 확인
    if groups $USER | grep -q docker; then
        log_success "사용자가 docker 그룹에 속해 있습니다."
    else
        log_warning "사용자가 docker 그룹에 속하지 않습니다. 로그아웃 후 다시 로그인하세요."
    fi
    
    # Docker 정보 출력
    log_info "Docker 시스템 정보:"
    docker system info | grep -E "(Server Version|Storage Driver|Cgroup Driver|Runtimes)"
}

# Docker 유용한 도구 설치
install_docker_tools() {
    log_step "🛠️ Docker 유용한 도구 설치"
    
    # ctop (컨테이너 모니터링)
    if ! command -v ctop > /dev/null; then
        log_info "ctop 설치 중..."
        sudo curl -L https://github.com/bcicen/ctop/releases/latest/download/ctop-0.7.7-linux-amd64 -o /usr/local/bin/ctop
        sudo chmod +x /usr/local/bin/ctop
        log_success "ctop 설치 완료"
    fi
    
    # dive (이미지 분석)
    if ! command -v dive > /dev/null; then
        log_info "dive 설치 중..."
        DIVE_VERSION=$(curl -s https://api.github.com/repos/wagoodman/dive/releases/latest | grep tag_name | cut -d '"' -f 4)
        curl -L "https://github.com/wagoodman/dive/releases/download/${DIVE_VERSION}/dive_${DIVE_VERSION#v}_linux_amd64.tar.gz" | sudo tar -xz -C /usr/local/bin dive
        sudo chmod +x /usr/local/bin/dive
        log_success "dive 설치 완료"
    fi
    
    # lazydocker (Docker TUI)
    if ! command -v lazydocker > /dev/null; then
        log_info "lazydocker 설치 중..."
        curl https://raw.githubusercontent.com/jesseduffield/lazydocker/master/scripts/install_update_linux.sh | bash
        log_success "lazydocker 설치 완료"
    fi
    
    log_success "Docker 도구 설치 완료"
}

# Dockerfile 및 docker-compose 템플릿 생성
create_docker_templates() {
    log_step "📄 Docker 템플릿 생성"
    
    # 템플릿 디렉토리 생성
    mkdir -p ~/docker-templates
    
    # vLLM API Dockerfile 템플릿
    cat << 'EOF' > ~/docker-templates/Dockerfile.vllm
# vLLM API Server Dockerfile
FROM nvidia/cuda:12.1-devel-ubuntu22.04

# 환경 변수 설정
ENV PYTHONUNBUFFERED=1
ENV DEBIAN_FRONTEND=noninteractive

# 시스템 패키지 설치
RUN apt-get update && apt-get install -y \
    python3 \
    python3-pip \
    python3-venv \
    git \
    wget \
    curl \
    && rm -rf /var/lib/apt/lists/*

# 작업 디렉토리 설정
WORKDIR /app

# Python 의존성 설치
COPY requirements.txt .
RUN pip3 install --no-cache-dir -r requirements.txt

# 애플리케이션 코드 복사
COPY . .

# 포트 노출
EXPOSE 8000

# 헬스체크
HEALTHCHECK --interval=30s --timeout=30s --start-period=60s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# 엔트리포인트
CMD ["python3", "scripts/start_server.py", "--mode", "prod"]
EOF
    
    # docker-compose.yml 템플릿
    cat << 'EOF' > ~/docker-templates/docker-compose.vllm.yml
version: '3.8'

services:
  vllm-api:
    build: .
    container_name: vllm-api-server
    restart: unless-stopped
    ports:
      - "8000:8000"
    volumes:
      - ./models:/app/models
      - ./logs:/app/logs
      - ./config:/app/config
    environment:
      - CUDA_VISIBLE_DEVICES=0
      - MODEL_NAME=microsoft/DialoGPT-medium
      - MAX_TOKENS=512
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              count: 1
              capabilities: [gpu]
    networks:
      - vllm-network
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 60s

  nginx:
    image: nginx:alpine
    container_name: vllm-nginx
    restart: unless-stopped
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./nginx.conf:/etc/nginx/nginx.conf:ro
      - ./ssl:/etc/nginx/ssl:ro
    depends_on:
      - vllm-api
    networks:
      - vllm-network

  redis:
    image: redis:7-alpine
    container_name: vllm-redis
    restart: unless-stopped
    ports:
      - "6379:6379"
    volumes:
      - redis_data:/data
    networks:
      - vllm-network

volumes:
  redis_data:

networks:
  vllm-network:
    external: true
EOF
    
    # nginx.conf 템플릿
    cat << 'EOF' > ~/docker-templates/nginx.conf
events {
    worker_connections 1024;
}

http {
    upstream vllm_backend {
        server vllm-api:8000;
    }

    server {
        listen 80;
        server_name localhost;

        location / {
            proxy_pass http://vllm_backend;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto $scheme;
            
            # WebSocket 지원
            proxy_http_version 1.1;
            proxy_set_header Upgrade $http_upgrade;
            proxy_set_header Connection "upgrade";
            
            # 타임아웃 설정
            proxy_connect_timeout 300s;
            proxy_send_timeout 300s;
            proxy_read_timeout 300s;
        }
    }
}
EOF
    
    log_success "Docker 템플릿 생성 완료: ~/docker-templates/"
}

# 시스템 정보 출력
show_docker_info() {
    log_step "📋 Docker 설정 정보"
    
    echo ""
    echo "==================== Docker 정보 ===================="
    echo "Docker 버전: $(docker --version 2>/dev/null || echo '설치되지 않음')"
    echo "Docker Compose: $(docker compose version 2>/dev/null || docker-compose --version 2>/dev/null || echo '설치되지 않음')"
    echo "Docker 상태: $(systemctl is-active docker 2>/dev/null || echo '알 수 없음')"
    echo "Docker 네트워크: $(docker network ls --format 'table {{.Name}}\t{{.Driver}}' 2>/dev/null || echo '확인 불가')"
    echo ""
    
    if [ "$INSTALL_PORTAINER" = true ]; then
        echo "Portainer: https://localhost:9443"
    fi
    
    if [ "$SETUP_REGISTRY" = true ]; then
        echo "Docker Registry: http://localhost:5000"
    fi
    
    echo "유용한 명령어:"
    echo "  - 컨테이너 모니터링: ctop"
    echo "  - 이미지 분석: dive <image>"
    echo "  - Docker TUI: lazydocker"
    echo "  - 시스템 정리: docker-cleanup"
    echo "=================================================="
    echo ""
}

# 메인 함수
main() {
    log_info "🚀 Docker 설치 시작"
    
    # 시스템 정보 확인
    detect_system
    
    # 제거 모드
    if [ "$UNINSTALL" = true ]; then
        uninstall_docker
        log_success "Docker 제거 완료"
        exit 0
    fi
    
    # 기존 설치 확인
    if command -v docker > /dev/null; then
        log_warning "Docker가 이미 설치되어 있습니다."
        docker --version
        read -p "기존 설치를 제거하고 재설치하시겠습니까? (y/N): " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            uninstall_docker
        else
            log_info "기존 설치를 유지합니다."
            verify_docker_installation
            exit 0
        fi
    fi
    
    # 설치 과정
    install_prerequisites
    add_docker_repo
    install_docker_engine
    setup_docker_group
    install_docker_compose
    
    # 선택적 설정
    if [ "$CONFIGURE_LOGGING" = true ]; then
        configure_docker_logging
    fi
    
    setup_docker_networks
    configure_docker_security
    optimize_docker_performance
    setup_docker_cleanup
    
    # 선택적 도구 설치
    if [ "$INSTALL_PORTAINER" = true ]; then
        install_portainer
    fi
    
    if [ "$SETUP_REGISTRY" = true ]; then
        setup_docker_registry
    fi
    
    install_docker_tools
    create_docker_templates
    
    # 설치 확인
    verify_docker_installation
    
    # 정보 출력
    show_docker_info
    
    log_success "🎉 Docker 설치 완료!"
    echo ""
    echo "다음 명령어로 Docker를 사용할 수 있습니다:"
    echo "  docker run hello-world"
    echo "  docker compose up -d"
    echo ""
    
    if ! groups $USER | grep -q docker; then
        log_warning "⚠️  변경사항을 적용하려면 로그아웃 후 다시 로그인하세요."
    fi
}

# 스크립트 실행
main "$@"