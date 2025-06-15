"""
app/services/model_monitor.py
모델 상태 모니터링 및 헬스체크 서비스
"""

import time
import asyncio
import psutil
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta
import torch
import ray
from dataclasses import dataclass
from enum import Enum

from app.core.config import settings
from app.core.logging import get_logger, log_error_with_context
from app.models.schemas import GenerateRequest

logger = get_logger("model_monitor")

class ModelStatus(str, Enum):
    """모델 상태 열거형"""
    HEALTHY = "healthy"
    DEGRADED = "degraded" 
    UNHEALTHY = "unhealthy"
    LOADING = "loading"
    ERROR = "error"
    UNKNOWN = "unknown"

@dataclass
class ModelHealthMetrics:
    """모델 헬스 메트릭"""
    status: ModelStatus
    last_check_time: float
    response_time_avg: float
    response_time_p95: float
    error_rate: float
    memory_usage_percent: float
    gpu_memory_usage_percent: Optional[float]
    temperature: Optional[float]
    throughput_tokens_per_second: float
    queue_length: int
    active_requests: int

@dataclass
class SystemHealthMetrics:
    """시스템 헬스 메트릭"""
    cpu_usage_percent: float
    memory_usage_percent: float
    disk_usage_percent: float
    gpu_utilization: Optional[float]
    gpu_memory_total: Optional[int]
    gpu_memory_used: Optional[int]
    gpu_temperature: Optional[float]
    load_average: tuple

