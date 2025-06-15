"""
app/services/vllm_engine.py
vLLM 엔진 Ray Actor 및 관리 서비스
"""

import asyncio
import time
import uuid
from typing import Dict, Any, Optional, AsyncGenerator, List
import ray
from vllm import AsyncLLMEngine, AsyncEngineArgs, SamplingParams
from vllm.outputs import RequestOutput

from app.core.config import settings
from app.core.logging import get_logger, log_error_with_context
from app.models.schemas import GenerateRequest, FinishReason

logger = get_logger("vllm_engine")

@ray.remote(num_gpus=1)
class VLLMEngineActor:
    """vLLM 추론 엔진 Ray Actor"""
    
    def __init__(self):
        self.engine: Optional[AsyncLLMEngine] = None
        self.request_id_counter = 0
        self.active_requests: Dict[str, Dict[str, Any]] = {}
        self.model_info: Dict[str, Any] = {}
        self.stats = {
            "total_requests": 0,
            "successful_requests": 0,
            "failed_requests": 0,
            "total_tokens_generated": 0,
            "total_prompt_tokens": 0,
            "start_time": time.time()
        }
        
        # 엔진 초기화
        self._initialize_engine()
    
    def _initialize_engine(self):
        """vLLM 엔진 초기화"""
        try:
            logger.info(f"vLLM 엔진 초기화 시작 - 모델: {settings.MODEL_PATH}")
            start_time = time.time()
            
            # 엔진 인자 설정
            engine_args = AsyncEngineArgs(**settings.get_vllm_engine_args())
            
            # 엔진 생성
            self.engine = AsyncLLMEngine.from_engine_args(engine_args)
            
            # 모델 정보 저장
            self.model_info = {
                "model_name": settings.MODEL_NAME,
                "model_path": settings.MODEL_PATH,
                "tensor_parallel_size": settings.TENSOR_PARALLEL_SIZE,
                "gpu_memory_utilization": settings.GPU_MEMORY_UTILIZATION,
                "max_model_len": settings.MAX_MODEL_LEN,
                "dtype": settings.DTYPE,
                "initialized_at": time.time(),
                "initialization_time": time.time() - start_time
            }
            
            logger.info(f"vLLM 엔진 초기화 완료 - {self.model_info['initialization_time']:.2f}초")
            
        except Exception as e:
            logger.error(f"vLLM 엔진 초기화 실패: {e}")
            raise
    
    def _create_sampling_params(self, request: GenerateRequest) -> SamplingParams:
        """샘플링 파라미터 생성"""
        return SamplingParams(
            temperature=request.temperature,
            top_p=request.top_p,
            top_k=request.top_k,
            max_tokens=request.max_tokens,
            repetition_penalty=request.repetition_penalty,
            frequency_penalty=request.frequency_penalty,
            presence_penalty=request.presence_penalty,
            stop=request.stop,
            seed=request.seed
        )
    
    def _generate_request_id(self) -> str:
        """요청 ID 생성"""
        self.request_id_counter += 1
        return f"req_{self.request_id_counter}_{uuid.uuid4().hex[:8]}"
    
    def _calculate_tokens(self, text: str) -> int:
        """대략적인 토큰 수 계산 (정확한 토크나이저 사용 권장)"""
        # 간단한 토큰 수 추정 (실제 토크나이저 사용 권장)
        return len(text.split())
    
    async def generate(self, request: GenerateRequest) -> Dict[str, Any]:
        """단일 텍스트 생성"""
        if not self.engine:
            raise RuntimeError("vLLM 엔진이 초기화되지 않았습니다")
        
        request_id = self._generate_request_id()
        start_time = time.time()
        
        try:
            logger.debug(f"생성 요청 시작 - ID: {request_id}")
            
            # 요청 추적 시작
            self.active_requests[request_id] = {
                "start_time": start_time,
                "prompt": request.prompt,
                "max_tokens": request.max_tokens
            }
            
            # 샘플링 파라미터 생성
            sampling_params = self._create_sampling_params(request)
            
            # 비동기 생성 실행
            outputs = []
            async for output in self.engine.generate(
                request.prompt, 
                sampling_params, 
                request_id
            ):
                outputs.append(output)
            
            if not outputs:
                raise RuntimeError("생성 결과가 없습니다")
            
            # 최종 결과 처리
            final_output = outputs[-1]
            generated_text = final_output.outputs[0].text
            finish_reason_str = final_output.outputs[0].finish_reason
            
            # FinishReason 매핑
            finish_reason = self._map_finish_reason(finish_reason_str)
            
            # 통계 계산
            generation_time = time.time() - start_time
            prompt_tokens = self._calculate_tokens(request.prompt)
            generated_tokens = len(final_output.outputs[0].token_ids)
            total_tokens = prompt_tokens + generated_tokens
            tokens_per_second = generated_tokens / generation_time if generation_time > 0 else 0
            
            # 통계 업데이트
            self.stats["total_requests"] += 1
            self.stats["successful_requests"] += 1
            self.stats["total_tokens_generated"] += generated_tokens
            self.stats["total_prompt_tokens"] += prompt_tokens
            
            result = {
                "text": generated_text,
                "prompt": request.prompt,
                "tokens_generated": generated_tokens,
                "prompt_tokens": prompt_tokens,
                "total_tokens": total_tokens,
                "finish_reason": finish_reason,
                "generation_time": generation_time,
                "tokens_per_second": tokens_per_second,
                "model_name": settings.MODEL_NAME,
                "request_id": request_id
            }
            
            logger.debug(f"생성 완료 - ID: {request_id}, 시간: {generation_time:.2f}초, "
                        f"토큰/초: {tokens_per_second:.1f}")
            
            return result
            
        except Exception as e:
            self.stats["failed_requests"] += 1
            logger.error(f"생성 실패 - ID: {request_id}, 오류: {e}")
            raise
        finally:
            # 요청 추적 종료
            self.active_requests.pop(request_id, None)
    
    async def generate_stream(self, request: GenerateRequest) -> AsyncGenerator[Dict[str, Any], None]:
        """스트리밍 텍스트 생성"""
        if not self.engine:
            raise RuntimeError("vLLM 엔진이 초기화되지 않았습니다")
        
        request_id = self._generate_request_id()
        start_time = time.time()
        
        try:
            logger.debug(f"스트리밍 생성 요청 시작 - ID: {request_id}")
            
            # 요청 추적 시작
            self.active_requests[request_id] = {
                "start_time": start_time,
                "prompt": request.prompt,
                "max_tokens": request.max_tokens,
                "streaming": True
            }
            
            # 샘플링 파라미터 생성
            sampling_params = self._create_sampling_params(request)
            
            # 스트리밍 생성
            tokens_generated = 0
            async for output in self.engine.generate(
                request.prompt, 
                sampling_params, 
                request_id
            ):
                current_text = output.outputs[0].text
                is_finished = output.finished
                finish_reason_str = output.outputs[0].finish_reason if is_finished else None
                tokens_generated = len(output.outputs[0].token_ids)
                
                yield {
                    "text": current_text,
                    "is_finished": is_finished,
                    "finish_reason": self._map_finish_reason(finish_reason_str) if finish_reason_str else None,
                    "tokens_generated": tokens_generated,
                    "request_id": request_id
                }
                
                if is_finished:
                    break
            
            # 통계 업데이트
            generation_time = time.time() - start_time
            self.stats["total_requests"] += 1
            self.stats["successful_requests"] += 1
            self.stats["total_tokens_generated"] += tokens_generated
            self.stats["total_prompt_tokens"] += self._calculate_tokens(request.prompt)
            
            logger.debug(f"스트리밍 생성 완료 - ID: {request_id}, 시간: {generation_time:.2f}초")
            
        except Exception as e:
            self.stats["failed_requests"] += 1
            logger.error(f"스트리밍 생성 실패 - ID: {request_id}, 오류: {e}")
            raise
        finally:
            # 요청 추적 종료
            self.active_requests.pop(request_id, None)
    
    async def generate_batch(self, requests: List[GenerateRequest]) -> List[Dict[str, Any]]:
        """배치 텍스트 생성"""
        if not self.engine:
            raise RuntimeError("vLLM 엔진이 초기화되지 않았습니다")
        
        start_time = time.time()
        results = []
        
        try:
            logger.debug(f"배치 생성 요청 시작 - 요청 수: {len(requests)}")
            
            # 동시 실행
            tasks = [self.generate(request) for request in requests]
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # 예외 처리
            for i, result in enumerate(results):
                if isinstance(result, Exception):
                    logger.error(f"배치 요청 {i} 실패: {result}")
                    results[i] = {
                        "error": str(result),
                        "request_index": i
                    }
            
            batch_time = time.time() - start_time
            logger.debug(f"배치 생성 완료 - 시간: {batch_time:.2f}초")
            
            return results
            
        except Exception as e:
            logger.error(f"배치 생성 실패: {e}")
            raise
    
    def _map_finish_reason(self, reason: str) -> FinishReason:
        """vLLM finish reason을 스키마 enum으로 매핑"""
        mapping = {
            "stop": FinishReason.STOP,
            "length": FinishReason.LENGTH,
            "tool_calls": FinishReason.TOOL_CALLS,
            "content_filter": FinishReason.CONTENT_FILTER
        }
        return mapping.get(reason, FinishReason.STOP)
    
    async def health_check(self) -> Dict[str, Any]:
        """엔진 상태 확인"""
        uptime = time.time() - self.stats["start_time"]
        
        return {
            "engine_initialized": self.engine is not None,
            "active_requests": len(self.active_requests),
            "uptime": uptime,
            "stats": self.stats.copy(),
            "model_info": self.model_info.copy()
        }
    
    def get_model_info(self) -> Dict[str, Any]:
        """모델 정보 반환"""
        return self.model_info.copy()
    
    def get_stats(self) -> Dict[str, Any]:
        """통계 정보 반환"""
        stats = self.stats.copy()
        stats["uptime"] = time.time() - stats["start_time"]
        stats["active_requests"] = len(self.active_requests)
        return stats
    
    async def abort_request(self, request_id: str) -> bool:
        """요청 중단"""
        try:
            if request_id in self.active_requests:
                # vLLM에서 요청 중단 (실제 구현은 vLLM 버전에 따라 다를 수 있음)
                await self.engine.abort(request_id)
                self.active_requests.pop(request_id, None)
                logger.info(f"요청 중단됨 - ID: {request_id}")
                return True
            return False
        except Exception as e:
            logger.error(f"요청 중단 실패 - ID: {request_id}, 오류: {e}")
            return False

