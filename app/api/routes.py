"""
app/api/routes.py
FastAPI 라우터 및 엔드포인트 정의
"""

import time
import asyncio
from typing import List, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from fastapi.responses import StreamingResponse
from sse_starlette.sse import EventSourceResponse

from app.core.config import settings
from app.core.logging import get_logger, request_logger
from app.models.schemas import (
    GenerateRequest, GenerateResponse, BatchGenerateRequest, BatchGenerateResponse,
    HealthResponse, ModelInfo, ErrorResponse, UsageStats, StreamResponse,
    ModelStatusResponse, ModelHealthCheckRequest, ModelHealthCheckResponse,
    SystemMetricsResponse, ModelHistoricalDataResponse
)
from app.services.vllm_engine import vllm_service
from app.services.ray_service import ray_service
from app.services.model_monitor import model_monitor_service, model_health_checker
from app.api.dependencies import (
    get_vllm_service, get_ray_service, check_service_health,
    verify_api_key, check_rate_limit, get_health_status, get_metrics,
    metrics_collector
)

logger = get_logger("api_routes")
router = APIRouter()

@router.post(
    "/generate",
    response_model=GenerateResponse,
    summary="텍스트 생성",
    description="단일 프롬프트에 대한 텍스트 생성",
    responses={
        200: {"description": "성공적으로 텍스트를 생성함"},
        400: {"model": ErrorResponse, "description": "잘못된 요청"},
        429: {"model": ErrorResponse, "description": "Rate limit 초과"},
        503: {"model": ErrorResponse, "description": "서비스 사용 불가"}
    }
)
async def generate_text(
    request: GenerateRequest,
    background_tasks: BackgroundTasks,
    _: bool = Depends(verify_api_key),
    client_ip: str = Depends(check_rate_limit),
    service = Depends(get_vllm_service)
):
    """텍스트 생성 API"""
    start_time = time.time()
    
    try:
        logger.info(f"텍스트 생성 요청 - IP: {client_ip}, 프롬프트 길이: {len(request.prompt)}")
        
        # 텍스트 생성 실행
        result = await service.generate(request)
        
        # 응답 생성
        response = GenerateResponse(
            text=result["text"],
            prompt=result["prompt"],
            tokens_generated=result["tokens_generated"],
            prompt_tokens=result["prompt_tokens"],
            total_tokens=result["total_tokens"],
            finish_reason=result["finish_reason"],
            generation_time=result["generation_time"],
            tokens_per_second=result["tokens_per_second"],
            model_name=result["model_name"],
            request_id=result.get("request_id")
        )
        
        # 성능 로깅
        request_logger.log_generation(
            prompt_length=len(request.prompt),
            generated_tokens=result["tokens_generated"],
            total_time=result["generation_time"],
            tokens_per_second=result["tokens_per_second"]
        )
        
        # 백그라운드에서 메트릭 기록
        background_tasks.add_task(
            metrics_collector.record_request,
            success=True,
            response_time=time.time() - start_time,
            tokens=result["tokens_generated"]
        )
        
        # 모델 헬스 체커에도 메트릭 기록
        background_tasks.add_task(
            model_health_checker.record_request_metrics,
            response_time=result["generation_time"],
            success=True,
            tokens_generated=result["tokens_generated"]
        )
        
        return response
        
    except Exception as e:
        # 오류 메트릭 기록
        background_tasks.add_task(
            metrics_collector.record_request,
            success=False,
            response_time=time.time() - start_time
        )
        
        # 모델 헬스 체커에도 실패 기록
        background_tasks.add_task(
            model_health_checker.record_request_metrics,
            response_time=time.time() - start_time,
            success=False
        )
        
        logger.error(f"텍스트 생성 실패 - IP: {client_ip}, 오류: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"텍스트 생성 중 오류가 발생했습니다: {str(e)}"
        )