class ModelHealthChecker:
    """모델 헬스 체커 클래스"""
    
    def __init__(self, check_interval: int = 30):
        self.check_interval = check_interval
        self.response_times: List[float] = []
        self.error_count = 0
        self.request_count = 0
        self.last_health_check = 0
        self.health_history: List[ModelHealthMetrics] = []
        self.max_history_size = 100
        
        # 임계값 설정
        self.thresholds = {
            "response_time_warning": 5.0,  # 5초
            "response_time_critical": 10.0,  # 10초
            "error_rate_warning": 0.05,  # 5%
            "error_rate_critical": 0.15,  # 15%
            "memory_warning": 80.0,  # 80%
            "memory_critical": 95.0,  # 95%
            "gpu_memory_warning": 90.0,  # 90%
            "gpu_memory_critical": 98.0,  # 98%
            "gpu_temp_warning": 80.0,  # 80°C
            "gpu_temp_critical": 90.0,  # 90°C
        }
    
    def record_request_metrics(self, response_time: float, success: bool, tokens_generated: int = 0):
        """요청 메트릭 기록"""
        self.response_times.append(response_time)
        self.request_count += 1
        
        if not success:
            self.error_count += 1
        
        # 최근 100개 요청만 유지
        if len(self.response_times) > 100:
            self.response_times.pop(0)
    
    def get_gpu_metrics(self) -> Dict[str, Optional[float]]:
        """GPU 메트릭 수집"""
        try:
            if not torch.cuda.is_available():
                return {
                    "gpu_utilization": None,
                    "gpu_memory_total": None,
                    "gpu_memory_used": None,
                    "gpu_memory_percent": None,
                    "gpu_temperature": None
                }
            
            # GPU 메모리 정보
            gpu_memory = torch.cuda.mem_get_info(0)
            memory_used = gpu_memory[1] - gpu_memory[0]
            memory_total = gpu_memory[1]
            memory_percent = (memory_used / memory_total) * 100
            
            # GPU 온도 (nvidia-ml-py 사용 시)
            gpu_temp = None
            try:
                import pynvml
                pynvml.nvmlInit()
                handle = pynvml.nvmlDeviceGetHandleByIndex(0)
                gpu_temp = pynvml.nvmlDeviceGetTemperature(handle, pynvml.NVML_TEMPERATURE_GPU)
                
                # GPU 사용률
                utilization = pynvml.nvmlDeviceGetUtilizationRates(handle)
                gpu_util = utilization.gpu
                
            except ImportError:
                gpu_util = None
                logger.debug("pynvml을 사용할 수 없습니다. GPU 온도 및 사용률 모니터링이 제한됩니다.")
            except Exception as e:
                gpu_util = None
                logger.warning(f"GPU 메트릭 수집 실패: {e}")
            
            return {
                "gpu_utilization": gpu_util,
                "gpu_memory_total": memory_total,
                "gpu_memory_used": memory_used,
                "gpu_memory_percent": memory_percent,
                "gpu_temperature": gpu_temp
            }
            
        except Exception as e:
            log_error_with_context(e, {"component": "get_gpu_metrics"})
            return {
                "gpu_utilization": None,
                "gpu_memory_total": None,
                "gpu_memory_used": None,
                "gpu_memory_percent": None,
                "gpu_temperature": None
            }
    
    def get_system_metrics(self) -> SystemHealthMetrics:
        """시스템 메트릭 수집"""
        try:
            # CPU 사용률
            cpu_percent = psutil.cpu_percent(interval=1)
            
            # 메모리 사용률
            memory = psutil.virtual_memory()
            memory_percent = memory.percent
            
            # 디스크 사용률
            disk = psutil.disk_usage('/')
            disk_percent = disk.percent
            
            # 로드 평균
            load_avg = psutil.getloadavg()
            
            # GPU 메트릭
            gpu_metrics = self.get_gpu_metrics()
            
            return SystemHealthMetrics(
                cpu_usage_percent=cpu_percent,
                memory_usage_percent=memory_percent,
                disk_usage_percent=disk_percent,
                gpu_utilization=gpu_metrics["gpu_utilization"],
                gpu_memory_total=gpu_metrics["gpu_memory_total"],
                gpu_memory_used=gpu_metrics["gpu_memory_used"],
                gpu_temperature=gpu_metrics["gpu_temperature"],
                load_average=load_avg
            )
            
        except Exception as e:
            log_error_with_context(e, {"component": "get_system_metrics"})
            # 기본값 반환
            return SystemHealthMetrics(
                cpu_usage_percent=0.0,
                memory_usage_percent=0.0,
                disk_usage_percent=0.0,
                gpu_utilization=None,
                gpu_memory_total=None,
                gpu_memory_used=None,
                gpu_temperature=None,
                load_average=(0.0, 0.0, 0.0)
            )
    
    def calculate_response_time_percentiles(self) -> Dict[str, float]:
        """응답 시간 백분위수 계산"""
        if not self.response_times:
            return {"avg": 0.0, "p50": 0.0, "p95": 0.0, "p99": 0.0}
        
        sorted_times = sorted(self.response_times)
        length = len(sorted_times)
        
        return {
            "avg": sum(sorted_times) / length,
            "p50": sorted_times[int(length * 0.5)],
            "p95": sorted_times[int(length * 0.95)],
            "p99": sorted_times[int(length * 0.99)]
        }
    
    def determine_model_status(self, metrics: Dict[str, Any]) -> ModelStatus:
        """메트릭을 기반으로 모델 상태 결정"""
        try:
            response_time_p95 = metrics.get("response_time_p95", 0)
            error_rate = metrics.get("error_rate", 0)
            gpu_memory_percent = metrics.get("gpu_memory_usage_percent", 0)
            gpu_temp = metrics.get("temperature", 0)
            
            # 크리티컬 상태 확인
            if (response_time_p95 > self.thresholds["response_time_critical"] or
                error_rate > self.thresholds["error_rate_critical"] or
                (gpu_memory_percent and gpu_memory_percent > self.thresholds["gpu_memory_critical"]) or
                (gpu_temp and gpu_temp > self.thresholds["gpu_temp_critical"])):
                return ModelStatus.UNHEALTHY
            
            # 경고 상태 확인
            if (response_time_p95 > self.thresholds["response_time_warning"] or
                error_rate > self.thresholds["error_rate_warning"] or
                (gpu_memory_percent and gpu_memory_percent > self.thresholds["gpu_memory_warning"]) or
                (gpu_temp and gpu_temp > self.thresholds["gpu_temp_warning"])):
                return ModelStatus.DEGRADED
            
            return ModelStatus.HEALTHY
            
        except Exception as e:
            log_error_with_context(e, {"component": "determine_model_status"})
            return ModelStatus.UNKNOWN
    
    async def perform_health_check(self, vllm_service) -> ModelHealthMetrics:
        """모델 헬스체크 수행"""
        start_time = time.time()
        
        try:
            # 시스템 메트릭 수집
            system_metrics = self.get_system_metrics()
            
            # 응답 시간 통계 계산
            response_stats = self.calculate_response_time_percentiles()
            
            # 에러율 계산
            error_rate = (self.error_count / max(self.request_count, 1)) * 100
            
            # GPU 메트릭
            gpu_metrics = self.get_gpu_metrics()
            
            # vLLM 서비스 상태 확인
            vllm_health = await vllm_service.health_check() if vllm_service else {"service_initialized": False}
            
            # 큐 길이 및 활성 요청 수 (vLLM 서비스에서 가져오기)
            vllm_stats = vllm_service.get_stats() if vllm_service else {}
            active_requests = vllm_stats.get("active_requests", 0)
            
            # 처리량 계산 (토큰/초)
            throughput = 0.0
            if self.response_times and vllm_stats:
                total_tokens = vllm_stats.get("total_tokens_generated", 0)
                total_time = sum(self.response_times)
                throughput = total_tokens / max(total_time, 1)
            
            # 메트릭 생성
            metrics = {
                "response_time_avg": response_stats["avg"],
                "response_time_p95": response_stats["p95"],
                "error_rate": error_rate / 100,  # 0-1 범위로 변환
                "memory_usage_percent": system_metrics.memory_usage_percent,
                "gpu_memory_usage_percent": gpu_metrics["gpu_memory_percent"],
                "temperature": gpu_metrics["gpu_temperature"],
                "throughput_tokens_per_second": throughput,
                "queue_length": 0,  # Ray 큐에서 가져와야 함
                "active_requests": active_requests
            }
            
            # 상태 결정
            status = self.determine_model_status(metrics)
            
            health_metrics = ModelHealthMetrics(
                status=status,
                last_check_time=time.time(),
                response_time_avg=response_stats["avg"],
                response_time_p95=response_stats["p95"],
                error_rate=error_rate / 100,
                memory_usage_percent=system_metrics.memory_usage_percent,
                gpu_memory_usage_percent=gpu_metrics["gpu_memory_percent"],
                temperature=gpu_metrics["gpu_temperature"],
                throughput_tokens_per_second=throughput,
                queue_length=0,
                active_requests=active_requests
            )
            
            # 히스토리에 추가
            self.health_history.append(health_metrics)
            if len(self.health_history) > self.max_history_size:
                self.health_history.pop(0)
            
            # 상태에 따른 로깅
            if status == ModelStatus.UNHEALTHY:
                logger.error(f"모델 상태 비정상: {metrics}")
            elif status == ModelStatus.DEGRADED:
                logger.warning(f"모델 성능 저하: {metrics}")
            else:
                logger.debug(f"모델 상태 정상: {metrics}")
            
            self.last_health_check = time.time()
            return health_metrics
            
        except Exception as e:
            log_error_with_context(e, {"component": "perform_health_check"})
            return ModelHealthMetrics(
                status=ModelStatus.ERROR,
                last_check_time=time.time(),
                response_time_avg=0.0,
                response_time_p95=0.0,
                error_rate=1.0,
                memory_usage_percent=0.0,
                gpu_memory_usage_percent=None,
                temperature=None,
                throughput_tokens_per_second=0.0,
                queue_length=0,
                active_requests=0
            )
    
    async def test_model_inference(self, vllm_service) -> Dict[str, Any]:
        """모델 추론 테스트 수행"""
        try:
            # 간단한 테스트 요청
            test_request = GenerateRequest(
                prompt="Hello",
                max_tokens=10,
                temperature=0.0
            )
            
            start_time = time.time()
            result = await vllm_service.generate(test_request)
            response_time = time.time() - start_time
            
            success = "text" in result and len(result["text"]) > 0
            
            # 메트릭 기록
            self.record_request_metrics(
                response_time=response_time,
                success=success,
                tokens_generated=result.get("tokens_generated", 0)
            )
            
            return {
                "success": success,
                "response_time": response_time,
                "tokens_generated": result.get("tokens_generated", 0),
                "error": None
            }
            
        except Exception as e:
            # 실패 메트릭 기록
            self.record_request_metrics(
                response_time=10.0,  # 타임아웃으로 가정
                success=False
            )
            
            return {
                "success": False,
                "response_time": 10.0,
                "tokens_generated": 0,
                "error": str(e)
            }
    
    def get_health_summary(self) -> Dict[str, Any]:
        """헬스 상태 요약 반환"""
        if not self.health_history:
            return {
                "status": ModelStatus.UNKNOWN,
                "last_check": None,
                "checks_performed": 0
            }
        
        latest = self.health_history[-1]
        
        # 최근 상태 통계
        recent_statuses = [h.status for h in self.health_history[-10:]]
        status_counts = {}
        for status in recent_statuses:
            status_counts[status.value] = status_counts.get(status.value, 0) + 1
        
        return {
            "current_status": latest.status.value,
            "last_check": datetime.fromtimestamp(latest.last_check_time).isoformat(),
            "checks_performed": len(self.health_history),
            "response_time_avg": latest.response_time_avg,
            "response_time_p95": latest.response_time_p95,
            "error_rate": latest.error_rate,
            "gpu_memory_usage": latest.gpu_memory_usage_percent,
            "gpu_temperature": latest.temperature,
            "throughput": latest.throughput_tokens_per_second,
            "active_requests": latest.active_requests,
            "recent_status_distribution": status_counts,
            "alerts": self._generate_alerts(latest)
        }
    
    def _generate_alerts(self, metrics: ModelHealthMetrics) -> List[Dict[str, str]]:
        """현재 메트릭 기반 알림 생성"""
        alerts = []
        
        if metrics.response_time_p95 > self.thresholds["response_time_warning"]:
            severity = "critical" if metrics.response_time_p95 > self.thresholds["response_time_critical"] else "warning"
            alerts.append({
                "type": "response_time",
                "severity": severity,
                "message": f"응답 시간이 높습니다: {metrics.response_time_p95:.2f}초",
                "threshold": self.thresholds[f"response_time_{severity}"]
            })
        
        if metrics.error_rate > self.thresholds["error_rate_warning"]:
            severity = "critical" if metrics.error_rate > self.thresholds["error_rate_critical"] else "warning"
            alerts.append({
                "type": "error_rate",
                "severity": severity,
                "message": f"에러율이 높습니다: {metrics.error_rate:.1%}",
                "threshold": self.thresholds[f"error_rate_{severity}"]
            })
        
        if metrics.gpu_memory_usage_percent and metrics.gpu_memory_usage_percent > self.thresholds["gpu_memory_warning"]:
            severity = "critical" if metrics.gpu_memory_usage_percent > self.thresholds["gpu_memory_critical"] else "warning"
            alerts.append({
                "type": "gpu_memory",
                "severity": severity,
                "message": f"GPU 메모리 사용률이 높습니다: {metrics.gpu_memory_usage_percent:.1f}%",
                "threshold": self.thresholds[f"gpu_memory_{severity}"]
            })
        
        if metrics.temperature and metrics.temperature > self.thresholds["gpu_temp_warning"]:
            severity = "critical" if metrics.temperature > self.thresholds["gpu_temp_critical"] else "warning"
            alerts.append({
                "type": "gpu_temperature",
                "severity": severity,
                "message": f"GPU 온도가 높습니다: {metrics.temperature:.1f}°C",
                "threshold": self.thresholds[f"gpu_temp_{severity}"]
            })
        
        return alerts
    
    def get_historical_data(self, hours: int = 24) -> List[Dict[str, Any]]:
        """과거 데이터 반환"""
        cutoff_time = time.time() - (hours * 3600)
        
        return [
            {
                "timestamp": h.last_check_time,
                "status": h.status.value,
                "response_time_avg": h.response_time_avg,
                "response_time_p95": h.response_time_p95,
                "error_rate": h.error_rate,
                "gpu_memory_usage": h.gpu_memory_usage_percent,
                "gpu_temperature": h.temperature,
                "throughput": h.throughput_tokens_per_second,
                "active_requests": h.active_requests
            }
            for h in self.health_history
            if h.last_check_time > cutoff_time
        ]

