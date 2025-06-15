# vLLM API 서버 배포 가이드

## 개요

이 문서는 vLLM API 서버를 다양한 환경에 배포하는 방법을 설명합니다. 개발 환경부터 프로덕션 환경까지 단계별로 안내합니다.

## 시스템 요구사항

### 최소 요구사항
- **CPU**: 8코어 이상
- **메모리**: 32GB RAM 이상
- **GPU**: NVIDIA GPU (8GB VRAM 이상 권장)
- **스토리지**: 100GB 이상 사용 가능 공간
- **OS**: Ubuntu 20.04 LTS 이상, CentOS 8 이상

### 권장 요구사항
- **CPU**: 16코어 이상 (Intel Xeon 또는 AMD EPYC)
- **메모리**: 64GB RAM 이상
- **GPU**: NVIDIA A100, V100, 또는 RTX 4090 이상
- **스토리지**: NVMe SSD 500GB 이상
- **네트워크**: 10Gbps 이상

## 환경별 배포 가이드

### 1. 로컬 개발 환경

#### 사전 준비
```bash
# Python 3.8+ 설치 확인
python3 --version

# pip 업그레이드
pip install --upgrade pip

# 가상환경 생성
python3 -m venv vllm-env
source vllm-env/bin/activate
```

#### 설치 및 실행
```bash
# 저장소 클론
git clone https://github.com/your-repo/vllm-api-server.git
cd vllm-api-server

# 의존성 설치
pip install -r requirements.txt

# 환경 설정
cp .env.example .env
# .env 파일을 편집하여 설정 조정

# 서버 실행
python app/main.py
```

#### 설정 파일 (.env)
```bash
# 서버 설정
HOST=0.0.0.0
PORT=8000
WORKERS=1

# 모델 설정
MODEL_NAME=meta-llama/Llama-2-7b-chat-hf
MODEL_PATH=/path/to/models
MAX_MODEL_LEN=4096
GPU_MEMORY_UTILIZATION=0.9

# 로깅 설정
LOG_LEVEL=INFO
LOG_FILE=logs/app.log

# Ray 설정 (멀티 GPU 사용시)
RAY_ENABLE=false
RAY_WORKERS=1
```

### 2. Docker 배포

#### Dockerfile
```dockerfile
FROM nvidia/cuda:12.1-devel-ubuntu22.04

# 시스템 패키지 설치
RUN apt-get update && apt-get install -y \
    python3 \
    python3-pip \
    git \
    wget \
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

# 서버 실행
CMD ["python3", "app/main.py"]
```

#### Docker Compose
```yaml
# docker-compose.yml
version: '3.8'

services:
  vllm-api:
    build: .
    ports:
      - "8000:8000"
    environment:
      - HOST=0.0.0.0
      - PORT=8000
      - MODEL_NAME=meta-llama/Llama-2-7b-chat-hf
      - GPU_MEMORY_UTILIZATION=0.9
    volumes:
      - ./models:/app/models
      - ./logs:/app/logs
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              count: 1
              capabilities: [gpu]
    restart: unless-stopped
    
  nginx:
    image: nginx:alpine
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./nginx.conf:/etc/nginx/nginx.conf
      - ./ssl:/etc/ssl/certs
    depends_on:
      - vllm-api
    restart: unless-stopped

  redis:
    image: redis:alpine
    ports:
      - "6379:6379"
    volumes:
      - redis_data:/data
    restart: unless-stopped

volumes:
  redis_data:
```

#### Docker 실행
```bash
# 이미지 빌드
docker build -t vllm-api-server .

# 컨테이너 실행
docker run -d \
  --name vllm-api \
  --gpus all \
  -p 8000:8000 \
  -v $(pwd)/models:/app/models \
  -v $(pwd)/logs:/app/logs \
  -e MODEL_NAME=meta-llama/Llama-2-7b-chat-hf \
  vllm-api-server

# Docker Compose 사용
docker-compose up -d
```

