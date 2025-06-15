# 멀티스테이지 Docker 이미지 빌드
# vLLM API 서버를 위한 최적화된 컨테이너

#============================================================================
# Stage 1: Base Python 환경 설정
#============================================================================
FROM python:3.11-slim as python-base

# 환경 변수 설정
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    POETRY_VERSION=1.7.1

# 시스템 패키지 업데이트 및 필수 도구 설치
RUN apt-get update && apt-get install -y \
    curl \
    build-essential \
    git \
    && rm -rf /var/lib/apt/lists/*

#============================================================================
# Stage 2: 의존성 설치 (개발용)
#============================================================================
FROM python-base as deps-dev

# Poetry 설치
RUN pip install poetry==$POETRY_VERSION

# 작업 디렉토리 설정
WORKDIR /app

# Poetry 설정
RUN poetry config virtualenvs.create false

# 의존성 파일 복사
COPY pyproject.toml poetry.lock* ./
COPY docker/requirements.txt ./

# 개발 의존성 포함하여 설치
RUN poetry install --with dev,test || pip install -r requirements.txt

#============================================================================
# Stage 3: 의존성 설치 (운영용)
#============================================================================
FROM python-base as deps-prod

# 최적화된 Python 패키지 설치
COPY docker/requirements.txt ./

# CUDA 지원을 위한 추가 패키지 설치
RUN apt-get update && apt-get install -y \
    nvidia-cuda-toolkit \
    && rm -rf /var/lib/apt/lists/*

# 운영용 의존성만 설치
RUN pip install --no-cache-dir -r requirements.txt

#============================================================================
# Stage 4: 개발 환경
#============================================================================
FROM deps-dev as development

# 개발용 추가 도구 설치
RUN apt-get update && apt-get install -y \
    vim \
    htop \
    tmux \
    && rm -rf /var/lib/apt/lists/*

# 작업 디렉토리 설정
WORKDIR /app

# 소스 코드 복사
COPY . .

# 권한 설정
RUN chmod +x scripts/*.sh

# 개발 서버 포트 노출
EXPOSE 8000 8001

# 헬스체크 설정
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# 개발 서버 실행
CMD ["python", "-m", "app.main", "--host", "0.0.0.0", "--port", "8000", "--reload"]

#============================================================================
# Stage 5: 운영 환경
#============================================================================
FROM deps-prod as production

# 비특권 사용자 생성
RUN groupadd -r appuser && useradd -r -g appuser appuser

# 작업 디렉토리 설정
WORKDIR /app

# 소스 코드 복사 (불필요한 파일 제외)
COPY --chown=appuser:appuser app/ ./app/
COPY --chown=appuser:appuser scripts/ ./scripts/
COPY --chown=appuser:appuser config/ ./config/
COPY --chown=appuser:appuser pyproject.toml ./

# 실행 권한 설정
RUN chmod +x scripts/*.sh

# 로그 디렉토리 생성
RUN mkdir -p /app/logs && chown -R appuser:appuser /app/logs

# 포트 노출
EXPOSE 8000

# 헬스체크 설정
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# 사용자 전환
USER appuser

# 운영 서버 실행
CMD ["python", "-m", "app.main", "--host", "0.0.0.0", "--port", "8000"]

#============================================================================
# Stage 6: GPU 지원 운영 환경
#============================================================================
FROM nvidia/cuda:12.1-devel-ubuntu22.04 as gpu-production

# Python 3.11 설치
RUN apt-get update && apt-get install -y \
    python3.11 \
    python3.11-pip \
    python3.11-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Python 심볼릭 링크 설정
RUN ln -s /usr/bin/python3.11 /usr/bin/python

# 작업 디렉토리 설정
WORKDIR /app

# requirements 복사 및 설치
COPY docker/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# vLLM GPU 버전 설치
RUN pip install vllm[cuda]

# 비특권 사용자 생성
RUN groupadd -r appuser && useradd -r -g appuser appuser

# 소스 코드 복사
COPY --chown=appuser:appuser app/ ./app/
COPY --chown=appuser:appuser scripts/ ./scripts/
COPY --chown=appuser:appuser config/ ./config/
COPY --chown=appuser:appuser pyproject.toml ./

# 실행 권한 설정
RUN chmod +x scripts/*.sh

# 로그 디렉토리 생성
RUN mkdir -p /app/logs && chown -R appuser:appuser /app/logs

# 포트 노출
EXPOSE 8000

# GPU 헬스체크 설정
HEALTHCHECK --interval=30s --timeout=10s --start-period=120s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# 사용자 전환
USER appuser

# GPU 서버 실행
CMD ["python", "-m", "app.main", "--host", "0.0.0.0", "--port", "8000", "--gpu"]

#============================================================================
# Stage 7: 테스트 환경
#============================================================================
FROM deps-dev as testing

# 테스트 도구 추가 설치
RUN pip install pytest-xdist pytest-benchmark

# 작업 디렉토리 설정
WORKDIR /app

# 전체 소스 코드 복사
COPY . .

# 테스트 실행 권한 설정
RUN chmod +x tests/run_tests.py

# 테스트 포트 노출
EXPOSE 8000 8001 8002

# 테스트 실행
CMD ["python", "tests/run_tests.py", "--type", "all", "--coverage"]