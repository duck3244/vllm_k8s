"""
app/models/schemas.py
API 요청/응답 스키마 정의
"""

from pydantic import BaseModel, Field, validator
from typing import Optional, List, Dict, Any, Union
from enum import Enum
import time

class FinishReason(str, Enum):
    """생성 완료 이유"""
    STOP = "stop"
    LENGTH = "length"
    TOOL_CALLS = "tool_calls"
    CONTENT_FILTER = "content_filter"
    ERROR = "error"

class GenerateRequest(BaseModel):
    """텍스트 생성 요청 스키마"""
    
    # 필수 필드
    prompt: str = Field(
        ..., 
        description="입력 프롬프트", 
        min_length=1,
        max_length=8192,
        example="안녕하세요! 머신러닝에 대해 설명해주세요."
    )
    
    # 생성 파라미터
    max_tokens: int = Field(
        100, 
        description="생성할 최대 토큰 수", 
        ge=1, 
        le=2048,
        example=200
    )
    
    temperature: float = Field(
        0.7, 
        description="샘플링 온도 (0.0-2.0)", 
        ge=0.0, 
        le=2.0,
        example=0.7
    )
    
    top_p: float = Field(
        0.95, 
        description="Top-p (nucleus) 샘플링", 
        ge=0.0, 
        le=1.0,
        example=0.95
    )
    
    top_k: int = Field(
        50, 
        description="Top-k 샘플링", 
        ge=1, 
        le=100,
        example=50
    )
    
    repetition_penalty: float = Field(
        1.0, 
        description="반복 패널티", 
        ge=0.1, 
        le=2.0,
        example=1.1
    )
    
    frequency_penalty: float = Field(
        0.0,
        description="빈도 패널티",
        ge=-2.0,
        le=2.0,
        example=0.0
    )
    
    presence_penalty: float = Field(
        0.0,
        description="존재 패널티",
        ge=-2.0,
        le=2.0,
        example=0.0
    )
    
    # 중지 조건
    stop: Optional[Union[str, List[str]]] = Field(
        None, 
        description="중지 토큰 또는 토큰 리스트",
        example=[".", "!", "?"]
    )
    
    # 시드 (재현성)
    seed: Optional[int] = Field(
        None,
        description="랜덤 시드",
        example=42
    )
    
    # 스트리밍
    stream: bool = Field(
        False,
        description="스트리밍 응답 여부",
        example=False
    )
    
    # 메타데이터
    user_id: Optional[str] = Field(
        None,
        description="사용자 ID",
        max_length=100,
        example="user123"
    )
    
    session_id: Optional[str] = Field(
        None,
        description="세션 ID",
        max_length=100,
        example="session456"
    )
    
    @validator('stop')
    def validate_stop(cls, v):
        """중지 토큰 검증"""
        if v is None:
            return v
        if isinstance(v, str):
            return [v]
        if isinstance(v, list):
            if len(v) > 10:
                raise ValueError("중지 토큰은 최대 10개까지 가능합니다")
            return v
        raise ValueError("중지 토큰은 문자열 또는 문자열 리스트여야 합니다")
    
    class Config:
        schema_extra = {
            "example": {
                "prompt": "Python에서 리스트와 튜플의 차이점을 설명해주세요.",
                "max_tokens": 300,
                "temperature": 0.8,
                "top_p": 0.9,
                "top_k": 40,
                "repetition_penalty": 1.1,
                "stop": [".", "\n\n"],
                "seed": 42
            }
        }

