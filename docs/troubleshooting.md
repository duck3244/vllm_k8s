# vLLM API 서버 문제 해결 가이드

## 개요

이 문서는 vLLM API 서버 운영 중 발생할 수 있는 일반적인 문제들과 해결 방법을 제공합니다. 문제 유형별로 단계적인 진단 및 해결 방법을 안내합니다.

## 목차

1. [서버 시작 문제](#서버-시작-문제)
2. [모델 로딩 문제](#모델-로딩-문제)
3. [GPU 관련 문제](#gpu-관련-문제)
4. [메모리 문제](#메모리-문제)
5. [성능 문제](#성능-문제)
6. [네트워크 문제](#네트워크-문제)
7. [API 응답 문제](#api-응답-문제)
8. [Docker 관련 문제](#docker-관련-문제)
9. [Kubernetes 관련 문제](#kubernetes-관련-문제)
10. [로깅 및 모니터링](#로깅-및-모니터링)

## 서버 시작 문제

### 1. 포트 바인딩 실패

**증상:**
```
OSError: [Errno 98] Address already in use
```

**원인:** 지정된 포트가 이미 사용 중

**해결 방법:**
```bash
# 1. 포트 사용 중인 프로세스 확인
lsof -i :8000
netstat -tlnp | grep :8000

# 2. 프로세스 종료
kill -9 <PID>

# 3. 다른 포트 사용
export PORT=8001
python app/main.py

# 4. 시스템 재부팅 후 재시도 (필요시)
sudo reboot
```

### 2. 환경 변수 누락

**증상:**
```
KeyError: 'MODEL_NAME'
ValueError: Environment variable not set
```

**해결 방법:**
```bash
# 1. 환경 변수 확인
env | grep -i model

# 2. .env 파일 존재 확인
ls -la .env

# 3. .env.example에서 복사
cp .env.example .env

# 4. 필수 환경 변수 설정
export MODEL_NAME=meta-llama/Llama-2-7b-chat-hf
export HOST=0.0.0.0
export PORT=8000
```

### 3. 의존성 패키지 누락

**증상:**
```
ModuleNotFoundError: No module named 'vllm'
ImportError: cannot import name 'AsyncLLMEngine'
```

**해결 방법:**
```bash
# 1. 가상환경 활성화 확인
which python
echo $VIRTUAL_ENV

# 2. 의존성 재설치
pip install -r requirements.txt

# 3. vLLM 수동 설치
pip install vllm

# 4. CUDA 버전 호환성 확인
nvidia-smi
pip install torch --index-url https://download.pytorch.org/whl/cu121
```

## 모델 로딩 문제

### 1. 모델 파일을 찾을 수 없음

**증상:**
```
FileNotFoundError: Model not found at /path/to/model
OSError: Can't load tokenizer for 'meta-llama/Llama-2-7b-chat-hf'
```

**해결 방법:**
```bash
# 1. 모델 경로 확인
ls -la /app/models/
echo $MODEL_PATH

# 2. Hugging Face 캐시 확인
ls -la ~/.cache/huggingface/

# 3. 모델 수동 다운로드
python -c "
from transformers import AutoTokenizer, AutoModelForCausalLM
tokenizer = AutoTokenizer.from_pretrained('meta-llama/Llama-2-7b-chat-hf')
model = AutoModelForCausalLM.from_pretrained('meta-llama/Llama-2-7b-chat-hf')
"

# 4. 네트워크 연결 확인
curl -I https://huggingface.co

# 5. 토큰 설정 (private 모델의 경우)
export HUGGINGFACE_HUB_TOKEN=your_token_here
```

### 2. 모델 권한 문제

**증상:**
```
PermissionError: [Errno 13] Permission denied
OSError: You are trying to access a gated repo
```

**해결 방법:**
```bash
# 1. 파일 권한 확인
ls -la /app/models/
stat /app/models/model_name/

# 2. 권한 수정
sudo chown -R $(whoami):$(whoami) /app/models/
chmod -R 755 /app/models/

# 3. Hugging Face 토큰 설정
huggingface-cli login

# 4. Docker 컨테이너 내에서 실행시
docker run -v ~/.cache/huggingface:/root/.cache/huggingface your-image
```

### 3. 모델 형식 호환성 문제

**증상:**
```
ValueError: Unsupported model architecture
RuntimeError: Model format not supported by vLLM
```

**해결 방법:**
```bash
# 1. 지원 모델 목록 확인
python -c "from vllm import ModelRegistry; print(ModelRegistry.get_supported_archs())"

# 2. 모델 변환 (필요시)
python convert_model.py --input /path/to/original --output /path/to/converted

# 3. 호환 모델로 교체
export MODEL_NAME=microsoft/DialoGPT-medium

# 4. vLLM 버전 업데이트
pip install --upgrade vllm
```

## GPU 관련 문제

### 1. GPU를 찾을 수 없음

**증상:**
```
RuntimeError: No CUDA GPUs are available
NVIDIA-SMI has failed because it couldn't communicate with the NVIDIA driver
```

**해결 방법:**
```bash
# 1. GPU 상태 확인
nvidia-smi
lspci | grep -i nvidia

# 2. NVIDIA 드라이버 설치 상태 확인
nvidia-driver-version
dpkg -l | grep nvidia

# 3. CUDA 설치 확인
nvcc --version
echo $CUDA_HOME

# 4. Docker에서 GPU 접근 확인
docker run --gpus all nvidia/cuda:11.8-base nvidia-smi

# 5. 드라이버 재설치 (필요시)
sudo apt purge nvidia-* -y
sudo apt autoremove -y
sudo apt install nvidia-driver-470 -y
sudo reboot
```

### 2. GPU 메모리 부족

**증상:**
```
torch.cuda.OutOfMemoryError: CUDA out of memory
RuntimeError: Unable to allocate memory on device
```

**해결 방법:**
```bash
# 1. GPU 메모리 사용량 확인
nvidia-smi --query-gpu=memory.used,memory.total --format=csv

# 2. GPU 메모리 사용률 조정
export GPU_MEMORY_UTILIZATION=0.7  # 기본값: 0.9

# 3. 모델 크기 줄이기
export MAX_MODEL_LEN=2048  # 기본값: 4096

# 4. 배치 크기 조정
export MAX_NUM_BATCHED_TOKENS=4096

# 5. 다른 GPU 프로세스 종료
sudo fuser -v /dev/nvidia*
kill -9 <GPU_PID>

# 6. GPU 메모리 초기화
python -c "
import torch
torch.cuda.empty_cache()
torch.cuda.ipc_collect()
"
```

### 3. 멀티 GPU 설정 문제

**증상:**
```
RuntimeError: Tensor parallel size exceeds number of available GPUs
AssertionError: tensor_parallel_size must be divisible by world_size
```

**해결 방법:**
```bash
# 1. 사용 가능한 GPU 수 확인
nvidia-smi --list-gpus
python -c "import torch; print(torch.cuda.device_count())"

# 2. 텐서 병렬화 크기 조정
export TENSOR_PARALLEL_SIZE=2  # GPU 수에 맞게 조정

# 3. Ray 클러스터 설정 확인
ray status
ray list nodes

# 4. GPU 가시성 설정
export CUDA_VISIBLE_DEVICES=0,1,2,3

# 5. 분산 설정 확인
export NCCL_DEBUG=INFO
export NCCL_IB_DISABLE=1  # InfiniBand 비활성화
```

## 메모리 문제

### 1. 시스템 메모리 부족

**증상:**
```
MemoryError: Unable to allocate memory
OSError: [Errno 12] Cannot allocate memory
```

**해결 방법:**
```bash
# 1. 메모리 사용량 확인
free -h
top -o %MEM
ps aux --sort=-%mem | head

# 2. 메모리 사용 프로세스 정리
sudo systemctl stop unnecessary-service
killall chrome firefox

# 3. 스왑 공간 확인 및 추가
swapon --show
sudo fallocate -l 8G /swapfile
sudo chmod 600 /swapfile
sudo mkswap /swapfile
sudo swapon /swapfile

# 4. 모델 로딩 방식 변경
export LOAD_IN_8BIT=true
export LOAD_IN_4BIT=true

# 5. 가비지 컬렉션 강제 실행
python -c "
import gc
gc.collect()
"
```

### 2. 메모리 누수

**증상:**
- 시간이 지날수록 메모리 사용량 증가
- 서버 응답 속도 점진적 저하

**해결 방법:**
```bash
# 1. 메모리 사용량 모니터링
python -c "
import psutil
import time
while True:
    mem = psutil.virtual_memory()
    print(f'Memory: {mem.percent}% used')
    time.sleep(60)
"

# 2. 메모리 프로파일링
pip install memory-profiler
python -m memory_profiler app/main.py

# 3. 주기적 재시작 설정
# crontab -e
# 0 2 * * * /usr/bin/systemctl restart vllm-api

# 4. 가비지 컬렉션 튜닝
export PYTHONHASHSEED=0
export MALLOC_MMAP_THRESHOLD_=131072
```

## 성능 문제

### 1. 응답 속도 저하

**증상:**
- API 응답 시간 증가
- 높은 대기 시간

**진단:**
```bash
# 1. 응답 시간 측정
curl -w "@curl-format.txt" -o /dev/null -s "http://localhost:8000/v1/chat/completions" \
  -H "Content-Type: application/json" \
  -d '{"model":"meta-llama/Llama-2-7b-chat-hf","messages":[{"role":"user","content":"Hello"}]}'

# curl-format.txt 내용:
# time_namelookup:    %{time_namelookup}\n
# time_connect:       %{time_connect}\n
# time_appconnect:    %{time_appconnect}\n
# time_pretransfer:   %{time_pretransfer}\n
# time_redirect:      %{time_redirect}\n
# time_starttransfer: %{time_starttransfer}\n
# time_total:         %{time_total}\n

# 2. 시스템 리소스 확인
htop
iotop
nvidia-smi -l 1
```

**해결 방법:**
```bash
# 1. 워커 수 조정
export WORKERS=4  # CPU 코어 수에 맞게

# 2. 배치 처리 최적화
export MAX_NUM_BATCHED_TOKENS=8192
export MAX_NUM_SEQS=256

# 3. KV 캐시 최적화
export ENABLE_PREFIX_CACHING=true
export KV_CACHE_DTYPE="fp8"

# 4. 추론 엔진 설정 튜닝
export USE_V2_BLOCK_MANAGER=true
export PREEMPTION_MODE="recompute"
```

### 2. 높은 CPU 사용률

**증상:**
```
CPU usage consistently above 90%
High system load average
```

**해결 방법:**
```bash
# 1. CPU 사용량 분석
top -H -p $(pgrep -f vllm)
perf top -p $(pgrep -f vllm)

# 2. 스레드 수 제한
export OMP_NUM_THREADS=8
export MKL_NUM_THREADS=8

# 3. CPU 친화성 설정
taskset -c 0-7 python app/main.py

# 4. 우선순위 조정
nice -n -10 python app/main.py
```

### 3. 디스크 I/O 병목

**증상:**
```
High disk wait time (iowait)
Slow model loading
```

**해결 방법:**
```bash
# 1. 디스크 사용량 확인
df -h
iotop -o

# 2. 모델을 SSD로 이동
sudo mount /dev/nvme0n1 /app/models
export MODEL_PATH=/app/models

# 3. 디스크 캐시 설정
echo 3 > /proc/sys/vm/drop_caches
echo 'vm.swappiness=10' >> /etc/sysctl.conf

# 4. tmpfs 사용 (메모리가 충분한 경우)
sudo mount -t tmpfs -o size=32G tmpfs /tmp/models
```

## 네트워크 문제

### 1. 연결 시간 초과

**증상:**
```
requests.exceptions.Timeout: HTTPSConnectionPool
curl: (28) Operation timed out
```

**해결 방법:**
```bash
# 1. 네트워크 연결 테스트
ping -c 4 localhost
telnet localhost 8000

# 2. 방화벽 확인
sudo ufw status
sudo iptables -L

# 3. 타임아웃 설정 조정
export REQUEST_TIMEOUT=300
export KEEPALIVE_TIMEOUT=60

# 4. 프록시 설정 확인
echo $HTTP_PROXY
echo $HTTPS_PROXY
unset HTTP_PROXY HTTPS_PROXY  # 필요시
```

### 2. 대역폭 문제

**증상:**
- 대용량 응답 전송 지연
- 스트리밍 응답 끊김

**해결 방법:**
```bash
# 1. 네트워크 대역폭 확인
iperf3 -s  # 서버
iperf3 -c server_ip  # 클라이언트

# 2. TCP 튜닝
echo 'net.core.rmem_max = 134217728' >> /etc/sysctl.conf
echo 'net.core.wmem_max = 134217728' >> /etc/sysctl.conf
sudo sysctl -p

# 3. 압축 활성화
export ENABLE_GZIP=true

# 4. 청크 크기 조정
export CHUNK_SIZE=8192
```

## API 응답 문제

### 1. HTTP 500 내부 서버 오류

**증상:**
```json
{
  "error": {
    "message": "Internal server error",
    "type": "internal_error"
  }
}
```

**진단 및 해결:**
```bash
# 1. 로그 확인
tail -f logs/app.log
grep -i error logs/app.log

# 2. 스택 트레이스 활성화
export LOG_LEVEL=DEBUG
export TRACEBACK_ENABLED=true

# 3. 헬스체크 확인
curl http://localhost:8000/health

# 4. 서비스 재시작
sudo systemctl restart vllm-api
# 또는
docker restart vllm-api-container
```

### 2. 잘못된 JSON 응답

**증상:**
```
json.decoder.JSONDecodeError: Expecting value
Invalid JSON format in response
```

**해결 방법:**
```bash
# 1. 응답 형식 검증
curl -v http://localhost:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{"model":"meta-llama/Llama-2-7b-chat-hf","messages":[{"role":"user","content":"test"}]}'

# 2. JSON 유효성 검사
echo '$response' | jq .

# 3. 인코딩 확인
export PYTHONIOENCODING=utf-8
locale

# 4. 응답 크기 제한 확인
export MAX_RESPONSE_SIZE=32768
```

### 3. 스트리밍 응답 문제

**증상:**
- 스트리밍이 중간에 끊김
- 불완전한 SSE 이벤트

**해결 방법:**
```bash
# 1. 스트리밍 테스트
curl -N http://localhost:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{"model":"meta-llama/Llama-2-7b-chat-hf","messages":[{"role":"user","content":"Count to 10"}],"stream":true}'

# 2. 버퍼링 비활성화
export PYTHONUNBUFFERED=1
export STREAMING_TIMEOUT=60

# 3. 프록시 설정 확인 (nginx)
# nginx.conf에서:
# proxy_buffering off;
# proxy_cache off;
# proxy_read_timeout 300s;
```

## Docker 관련 문제

### 1. 컨테이너 시작 실패

**증상:**
```
docker: Error response from daemon: could not select device driver
Container exited with code 125
```

**해결 방법:**
```bash
# 1. Docker 로그 확인
docker logs container_name
docker events

# 2. GPU 런타임 확인
docker run --rm --gpus all nvidia/cuda:11.8-base nvidia-smi

# 3. nvidia-container-runtime 설치
sudo apt-get install nvidia-container-runtime
sudo systemctl restart docker

# 4. Docker daemon 설정 확인
cat /etc/docker/daemon.json
sudo systemctl status docker

# 5. 권한 문제 해결
sudo usermod -aG docker $USER
newgrp docker
```

### 2. 볼륨 마운트 문제

**증상:**
```
docker: Error response from daemon: invalid mount config
Permission denied when accessing mounted files
```

**해결 방법:**
```bash
# 1. 볼륨 권한 확인
ls -la /host/path
docker exec container_name ls -la /container/path

# 2. SELinux 컨텍스트 수정 (CentOS/RHEL)
sudo chcon -Rt svirt_sandbox_file_t /host/path

# 3. 올바른 마운트 문법 사용
docker run -v /absolute/host/path:/container/path:rw image_name

# 4. 사용자 ID 매핑
docker run --user $(id -u):$(id -g) image_name
```

### 3. 네트워크 연결 문제

**증상:**
```
docker: Error response from daemon: network not found
Container cannot reach external services
```

**해결 방법:**
```bash
# 1. 네트워크 목록 확인
docker network ls

# 2. 컨테이너 네트워크 정보
docker inspect container_name | grep -A 20 NetworkSettings

# 3. 사용자 정의 네트워크 생성
docker network create vllm-network
docker run --network vllm-network image_name

# 4. DNS 설정 확인
docker run --dns 8.8.8.8 image_name

# 5. 포트 바인딩 확인
docker run -p 8000:8000 image_name
netstat -tlnp | grep 8000
```

## Kubernetes 관련 문제

### 1. Pod 시작 실패

**증상:**
```
Pod stuck in Pending state
CrashLoopBackOff status
ImagePullBackOff error
```

**진단:**
```bash
# 1. Pod 상태 확인
kubectl get pods -n vllm-api
kubectl describe pod pod-name -n vllm-api

# 2. 이벤트 로그 확인
kubectl get events -n vllm-api --sort-by='.lastTimestamp'

# 3. Pod 로그 확인
kubectl logs pod-name -n vllm-api
kubectl logs pod-name -n vllm-api --previous
```

**해결 방법:**
```bash
# 1. 리소스 요청량 조정
kubectl edit deployment vllm-api-deployment -n vllm-api
# resources.requests 값 감소

# 2. 노드 상태 확인
kubectl get nodes
kubectl describe node node-name

# 3. 이미지 풀 정책 수정
kubectl patch deployment vllm-api-deployment -n vllm-api -p '{"spec":{"template":{"spec":{"containers":[{"name":"vllm-api","imagePullPolicy":"Always"}]}}}}'

# 4. Secret 확인 (private 이미지)
kubectl get secrets -n vllm-api
kubectl create secret docker-registry regcred \
  --docker-server=your-registry.com \
  --docker-username=your-username \
  --docker-password=your-password
```

### 2. 서비스 연결 문제

**증상:**
```
Service endpoints not available
Cannot connect to service from other pods
```

**해결 방법:**
```bash
# 1. 서비스 상태 확인
kubectl get svc -n vllm-api
kubectl describe svc vllm-api-service -n vllm-api

# 2. 엔드포인트 확인
kubectl get endpoints -n vllm-api
kubectl describe endpoints vllm-api-service -n vllm-api

# 3. 레이블 셀렉터 확인
kubectl get pods -n vllm-api --show-labels
kubectl get svc vllm-api-service -n vllm-api -o yaml | grep selector

# 4. 네트워크 정책 확인
kubectl get networkpolicies -n vllm-api

# 5. DNS 테스트
kubectl run test-pod --image=busybox --rm -it --restart=Never -- nslookup vllm-api-service.vllm-api.svc.cluster.local
```

### 3. 퍼시스턴트 볼륨 문제

**증상:**
```
PersistentVolumeClaim stuck in Pending
Volume mount failed
```

**해결 방법:**
```bash
# 1. PVC 상태 확인
kubectl get pvc -n vllm-api
kubectl describe pvc model-pvc -n vllm-api

# 2. 스토리지 클래스 확인
kubectl get storageclass
kubectl describe storageclass storage-class-name

# 3. PV 상태 확인
kubectl get pv
kubectl describe pv pv-name

# 4. 노드 스토리지 확인
kubectl get nodes -o wide
ssh node-name "df -h"

# 5. 동적 프로비저닝 설정 확인
kubectl get pods -n kube-system | grep provisioner
```

## 로깅 및 모니터링

### 1. 로그 수집 설정

**로그 레벨 조정:**
```bash
# 환경 변수로 설정
export LOG_LEVEL=DEBUG  # DEBUG, INFO, WARNING, ERROR

# 실시간 로그 모니터링
tail -f logs/app.log

# 로그 필터링
grep -i "error\|exception\|failure" logs/app.log
grep -E "^$(date +%Y-%m-%d)" logs/app.log  # 오늘 로그만
```

**구조화된 로깅:**
```python
# app/utils/logger.py 확인
import logging
import json

def setup_structured_logging():
    formatter = logging.Formatter(
        '{"timestamp": "%(asctime)s", "level": "%(levelname)s", "message": "%(message)s", "module": "%(name)s"}'
    )
    handler = logging.StreamHandler()
    handler.setFormatter(formatter)
    logging.getLogger().addHandler(handler)
```

### 2. 성능 메트릭 모니터링

**기본 메트릭 수집:**
```bash
# 1. CPU 및 메모리 사용률
ps -p $(pgrep -f vllm) -o pid,ppid,cmd,%mem,%cpu

# 2. GPU 메트릭
nvidia-smi --query-gpu=timestamp,name,temperature.gpu,utilization.gpu,memory.used,memory.total --format=csv -l 5

# 3. 네트워크 I/O
ss -tuln | grep :8000
netstat -i

# 4. 디스크 I/O
iostat -x 1 5
```

**Prometheus 메트릭 설정:**
```python
# app/middleware/metrics.py
from prometheus_client import Counter, Histogram, Gauge

REQUEST_COUNT = Counter('requests_total', 'Total requests', ['method', 'endpoint'])
REQUEST_DURATION = Histogram('request_duration_seconds', 'Request duration')
GPU_MEMORY_USAGE = Gauge('gpu_memory_usage_bytes', 'GPU memory usage')
```

### 3. 알림 설정

**기본 알림 규칙:**
```yaml
# prometheus/alerts.yml
groups:
- name: vllm-api-alerts
  rules:
  - alert: HighErrorRate
    expr: rate(http_requests_total{status=~"5.."}[5m]) > 0.1
    for: 5m
    annotations:
      summary: High error rate detected
      
  - alert: HighGPUMemoryUsage
    expr: gpu_memory_usage_bytes / gpu_memory_total_bytes > 0.95
    for: 2m
    annotations:
      summary: GPU memory usage is too high
      
  - alert: ServiceDown
    expr: up{job="vllm-api"} == 0
    for: 1m
    annotations:
      summary: vLLM API service is down
```

**Slack 알림 설정:**
```bash
# alertmanager.yml
route:
  group_by: ['alertname']
  receiver: 'slack-notifications'

receivers:
- name: 'slack-notifications'
  slack_configs:
  - api_url: 'https://hooks.slack.com/services/YOUR/SLACK/WEBHOOK'
    channel: '#alerts'
    title: 'vLLM API Alert'
    text: '{{ range .Alerts }}{{ .Annotations.summary }}{{ end }}'
```

## 디버깅 도구 및 기법

### 1. 프로파일링

**메모리 프로파일링:**
```bash
# memory_profiler 사용
pip install memory-profiler
python -m memory_profiler app/main.py

# line_profiler 사용
pip install line_profiler
kernprof -l -v app/main.py
```

**성능 프로파일링:**
```bash
# cProfile 사용
python -m cProfile -o profile.stats app/main.py
python -c "import pstats; pstats.Stats('profile.stats').sort_stats('cumulative').print_stats(20)"

# py-spy 사용
pip install py-spy
py-spy top --pid $(pgrep -f vllm)
py-spy record -o profile.svg --pid $(pgrep -f vllm)
```

### 2. 네트워크 디버깅

**패킷 캡처:**
```bash
# tcpdump 사용
sudo tcpdump -i any -w capture.pcap port 8000

# Wireshark로 분석
wireshark capture.pcap
```

**HTTP 요청 분석:**
```bash
# mitmproxy 사용
pip install mitmproxy
mitmproxy -p 8080

# 클라이언트에서 프록시 설정
curl --proxy localhost:8080 http://localhost:8000/health
```

### 3. 분산 추적

**OpenTelemetry 설정:**
```python
# app/tracing.py
from opentelemetry import trace
from opentelemetry.exporter.jaeger.thrift import JaegerExporter
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor

trace.set_tracer_provider(TracerProvider())
tracer = trace.get_tracer(__name__)

jaeger_exporter = JaegerExporter(
    agent_host_name="localhost",
    agent_port=6831,
)

span_processor = BatchSpanProcessor(jaeger_exporter)
trace.get_tracer_provider().add_span_processor(span_processor)
```

## 일반적인 에러 코드 및 해결책

### HTTP 상태 코드별 대응

| 상태 코드 | 원인 | 해결 방법 |
|----------|------|-----------|
| 400 | 잘못된 요청 형식 | JSON 스키마 확인, 필수 필드 검증 |
| 401 | 인증 실패 | API 키 확인, 토큰 유효성 검증 |
| 403 | 권한 없음 | 사용자 권한 확인, RBAC 설정 검토 |
| 404 | 리소스 없음 | 엔드포인트 URL 확인, 라우팅 설정 검토 |
| 413 | 요청 크기 초과 | MAX_REQUEST_SIZE 설정 조정 |
| 429 | 요청 한도 초과 | 레이트 리미팅 설정 확인, 클라이언트 요청 간격 조정 |
| 500 | 서버 내부 오류 | 로그 확인, 예외 처리 개선 |
| 502 | 게이트웨이 오류 | 업스트림 서버 상태 확인, 로드 밸런서 설정 |
| 503 | 서비스 불가 | 서버 과부하 확인, 리소스 증설 |
| 504 | 게이트웨이 타임아웃 | 타임아웃 설정 증가, 성능 최적화 |

### vLLM 특화 오류

**텐서 관련 오류:**
```python
# RuntimeError: Expected all tensors to be on the same device
# 해결: GPU 디바이스 일관성 확인
export CUDA_VISIBLE_DEVICES=0
```

**토크나이저 오류:**
```python
# ValueError: Tokenizer not found for model
# 해결: 토크나이저 수동 다운로드
from transformers import AutoTokenizer
tokenizer = AutoTokenizer.from_pretrained(model_name, trust_remote_code=True)
```

**quantization 오류:**
```python
# RuntimeError: quantization not supported
# 해결: 지원되는 quantization 방법 사용
export QUANTIZATION="bitsandbytes"  # 또는 "gptq", "awq"
```

## 자동화된 복구 스크립트

### 서비스 자동 재시작
```bash
#!/bin/bash
# auto_restart.sh

SERVICE_NAME="vllm-api"
MAX_RETRIES=3
RETRY_COUNT=0

while [ $RETRY_COUNT -lt $MAX_RETRIES ]; do
    if ! curl -f http://localhost:8000/health > /dev/null 2>&1; then
        echo "서비스 응답 없음. 재시작 시도 $((RETRY_COUNT + 1))/$MAX_RETRIES"
        
        # Docker 환경
        if command -v docker &> /dev/null; then
            docker restart $SERVICE_NAME
        # Systemd 환경
        elif command -v systemctl &> /dev/null; then
            systemctl restart $SERVICE_NAME
        # Kubernetes 환경
        elif command -v kubectl &> /dev/null; then
            kubectl rollout restart deployment/vllm-api-deployment -n vllm-api
        fi
        
        sleep 30
        RETRY_COUNT=$((RETRY_COUNT + 1))
    else
        echo "서비스 정상 동작 확인"
        exit 0
    fi
done

echo "서비스 복구 실패. 수동 개입 필요"
exit 1
```

### 리소스 정리 스크립트
```bash
#!/bin/bash
# cleanup_resources.sh

echo "🧹 리소스 정리 시작..."

# 1. GPU 메모리 정리
echo "GPU 메모리 정리 중..."
python -c "
import torch
torch.cuda.empty_cache()
print('GPU 메모리 정리 완료')
"

# 2. 시스템 캐시 정리
echo "시스템 캐시 정리 중..."
sync
echo 3 > /proc/sys/vm/drop_caches

# 3. 임시 파일 정리
echo "임시 파일 정리 중..."
find /tmp -name "*.tmp" -mtime +1 -delete
find /var/log -name "*.log" -size +100M -exec truncate -s 50M {} \;

# 4. Docker 정리 (해당되는 경우)
if command -v docker &> /dev/null; then
    echo "Docker 리소스 정리 중..."
    docker system prune -f
    docker volume prune -f
fi

echo "✅ 리소스 정리 완료"
```

## 긴급 대응 체크리스트

### 서비스 중단 시 대응 순서

1. **즉시 확인 사항**
   - [ ] 서비스 상태 확인 (`curl http://localhost:8000/health`)
   - [ ] 프로세스 실행 상태 (`ps aux | grep vllm`)
   - [ ] 시스템 리소스 (`top`, `nvidia-smi`)
   - [ ] 로그 에러 확인 (`tail -100 logs/app.log`)

2. **1차 복구 시도 (5분 이내)**
   - [ ] 서비스 재시작
   - [ ] GPU 메모리 정리
   - [ ] 네트워크 연결 확인

3. **2차 복구 시도 (15분 이내)**
   - [ ] 컨테이너/Pod 재시작
   - [ ] 설정 파일 검증
   - [ ] 의존성 서비스 확인

4. **3차 복구 시도 (30분 이내)**
   - [ ] 백업에서 복원
   - [ ] 다른 인스턴스로 트래픽 라우팅
   - [ ] 운영팀 에스컬레이션

### 연락처 정보

- **L1 지원**: support-l1@company.com
- **L2 지원**: support-l2@company.com  
- **온콜 엔지니어**: +82-10-1234-5678
- **슬랙 채널**: #vllm-api-support

## 참고 자료

- [vLLM 공식 문서](https://docs.vllm.ai/)
- [CUDA 문제 해결 가이드](https://docs.nvidia.com/cuda/cuda-installation-guide-linux/)
- [Docker GPU 문제 해결](https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/troubleshooting.html)
- [Kubernetes 문제 해결](https://kubernetes.io/docs/tasks/debug-application-cluster/)

이 문서는 지속적으로 업데이트되며, 새로운 문제와 해결책이 발견되면 추가됩니다. 문제 해결에 도움이 필요하면 위의 연락처로 문의하세요.