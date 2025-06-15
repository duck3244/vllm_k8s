"""
tests/test_vllm_service.py
vLLM 서비스 테스트
"""

import pytest
import asyncio
import time
from unittest.mock import Mock, patch, AsyncMock, MagicMock
import ray

from app.services.vllm_engine import VLLMService, VLLMEngineActor
from app.models.schemas import GenerateRequest, FinishReason
from app.core.config import settings
from tests import (
    create_test_generate_request, MockVLLMEngine, async_test,
    override_settings
)

class TestVLLMEngineActor:
    """VLLMEngineActor 테스트 클래스"""
    
    @pytest.fixture
    def mock_async_engine(self):
        """모킹된 AsyncLLMEngine"""
        with patch('app.services.vllm_engine.AsyncLLMEngine') as mock_engine_class:
            mock_engine = Mock()
            mock_engine_class.from_engine_args.return_value = mock_engine
            
            # 비동기 생성 메서드 모킹
            async def mock_generate(prompt, sampling_params, request_id):
                # 가짜 출력 객체 생성
                class MockOutput:
                    def __init__(self):
                        self.text = f"Generated: {prompt}"
                        self.finish_reason = "stop"
                        self.token_ids = list(range(10))
                
                class MockRequestOutput:
                    def __init__(self):
                        self.outputs = [MockOutput()]
                        self.finished = True
                
                yield MockRequestOutput()
            
            mock_engine.generate = mock_generate
            yield mock_engine
    
    @pytest.fixture
    def actor_instance(self, mock_async_engine):
        """VLLMEngineActor 인스턴스"""
        with patch('app.services.vllm_engine.AsyncEngineArgs'):
            actor = VLLMEngineActor()
            actor.engine = mock_async_engine
            return actor
    
    def test_actor_initialization(self, mock_async_engine):
        """Actor 초기화 테스트"""
        with patch('app.services.vllm_engine.AsyncEngineArgs'):
            actor = VLLMEngineActor()
            
            assert actor.engine is not None
            assert actor.request_id_counter == 0
            assert actor.active_requests == {}
            assert "start_time" in actor.stats

    def test_create_sampling_params(self, actor_instance):
        """샘플링 파라미터 생성 테스트"""
        request = create_test_generate_request(
            temperature=0.8,
            top_p=0.9,
            max_tokens=100
        )
        
        with patch('app.services.vllm_engine.SamplingParams') as mock_params:
            actor_instance._create_sampling_params(request)
            
            mock_params.assert_called_once_with(
                temperature=0.8,
                top_p=0.9,
                top_k=50,
                max_tokens=100,
                repetition_penalty=1.0,
                frequency_penalty=0.0,
                presence_penalty=0.0,
                stop=None,
                seed=None
            )

    def test_generate_request_id(self, actor_instance):
        """요청 ID 생성 테스트"""
        id1 = actor_instance._generate_request_id()
        id2 = actor_instance._generate_request_id()
        
        assert id1 != id2
        assert id1.startswith("req_1_")
        assert id2.startswith("req_2_")

    def test_calculate_tokens(self, actor_instance):
        """토큰 수 계산 테스트"""
        text = "이것은 테스트 문장입니다"
        tokens = actor_instance._calculate_tokens(text)
        
        assert isinstance(tokens, int)
        assert tokens > 0

    @async_test
    async def test_generate_success(self, actor_instance):
        """텍스트 생성 성공 테스트"""
        request = create_test_generate_request(prompt="안녕하세요")
        
        result = await actor_instance.generate(request)
        
        assert "text" in result
        assert "prompt" in result
        assert "tokens_generated" in result
        assert "finish_reason" in result
        assert result["prompt"] == "안녕하세요"
        assert result["finish_reason"] == FinishReason.STOP

    @async_test
    async def test_generate_stream(self, actor_instance):
        """스트리밍 생성 테스트"""
        request = create_test_generate_request(prompt="스트리밍 테스트")
        
        chunks = []
        async for chunk in actor_instance.generate_stream(request):
            chunks.append(chunk)
        
        assert len(chunks) > 0
        final_chunk = chunks[-1]
        assert final_chunk["is_finished"] is True

    @async_test
    async def test_generate_batch(self, actor_instance):
        """배치 생성 테스트"""
        requests = [
            create_test_generate_request(prompt=f"프롬프트 {i}")
            for i in range(3)
        ]
        
        results = await actor_instance.generate_batch(requests)
        
        assert len(results) == 3
        for result in results:
            if not isinstance(result, Exception):
                assert "text" in result
                assert "prompt" in result

    def test_map_finish_reason(self, actor_instance):
        """완료 이유 매핑 테스트"""
        assert actor_instance._map_finish_reason("stop") == FinishReason.STOP
        assert actor_instance._map_finish_reason("length") == FinishReason.LENGTH
        assert actor_instance._map_finish_reason("unknown") == FinishReason.STOP

    @async_test
    async def test_health_check(self, actor_instance):
        """헬스체크 테스트"""
        health = await actor_instance.health_check()
        
        assert "engine_initialized" in health
        assert "active_requests" in health
        assert "uptime" in health
        assert "stats" in health
        assert health["engine_initialized"] is True

    def test_get_model_info(self, actor_instance):
        """모델 정보 조회 테스트"""
        info = actor_instance.get_model_info()
        
        assert "model_name" in info
        assert "model_path" in info
        assert "initialized_at" in info

    def test_get_stats(self, actor_instance):
        """통계 정보 조회 테스트"""
        stats = actor_instance.get_stats()
        
        assert "total_requests" in stats
        assert "successful_requests" in stats
        assert "uptime" in stats
        assert "active_requests" in stats

    @async_test
    async def test_abort_request(self, actor_instance):
        """요청 중단 테스트"""
        # 모킹된 abort 메서드
        actor_instance.engine.abort = AsyncMock()
        
        # 활성 요청 추가
        request_id = "test_req_001"
        actor_instance.active_requests[request_id] = {"start_time": time.time()}
        
        result = await actor_instance.abort_request(request_id)
        
        assert result is True
        assert request_id not in actor_instance.active_requests

