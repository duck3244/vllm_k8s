#!/bin/bash
# scripts/kubernetes_setup.sh
# Kubernetes 설치 스크립트

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
K8S_VERSION=${K8S_VERSION:-"1.29"}
CONTAINERD_VERSION=${CONTAINERD_VERSION:-"1.7.13"}
CNI_PLUGIN=${CNI_PLUGIN:-"calico"}
INSTALL_HELM=${INSTALL_HELM:-true}
INSTALL_KUBECTL=${INSTALL_KUBECTL:-true}

# 도움말 함수
show_help() {
    cat << EOF
사용법: $0 [옵션]

옵션:
  --k8s-version VERSION     Kubernetes 버전 (기본값: 1.29)
  --containerd-version VER  containerd 버전 (기본값: 1.7.13)
  --cni PLUGIN             CNI 플러그인 (calico|flannel|weave) (기본값: calico)
  --no-helm                Helm 설치 안 함
  --no-kubectl             kubectl 설치 안 함
  --worker-only            워커 노드만 설정
  --uninstall              Kubernetes 제거
  --help                   이 도움말 표시

예시:
  $0                              # 기본 설치 (마스터 노드)
  $0 --worker-only               # 워커 노드만 설정
  $0 --cni flannel              # Flannel CNI 사용
  $0 --k8s-version 1.28         # 특정 버전 설치
EOF
}

# 명령행 인수 파싱
WORKER_ONLY=false
UNINSTALL=false

while [[ $# -gt 0 ]]; do
    case $1 in
        --k8s-version)
            K8S_VERSION="$2"
            shift 2
            ;;
        --containerd-version)
            CONTAINERD_VERSION="$2"
            shift 2
            ;;
        --cni)
            CNI_PLUGIN="$2"
            shift 2
            ;;
        --no-helm)
            INSTALL_HELM=false
            shift
            ;;
        --no-kubectl)
            INSTALL_KUBECTL=false
            shift
            ;;
        --worker-only)
            WORKER_ONLY=true
            shift
            ;;
        --uninstall)
            UNINSTALL=true
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
    
    # 최소 요구사항 확인
    MEMORY_GB=$(free -g | awk 'NR==2{print $2}')
    CPU_CORES=$(nproc)
    
    log_info "메모리: ${MEMORY_GB}GB"
    log_info "CPU 코어: ${CPU_CORES}개"
    
    if [ $MEMORY_GB -lt 2 ]; then
        log_error "Kubernetes는 최소 2GB 메모리가 필요합니다."
        exit 1
    fi
    
    if [ $CPU_CORES -lt 2 ]; then
        log_error "Kubernetes는 최소 2개 CPU 코어가 필요합니다."
        exit 1
    fi
    
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

# Kubernetes 제거
uninstall_kubernetes() {
    log_step "🗑️ Kubernetes 제거"
    
    # kubeadm reset
    if command -v kubeadm > /dev/null; then
        sudo kubeadm reset -f
    fi
    
    # 서비스 중지
    sudo systemctl stop kubelet
    sudo systemctl stop containerd
    
    # 패키지 제거
    case $PACKAGE_MANAGER in
        apt)
            sudo apt-get remove -y kubeadm kubectl kubelet kubernetes-cni kube*
            sudo apt-get purge -y kubeadm kubectl kubelet kubernetes-cni kube*
            sudo apt-get autoremove -y
            ;;
        yum)
            sudo yum remove -y kubeadm kubectl kubelet kubernetes-cni
            ;;
        dnf)
            sudo dnf remove -y kubeadm kubectl kubelet kubernetes-cni
            ;;
    esac
    
    # 디렉토리 제거
    sudo rm -rf ~/.kube
    sudo rm -rf /etc/kubernetes
    sudo rm -rf /var/lib/kubelet
    sudo rm -rf /var/lib/etcd
    sudo rm -rf /etc/cni
    sudo rm -rf /opt/cni
    sudo rm -rf /var/lib/containerd
    
    # iptables 규칙 정리
    sudo iptables -F && sudo iptables -t nat -F && sudo iptables -t mangle -F && sudo iptables -X
    
    log_success "Kubernetes 제거 완료"
}

