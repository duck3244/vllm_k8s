"""
app/api/dependencies.py
FastAPI 의존성 주입 함수들
"""

import time
from typing import Optional
from fastapi import HTTPException, status, Request, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from app.core.config import settings
from app.core.logging import get_logger, request_logger
from app.services.vllm_engine import vllm_service
from app.services.ray_service import ray_service

logger = get_logger("dependencies")
security = HTTPBearer(auto_error=False) if settings.API_KEY_ENABLED else None

class RateLimiter:
    """간단한 메모리 기반 Rate Limiter"""
    
    def __init__(self, max_requests: int = 100, window_seconds: int = 60):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.requests = {}  # {client_ip: [request_times]}
    
    def is_allowed(self, client_ip: str) -> bool:
        """요청 허용 여부 확인"""
        current_time = time.time()
        
        # 클라이언트별 요청 기록 초기화
        if client_ip not in self.requests:
            self.requests[client_ip] = []
        
        # 윈도우 밖의 오래된 요청 제거
        self.requests[client_ip] = [
            req_time for req_time in self.requests[client_ip]
            if current_time - req_time < self.window_seconds
        ]
        
        # 요청 수 확인
        if len(self.requests[client_ip]) >= self.max_requests:
            return False
        
        # 새 요청 기록
        self.requests[client_ip].append(current_time)
        return True

# Rate Limiter 인스턴스
rate_limiter = RateLimiter(
    max_requests=settings.MAX_CONCURRENT_REQUESTS,
    window_seconds=60
)

async def get_client_ip(request: Request) -> str:
    """클라이언트 IP 주소 추출"""
    forwarded_for = request.headers.get("X-Forwarded-For")
    if forwarded_for:
        return forwarded_for.split(",")[0].strip()
    
    real_ip = request.headers.get("X-Real-IP")
    if real_ip:
        return real_ip
    
    return request.client.host if request.client else "unknown"

async def verify_api_key(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security)
) -> bool:
    """API 키 검증"""
    if not settings.API_KEY_ENABLED:
        return True
    
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="API 키가 필요합니다",
            headers={"WWW-Authenticate": "Bearer"}
        )
    
    if credentials.credentials != settings.API_KEY:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="유효하지 않은 API 키입니다",
            headers={"WWW-Authenticate": "Bearer"}
        )
    
    return True

async def check_rate_limit(
    request: Request,
    client_ip: str = Depends(get_client_ip)
) -> str:
    """Rate Limiting 검사"""
    if not rate_limiter.is_allowed(client_ip):
        logger.warning(f"Rate limit 초과 - IP: {client_ip}")
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="요청 한도를 초과했습니다. 잠시 후 다시 시도해주세요.",
            headers={"Retry-After": "60"}
        )
    
    return client_ip

async def get_vllm_service():
    """vLLM 서비스 의존성"""
    if not vllm_service._initialized:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="vLLM 서비스가 초기화되지 않았습니다"
        )
    
    return vllm_service

async def get_ray_service():
    """Ray 서비스 의존성"""
    if not ray_service.is_connected():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Ray 클러스터에 연결되지 않았습니다"
        )
    
    return ray_service

async def check_service_health():
    """서비스 상태 확인 의존성"""
    try:
        # vLLM 서비스 상태 확인
        vllm_health = await vllm_service.health_check()
        if not vllm_health.get("service_initialized", False):
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="vLLM 서비스를 사용할 수 없습니다"
            )
        
        # Ray 클러스터 상태 확인
        if not ray_service.is_connected():
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Ray 클러스터에 연결되지 않았습니다"
            )
        
        return {
            "vllm_status": vllm_health,
            "ray_connected": True
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"서비스 상태 확인 실패: {e}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="서비스 상태를 확인할 수 없습니다"
        )