class TestVLLMService:
    """VLLMService 테스트 클래스"""
    
    @pytest.fixture
    def service(self):
        """VLLMService 인스턴스"""
        return VLLMService()
    
    @pytest.fixture
    def mock_ray_actor(self):
        """모킹된 Ray Actor"""
        with patch('ray.get') as mock_get, \
             patch('app.services.vllm_engine.VLLMEngineActor') as mock_actor_class:
            
            mock_actor = Mock()
            mock_actor_class.remote.return_value = mock_actor
            
            # Ray.get 반환값 설정
            mock_get.side_effect = lambda x: {
                "engine_initialized": True,
                "active_requests": 0,
                "uptime": 100.0
            } if hasattr(x, 'health_check') else x
            
            yield mock_actor

    def test_service_initialization(self, service):
        """서비스 초기화 테스트"""
        assert service.engine_actor is None
        assert service._initialized is False

    def test_initialize_success(self, service, mock_ray_actor):
        """서비스 초기화 성공 테스트"""
        with patch('ray.get') as mock_get:
            mock_get.return_value = {"engine_initialized": True}
            
            service.initialize()
            
            assert service._initialized is True
            assert service.engine_actor is not None

    def test_initialize_failure(self, service, mock_ray_actor):
        """서비스 초기화 실패 테스트"""
        with patch('ray.get') as mock_get:
            mock_get.return_value = {"engine_initialized": False}
            
            with pytest.raises(RuntimeError, match="vLLM 엔진 초기화 실패"):
                service.initialize()

    @async_test
    async def test_generate_not_initialized(self, service):
        """초기화되지 않은 상태에서 생성 요청 테스트"""
        request = create_test_generate_request()
        
        with pytest.raises(RuntimeError, match="vLLM 서비스가 초기화되지 않았습니다"):
            await service.generate(request)

    @async_test
    async def test_generate_success(self, service, mock_ray_actor):
        """생성 요청 성공 테스트"""
        service._initialized = True
        service.engine_actor = mock_ray_actor
        
        with patch('ray.get') as mock_get:
            mock_get.return_value = {
                "text": "테스트 응답",
                "prompt": "테스트",
                "tokens_generated": 10,
                "finish_reason": FinishReason.STOP
            }
            
            request = create_test_generate_request()
            result = await service.generate(request)
            
            assert "text" in result
            assert result["text"] == "테스트 응답"

    @async_test
    async def test_generate_stream_success(self, service, mock_ray_actor):
        """스트리밍 생성 성공 테스트"""
        service._initialized = True
        service.engine_actor = mock_ray_actor
        
        # AsyncGenerator 모킹
        async def mock_stream():
            yield {"text": "부분1", "is_finished": False}
            yield {"text": "부분1 부분2", "is_finished": True}
        
        with patch('ray.get', side_effect=lambda x: x):
            mock_ray_actor.generate_stream.remote.return_value = mock_stream()
            
            request = create_test_generate_request()
            chunks = []
            
            async for chunk in service.generate_stream(request):
                chunks.append(chunk)
            
            assert len(chunks) == 2
            assert chunks[-1]["is_finished"] is True

    @async_test
    async def test_generate_batch_success(self, service, mock_ray_actor):
        """배치 생성 성공 테스트"""
        service._initialized = True
        service.engine_actor = mock_ray_actor
        
        with patch('ray.get') as mock_get:
            mock_get.return_value = [
                {"text": f"응답 {i}", "tokens_generated": 10}
                for i in range(3)
            ]
            
            requests = [create_test_generate_request() for _ in range(3)]
            results = await service.generate_batch(requests)
            
            assert len(results) == 3
            for i, result in enumerate(results):
                assert result["text"] == f"응답 {i}"

    @async_test
    async def test_health_check_not_initialized(self, service):
        """초기화되지 않은 상태 헬스체크 테스트"""
        health = await service.health_check()
        
        assert health["service_initialized"] is False
        assert health["engine_status"] is None

    @async_test
    async def test_health_check_initialized(self, service, mock_ray_actor):
        """초기화된 상태 헬스체크 테스트"""
        service._initialized = True
        service.engine_actor = mock_ray_actor
        
        with patch('ray.get') as mock_get:
            mock_get.return_value = {
                "engine_initialized": True,
                "active_requests": 2,
                "uptime": 3600
            }
            
            health = await service.health_check()
            
            assert health["service_initialized"] is True
            assert health["engine_status"]["engine_initialized"] is True

    def test_get_model_info_not_initialized(self, service):
        """초기화되지 않은 상태 모델 정보 조회 테스트"""
        info = service.get_model_info()
        assert info is None

    def test_get_model_info_success(self, service, mock_ray_actor):
        """모델 정보 조회 성공 테스트"""
        service._initialized = True
        service.engine_actor = mock_ray_actor
        
        with patch('ray.get') as mock_get:
            mock_get.return_value = {
                "model_name": "test-model",
                "model_path": "/test/model",
                "initialized_at": time.time()
            }
            
            info = service.get_model_info()
            
            assert info["model_name"] == "test-model"
            assert "model_path" in info

    def test_get_stats_not_initialized(self, service):
        """초기화되지 않은 상태 통계 조회 테스트"""
        stats = service.get_stats()
        assert stats is None

    def test_get_stats_success(self, service, mock_ray_actor):
        """통계 조회 성공 테스트"""
        service._initialized = True
        service.engine_actor = mock_ray_actor
        
        with patch('ray.get') as mock_get:
            mock_get.return_value = {
                "total_requests": 100,
                "successful_requests": 95,
                "total_tokens_generated": 5000
            }
            
            stats = service.get_stats()
            
            assert stats["total_requests"] == 100
            assert stats["successful_requests"] == 95

    def test_shutdown_not_initialized(self, service):
        """초기화되지 않은 상태 종료 테스트"""
        # 오류 없이 실행되어야 함
        service.shutdown()

    def test_shutdown_success(self, service, mock_ray_actor):
        """서비스 종료 성공 테스트"""
        service._initialized = True
        service.engine_actor = mock_ray_actor
        
        with patch('ray.kill') as mock_kill:
            service.shutdown()
            
            mock_kill.assert_called_once_with(mock_ray_actor)
            assert service._initialized is False

