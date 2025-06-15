"""
app/services/ray_service.py
Ray 클러스터 연결 및 관리 서비스
"""

import ray
import time
from typing import Dict, Any, Optional
from app.core.config import settings
from app.core.logging import get_logger, log_error_with_context, log_ray_cluster_info

logger = get_logger("ray_service")

class RayClusterService:
    """Ray 클러스터 연결 및 관리 서비스"""
    
    def __init__(self):
        self._connected = False
        self._cluster_info: Optional[Dict[str, Any]] = None
        self._connection_time: Optional[float] = None
        self._connection_attempts = 0
        self._max_retry_attempts = 3
        self._retry_delay = 5.0  # 초
    
    def initialize(self) -> bool:
        """Ray 클러스터 연결 초기화"""
        if self._connected:
            logger.info("Ray 클러스터 이미 연결됨")
            return True
        
        for attempt in range(1, self._max_retry_attempts + 1):
            try:
                logger.info(f"Ray 클러스터 연결 시도 {attempt}/{self._max_retry_attempts}")
                start_time = time.time()
                
                # Ray 클러스터 연결
                ray.init(
                    address=settings.RAY_ADDRESS,
                    _redis_password=settings.RAY_REDIS_PASSWORD,
                    namespace=settings.RAY_NAMESPACE,
                    runtime_env=settings.get_ray_runtime_env(),
                    ignore_reinit_error=True,
                    logging_level=settings.LOG_LEVEL,
                    log_to_driver=True
                )
                
                # 연결 상태 확인
                if not ray.is_initialized():
                    raise RuntimeError("Ray 초기화 실패")
                
                # 클러스터 정보 수집
                self._collect_cluster_info()
                
                self._connected = True
                self._connection_time = time.time() - start_time
                self._connection_attempts = attempt
                
                logger.info(f"Ray 클러스터 연결 성공 - {self._connection_time:.2f}초")
                log_ray_cluster_info(self._cluster_info)
                
                return True
                
            except Exception as e:
                logger.warning(f"Ray 클러스터 연결 실패 (시도 {attempt}): {e}")
                
                if attempt < self._max_retry_attempts:
                    logger.info(f"{self._retry_delay}초 후 재시도...")
                    time.sleep(self._retry_delay)
                else:
                    log_error_with_context(e, {
                        "component": "RayClusterService",
                        "attempts": attempt,
                        "ray_address": settings.RAY_ADDRESS
                    })
        
        return False
    
    def _collect_cluster_info(self):
        """클러스터 정보 수집"""
        try:
            self._cluster_info = {
                "cluster_resources": ray.cluster_resources(),
                "available_resources": ray.available_resources(),
                "nodes": self._get_node_info(),
                "dashboard_url": self._get_dashboard_url(),
                "namespace": settings.RAY_NAMESPACE,
                "connected_at": time.time()
            }
        except Exception as e:
            logger.warning(f"클러스터 정보 수집 실패: {e}")
            self._cluster_info = {"error": str(e)}
    
    def _get_node_info(self) -> Dict[str, Any]:
        """노드 정보 조회"""
        try:
            nodes_info = ray.nodes()
            processed_nodes = []
            
            for node in nodes_info:
                processed_nodes.append({
                    "node_id": node["NodeID"],
                    "alive": node["Alive"],
                    "resources": node["Resources"],
                    "node_manager_address": node.get("NodeManagerAddress", ""),
                    "node_manager_port": node.get("NodeManagerPort", 0)
                })
            
            return {
                "total_nodes": len(processed_nodes),
                "alive_nodes": sum(1 for node in processed_nodes if node["alive"]),
                "nodes_detail": processed_nodes
            }
        except Exception as e:
            logger.warning(f"노드 정보 조회 실패: {e}")
            return {"error": str(e)}
    
    def _get_dashboard_url(self) -> Optional[str]:
        """Ray Dashboard URL 조회"""
        try:
            # Ray head 노드에서 dashboard 포트 추출
            ray_address = settings.RAY_ADDRESS
            if ray_address.startswith("ray://"):
                head_address = ray_address.replace("ray://", "").split(":")[0]
                return f"http://{head_address}:8265"
            return None
        except Exception as e:
            logger.warning(f"Dashboard URL 조회 실패: {e}")
            return None
    
    def is_connected(self) -> bool:
        """연결 상태 확인"""
        if not self._connected:
            return False
        
        try:
            # Ray 상태 확인
            return ray.is_initialized()
        except Exception:
            self._connected = False
            return False
    
    def get_cluster_resources(self) -> Dict[str, Any]:
        """클러스터 리소스 정보 조회"""
        if not self.is_connected():
            return {"error": "Ray 클러스터에 연결되지 않음"}
        
        try:
            return {
                "cluster_resources": ray.cluster_resources(),
                "available_resources": ray.available_resources(),
                "timeline": time.time()
            }
        except Exception as e:
            log_error_with_context(e, {"component": "get_cluster_resources"})
            return {"error": str(e)}
    
    def get_cluster_status(self) -> Dict[str, Any]:
        """전체 클러스터 상태 조회"""
        if not self.is_connected():
            return {
                "connected": False,
                "error": "Ray 클러스터에 연결되지 않음"
            }
        
        try:
            # 현재 리소스 정보 업데이트
            current_resources = self.get_cluster_resources()
            
            # 노드 정보 업데이트
            current_nodes = self._get_node_info()
            
            return {
                "connected": True,
                "connection_time": self._connection_time,
                "connection_attempts": self._connection_attempts,
                "uptime": time.time() - self._cluster_info.get("connected_at", time.time()),
                "cluster_resources": current_resources,
                "nodes": current_nodes,
                "dashboard_url": self._cluster_info.get("dashboard_url"),
                "namespace": settings.RAY_NAMESPACE,
                "ray_address": settings.RAY_ADDRESS
            }
        except Exception as e:
            log_error_with_context(e, {"component": "get_cluster_status"})
            return {
                "connected": False,
                "error": str(e)
            }
    
    def get_ray_context(self) -> Dict[str, Any]:
        """Ray 컨텍스트 정보 조회"""
        if not self.is_connected():
            return {"error": "Ray 클러스터에 연결되지 않음"}
        
        try:
            context = ray.get_runtime_context()
            return {
                "job_id": context.job_id.hex(),
                "task_id": context.task_id.hex() if context.task_id else None,
                "actor_id": context.actor_id.hex() if context.actor_id else None,
                "node_id": context.node_id.hex(),
                "worker_id": context.worker_id.hex(),
                "namespace": context.namespace
            }
        except Exception as e:
            log_error_with_context(e, {"component": "get_ray_context"})
            return {"error": str(e)}
    
    def submit_task(self, func, *args, **kwargs):
        """Ray 태스크 제출"""
        if not self.is_connected():
            raise RuntimeError("Ray 클러스터에 연결되지 않음")
        
        try:
            # Ray remote 함수로 태스크 제출
            remote_func = ray.remote(func)
            return remote_func.remote(*args, **kwargs)
        except Exception as e:
            log_error_with_context(e, {
                "component": "submit_task",
                "function": func.__name__ if hasattr(func, '__name__') else str(func)
            })
            raise
    
    def create_actor(self, actor_class, *args, **kwargs):
        """Ray Actor 생성"""
        if not self.is_connected():
            raise RuntimeError("Ray 클러스터에 연결되지 않음")
        
        try:
            # Ray remote actor 생성
            remote_actor = ray.remote(actor_class)
            return remote_actor.remote(*args, **kwargs)
        except Exception as e:
            log_error_with_context(e, {
                "component": "create_actor",
                "actor_class": actor_class.__name__ if hasattr(actor_class, '__name__') else str(actor_class)
            })
            raise
    
    def wait_for_tasks(self, task_refs, num_returns=1, timeout=None):
        """태스크 완료 대기"""
        if not self.is_connected():
            raise RuntimeError("Ray 클러스터에 연결되지 않음")
        
        try:
            return ray.wait(task_refs, num_returns=num_returns, timeout=timeout)
        except Exception as e:
            log_error_with_context(e, {"component": "wait_for_tasks"})
            raise
    
    def get_task_result(self, task_ref):
        """태스크 결과 조회"""
        if not self.is_connected():
            raise RuntimeError("Ray 클러스터에 연결되지 않음")
        
        try:
            return ray.get(task_ref)
        except Exception as e:
            log_error_with_context(e, {"component": "get_task_result"})
            raise
    
    def cancel_task(self, task_ref):
        """태스크 취소"""
        if not self.is_connected():
            return False
        
        try:
            ray.cancel(task_ref)
            return True
        except Exception as e:
            log_error_with_context(e, {"component": "cancel_task"})
            return False
    
    def monitor_cluster_health(self) -> Dict[str, Any]:
        """클러스터 헬스 모니터링"""
        if not self.is_connected():
            return {
                "healthy": False,
                "reason": "Ray 클러스터에 연결되지 않음"
            }
        
        try:
            # 리소스 가용성 확인
            cluster_resources = ray.cluster_resources()
            available_resources = ray.available_resources()
            
            # 노드 상태 확인
            nodes_info = self._get_node_info()
            alive_nodes = nodes_info.get("alive_nodes", 0)
            total_nodes = nodes_info.get("total_nodes", 0)
            
            # GPU 리소스 확인
            gpu_total = cluster_resources.get("GPU", 0)
            gpu_available = available_resources.get("GPU", 0)
            
            # 헬스 상태 판단
            healthy = (
                alive_nodes > 0 and 
                alive_nodes == total_nodes and
                gpu_total > 0
            )
            
            health_info = {
                "healthy": healthy,
                "nodes": {
                    "total": total_nodes,
                    "alive": alive_nodes,
                    "dead": total_nodes - alive_nodes
                },
                "resources": {
                    "gpu_total": gpu_total,
                    "gpu_available": gpu_available,
                    "gpu_utilization": ((gpu_total - gpu_available) / gpu_total * 100) if gpu_total > 0 else 0
                },
                "uptime": time.time() - self._cluster_info.get("connected_at", time.time()),
                "last_check": time.time()
            }
            
            # 경고 조건 확인
            warnings = []
            if alive_nodes < total_nodes:
                warnings.append(f"{total_nodes - alive_nodes}개 노드가 오프라인")
            if gpu_total == 0:
                warnings.append("GPU 리소스를 찾을 수 없음")
            if gpu_available == 0:
                warnings.append("사용 가능한 GPU가 없음")
            
            health_info["warnings"] = warnings
            
            return health_info
            
        except Exception as e:
            log_error_with_context(e, {"component": "monitor_cluster_health"})
            return {
                "healthy": False,
                "reason": f"헬스 체크 실패: {str(e)}"
            }
    
    def get_performance_metrics(self) -> Dict[str, Any]:
        """성능 메트릭 조회"""
        if not self.is_connected():
            return {"error": "Ray 클러스터에 연결되지 않음"}
        
        try:
            # 시스템 메트릭 수집
            cluster_resources = ray.cluster_resources()
            available_resources = ray.available_resources()
            
            # CPU 사용률 계산
            cpu_total = cluster_resources.get("CPU", 0)
            cpu_available = available_resources.get("CPU", 0)
            cpu_utilization = ((cpu_total - cpu_available) / cpu_total * 100) if cpu_total > 0 else 0
            
            # GPU 사용률 계산
            gpu_total = cluster_resources.get("GPU", 0)
            gpu_available = available_resources.get("GPU", 0)
            gpu_utilization = ((gpu_total - gpu_available) / gpu_total * 100) if gpu_total > 0 else 0
            
            # 메모리 사용률 계산
            memory_total = cluster_resources.get("memory", 0)
            memory_available = available_resources.get("memory", 0)
            memory_utilization = ((memory_total - memory_available) / memory_total * 100) if memory_total > 0 else 0
            
            return {
                "cpu_utilization": round(cpu_utilization, 2),
                "gpu_utilization": round(gpu_utilization, 2),
                "memory_utilization": round(memory_utilization, 2),
                "resources": {
                    "cpu": {"total": cpu_total, "available": cpu_available, "used": cpu_total - cpu_available},
                    "gpu": {"total": gpu_total, "available": gpu_available, "used": gpu_total - gpu_available},
                    "memory": {"total": memory_total, "available": memory_available, "used": memory_total - memory_available}
                },
                "timestamp": time.time()
            }
            
        except Exception as e:
            log_error_with_context(e, {"component": "get_performance_metrics"})
            return {"error": str(e)}
    
    def reconnect(self) -> bool:
        """Ray 클러스터 재연결"""
        logger.info("Ray 클러스터 재연결 시도")
        
        # 기존 연결 종료
        self.shutdown()
        
        # 재연결
        return self.initialize()
    
    def shutdown(self):
        """Ray 연결 종료"""
        if self._connected:
            try:
                logger.info("Ray 클러스터 연결 종료 중...")
                ray.shutdown()
                self._connected = False
                self._cluster_info = None
                self._connection_time = None
                logger.info("Ray 클러스터 연결 종료 완료")
            except Exception as e:
                log_error_with_context(e, {"component": "RayClusterService.shutdown"})
    
    def __del__(self):
        """소멸자 - 자동 정리"""
        self.shutdown()

