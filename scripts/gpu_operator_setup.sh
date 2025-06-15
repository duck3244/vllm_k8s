# ==============================================================================
# scripts/gpu_operator_setup.sh - GPU Operator 설치 스크립트
# ==============================================================================
#!/bin/bash
# scripts/gpu_operator_setup.sh
# NVIDIA GPU Operator 설치 스크립트

install_gpu_operator() {
    log_step "🎮 NVIDIA GPU Operator 설치"

    # Helm 저장소 추가
    helm repo add nvidia https://helm.ngc.nvidia.com/nvidia
    helm repo update

    # GPU Operator 설치
    helm install --wait gpu-operator \
        -n gpu-operator --create-namespace \
        nvidia/gpu-operator \
        --set driver.enabled=false

    log_success "GPU Operator 설치 완료"
}

verify_gpu_operator() {
    log_step "✅ GPU Operator 확인"

    kubectl get pods -n gpu-operator
    kubectl describe nodes | grep nvidia.com/gpu

    log_success "GPU Operator 확인 완료"
}