class VLLMService:
    """vLLM 서비스 관리 클래스"""
    
    def __init__(self):
        self.engine_actor: Optional[ray.ObjectRef] = None
        self._initialized = False
        self._start_time = time.time()
    
    def initialize(self):
        """vLLM 서비스 초기화"""
        if self._initialized:
            return
        
        try:
            logger.info("vLLM 서비스 초기화 시작")
            
            # vLLM 엔진 Actor 생성
            self.engine_actor = VLLMEngineActor.remote()
            
            # 초기화 대기 (헬스체크로 확인)
            health_check = ray.get(self.engine_actor.health_check.remote())
            if not health_check.get("engine_initialized", False):
                raise RuntimeError("vLLM 엔진 초기화 실패")
            
            self._initialized = True
            initialization_time = time.time() - self._start_time
            
            logger.info(f"vLLM 서비스 초기화 완료 - {initialization_time:.2f}초")
            
        except Exception as e:
            log_error_with_context(e, {"component": "VLLMService"})
            raise
    
    async def generate(self, request: GenerateRequest) -> Dict[str, Any]:
        """텍스트 생성 요청"""
        if not self._initialized:
            raise RuntimeError("vLLM 서비스가 초기화되지 않았습니다")
        
        try:
            result = await self.engine_actor.generate.remote(request)
            return ray.get(result)
        except Exception as e:
            log_error_with_context(e, {"request": request.dict()})
            raise
    
    async def generate_stream(self, request: GenerateRequest) -> AsyncGenerator[Dict[str, Any], None]:
        """스트리밍 텍스트 생성"""
        if not self._initialized:
            raise RuntimeError("vLLM 서비스가 초기화되지 않았습니다")
        
        try:
            async for chunk in self.engine_actor.generate_stream.remote(request):
                yield ray.get(chunk)
        except Exception as e:
            log_error_with_context(e, {"request": request.dict()})
            raise
    
    async def generate_batch(self, requests: List[GenerateRequest]) -> List[Dict[str, Any]]:
        """배치 텍스트 생성"""
        if not self._initialized:
            raise RuntimeError("vLLM 서비스가 초기화되지 않았습니다")
        
        try:
            result = await self.engine_actor.generate_batch.remote(requests)
            return ray.get(result)
        except Exception as e:
            log_error_with_context(e, {"request_count": len(requests)})
            raise
    
    async def health_check(self) -> Dict[str, Any]:
        """서비스 상태 확인"""
        try:
            if not self._initialized:
                return {
                    "service_initialized": False,
                    "engine_status": None
                }
            
            result = await self.engine_actor.health_check.remote()
            engine_status = ray.get(result)
            
            return {
                "service_initialized": True,
                "engine_status": engine_status,
                "service_uptime": time.time() - self._start_time
            }
        except Exception as e:
            log_error_with_context(e, {"component": "VLLMService.health_check"})
            return {
                "service_initialized": False,
                "engine_status": None,
                "error": str(e)
            }
    
    def get_model_info(self) -> Optional[Dict[str, Any]]:
        """모델 정보 조회"""
        if not self._initialized:
            return None
        
        try:
            result = ray.get(self.engine_actor.get_model_info.remote())
            return result
        except Exception as e:
            log_error_with_context(e, {"component": "VLLMService.get_model_info"})
            return None
    
    def get_stats(self) -> Optional[Dict[str, Any]]:
        """통계 정보 조회"""
        if not self._initialized:
            return None
        
        try:
            result = ray.get(self.engine_actor.get_stats.remote())
            return result
        except Exception as e:
            log_error_with_context(e, {"component": "VLLMService.get_stats"})
            return None
    
    def shutdown(self):
        """서비스 종료"""
        if self._initialized:
            try:
                # Ray Actor 종료
                if self.engine_actor:
                    ray.kill(self.engine_actor)
                
                self._initialized = False
                logger.info("vLLM 서비스 종료 완료")
                
            except Exception as e:
                log_error_with_context(e, {"component": "VLLMService.shutdown"})

# 전역 vLLM 서비스 인스턴스
vllm_service = VLLMService()