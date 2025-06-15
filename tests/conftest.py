"""
tests/conftest.py
pytest 설정 및 공통 픽스처
"""

import pytest
import asyncio
import os
import tempfile
import shutil
from unittest.mock import Mock, patch, AsyncMock
from typing import Generator, Dict, Any

# 테스트 환경 설정
os.environ["TESTING"] = "true"
os.environ["LOG_LEVEL"] = "ERROR"  # 테스트 중 로그 출력 최소화
os.environ["API_KEY_ENABLED"] = "false"
os.environ["METRICS_ENABLED"] = "true"

# pytest 설정
def pytest_configure(config):
    """pytest 설정"""
    config.addinivalue_line(
        "markers", 
        "integration: 통합 테스트 마커 (실제 서비스 연동 필요)"
    )
    config.addinivalue_line(
        "markers", 
        "slow: 느린 테스트 마커 (시간이 오래 걸리는 테스트)"
    )
    config.addinivalue_line(
        "markers", 
        "gpu: GPU가 필요한 테스트 마커"
    )
    config.addinivalue_line(
        "markers", 
        "ray: Ray 클러스터가 필요한 테스트 마커"
    )

def pytest_collection_modifyitems(config, items):
    """테스트 수집 시 자동 마커 적용"""
    for item in items:
        # 통합 테스트 자동 마킹
        if "integration" in item.nodeid:
            item.add_marker(pytest.mark.integration)
        
        # 느린 테스트 자동 마킹
        if "slow" in item.nodeid or "long_running" in item.name:
            item.add_marker(pytest.mark.slow)

# 비동기 테스트를 위한 이벤트 루프 설정
@pytest.fixture(scope="session")
def event_loop():
    """세션 범위 이벤트 루프"""
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
    
    yield loop
    loop.close()

# 임시 디렉토리 관련 픽스처
@pytest.fixture(scope="function")
def temp_dir() -> Generator[str, None, None]:
    """함수 범위 임시 디렉토리"""
    temp_dir = tempfile.mkdtemp(prefix="vllm_test_")
    yield temp_dir
    shutil.rmtree(temp_dir, ignore_errors=True)

@pytest.fixture(scope="session")
def temp_model_dir() -> Generator[str, None, None]:
    """세션 범위 임시 모델 디렉토리"""
    temp_dir = tempfile.mkdtemp(prefix="vllm_model_test_")
    
    # 가짜 모델 파일 생성
    config_file = os.path.join(temp_dir, "config.json")
    with open(config_file, "w") as f:
        f.write('{"model_type": "llama", "vocab_size": 32000}')
    
    tokenizer_file = os.path.join(temp_dir, "tokenizer.json")
    with open(tokenizer_file, "w") as f:
        f.write('{"version": "1.0"}')
    
    yield temp_dir
    shutil.rmtree(temp_dir, ignore_errors=True)

# 환경 변수 관련 픽스처
@pytest.fixture(scope="function")
def clean_env() -> Generator[Dict[str, str], None, None]:
    """깨끗한 환경 변수"""
    original_env = os.environ.copy()
    
    # 테스트용 환경 변수 설정
    test_env = {
        "APP_NAME": "Test vLLM API",
        "MODEL_PATH": "/tmp/test-model",
        "RAY_ADDRESS": "ray://localhost:10001",
        "API_KEY_ENABLED": "false",
        "LOG_LEVEL": "ERROR",
        "DEBUG": "true",
        "TENSOR_PARALLEL_SIZE": "1",
        "GPU_MEMORY_UTILIZATION": "0.5",
        "MAX_MODEL_LEN": "2048",
        "DTYPE": "half"
    }
    
    # 기존 환경 변수 백업 후 테스트 환경 설정
    for key, value in test_env.items():
        os.environ[key] = value
    
    yield test_env
    
    # 원래 환경 변수 복원
    os.environ.clear()
    os.environ.update(original_env)

# Mock 서비스 픽스처들
@pytest.fixture(scope="function")
def mock_torch():
    """PyTorch 모킹"""
    with patch('torch.cuda.is_available', return_value=True), \
         patch('torch.cuda.device_count', return_value=1), \
         patch('torch.cuda.get_device_name', return_value="Test GPU"), \
         patch('torch.cuda.mem_get_info', return_value=(4000000000, 8000000000)), \
         patch('torch.cuda.memory_allocated', return_value=2000000000), \
         patch('torch.cuda.max_memory_allocated', return_value=8000000000):
        yield

