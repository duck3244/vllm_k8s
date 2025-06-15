"""
tests/test_ray_service.py
Ray 서비스 테스트
"""

import pytest
import time
from unittest.mock import Mock, patch, MagicMock
import ray

from app.services.ray_service import RayClusterService, RayTaskManager
from app.core.config import settings
from tests import MockRayCluster, override_settings

class TestRayClusterService:
    """RayClusterService 테스트 클래스"""
    
    @pytest.fixture
    def service(self):
        """RayClusterService 인스턴스"""
        return RayClusterService()
    
    @pytest.fixture
    def mock_ray_functions(self):
        """Ray 함수들 모킹"""
        with patch('ray.init') as mock_init, \
             patch('ray.is_initialized') as mock_is_init, \
             patch('ray.cluster_resources') as mock_cluster_res, \
             patch('ray.available_resources') as mock_avail_res, \
             patch('ray.nodes') as mock_nodes, \
             patch('ray.shutdown') as mock_shutdown:
            
            mock_is_init.return_value = True
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
                    "NodeID": "node1",
                    "Alive": True,
                    "Resources": {"CPU": 4.0, "GPU": 1.0},
                    "NodeManagerAddress": "192.168.1.100",
                    "NodeManagerPort": 8076
                },
                {
                    "NodeID": "node2",
                    "Alive": True,
                    "Resources": {"CPU": 4.0, "GPU": 1.0},
                    "NodeManagerAddress": "192.168.1.101",
                    "NodeManagerPort": 8076
                }
            ]
            
            yield {
                "init": mock_init,
                "is_initialized": mock_is_init,
                "cluster_resources": mock_cluster_res,
                "available_resources": mock_avail_res,
                "nodes": mock_nodes,
                "shutdown": mock_shutdown
            }

    def test_service_initialization(self, service):
        """서비스 초기화 상태 테스트"""
        assert service._connected is False
        assert service._cluster_info is None
        assert service._connection_time is None
        assert service._connection_attempts == 0

    def test_initialize_success(self, service, mock_ray_functions):
        """Ray 클러스터 연결 성공 테스트"""
        result = service.initialize()
        
        assert result is True
        assert service._connected is True
        assert service._cluster_info is not None
        assert service._connection_time is not None
        assert service._connection_attempts == 1
        
        # Ray 초기화가 호출되었는지 확인
        mock_ray_functions["init"].assert_called_once()

    def test_initialize_failure(self, service, mock_ray_functions):
        """Ray 클러스터 연결 실패 테스트"""
        mock_ray_functions["init"].side_effect = Exception("연결 실패")
        
        result = service.initialize()
        
        assert result is False
        assert service._connected is False
        assert service._connection_attempts == 3  # 최대 재시도 횟수

    def test_initialize_already_connected(self, service, mock_ray_functions):
        """이미 연결된 상태에서 초기화 테스트"""
        service._connected = True
        
        result = service.initialize()
        
        assert result is True
        # Ray 초기화가 호출되지 않았는지 확인
        mock_ray_functions["init"].assert_not_called()

    def test_is_connected_true(self, service, mock_ray_functions):
        """연결 상태 확인 - 연결됨"""
        service._connected = True
        
        result = service.is_connected()
        
        assert result is True

    def test_is_connected_false(self, service, mock_ray_functions):
        """연결 상태 확인 - 연결 안됨"""
        service._connected = False
        
        result = service.is_connected()
        
        assert result is False

    def test_is_connected_ray_not_initialized(self, service, mock_ray_functions):
        """Ray가 초기화되지 않은 경우 연결 상태 확인"""
        service._connected = True
        mock_ray_functions["is_initialized"].return_value = False
        
        result = service.is_connected()
        
        assert result is False
        assert service._connected is False

    def test_get_cluster_resources_success(self, service, mock_ray_functions):
        """클러스터 리소스 조회 성공 테스트"""
        service._connected = True
        
        resources = service.get_cluster_resources()
        
        assert "cluster_resources" in resources
        assert "available_resources" in resources
        assert "timeline" in resources
        assert resources["cluster_resources"]["CPU"] == 8.0

    def test_get_cluster_resources_not_connected(self, service):
        """연결되지 않은 상태에서 리소스 조회 테스트"""
        resources = service.get_cluster_resources()
        
        assert "error" in resources
        assert "Ray 클러스터에 연결되지 않음" in resources["error"]

    def test_get_cluster_status_success(self, service, mock_ray_functions):
        """클러스터 상태 조회 성공 테스트"""
        service._connected = True
        service._connection_time = 1.5
        service._connection_attempts = 1
        service._cluster_info = {"connected_at": time.time() - 100}
        
        status = service.get_cluster_status()
        
        assert status["connected"] is True
        assert "connection_time" in status
        assert "uptime" in status
        assert "cluster_resources" in status
        assert "nodes" in status

    def test_get_cluster_status_not_connected(self, service):
        """연결되지 않은 상태에서 상태 조회 테스트"""
        status = service.get_cluster_status()
        
        assert status["connected"] is False
        assert "error" in status

    def test_get_node_info(self, service, mock_ray_functions):
        """노드 정보 조회 테스트"""
        service._connected = True
        
        node_info = service._get_node_info()
        
        assert "total_nodes" in node_info
        assert "alive_nodes" in node_info
        assert "nodes_detail" in node_info
        assert node_info["total_nodes"] == 2
        assert node_info["alive_nodes"] == 2

    def test_get_dashboard_url(self, service):
        """Dashboard URL 조회 테스트"""
        url = service._get_dashboard_url()
        
        # settings.RAY_ADDRESS가 "ray://ray-head:10001"인 경우
        expected_url = "http://ray-head:8265"
        assert url == expected_url

    def test_get_ray_context_success(self, service, mock_ray_functions):
        """Ray 컨텍스트 조회 성공 테스트"""
        service._connected = True
        
        with patch('ray.get_runtime_context') as mock_context:
            # Mock context 객체 생성
            mock_ctx = Mock()
            mock_ctx.job_id.hex.return_value = "job123"
            mock_ctx.task_id = None
            mock_ctx.actor_id = None
            mock_ctx.node_id.hex.return_value = "node123"
            mock_ctx.worker_id.hex.return_value = "worker123"
            mock_ctx.namespace = "test-namespace"
            
            mock_context.return_value = mock_ctx
            
            context = service.get_ray_context()
            
            assert "job_id" in context
            assert "node_id" in context
            assert context["job_id"] == "job123"

    def test_get_ray_context_not_connected(self, service):
        """연결되지 않은 상태에서 컨텍스트 조회 테스트"""
        context = service.get_ray_context()
        
        assert "error" in context

    def test_submit_task_success(self, service, mock_ray_functions):
        """태스크 제출 성공 테스트"""
        service._connected = True
        
        def test_function(x, y):
            return x + y
        
        with patch('ray.remote') as mock_remote:
            mock_remote_func = Mock()
            mock_remote_func.remote.return_value = "task_ref"
            mock_remote.return_value = mock_remote_func
            
            result = service.submit_task(test_function, 1, 2)
            
            assert result == "task_ref"
            mock_remote.assert_called_once_with(test_function)

    def test_submit_task_not_connected(self, service):
        """연결되지 않은 상태에서 태스크 제출 테스트"""
        def test_function():
            pass
        
        with pytest.raises(RuntimeError, match="Ray 클러스터에 연결되지 않음"):
            service.submit_task(test_function)

    def test_create_actor_success(self, service, mock_ray_functions):
        """Actor 생성 성공 테스트"""
        service._connected = True
        
        class TestActor:
            def __init__(self):
                pass
        
        with patch('ray.remote') as mock_remote:
            mock_remote_actor = Mock()
            mock_remote_actor.remote.return_value = "actor_ref"
            mock_remote.return_value = mock_remote_actor
            
            result = service.create_actor(TestActor)
            
            assert result == "actor_ref"
            mock_remote.assert_called_once_with(TestActor)

    def test_wait_for_tasks_success(self, service, mock_ray_functions):
        """태스크 대기 성공 테스트"""
        service._connected = True
        
        with patch('ray.wait') as mock_wait:
            mock_wait.return_value = (["completed_task"], ["pending_task"])
            
            ready, not_ready = service.wait_for_tasks(["task1", "task2"])
            
            assert ready == ["completed_task"]
            assert not_ready == ["pending_task"]

    def test_get_task_result_success(self, service, mock_ray_functions):
        """태스크 결과 조회 성공 테스트"""
        service._connected = True
        
        with patch('ray.get') as mock_get:
            mock_get.return_value = "task_result"
            
            result = service.get_task_result("task_ref")
            
            assert result == "task_result"

    def test_cancel_task_success(self, service, mock_ray_functions):
        """태스크 취소 성공 테스트"""
        service._connected = True
        
        with patch('ray.cancel') as mock_cancel:
            result = service.cancel_task("task_ref")
            
            assert result is True
            mock_cancel.assert_called_once_with("task_ref")

    def test_cancel_task_not_connected(self, service):
        """연결되지 않은 상태에서 태스크 취소 테스트"""
        result = service.cancel_task("task_ref")
        
        assert result is False

    def test_monitor_cluster_health_healthy(self, service, mock_ray_functions):
        """클러스터 헬스 모니터링 - 정상 상태"""
        service._connected = True
        service._cluster_info = {"connected_at": time.time() - 100}
        
        health = service.monitor_cluster_health()
        
        assert health["healthy"] is True
        assert "nodes" in health
        assert "resources" in health
        assert health["nodes"]["total"] == 2
        assert health["nodes"]["alive"] == 2

    def test_monitor_cluster_health_unhealthy_dead_nodes(self, service, mock_ray_functions):
        """클러스터 헬스 모니터링 - 죽은 노드 존재"""
        service._connected = True
        service._cluster_info = {"connected_at": time.time() - 100}
        
        # 하나의 노드가 죽은 상태로 설정
        mock_ray_functions["nodes"].return_value = [
            {"NodeID": "node1", "Alive": True, "Resources": {"CPU": 4.0, "GPU": 1.0}},
            {"NodeID": "node2", "Alive": False, "Resources": {"CPU": 4.0, "GPU": 1.0}}
        ]
        
        health = service.monitor_cluster_health()
        
        assert health["healthy"] is False
        assert health["nodes"]["dead"] == 1
        assert "1개 노드가 오프라인" in health["warnings"]

    def test_monitor_cluster_health_no_gpu(self, service, mock_ray_functions):
        """클러스터 헬스 모니터링 - GPU 없음"""
        service._connected = True
        service._cluster_info = {"connected_at": time.time() - 100}
        
        # GPU가 없는 상태로 설정
        mock_ray_functions["cluster_resources"].return_value = {
            "CPU": 8.0,
            "memory": 16000000000
        }
        mock_ray_functions["available_resources"].return_value = {
            "CPU": 6.0,
            "memory": 8000000000
        }
        
        health = service.monitor_cluster_health()
        
        assert health["healthy"] is False
        assert "GPU 리소스를 찾을 수 없음" in health["warnings"]

    def test_monitor_cluster_health_not_connected(self, service):
        """연결되지 않은 상태에서 헬스 모니터링"""
        health = service.monitor_cluster_health()
        
        assert health["healthy"] is False
        assert "Ray 클러스터에 연결되지 않음" in health["reason"]

    def test_get_performance_metrics_success(self, service, mock_ray_functions):
        """성능 메트릭 조회 성공 테스트"""
        service._connected = True
        
        metrics = service.get_performance_metrics()
        
        assert "cpu_utilization" in metrics
        assert "gpu_utilization" in metrics
        assert "memory_utilization" in metrics
        assert "resources" in metrics
        
        # CPU 사용률 계산 확인 (총 8.0 중 2.0 사용 = 25%)
        assert metrics["cpu_utilization"] == 25.0
        
        # GPU 사용률 계산 확인 (총 2.0 중 1.0 사용 = 50%)
        assert metrics["gpu_utilization"] == 50.0

    def test_get_performance_metrics_not_connected(self, service):
        """연결되지 않은 상태에서 성능 메트릭 조회"""
        metrics = service.get_performance_metrics()
        
        assert "error" in metrics

    def test_reconnect_success(self, service, mock_ray_functions):
        """재연결 성공 테스트"""
        service._connected = True
        
        result = service.reconnect()
        
        assert result is True
        # shutdown이 호출되었는지 확인
        mock_ray_functions["shutdown"].assert_called_once()

    def test_shutdown_connected(self, service, mock_ray_functions):
        """연결된 상태에서 종료 테스트"""
        service._connected = True
        
        service.shutdown()
        
        assert service._connected is False
        assert service._cluster_info is None
        mock_ray_functions["shutdown"].assert_called_once()

    def test_shutdown_not_connected(self, service, mock_ray_functions):
        """연결되지 않은 상태에서 종료 테스트"""
        service._connected = False
        
        service.shutdown()
        
        # shutdown이 호출되지 않았는지 확인
        mock_ray_functions["shutdown"].assert_not_called()

    @override_settings(RAY_ADDRESS="ray://test-cluster:10001")
    def test_custom_ray_address(self, service, mock_ray_functions):
        """사용자 정의 Ray 주소 테스트"""
        service.initialize()
        
        # 설정된 주소로 초기화되었는지 확인
        call_args = mock_ray_functions["init"].call_args[1]
        assert call_args["address"] == "ray://test-cluster:10001"

