#!/usr/bin/env python3
"""
examples/model_status_example.py
vLLM 모델 상태 체크 예제

이 스크립트는 vLLM API 서버의 모델 상태를 체크하고
다양한 정보를 확인하는 방법을 보여줍니다.

실행 방법:
    python examples/model_status_example.py
    python examples/model_status_example.py --api-base http://localhost:8000
    python examples/model_status_example.py --detailed --export-json
"""

import argparse
import asyncio
import json
import sys
import time
from datetime import datetime
from typing import Dict, List, Optional, Any
import aiohttp
import requests
from dataclasses import dataclass, asdict
from pathlib import Path

@dataclass
class ModelInfo:
    """모델 정보 데이터 클래스"""
    id: str
    object: str
    created: Optional[int] = None
    owned_by: Optional[str] = None
    permission: Optional[List[Dict]] = None
    root: Optional[str] = None
    parent: Optional[str] = None

@dataclass
class ServerStatus:
    """서버 상태 정보 데이터 클래스"""
    is_healthy: bool
    response_time_ms: float
    timestamp: str
    error_message: Optional[str] = None

@dataclass
class ModelStatus:
    """모델 상태 종합 정보"""
    server_status: ServerStatus
    models: List[ModelInfo]
    model_count: int
    primary_model: Optional[str] = None

class ModelStatusChecker:
    """모델 상태 체크 클래스"""
    
    def __init__(self, api_base: str = "http://localhost:8000"):
        self.api_base = api_base.rstrip('/')
        self.session = requests.Session()
        self.session.timeout = 30
        
    def check_server_health(self) -> ServerStatus:
        """서버 헬스 상태 체크"""
        start_time = time.time()
        timestamp = datetime.now().isoformat()
        
        try:
            response = self.session.get(f"{self.api_base}/health")
            response_time_ms = (time.time() - start_time) * 1000
            
            if response.status_code == 200:
                return ServerStatus(
                    is_healthy=True,
                    response_time_ms=response_time_ms,
                    timestamp=timestamp
                )
            else:
                return ServerStatus(
                    is_healthy=False,
                    response_time_ms=response_time_ms,
                    timestamp=timestamp,
                    error_message=f"HTTP {response.status_code}: {response.text}"
                )
                
        except requests.exceptions.ConnectionError:
            return ServerStatus(
                is_healthy=False,
                response_time_ms=0,
                timestamp=timestamp,
                error_message="Connection refused - 서버가 실행 중이지 않거나 접근할 수 없습니다."
            )
        except requests.exceptions.Timeout:
            return ServerStatus(
                is_healthy=False,
                response_time_ms=0,
                timestamp=timestamp,
                error_message="Request timeout - 서버 응답 시간이 초과되었습니다."
            )
        except Exception as e:
            return ServerStatus(
                is_healthy=False,
                response_time_ms=0,
                timestamp=timestamp,
                error_message=f"Unexpected error: {str(e)}"
            )
    
    def get_models(self) -> List[ModelInfo]:
        """사용 가능한 모델 목록 조회"""
        try:
            response = self.session.get(f"{self.api_base}/v1/models")
            
            if response.status_code == 200:
                data = response.json()
                models = []
                
                for model_data in data.get("data", []):
                    model = ModelInfo(
                        id=model_data.get("id", "unknown"),
                        object=model_data.get("object", "model"),
                        created=model_data.get("created"),
                        owned_by=model_data.get("owned_by"),
                        permission=model_data.get("permission"),
                        root=model_data.get("root"),
                        parent=model_data.get("parent")
                    )
                    models.append(model)
                
                return models
            else:
                print(f"❌ 모델 목록 조회 실패: HTTP {response.status_code}")
                return []
                
        except Exception as e:
            print(f"❌ 모델 목록 조회 중 오류 발생: {e}")
            return []
    
    def get_model_details(self, model_id: str) -> Optional[Dict[str, Any]]:
        """특정 모델의 세부 정보 조회"""
        try:
            response = self.session.get(f"{self.api_base}/v1/models/{model_id}")
            
            if response.status_code == 200:
                return response.json()
            else:
                print(f"❌ 모델 '{model_id}' 세부 정보 조회 실패: HTTP {response.status_code}")
                return None
                
        except Exception as e:
            print(f"❌ 모델 '{model_id}' 세부 정보 조회 중 오류 발생: {e}")
            return None
    
    async def test_model_inference(self, model_id: str, prompt: str = "Hello, how are you?") -> Dict[str, Any]:
        """모델 추론 테스트"""
        try:
            async with aiohttp.ClientSession() as session:
                payload = {
                    "model": model_id,
                    "prompt": prompt,
                    "max_tokens": 50,
                    "temperature": 0.7,
                    "top_p": 0.9
                }
                
                start_time = time.time()
                async with session.post(
                    f"{self.api_base}/v1/completions",
                    json=payload,
                    timeout=30
                ) as response:
                    end_time = time.time()
                    
                    if response.status == 200:
                        result = await response.json()
                        return {
                            "success": True,
                            "response_time": end_time - start_time,
                            "tokens_generated": len(result.get("choices", [{}])[0].get("text", "").split()),
                            "result": result
                        }
                    else:
                        error_text = await response.text()
                        return {
                            "success": False,
                            "response_time": end_time - start_time,
                            "error": f"HTTP {response.status}: {error_text}"
                        }
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }
    
    def check_all_status(self) -> ModelStatus:
        """모든 상태 정보 종합 체크"""
        print("🔍 vLLM API 서버 상태 체크 시작...")
        
        # 서버 헬스 체크
        print("\n1️⃣ 서버 헬스 체크 중...")
        server_status = self.check_server_health()
        
        if not server_status.is_healthy:
            print(f"❌ 서버 상태: 비정상")
            print(f"   오류: {server_status.error_message}")
            return ModelStatus(
                server_status=server_status,
                models=[],
                model_count=0
            )
        
        print(f"✅ 서버 상태: 정상 (응답시간: {server_status.response_time_ms:.1f}ms)")
        
        # 모델 목록 조회
        print("\n2️⃣ 모델 목록 조회 중...")
        models = self.get_models()
        
        if not models:
            print("❌ 사용 가능한 모델이 없습니다.")
            return ModelStatus(
                server_status=server_status,
                models=[],
                model_count=0
            )
        
        print(f"✅ {len(models)}개의 모델 발견")
        
        # 주요 모델 식별
        primary_model = models[0].id if models else None
        
        return ModelStatus(
            server_status=server_status,
            models=models,
            model_count=len(models),
            primary_model=primary_model
        )