# 시스템 준비
prepare_system() {
    log_step "🔧 시스템 준비"
    
    # 스왑 비활성화
    sudo swapoff -a
    sudo sed -i '/ swap / s/^\(.*\)$/#\1/g' /etc/fstab
    
    # 필수 모듈 로드
    cat << EOF | sudo tee /etc/modules-load.d/k8s.conf
overlay
br_netfilter
EOF
    
    sudo modprobe overlay
    sudo modprobe br_netfilter
    
    # 커널 파라미터 설정
    cat << EOF | sudo tee /etc/sysctl.d/k8s.conf
net.bridge.bridge-nf-call-iptables = 1
net.bridge.bridge-nf-call-ip6tables = 1
net.ipv4.ip_forward = 1
EOF
    
    sudo sysctl --system
    
    # SELinux 비활성화 (CentOS/RHEL)
    if [ -f /etc/selinux/config ]; then
        sudo setenforce 0
        sudo sed -i 's/^SELINUX=enforcing$/SELINUX=permissive/' /etc/selinux/config
    fi
    
    log_success "시스템 준비 완료"
}

# containerd 설치
install_containerd() {
    log_step "📦 containerd 설치"
    
    case $PACKAGE_MANAGER in
        apt)
            # Docker 저장소 추가
            curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /usr/share/keyrings/docker-archive-keyring.gpg
            echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/docker-archive-keyring.gpg] https://download.docker.com/linux/ubuntu $(lsb_release -cs) stable" | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null
            
            sudo apt-get update
            sudo apt-get install -y containerd.io
            ;;
        yum)
            sudo yum-config-manager --add-repo https://download.docker.com/linux/centos/docker-ce.repo
            sudo yum install -y containerd.io
            ;;
        dnf)
            sudo dnf config-manager --add-repo https://download.docker.com/linux/fedora/docker-ce.repo
            sudo dnf install -y containerd.io
            ;;
    esac
    
    # containerd 설정
    sudo mkdir -p /etc/containerd
    containerd config default | sudo tee /etc/containerd/config.toml
    
    # systemd cgroup 드라이버 설정
    sudo sed -i 's/SystemdCgroup \= false/SystemdCgroup \= true/g' /etc/containerd/config.toml
    
    # containerd 시작
    sudo systemctl restart containerd
    sudo systemctl enable containerd
    
    log_success "containerd 설치 완료"
}

# Kubernetes 저장소 추가
add_kubernetes_repo() {
    log_step "📋 Kubernetes 저장소 추가"
    
    case $PACKAGE_MANAGER in
        apt)
            curl -fsSL https://pkgs.k8s.io/core:/stable:/v${K8S_VERSION}/deb/Release.key | sudo gpg --dearmor -o /etc/apt/keyrings/kubernetes-apt-keyring.gpg
            echo "deb [signed-by=/etc/apt/keyrings/kubernetes-apt-keyring.gpg] https://pkgs.k8s.io/core:/stable:/v${K8S_VERSION}/deb/ /" | sudo tee /etc/apt/sources.list.d/kubernetes.list
            sudo apt-get update
            ;;
        yum)
            cat << EOF | sudo tee /etc/yum.repos.d/kubernetes.repo
[kubernetes]
name=Kubernetes
baseurl=https://pkgs.k8s.io/core:/stable:/v${K8S_VERSION}/rpm/
enabled=1
gpgcheck=1
gpgkey=https://pkgs.k8s.io/core:/stable:/v${K8S_VERSION}/rpm/repodata/repomd.xml.key
EOF
            ;;
        dnf)
            cat << EOF | sudo tee /etc/yum.repos.d/kubernetes.repo