class ModelStatusResponse(BaseModel):
    """모델 상태 응답 스키마"""
    
    status: str = Field(..., description="모델 상태")
    last_check: Optional[str] = Field(None, description="마지막 체크 시간")
    checks_performed: int = Field(..., description="수행된 체크 수")
    
    # 성능 메트릭
    response_time_avg: float = Field(..., description="평균 응답 시간")
    response_time_p95: float = Field(..., description="95% 응답 시간")
    error_rate: float = Field(..., description="에러율 (0-1)")
    throughput: float = Field(..., description="처리량 (tokens/sec)")
    
    # 리소스 메트릭
    gpu_memory_usage: Optional[float] = Field(None, description="GPU 메모리 사용률 (%)")
    gpu_temperature: Optional[float] = Field(None, description="GPU 온도 (°C)")
    active_requests: int = Field(..., description="활성 요청 수")
    
    # 상태 분포
    recent_status_distribution: Dict[str, int] = Field(..., description="최근 상태 분포")
    alerts: List[Dict[str, Any]] = Field(..., description="활성 알림")
    
    class Config:
        schema_extra = {
            "example": {
                "status": "healthy",
                "last_check": "2024-01-15T10:30:45",
                "checks_performed": 150,
                "response_time_avg": 1.23,
                "response_time_p95": 2.15,
                "error_rate": 0.02,
                "throughput": 35.6,
                "gpu_memory_usage": 85.5,
                "gpu_temperature": 72.0,
                "active_requests": 3,
                "recent_status_distribution": {
                    "healthy": 8,
                    "degraded": 2
                },
                "alerts": []
            }
        }

class ModelHealthCheckRequest(BaseModel):
    """모델 헬스체크 요청 스키마"""
    
    include_inference_test: bool = Field(
        False, 
        description="추론 테스트 포함 여부"
    )
    test_prompt: Optional[str] = Field(
        None,
        description="테스트용 프롬프트",
        max_length=100
    )

class ModelHealthCheckResponse(BaseModel):
    """모델 헬스체크 응답 스키마"""
    
    status: str = Field(..., description="모델 상태")
    timestamp: float = Field(..., description="체크 시간")
    
    metrics: Dict[str, Any] = Field(..., description="상세 메트릭")
    
    # 추론 테스트 결과 (선택사항)
    inference_test: Optional[Dict[str, Any]] = Field(None, description="추론 테스트 결과")
    
    class Config:
        schema_extra = {
            "example": {
                "status": "healthy",
                "timestamp": 1699123456.789,
                "metrics": {
                    "response_time_avg": 1.23,
                    "response_time_p95": 2.15,
                    "error_rate": 0.02,
                    "memory_usage": 65.2,
                    "gpu_memory_usage": 85.5,
                    "gpu_temperature": 72.0,
                    "throughput": 35.6,
                    "active_requests": 3
                },
                "inference_test": {
                    "success": True,
                    "response_time": 0.85,
                    "tokens_generated": 8,
                    "error": None
                }
            }
        }

class SystemMetricsResponse(BaseModel):
    """시스템 메트릭 응답 스키마"""
    
    timestamp: float = Field(..., description="측정 시간")
    
    # CPU 및 메모리
    cpu_usage_percent: float = Field(..., description="CPU 사용률")
    memory_usage_percent: float = Field(..., description="메모리 사용률")
    disk_usage_percent: float = Field(..., description="디스크 사용률")
    load_average: List[float] = Field(..., description="로드 평균 [1m, 5m, 15m]")
    
    # GPU 메트릭
    gpu_utilization: Optional[float] = Field(None, description="GPU 사용률")
    gpu_memory_total: Optional[int] = Field(None, description="총 GPU 메모리 (bytes)")
    gpu_memory_used: Optional[int] = Field(None, description="사용된 GPU 메모리 (bytes)")
    gpu_memory_percent: Optional[float] = Field(None, description="GPU 메모리 사용률")
    gpu_temperature: Optional[float] = Field(None, description="GPU 온도")
    
    class Config:
        schema_extra = {
            "example": {
                "timestamp": 1699123456.789,
                "cpu_usage_percent": 45.2,
                "memory_usage_percent": 67.8,
                "disk_usage_percent": 23.1,
                "load_average": [1.2, 1.5, 1.8],
                "gpu_utilization": 78.5,
                "gpu_memory_total": 12884901888,
                "gpu_memory_used": 11019960320,
                "gpu_memory_percent": 85.5,
                "gpu_temperature": 72.0
            }
        }

