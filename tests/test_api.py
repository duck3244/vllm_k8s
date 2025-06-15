"""
tests/test_api.py
API 엔드포인트 테스트
"""

import pytest
import asyncio
from unittest.mock import Mock, patch, AsyncMock
from fastapi.testclient import TestClient
from fastapi import status
import json

from app.main import app
from app.models.schemas import (
    GenerateRequest, BatchGenerateRequest, FinishReason
)
from tests import (
    create_test_generate_request, create_test_batch_request,
    MockVLLMEngine, override_settings
)

class TestAPIEndpoints:
    """API 엔드포인트 테스트 클래스"""
    
    @pytest.fixture
    def client(self):
        """테스트 클라이언트 픽스처"""
        return TestClient(app)
    
    @pytest.fixture
    def mock_services(self):
        """모킹된 서비스들 픽스처"""
        with patch('app.services.vllm_engine.vllm_service') as mock_vllm, \
             patch('app.services.ray_service.ray_service') as mock_ray, \
             patch('app.services.model_monitor.model_monitor_service') as mock_monitor:
            
            # vLLM 서비스 모킹
            mock_vllm._initialized = True
            mock_vllm.generate = AsyncMock(return_value={
                "text": "테스트 응답입니다.",
                "prompt": "테스트 프롬프트",
                "tokens_generated": 10,
                "prompt_tokens": 5,
                "total_tokens": 15,
                "finish_reason": FinishReason.STOP,
                "generation_time": 1.5,
                "tokens_per_second": 6.67,
                "model_name": "test-model",
                "request_id": "test_req_001"
            })
            
            # Ray 서비스 모킹
            mock_ray.is_connected.return_value = True
            mock_ray.get_cluster_status.return_value = {
                "connected": True,
                "nodes": {"total": 1, "alive": 1}
            }
            
            # 모니터 서비스 모킹
            mock_monitor.get_current_status = AsyncMock(return_value={
                "current_status": "healthy",
                "last_check": "2024-01-15T10:30:45",
                "checks_performed": 100,
                "response_time_avg": 1.5,
                "response_time_p95": 2.0,
                "error_rate": 0.01,
                "throughput": 30.0,
                "gpu_memory_usage": 75.0,
                "gpu_temperature": 65.0,
                "active_requests": 2,
                "recent_status_distribution": {"healthy": 9, "degraded": 1},
                "alerts": []
            })
            
            yield {
                "vllm": mock_vllm,
                "ray": mock_ray,
                "monitor": mock_monitor
            }

    def test_root_endpoint(self, client):
        """루트 엔드포인트 테스트"""
        response = client.get("/")
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        
        assert "message" in data
        assert "version" in data
        assert "status" in data
        assert data["status"] == "running"

    def test_health_check(self, client, mock_services):
        """헬스체크 엔드포인트 테스트"""
        with patch('app.api.routes.get_health_status') as mock_health:
            mock_health.return_value = {
                "overall_status": "healthy",
                "services": {
                    "vllm": {"service_initialized": True},
                    "ray": {"connected": True}
                }
            }
            
            response = client.get("/api/v1/health")
            
            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            
            assert data["status"] in ["healthy", "unhealthy"]
            assert isinstance(data["model_loaded"], bool)
            assert isinstance(data["ray_connected"], bool)
            assert isinstance(data["gpu_available"], bool)

    def test_simple_health_check(self, client):
        """간단한 헬스체크 테스트"""
        response = client.get("/health")
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        
        assert data["status"] == "ok"
        assert "timestamp" in data

    def test_generate_text_success(self, client, mock_services):
        """텍스트 생성 성공 테스트"""
        request_data = {
            "prompt": "안녕하세요",
            "max_tokens": 100,
            "temperature": 0.7
        }
        
        response = client.post("/api/v1/generate", json=request_data)
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        
        assert "text" in data
        assert "prompt" in data
        assert "tokens_generated" in data
        assert "finish_reason" in data
        assert data["prompt"] == request_data["prompt"]

    def test_generate_text_validation_error(self, client):
        """텍스트 생성 검증 오류 테스트"""
        # 빈 프롬프트
        response = client.post("/api/v1/generate", json={"prompt": ""})
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
        
        # 너무 긴 프롬프트
        long_prompt = "a" * 10000
        response = client.post("/api/v1/generate", json={"prompt": long_prompt})
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
        
        # 잘못된 temperature 값
        response = client.post("/api/v1/generate", json={
            "prompt": "test",
            "temperature": 3.0  # 최대 2.0
        })
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    def test_generate_batch_success(self, client, mock_services):
        """배치 생성 성공 테스트"""
        mock_services["vllm"].generate_batch = AsyncMock(return_value=[
            {
                "text": f"응답 {i}",
                "prompt": f"프롬프트 {i}",
                "tokens_generated": 10,
                "prompt_tokens": 5,
                "total_tokens": 15,
                "finish_reason": FinishReason.STOP,
                "generation_time": 1.0,
                "tokens_per_second": 10.0,
                "model_name": "test-model"
            } for i in range(3)
        ])
        
        request_data = {
            "prompts": ["프롬프트 1", "프롬프트 2", "프롬프트 3"],
            "max_tokens": 50,
            "temperature": 0.5
        }
        
        response = client.post("/api/v1/generate/batch", json=request_data)
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        
        assert "responses" in data
        assert "total_time" in data
        assert "request_count" in data
        assert len(data["responses"]) == 3

    def test_generate_batch_validation_error(self, client):
        """배치 생성 검증 오류 테스트"""
        # 빈 프롬프트 리스트
        response = client.post("/api/v1/generate/batch", json={"prompts": []})
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
        
        # 너무 많은 프롬프트 (최대 10개)
        too_many_prompts = [f"프롬프트 {i}" for i in range(15)]
        response = client.post("/api/v1/generate/batch", json={"prompts": too_many_prompts})
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    def test_model_info(self, client, mock_services):
        """모델 정보 조회 테스트"""
        mock_services["vllm"].get_model_info.return_value = {
            "model_name": "test-model",
            "model_path": "/test/model",
            "tensor_parallel_size": 1,
            "gpu_memory_utilization": 0.9,
            "max_model_len": 4096,
            "dtype": "half",
            "initialized_at": 1699123456.789
        }
        
        response = client.get("/api/v1/model-info")
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        
        assert "model_name" in data
        assert "model_path" in data
        assert "tensor_parallel_size" in data

    def test_usage_stats(self, client, mock_services):
        """사용 통계 조회 테스트"""
        with patch('app.api.routes.get_metrics') as mock_metrics:
            mock_metrics.return_value = {
                "requests_total": 100,
                "requests_successful": 95,
                "requests_failed": 5,
                "average_response_time": 2.5,
                "uptime": 3600
            }
            
            mock_services["vllm"].get_stats.return_value = {
                "total_tokens_generated": 5000,
                "total_prompt_tokens": 2500
            }
            
            response = client.get("/api/v1/stats")
            
            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            
            assert "total_requests" in data
            assert "successful_requests" in data
            assert "total_tokens_generated" in data

    def test_cluster_status(self, client, mock_services):
        """클러스터 상태 조회 테스트"""
        response = client.get("/api/v1/cluster/status")
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        
        assert "connected" in data

    def test_model_status(self, client, mock_services):
        """모델 상태 조회 테스트"""
        response = client.get("/api/v1/model/status")
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        
        assert "status" in data
        assert "response_time_avg" in data
        assert "error_rate" in data

    def test_model_health_check(self, client, mock_services):
        """모델 헬스체크 테스트"""
        mock_services["monitor"].run_health_check = AsyncMock(return_value={
            "status": "healthy",
            "timestamp": 1699123456.789,
            "metrics": {
                "response_time_avg": 1.5,
                "error_rate": 0.01,
                "memory_usage": 65.0
            }
        })
        
        response = client.post("/api/v1/model/health-check", json={})
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        
        assert "status" in data
        assert "metrics" in data

    def test_system_metrics(self, client, mock_services):
        """시스템 메트릭 조회 테스트"""
        with patch('app.api.routes.model_health_checker') as mock_checker:
            mock_checker.get_system_metrics.return_value = Mock(
                cpu_usage_percent=45.0,
                memory_usage_percent=65.0,
                disk_usage_percent=30.0,
                load_average=(1.2, 1.5, 1.8),
                gpu_utilization=75.0,
                gpu_memory_total=12884901888,
                gpu_memory_used=9663676416,
                gpu_temperature=70.0
            )
            
            response = client.get("/api/v1/model/metrics/system")
            
            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            
            assert "cpu_usage_percent" in data
            assert "memory_usage_percent" in data
            assert "gpu_utilization" in data

    @override_settings(API_KEY_ENABLED=True, API_KEY="test-api-key")
    def test_api_key_authentication(self, client, mock_services):
        """API 키 인증 테스트"""
        # API 키 없이 요청
        response = client.post("/api/v1/generate", json={"prompt": "test"})
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
        
        # 잘못된 API 키로 요청
        headers = {"Authorization": "Bearer wrong-key"}
        response = client.post("/api/v1/generate", json={"prompt": "test"}, headers=headers)
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
        
        # 올바른 API 키로 요청
        headers = {"Authorization": "Bearer test-api-key"}
        response = client.post("/api/v1/generate", json={"prompt": "test"}, headers=headers)
        assert response.status_code == status.HTTP_200_OK

    def test_rate_limiting(self, client, mock_services):
        """Rate Limiting 테스트"""
        with patch('app.api.dependencies.rate_limiter') as mock_limiter:
            # 첫 번째 요청은 허용
            mock_limiter.is_allowed.return_value = True
            response = client.post("/api/v1/generate", json={"prompt": "test"})
            assert response.status_code == status.HTTP_200_OK
            
            # Rate limit 초과 시뮬레이션
            mock_limiter.is_allowed.return_value = False
            response = client.post("/api/v1/generate", json={"prompt": "test"})
            assert response.status_code == status.HTTP_429_TOO_MANY_REQUESTS

    def test_cors_headers(self, client):
        """CORS 헤더 테스트"""
        response = client.options("/api/v1/generate", headers={
            "Origin": "http://localhost:3000",
            "Access-Control-Request-Method": "POST"
        })
        
        assert "access-control-allow-origin" in response.headers

    def test_error_handling(self, client, mock_services):
        """오류 처리 테스트"""
        # vLLM 서비스 오류 시뮬레이션
        mock_services["vllm"].generate.side_effect = Exception("vLLM 오류")
        
        response = client.post("/api/v1/generate", json={"prompt": "test"})
        
        assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
        data = response.json()
        assert "error" in data

    def test_metrics_endpoint(self, client):
        """메트릭 엔드포인트 테스트"""
        with patch('app.api.dependencies.metrics_collector') as mock_collector:
            mock_collector.get_metrics.return_value = {
                "requests_total": 100,
                "requests_successful": 95,
                "tokens_generated": 5000,
                "uptime": 3600
            }
            
            response = client.get("/metrics")
            
            assert response.status_code == status.HTTP_200_OK
            assert response.headers["content-type"] == "text/plain; charset=utf-8"
            assert "vllm_requests_total" in response.text

    def test_content_type_validation(self, client):
        """Content-Type 검증 테스트"""
        # 잘못된 Content-Type
        response = client.post(
            "/api/v1/generate",
            data="not json",
            headers={"Content-Type": "text/plain"}
        )
        assert response.status_code == status.HTTP_415_UNSUPPORTED_MEDIA_TYPE

    def test_request_size_limit(self, client):
        """요청 크기 제한 테스트"""
        # 매우 큰 요청 시뮬레이션
        large_prompt = "a" * (11 * 1024 * 1024)  # 11MB
        
        with patch('app.api.dependencies.check_request_size') as mock_check:
            from fastapi import HTTPException
            mock_check.side_effect = HTTPException(
                status_code=413,
                detail="요청 크기가 너무 큽니다"
            )
            
            response = client.post("/api/v1/generate", json={"prompt": large_prompt})
            assert response.status_code == status.HTTP_413_REQUEST_ENTITY_TOO_LARGE