[kubernetes]
name=Kubernetes
baseurl=https://pkgs.k8s.io/core:/stable:/v${K8S_VERSION}/rpm/
enabled=1
gpgcheck=1
gpgkey=https://pkgs.k8s.io/core:/stable:/v${K8S_VERSION}/rpm/repodata/repomd.xml.key
EOF
            ;;
    esac
    
    log_success "Kubernetes 저장소 추가 완료"
}

# Kubernetes 컴포넌트 설치
install_kubernetes_components() {
    log_step "⚙️ Kubernetes 컴포넌트 설치"
    
    case $PACKAGE_MANAGER in
        apt)
            sudo apt-get install -y kubelet kubeadm kubectl
            sudo apt-mark hold kubelet kubeadm kubectl
            ;;
        yum)
            sudo yum install -y kubelet kubeadm kubectl --disableexcludes=kubernetes
            ;;
        dnf)
            sudo dnf install -y kubelet kubeadm kubectl --disableexcludes=kubernetes
            ;;
    esac
    
    # kubelet 시작
    sudo systemctl enable --now kubelet
    
    log_success "Kubernetes 컴포넌트 설치 완료"
    log_info "kubeadm 버전: $(kubeadm version -o short)"
    log_info "kubectl 버전: $(kubectl version --client -o yaml | grep gitVersion | awk '{print $2}')"
}

# 클러스터 초기화 (마스터 노드)
initialize_cluster() {
    if [ "$WORKER_ONLY" = true ]; then
        log_info "워커 노드 모드: 클러스터 초기화를 건너뜁니다."
        return
    fi
    
    log_step "🎯 Kubernetes 클러스터 초기화"
    
    # 클러스터 초기화
    sudo kubeadm init \
        --pod-network-cidr=192.168.0.0/16 \
        --apiserver-advertise-address=$(hostname -I | awk '{print $1}') \
        --kubernetes-version=v${K8S_VERSION}.0
    
    # kubectl 설정
    mkdir -p $HOME/.kube
    sudo cp -i /etc/kubernetes/admin.conf $HOME/.kube/config
    sudo chown $(id -u):$(id -g) $HOME/.kube/config
    
    # 마스터 노드에서 파드 실행 허용 (단일 노드 클러스터인 경우)
    kubectl taint nodes --all node-role.kubernetes.io/control-plane- || true
    
    log_success "클러스터 초기화 완료"
    
    # 조인 명령어 저장
    kubeadm token create --print-join-command > ~/k8s-join-command.sh
    chmod +x ~/k8s-join-command.sh
    log_info "워커 노드 조인 명령어: ~/k8s-join-command.sh"
}

# CNI 플러그인 설치
install_cni_plugin() {
    if [ "$WORKER_ONLY" = true ]; then
        log_info "워커 노드 모드: CNI 설치를 건너뜁니다."
        return
    fi
    
    log_step "🌐 CNI 플러그인 설치: $CNI_PLUGIN"
    
    case $CNI_PLUGIN in
        calico)
            # Calico 설치
            kubectl create -f https://raw.githubusercontent.com/projectcalico/calico/v3.27.0/manifests/tigera-operator.yaml
            
            # Calico 설정
            cat << EOF | kubectl apply -f -
apiVersion: operator.tigera.io/v1
kind: Installation
metadata:
  name: default
spec:
  calicoNetwork:
    ipPools:
    - blockSize: 26
      cidr: 192.168.0.0/16
      encapsulation: VXLANCrossSubnet
      natOutgoing: Enabled
      nodeSelector: all()
---
apiVersion: operator.tigera.io/v1
kind: APIServer
metadata:
  name: default
