#!/bin/bash
# scripts/deploy.sh
# vLLM API 서버 배포 스크립트

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
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DEPLOY_ENV=${1:-production}
SERVICE_NAME="vllm-api"
DEPLOY_USER=${DEPLOY_USER:-$(whoami)}
DEPLOY_HOST=${DEPLOY_HOST:-localhost}
DEPLOY_PORT=${DEPLOY_PORT:-8000}
BACKUP_DIR="$PROJECT_ROOT/backups"

# 도움말 함수
show_help() {
    cat << EOF
사용법: $0 [환경] [옵션]

환경:
  production    프로덕션 환경 배포 (기본값)
  staging       스테이징 환경 배포
  development   개발 환경 배포

옵션:
  --host HOST          배포 호스트 (기본값: localhost)
  --port PORT          서비스 포트 (기본값: 8000)
  --user USER          배포 사용자 (기본값: 현재 사용자)
  --backup            배포 전 백업 생성
  --no-test           테스트 건너뛰기
  --rollback          이전 버전으로 롤백
  --docker            Docker 컨테이너로 배포
  --k8s               Kubernetes로 배포
  --help              이 도움말 표시

예시:
  $0 production --host 192.168.1.100 --backup
  $0 staging --docker
  $0 --rollback
EOF
}

# 명령행 인수 파싱
BACKUP=false
NO_TEST=false
ROLLBACK=false
DOCKER_DEPLOY=false
K8S_DEPLOY=false

while [[ $# -gt 0 ]]; do
    case $1 in
        --host)
            DEPLOY_HOST="$2"
            shift 2
            ;;
        --port)
            DEPLOY_PORT="$2"
            shift 2
            ;;
        --user)
            DEPLOY_USER="$2"
            shift 2
            ;;
        --backup)
            BACKUP=true
            shift
            ;;
        --no-test)
            NO_TEST=true
            shift
            ;;
        --rollback)
            ROLLBACK=true
            shift
            ;;
        --docker)
            DOCKER_DEPLOY=true
            shift
            ;;
        --k8s)
            K8S_DEPLOY=true
            shift
            ;;
        --help)
            show_help
            exit 0
            ;;
        *)
            if [[ "$1" =~ ^(production|staging|development)$ ]]; then
                DEPLOY_ENV="$1"
            else
                log_error "알 수 없는 옵션: $1"
                show_help
                exit 1
            fi
            shift
            ;;
    esac
done

log_info "🚀 vLLM API 서버 배포 시작"
log_info "배포 환경: $DEPLOY_ENV"
log_info "배포 호스트: $DEPLOY_HOST:$DEPLOY_PORT"
log_info "배포 사용자: $DEPLOY_USER"

cd "$PROJECT_ROOT"

# 롤백 처리
if [ "$ROLLBACK" = true ]; then
    log_step "🔄 이전 버전으로 롤백"
    
    if [ ! -d "$BACKUP_DIR" ]; then
        log_error "백업 디렉토리가 존재하지 않습니다: $BACKUP_DIR"
        exit 1
    fi
    
    # 최신 백업 찾기
    LATEST_BACKUP=$(ls -t "$BACKUP_DIR" | head -n 1)
    if [ -z "$LATEST_BACKUP" ]; then
        log_error "백업 파일을 찾을 수 없습니다."
        exit 1
    fi
    
    log_info "롤백할 백업: $LATEST_BACKUP"
    
    # 서비스 중지
    sudo systemctl stop "$SERVICE_NAME" || log_warning "서비스 중지 실패"
    
    # 백업 복원
    tar -xzf "$BACKUP_DIR/$LATEST_BACKUP" -C "$(dirname "$PROJECT_ROOT")"
    
    # 서비스 시작
    sudo systemctl start "$SERVICE_NAME"
    
    log_success "롤백 완료"
    exit 0
fi

# 배포 전 검증
log_step "🔍 배포 전 검증"

# Git 저장소 확인
if [ ! -d ".git" ]; then
    log_warning "Git 저장소가 아닙니다."
else
    # 변경사항 확인
    if [ -n "$(git status --porcelain)" ]; then
        log_warning "커밋되지 않은 변경사항이 있습니다."
        git status --short
        read -p "계속 진행하시겠습니까? (y/N): " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            log_info "배포를 취소합니다."
            exit 0
        fi
    fi
    
    # 현재 브랜치 확인
    CURRENT_BRANCH=$(git rev-parse --abbrev-ref HEAD)
    log_info "현재 브랜치: $CURRENT_BRANCH"
    
    if [ "$DEPLOY_ENV" = "production" ] && [ "$CURRENT_BRANCH" != "main" ] && [ "$CURRENT_BRANCH" != "master" ]; then
        log_warning "프로덕션 배포는 main/master 브랜치에서만 권장됩니다."
        read -p "계속 진행하시겠습니까? (y/N): " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            log_info "배포를 취소합니다."
            exit 0
        fi
    fi