### 3. Kubernetes 배포

#### 네임스페이스 생성
```yaml
# namespace.yaml
apiVersion: v1
kind: Namespace
metadata:
  name: vllm-api
```

#### ConfigMap
```yaml
# configmap.yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: vllm-config
  namespace: vllm-api
data:
  HOST: "0.0.0.0"
  PORT: "8000"
  MODEL_NAME: "meta-llama/Llama-2-7b-chat-hf"
  GPU_MEMORY_UTILIZATION: "0.9"
  LOG_LEVEL: "INFO"
```

#### Deployment
```yaml
# deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: vllm-api-deployment
  namespace: vllm-api
spec:
  replicas: 2
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
        image: vllm-api-server:latest
        ports:
        - containerPort: 8000
        envFrom:
        - configMapRef:
            name: vllm-config
        resources:
          requests:
            memory: "16Gi"
            cpu: "4"
            nvidia.com/gpu: 1
          limits:
            memory: "32Gi"
            cpu: "8"
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
        - name: model-storage
          mountPath: /app/models
        - name: log-storage
          mountPath: /app/logs
      volumes:
      - name: model-storage
        persistentVolumeClaim:
          claimName: model-pvc
      - name: log-storage
        persistentVolumeClaim:
          claimName: log-pvc
      nodeSelector:
        accelerator: nvidia-tesla-v100
```

#### Service
```yaml
# service.yaml
apiVersion: v1
kind: Service
metadata:
  name: vllm-api-service
  namespace: vllm-api
spec:
  selector:
    app: vllm-api
  ports:
  - protocol: TCP
    port: 80
    targetPort: 8000
  type: ClusterIP
```

#### Ingress
```yaml
# ingress.yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: vllm-api-ingress
  namespace: vllm-api
  annotations:
    kubernetes.io/ingress.class: nginx
    cert-manager.io/cluster-issuer: letsencrypt-prod
    nginx.ingress.kubernetes.io/rate-limit: "100"
spec:
  tls:
  - hosts:
    - api.yourcompany.com
    secretName: vllm-api-tls
  rules:
  - host: api.yourcompany.com
    http:
      paths:
      - path: /
        pathType: Prefix
        backend:
          service:
            name: vllm-api-service
            port:
              number: 80
```

#### 배포 실행
```bash
# 네임스페이스 생성
kubectl apply -f namespace.yaml

# 설정 적용
kubectl apply -f configmap.yaml
kubectl apply -f deployment.yaml
kubectl apply -f service.yaml
kubectl apply -f ingress.yaml

# 배포 상태 확인
kubectl get pods -n vllm-api
kubectl get services -n vllm-api
kubectl logs -f deployment/vllm-api-deployment -n vllm-api
```

### 4. AWS EKS 배포

#### EKS 클러스터 생성
```bash
# eksctl 설치
curl --silent --location "https://github.com/weaveworks/eksctl/releases/latest/download/eksctl_$(uname -s)_amd64.tar.gz" | tar xz -C /tmp
sudo mv /tmp/eksctl /usr/local/bin

# 클러스터 생성
eksctl create cluster \
  --name vllm-cluster \
  --region us-west-2 \
  --nodegroup-name gpu-nodes \
  --node-type p3.2xlarge \
  --nodes 2 \
  --nodes-min 1 \
  --nodes-max 4 \
  --ssh-access \
  --ssh-public-key your-key-name
```

#### GPU 드라이버 설치
```bash
# NVIDIA 디바이스 플러그인 설치
kubectl apply -f https://raw.githubusercontent.com/NVIDIA/k8s-device-plugin/v0.14.0/nvidia-device-plugin.yml

# 노드에 GPU 라벨 추가
kubectl label nodes --all accelerator=nvidia-tesla-v100
```

### 5. Google Cloud Platform (GKE) 배포