spec: {}
EOF
            ;;
        flannel)
            # Flannel 설치
            kubectl apply -f https://github.com/flannel-io/flannel/releases/latest/download/kube-flannel.yml
            ;;
        weave)
            # Weave Net 설치
            kubectl apply -f https://github.com/weaveworks/weave/releases/download/v2.8.1/weave-daemonset-k8s.yaml
            ;;
        *)
            log_error "지원하지 않는 CNI 플러그인: $CNI_PLUGIN"
            exit 1
            ;;
    esac
    
    log_success "$CNI_PLUGIN CNI 플러그인 설치 완료"
}

# Helm 설치
install_helm() {
    if [ "$INSTALL_HELM" = false ]; then
        return
    fi
    
    log_step "📦 Helm 설치"
    
    # Helm 설치 스크립트 다운로드 및 실행
    curl -fsSL -o get_helm.sh https://raw.githubusercontent.com/helm/helm/main/scripts/get-helm-3
    chmod 700 get_helm.sh
    ./get_helm.sh
    rm get_helm.sh
    
    # Helm 저장소 추가
    helm repo add stable https://charts.helm.sh/stable
    helm repo add bitnami https://charts.bitnami.com/bitnami
    helm repo update
    
    log_success "Helm 설치 완료"
    log_info "Helm 버전: $(helm version --short)"
}

# kubectl 자동완성 설정
setup_kubectl_completion() {
    log_step "⌨️ kubectl 자동완성 설정"
    
    # bash 자동완성
    kubectl completion bash | sudo tee /etc/bash_completion.d/kubectl > /dev/null
    
    # 현재 사용자의 bashrc에 추가
    if ! grep -q "kubectl completion bash" ~/.bashrc; then
        echo 'source <(kubectl completion bash)' >>~/.bashrc
        echo 'alias k=kubectl' >>~/.bashrc
        echo 'complete -o default -F __start_kubectl k' >>~/.bashrc
    fi
    
    log_success "kubectl 자동완성 설정 완료"
}

# Kubernetes 대시보드 설치
install_kubernetes_dashboard() {
    if [ "$WORKER_ONLY" = true ]; then
        return
    fi
    
    log_step "📊 Kubernetes 대시보드 설치"
    
    # 대시보드 설치
    kubectl apply -f https://raw.githubusercontent.com/kubernetes/dashboard/v2.7.0/aio/deploy/recommended.yaml
    
    # 관리자 서비스 계정 생성
    cat << EOF | kubectl apply -f -
apiVersion: v1
kind: ServiceAccount
metadata:
  name: admin-user
  namespace: kubernetes-dashboard
---
apiVersion: rbac.authorization.k8s.io/v1
kind: ClusterRoleBinding
metadata:
  name: admin-user
roleRef:
  apiGroup: rbac.authorization.k8s.io
  kind: ClusterRole
  name: cluster-admin
subjects:
- kind: ServiceAccount
  name: admin-user
  namespace: kubernetes-dashboard
EOF
    
    # 토큰 생성 스크립트 생성
    cat << 'EOF' > ~/get-dashboard-token.sh
#!/bin/bash
kubectl -n kubernetes-dashboard create token admin-user
EOF
    chmod +x ~/get-dashboard-token.sh
    
    log_success "Kubernetes 대시보드 설치 완료"
    log_info "대시보드 접속: kubectl proxy 실행 후 http://localhost:8001/api/v1/namespaces/kubernetes-dashboard/services/https:kubernetes-dashboard:/proxy/"
    log_info "토큰 확인: ~/get-dashboard-token.sh"
}

# 메트릭 서버 설치
install_metrics_server() {
    if [ "$WORKER_ONLY" = true ]; then
        return
    fi
    
    log_step "📈 Metrics Server 설치"
    
    # Metrics Server 설치
    kubectl apply -f https://github.com/kubernetes-sigs/metrics-server/releases/latest/download/components.yaml
    
    # Metrics Server 설정 수정 (개발환경용)
    kubectl patch deployment metrics-server -n kube-system --type='json' -p='[{"op": "add", "path": "/spec/template/spec/containers/0/args/-", "value": "--kubelet-insecure-tls"}]'
    
    log_success "Metrics Server 설치 완료"
}