class RayTaskManager:
    """Ray 태스크 관리 헬퍼 클래스"""
    
    def __init__(self, ray_service: RayClusterService):
        self.ray_service = ray_service
        self.active_tasks = {}
        self.task_counter = 0
    
    def submit_task(self, func, *args, task_name=None, **kwargs):
        """태스크 제출 및 추적"""
        if not self.ray_service.is_connected():
            raise RuntimeError("Ray 클러스터에 연결되지 않음")
        
        self.task_counter += 1
        task_id = f"task_{self.task_counter}"
        
        if task_name:
            task_id = f"{task_name}_{self.task_counter}"
        
        try:
            task_ref = self.ray_service.submit_task(func, *args, **kwargs)
            
            self.active_tasks[task_id] = {
                "task_ref": task_ref,
                "submitted_at": time.time(),
                "function": func.__name__ if hasattr(func, '__name__') else str(func),
                "args": args,
                "kwargs": kwargs
            }
            
            logger.debug(f"태스크 제출됨 - ID: {task_id}")
            return task_id, task_ref
            
        except Exception as e:
            log_error_with_context(e, {"component": "RayTaskManager.submit_task"})
            raise
    
    def get_task_status(self, task_id: str) -> Dict[str, Any]:
        """태스크 상태 조회"""
        if task_id not in self.active_tasks:
            return {"error": f"태스크를 찾을 수 없음: {task_id}"}
        
        try:
            task_info = self.active_tasks[task_id]
            task_ref = task_info["task_ref"]
            
            # 태스크 완료 여부 확인
            ready, not_ready = self.ray_service.wait_for_tasks([task_ref], timeout=0)
            
            status = {
                "task_id": task_id,
                "status": "completed" if ready else "running",
                "submitted_at": task_info["submitted_at"],
                "elapsed_time": time.time() - task_info["submitted_at"],
                "function": task_info["function"]
            }
            
            if ready:
                try:
                    result = self.ray_service.get_task_result(task_ref)
                    status["result"] = result
                    status["completed_at"] = time.time()
                    # 완료된 태스크는 추적 목록에서 제거
                    del self.active_tasks[task_id]
                except Exception as e:
                    status["error"] = str(e)
                    status["status"] = "failed"
            
            return status
            
        except Exception as e:
            log_error_with_context(e, {"component": "get_task_status", "task_id": task_id})
            return {"error": str(e)}
    
    def cancel_task(self, task_id: str) -> bool:
        """태스크 취소"""
        if task_id not in self.active_tasks:
            return False
        
        try:
            task_ref = self.active_tasks[task_id]["task_ref"]
            success = self.ray_service.cancel_task(task_ref)
            
            if success:
                del self.active_tasks[task_id]
                logger.info(f"태스크 취소됨 - ID: {task_id}")
            
            return success
            
        except Exception as e:
            log_error_with_context(e, {"component": "cancel_task", "task_id": task_id})
            return False
    
    def get_all_tasks_status(self) -> Dict[str, Any]:
        """모든 활성 태스크 상태 조회"""
        return {
            "total_tasks": len(self.active_tasks),
            "tasks": {task_id: self.get_task_status(task_id) for task_id in self.active_tasks.keys()}
        }
    
    def cleanup_completed_tasks(self):
        """완료된 태스크 정리"""
        completed_tasks = []
        for task_id in list(self.active_tasks.keys()):
            status = self.get_task_status(task_id)
            if status.get("status") in ["completed", "failed"]:
                completed_tasks.append(task_id)
        
        logger.debug(f"완료된 태스크 {len(completed_tasks)}개 정리됨")

# 전역 Ray 서비스 인스턴스
ray_service = RayClusterService()
ray_task_manager = RayTaskManager(ray_service)