@pytest.fixture(scope="function") 
def mock_ray():
    """Ray 모킹"""
    with patch('ray.init') as mock_init, \
         patch('ray.is_initialized', return_value=True) as mock_is_init, \
         patch('ray.shutdown') as mock_shutdown, \
         patch('ray.cluster_resources') as mock_cluster_res, \
         patch('ray.available_resources') as mock_avail_res, \
         patch('ray.nodes') as mock_nodes, \
         patch('ray.get') as mock_get, \
         patch('ray.remote') as mock_remote, \
         patch('ray.wait') as mock_wait:
        
        # 기본 반환값 설정
        mock_cluster_res.return_value = {
            "CPU": 8.0,
            "GPU": 2.0,
            "memory": 16000000000
        }
        
        mock_avail_res.return_value = {
            "CPU": 6.0,
            "GPU": 1.0,
            "memory": 8000000000
        }
        
        mock_nodes.return_value = [
            {
                "NodeID": "test_node_1",
                "Alive": True,
                "Resources": {"CPU": 4.0, "GPU": 1.0},
                "NodeManagerAddress": "127.0.0.1",
                "NodeManagerPort": 8076
            },
            {
                "NodeID": "test_node_2", 
                "Alive": True,
                "Resources": {"CPU": 4.0, "GPU": 1.0},
                "NodeManagerAddress": "127.0.0.1",
                "NodeManagerPort": 8077
            }
        ]
        
        mock_wait.return_value = ([], ["task_ref"])  # 기본적으로 대기 중
        
        yield {
            "init": mock_init,
            "is_initialized": mock_is_init,
            "shutdown": mock_shutdown,
            "cluster_resources": mock_cluster_res,
            "available_resources": mock_avail_res,
            "nodes": mock_nodes,
            "get": mock_get,
            "remote": mock_remote,
            "wait": mock_wait
        }

@pytest.fixture(scope="function")
def mock_vllm_engine():
    """vLLM 엔진 모킹"""
    with patch('app.services.vllm_engine.AsyncLLMEngine') as mock_engine_class, \
         patch('app.services.vllm_engine.AsyncEngineArgs') as mock_args_class, \
         patch('app.services.vllm_engine.SamplingParams') as mock_sampling_class:
        
        # Mock 엔진 인스턴스
        mock_engine = Mock()
        mock_engine_class.from_engine_args.return_value = mock_engine
        
        # Mock 비동기 제너레이터
        async def mock_generate(prompt, sampling_params, request_id):
            # 가짜 출력 객체 생성
            class MockOutput:
                def __init__(self):
                    self.text = f"Generated response for: {prompt}"
                    self.finish_reason = "stop"
                    self.token_ids = list(range(10))
            
            class MockRequestOutput:
                def __init__(self):
                    self.outputs = [MockOutput()]
                    self.finished = True
            
            yield MockRequestOutput()
        
        mock_engine.generate = mock_generate
        mock_engine.abort = AsyncMock()
        
        yield {
            "engine_class": mock_engine_class,
            "engine": mock_engine,
            "args_class": mock_args_class,
            "sampling_class": mock_sampling_class
        }

@pytest.fixture(scope="function")
def mock_psutil():
    """psutil 모킹"""
    with patch('psutil.cpu_percent', return_value=45.0) as mock_cpu, \
         patch('psutil.virtual_memory') as mock_memory, \
         patch('psutil.disk_usage') as mock_disk, \
         patch('psutil.getloadavg', return_value=(1.0, 1.2, 1.5)) as mock_load:
        
        # 메모리 정보 모킹
        mock_memory.return_value.percent = 65.0
        mock_memory.return_value.total = 16000000000
        mock_memory.return_value.available = 5600000000
        
        # 디스크 정보 모킹
        mock_disk.return_value.percent = 30.0
        mock_disk.return_value.total = 1000000000000
        mock_disk.return_value.free = 700000000000
        
        yield {
            "cpu_percent": mock_cpu,
            "virtual_memory": mock_memory,
            "disk_usage": mock_disk,
            "getloadavg": mock_load
        }

# 데이터 생성 픽스처들
@pytest.fixture(scope="function")
def sample_generate_request():
    """샘플 생성 요청"""
    from app.models.schemas import GenerateRequest
    return GenerateRequest(
        prompt="안녕하세요! 테스트 프롬프트입니다.",
        max_tokens=100,
        temperature=0.7,
        top_p=0.9,
        top_k=50,
        repetition_penalty=1.1,
        seed=42
    )