class TestRayTaskManager:
    """RayTaskManager 테스트 클래스"""
    
    @pytest.fixture
    def ray_service(self):
        """모킹된 RayClusterService"""
        service = Mock(spec=RayClusterService)
        service.is_connected.return_value = True
        service.submit_task.return_value = "task_ref"
        service.wait_for_tasks.return_value = ([], ["task_ref"])  # 기본적으로 대기 중
        service.get_task_result.return_value = "task_result"
        service.cancel_task.return_value = True
        return service
    
    @pytest.fixture
    def task_manager(self, ray_service):
        """RayTaskManager 인스턴스"""
        return RayTaskManager(ray_service)

    def test_task_manager_initialization(self, task_manager):
        """태스크 매니저 초기화 테스트"""
        assert task_manager.active_tasks == {}
        assert task_manager.task_counter == 0

    def test_submit_task_success(self, task_manager, ray_service):
        """태스크 제출 성공 테스트"""
        def test_function(x, y):
            return x + y
        
        task_id, task_ref = task_manager.submit_task(test_function, 1, 2)
        
        assert task_id == "task_1"
        assert task_ref == "task_ref"
        assert task_id in task_manager.active_tasks
        assert task_manager.task_counter == 1

    def test_submit_task_with_name(self, task_manager, ray_service):
        """이름을 가진 태스크 제출 테스트"""
        def test_function():
            pass
        
        task_id, task_ref = task_manager.submit_task(test_function, task_name="custom")
        
        assert task_id == "custom_1"
        assert task_ref == "task_ref"

    def test_submit_task_not_connected(self, task_manager):
        """연결되지 않은 상태에서 태스크 제출 테스트"""
        task_manager.ray_service.is_connected.return_value = False
        
        def test_function():
            pass
        
        with pytest.raises(RuntimeError, match="Ray 클러스터에 연결되지 않음"):
            task_manager.submit_task(test_function)

    def test_get_task_status_running(self, task_manager, ray_service):
        """실행 중인 태스크 상태 조회 테스트"""
        # 태스크 제출
        def test_function():
            pass
        
        task_id, _ = task_manager.submit_task(test_function)
        
        # 실행 중 상태로 설정
        ray_service.wait_for_tasks.return_value = ([], ["task_ref"])
        
        status = task_manager.get_task_status(task_id)
        
        assert status["status"] == "running"
        assert "elapsed_time" in status
        assert status["task_id"] == task_id

    def test_get_task_status_completed(self, task_manager, ray_service):
        """완료된 태스크 상태 조회 테스트"""
        # 태스크 제출
        def test_function():
            return "result"
        
        task_id, _ = task_manager.submit_task(test_function)
        
        # 완료 상태로 설정
        ray_service.wait_for_tasks.return_value = (["task_ref"], [])
        ray_service.get_task_result.return_value = "result"
        
        status = task_manager.get_task_status(task_id)
        
        assert status["status"] == "completed"
        assert status["result"] == "result"
        assert "completed_at" in status
        # 완료된 태스크는 active_tasks에서 제거되어야 함
        assert task_id not in task_manager.active_tasks

    def test_get_task_status_failed(self, task_manager, ray_service):
        """실패한 태스크 상태 조회 테스트"""
        # 태스크 제출
        def test_function():
            pass
        
        task_id, _ = task_manager.submit_task(test_function)
        
        # 완료 상태로 설정하지만 결과 조회 시 오류 발생
        ray_service.wait_for_tasks.return_value = (["task_ref"], [])
        ray_service.get_task_result.side_effect = Exception("태스크 실행 오류")
        
        status = task_manager.get_task_status(task_id)
        
        assert status["status"] == "failed"
        assert "error" in status

    def test_get_task_status_not_found(self, task_manager):
        """존재하지 않는 태스크 상태 조회 테스트"""
        status = task_manager.get_task_status("nonexistent_task")
        
        assert "error" in status
        assert "태스크를 찾을 수 없음" in status["error"]

    def test_cancel_task_success(self, task_manager, ray_service):
        """태스크 취소 성공 테스트"""
        # 태스크 제출
        def test_function():
            pass
        
        task_id, _ = task_manager.submit_task(test_function)
        
        result = task_manager.cancel_task(task_id)
        
        assert result is True
        assert task_id not in task_manager.active_tasks
        ray_service.cancel_task.assert_called_once()

    def test_cancel_task_not_found(self, task_manager):
        """존재하지 않는 태스크 취소 테스트"""
        result = task_manager.cancel_task("nonexistent_task")
        
        assert result is False

    def test_get_all_tasks_status(self, task_manager, ray_service):
        """모든 태스크 상태 조회 테스트"""
        # 여러 태스크 제출
        for i in range(3):
            def test_function():
                return i
            task_manager.submit_task(test_function)
        
        all_status = task_manager.get_all_tasks_status()
        
        assert all_status["total_tasks"] == 3
        assert len(all_status["tasks"]) == 3

    def test_cleanup_completed_tasks(self, task_manager, ray_service):
        """완료된 태스크 정리 테스트"""
        # 태스크 제출
        def test_function():
            return "result"
        
        task_id, _ = task_manager.submit_task(test_function)
        
        # 완료 상태로 설정
        ray_service.wait_for_tasks.return_value = (["task_ref"], [])
        ray_service.get_task_result.return_value = "result"
        
        # 정리 전 상태 확인
        assert task_id in task_manager.active_tasks
        
        # 정리 실행
        task_manager.cleanup_completed_tasks()
        
        # 완료된 태스크가 제거되었는지 확인
        assert task_id not in task_manager.active_tasks