#### GKE 클러스터 생성
```bash
# gcloud CLI 설치 및 인증
gcloud auth login
gcloud config set project your-project-id

# GPU 클러스터 생성
gcloud container clusters create vllm-cluster \
  --zone us-central1-a \
  --machine-type n1-standard-4 \
  --num-nodes 2 \
  --enable-autoscaling \
  --min-nodes 1 \
  --max-nodes 5 \
  --enable-gpu \
  --gpu-type nvidia-tesla-v100 \
  --gpu-count 1

# kubectl 설정
gcloud container clusters get-credentials vllm-cluster --zone us-central1-a
```

## 로드 밸런싱 및 오토스케일링

### Nginx 설정
```nginx
# nginx.conf
upstream vllm_backend {
    least_conn;
    server vllm-api-1:8000 max_fails=3 fail_timeout=30s;
    server vllm-api-2:8000 max_fails=3 fail_timeout=30s;
}

server {
    listen 80;
    server_name api.yourcompany.com;
    
    location / {
        proxy_pass http://vllm_backend;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_timeout 300s;
        proxy_read_timeout 300s;
    }
    
    location /health {
        access_log off;
        proxy_pass http://vllm_backend;
    }
}
```

### HPA (Horizontal Pod Autoscaler)
```yaml
# hpa.yaml
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: vllm-api-hpa
  namespace: vllm-api
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: vllm-api-deployment
  minReplicas: 2
  maxReplicas: 10
  metrics:
  - type: Resource
    resource:
      name: cpu
      target:
        type: Utilization
        averageUtilization: 70
  - type: Resource
    resource:
      name: memory
      target:
        type: Utilization
        averageUtilization: 80
```

## 모니터링 및 로깅

### Prometheus 설정
```yaml
# prometheus-config.yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: prometheus-config
data:
  prometheus.yml: |
    global:
      scrape_interval: 15s
    scrape_configs:
    - job_name: 'vllm-api'
      static_configs:
      - targets: ['vllm-api-service:80']
      metrics_path: /metrics
```

### Grafana 대시보드
```json
{
  "dashboard": {
    "title": "vLLM API Metrics",
    "panels": [
      {
        "title": "Request Rate",
        "type": "graph",
        "targets": [
          {
            "expr": "rate(http_requests_total[5m])",
            "legendFormat": "{{method}} {{handler}}"
          }
        ]
      },
      {
        "title": "Response Time",
        "type": "graph", 
        "targets": [
          {
            "expr": "histogram_quantile(0.95, rate(http_request_duration_seconds_bucket[5m]))",
            "legendFormat": "95th percentile"
          }
        ]
      }
    ]
  }
}
```

## 보안 설정

### SSL/TLS 인증서
```bash
# Let's Encrypt 인증서 발급
certbot certonly --nginx -d api.yourcompany.com

# 인증서 자동 갱신 크론잡 설정
echo "0 12 * * * /usr/bin/certbot renew --quiet" | crontab -
```

### API 키 인증
```python
# app/middleware/auth.py
from fastapi import HTTPException, Security
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

security = HTTPBearer()

async def verify_api_key(credentials: HTTPAuthorizationCredentials = Security(security)):
    if credentials.credentials != os.getenv("API_KEY"):
        raise HTTPException(status_code=401, detail="Invalid API key")
    return credentials.credentials
```

## 백업 및 복구

### 모델 백업
```bash
#!/bin/bash
# backup_models.sh

BACKUP_DIR="/backup/models"
MODEL_DIR="/app/models"
DATE=$(date +%Y%m%d_%H%M%S)

# 모델 디렉토리 백업
tar -czf "${BACKUP_DIR}/models_${DATE}.tar.gz" -C "${MODEL_DIR}" .

# 30일 이상 된 백업 파일 삭제
find "${BACKUP_DIR}" -name "models_*.tar.gz" -mtime +30 -delete

echo "모델 백업 완료: models_${DATE}.tar.gz"
```

