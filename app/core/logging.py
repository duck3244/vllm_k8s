"""
app/core/logging.py
로깅 설정 및 관리 모듈
"""

import logging
import logging.handlers
import sys
import os
from typing import Optional
from datetime import datetime
from app.core.config import settings

class ColoredFormatter(logging.Formatter):
    """색상이 있는 로그 포매터"""
    
    COLORS = {
        'DEBUG': '\033[36m',      # 청록색
        'INFO': '\033[32m',       # 초록색
        'WARNING': '\033[33m',    # 노란색
        'ERROR': '\033[31m',      # 빨간색
        'CRITICAL': '\033[35m',   # 보라색
        'RESET': '\033[0m'        # 리셋
    }
    
    def format(self, record):
        log_color = self.COLORS.get(record.levelname, self.COLORS['RESET'])
        record.levelname = f"{log_color}{record.levelname}{self.COLORS['RESET']}"
        return super().format(record)

class RequestLogger:
    """API 요청 로깅 클래스"""
    
    def __init__(self):
        self.logger = logging.getLogger("api_requests")
        self.request_count = 0
    
    def log_request(self, method: str, path: str, status_code: int, 
                   response_time: float, client_ip: str = None):
        """API 요청 로깅"""
        self.request_count += 1
        
        self.logger.info(
            f"#{self.request_count} {method} {path} - "
            f"Status: {status_code} - "
            f"Time: {response_time:.3f}s"
            f"{f' - IP: {client_ip}' if client_ip else ''}"
        )
    
    def log_generation(self, prompt_length: int, generated_tokens: int, 
                      total_time: float, tokens_per_second: float):
        """텍스트 생성 성능 로깅"""
        self.logger.info(
            f"Generation - Prompt: {prompt_length} chars, "
            f"Generated: {generated_tokens} tokens, "
            f"Time: {total_time:.3f}s, "
            f"Speed: {tokens_per_second:.1f} tokens/s"
        )

def setup_logging() -> logging.Logger:
    """로깅 시스템 설정"""
    
    # 루트 로거 설정
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, settings.LOG_LEVEL))
    
    # 기존 핸들러 제거
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)
    
    # 콘솔 핸들러
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(getattr(logging, settings.LOG_LEVEL))
    
    # 색상 포매터 (터미널에서만)
    if sys.stdout.isatty():
        console_formatter = ColoredFormatter(settings.LOG_FORMAT)
    else:
        console_formatter = logging.Formatter(settings.LOG_FORMAT)
    
    console_handler.setFormatter(console_formatter)
    root_logger.addHandler(console_handler)
    
    # 파일 핸들러 (설정된 경우)
    if settings.LOG_FILE:
        # 로그 디렉토리 생성
        log_dir = os.path.dirname(settings.LOG_FILE)
        if log_dir and not os.path.exists(log_dir):
            os.makedirs(log_dir)
        
        # 로테이팅 파일 핸들러
        file_handler = logging.handlers.RotatingFileHandler(
            settings.LOG_FILE,
            maxBytes=10*1024*1024,  # 10MB
            backupCount=5,
            encoding='utf-8'
        )
        file_handler.setLevel(logging.DEBUG)
        
        file_formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(funcName)s:%(lineno)d - %(message)s'
        )
        file_handler.setFormatter(file_formatter)
        root_logger.addHandler(file_handler)
    
    # 외부 라이브러리 로깅 레벨 조정
    logging.getLogger("uvicorn").setLevel(logging.WARNING)
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("ray").setLevel(logging.WARNING)
    logging.getLogger("vllm").setLevel(logging.INFO)
    logging.getLogger("transformers").setLevel(logging.WARNING)
    logging.getLogger("torch").setLevel(logging.WARNING)
    
    # 애플리케이션 로거
    app_logger = logging.getLogger("vllm_api")
    app_logger.info(f"로깅 시스템 초기화 완료 - Level: {settings.LOG_LEVEL}")
    
    return app_logger

def get_logger(name: str) -> logging.Logger:
    """이름별 로거 반환"""
    return logging.getLogger(name)

class PerformanceLogger:
    """성능 모니터링 로거"""
    
    def __init__(self):
        self.logger = logging.getLogger("performance")
        self.start_time = datetime.now()
    
    def log_startup_time(self, component: str, elapsed_time: float):
        """시작 시간 로깅"""
        self.logger.info(f"{component} 시작 완료 - {elapsed_time:.2f}초")
    
    def log_memory_usage(self, gpu_memory: Optional[float] = None, 
                        system_memory: Optional[float] = None):
        """메모리 사용량 로깅"""
        if gpu_memory is not None:
            self.logger.info(f"GPU 메모리 사용량: {gpu_memory:.1f}%")
        if system_memory is not None:
            self.logger.info(f"시스템 메모리 사용량: {system_memory:.1f}%")
    
    def log_queue_status(self, pending_requests: int, active_requests: int):
        """요청 큐 상태 로깅"""
        self.logger.debug(f"요청 큐 - 대기: {pending_requests}, 처리중: {active_requests}")

# 전역 로거 인스턴스들
logger = setup_logging()
request_logger = RequestLogger()
performance_logger = PerformanceLogger()

# 로거 사용 예제 함수들
def log_model_loading(model_path: str, loading_time: float):
    """모델 로딩 로그"""
    logger.info(f"모델 로딩 완료: {model_path} ({loading_time:.2f}초)")

def log_generation_request(prompt: str, max_tokens: int, temperature: float):
    """생성 요청 로그"""
    logger.debug(f"생성 요청 - 프롬프트 길이: {len(prompt)}, 최대 토큰: {max_tokens}, 온도: {temperature}")

def log_error_with_context(error: Exception, context: dict = None):
    """컨텍스트와 함께 오류 로깅"""
    error_msg = f"오류 발생: {type(error).__name__}: {str(error)}"
    if context:
        error_msg += f" - 컨텍스트: {context}"
    logger.error(error_msg, exc_info=True)

def log_ray_cluster_info(cluster_resources: dict):
    """Ray 클러스터 정보 로깅"""
    logger.info(f"Ray 클러스터 리소스: {cluster_resources}")

def log_api_startup():
    """API 서버 시작 로그"""
    logger.info(f"🚀 {settings.APP_NAME} v{settings.APP_VERSION} 시작")
    logger.info(f"📍 서버 주소: {settings.API_HOST}:{settings.API_PORT}")
    logger.info(f"🤖 모델: {settings.MODEL_NAME}")
    logger.info(f"⚡ Ray 주소: {settings.RAY_ADDRESS}")

def log_api_shutdown():
    """API 서버 종료 로그"""
    logger.info(f"🛑 {settings.APP_NAME} 종료")

# 시스템 정보 로깅
def log_system_info():
    """시스템 정보 로깅"""
    import platform
    import torch
    
    logger.info("=== 시스템 정보 ===")
    logger.info(f"OS: {platform.system()} {platform.release()}")
    logger.info(f"Python: {platform.python_version()}")
    logger.info(f"PyTorch: {torch.__version__}")
    
    if torch.cuda.is_available():
        logger.info(f"CUDA: {torch.version.cuda}")
        logger.info(f"GPU 수: {torch.cuda.device_count()}")
        for i in range(torch.cuda.device_count()):
            gpu_name = torch.cuda.get_device_name(i)
            gpu_memory = torch.cuda.get_device_properties(i).total_memory / (1024**3)
            logger.info(f"GPU {i}: {gpu_name} ({gpu_memory:.1f}GB)")
    else:
        logger.warning("CUDA를 사용할 수 없습니다")
    
    logger.info("===================")