class TestRayServiceIntegration:
    """Ray 서비스 통합 테스트"""
    
    @pytest.mark.integration
    def test_full_workflow(self):
        """전체 워크플로우 통합 테스트"""
        with patch('ray.init'), \
             patch('ray.is_initialized', return_value=True), \
             patch('ray.cluster_resources', return_value={"CPU": 8.0, "GPU": 2.0}), \
             patch('ray.available_resources', return_value={"CPU": 6.0, "GPU": 1.0}), \
             patch('ray.nodes', return_value=[{"NodeID": "node1", "Alive": True}]):
            
            service = RayClusterService()
            task_manager = RayTaskManager(service)
            
            # 클러스터 연결
            assert service.initialize() is True
            assert service.is_connected() is True
            
            # 리소스 확인
            resources = service.get_cluster_resources()
            assert "cluster_resources" in resources
            
            # 헬스 모니터링
            health = service.monitor_cluster_health()
            assert "healthy" in health
            
            # 성능 메트릭
            metrics = service.get_performance_metrics()
            assert "cpu_utilization" in metrics
            
            # 태스크 관리
            def test_task(x):
                return x * 2
            
            with patch('ray.remote') as mock_remote, \
                 patch('ray.wait', return_value=(["task_ref"], [])), \
                 patch('ray.get', return_value=10):
                
                mock_remote_func = Mock()
                mock_remote_func.remote.return_value = "task_ref"
                mock_remote.return_value = mock_remote_func
                
                task_id, _ = task_manager.submit_task(test_task, 5)
                status = task_manager.get_task_status(task_id)
                
                assert status["status"] == "completed"
                assert status["result"] == 10
            
            # 서비스 종료
            service.shutdown()
            assert service.is_connected() is False

    @pytest.mark.slow
    def test_retry_mechanism(self):
        """재시도 메커니즘 테스트"""
        service = RayClusterService()
        
        with patch('ray.init') as mock_init, \
             patch('ray.is_initialized', return_value=True):
            
            # 처음 두 번은 실패, 세 번째는 성공
            mock_init.side_effect = [
                Exception("첫 번째 실패"),
                Exception("두 번째 실패"),
                None  # 세 번째 성공
            ]
            
            with patch('time.sleep'):  # 실제 대기 시간 제거
                result = service.initialize()
            
            assert result is True
            assert service._connection_attempts == 3
            assert mock_init.call_count == 3

    def test_error_handling_during_operations(self):
        """작업 중 오류 처리 테스트"""
        service = RayClusterService()
        service._connected = True
        
        # 클러스터 리소스 조회 중 오류
        with patch('ray.cluster_resources', side_effect=Exception("리소스 조회 오류")):
            resources = service.get_cluster_resources()
            assert "error" in resources
        
        # 노드 정보 조회 중 오류
        with patch('ray.nodes', side_effect=Exception("노드 조회 오류")):
            status = service.get_cluster_status()
            assert "error" in status

    def test_performance_under_concurrent_load(self):
        """동시 부하 상황에서의 성능 테스트"""
        import threading
        import queue
        
        service = RayClusterService()
        task_manager = RayTaskManager(service)
        
        with patch('ray.init'), \
             patch('ray.is_initialized', return_value=True), \
             patch('ray.remote') as mock_remote, \
             patch('ray.wait', return_value=([], ["task_ref"])):
            
            service.initialize()
            
            mock_remote_func = Mock()
            mock_remote_func.remote.return_value = "task_ref"
            mock_remote.return_value = mock_remote_func
            
            results_queue = queue.Queue()
            
            def submit_tasks():
                """동시에 태스크 제출"""
                for i in range(10):
                    try:
                        def test_task():
                            return i
                        task_id, _ = task_manager.submit_task(test_task)
                        results_queue.put(("success", task_id))
                    except Exception as e:
                        results_queue.put(("error", str(e)))
            
            # 여러 스레드에서 동시에 태스크 제출
            threads = []
            for _ in range(5):
                thread = threading.Thread(target=submit_tasks)
                threads.append(thread)
                thread.start()
            
            # 모든 스레드 완료 대기
            for thread in threads:
                thread.join()
            
            # 결과 확인
            successful_submissions = 0
            while not results_queue.empty():
                result_type, result_data = results_queue.get()
                if result_type == "success":
                    successful_submissions += 1
            
            # 대부분의 요청이 성공했는지 확인
            assert successful_submissions >= 40  # 50개 중 최소 40개

if __name__ == "__main__":
    pytest.main([__file__, "-v"])