### 데이터베이스 백업
```bash
#!/bin/bash
# backup_db.sh

BACKUP_DIR="/backup/db"
DATE=$(date +%Y%m%d_%H%M%S)

# Redis 백업
redis-cli --rdb "${BACKUP_DIR}/redis_${DATE}.rdb"

echo "데이터베이스 백업 완료: redis_${DATE}.rdb"
```

## 성능 튜닝

### GPU 메모리 최적화
```python
# app/config.py
class ModelConfig:
    GPU_MEMORY_UTILIZATION = 0.85  # GPU 메모리 사용률
    MAX_MODEL_LEN = 4096          # 최대 시퀀스 길이
    TENSOR_PARALLEL_SIZE = 1      # 텐서 병렬화 크기
    PIPELINE_PARALLEL_SIZE = 1    # 파이프라인 병렬화 크기
```

### Ray 클러스터 설정
```python
# ray_cluster.py
import ray

ray.init(
    address="ray://head-node:10001",
    runtime_env={
        "pip": ["vllm", "transformers", "torch"]
    }
)
```

## 트러블슈팅

### 일반적인 이슈

1. **GPU 메모리 부족**
   ```bash
   # GPU 메모리 사용량 확인
   nvidia-smi
   
   # 설정에서 GPU_MEMORY_UTILIZATION 값 조정
   export GPU_MEMORY_UTILIZATION=0.7
   ```

2. **모델 로딩 실패**
   ```bash
   # 모델 파일 권한 확인
   ls -la /app/models/
   
   # 모델 다운로드 재시도
   python -c "from transformers import AutoTokenizer, AutoModelForCausalLM; AutoTokenizer.from_pretrained('meta-llama/Llama-2-7b-chat-hf'); AutoModelForCausalLM.from_pretrained('meta-llama/Llama-2-7b-chat-hf')"
   ```

3. **포트 바인딩 오류**
   ```bash
   # 포트 사용 중인 프로세스 확인
   lsof -i :8000
   
   # 프로세스 종료
   kill -9 <PID>
   ```

### 로그 분석
```bash
# 실시간 로그 모니터링
tail -f logs/app.log

# 에러 로그 필터링
grep -i error logs/app.log

# 성능 로그 분석
grep "response_time" logs/app.log | awk '{print $NF}' | sort -n
```

## CI/CD 파이프라인

### GitHub Actions
```yaml
# .github/workflows/deploy.yml
name: Deploy vLLM API Server

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
    - uses: actions/checkout@v3
    - name: Set up Python
      uses: actions/setup-python@v4
      with:
        python-version: 3.9
    - name: Install dependencies
      run: |
        pip install -r requirements.txt
        pip install pytest pytest-cov
    - name: Run tests
      run: |
        python tests/run_tests.py --type unit --coverage

  build:
    needs: test
    runs-on: ubuntu-latest
    steps:
    - uses: actions/checkout@v3
    - name: Build Docker image
      run: |
        docker build -t vllm-api-server:${{ github.sha }} .
        docker tag vllm-api-server:${{ github.sha }} vllm-api-server:latest
    - name: Push to registry
      run: |
        echo ${{ secrets.DOCKER_PASSWORD }} | docker login -u ${{ secrets.DOCKER_USERNAME }} --password-stdin
        docker push vllm-api-server:${{ github.sha }}
        docker push vllm-api-server:latest

  deploy:
    needs: build
    runs-on: ubuntu-latest
    if: github.ref == 'refs/heads/main'
    steps:
    - name: Deploy to Kubernetes
      run: |
        echo "${{ secrets.KUBECONFIG }}" | base64 -d > kubeconfig
        export KUBECONFIG=kubeconfig
        kubectl set image deployment/vllm-api-deployment vllm-api=vllm-api-server:${{ github.sha }} -n vllm-api
        kubectl rollout status deployment/vllm-api-deployment -n vllm-api
```