# Ingress 컨트롤러 설치
install_ingress_controller() {
    if [ "$WORKER_ONLY" = true ]; then
        return
    fi
    
    log_step "🌐 NGINX Ingress 컨트롤러 설치"
    
    # NGINX Ingress 컨트롤러 설치
    kubectl apply -f https://raw.githubusercontent.com/kubernetes/ingress-nginx/controller-v1.8.2/deploy/static/provider/baremetal/deploy.yaml
    
    log_success "NGINX Ingress 컨트롤러 설치 완료"
}

# 스토리지 클래스 설정
setup_storage_class() {
    if [ "$WORKER_ONLY" = true ]; then
        return
    fi
    
    log_step "💾 스토리지 클래스 설정"
    
    # Local Path Provisioner 설치
    kubectl apply -f https://raw.githubusercontent.com/rancher/local-path-provisioner/v0.0.24/deploy/local-path-storage.yaml
    
    # 기본 스토리지 클래스로 설정
    kubectl patch storageclass local-path -p '{"metadata": {"annotations":{"storageclass.kubernetes.io/is-default-class":"true"}}}'
    
    log_success "Local Path 스토리지 클래스 설정 완료"
}

# Kubernetes 도구 설치
install_k8s_tools() {
    log_step "🛠️ Kubernetes 도구 설치"
    
    # k9s 설치
    if ! command -v k9s > /dev/null; then
        log_info "k9s 설치 중..."
        K9S_VERSION=$(curl -s https://api.github.com/repos/derailed/k9s/releases/latest | grep tag_name | cut -d '"' -f 4)
        curl -L "https://github.com/derailed/k9s/releases/download/${K9S_VERSION}/k9s_Linux_amd64.tar.gz" | sudo tar -xz -C /usr/local/bin k9s
        sudo chmod +x /usr/local/bin/k9s
        log_success "k9s 설치 완료"
    fi
    
    # kubectx/kubens 설치
    if ! command -v kubectx > /dev/null; then
        log_info "kubectx/kubens 설치 중..."
        sudo git clone https://github.com/ahmetb/kubectx /opt/kubectx
        sudo ln -sf /opt/kubectx/kubectx /usr/local/bin/kubectx
        sudo ln -sf /opt/kubectx/kubens /usr/local/bin/kubens
        log_success "kubectx/kubens 설치 완료"
    fi
    
    # stern 설치 (로그 스트리밍)
    if ! command -v stern > /dev/null; then
        log_info "stern 설치 중..."
        STERN_VERSION=$(curl -s https://api.github.com/repos/stern/stern/releases/latest | grep tag_name | cut -d '"' -f 4)
        curl -L "https://github.com/stern/stern/releases/download/${STERN_VERSION}/stern_${STERN_VERSION#v}_linux_amd64.tar.gz" | sudo tar -xz -C /usr/local/bin stern
        sudo chmod +x /usr/local/bin/stern
        log_success "stern 설치 완료"
    fi
    
    log_success "Kubernetes 도구 설치 완료"
}

# 클러스터 상태 확인
verify_cluster() {
    if [ "$WORKER_ONLY" = true ]; then
        log_info "워커 노드 모드: 클러스터 상태 확인을 건너뜁니다."
        return
    fi
    
    log_step "✅ 클러스터 상태 확인"
    
    # 노드 상태 확인
    log_info "노드 상태:"
    kubectl get nodes -o wide
    
    # 파드 상태 확인
    log_info "시스템 파드 상태:"
    kubectl get pods -A
    
    # 서비스 상태 확인
    log_info "서비스 상태:"
    kubectl get svc -A
    
    # 클러스터 정보
    log_info "클러스터 정보:"
    kubectl cluster-info
    
    # 컴포넌트 상태 확인
    kubectl get componentstatuses 2>/dev/null || log_warning "ComponentStatus API가 비활성화되어 있습니다."
    
    log_success "클러스터 상태 확인 완료"
}

# Kubernetes 매니페스트 템플릿 생성
create_k8s_templates() {
    if [ "$WORKER_ONLY" = true ]; then
        return
    fi
    
    log_step "📄 Kubernetes 매니페스트 템플릿 생성"
    
    mkdir -p ~/k8s-templates
    
    # vLLM API 배포 매니페스트
    cat << 'EOF' > ~/k8s-templates/vllm-api-deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: vllm-api
  namespace: default
  labels:
    app: vllm-api
spec:
  replicas: 1
  selector:
    matchLabels:
      app: vllm-api
  template:
    metadata:
      labels:
        app: vllm-api
    spec:
      containers:
      - name: vllm-api
        image: vllm-api:latest
        ports:
        - containerPort: 8000
        env:
        - name: CUDA_VISIBLE_DEVICES
          value: "0"
        - name: MODEL_NAME
          value: "microsoft/DialoGPT-medium"
        resources:
          requests:
            memory: "4Gi"
            cpu: "2"
            nvidia.com/gpu: 1
          limits:
            memory: "8Gi"
            cpu: "4"
            nvidia.com/gpu: 1
        livenessProbe:
          httpGet:
            path: /health
            port: 8000
          initialDelaySeconds: 60
          periodSeconds: 30
        readinessProbe:
          httpGet:
            path: /health
            port: 8000
          initialDelaySeconds: 30
          periodSeconds: 10
        volumeMounts:
        - name: models
          mountPath: /app/models
        - name: logs
          mountPath: /app/logs
      volumes:
      - name: models
        persistentVolumeClaim:
          claimName: vllm-models-pvc
      - name: logs
        persistentVolumeClaim:
          claimName: vllm-logs-pvc
      nodeSelector:
        accelerator: nvidia-tesla-gpu
---
apiVersion: v1
kind: Service
metadata:
  name: vllm-api-service
  namespace: default
spec:
  selector:
    app: vllm-api
  ports:
  - protocol: TCP
    port: 80
    targetPort: 8000
  type: ClusterIP
---
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: vllm-api-ingress
  namespace: default
  annotations:
    nginx.ingress.kubernetes.io/rewrite-target: /
spec:
  ingressClassName: nginx
  rules:
  - host: vllm-api.local
    http:
      paths:
      - path: /
        pathType: Prefix
        backend:
          service:
            name: vllm-api-service
            port:
              number: 80
EOF
    
    # PVC 매니페스트
    cat << 'EOF' > ~/k8s-templates/vllm-pvc.yaml
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: vllm-models-pvc
  namespace: default
spec:
  accessModes:
    - ReadWriteOnce
  resources:
    requests:
      storage: 100Gi
  storageClassName: local-path
---
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: vllm-logs-pvc
  namespace: default
spec:
  accessModes:
    - ReadWriteOnce
  resources:
    requests:
      storage: 10Gi
  storageClassName: local-path
EOF
    
    # ConfigMap 예시
    cat << 'EOF' > ~/k8s-templates/vllm-configmap.yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: vllm-config
  namespace: default
data:
  server_config.yaml: |
    server:
      host: "0.0.0.0"
      port: 8000
      workers: 1
    model:
      name: "microsoft/DialoGPT-medium"
      max_tokens: 512
      temperature: 0.7
    vllm:
      tensor_parallel_size: 1
      gpu_memory_utilization: 0.9
      max_model_len: 2048
EOF
    
    log_success "Kubernetes 템플릿 생성 완료: ~/k8s-templates/"
}

# 시스템 정보 출력
show_k8s_info() {
    log_step "📋 Kubernetes 설정 정보"
    
    echo ""
    echo "==================== Kubernetes 정보 ===================="
    echo "kubectl 버전: $(kubectl version --client -o yaml 2>/dev/null | grep gitVersion | awk '{print $2}' || echo '설치되지 않음')"
    echo "kubeadm 버전: $(kubeadm version -o short 2>/dev/null || echo '설치되지 않음')"
    echo "Helm 버전: $(helm version --short 2>/dev/null || echo '설치되지 않음')"
    
    if [ "$WORKER_ONLY" = false ]; then
        echo "클러스터 상태: $(kubectl get nodes --no-headers 2>/dev/null | wc -l)개 노드"
        echo "CNI 플러그인: $CNI_PLUGIN"
    fi
    
    echo ""
    echo "유용한 명령어:"
    echo "  - 클러스터 상태: kubectl get nodes"
    echo "  - 모든 파드: kubectl get pods -A"
    echo "  - 클러스터 TUI: k9s"
    echo "  - 로그 스트리밍: stern <pod-name>"
    echo "  - 컨텍스트 전환: kubectx"
    echo "  - 네임스페이스 전환: kubens"
    
    if [ "$WORKER_ONLY" = false ]; then
        echo ""
        echo "대시보드 접속:"
        echo "  1. kubectl proxy"
        echo "  2. http://localhost:8001/api/v1/namespaces/kubernetes-dashboard/services/https:kubernetes-dashboard:/proxy/"
        echo "  3. 토큰: ~/get-dashboard-token.sh"
    fi
    
    echo "=================================================="
    echo ""
}

# 메인 함수
main() {
    log_info "🚀 Kubernetes 설치 시작"
    log_info "Kubernetes 버전: $K8S_VERSION"
    log_info "CNI 플러그인: $CNI_PLUGIN"
    
    if [ "$WORKER_ONLY" = true ]; then
        log_info "모드: 워커 노드"
    else
        log_info "모드: 마스터 노드"
    fi
    
    # 시스템 정보 확인
    detect_system
    
    # 제거 모드
    if [ "$UNINSTALL" = true ]; then
        uninstall_kubernetes
        exit 0
    fi
    
    # 기존 설치 확인
    if command -v kubectl > /dev/null; then
        log_warning "Kubernetes가 이미 설치되어 있을 수 있습니다."
        kubectl version --client 2>/dev/null || true
        read -p "계속 진행하시겠습니까? (y/N): " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            log_info "설치를 취소합니다."
            exit 0
        fi
    fi
    
    # 설치 과정
    prepare_system
    install_containerd
    add_kubernetes_repo
    install_kubernetes_components
    
    # 마스터 노드 설정
    if [ "$WORKER_ONLY" = false ]; then
        initialize_cluster
        install_cni_plugin
        install_kubernetes_dashboard
        install_metrics_server
        install_ingress_controller
        setup_storage_class
        create_k8s_templates
    fi
    
    # 공통 도구 설치
    if [ "$INSTALL_HELM" = true ]; then
        install_helm
    fi
    
    setup_kubectl_completion
    install_k8s_tools
    
    # 클러스터 확인
    verify_cluster
    
    # 정보 출력
    show_k8s_info
    
    log_success "🎉 Kubernetes 설치 완료!"
    echo ""
    
    if [ "$WORKER_ONLY" = false ]; then
        echo "다음 단계:"
        echo "  1. 워커 노드 추가: ~/k8s-join-command.sh (워커 노드에서 실행)"
        echo "  2. 애플리케이션 배포: kubectl apply -f ~/k8s-templates/"
        echo "  3. 클러스터 모니터링: k9s"
    else
        echo "워커 노드 설정이 완료되었습니다."
        echo "마스터 노드에서 생성된 조인 명령어를 실행하여 클러스터에 참여하세요."
    fi
    
    echo ""
    log_warning "⚠️  변경사항을 적용하려면 재로그인하거나 'source ~/.bashrc'를 실행하세요."
}

# 스크립트 실행
main "$@"