fi

# 환경 설정 파일 확인
CONFIG_FILE="config/${DEPLOY_ENV}_config.yaml"
if [ ! -f "$CONFIG_FILE" ]; then
    log_warning "환경 설정 파일이 없습니다: $CONFIG_FILE"
    log_info "기본 설정 파일을 사용합니다: config/server_config.yaml"
    CONFIG_FILE="config/server_config.yaml"
fi

# 테스트 실행
if [ "$NO_TEST" = false ]; then
    log_step "🧪 테스트 실행"
    
    # 가상환경 활성화
    if [ -f "venv/bin/activate" ]; then
        source venv/bin/activate
    fi
    
    # 단위 테스트 실행
    if ! python tests/run_tests.py --type unit; then
        log_error "단위 테스트 실패"
        exit 1
    fi
    
    # 통합 테스트 실행
    if ! python tests/run_tests.py --type integration; then
        log_error "통합 테스트 실패"
        exit 1
    fi
    
    log_success "모든 테스트 통과"
fi

# 백업 생성
if [ "$BACKUP" = true ]; then
    log_step "💾 배포 전 백업 생성"
    
    mkdir -p "$BACKUP_DIR"
    
    BACKUP_NAME="vllm-api-backup-$(date +%Y%m%d-%H%M%S).tar.gz"
    BACKUP_PATH="$BACKUP_DIR/$BACKUP_NAME"
    
    tar -czf "$BACKUP_PATH" \
        --exclude=venv \
        --exclude=__pycache__ \
        --exclude=.git \
        --exclude=htmlcov \
        --exclude=.pytest_cache \
        --exclude=logs \
        --exclude=models \
        -C "$(dirname "$PROJECT_ROOT")" \
        "$(basename "$PROJECT_ROOT")"
    
    log_success "백업 생성 완료: $BACKUP_PATH"
    
    # 오래된 백업 정리 (최근 5개만 유지)
    ls -t "$BACKUP_DIR"/*.tar.gz | tail -n +6 | xargs -r rm
    log_info "오래된 백업 정리 완료"
fi

# Docker 배포
if [ "$DOCKER_DEPLOY" = true ]; then
    log_step "🐳 Docker 컨테이너 배포"
    
    # Dockerfile 확인
    if [ ! -f "Dockerfile" ]; then
        log_error "Dockerfile이 존재하지 않습니다."
        exit 1
    fi
    
    # 이미지 빌드
    IMAGE_NAME="vllm-api:${DEPLOY_ENV}"
    log_info "Docker 이미지 빌드: $IMAGE_NAME"
    
    docker build -t "$IMAGE_NAME" .
    
    # 기존 컨테이너 중지 및 제거
    if docker ps -q --filter "name=$SERVICE_NAME" | grep -q .; then
        log_info "기존 컨테이너 중지 중..."
        docker stop "$SERVICE_NAME"
        docker rm "$SERVICE_NAME"
    fi
    
    # 새 컨테이너 실행
    log_info "새 컨테이너 시작..."
    docker run -d \
        --name "$SERVICE_NAME" \
        --restart unless-stopped \
        -p "$DEPLOY_PORT:8000" \
        -v "$PROJECT_ROOT/models:/app/models" \
        -v "$PROJECT_ROOT/logs:/app/logs" \
        -v "$PROJECT_ROOT/config:/app/config" \
        --gpus all \
        "$IMAGE_NAME"
    
    log_success "Docker 배포 완료"
    
# Kubernetes 배포
elif [ "$K8S_DEPLOY" = true ]; then
    log_step "☸️ Kubernetes 배포"
    
    # Kubernetes 매니페스트 확인
    if [ ! -d "k8s" ]; then
        log_error "Kubernetes 매니페스트 디렉토리가 존재하지 않습니다: k8s/"
        exit 1
    fi
    
    # 네임스페이스 생성
    kubectl create namespace vllm-api --dry-run=client -o yaml | kubectl apply -f -
    
    # 설정 맵 업데이트
    if [ -f "$CONFIG_FILE" ]; then
        kubectl create configmap vllm-config \
            --from-file="$CONFIG_FILE" \
            --namespace=vllm-api \
            --dry-run=client -o yaml | kubectl apply -f -
    fi
    
    # 배포 적용
    kubectl apply -f k8s/ --namespace=vllm-api
    
    # 배포 상태 확인
    kubectl rollout status deployment/vllm-api --namespace=vllm-api
    
    log_success "Kubernetes 배포 완료"
    
# 일반 서버 배포
else
    log_step "🖥️ 서버 배포"
    
    # 가상환경 활성화
    if [ -f "venv/bin/activate" ]; then
        source venv/bin/activate
    fi
    
    # 의존성 업데이트
    log_info "의존성 업데이트 중..."
    pip install -r requirements.txt --upgrade
    
    # 데이터베이스 마이그레이션 (필요한 경우)
    # python manage.py migrate
    
    # 정적 파일 수집 (필요한 경우)
    # python manage.py collectstatic --noinput
    
    # systemd 서비스 파일 생성/업데이트
    SERVICE_FILE="/etc/systemd/system/${SERVICE_NAME}.service"
    
    if [ ! -f "$SERVICE_FILE" ]; then
        log_info "systemd 서비스 파일 생성..."
        
        sudo tee "$SERVICE_FILE" > /dev/null << EOF
[Unit]
Description=vLLM API Server
After=network.target

[Service]
Type=exec
User=$DEPLOY_USER
Group=$DEPLOY_USER
WorkingDirectory=$PROJECT_ROOT
Environment=PATH=$PROJECT_ROOT/venv/bin
ExecStart=$PROJECT_ROOT/venv/bin/python scripts/start_server.py --mode prod
ExecReload=/bin/kill -HUP \$MAINPID
Restart=always
RestartSec=5
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF
        
        sudo systemctl daemon-reload
        sudo systemctl enable "$SERVICE_NAME"
        log_success "systemd 서비스 파일 생성 완료"
    fi
    
    # 서비스 재시작
    log_info "서비스 재시작 중..."
    sudo systemctl restart "$SERVICE_NAME"
    
    # 서비스 상태 확인
    sleep 3
    if sudo systemctl is-active --quiet "$SERVICE_NAME"; then
        log_success "서비스가 성공적으로 시작되었습니다."
    else
        log_error "서비스 시작 실패"
        sudo systemctl status "$SERVICE_NAME"
        exit 1
    fi
fi

# 배포 후 검증
log_step "✅ 배포 후 검증"

# 헬스 체크
log_info "헬스 체크 수행 중..."
for i in {1..30}; do
    if curl -f -s "http://$DEPLOY_HOST:$DEPLOY_PORT/health" > /dev/null; then
        log_success "헬스 체크 성공"
        break
    fi
    
    if [ $i -eq 30 ]; then
        log_error "헬스 체크 실패 - 서비스가 응답하지 않습니다."
        exit 1
    fi
    
    log_info "헬스 체크 재시도 ($i/30)..."
    sleep 2
done

# API 기본 테스트
log_info "API 기본 테스트..."
API_RESPONSE=$(curl -s "http://$DEPLOY_HOST:$DEPLOY_PORT/")
if echo "$API_RESPONSE" | grep -q "vLLM API"; then
    log_success "API 응답 확인"
else
    log_warning "API 응답이 예상과 다릅니다."
fi

# 배포 정보 기록
DEPLOY_LOG="$PROJECT_ROOT/logs/deploy.log"
mkdir -p "$(dirname "$DEPLOY_LOG")"

cat >> "$DEPLOY_LOG" << EOF
=== 배포 로그 ===
날짜: $(date)
환경: $DEPLOY_ENV
호스트: $DEPLOY_HOST:$DEPLOY_PORT
사용자: $DEPLOY_USER
Git 커밋: $(git rev-parse HEAD 2>/dev/null || echo "N/A")
브랜치: $(git rev-parse --abbrev-ref HEAD 2>/dev/null || echo "N/A")
배포 방식: $([ "$DOCKER_DEPLOY" = true ] && echo "Docker" || [ "$K8S_DEPLOY" = true ] && echo "Kubernetes" || echo "서버")
상태: 성공
================

EOF

# 완료 메시지
echo ""
log_success "🎉 배포 완료!"
echo ""
echo "서비스 정보:"
echo "  - 환경: $DEPLOY_ENV"
echo "  - 주소: http://$DEPLOY_HOST:$DEPLOY_PORT"
echo "  - API 문서: http://$DEPLOY_HOST:$DEPLOY_PORT/docs"
echo ""

if [ "$DOCKER_DEPLOY" = true ]; then
    echo "Docker 명령어:"
    echo "  - 로그 확인: docker logs $SERVICE_NAME"
    echo "  - 컨테이너 중지: docker stop $SERVICE_NAME"
    echo "  - 컨테이너 재시작: docker restart $SERVICE_NAME"
elif [ "$K8S_DEPLOY" = true ]; then
    echo "Kubernetes 명령어:"
    echo "  - 파드 상태: kubectl get pods -n vllm-api"
    echo "  - 로그 확인: kubectl logs -f deployment/vllm-api -n vllm-api"
    echo "  - 서비스 확인: kubectl get svc -n vllm-api"
else
    echo "시스템 명령어:"
    echo "  - 서비스 상태: sudo systemctl status $SERVICE_NAME"
    echo "  - 로그 확인: sudo journalctl -u $SERVICE_NAME -f"
    echo "  - 서비스 재시작: sudo systemctl restart $SERVICE_NAME"
fi

echo ""
log_info "배포가 성공적으로 완료되었습니다! 🚀"