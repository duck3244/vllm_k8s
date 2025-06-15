# 🚀 vLLM API Server

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.104.1-green.svg)](https://fastapi.tiangolo.com/)
[![vLLM](https://img.shields.io/badge/vLLM-0.2.5-orange.svg)](https://github.com/vllm-project/vllm)
[![Docker](https://img.shields.io/badge/docker-ready-blue.svg)](https://www.docker.com/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

**고성능 대용량 언어 모델 API 서버**

vLLM을 기반으로 한 확장 가능하고 고성능인 언어 모델 API 서버입니다. FastAPI를 사용하여 구축되었으며, 운영 환경에서 안정적으로 대용량 언어 모델을 서빙할 수 있도록 설계되었습니다.

## ✨ 주요 기능

### 🔥 **핵심 기능**
- **고성능 모델 서빙**: vLLM을 통한 최적화된 추론 성능
- **비동기 처리**: 동시 다중 요청 처리 및 스트리밍 응답
- **다중 모델 지원**: 여러 모델 동시 로드 및 관리
- **GPU 가속**: CUDA 지원 및 텐서 병렬화
- **배치 처리**: 효율적인 배치 추론 및 큐 관리

### 🛡️ **운영 기능**
- **인증 및 보안**: JWT 토큰 기반 인증 시스템
- **Rate Limiting**: API 사용량 제한 및 제어
- **모니터링**: Prometheus 메트릭스 및 헬스체크
- **로깅**: 구조화된 로깅 및 추적
- **캐싱**: Redis를 통한 응답 캐싱

### 🔧 **개발 지원**
- **자동 문서화**: Swagger UI 및 ReDoc
- **테스트 완비**: 단위/통합/성능 테스트
- **컨테이너화**: Docker 및 Kubernetes 지원
- **CI/CD**: GitHub Actions 워크플로우

## 🏗️ 아키텍처

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Load Balancer │    │   API Gateway   │    │   Monitoring    │
│    (Nginx)      │    │   (FastAPI)     │    │ (Prometheus)    │
└─────────────────┘    └─────────────────┘    └─────────────────┘
         │                       │                       │
         └───────────────────────┼───────────────────────┘
                                 │
                    ┌─────────────────┐
                    │   vLLM Engine   │
                    │   (GPU/CPU)     │
                    └─────────────────┘
                                 │
                    ┌─────────────────┐
                    │     Redis       │
                    │   (Caching)     │
                    └─────────────────┘
```

## 🚀 빠른 시작

### 1️⃣ **환경 설정**

```bash
# 리포지토리 클론
git clone https://github.com/your-org/vllm-api-server.git
cd vllm-api-server

# 환경 변수 설정
cp .env.example .env
# .env 파일을 편집하여 설정값을 수정하세요

# 의존성 설치
pip install -r requirements.txt
```

### 2️⃣ **개발 서버 실행**

```bash
# 개발 서버 시작
python -m app.main --reload

# 또는 uvicorn 직접 사용
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### 3️⃣ **Docker로 실행**

```bash
# 개발 환경
docker-compose up -d

# 운영 환경
docker-compose -f docker-compose.prod.yml up -d

# GPU 지원 환경
docker-compose -f docker-compose.gpu.yml up -d
```

### 4️⃣ **API 테스트**

```bash
# 헬스체크
curl http://localhost:8000/health

# 채팅 완성
curl -X POST "http://localhost:8000/v1/chat/completions" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "gpt-3.5-turbo",
    "messages": [{"role": "user", "content": "Hello!"}],
    "max_tokens": 100
  }'
```

## 📚 API 문서

### 🔗 **엔드포인트**

| 엔드포인트 | 설명 | 문서 |
|-----------|------|------|
| `/v1/chat/completions` | 채팅 완성 | [OpenAI 호환] |
| `/v1/completions` | 텍스트 완성 | [OpenAI 호환] |
| `/v1/embeddings` | 텍스트 임베딩 | [OpenAI 호환] |
| `/v1/models` | 모델 목록 | [OpenAI 호환] |
| `/health` | 헬스체크 | [내부 API] |
| `/metrics` | Prometheus 메트릭스 | [모니터링] |

### 📖 **인터랙티브 문서**

서버 실행 후 다음 URL에서 API 문서를 확인할 수 있습니다:

- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc
- **OpenAPI 스키마**: http://localhost:8000/openapi.json

## ⚙️ 설정

### 🔧 **환경 변수**

주요 환경 변수들:

```bash
# 모델 설정
MODEL_NAME="microsoft/DialoGPT-medium"
MAX_MODEL_LEN=2048
GPU_MEMORY_UTILIZATION=0.9

# 서버 설정
HOST="0.0.0.0"
PORT=8000
WORKERS=1

# 데이터베이스
DATABASE_URL="postgresql://user:pass@localhost:5432/vllm_api"
REDIS_URL="redis://localhost:6379/0"

# 보안
SECRET_KEY="your-secret-key"
API_KEY="your-api-key"
```

전체 설정 옵션은 `.env.example` 파일을 참고하세요.

### 🎛️ **고급 설정**

```yaml
# config/production.yml
model:
  name: "microsoft/DialoGPT-large"
  tensor_parallel_size: 2
  pipeline_parallel_size: 1
  max_model_len: 4096
  
server:
  workers: 4
  timeout: 300
  
cache:
  enabled: true
  ttl: 3600
  
monitoring:
  metrics_enabled: true
  tracing_enabled: true
```

## 🧪 테스트

### 🔬 **테스트 실행**

```bash
# 전체 테스트 실행
python tests/run_tests.py

# 특정 테스트 타입 실행
python tests/run_tests.py --type unit
python tests/run_tests.py --type integration
python tests/run_tests.py --type performance

# 커버리지 포함 테스트
python tests/run_tests.py --type coverage

# 특정 테스트 파일 실행
python tests/run_tests.py --file tests/test_api.py
```

### 📊 **코드 품질**

```bash
# 린팅 실행
python tests/run_tests.py --lint

# 포매팅 체크
python tests/run_tests.py --format

# 포매팅 자동 수정
python tests/run_tests.py --fix-format
```

## 🚀 배포

### 🐳 **Docker 배포**

```bash
# 프로덕션 이미지 빌드
docker build --target production -t vllm-api:latest .

# 컨테이너 실행
docker run -d \
  --name vllm-api \
  --gpus all \
  -p 8000:8000 \
  -v $(pwd)/models:/app/models \
  -v $(pwd)/logs:/app/logs \
  --env-file .env \
  vllm-api:latest
```

### ☸️ **Kubernetes 배포**

```bash
# Helm 차트 설치
helm install vllm-api ./charts/vllm-api \
  --namespace vllm \
  --create-namespace \
  --values values.prod.yaml

# 직접 배포
kubectl apply -f k8s/
```

### 🌐 **클라우드 배포**

#### AWS ECS
```bash
# ECS 태스크 정의 배포
aws ecs register-task-definition --cli-input-json file://ecs-task-definition.json

# ECS 서비스 업데이트
aws ecs update-service \
  --cluster vllm-cluster \
  --service vllm-api-service \
  --task-definition vllm-api:latest
```

#### Google Cloud Run
```bash
# Cloud Run 배포
gcloud run deploy vllm-api \
  --image gcr.io/your-project/vllm-api:latest \
  --platform managed \
  --region us-central1 \
  --allow-unauthenticated \
  --memory 8Gi \
  --cpu 4
```

#### Azure Container Instances
```bash
# Azure 컨테이너 인스턴스 배포
az container create \
  --resource-group vllm-rg \
  --name vllm-api \
  --image your-registry.azurecr.io/vllm-api:latest \
  --cpu 4 \
  --memory 8 \
  --ports 8000
```

## 📊 모니터링 및 관찰성

### 📈 **메트릭스**

서버는 다음 메트릭스를 제공합니다:

```prometheus
# 요청 관련
http_requests_total{method, path, status}
http_request_duration_seconds{method, path}
http_requests_in_progress{method, path}

# 모델 관련
model_inference_duration_seconds{model_name}
model_queue_size{model_name}
model_active_requests{model_name}
gpu_memory_usage_bytes{device}

# 시스템 관련
process_cpu_usage_percent
process_memory_usage_bytes
```

### 🔍 **로깅**

구조화된 JSON 로깅 예시:

```json
{
  "timestamp": "2024-01-15T10:30:00Z",
  "level": "INFO",
  "logger": "app.api.chat",
  "message": "Chat completion request",
  "request_id": "req_123456",
  "model": "gpt-3.5-turbo",
  "tokens": 150,
  "duration_ms": 1250,
  "user_id": "user_789"
}
```

### 📊 **대시보드**

Grafana 대시보드 예시:

- **시스템 상태**: CPU, 메모리, GPU 사용률
- **API 성능**: 응답 시간, 처리량, 오류율
- **모델 메트릭스**: 추론 시간, 큐 상태, 토큰 처리량
- **비즈니스 메트릭스**: 사용자 활동, 비용 추적

## 🔧 개발 가이드

### 📝 **코드 스타일**

프로젝트는 다음 코드 스타일을 따릅니다:

```bash
# 코드 포매팅
black app/ tests/ --line-length 100
isort app/ tests/

# 린팅
flake8 app/ tests/ --max-line-length=100
mypy app/ --strict
```

### 🔀 **Git 워크플로우**

```bash
# 기능 브랜치 생성
git checkout -b feature/new-endpoint

# 커밋 메시지 컨벤션
git commit -m "feat: add streaming response support"
git commit -m "fix: resolve memory leak in model loading"
git commit -m "docs: update API documentation"

# 풀 리퀘스트 생성
gh pr create --title "Add streaming response support" --body "..."
```

### 🧪 **테스트 작성**

```python
# tests/test_api.py
import pytest
from httpx import AsyncClient

@pytest.mark.asyncio
async def test_chat_completion(client: AsyncClient):
    response = await client.post(
        "/v1/chat/completions",
        json={
            "model": "test-model",
            "messages": [{"role": "user", "content": "Hello"}],
            "max_tokens": 10
        }
    )
    assert response.status_code == 200
    data = response.json()
    assert "choices" in data
    assert len(data["choices"]) > 0
```

## 🔐 보안

### 🛡️ **보안 체크리스트**

- [ ] API 키 인증 구현
- [ ] HTTPS 강제 사용
- [ ] Rate limiting 설정
- [ ] 입력 유효성 검사
- [ ] 에러 정보 최소화
- [ ] 로그에서 민감한 정보 제거
- [ ] 정기적인 의존성 업데이트
- [ ] 보안 헤더 설정

### 🔑 **인증 예시**

```bash
# API 키 사용
curl -X POST "http://localhost:8000/v1/chat/completions" \
  -H "Authorization: Bearer your-api-key" \
  -H "Content-Type: application/json" \
  -d '{"model": "gpt-3.5-turbo", "messages": [...]}'

# JWT 토큰 사용
curl -X POST "http://localhost:8000/v1/chat/completions" \
  -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIs..." \
  -H "Content-Type: application/json" \
  -d '{"model": "gpt-3.5-turbo", "messages": [...]}'
```

## 🚨 문제 해결

### ❓ **자주 묻는 질문**

**Q: GPU 메모리 부족 오류가 발생합니다.**
```bash
# GPU 메모리 사용률 조정
export GPU_MEMORY_UTILIZATION=0.8

# 모델 길이 제한
export MAX_MODEL_LEN=2048

# 배치 크기 감소
export MAX_NUM_SEQS=128
```

**Q: 응답 속도가 느립니다.**
```bash
# 텐서 병렬화 활성화
export TENSOR_PARALLEL_SIZE=2

# 캐싱 활성화
export CACHE_TTL_DEFAULT=1800

# 배치 처리 최적화
export MAX_BATCH_SIZE=64
```

**Q: 메모리 누수가 발생합니다.**
```python
# 모델 명시적 해제
await model_manager.unload_model("model-name")

# 가비지 컬렉션 강제 실행
import gc
gc.collect()
```

### 🐛 **디버깅**

```bash
# 디버그 모드 실행
export DEBUG=true
export LOG_LEVEL=DEBUG

# 프로파일링 활성화
export PROFILE_ENABLED=true

# 상세 로그 확인
tail -f logs/app.log | grep ERROR
```

## 🤝 기여하기

### 👥 **기여 방법**

1. **이슈 생성**: 버그 리포트나 기능 요청
2. **포크**: 프로젝트를 포크하여 작업
3. **브랜치**: 기능별 브랜치 생성
4. **테스트**: 변경사항에 대한 테스트 작성
5. **풀 리퀘스트**: 상세한 설명과 함께 PR 생성

### 📋 **개발 환경 설정**

```bash
# 개발 의존성 설치
pip install -e ".[dev]"

# pre-commit 훅 설정
pre-commit install

# 테스트 환경 확인
python tests/run_tests.py --check-deps
```

### 🎯 **기여 가이드라인**

- 코드 스타일 가이드 준수
- 모든 테스트 통과 확인
- 문서 업데이트
- 커밋 메시지 컨벤션 따르기
- 리뷰어 피드백 적극 반영

## 📄 라이선스

이 프로젝트는 MIT 라이선스 하에 배포됩니다. 자세한 내용은 [LICENSE](LICENSE) 파일을 참조하세요.

---

⭐ **이 프로젝트가 도움이 되었다면 Star를 눌러주세요!**

**Made with ❤️ by the vLLM API Server Team**