class TestVLLMServiceIntegration:
    """VLLMService 통합 테스트"""
    
    @pytest.mark.integration
    def test_full_workflow(self):
        """전체 워크플로우 통합 테스트"""
        with patch('ray.init'), \
             patch('ray.is_initialized', return_value=True), \
             patch('app.services.vllm_engine.AsyncLLMEngine'):
            
            service = VLLMService()
            
            # 초기화
            with patch('ray.get', return_value={"engine_initialized": True}):
                service.initialize()
                assert service._initialized is True
            
            # 헬스체크
            with patch('ray.get', return_value={"engine_initialized": True}):
                health = asyncio.run(service.health_check())
                assert health["service_initialized"] is True
            
            # 종료
            with patch('ray.kill'):
                service.shutdown()
                assert service._initialized is False

    @pytest.mark.slow
    def test_performance_under_load(self):
        """부하 상황에서의 성능 테스트"""
        with patch('ray.init'), \
             patch('ray.is_initialized', return_value=True), \
             patch('app.services.vllm_engine.AsyncLLMEngine'):
            
            service = VLLMService()
            
            with patch('ray.get') as mock_get:
                # 초기화
                mock_get.return_value = {"engine_initialized": True}
                service.initialize()
                
                # 동시 요청 시뮬레이션
                async def simulate_concurrent_requests():
                    mock_get.return_value = {
                        "text": "응답",
                        "tokens_generated": 10,
                        "finish_reason": FinishReason.STOP
                    }
                    
                    tasks = []
                    for i in range(10):
                        request = create_test_generate_request(prompt=f"요청 {i}")
                        task = service.generate(request)
                        tasks.append(task)
                    
                    results = await asyncio.gather(*tasks, return_exceptions=True)
                    return results
                
                results = asyncio.run(simulate_concurrent_requests())
                
                # 모든 요청이 성공적으로 처리되었는지 확인
                successful_results = [r for r in results if not isinstance(r, Exception)]
                assert len(successful_results) == 10