@router.post(
    "/generate/stream",
    summary="스트리밍 텍스트 생성",
    description="실시간 스트리밍으로 텍스트 생성",
    response_class=EventSourceResponse
)
async def generate_stream(
    request: GenerateRequest,
    _: bool = Depends(verify_api_key),
    client_ip: str = Depends(check_rate_limit),
    service = Depends(get_vllm_service)
):
    """스트리밍 텍스트 생성 API"""
    
    async def generate_stream_events():
        """스트리밍 이벤트 생성기"""
        try:
            logger.info(f"스트리밍 생성 요청 - IP: {client_ip}, 프롬프트 길이: {len(request.prompt)}")
            
            async for chunk in service.generate_stream(request):
                # SSE 형식으로 데이터 전송
                stream_response = StreamResponse(
                    text=chunk["text"],
                    is_finished=chunk["is_finished"],
                    finish_reason=chunk.get("finish_reason"),
                    tokens_generated=chunk["tokens_generated"]
                )
                
                yield {
                    "event": "message",
                    "data": stream_response.json()
                }
                
                if chunk["is_finished"]:
                    yield {
                        "event": "done",
                        "data": "[DONE]"
                    }
                    break
                    
        except Exception as e:
            logger.error(f"스트리밍 생성 실패 - IP: {client_ip}, 오류: {e}")
            yield {
                "event": "error",
                "data": f"오류 발생: {str(e)}"
            }
    
    return EventSourceResponse(generate_stream_events())

@router.post(
    "/generate/batch",
    response_model=BatchGenerateResponse,
    summary="배치 텍스트 생성",
    description="여러 프롬프트에 대한 배치 텍스트 생성"
)
async def generate_batch(
    request: BatchGenerateRequest,
    background_tasks: BackgroundTasks,
    _: bool = Depends(verify_api_key),
    client_ip: str = Depends(check_rate_limit),
    service = Depends(get_vllm_service)
):
    """배치 텍스트 생성 API"""
    start_time = time.time()
    
    try:
        logger.info(f"배치 생성 요청 - IP: {client_ip}, 프롬프트 수: {len(request.prompts)}")
        
        # 개별 요청으로 변환
        generate_requests = []
        for prompt in request.prompts:
            gen_request = GenerateRequest(
                prompt=prompt,
                max_tokens=request.max_tokens,
                temperature=request.temperature,
                top_p=request.top_p,
                top_k=request.top_k,
                repetition_penalty=request.repetition_penalty,
                stop=request.stop
            )
            generate_requests.append(gen_request)
        
        # 배치 생성 실행
        results = await service.generate_batch(generate_requests)
        
        # 응답 변환
        responses = []
        total_tokens = 0
        
        for result in results:
            if isinstance(result, dict) and "error" not in result:
                response = GenerateResponse(
                    text=result["text"],
                    prompt=result["prompt"],
                    tokens_generated=result["tokens_generated"],
                    prompt_tokens=result["prompt_tokens"],
                    total_tokens=result["total_tokens"],
                    finish_reason=result["finish_reason"],
                    generation_time=result["generation_time"],
                    tokens_per_second=result["tokens_per_second"],
                    model_name=result["model_name"],
                    request_id=result.get("request_id")
                )
                responses.append(response)
                total_tokens += result["tokens_generated"]
            else:
                # 오류 발생한 경우 기본값으로 응답 생성
                error_response = GenerateResponse(
                    text="",
                    prompt="",
                    tokens_generated=0,
                    prompt_tokens=0,
                    total_tokens=0,
                    finish_reason="error",
                    generation_time=0,
                    tokens_per_second=0,
                    model_name=settings.MODEL_NAME
                )
                responses.append(error_response)
        
        total_time = time.time() - start_time
        
        # 백그라운드에서 메트릭 기록
        background_tasks.add_task(
            metrics_collector.record_request,
            success=True,
            response_time=total_time,
            tokens=total_tokens
        )
        
        return BatchGenerateResponse(
            responses=responses,
            total_time=total_time,
            request_count=len(request.prompts)
        )
        
    except Exception as e:
        # 오류 메트릭 기록
        background_tasks.add_task(
            metrics_collector.record_request,
            success=False,
            response_time=time.time() - start_time
        )
        
        logger.error(f"배치 생성 실패 - IP: {client_ip}, 오류: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"배치 텍스트 생성 중 오류가 발생했습니다: {str(e)}"
        )