def print_detailed_status(status: ModelStatus, checker: ModelStatusChecker):
    """상세 상태 정보 출력"""
    print(f"\n{'='*60}")
    print("📊 상세 상태 리포트")
    print(f"{'='*60}")
    
    # 서버 정보
    print(f"\n🖥️  서버 정보:")
    print(f"   • API 주소: {checker.api_base}")
    print(f"   • 상태: {'✅ 정상' if status.server_status.is_healthy else '❌ 비정상'}")
    print(f"   • 응답시간: {status.server_status.response_time_ms:.1f}ms")
    print(f"   • 체크 시간: {status.server_status.timestamp}")
    
    if status.server_status.error_message:
        print(f"   • 오류: {status.server_status.error_message}")
    
    # 모델 정보
    print(f"\n🤖 모델 정보:")
    print(f"   • 총 모델 수: {status.model_count}")
    
    if status.primary_model:
        print(f"   • 주요 모델: {status.primary_model}")
    
    if status.models:
        print(f"\n   📋 모델 목록:")
        for i, model in enumerate(status.models, 1):
            print(f"      {i}. {model.id}")
            if model.owned_by:
                print(f"         • 소유자: {model.owned_by}")
            if model.created:
                created_date = datetime.fromtimestamp(model.created).strftime("%Y-%m-%d %H:%M:%S")
                print(f"         • 생성 시간: {created_date}")

def print_summary_status(status: ModelStatus):
    """요약 상태 정보 출력"""
    print(f"\n{'='*40}")
    print("📋 상태 요약")
    print(f"{'='*40}")
    
    # 서버 상태
    server_emoji = "✅" if status.server_status.is_healthy else "❌"
    print(f"{server_emoji} 서버: {'정상' if status.server_status.is_healthy else '비정상'}")
    
    if status.server_status.is_healthy:
        print(f"⚡ 응답시간: {status.server_status.response_time_ms:.1f}ms")
    
    # 모델 상태
    if status.model_count > 0:
        print(f"🤖 모델: {status.model_count}개 사용 가능")
        if status.primary_model:
            print(f"🎯 주요 모델: {status.primary_model}")
    else:
        print("❌ 모델: 사용 가능한 모델 없음")

