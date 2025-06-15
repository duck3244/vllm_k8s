# ==============================================================================
# scripts/ray_operator_setup.sh - Ray Operator 설치 스크립트
# ==============================================================================
#!/bin/bash
# scripts/ray_operator_setup.sh
# Ray Operator 설치 스크립트

install_ray_operator() {
    log_step "⚡ Ray Operator 설치"

    # Ray Operator 설치
    kubectl create -k "github.com/ray-project/kuberay/ray-operator/config/default?ref=v1.0.0"

    # Ray 클러스터 예시 생성
    cat << EOF | kubectl apply -f -
apiVersion: ray.io/v1
kind: RayCluster
metadata:
  name: raycluster-complete
  namespace: default
spec:
  rayVersion: '2.9.0'
  headGroupSpec:
    replicas: 1
    rayStartParams:
      dashboard-host: '0.0.0.0'
    template:
      spec:
        containers:
        - name: ray-head
          image: rayproject/ray:2.9.0
          resources:
            limits:
              cpu: 2
              memory: 4Gi
            requests:
              cpu: 2
              memory: 4Gi
          ports:
          - containerPort: 6379
            name: gcs-server
          - containerPort: 8265
            name: dashboard
          - containerPort: 10001
            name: client
  workerGroupSpecs:
  - replicas: 1
    minReplicas: 1
    maxReplicas: 5
    groupName: small-group
    rayStartParams: {}
    template:
      spec:
        containers:
        - name: ray-worker
          image: rayproject/ray:2.9.0
          lifecycle:
            preStop:
              exec:
                command: ["/bin/sh","-c","ray stop"]
          resources:
            limits:
              cpu: 2
              memory: 4Gi
            requests:
              cpu: 2
              memory: 4Gi
EOF

    log_success "Ray Operator 설치 완료"
}