@router.get(
    "/health",
    response_model=HealthResponse,
    summary="헬스체크",
    description="서비스 상태 확인"
)
async def health_check():
    """헬스체크 API"""
    try:
        # 전체 헬스 상태 조회
        health_status = await get_health_status()
        
        # vLLM 상태
        vllm_status = health_status.get("services", {}).get("vllm", {})
        model_loaded = vllm_status.get("service_initialized", False)
        
        # Ray 상태
        ray_status = health_status.get("services", {}).get("ray", {})
        ray_connected = ray_status.get("connected", False)
        
        # GPU 상태 확인
        import torch
        gpu_available = torch.cuda.is_available()
        
        # 메트릭 정보
        metrics = await get_metrics()
        
        # GPU 메모리 정보
        gpu_memory_used = None
        if gpu_available:
            try:
                torch.cuda.synchronize()
                gpu_memory_used = torch.cuda.memory_allocated(0) / torch.cuda.max_memory_allocated(0) * 100
            except:
                pass
        
        return HealthResponse(
            status="healthy" if health_status.get("overall_status") == "healthy" else "unhealthy",
            model_loaded=model_loaded,
            ray_connected=ray_connected,
            gpu_available=gpu_available,
            version=settings.APP_VERSION,
            model_name=settings.MODEL_NAME,
            uptime=metrics.get("uptime", 0),
            total_requests=metrics.get("requests_total", 0),
            active_requests=0,  # 현재 활성 요청 수는 별도 구현 필요
            gpu_memory_used=gpu_memory_used
        )
        
    except Exception as e:
        logger.error(f"헬스체크 실패: {e}")
        return HealthResponse(
            status="unhealthy",
            model_loaded=False,
            ray_connected=False,
            gpu_available=False,
            version=settings.APP_VERSION,
            model_name=settings.MODEL_NAME,
            uptime=0,
            total_requests=0,
            active_requests=0
        )

@router.get(
    "/model-info",
    response_model=ModelInfo,
    summary="모델 정보",
    description="로딩된 모델 정보 조회"
)
async def get_model_info(service = Depends(get_vllm_service)):
    """모델 정보 조회 API"""
    try:
        model_info = service.get_model_info()
        if not model_info:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="모델 정보를 조회할 수 없습니다"
            )
        
        return ModelInfo(
            model_name=model_info.get("model_name", settings.MODEL_NAME),
            model_path=model_info.get("model_path", settings.MODEL_PATH),
            model_type=settings.MODEL_TYPE,
            tensor_parallel_size=model_info.get("tensor_parallel_size", settings.TENSOR_PARALLEL_SIZE),
            gpu_memory_utilization=model_info.get("gpu_memory_utilization", settings.GPU_MEMORY_UTILIZATION),
            max_model_len=model_info.get("max_model_len", settings.MAX_MODEL_LEN),
            dtype=model_info.get("dtype", settings.DTYPE),
            loaded_at=model_info.get("initialized_at", time.time()),
            parameters=None  # 모델 파라미터 수는 별도 구현 필요
        )
        
    except Exception as e:
        logger.error(f"모델 정보 조회 실패: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"모델 정보 조회 중 오류가 발생했습니다: {str(e)}"
        )

@router.get(
    "/stats",
    response_model=UsageStats,
    summary="사용 통계",
    description="API 사용 통계 조회"
)
async def get_usage_stats(service = Depends(get_vllm_service)):
    """사용 통계 조회 API"""
    try:
        # 메트릭 정보
        metrics = await get_metrics()
        
        # vLLM 통계
        vllm_stats = service.get_stats()
        
        return UsageStats(
            total_requests=metrics.get("requests_total", 0),
            successful_requests=metrics.get("requests_successful", 0),
            failed_requests=metrics.get("requests_failed", 0),
            total_tokens_generated=vllm_stats.get("total_tokens_generated", 0) if vllm_stats else 0,
            total_prompt_tokens=vllm_stats.get("total_prompt_tokens", 0) if vllm_stats else 0,
            average_response_time=metrics.get("average_response_time", 0),
            average_tokens_per_second=0,  # 계산 로직 추가 필요
            uptime=metrics.get("uptime", 0),
            last_request_time=None  # 별도 추적 필요
        )
        
    except Exception as e:
        logger.error(f"통계 조회 실패: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"통계 조회 중 오류가 발생했습니다: {str(e)}"
        )