@pytest.fixture(scope="function")
def sample_batch_request():
    """샘플 배치 요청"""
    from app.models.schemas import BatchGenerateRequest
    return BatchGenerateRequest(
        prompts=[
            "첫 번째 프롬프트",
            "두 번째 프롬프트", 
            "세 번째 프롬프트"
        ],
        max_tokens=50,
        temperature=0.8,
        top_p=0.95
    )

@pytest.fixture(scope="function")
def sample_generate_response():
    """샘플 생성 응답"""
    from app.models.schemas import GenerateResponse, FinishReason
    return GenerateResponse(
        text="안녕하세요! 저는 AI 어시스턴트입니다.",
        prompt="안녕하세요! 테스트 프롬프트입니다.",
        tokens_generated=15,
        prompt_tokens=8,
        total_tokens=23,
        finish_reason=FinishReason.STOP,
        generation_time=1.23,
        tokens_per_second=12.2,
        model_name="test-llama-model"
    )

@pytest.fixture(scope="function")
def sample_health_metrics():
    """샘플 헬스 메트릭"""
    from app.services.model_monitor import ModelHealthMetrics, ModelStatus
    import time
    
    return ModelHealthMetrics(
        status=ModelStatus.HEALTHY,
        last_check_time=time.time(),
        response_time_avg=1.5,
        response_time_p95=2.1,
        error_rate=0.02,
        memory_usage_percent=65.0,
        gpu_memory_usage_percent=75.0,
        temperature=68.0,
        throughput_tokens_per_second=32.5,
        queue_length=0,
        active_requests=3
    )

# 서비스 모킹 픽스처들
@pytest.fixture(scope="function")
def mock_vllm_service():
    """완전히 모킹된 vLLM 서비스"""
    service = Mock()
    service._initialized = True
    
    # 비동기 메서드들
    service.generate = AsyncMock(return_value={
        "text": "모킹된 응답입니다.",
        "prompt": "테스트 프롬프트",
        "tokens_generated": 12,
        "prompt_tokens": 6,
        "total_tokens": 18,
        "finish_reason": "stop",
        "generation_time": 1.1,
        "tokens_per_second": 10.9,
        "model_name": "mock-model",
        "request_id": "mock_req_001"
    })
    
    service.health_check = AsyncMock(return_value={
        "service_initialized": True,
        "engine_status": {
            "engine_initialized": True,
            "active_requests": 2,
            "uptime": 3600
        }
    })
    
    async def mock_generate_stream(request):
        """모킹된 스트림 생성"""
        chunks = [
            {"text": "안녕", "is_finished": False, "tokens_generated": 1},
            {"text": "안녕하세요", "is_finished": False, "tokens_generated": 2},
            {"text": "안녕하세요!", "is_finished": True, "finish_reason": "stop", "tokens_generated": 3}
        ]
        for chunk in chunks:
            yield chunk
    
    service.generate_stream = mock_generate_stream
    
    service.generate_batch = AsyncMock(return_value=[
        {
            "text": f"배치 응답 {i}",
            "tokens_generated": 10,
            "finish_reason": "stop"
        } for i in range(3)
    ])
    
    # 동기 메서드들
    service.get_model_info.return_value = {
        "model_name": "mock-llama-model",
        "model_path": "/tmp/mock-model",
        "tensor_parallel_size": 1,
        "initialized_at": 1699123456.789
    }
    
    service.get_stats.return_value = {
        "total_requests": 100,
        "successful_requests": 95,
        "total_tokens_generated": 5000,
        "active_requests": 2
    }
    
    service.shutdown = Mock()
    service.initialize = Mock()
    
    return service