### Jenkins Pipeline
```groovy
// Jenkinsfile
pipeline {
    agent any
    
    environment {
        DOCKER_REGISTRY = 'your-registry.com'
        IMAGE_NAME = 'vllm-api-server'
        KUBECONFIG = credentials('kubeconfig')
    }
    
    stages {
        stage('Test') {
            steps {
                sh 'python tests/run_tests.py --type all --coverage'
                publishTestResults testResultsPattern: 'tests/reports/*.xml'
                publishCoverageReports([
                    coberturaReportFile: 'coverage.xml'
                ])
            }
        }
        
        stage('Build') {
            steps {
                script {
                    def image = docker.build("${DOCKER_REGISTRY}/${IMAGE_NAME}:${BUILD_NUMBER}")
                    docker.withRegistry("https://${DOCKER_REGISTRY}", 'docker-registry-credentials') {
                        image.push()
                        image.push('latest')
                    }
                }
            }
        }
        
        stage('Deploy') {
            when { branch 'main' }
            steps {
                sh """
                    kubectl set image deployment/vllm-api-deployment \\
                        vllm-api=${DOCKER_REGISTRY}/${IMAGE_NAME}:${BUILD_NUMBER} \\
                        -n vllm-api
                    kubectl rollout status deployment/vllm-api-deployment -n vllm-api
                """
            }
        }
    }
    
    post {
        always {
            cleanWs()
        }
        failure {
            emailext (
                subject: "Build Failed: ${env.JOB_NAME} - ${env.BUILD_NUMBER}",
                body: "Build failed. Check console output for details.",
                to: "${env.CHANGE_AUTHOR_EMAIL}"
            )
        }
    }
}
```

## 환경별 설정

### 개발 환경 (Development)
```yaml
# config/dev.yaml
server:
  host: localhost
  port: 8000
  workers: 1
  
model:
  name: meta-llama/Llama-2-7b-chat-hf
  max_length: 2048
  gpu_memory_utilization: 0.7

logging:
  level: DEBUG
  file: logs/dev.log

cache:
  enabled: false
```

### 스테이징 환경 (Staging)
```yaml
# config/staging.yaml
server:
  host: 0.0.0.0
  port: 8000
  workers: 2
  
model:
  name: meta-llama/Llama-2-7b-chat-hf
  max_length: 4096
  gpu_memory_utilization: 0.8

logging:
  level: INFO
  file: logs/staging.log

cache:
  enabled: true
  redis_url: redis://redis:6379
```

### 프로덕션 환경 (Production)
```yaml
# config/prod.yaml
server:
  host: 0.0.0.0
  port: 8000
  workers: 4
  
model:
  name: meta-llama/Llama-2-7b-chat-hf
  max_length: 4096
  gpu_memory_utilization: 0.9

logging:
  level: WARNING
  file: logs/prod.log

cache:
  enabled: true
  redis_url: redis://redis-cluster:6379

security:
  api_key_required: true
  rate_limit: 1000
```

## 비용 최적화

### 인스턴스 스케줄링
```bash
#!/bin/bash
# auto_scaling.sh

# 업무 시간 (09:00-18:00) 스케일 업
if [ $(date +%H) -ge 9 ] && [ $(date +%H) -le 18 ]; then
    kubectl scale deployment vllm-api-deployment --replicas=4 -n vllm-api
else
    # 업무 시간 외 스케일 다운
    kubectl scale deployment vllm-api-deployment --replicas=1 -n vllm-api
fi
```

### Spot 인스턴스 활용
```yaml
# spot-nodepool.yaml
apiVersion: v1
kind: NodePool
metadata:
  name: spot-gpu-pool
spec:
  nodeClassRef:
    name: spot-nodeclass
  taints:
  - key: spot-instance
    value: "true"
    effect: NoSchedule
  requirements:
  - key: karpenter.sh/capacity-type
    operator: In
    values: ["spot"]
  - key: node.kubernetes.io/instance-type
    operator: In
    values: ["p3.2xlarge", "p3.8xlarge"]
```