@router.get(
    "/cluster/status",
    summary="클러스터 상태",
    description="Ray 클러스터 상태 정보"
)
async def get_cluster_status(service = Depends(get_ray_service)):
    """Ray 클러스터 상태 조회 API"""
    try:
        cluster_status = service.get_cluster_status()
        return cluster_status
        
    except Exception as e:
        logger.error(f"클러스터 상태 조회 실패: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"클러스터 상태 조회 중 오류가 발생했습니다: {str(e)}"
        )

@router.get(
    "/cluster/resources",
    summary="클러스터 리소스",
    description="Ray 클러스터 리소스 정보"
)
async def get_cluster_resources(service = Depends(get_ray_service)):
    """Ray 클러스터 리소스 조회 API"""
    try:
        resources = service.get_cluster_resources()
        return resources
        
    except Exception as e:
        logger.error(f"클러스터 리소스 조회 실패: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"클러스터 리소스 조회 중 오류가 발생했습니다: {str(e)}"
        )

@router.get(
    "/cluster/health",
    summary="클러스터 헬스",
    description="Ray 클러스터 헬스 모니터링"
)
async def get_cluster_health(service = Depends(get_ray_service)):
    """Ray 클러스터 헬스 모니터링 API"""
    try:
        health = service.monitor_cluster_health()
        return health
        
    except Exception as e:
        logger.error(f"클러스터 헬스 조회 실패: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"클러스터 헬스 조회 중 오류가 발생했습니다: {str(e)}"
        )

@router.get(
    "/metrics",
    summary="메트릭",
    description="서비스 메트릭 정보"
)
async def get_service_metrics():
    """서비스 메트릭 API"""
    try:
        metrics = await get_metrics()
        return metrics
        
    except Exception as e:
        logger.error(f"메트릭 조회 실패: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"메트릭 조회 중 오류가 발생했습니다: {str(e)}"
        )

@router.post(
    "/admin/shutdown",
    summary="서비스 종료",
    description="서비스 종료 (관리자용)"
)
async def shutdown_service(
    _: bool = Depends(verify_api_key),
    vllm_svc = Depends(get_vllm_service),
    ray_svc = Depends(get_ray_service)
):
    """서비스 종료 API (개발/테스트용)"""
    try:
        logger.info("서비스 종료 요청 받음")
        
        # vLLM 서비스 종료
        vllm_svc.shutdown()
        
        # Ray 서비스 종료
        ray_svc.shutdown()
        
        return {"message": "서비스가 종료되었습니다"}
        
    except Exception as e:
        logger.error(f"서비스 종료 실패: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"서비스 종료 중 오류가 발생했습니다: {str(e)}"
        )

@router.post(
    "/admin/reload",
    summary="서비스 재시작",
    description="서비스 재시작 (관리자용)"
)
async def reload_service(
    _: bool = Depends(verify_api_key)
):
    """서비스 재시작 API"""
    try:
        logger.info("서비스 재시작 요청 받음")
        
        # Ray 서비스 재연결
        if not ray_service.reconnect():
            raise RuntimeError("Ray 클러스터 재연결 실패")
        
        # vLLM 서비스 재초기화
        vllm_service.initialize()
        
        return {"message": "서비스가 재시작되었습니다"}
        
    except Exception as e:
        logger.error(f"서비스 재시작 실패: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"서비스 재시작 중 오류가 발생했습니다: {str(e)}"
        )

# ================================
# 모델 모니터링 API
# ================================

