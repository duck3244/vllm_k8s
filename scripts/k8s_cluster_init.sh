# ==============================================================================
# scripts/k8s_cluster_init.sh - 클러스터 초기화 스크립트
# ==============================================================================
#!/bin/bash
# scripts/k8s_cluster_init.sh
# Kubernetes 클러스터 초기화 및 기본 설정 스크립트

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

# 네임스페이스 생성
create_namespaces() {
    log_step "📁 네임스페이스 생성"

    kubectl create namespace vllm-api --dry-run=client -o yaml | kubectl apply -f -
    kubectl create namespace monitoring --dry-run=client -o yaml | kubectl apply -f -
    kubectl create namespace logging --dry-run=client -o yaml | kubectl apply -f -

    log_success "네임스페이스 생성 완료"
}

# RBAC 설정
setup_rbac() {
    log_step "🔐 RBAC 설정"

    cat << EOF | kubectl apply -f -
apiVersion: v1
kind: ServiceAccount
metadata:
  name: vllm-api-sa
  namespace: vllm-api
---
apiVersion: rbac.authorization.k8s.io/v1
kind: ClusterRole
metadata:
  name: vllm-api-role
rules:
- apiGroups: [""]
  resources: ["pods", "services", "configmaps"]
  verbs: ["get", "list", "watch"]
---
apiVersion: rbac.authorization.k8s.io/v1
kind: ClusterRoleBinding
metadata:
  name: vllm-api-binding
roleRef:
  apiGroup: rbac.authorization.k8s.io
  kind: ClusterRole
  name: vllm-api-role
subjects:
- kind: ServiceAccount
  name: vllm-api-sa
  namespace: vllm-api
EOF

    log_success "RBAC 설정 완료"
}

# 리소스 쿼터 설정
setup_resource_quotas() {
    log_step "📊 리소스 쿼터 설정"

    cat << EOF | kubectl apply -f -
apiVersion: v1
kind: ResourceQuota
metadata:
  name: vllm-api-quota
  namespace: vllm-api
spec:
  hard:
    requests.cpu: "8"
    requests.memory: 32Gi
    requests.nvidia.com/gpu: 2
    limits.cpu: "16"
    limits.memory: 64Gi
    limits.nvidia.com/gpu: 2
    pods: "10"
    services: "5"
    persistentvolumeclaims: "10"
EOF

    log_success "리소스 쿼터 설정 완료"
}