# 전역 모델 헬스 체커 인스턴스
model_health_checker = ModelHealthChecker()

class ModelMonitorService:
    """모델 모니터링 서비스"""
    
    def __init__(self, health_checker: ModelHealthChecker):
        self.health_checker = health_checker
        self.monitoring_active = False
        self.monitoring_task = None
    
    async def start_monitoring(self, vllm_service, interval: int = 30):
        """모니터링 시작"""
        if self.monitoring_active:
            logger.warning("모니터링이 이미 활성화되어 있습니다")
            return
        
        self.monitoring_active = True
        self.monitoring_task = asyncio.create_task(
            self._monitoring_loop(vllm_service, interval)
        )
        logger.info(f"모델 모니터링 시작됨 - 간격: {interval}초")
    
    async def stop_monitoring(self):
        """모니터링 중지"""
        self.monitoring_active = False
        if self.monitoring_task:
            self.monitoring_task.cancel()
            try:
                await self.monitoring_task
            except asyncio.CancelledError:
                pass
        logger.info("모델 모니터링 중지됨")
    
    async def _monitoring_loop(self, vllm_service, interval: int):
        """모니터링 루프"""
        while self.monitoring_active:
            try:
                await self.health_checker.perform_health_check(vllm_service)
                await asyncio.sleep(interval)
            except asyncio.CancelledError:
                break
            except Exception as e:
                log_error_with_context(e, {"component": "monitoring_loop"})
                await asyncio.sleep(interval)
    
    async def get_current_status(self) -> Dict[str, Any]:
        """현재 상태 반환"""
        return self.health_checker.get_health_summary()
    
    async def get_historical_data(self, hours: int = 24) -> List[Dict[str, Any]]:
        """과거 데이터 반환"""
        return self.health_checker.get_historical_data(hours)
    
    async def run_health_check(self, vllm_service) -> Dict[str, Any]:
        """수동 헬스체크 실행"""
        metrics = await self.health_checker.perform_health_check(vllm_service)
        return {
            "status": metrics.status.value,
            "metrics": {
                "response_time_avg": metrics.response_time_avg,
                "response_time_p95": metrics.response_time_p95,
                "error_rate": metrics.error_rate,
                "memory_usage": metrics.memory_usage_percent,
                "gpu_memory_usage": metrics.gpu_memory_usage_percent,
                "gpu_temperature": metrics.temperature,
                "throughput": metrics.throughput_tokens_per_second,
                "active_requests": metrics.active_requests
            },
            "timestamp": metrics.last_check_time
        }

# 전역 모니터링 서비스 인스턴스
model_monitor_service = ModelMonitorService(model_health_checker)