@router.get(
    "/model/status",
    response_model=ModelStatusResponse,
    summary="모델 상태 조회",
    description="모델의 현재 상태 및 성능 메트릭 조회"
)
async def get_model_status():
    """모델 상태 조회 API"""
    try:
        status = await model_monitor_service.get_current_status()
        
        return ModelStatusResponse(
            status=status["current_status"],
            last_check=status["last_check"],
            checks_performed=status["checks_performed"],
            response_time_avg=status["response_time_avg"],
            response_time_p95=status["response_time_p95"],
            error_rate=status["error_rate"],
            throughput=status["throughput"],
            gpu_memory_usage=status["gpu_memory_usage"],
            gpu_temperature=status["gpu_temperature"],
            active_requests=status["active_requests"],
            recent_status_distribution=status["recent_status_distribution"],
            alerts=status["alerts"]
        )
        
    except Exception as e:
        logger.error(f"모델 상태 조회 실패: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"모델 상태 조회 중 오류가 발생했습니다: {str(e)}"
        )

@router.post(
    "/model/health-check",
    response_model=ModelHealthCheckResponse,
    summary="모델 헬스체크 실행",
    description="모델 헬스체크를 수동으로 실행하고 결과 반환"
)
async def run_model_health_check(
    request: ModelHealthCheckRequest = ModelHealthCheckRequest(),
    service = Depends(get_vllm_service)
):
    """모델 헬스체크 실행 API"""
    try:
        logger.info("수동 모델 헬스체크 실행")
        
        # 기본 헬스체크 실행
        health_result = await model_monitor_service.run_health_check(service)
        
        response_data = ModelHealthCheckResponse(
            status=health_result["status"],
            timestamp=health_result["timestamp"],
            metrics=health_result["metrics"]
        )
        
        # 추론 테스트 포함인 경우
        if request.include_inference_test:
            test_prompt = request.test_prompt or "Hello, how are you?"
            
            from app.models.schemas import GenerateRequest
            test_request = GenerateRequest(
                prompt=test_prompt,
                max_tokens=20,
                temperature=0.0
            )
            
            inference_result = await model_health_checker.test_model_inference(service)
            response_data.inference_test = inference_result
        
        return response_data
        
    except Exception as e:
        logger.error(f"모델 헬스체크 실행 실패: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"모델 헬스체크 실행 중 오류가 발생했습니다: {str(e)}"
        )

@router.get(
    "/model/metrics/system",
    response_model=SystemMetricsResponse,
    summary="시스템 메트릭 조회",
    description="현재 시스템 리소스 사용량 조회"
)
async def get_system_metrics():
    """시스템 메트릭 조회 API"""
    try:
        system_metrics = model_health_checker.get_system_metrics()
        
        return SystemMetricsResponse(
            timestamp=time.time(),
            cpu_usage_percent=system_metrics.cpu_usage_percent,
            memory_usage_percent=system_metrics.memory_usage_percent,
            disk_usage_percent=system_metrics.disk_usage_percent,
            load_average=list(system_metrics.load_average),
            gpu_utilization=system_metrics.gpu_utilization,
            gpu_memory_total=system_metrics.gpu_memory_total,
            gpu_memory_used=system_metrics.gpu_memory_used,
            gpu_memory_percent=system_metrics.gpu_memory_used / system_metrics.gpu_memory_total * 100 
                              if system_metrics.gpu_memory_total else None,
            gpu_temperature=system_metrics.gpu_temperature
        )
        
    except Exception as e:
        logger.error(f"시스템 메트릭 조회 실패: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"시스템 메트릭 조회 중 오류가 발생했습니다: {str(e)}"
        )

