"""
app/main.py
메인 FastAPI 애플리케이션
"""

import asyncio
import signal
import sys
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException
import uvicorn

from app.core.config import settings
from app.core.logging import (
    logger, log_api_startup, log_api_shutdown, log_system_info,
    log_error_with_context
)
from app.api.routes import router
from app.services.vllm_engine import vllm_service
from app.services.ray_service import ray_service
from app.services.model_monitor import model_monitor_service
from app.api.dependencies import RequestLogger

class GracefulKiller:
    """Graceful shutdown 핸들러"""
    
    def __init__(self):
        self.kill_now = False
        signal.signal(signal.SIGINT, self._exit_gracefully)
        signal.signal(signal.SIGTERM, self._exit_gracefully)
    
    def _exit_gracefully(self, signum, frame):
        logger.info(f"종료 신호 받음: {signum}")
        self.kill_now = True

@asynccontextmanager
async def lifespan(app: FastAPI):
    """애플리케이션 라이프사이클 관리"""
    # 시작 시 초기화
    logger.info("🚀 vLLM API 서버 시작 중...")
    
    try:
        # 시스템 정보 로깅
        log_system_info()
        
        # Ray 클러스터 연결
        logger.info("Ray 클러스터 연결 중...")
        if not ray_service.initialize():
            raise RuntimeError("Ray 클러스터 연결 실패")
        logger.info("✅ Ray 클러스터 연결 완료")
        
        # vLLM 서비스 초기화
        logger.info("vLLM 서비스 초기화 중...")
        vllm_service.initialize()
        logger.info("✅ vLLM 서비스 초기화 완료")
        
        # 모델 모니터링 시작
        logger.info("모델 모니터링 시작 중...")
        await model_monitor_service.start_monitoring(vllm_service, interval=60)
        logger.info("✅ 모델 모니터링 시작 완료")
        
        # 시작 로그
        log_api_startup()
        
        yield
        
    except Exception as e:
        log_error_with_context(e, {"component": "startup"})
        logger.error("서비스 초기화 실패")
        sys.exit(1)
    
    # 종료 시 정리
    logger.info("🛑 vLLM API 서버 종료 중...")
    
    try:
        # 모델 모니터링 중지
        logger.info("모델 모니터링 중지 중...")
        await model_monitor_service.stop_monitoring()
        
        # vLLM 서비스 종료
        logger.info("vLLM 서비스 종료 중...")
        vllm_service.shutdown()
        
        # Ray 서비스 종료
        logger.info("Ray 서비스 종료 중...")
        ray_service.shutdown()
        
        # 종료 로그
        log_api_shutdown()
        
    except Exception as e:
        log_error_with_context(e, {"component": "shutdown"})

# FastAPI 애플리케이션 생성
app = FastAPI(
    title=settings.APP_NAME,
    description=settings.APP_DESCRIPTION,
    version=settings.APP_VERSION,
    lifespan=lifespan,
    docs_url="/docs" if settings.DEBUG else None,
    redoc_url="/redoc" if settings.DEBUG else None,
    openapi_url="/openapi.json" if settings.DEBUG else None
)

# 미들웨어 설정
if settings.CORS_ORIGINS:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

# Gzip 압축 미들웨어
app.add_middleware(GZipMiddleware, minimum_size=1000)

# 요청 로깅 미들웨어
request_logger_middleware = RequestLogger()
app.middleware("http")(request_logger_middleware)

# 글로벌 예외 처리기
@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    """HTTP 예외 처리"""
    logger.warning(f"HTTP 예외: {exc.status_code} - {exc.detail} - {request.url}")
    
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": "HTTPException",
            "message": exc.detail,
            "status_code": exc.status_code,
            "path": str(request.url.path)
        }
    )

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """요청 검증 예외 처리"""
    logger.warning(f"검증 오류: {exc.errors()} - {request.url}")
    
    return JSONResponse(
        status_code=422,
        content={
            "error": "ValidationError",
            "message": "요청 데이터가 유효하지 않습니다",
            "details": exc.errors(),
            "path": str(request.url.path)
        }
    )

@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    """일반 예외 처리"""
    log_error_with_context(exc, {
        "path": str(request.url.path),
        "method": request.method,
        "client": request.client.host if request.client else "unknown"
    })
    
    return JSONResponse(
        status_code=500,
        content={
            "error": "InternalServerError",
            "message": "내부 서버 오류가 발생했습니다",
            "detail": str(exc) if settings.DEBUG else "서버 로그를 확인하세요"
        }
    )

# 헬스체크 미들웨어
@app.middleware("http")
async def health_check_middleware(request: Request, call_next):
    """헬스체크 요청은 빠르게 처리"""
    if request.url.path == settings.HEALTH_CHECK_PATH:
        # 간단한 헬스체크 (미들웨어 레벨)
        try:
            response = await call_next(request)
            return response
        except Exception as e:
            logger.error(f"헬스체크 오류: {e}")
            return JSONResponse(
                status_code=503,
                content={
                    "status": "unhealthy",
                    "error": str(e)
                }
            )
    
    return await call_next(request)

