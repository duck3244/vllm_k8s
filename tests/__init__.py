"""
tests/__init__.py
테스트 패키지 초기화 파일
"""

import os
import sys
import pytest
from unittest.mock import Mock, patch

# 프로젝트 루트를 Python 경로에 추가
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# 테스트용 환경변수 설정
os.environ.setdefault("APP_NAME", "vLLM Test API")
os.environ.setdefault("MODEL_PATH", "/tmp/test-model")
os.environ.setdefault("RAY_ADDRESS", "ray://localhost:10001")
os.environ.setdefault("API_KEY_ENABLED", "false")
os.environ.setdefault("LOG_LEVEL", "DEBUG")

# 공통 테스트 픽스처 및 헬퍼 함수들

class MockVLLMEngine:
    """vLLM 엔진 모킹용 클래스"""
    
    def __init__(self):
        self.initialized = True
        self.request_counter = 0
    
    async def generate(self, prompt, sampling_params, request_id):
        """모킹된 생성 메서드"""
        self.request_counter += 1
        
        # 가짜 출력 객체 생성
        class MockOutput:
            def __init__(self):
                self.text = f"Generated response for: {prompt[:50]}..."
                self.finish_reason = "stop"
                self.token_ids = list(range(10))  # 10개 토큰 시뮬레이션
        
        class MockRequestOutput:
            def __init__(self):
                self.outputs = [MockOutput()]
                self.finished = True
        
        yield MockRequestOutput()

class MockRayCluster:
    """Ray 클러스터 모킹용 클래스"""
    
    @staticmethod
    def is_initialized():
        return True
    
    @staticmethod
    def cluster_resources():
        return {
            "CPU": 8.0,
            "GPU": 1.0,
            "memory": 16000000000
        }
    
    @staticmethod
    def available_resources():
        return {
            "CPU": 6.0,
            "GPU": 0.5,
            "memory": 8000000000
        }

# 테스트용 설정 오버라이드
def override_settings(**kwargs):
    """테스트용 설정 오버라이드 데코레이터"""
    def decorator(func):
        def wrapper(*args, **test_kwargs):
            from app.core.config import settings
            original_values = {}
            
            # 원본 값 저장
            for key, value in kwargs.items():
                if hasattr(settings, key):
                    original_values[key] = getattr(settings, key)
                    setattr(settings, key, value)
            
            try:
                return func(*args, **test_kwargs)
            finally:
                # 원본 값 복원
                for key, value in original_values.items():
                    setattr(settings, key, value)
        
        return wrapper
    return decorator

# 비동기 테스트 헬퍼
def async_test(coro):
    """비동기 함수를 동기적으로 실행하는 헬퍼"""
    import asyncio
    
    def wrapper(*args, **kwargs):
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            return loop.run_until_complete(coro(*args, **kwargs))
        finally:
            loop.close()
    
    return wrapper

# 테스트 데이터 생성 헬퍼
def create_test_generate_request(**overrides):
    """테스트용 GenerateRequest 생성"""
    from app.models.schemas import GenerateRequest
    
    default_data = {
        "prompt": "테스트 프롬프트입니다.",
        "max_tokens": 100,
        "temperature": 0.7,
        "top_p": 0.9,
        "top_k": 50,
        "repetition_penalty": 1.0
    }
    default_data.update(overrides)
    
    return GenerateRequest(**default_data)

def create_test_batch_request(prompt_count=3, **overrides):
    """테스트용 BatchGenerateRequest 생성"""
    from app.models.schemas import BatchGenerateRequest
    
    default_data = {
        "prompts": [f"테스트 프롬프트 {i}" for i in range(prompt_count)],
        "max_tokens": 50,
        "temperature": 0.5,
        "top_p": 0.9
    }
    default_data.update(overrides)
    
    return BatchGenerateRequest(**default_data)

# pytest 설정
def pytest_configure(config):
    """pytest 설정"""
    config.addinivalue_line(
        "markers",
        "integration: 통합 테스트 (실제 서비스 필요)"
    )
    config.addinivalue_line(
        "markers", 
        "slow: 느린 테스트"
    )

# 공통 픽스처
@pytest.fixture
def mock_vllm_engine():
    """모킹된 vLLM 엔진 픽스처"""
    return MockVLLMEngine()

@pytest.fixture
def mock_ray_cluster():
    """모킹된 Ray 클러스터 픽스처"""
    with patch('ray.is_initialized', return_value=True), \
         patch('ray.cluster_resources', return_value=MockRayCluster.cluster_resources()), \
         patch('ray.available_resources', return_value=MockRayCluster.available_resources()):
        yield MockRayCluster()

@pytest.fixture
def test_request():
    """테스트용 생성 요청 픽스처"""
    return create_test_generate_request()

@pytest.fixture
def test_batch_request():
    """테스트용 배치 요청 픽스처"""
    return create_test_batch_request()

# 환경 정리 함수
def cleanup_test_environment():
    """테스트 환경 정리"""
    import tempfile
    import shutil
    
    # 임시 파일 정리
    temp_dirs = ['/tmp/test-model', '/tmp/ray-temp']
    for temp_dir in temp_dirs:
        if os.path.exists(temp_dir):
            shutil.rmtree(temp_dir, ignore_errors=True)

# 테스트 실행 전후 설정
def setup_module():
    """모듈 테스트 시작 전 설정"""
    print("🧪 테스트 환경 설정 중...")

def teardown_module():
    """모듈 테스트 완료 후 정리"""
    cleanup_test_environment()
    print("🧹 테스트 환경 정리 완료")

# 로깅 설정 (테스트용)
import logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

# 테스트용 상수
TEST_MODEL_PATH = "/tmp/test-model"
TEST_RAY_ADDRESS = "ray://localhost:10001"
TEST_API_BASE_URL = "http://localhost:8000"
TEST_TIMEOUT = 30  # 초