class TestStreamingEndpoint:
    """스트리밍 엔드포인트 테스트"""
    
    @pytest.fixture
    def client(self):
        return TestClient(app)
    
    def test_streaming_response(self, client):
        """스트리밍 응답 테스트"""
        with patch('app.services.vllm_engine.vllm_service') as mock_vllm:
            # AsyncGenerator 모킹
            async def mock_stream():
                yield {"text": "안녕", "is_finished": False, "tokens_generated": 1}
                yield {"text": "안녕하세요", "is_finished": False, "tokens_generated": 2}
                yield {"text": "안녕하세요!", "is_finished": True, "finish_reason": "stop", "tokens_generated": 3}
            
            mock_vllm._initialized = True
            mock_vllm.generate_stream.return_value = mock_stream()
            
            response = client.post("/api/v1/generate/stream", json={"prompt": "안녕"})
            
            assert response.status_code == status.HTTP_200_OK
            assert "text/event-stream" in response.headers.get("content-type", "")

class TestAdminEndpoints:
    """관리자 엔드포인트 테스트"""
    
    @pytest.fixture
    def client(self):
        return TestClient(app)
    
    @override_settings(API_KEY_ENABLED=True, API_KEY="admin-key")
    def test_shutdown_endpoint(self, client):
        """서비스 종료 엔드포인트 테스트"""
        with patch('app.services.vllm_engine.vllm_service') as mock_vllm, \
             patch('app.services.ray_service.ray_service') as mock_ray:
            
            headers = {"Authorization": "Bearer admin-key"}
            response = client.post("/api/v1/admin/shutdown", headers=headers)
            
            assert response.status_code == status.HTTP_200_OK
            mock_vllm.shutdown.assert_called_once()
            mock_ray.shutdown.assert_called_once()

    @override_settings(API_KEY_ENABLED=True, API_KEY="admin-key")
    def test_reload_endpoint(self, client):
        """서비스 재시작 엔드포인트 테스트"""
        with patch('app.services.ray_service.ray_service') as mock_ray, \
             patch('app.services.vllm_engine.vllm_service') as mock_vllm:
            
            mock_ray.reconnect.return_value = True
            
            headers = {"Authorization": "Bearer admin-key"}
            response = client.post("/api/v1/admin/reload", headers=headers)
            
            assert response.status_code == status.HTTP_200_OK
            mock_ray.reconnect.assert_called_once()
            mock_vllm.initialize.assert_called_once()

if __name__ == "__main__":
    pytest.main([__file__, "-v"])