async def test_model_performance(checker: ModelStatusChecker, model_id: str):
    """모델 성능 테스트"""
    print(f"\n🧪 모델 '{model_id}' 성능 테스트 중...")
    
    test_prompts = [
        "Hello, how are you?",
        "What is the capital of France?",
        "Explain machine learning in simple terms."
    ]
    
    total_time = 0
    total_tokens = 0
    successful_tests = 0
    
    for i, prompt in enumerate(test_prompts, 1):
        print(f"   테스트 {i}/{len(test_prompts)}: {prompt[:30]}...")
        
        result = await checker.test_model_inference(model_id, prompt)
        
        if result["success"]:
            successful_tests += 1
            total_time += result["response_time"]
            total_tokens += result["tokens_generated"]
            print(f"      ✅ 성공 ({result['response_time']:.2f}초, {result['tokens_generated']}토큰)")
        else:
            print(f"      ❌ 실패: {result['error']}")
    
    if successful_tests > 0:
        avg_time = total_time / successful_tests
        avg_tokens = total_tokens / successful_tests
        tokens_per_second = avg_tokens / avg_time if avg_time > 0 else 0
        
        print(f"\n📊 성능 요약:")
        print(f"   • 성공률: {successful_tests}/{len(test_prompts)} ({successful_tests/len(test_prompts)*100:.1f}%)")
        print(f"   • 평균 응답시간: {avg_time:.2f}초")
        print(f"   • 평균 토큰 수: {avg_tokens:.1f}개")
        print(f"   • 토큰/초: {tokens_per_second:.1f}")
    else:
        print(f"\n❌ 모든 테스트 실패")

def export_to_json(status: ModelStatus, filename: str):
    """상태 정보를 JSON 파일로 내보내기"""
    try:
        # 데이터 직렬화를 위한 딕셔너리 변환
        status_dict = {
            "server_status": asdict(status.server_status),
            "models": [asdict(model) for model in status.models],
            "model_count": status.model_count,
            "primary_model": status.primary_model,
            "export_timestamp": datetime.now().isoformat()
        }
        
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(status_dict, f, indent=2, ensure_ascii=False)
        
        print(f"✅ 상태 정보가 '{filename}'에 저장되었습니다.")
        
    except Exception as e:
        print(f"❌ JSON 내보내기 실패: {e}")

async def main():
    """메인 함수"""
    parser = argparse.ArgumentParser(description="vLLM 모델 상태 체크 도구")
    
    parser.add_argument(
        "--api-base",
        default="http://localhost:8000",
        help="vLLM API 서버 주소 (기본값: http://localhost:8000)"
    )
    
    parser.add_argument(
        "--detailed",
        action="store_true",
        help="상세한 상태 정보 표시"
    )
    
    parser.add_argument(
        "--test-performance",
        action="store_true",
        help="모델 성능 테스트 실행"
    )
    
    parser.add_argument(
        "--export-json",
        metavar="FILENAME",
        help="상태 정보를 JSON 파일로 내보내기"
    )
    
    parser.add_argument(
        "--model-id",
        help="테스트할 특정 모델 ID (성능 테스트 시 사용)"
    )
    
    args = parser.parse_args()
    
    print("🚀 vLLM 모델 상태 체크 도구")
    print(f"📡 연결 대상: {args.api_base}")
    
    # 상태 체크 실행
    checker = ModelStatusChecker(args.api_base)
    status = checker.check_all_status()
    
    # 결과 출력
    if args.detailed:
        print_detailed_status(status, checker)
    else:
        print_summary_status(status)
    
    # 성능 테스트
    if args.test_performance and status.server_status.is_healthy:
        model_to_test = args.model_id or status.primary_model
        
        if model_to_test:
            await test_model_performance(checker, model_to_test)
        else:
            print("❌ 테스트할 모델이 없습니다.")
    
    # JSON 내보내기
    if args.export_json:
        filename = args.export_json if args.export_json.endswith('.json') else f"{args.export_json}.json"
        export_to_json(status, filename)
    
    # 최종 상태 코드 반환
    if not status.server_status.is_healthy:
        print(f"\n❌ 서버 상태가 비정상입니다.")
        sys.exit(1)
    elif status.model_count == 0:
        print(f"\n⚠️  사용 가능한 모델이 없습니다.")
        sys.exit(1)
    else:
        print(f"\n✅ 모든 상태가 정상입니다.")
        sys.exit(0)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\n⚠️  사용자에 의해 중단되었습니다.")
        sys.exit(130)
    except Exception as e:
        print(f"\n❌ 예기치 않은 오류 발생: {e}")
        sys.exit(1)
