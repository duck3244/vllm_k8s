"""
tests/test_model_monitor.py
모델 모니터링 서비스 테스트
"""

import pytest
import asyncio
import time
from unittest.mock import Mock, patch, AsyncMock, MagicMock
from dataclasses import asdict

from app.services.model_monitor import (
    ModelHealthChecker, ModelMonitorService, ModelStatus, 
    ModelHealthMetrics, SystemHealthMetrics, model_health_checker, model_monitor_service
)
from app.models.schemas import GenerateRequest
from tests import create_test_generate_request, async_test, MockVLLMEngine

class TestModelHealthChecker:
    """ModelHealthChecker 테스트 클래스"""
    
    @pytest.fixture
    def health_checker(self):
        """ModelHealthChecker 인스턴스"""
        return ModelHealthChecker(check_interval=10)
    
    @pytest.fixture
    def mock_vllm_service(self):
        """모킹된 vLLM 서비스"""
        service = Mock()
        service.generate = AsyncMock(return_value={
            "text": "테스트 응답",
            "tokens_generated": 10,
            "generation_time": 1.5
        })
        service.health_check = AsyncMock(return_value={
            "service_initialized": True,
            "engine_status": {"engine_initialized": True}
        })
        service.get_stats.return_value = {
            "active_requests": 2,
            "total_tokens_generated": 5000
        }
        return service

    def test_health_checker_initialization(self, health_checker):
        """헬스 체커 초기화 테스트"""
        assert health_checker.check_interval == 10
        assert health_checker.response_times == []
        assert health_checker.error_count == 0
        assert health_checker.request_count == 0
        assert health_checker.health_history == []
        assert health_checker.max_history_size == 100

    def test_record_request_metrics_success(self, health_checker):
        """성공 요청 메트릭 기록 테스트"""
        health_checker.record_request_metrics(
            response_time=1.5,
            success=True,
            tokens_generated=10
        )
        
        assert len(health_checker.response_times) == 1
        assert health_checker.response_times[0] == 1.5
        assert health_checker.request_count == 1
        assert health_checker.error_count == 0

    def test_record_request_metrics_failure(self, health_checker):
        """실패 요청 메트릭 기록 테스트"""
        health_checker.record_request_metrics(
            response_time=5.0,
            success=False
        )
        
        assert len(health_checker.response_times) == 1
        assert health_checker.request_count == 1
        assert health_checker.error_count == 1

    def test_record_request_metrics_overflow(self, health_checker):
        """메트릭 오버플로우 테스트 (최대 100개 유지)"""
        # 150개 요청 기록
        for i in range(150):
            health_checker.record_request_metrics(
                response_time=float(i),
                success=True
            )
        
        # 최대 100개만 유지되는지 확인
        assert len(health_checker.response_times) == 100
        # 가장 오래된 50개가 제거되었는지 확인
        assert health_checker.response_times[0] == 50.0

    @patch('torch.cuda.is_available')
    @patch('torch.cuda.mem_get_info')
    def test_get_gpu_metrics_available(self, mock_mem_info, mock_cuda_available, health_checker):
        """GPU 사용 가능한 경우 메트릭 수집 테스트"""
        mock_cuda_available.return_value = True
        mock_mem_info.return_value = (4000000000, 8000000000)  # (free, total)
        
        with patch('pynvml.nvmlInit'), \
             patch('pynvml.nvmlDeviceGetHandleByIndex'), \
             patch('pynvml.nvmlDeviceGetTemperature', return_value=75.0), \
             patch('pynvml.nvmlDeviceGetUtilizationRates') as mock_util:
            
            mock_util.return_value.gpu = 80.0
            
            metrics = health_checker.get_gpu_metrics()
            
            assert metrics["gpu_utilization"] == 80.0
            assert metrics["gpu_memory_total"] == 8000000000
            assert metrics["gpu_memory_used"] == 4000000000
            assert metrics["gpu_memory_percent"] == 50.0
            assert metrics["gpu_temperature"] == 75.0

    @patch('torch.cuda.is_available')
    def test_get_gpu_metrics_not_available(self, mock_cuda_available, health_checker):
        """GPU 사용 불가능한 경우 메트릭 수집 테스트"""
        mock_cuda_available.return_value = False
        
        metrics = health_checker.get_gpu_metrics()
        
        assert all(value is None for value in metrics.values())

    @patch('psutil.cpu_percent')
    @patch('psutil.virtual_memory')
    @patch('psutil.disk_usage')
    @patch('psutil.getloadavg')
    def test_get_system_metrics(self, mock_load, mock_disk, mock_memory, mock_cpu, health_checker):
        """시스템 메트릭 수집 테스트"""
        mock_cpu.return_value = 45.0
        mock_memory.return_value.percent = 65.0
        mock_disk.return_value.percent = 30.0
        mock_load.return_value = (1.2, 1.5, 1.8)
        
        with patch.object(health_checker, 'get_gpu_metrics', return_value={
            "gpu_utilization": 75.0,
            "gpu_memory_total": 8000000000,
            "gpu_memory_used": 6000000000,
            "gpu_temperature": 70.0
        }):
            metrics = health_checker.get_system_metrics()
            
            assert metrics.cpu_usage_percent == 45.0
            assert metrics.memory_usage_percent == 65.0
            assert metrics.disk_usage_percent == 30.0
            assert metrics.load_average == (1.2, 1.5, 1.8)
            assert metrics.gpu_utilization == 75.0

    def test_calculate_response_time_percentiles_empty(self, health_checker):
        """빈 응답 시간 리스트의 백분위수 계산 테스트"""
        percentiles = health_checker.calculate_response_time_percentiles()
        
        assert percentiles["avg"] == 0.0
        assert percentiles["p50"] == 0.0
        assert percentiles["p95"] == 0.0
        assert percentiles["p99"] == 0.0

    def test_calculate_response_time_percentiles_with_data(self, health_checker):
        """데이터가 있는 응답 시간 백분위수 계산 테스트"""
        # 1.0초부터 10.0초까지 10개 샘플
        health_checker.response_times = [float(i) for i in range(1, 11)]
        
        percentiles = health_checker.calculate_response_time_percentiles()
        
        assert percentiles["avg"] == 5.5
        assert percentiles["p50"] == 5.0
        assert percentiles["p95"] == 10.0
        assert percentiles["p99"] == 10.0

    def test_determine_model_status_healthy(self, health_checker):
        """정상 상태 판단 테스트"""
        metrics = {
            "response_time_p95": 2.0,  # 임계값 5.0 미만
            "error_rate": 0.01,  # 임계값 0.05 미만
            "gpu_memory_usage_percent": 70.0,  # 임계값 90.0 미만
            "temperature": 65.0  # 임계값 80.0 미만
        }
        
        status = health_checker.determine_model_status(metrics)
        assert status == ModelStatus.HEALTHY

    def test_determine_model_status_degraded(self, health_checker):
        """성능 저하 상태 판단 테스트"""
        metrics = {
            "response_time_p95": 7.0,  # 경고 임계값 초과, 크리티컬 미만
            "error_rate": 0.08,  # 경고 임계값 초과, 크리티컬 미만
            "gpu_memory_usage_percent": 85.0,  # 경고 임계값 초과
            "temperature": 75.0  # 정상 범위
        }
        
        status = health_checker.determine_model_status(metrics)
        assert status == ModelStatus.DEGRADED

    def test_determine_model_status_unhealthy(self, health_checker):
        """비정상 상태 판단 테스트"""
        metrics = {
            "response_time_p95": 15.0,  # 크리티컬 임계값 초과
            "error_rate": 0.20,  # 크리티컬 임계값 초과
            "gpu_memory_usage_percent": 99.0,  # 크리티컬 임계값 초과
            "temperature": 95.0  # 크리티컬 임계값 초과
        }
        
        status = health_checker.determine_model_status(metrics)
        assert status == ModelStatus.UNHEALTHY

    @async_test
    async def test_perform_health_check_success(self, health_checker, mock_vllm_service):
        """헬스체크 수행 성공 테스트"""
        # 일부 메트릭 데이터 설정
        health_checker.response_times = [1.0, 1.5, 2.0]
        health_checker.request_count = 10
        health_checker.error_count = 1
        
        with patch.object(health_checker, 'get_system_metrics') as mock_system:
            mock_system.return_value = SystemHealthMetrics(
                cpu_usage_percent=45.0,
                memory_usage_percent=65.0,
                disk_usage_percent=30.0,
                gpu_utilization=75.0,
                gpu_memory_total=8000000000,
                gpu_memory_used=6000000000,
                gpu_temperature=70.0,
                load_average=(1.2, 1.5, 1.8)
            )
            
            with patch.object(health_checker, 'get_gpu_metrics') as mock_gpu:
                mock_gpu.return_value = {
                    "gpu_memory_percent": 75.0,
                    "gpu_temperature": 70.0
                }
                
                metrics =