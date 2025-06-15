"""
app/core/config.py
애플리케이션 설정 관리 모듈
"""

import os
from typing import Optional, List
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    """애플리케이션 설정 클래스"""
    
    # 애플리케이션 기본 설정
    APP_NAME: str = "vLLM Llama 3.2 API Server"
    APP_VERSION: str = "1.0.0"
    APP_DESCRIPTION: str = "Ray Cluster 기반 vLLM을 사용한 Llama 3.2 추론 서버"
    DEBUG: bool = False
    
    # 모델 설정
    MODEL_PATH: str = "/models/llama-3.2-3b-instruct"  # 로컬 모델 경로
    MODEL_NAME: str = "llama-3.2-3b-instruct"
    MODEL_TYPE: str = "llama"
    
    # vLLM 엔진 설정
    TENSOR_PARALLEL_SIZE: int = 1
    GPU_MEMORY_UTILIZATION: float = 0.9
    MAX_MODEL_LEN: int = 4096
    MAX_NUM_SEQS: int = 256
    DTYPE: str = "half"  # "auto", "half", "float16", "bfloat16", "float", "float32"
    TRUST_REMOTE_CODE: bool = True
    QUANTIZATION: Optional[str] = None  # "awq", "gptq", "squeezellm", "fp8"
    
    # Ray 클러스터 설정
    RAY_ADDRESS: str = "ray://ray-head:10001"
    RAY_REDIS_PASSWORD: str = "LetMeInRay"
    RAY_NAMESPACE: str = "vllm"
    RAY_RUNTIME_ENV: dict = {}
    
    # API 서버 설정
    API_HOST: str = "0.0.0.0"
    API_PORT: int = 8000
    API_WORKERS: int = 1
    API_PREFIX: str = "/api/v1"
    CORS_ORIGINS: List[str] = ["*"]
    
    # 인증 설정 (선택사항)
    API_KEY_ENABLED: bool = False
    API_KEY: Optional[str] = None
    
    # 로깅 설정
    LOG_LEVEL: str = "INFO"
    LOG_FORMAT: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    LOG_FILE: Optional[str] = None
    
    # 성능 및 제한 설정
    MAX_CONCURRENT_REQUESTS: int = 100
    REQUEST_TIMEOUT: int = 300  # 초
    MAX_TOKENS_PER_REQUEST: int = 2048
    
    # 모니터링 설정
    METRICS_ENABLED: bool = True
    HEALTH_CHECK_PATH: str = "/health"
    METRICS_PATH: str = "/metrics"
    
    # 보안 설정
    ALLOWED_HOSTS: List[str] = ["*"]
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = True
    
    def get_ray_runtime_env(self) -> dict:
        """Ray 런타임 환경 설정 반환"""
        return {
            "pip": [
                "vllm==0.3.3",
                "transformers==4.36.0",
                "torch==2.1.0",
            ],
            "env_vars": {
                "CUDA_VISIBLE_DEVICES": "0",
                "HF_HOME": "/tmp/huggingface",
            }
        }
    
    def get_vllm_engine_args(self) -> dict:
        """vLLM 엔진 인자 반환"""
        return {
            "model": self.MODEL_PATH,
            "tensor_parallel_size": self.TENSOR_PARALLEL_SIZE,
            "dtype": self.DTYPE,
            "max_model_len": self.MAX_MODEL_LEN,
            "gpu_memory_utilization": self.GPU_MEMORY_UTILIZATION,
            "trust_remote_code": self.TRUST_REMOTE_CODE,
            "quantization": self.QUANTIZATION,
            "max_num_seqs": self.MAX_NUM_SEQS,
            "disable_log_stats": False,
        }
    
    def validate_settings(self) -> bool:
        """설정 유효성 검사"""
        errors = []
        
        # 모델 경로 확인
        if not os.path.exists(self.MODEL_PATH) and not self.MODEL_PATH.startswith("http"):
            errors.append(f"모델 경로가 존재하지 않습니다: {self.MODEL_PATH}")
        
        # GPU 메모리 사용률 확인
        if not 0.1 <= self.GPU_MEMORY_UTILIZATION <= 1.0:
            errors.append(f"GPU 메모리 사용률이 잘못되었습니다: {self.GPU_MEMORY_UTILIZATION}")
        
        # 포트 번호 확인
        if not 1024 <= self.API_PORT <= 65535:
            errors.append(f"API 포트 번호가 잘못되었습니다: {self.API_PORT}")
        
        if errors:
            for error in errors:
                print(f"설정 오류: {error}")
            return False
        
        return True

# 전역 설정 인스턴스
settings = Settings()

# 설정 유효성 검사
if not settings.validate_settings():
    raise ValueError("설정 검증 실패")

# 개발/프로덕션 환경별 설정
if settings.DEBUG:
    settings.LOG_LEVEL = "DEBUG"
    settings.MAX_CONCURRENT_REQUESTS = 10