class RequestLogger:
    """요청 로깅 미들웨어"""
    
    def __init__(self):
        self.start_time = None
    
    async def __call__(self, request: Request, call_next):
        """요청 처리 및 로깅"""
        self.start_time = time.time()
        client_ip = await get_client_ip(request)
        
        # 요청 로깅
        logger.debug(f"요청 시작 - {request.method} {request.url.path} - IP: {client_ip}")
        
        try:
            response = await call_next(request)
            
            # 응답 시간 계산
            process_time = time.time() - self.start_time
            
            # 요청 로깅
            request_logger.log_request(
                method=request.method,
                path=str(request.url.path),
                status_code=response.status_code,
                response_time=process_time,
                client_ip=client_ip
            )
            
            # 응답 헤더에 처리 시간 추가
            response.headers["X-Process-Time"] = str(process_time)
            
            return response
            
        except Exception as e:
            process_time = time.time() - self.start_time
            logger.error(f"요청 처리 실패 - {request.method} {request.url.path} - "
                        f"시간: {process_time:.3f}s - 오류: {e}")
            raise

async def validate_content_type(request: Request):
    """Content-Type 검증"""
    if request.method in ["POST", "PUT", "PATCH"]:
        content_type = request.headers.get("content-type", "")
        if not content_type.startswith("application/json"):
            raise HTTPException(
                status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
                detail="Content-Type은 application/json이어야 합니다"
            )

async def check_request_size(request: Request):
    """요청 크기 검증"""
    content_length = request.headers.get("content-length")
    if content_length:
        size = int(content_length)
        max_size = 10 * 1024 * 1024  # 10MB
        
        if size > max_size:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail=f"요청 크기가 너무 큽니다. 최대 {max_size} bytes"
            )

class ServiceHealthChecker:
    """서비스 헬스 체커"""
    
    def __init__(self):
        self.last_check_time = 0
        self.check_interval = 30  # 30초
        self.cached_health = None
    
    async def get_health_status(self) -> dict:
        """캐시된 헬스 상태 반환"""
        current_time = time.time()
        
        # 캐시가 만료되었거나 없는 경우 새로 확인
        if (current_time - self.last_check_time > self.check_interval or 
            self.cached_health is None):
            
            self.cached_health = await self._check_all_services()
            self.last_check_time = current_time
        
        return self.cached_health
    
    async def _check_all_services(self) -> dict:
        """모든 서비스 상태 확인"""
        health_status = {
            "timestamp": time.time(),
            "overall_status": "healthy",
            "services": {}
        }
        
        try:
            # vLLM 서비스 확인
            vllm_health = await vllm_service.health_check()
            health_status["services"]["vllm"] = vllm_health
            
            # Ray 서비스 확인
            ray_health = ray_service.get_cluster_status()
            health_status["services"]["ray"] = ray_health
            
            # 전체 상태 판단
            if (not vllm_health.get("service_initialized", False) or 
                not ray_health.get("connected", False)):
                health_status["overall_status"] = "unhealthy"
            
        except Exception as e:
            logger.error(f"헬스 체크 실패: {e}")
            health_status["overall_status"] = "unhealthy"
            health_status["error"] = str(e)
        
        return health_status

# 전역 인스턴스
service_health_checker = ServiceHealthChecker()

async def get_health_status() -> dict:
    """헬스 상태 의존성"""
    return await service_health_checker.get_health_status()

class MetricsCollector:
    """메트릭 수집 클래스"""
    
    def __init__(self):
        self.metrics = {
            "requests_total": 0,
            "requests_successful": 0,
            "requests_failed": 0,
            "tokens_generated": 0,
            "total_response_time": 0.0,
            "start_time": time.time()
        }
    
    def record_request(self, success: bool, response_time: float, tokens: int = 0):
        """요청 메트릭 기록"""
        self.metrics["requests_total"] += 1
        if success:
            self.metrics["requests_successful"] += 1
            self.metrics["tokens_generated"] += tokens
        else:
            self.metrics["requests_failed"] += 1
        
        self.metrics["total_response_time"] += response_time
    
    def get_metrics(self) -> dict:
        """메트릭 반환"""
        uptime = time.time() - self.metrics["start_time"]
        avg_response_time = (
            self.metrics["total_response_time"] / self.metrics["requests_total"] 
            if self.metrics["requests_total"] > 0 else 0
        )
        
        return {
            **self.metrics,
            "uptime": uptime,
            "average_response_time": avg_response_time,
            "requests_per_second": self.metrics["requests_total"] / uptime if uptime > 0 else 0
        }

# 메트릭 수집기 인스턴스
metrics_collector = MetricsCollector()

async def get_metrics() -> dict:
    """메트릭 의존성"""
    return metrics_collector.get_metrics()