## 마이그레이션 가이드

### 버전 업그레이드
```bash
#!/bin/bash
# migrate.sh

# 1. 백업 생성
./backup_models.sh
./backup_db.sh

# 2. 새 버전 배포
kubectl set image deployment/vllm-api-deployment vllm-api=vllm-api-server:v2.0.0 -n vllm-api

# 3. 배포 상태 확인
kubectl rollout status deployment/vllm-api-deployment -n vllm-api

# 4. 헬스체크
curl -f http://api.yourcompany.com/health

# 5. 이전 버전으로 롤백 (필요시)
# kubectl rollout undo deployment/vllm-api-deployment -n vllm-api
```

### 데이터 마이그레이션
```python
# migrate_data.py
import redis
import json

def migrate_cache_format():
    """캐시 데이터 형식 마이그레이션"""
    r = redis.Redis(host='redis', port=6379, db=0)
    
    # 기존 키 패턴
    old_keys = r.keys('cache:*')
    
    for key in old_keys:
        old_data = r.get(key)
        if old_data:
            # 새 형식으로 변환
            new_data = transform_data(json.loads(old_data))
            new_key = key.decode().replace('cache:', 'v2:cache:')
            r.set(new_key, json.dumps(new_data))
            r.delete(key)

def transform_data(old_data):
    """데이터 형식 변환"""
    return {
        'version': '2.0',
        'timestamp': old_data.get('created_at'),
        'content': old_data.get('response'),
        'metadata': {
            'model': old_data.get('model_name'),
            'tokens': old_data.get('token_count')
        }
    }

if __name__ == "__main__":
    migrate_cache_format()
    print("데이터 마이그레이션 완료")
```

## 재해 복구 계획

### 백업 전략
```bash
#!/bin/bash
# disaster_recovery.sh

# 1. 다중 지역 백업
aws s3 sync /app/models s3://backup-us-west-2/models/
aws s3 sync /app/models s3://backup-eu-west-1/models/ --region eu-west-1

# 2. 데이터베이스 복제
redis-cli --rdb backup.rdb
aws s3 cp backup.rdb s3://backup-us-west-2/db/

# 3. 설정 파일 백업
kubectl get configmap vllm-config -o yaml > config-backup.yaml
aws s3 cp config-backup.yaml s3://backup-us-west-2/config/
```

### 복구 절차
```bash
#!/bin/bash
# restore.sh

# 1. 백업에서 모델 복원
aws s3 sync s3://backup-us-west-2/models/ /app/models/

# 2. 데이터베이스 복원
aws s3 cp s3://backup-us-west-2/db/backup.rdb .
redis-cli --rdb backup.rdb FLUSHALL
redis-cli DEBUG RELOAD

# 3. 서비스 재시작
kubectl rollout restart deployment/vllm-api-deployment -n vllm-api
```

## 지원 및 유지보수

### 정기 점검 체크리스트
- [ ] GPU 메모리 사용률 확인
- [ ] 디스크 공간 사용량 점검
- [ ] 로그 파일 크기 확인 및 로테이션
- [ ] 보안 업데이트 적용
- [ ] 성능 메트릭 리뷰
- [ ] 백업 무결성 검증

### 연락처
- **운영팀**: ops@yourcompany.com
- **개발팀**: dev@yourcompany.com
- **긴급 대응**: +82-10-1234-5678

이 배포 가이드를 통해 vLLM API 서버를 안정적이고 확장 가능하게 배포할 수 있습니다. 환경에 맞는 배포 방식을 선택하고, 지속적인 모니터링과 유지보수를 통해 최적의 성능을 유지하세요.