class TestErrorHandling:
    """오류 처리 테스트"""
    
    def test_engine_initialization_error(self):
        """엔진 초기화 오류 테스트"""
        with patch('app.services.vllm_engine.AsyncLLMEngine') as mock_engine:
            mock_engine.from_engine_args.side_effect = Exception("GPU 메모리 부족")
            
            with pytest.raises(Exception, match="GPU 메모리 부족"):
                VLLMEngineActor()

    @async_test
    async def test_generation_error_handling(self):
        """생성 중 오류 처리 테스트"""
        with patch('app.services.vllm_engine.AsyncEngineArgs'), \
             patch('app.services.vllm_engine.AsyncLLMEngine') as mock_engine_class:
            
            mock_engine = Mock()
            mock_engine_class.from_engine_args.return_value = mock_engine
            
            # 생성 중 오류 발생 시뮬레이션
            async def error_generator(*args, **kwargs):
                raise Exception("생성 중 오류 발생")
            
            mock_engine.generate = error_generator
            
            actor = VLLMEngineActor()
            request = create_test_generate_request()
            
            with pytest.raises(Exception, match="생성 중 오류 발생"):
                await actor.generate(request)
            
            # 실패 통계가 업데이트되었는지 확인
            assert actor.stats["failed_requests"] > 0

    def test_ray_connection_error(self):
        """Ray 연결 오류 테스트"""
        service = VLLMService()
        
        with patch('app.services.vllm_engine.VLLMEngineActor') as mock_actor:
            mock_actor.remote.side_effect = Exception("Ray 클러스터 연결 실패")
            
            with pytest.raises(Exception):
                service.initialize()

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
                