# 보안 헤더 미들웨어
@app.middleware("http")
async def security_headers_middleware(request: Request, call_next):
    """보안 헤더 추가"""
    response = await call_next(request)
    
    # 보안 헤더 추가
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    
    if not settings.DEBUG:
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    
    return response

# 라우터 등록
app.include_router(router, prefix=settings.API_PREFIX)

# 루트 엔드포인트
@app.get("/")
async def root():
    """루트 엔드포인트"""
    return {
        "message": f"🤖 {settings.APP_NAME}",
        "version": settings.APP_VERSION,
        "status": "running",
        "model": settings.MODEL_NAME,
        "endpoints": {
            "docs": "/docs" if settings.DEBUG else "disabled",
            "health": settings.HEALTH_CHECK_PATH,
            "api": settings.API_PREFIX
        }
    }

# 상태 엔드포인트 (간단한 헬스체크)
@app.get(settings.HEALTH_CHECK_PATH)
async def simple_health():
    """간단한 헬스체크"""
    return {
        "status": "ok",
        "timestamp": asyncio.get_event_loop().time(),
        "service": settings.APP_NAME,
        "version": settings.APP_VERSION
    }

# 메트릭 엔드포인트 (Prometheus 형식)
@app.get(settings.METRICS_PATH)
async def metrics():
    """Prometheus 메트릭 엔드포인트"""
    if not settings.METRICS_ENABLED:
        return JSONResponse(
            status_code=404,
            content={"error": "Metrics disabled"}
        )
    
    try:
        from app.api.dependencies import metrics_collector
        metrics_data = metrics_collector.get_metrics()
        
        # Prometheus 형식으로 메트릭 반환
        prometheus_metrics = []
        
        prometheus_metrics.append(f"# HELP vllm_requests_total Total number of requests")
        prometheus_metrics.append(f"# TYPE vllm_requests_total counter")
        prometheus_metrics.append(f"vllm_requests_total {metrics_data.get('requests_total', 0)}")
        
        prometheus_metrics.append(f"# HELP vllm_requests_successful_total Total number of successful requests")
        prometheus_metrics.append(f"# TYPE vllm_requests_successful_total counter")
        prometheus_metrics.append(f"vllm_requests_successful_total {metrics_data.get('requests_successful', 0)}")
        
        prometheus_metrics.append(f"# HELP vllm_requests_failed_total Total number of failed requests")
        prometheus_metrics.append(f"# TYPE vllm_requests_failed_total counter")
        prometheus_metrics.append(f"vllm_requests_failed_total {metrics_data.get('requests_failed', 0)}")
        
        prometheus_metrics.append(f"# HELP vllm_tokens_generated_total Total number of tokens generated")
        prometheus_metrics.append(f"# TYPE vllm_tokens_generated_total counter")
        prometheus_metrics.append(f"vllm_tokens_generated_total {metrics_data.get('tokens_generated', 0)}")
        
        prometheus_metrics.append(f"# HELP vllm_response_time_seconds Average response time")
        prometheus_metrics.append(f"# TYPE vllm_response_time_seconds gauge")
        prometheus_metrics.append(f"vllm_response_time_seconds {metrics_data.get('average_response_time', 0)}")
        
        prometheus_metrics.append(f"# HELP vllm_uptime_seconds Service uptime")
        prometheus_metrics.append(f"# TYPE vllm_uptime_seconds gauge")
        prometheus_metrics.append(f"vllm_uptime_seconds {metrics_data.get('uptime', 0)}")
        
        return Response(
            content="\n".join(prometheus_metrics),
            media_type="text/plain"
        )
        
    except Exception as e:
        logger.error(f"메트릭 조회 실패: {e}")
        return JSONResponse(
            status_code=500,
            content={"error": "Failed to collect metrics"}
        )

# 개발 서버 실행 함수
def run_server():
    """개발 서버 실행"""
    uvicorn.run(
        "app.main:app",
        host=settings.API_HOST,
        port=settings.API_PORT,
        workers=settings.API_WORKERS,
        reload=settings.DEBUG,
        log_level=settings.LOG_LEVEL.lower(),
        access_log=True
    )

# 프로덕션 서버 실행 함수
async def run_server_async():
    """비동기 서버 실행"""
    config = uvicorn.Config(
        "app.main:app",
        host=settings.API_HOST,
        port=settings.API_PORT,
        workers=settings.API_WORKERS,
        log_level=settings.LOG_LEVEL.lower(),
        access_log=True
    )
    
    server = uvicorn.Server(config)
    
    # Graceful shutdown 설정
    killer = GracefulKiller()
    
    try:
        # 서버 시작
        await server.serve()
        
        # Graceful shutdown 대기
        while not killer.kill_now:
            await asyncio.sleep(1)
            
    except KeyboardInterrupt:
        logger.info("키보드 인터럽트로 서버 종료")
    finally:
        logger.info("서버 종료 중...")
        await server.shutdown()

if __name__ == "__main__":
    # 직접 실행 시
    if len(sys.argv) > 1 and sys.argv[1] == "--async":
        # 비동기 실행
        asyncio.run(run_server_async())
    else:
        # 동기 실행 (개발용)
        run_server()