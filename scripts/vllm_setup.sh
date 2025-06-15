# ==============================================================================
# scripts/vllm_setup.sh - vLLM 환경 설정 스크립트
# ==============================================================================
#!/bin/bash
# scripts/vllm_setup.sh
# vLLM 특화 환경 설정 스크립트

setup_vllm_environment() {
    log_step "🤖 vLLM 환경 설정"

    # vLLM 네임스페이스 설정
    kubectl create namespace vllm-system --dry-run=client -o yaml | kubectl apply -f -

    # vLLM 모델 스토리지 설정
    cat << EOF | kubectl apply -f -
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: vllm-model-cache
  namespace: vllm-system
spec:
  accessModes:
    - ReadWriteMany
  resources:
    requests:
      storage: 500Gi
  storageClassName: local-path
EOF

    # vLLM ConfigMap
    cat << EOF | kubectl apply -f -
apiVersion: v1
kind: ConfigMap
metadata:
  name: vllm-config
  namespace: vllm-system
data:
  vllm_config.yaml: |
    model_configs:
      - name: "llama2-7b"
        model_path: "meta-llama/Llama-2-7b-chat-hf"
        tensor_parallel_size: 1
        max_model_len: 4096
        gpu_memory_utilization: 0.9
      - name: "codellama-7b"
        model_path: "codellama/CodeLlama-7b-Instruct-hf"
        tensor_parallel_size: 1
        max_model_len: 4096
        gpu_memory_utilization: 0.9
    server:
      host: "0.0.0.0"
      port: 8000
      uvicorn_log_level: "info"
EOF

    log_success "vLLM 환경 설정 완료"
}