class ModelHistoricalDataResponse(BaseModel):
    """모델 과거 데이터 응답 스키마"""
    
    timeframe_hours: int = Field(..., description="데이터 기간 (시간)")
    data_points: int = Field(..., description="데이터 포인트 수")
    
    data: List[Dict[str, Any]] = Field(..., description="시계열 데이터")
    
    # 요약 통계
    summary: Dict[str, Any] = Field(..., description="요약 통계")
    
    class Config:
        schema_extra = {
            "example": {
                "timeframe_hours": 24,
                "data_points": 48,
                "data": [
                    {
                        "timestamp": 1699123456.789,
                        "status": "healthy",
                        "response_time_p95": 2.15,
                        "error_rate": 0.02,
                        "gpu_memory_usage": 85.5,
                        "gpu_temperature": 72.0,
                        "throughput": 35.6,
                        "active_requests": 3
                    }
                ],
                "summary": {
                    "avg_response_time": 1.45,
                    "max_response_time": 3.21,
                    "avg_error_rate": 0.015,
                    "uptime_percentage": 99.2,
                    "status_distribution": {
                        "healthy": 45,
                        "degraded": 3,
                        "unhealthy": 0
                    }
                }
            }
        }

class GenerateResponse(BaseModel):
    """텍스트 생성 응답 스키마"""
    
    # 생성된 텍스트
    text: str = Field(..., description="생성된 텍스트")
    
    # 입력 정보
    prompt: str = Field(..., description="입력 프롬프트")
    
    # 생성 통계
    tokens_generated: int = Field(..., description="생성된 토큰 수")
    prompt_tokens: int = Field(..., description="프롬프트 토큰 수")
    total_tokens: int = Field(..., description="총 토큰 수")
    
    # 완료 정보
    finish_reason: FinishReason = Field(..., description="생성 완료 이유")
    
    # 성능 정보
    generation_time: float = Field(..., description="생성 시간 (초)")
    tokens_per_second: float = Field(..., description="초당 토큰 수")
    
    # 메타데이터
    model_name: str = Field(..., description="사용된 모델명")
    timestamp: float = Field(default_factory=time.time, description="응답 타임스탬프")
    request_id: Optional[str] = Field(None, description="요청 ID")
    
    class Config:
        schema_extra = {
            "example": {
                "text": "Python에서 리스트는 변경 가능한(mutable) 데이터 타입이고, 튜플은 변경 불가능한(immutable) 데이터 타입입니다.",
                "prompt": "Python에서 리스트와 튜플의 차이점을 설명해주세요.",
                "tokens_generated": 45,
                "prompt_tokens": 15,
                "total_tokens": 60,
                "finish_reason": "stop",
                "generation_time": 1.23,
                "tokens_per_second": 36.6,
                "model_name": "llama-3.2-3b-instruct",
                "timestamp": 1699123456.789,
                "request_id": "req_abc123"
            }
        }

class BatchGenerateRequest(BaseModel):
    """배치 텍스트 생성 요청 스키마"""
    
    prompts: List[str] = Field(
        ...,
        description="프롬프트 리스트",
        min_items=1,
        max_items=10
    )
    
    # GenerateRequest의 파라미터들 (개별 프롬프트에 공통 적용)
    max_tokens: int = Field(100, ge=1, le=2048)
    temperature: float = Field(0.7, ge=0.0, le=2.0)
    top_p: float = Field(0.95, ge=0.0, le=1.0)
    top_k: int = Field(50, ge=1, le=100)
    repetition_penalty: float = Field(1.0, ge=0.1, le=2.0)
    stop: Optional[List[str]] = Field(None)
    
    @validator('prompts')
    def validate_prompts(cls, v):
        """프롬프트 리스트 검증"""
        for prompt in v:
            if not prompt.strip():
                raise ValueError("빈 프롬프트는 허용되지 않습니다")
            if len(prompt) > 8192:
                raise ValueError(f"프롬프트가 너무 깁니다: {len(prompt)} > 8192")
        return v

class BatchGenerateResponse(BaseModel):
    """배치 텍스트 생성 응답 스키마"""
    
    responses: List[GenerateResponse] = Field(..., description="응답 리스트")
    total_time: float = Field(..., description="전체 처리 시간")
    request_count: int = Field(..., description="처리된 요청 수")