@pytest.fixture(scope="function")
def mock_ray_service():
    """완전히 모킹된 Ray 서비스"""
    service = Mock()
    service._connected = True
    
    service.initialize.return_value = True
    service.is_connected.return_value = True
    service.shutdown = Mock()
    service.reconnect.return_value = True
    
    service.get_cluster_resources.return_value = {
        "cluster_resources": {"CPU": 8.0, "GPU": 2.0, "memory": 16000000000},
        "available_resources": {"CPU": 6.0, "GPU": 1.0, "memory": 8000000000},
        "timeline": 1699123456.789
    }
    
    service.get_cluster_status.return_value = {
        "connected": True,
        "connection_time": 2.5,
        "uptime": 3600,
        "nodes": {"total": 2, "alive": 2},
        "namespace": "test"
    }
    
    service.monitor_cluster_health.return_value = {
        "healthy": True,
        "nodes": {"total": 2, "alive": 2, "dead": 0},
        "resources": {"gpu_total": 2.0, "gpu_available": 1.0},
        "warnings": []
    }
    
    service.get_performance_metrics.return_value = {
        "cpu_utilization": 25.0,
        "gpu_utilization": 50.0,
        "memory_utilization": 50.0,
        "timestamp": 1699123456.789
    }
    
    service.submit_task.return_value = "mock_task_ref"
    service.wait_for_tasks.return_value = ([], ["mock_task_ref"])
    service.get_task_result.return_value = "mock_result"
    service.cancel_task.return_value = True
    
    return service

@pytest.fixture(scope="function")
def mock_model_monitor():
    """완전히 모킹된 모델 모니터링 서비스"""
    service = Mock()
    
    service.start_monitoring = AsyncMock()
    service.stop_monitoring = AsyncMock()
    
    service.get_current_status = AsyncMock(return_value={
        "current_status": "healthy",
        "last_check": "2024-01-15T10:30:45",
        "checks_performed": 150,
        "response_time_avg": 1.45,
        "response_time_p95": 2.1,
        "error_rate": 0.015,
        "throughput": 35.2,
        "gpu_memory_usage": 78.5,
        "gpu_temperature": 68.0,
        "active_requests": 3,
        "recent_status_distribution": {"healthy": 9, "degraded": 1},
        "alerts": []
    })
    
    service.get_historical_data = AsyncMock(return_value=[
        {
            "timestamp": 1699123456.789,
            "status": "healthy",
            "response_time_avg": 1.45,
            "error_rate": 0.015
        }
    ])
    
    service.run_health_check = AsyncMock(return_value={
        "status": "healthy",
        "timestamp": 1699123456.789,
        "metrics": {
            "response_time_avg": 1.45,
            "error_rate": 0.015,
            "memory_usage": 65.0
        }
    })
    
    return service

# 통합 픽스처 (모든 서비스 모킹)
@pytest.fixture(scope="function")
def mock_all_services(mock_vllm_service, mock_ray_service, mock_model_monitor):
    """모든 서비스 모킹"""
    with patch('app.services.vllm_engine.vllm_service', mock_vllm_service), \
         patch('app.services.ray_service.ray_service', mock_ray_service), \
         patch('app.services.model_monitor.model_monitor_service', mock_model_monitor), \
         patch('app.services.model_monitor.model_health_checker', Mock()):
        
        yield {
            "vllm": mock_vllm_service,
            "ray": mock_ray_service,
            "monitor": mock_model_monitor
        }

# 테스트 클라이언트 픽스처
@pytest.fixture(scope="function")
def test_client(mock_all_services):
    """테스트용 FastAPI 클라이언트"""
    from fastapi.testclient import TestClient
    from app.main import app
    
    # 라이프사이클 이벤트 비활성화 (테스트에서는 실제 서비스 초기화 안함)
    app.router.lifespan_context = None
    
    return TestClient(app)

# 성능 테스트용 픽스처
@pytest.fixture(scope="function")
def performance_timer():
    """성능 측정용 타이머"""
    import time
    
    class Timer:
        def __init__(self):
            self.start_time = None
            self.end_time = None
            
        def start(self):
            self.start_time = time.time()
            
        def stop(self):
            self.end_time = time.time()
            
        @property
        def elapsed(self):
            if self.start_time and self.end_time:
                return self.end_time - self.start_time
            return None
            
        def __enter__(self):
            self.start()
            return self
            
        def __exit__(self, *args):
            self.stop()
    
    return Timer()

# 데이터베이스 관련 픽스처 (향후 확장용)
@pytest.fixture(scope="function")
def mock_database():
    """모킹된 데이터베이스 (향후 사용을 위한 준비)"""
    database = {}
    
    def get_item(key):
        return database.get(key)
    
    def set_item(key, value):
        database[key] = value
    
    def delete_item(key):
        return database.pop(key, None)
    
    def clear():
        database.clear()
    
    return {
        "get": get_item,
        "set": set_item,
        "delete": delete_item,
        "clear": clear,
        "data": database
    }