@router.get(
    "/model/history",
    response_model=ModelHistoricalDataResponse,
    summary="모델 과거 데이터 조회",
    description="지정된 시간 동안의 모델 상태 히스토리 조회"
)
async def get_model_history(
    hours: int = 24,
    _: bool = Depends(verify_api_key)
):
    """모델 과거 데이터 조회 API"""
    try:
        if hours < 1 or hours > 168:  # 최대 1주일
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="시간 범위는 1-168시간 사이여야 합니다"
            )
        
        historical_data = await model_monitor_service.get_historical_data(hours)
        
        # 요약 통계 계산
        if historical_data:
            response_times = [d["response_time_avg"] for d in historical_data if d["response_time_avg"]]
            error_rates = [d["error_rate"] for d in historical_data if d["error_rate"] is not None]
            
            # 상태 분포 계산
            status_counts = {}
            for d in historical_data:
                status = d["status"]
                status_counts[status] = status_counts.get(status, 0) + 1
            
            # 업타임 계산 (healthy + degraded)
            healthy_count = status_counts.get("healthy", 0) + status_counts.get("degraded", 0)
            uptime_percentage = (healthy_count / len(historical_data)) * 100 if historical_data else 0
            
            summary = {
                "avg_response_time": sum(response_times) / len(response_times) if response_times else 0,
                "max_response_time": max(response_times) if response_times else 0,
                "avg_error_rate": sum(error_rates) / len(error_rates) if error_rates else 0,
                "uptime_percentage": uptime_percentage,
                "status_distribution": status_counts
            }
        else:
            summary = {
                "avg_response_time": 0,
                "max_response_time": 0,
                "avg_error_rate": 0,
                "uptime_percentage": 0,
                "status_distribution": {}
            }
        
        return ModelHistoricalDataResponse(
            timeframe_hours=hours,
            data_points=len(historical_data),
            data=historical_data,
            summary=summary
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"모델 과거 데이터 조회 실패: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"모델 과거 데이터 조회 중 오류가 발생했습니다: {str(e)}"
        )

@router.post(
    "/model/monitoring/start",
    summary="모델 모니터링 시작",
    description="백그라운드 모델 모니터링 시작"
)
async def start_model_monitoring(
    interval: int = 30,
    _: bool = Depends(verify_api_key),
    service = Depends(get_vllm_service)
):
    """모델 모니터링 시작 API"""
    try:
        if interval < 10 or interval > 300:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="모니터링 간격은 10-300초 사이여야 합니다"
            )
        
        await model_monitor_service.start_monitoring(service, interval)
        
        return {
            "message": "모델 모니터링이 시작되었습니다",
            "monitoring_interval": interval,
            "started_at": time.time()
        }
        
    except Exception as e:
        logger.error(f"모델 모니터링 시작 실패: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"모델 모니터링 시작 중 오류가 발생했습니다: {str(e)}"
        )

@router.post(
    "/model/monitoring/stop",
    summary="모델 모니터링 중지",
    description="백그라운드 모델 모니터링 중지"
)
async def stop_model_monitoring(_: bool = Depends(verify_api_key)):
    """모델 모니터링 중지 API"""
    try:
        await model_monitor_service.stop_monitoring()
        
        return {
            "message": "모델 모니터링이 중지되었습니다",
            "stopped_at": time.time()
        }
        
    except Exception as e:
        logger.error(f"모델 모니터링 중지 실패: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"모델 모니터링 중지 중 오류가 발생했습니다: {str(e)}"
        )

@router.get(
    "/model/alerts",
    summary="모델 알림 조회",
    description="현재 활성화된 모델 알림 조회"
)
async def get_model_alerts():
    """모델 알림 조회 API"""
    try:
        status = await model_monitor_service.get_current_status()
        alerts = status.get("alerts", [])
        
        # 알림을 심각도별로 분류
        critical_alerts = [a for a in alerts if a.get("severity") == "critical"]
        warning_alerts = [a for a in alerts if a.get("severity") == "warning"]
        
        return {
            "total_alerts": len(alerts),
            "critical_count": len(critical_alerts),
            "warning_count": len(warning_alerts),
            "alerts": alerts,
            "critical_alerts": critical_alerts,
            "warning_alerts": warning_alerts,
            "last_check": status.get("last_check"),
            "timestamp": time.time()
        }
        
    except Exception as e:
        logger.error(f"모델 알림 조회 실패: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"모델 알림 조회 중 오류가 발생했습니다: {str(e)}"
        )