class HealthResponse(BaseModel):
    """헬스체크 응답 스키마"""
    
    status: str = Field(..., description="서비스 상태")
    timestamp: float = Field(default_factory=time.time, description="체크 시간")
    
    # 구성 요소 상태
    model_loaded: bool = Field(..., description="모델 로딩 상태")
    ray_connected: bool = Field(..., description="Ray 클러스터 연결 상태")
    gpu_available: bool = Field(..., description="GPU 사용 가능 여부")
    
    # 시스템 정보
    version: str = Field(..., description="애플리케이션 버전")
    model_name: str = Field(..., description="로딩된 모델명")
    
    # 성능 정보
    uptime: float = Field(..., description="업타임 (초)")
    total_requests: int = Field(..., description="총 요청 수")
    active_requests: int = Field(..., description="활성 요청 수")
    
    # 리소스 사용량
    gpu_memory_used: Optional[float] = Field(None, description="GPU 메모리 사용률 (%)")
    system_memory_used: Optional[float] = Field(None, description="시스템 메모리 사용률 (%)")
    
    class Config:
        schema_extra = {
            "example": {
                "status": "healthy",
                "timestamp": 1699123456.789,
                "model_loaded": True,
                "ray_connected": True,
                "gpu_available": True,
                "version": "1.0.0",
                "model_name": "llama-3.2-3b-instruct",
                "uptime": 3600.0,
                "total_requests": 150,
                "active_requests": 2,
                "gpu_memory_used": 85.5,
                "system_memory_used": 45.2
            }
        }

class ModelInfo(BaseModel):
    """모델 정보 스키마"""
    
    model_name: str = Field(..., description="모델명")
    model_path: str = Field(..., description="모델 경로")
    model_type: str = Field(..., description="모델 타입")
    
    # vLLM 설정
    tensor_parallel_size: int = Field(..., description="텐서 병렬 크기")
    gpu_memory_utilization: float = Field(..., description="GPU 메모리 사용률")
    max_model_len: int = Field(..., description="최대 모델 길이")
    dtype: str = Field(..., description="데이터 타입")
    
    # 지원 기능
    supports_streaming: bool = Field(True, description="스트리밍 지원 여부")
    supports_batch: bool = Field(True, description="배치 처리 지원 여부")
    
    # 메타데이터
    loaded_at: float = Field(default_factory=time.time, description="모델 로딩 시간")
    parameters: Optional[str] = Field(None, description="모델 파라미터 수")

class ErrorResponse(BaseModel):
    """오류 응답 스키마"""
    
    error: str = Field(..., description="오류 타입")
    message: str = Field(..., description="오류 메시지")
    detail: Optional[str] = Field(None, description="상세 오류 정보")
    timestamp: float = Field(default_factory=time.time, description="오류 발생 시간")
    request_id: Optional[str] = Field(None, description="요청 ID")
    
    class Config:
        schema_extra = {
            "example": {
                "error": "ValidationError",
                "message": "입력 값이 유효하지 않습니다",
                "detail": "temperature 값은 0.0과 2.0 사이여야 합니다",
                "timestamp": 1699123456.789,
                "request_id": "req_abc123"
            }
        }

class StreamResponse(BaseModel):
    """스트리밍 응답 스키마"""
    
    text: str = Field(..., description="생성된 텍스트 청크")
    is_finished: bool = Field(..., description="생성 완료 여부")
    finish_reason: Optional[FinishReason] = Field(None, description="완료 이유")
    tokens_generated: int = Field(..., description="현재까지 생성된 토큰 수")
    
class UsageStats(BaseModel):
    """사용 통계 스키마"""
    
    total_requests: int = Field(..., description="총 요청 수")
    successful_requests: int = Field(..., description="성공한 요청 수")
    failed_requests: int = Field(..., description="실패한 요청 수")
    
    total_tokens_generated: int = Field(..., description="총 생성된 토큰 수")
    total_prompt_tokens: int = Field(..., description="총 프롬프트 토큰 수")
    
    average_response_time: float = Field(..., description="평균 응답 시간 (초)")
    average_tokens_per_second: float = Field(..., description="평균 초당 토큰 수")
    
    uptime: float = Field(..., description="서비스 업타임 (초)")
    last_request_time: Optional[float] = Field(None, description="마지막 요청 시간")
    
    class Config:
        schema_extra = {
            "example": {
                "total_requests": 1000,
                "successful_requests": 985,
                "failed_requests": 15,
                "total_tokens_generated": 50000,
                "total_prompt_tokens": 25000,
                "average_response_time": 2.5,
                "average_tokens_per_second": 35.2,
                "uptime": 86400.0,
                "last_request_time": 1699123456.789
            }
        }