# 로깅 관련 픽스처
@pytest.fixture(scope="function")
def capture_logs():
    """로그 캡처"""
    import logging
    from io import StringIO
    
    log_capture = StringIO()
    handler = logging.StreamHandler(log_capture)
    
    # 루트 로거에 핸들러 추가
    root_logger = logging.getLogger()
    root_logger.addHandler(handler)
    original_level = root_logger.level
    root_logger.setLevel(logging.DEBUG)
    
    yield log_capture
    
    # 정리
    root_logger.removeHandler(handler)
    root_logger.setLevel(original_level)

# 네트워크 모킹 픽스처
@pytest.fixture(scope="function")
def mock_http_requests():
    """HTTP 요청 모킹"""
    with patch('requests.get') as mock_get, \
         patch('requests.post') as mock_post, \
         patch('requests.put') as mock_put, \
         patch('requests.delete') as mock_delete:
        
        # 기본 응답 설정
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"status": "ok"}
        mock_response.text = "OK"
        mock_response.headers = {"Content-Type": "application/json"}
        
        mock_get.return_value = mock_response
        mock_post.return_value = mock_response
        mock_put.return_value = mock_response
        mock_delete.return_value = mock_response
        
        yield {
            "get": mock_get,
            "post": mock_post,
            "put": mock_put,
            "delete": mock_delete,
            "response": mock_response
        }

# 파일 시스템 모킹 픽스처
@pytest.fixture(scope="function")
def mock_filesystem(temp_dir):
    """파일 시스템 모킹"""
    import json
    
    def create_file(filename, content=""):
        filepath = os.path.join(temp_dir, filename)
        os.makedirs(os.path.dirname(filepath), exist_ok=True)
        with open(filepath, 'w') as f:
            f.write(content)
        return filepath
    
    def create_json_file(filename, data):
        filepath = os.path.join(temp_dir, filename)
        os.makedirs(os.path.dirname(filepath), exist_ok=True)
        with open(filepath, 'w') as f:
            json.dump(data, f)
        return filepath
    
    def read_file(filename):
        filepath = os.path.join(temp_dir, filename)
        with open(filepath, 'r') as f:
            return f.read()
    
    def file_exists(filename):
        filepath = os.path.join(temp_dir, filename)
        return os.path.exists(filepath)
    
    return {
        "create_file": create_file,
        "create_json_file": create_json_file,
        "read_file": read_file,
        "exists": file_exists,
        "temp_dir": temp_dir
    }

# 테스트 종료 시 정리
@pytest.fixture(scope="session", autouse=True)
def cleanup_after_tests():
    """테스트 세션 종료 시 정리"""
    yield
    
    # 임시 파일들 정리
    import tempfile
    import glob
    
    temp_patterns = [
        "/tmp/vllm_test_*",
        "/tmp/test-model*",
        "/tmp/ray-temp*"
    ]
    
    for pattern in temp_patterns:
        for path in glob.glob(pattern):
            try:
                if os.path.isdir(path):
                    shutil.rmtree(path, ignore_errors=True)
                else:
                    os.remove(path)
            except Exception:
                pass

# 테스트 실행 시간 측정
@pytest.fixture(autouse=True)
def test_timing(request):
    """모든 테스트의 실행 시간 자동 측정"""
    import time
    
    start_time = time.time()
    yield
    end_time = time.time()
    
    duration = end_time - start_time
    
    # 느린 테스트 경고 (5초 이상)
    if duration > 5.0:
        pytest.warnings.warn(
            f"테스트 '{request.node.name}'이 {duration:.2f}초가 걸렸습니다. "
            "@pytest.mark.slow를 추가하는 것을 고려하세요.",
            UserWarning
        )

# 메모리 사용량 모니터링 (선택적)
@pytest.fixture(scope="function")
def memory_monitor():
    """메모리 사용량 모니터링"""
    import psutil
    import gc
    
    process = psutil.Process()
    initial_memory = process.memory_info().rss
    
    yield
    
    # 가비지 컬렉션 강제 실행
    gc.collect()
    
    final_memory = process.memory_info().rss
    memory_diff = final_memory - initial_memory
    
    # 메모리 증가가 100MB 이상인 경우 경고
    if memory_diff > 100 * 1024 * 1024:
        pytest.warnings.warn(
            f"메모리 사용량이 {memory_diff / 1024 / 1024:.1f}MB 증가했습니다. "
            "메모리 누수를 확인하세요.",
            UserWarning
        )