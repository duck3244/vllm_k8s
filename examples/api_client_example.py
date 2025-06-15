#!/usr/bin/env python3
"""
examples/api_client_example.py
vLLM API 클라이언트 사용 예제

이 스크립트는 vLLM API 서버와 상호작용하는 다양한 방법을 보여줍니다.
동기/비동기 호출, 스트리밍, 배치 처리 등의 예제를 포함합니다.

실행 방법:
    python examples/api_client_example.py
    python examples/api_client_example.py --api-base http://localhost:8000
    python examples/api_client_example.py --demo streaming
    python examples/api_client_example.py --demo batch --input-file prompts.txt
"""

import argparse
import asyncio
import json
import sys
import time
from datetime import datetime
from typing import Dict, List, Optional, Any, AsyncGenerator, Generator
import aiohttp
import requests
from dataclasses import dataclass
from pathlib import Path
import logging

# 로깅 설정
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

@dataclass
class CompletionRequest:
    """완성 요청 데이터 클래스"""
    prompt: str
    model: str = "default"
    max_tokens: int = 100
    temperature: float = 0.7
    top_p: float = 0.9
    frequency_penalty: float = 0.0
    presence_penalty: float = 0.0
    stop: Optional[List[str]] = None
    stream: bool = False

@dataclass
class ChatMessage:
    """채팅 메시지 데이터 클래스"""
    role: str  # "system", "user", "assistant"
    content: str

@dataclass
class ChatRequest:
    """채팅 요청 데이터 클래스"""
    messages: List[ChatMessage]
    model: str = "default"
    max_tokens: int = 100
    temperature: float = 0.7
    top_p: float = 0.9
    stream: bool = False

class VLLMAPIClient:
    """vLLM API 클라이언트 클래스"""
    
    def __init__(self, api_base: str = "http://localhost:8000", api_key: Optional[str] = None):
        self.api_base = api_base.rstrip('/')
        self.api_key = api_key
        self.session = requests.Session()
        self.session.timeout = 60
        
        # 헤더 설정
        self.headers = {
            "Content-Type": "application/json",
            "User-Agent": "vLLM-API-Client/1.0"
        }
        
        if api_key:
            self.headers["Authorization"] = f"Bearer {api_key}"
        
        self.session.headers.update(self.headers)
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.session.close()
    
    # 동기 메서드들
    def get_models(self) -> Dict[str, Any]:
        """사용 가능한 모델 목록 조회"""
        try:
            response = self.session.get(f"{self.api_base}/v1/models")
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            logger.error(f"모델 목록 조회 실패: {e}")
            raise
    
    def complete(self, request: CompletionRequest) -> Dict[str, Any]:
        """텍스트 완성 (동기)"""
        payload = {
            "model": request.model,
            "prompt": request.prompt,
            "max_tokens": request.max_tokens,
            "temperature": request.temperature,
            "top_p": request.top_p,
            "frequency_penalty": request.frequency_penalty,
            "presence_penalty": request.presence_penalty,
            "stream": False
        }
        
        if request.stop:
            payload["stop"] = request.stop
        
        try:
            response = self.session.post(f"{self.api_base}/v1/completions", json=payload)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            logger.error(f"완성 요청 실패: {e}")
            raise
    
    def complete_stream(self, request: CompletionRequest) -> Generator[Dict[str, Any], None, None]:
        """텍스트 완성 스트리밍 (동기)"""
        payload = {
            "model": request.model,
            "prompt": request.prompt,
            "max_tokens": request.max_tokens,
            "temperature": request.temperature,
            "top_p": request.top_p,
            "frequency_penalty": request.frequency_penalty,
            "presence_penalty": request.presence_penalty,
            "stream": True
        }
        
        if request.stop:
            payload["stop"] = request.stop
        
        try:
            response = self.session.post(
                f"{self.api_base}/v1/completions",
                json=payload,
                stream=True
            )
            response.raise_for_status()
            
            for line in response.iter_lines(decode_unicode=True):
                if line.startswith("data: "):
                    data_str = line[6:]  # "data: " 제거
                    if data_str.strip() == "[DONE]":
                        break
                    try:
                        chunk = json.loads(data_str)
                        yield chunk
                    except json.JSONDecodeError:
                        continue
                        
        except requests.exceptions.RequestException as e:
            logger.error(f"스트리밍 완성 요청 실패: {e}")
            raise
    
    def chat(self, request: ChatRequest) -> Dict[str, Any]:
        """채팅 완성 (동기)"""
        payload = {
            "model": request.model,
            "messages": [{"role": msg.role, "content": msg.content} for msg in request.messages],
            "max_tokens": request.max_tokens,
            "temperature": request.temperature,
            "top_p": request.top_p,
            "stream": False
        }
        
        try:
            response = self.session.post(f"{self.api_base}/v1/chat/completions", json=payload)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            logger.error(f"채팅 요청 실패: {e}")
            raise
    
    # 비동기 메서드들
    async def async_get_models(self) -> Dict[str, Any]:
        """사용 가능한 모델 목록 조회 (비동기)"""
        async with aiohttp.ClientSession(headers=self.headers) as session:
            try:
                async with session.get(f"{self.api_base}/v1/models") as response:
                    response.raise_for_status()
                    return await response.json()
            except aiohttp.ClientError as e:
                logger.error(f"비동기 모델 목록 조회 실패: {e}")
                raise
    
    async def async_complete(self, request: CompletionRequest) -> Dict[str, Any]:
        """텍스트 완성 (비동기)"""
        payload = {
            "model": request.model,
            "prompt": request.prompt,
            "max_tokens": request.max_tokens,
            "temperature": request.temperature,
            "top_p": request.top_p,
            "frequency_penalty": request.frequency_penalty,
            "presence_penalty": request.presence_penalty,
            "stream": False
        }
        
        if request.stop:
            payload["stop"] = request.stop
        
        async with aiohttp.ClientSession(headers=self.headers) as session:
            try:
                async with session.post(f"{self.api_base}/v1/completions", json=payload) as response:
                    response.raise_for_status()
                    return await response.json()
            except aiohttp.ClientError as e:
                logger.error(f"비동기 완성 요청 실패: {e}")
                raise
    
    async def async_complete_stream(self, request: CompletionRequest) -> AsyncGenerator[Dict[str, Any], None]:
        """텍스트 완성 스트리밍 (비동기)"""
        payload = {
            "model": request.model,
            "prompt": request.prompt,
            "max_tokens": request.max_tokens,
            "temperature": request.temperature,
            "top_p": request.top_p,
            "frequency_penalty": request.frequency_penalty,
            "presence_penalty": request.presence_penalty,
            "stream": True
        }
        
        if request.stop:
            payload["stop"] = request.stop
        
        async with aiohttp.ClientSession(headers=self.headers) as session:
            try:
                async with session.post(f"{self.api_base}/v1/completions", json=payload) as response:
                    response.raise_for_status()
                    
                    async for line in response.content:
                        line_str = line.decode('utf-8').strip()
                        if line_str.startswith("data: "):
                            data_str = line_str[6:]
                            if data_str == "[DONE]":
                                break
                            try:
                                chunk = json.loads(data_str)
                                yield chunk
                            except json.JSONDecodeError:
                                continue
                                
            except aiohttp.ClientError as e:
                logger.error(f"비동기 스트리밍 완성 요청 실패: {e}")
                raise
    
    async def async_chat(self, request: ChatRequest) -> Dict[str, Any]:
        """채팅 완성 (비동기)"""
        payload = {
            "model": request.model,
            "messages": [{"role": msg.role, "content": msg.content} for msg in request.messages],
            "max_tokens": request.max_tokens,
            "temperature": request.temperature,
            "top_p": request.top_p,
            "stream": False
        }
        
        async with aiohttp.ClientSession(headers=self.headers) as session:
            try:
                async with session.post(f"{self.api_base}/v1/chat/completions", json=payload) as response:
                    response.raise_for_status()
                    return await response.json()
            except aiohttp.ClientError as e:
                logger.error(f"비동기 채팅 요청 실패: {e}")
                raise

class DemoRunner:
    """데모 실행 클래스"""
    
    def __init__(self, api_base: str, api_key: Optional[str] = None):
        self.client = VLLMAPIClient(api_base, api_key)
    
    def run_basic_demo(self):
        """기본 사용법 데모"""
        print("🚀 기본 사용법 데모")
        print("=" * 50)
        
        try:
            # 모델 목록 조회
            print("1️⃣ 모델 목록 조회 중...")
            models = self.client.get_models()
            print(f"   사용 가능한 모델: {len(models.get('data', []))}개")
            
            for model in models.get('data', [])[:3]:  # 처음 3개만 표시
                print(f"   - {model.get('id', 'Unknown')}")
            
            # 기본 완성 요청
            print("\n2️⃣ 기본 텍스트 완성...")
            request = CompletionRequest(
                prompt="안녕하세요! 오늘은",
                max_tokens=50,
                temperature=0.7
            )
            
            start_time = time.time()
            result = self.client.complete(request)
            end_time = time.time()
            
            if result.get('choices'):
                generated_text = result['choices'][0]['text']
                print(f"   프롬프트: {request.prompt}")
                print(f"   생성 결과: {generated_text.strip()}")
                print(f"   소요 시간: {end_time - start_time:.2f}초")
            
            # 채팅 완성 요청
            print("\n3️⃣ 채팅 완성...")
            chat_request = ChatRequest(
                messages=[
                    ChatMessage(role="system", content="당신은 도움이 되는 AI 어시스턴트입니다."),
                    ChatMessage(role="user", content="파이썬으로 간단한 계산기를 만드는 방법을 알려주세요.")
                ],
                max_tokens=100
            )
            
            start_time = time.time()
            chat_result = self.client.chat(chat_request)
            end_time = time.time()
            
            if chat_result.get('choices'):
                response = chat_result['choices'][0]['message']['content']
                print(f"   질문: 파이썬으로 간단한 계산기를 만드는 방법을 알려주세요.")
                print(f"   답변: {response.strip()[:200]}...")
                print(f"   소요 시간: {end_time - start_time:.2f}초")
            
            print("\n✅ 기본 데모 완료!")
            
        except Exception as e:
            print(f"❌ 데모 실행 중 오류 발생: {e}")
    
    def run_streaming_demo(self):
        """스트리밍 데모"""
        print("🌊 스트리밍 데모")
        print("=" * 50)
        
        try:
            request = CompletionRequest(
                prompt="인공지능의 미래에 대해 설명해주세요.",
                max_tokens=200,
                temperature=0.8,
                stream=True
            )
            
            print(f"프롬프트: {request.prompt}")
            print("스트리밍 응답:")
            print("-" * 30)
            
            generated_text = ""
            chunk_count = 0
            start_time = time.time()
            
            for chunk in self.client.complete_stream(request):
                if chunk.get('choices'):
                    chunk_text = chunk['choices'][0].get('text', '')
                    generated_text += chunk_text
                    print(chunk_text, end='', flush=True)
                    chunk_count += 1
            
            end_time = time.time()
            
            print(f"\n{'-' * 30}")
            print(f"총 청크 수: {chunk_count}")
            print(f"생성된 텍스트 길이: {len(generated_text)}자")
            print(f"총 소요 시간: {end_time - start_time:.2f}초")
            print("\n✅ 스트리밍 데모 완료!")
            
        except Exception as e:
            print(f"❌ 스트리밍 데모 실행 중 오류 발생: {e}")
    
    async def run_async_demo(self):
        """비동기 데모"""
        print("⚡ 비동기 처리 데모")
        print("=" * 50)
        
        try:
            # 여러 요청을 동시에 처리
            prompts = [
                "파이썬의 장점은 무엇인가요?",
                "기계학습이란 무엇인가요?",
                "웹 개발의 기초는 무엇인가요?",
                "데이터베이스의 역할은 무엇인가요?"
            ]
            
            print(f"동시에 {len(prompts)}개 요청 처리 중...")
            
            # 비동기 완성 요청들 생성
            tasks = []
            for prompt in prompts:
                request = CompletionRequest(
                    prompt=prompt,
                    max_tokens=80,
                    temperature=0.7
                )
                task = self.client.async_complete(request)
                tasks.append((prompt, task))
            
            start_time = time.time()
            
            # 모든 요청을 동시에 실행
            results = await asyncio.gather(*[task for _, task in tasks], return_exceptions=True)
            
            end_time = time.time()
            
            print(f"\n📊 결과 (총 소요 시간: {end_time - start_time:.2f}초):")
            print("-" * 60)
            
            for i, ((prompt, _), result) in enumerate(zip(tasks, results)):
                print(f"\n{i+1}. 질문: {prompt}")
                
                if isinstance(result, Exception):
                    print(f"   ❌ 오류: {result}")
                elif result.get('choices'):
                    response = result['choices'][0]['text'].strip()
                    print(f"   ✅ 답변: {response[:100]}...")
                else:
                    print(f"   ⚠️ 응답 없음")
            
            print("\n✅ 비동기 데모 완료!")
            
        except Exception as e:
            print(f"❌ 비동기 데모 실행 중 오류 발생: {e}")
    
    def run_batch_demo(self, input_file: Optional[str] = None):
        """배치 처리 데모"""
        print("📦 배치 처리 데모")
        print("=" * 50)
        
        try:
            # 입력 프롬프트 준비
            if input_file and Path(input_file).exists():
                print(f"파일에서 프롬프트 로드: {input_file}")
                with open(input_file, 'r', encoding='utf-8') as f:
                    prompts = [line.strip() for line in f if line.strip()]
            else:
                print("기본 프롬프트 사용")
                prompts = [
                    "좋은 코드를 작성하는 방법은?",
                    "효율적인 학습 방법은?",
                    "건강한 생활습관은?",
                    "시간 관리의 핵심은?",
                    "창의성을 기르는 방법은?"
                ]
            
            print(f"처리할 프롬프트 수: {len(prompts)}")
            
            results = []
            total_tokens = 0
            total_time = 0
            
            for i, prompt in enumerate(prompts, 1):
                print(f"\n[{i}/{len(prompts)}] 처리 중: {prompt[:30]}...")
                
                request = CompletionRequest(
                    prompt=prompt,
                    max_tokens=100,
                    temperature=0.7
                )
                
                start_time = time.time()
                
                try:
                    result = self.client.complete(request)
                    end_time = time.time()
                    
                    if result.get('choices'):
                        generated_text = result['choices'][0]['text']
                        tokens_used = result.get('usage', {}).get('total_tokens', 0)
                        
                        results.append({
                            'prompt': prompt,
                            'response': generated_text.strip(),
                            'tokens': tokens_used,
                            'time': end_time - start_time
                        })
                        
                        total_tokens += tokens_used
                        total_time += end_time - start_time
                        
                        print(f"   ✅ 완료 ({end_time - start_time:.2f}초, {tokens_used}토큰)")
                    else:
                        print(f"   ⚠️ 응답 없음")
                        
                except Exception as e:
                    print(f"   ❌ 오류: {e}")
                
                # 요청 간 간격 (API 제한 고려)
                time.sleep(0.1)
            
            # 결과 요약
            print(f"\n📊 배치 처리 결과:")
            print(f"   • 성공한 요청: {len(results)}/{len(prompts)}")
            print(f"   • 총 토큰 사용량: {total_tokens}")
            print(f"   • 총 소요 시간: {total_time:.2f}초")
            print(f"   • 평균 응답 시간: {total_time/len(results):.2f}초" if results else "   • 평균 응답 시간: N/A")
            
            # 결과를 파일로 저장
            output_file = f"batch_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(results, f, indent=2, ensure_ascii=False)
            
            print(f"   • 결과 저장: {output_file}")
            print("\n✅ 배치 처리 데모 완료!")
            
        except Exception as e:
            print(f"❌ 배치 처리 데모 실행 중 오류 발생: {e}")
    
    def run_performance_test(self):
        """성능 테스트 데모"""
        print("🏃 성능 테스트 데모")
        print("=" * 50)
        
        try:
            test_configs = [
                {"max_tokens": 50, "temperature": 0.1, "name": "짧은 응답, 낮은 온도"},
                {"max_tokens": 100, "temperature": 0.7, "name": "중간 응답, 보통 온도"},
                {"max_tokens": 200, "temperature": 0.9, "name": "긴 응답, 높은 온도"},
            ]
            
            test_prompt = "인공지능과 기계학습의 차이점을 설명해주세요."
            
            for config in test_configs:
                print(f"\n🧪 테스트: {config['name']}")
                print(f"   설정: max_tokens={config['max_tokens']}, temperature={config['temperature']}")
                
                # 여러 번 실행하여 평균 성능 측정
                times = []
                token_counts = []
                
                for i in range(3):
                    request = CompletionRequest(
                        prompt=test_prompt,
                        max_tokens=config['max_tokens'],
                        temperature=config['temperature']
                    )
                    
                    start_time = time.time()
                    result = self.client.complete(request)
                    end_time = time.time()
                    
                    response_time = end_time - start_time
                    times.append(response_time)
                    
                    if result.get('usage'):
                        token_counts.append(result['usage'].get('total_tokens', 0))
                    
                    print(f"   실행 {i+1}: {response_time:.2f}초")
                
                avg_time = sum(times) / len(times)
                avg_tokens = sum(token_counts) / len(token_counts) if token_counts else 0
                tokens_per_second = avg_tokens / avg_time if avg_time > 0 else 0
                
                print(f"   📊 평균 성능:")
                print(f"      • 응답 시간: {avg_time:.2f}초")
                print(f"      • 토큰 수: {avg_tokens:.1f}개")
                print(f"      • 토큰/초: {tokens_per_second:.1f}")
            
            print("\n✅ 성능 테스트 완료!")
            
        except Exception as e:
            print(f"❌ 성능 테스트 실행 중 오류 발생: {e}")
    
    def run_error_handling_demo(self):
        """오류 처리 데모"""
        print("🛠️ 오류 처리 데모")
        print("=" * 50)
        
        test_cases = [
            {
                "name": "매우 긴 프롬프트",
                "request": CompletionRequest(
                    prompt="A" * 10000,  # 매우 긴 프롬프트
                    max_tokens=10
                )
            },
            {
                "name": "잘못된 모델명",
                "request": CompletionRequest(
                    prompt="Hello",
                    model="non-existent-model",
                    max_tokens=10
                )
            },
            {
                "name": "0개 토큰 요청",
                "request": CompletionRequest(
                    prompt="Hello",
                    max_tokens=0
                )
            },
            {
                "name": "잘못된 온도 값",
                "request": CompletionRequest(
                    prompt="Hello",
                    temperature=5.0,  # 보통 0-2 범위
                    max_tokens=10
                )
            }
        ]
        
        for test_case in test_cases:
            print(f"\n🧪 테스트: {test_case['name']}")
            
            try:
                result = self.client.complete(test_case['request'])
                print(f"   ✅ 성공 (예상치 못한 결과)")
                
            except requests.exceptions.HTTPError as e:
                print(f"   ❌ HTTP 오류: {e.response.status_code} - {e.response.reason}")
                try:
                    error_detail = e.response.json()
                    print(f"      세부사항: {error_detail}")
                except:
                    pass
                    
            except requests.exceptions.ConnectionError:
                print(f"   ❌ 연결 오류: 서버에 연결할 수 없습니다.")
                
            except requests.exceptions.Timeout:
                print(f"   ❌ 시간 초과: 요청이 너무 오래 걸립니다.")
                
            except Exception as e:
                print(f"   ❌ 기타 오류: {type(e).__name__}: {e}")
        
        print("\n✅ 오류 처리 데모 완료!")

def create_sample_prompts_file():
    """샘플 프롬프트 파일 생성"""
    sample_prompts = [
        "효과적인 프레젠테이션을 만드는 방법은?",
        "팀워크를 향상시키는 방법은?",
        "스트레스를 관리하는 방법은?",
        "새로운 기술을 빠르게 학습하는 방법은?",
        "의사결정을 개선하는 방법은?",
        "창의적 사고를 기르는 방법은?",
        "목표 설정의 중요성은?",
        "효율적인 독서 방법은?",
        "건강한 수면 습관은?",
        "성공적인 네트워킹 방법은?"
    ]
    
    filename = "sample_prompts.txt"
    with open(filename, 'w', encoding='utf-8') as f:
        for prompt in sample_prompts:
            f.write(f"{prompt}\n")
    
    print(f"✅ 샘플 프롬프트 파일 생성: {filename}")
    return filename

async def main():
    """메인 함수"""
    parser = argparse.ArgumentParser(description="vLLM API 클라이언트 사용 예제")
    
    parser.add_argument(
        "--api-base",
        default="http://localhost:8000",
        help="vLLM API 서버 주소 (기본값: http://localhost:8000)"
    )
    
    parser.add_argument(
        "--api-key",
        help="API 키 (필요한 경우)"
    )
    
    parser.add_argument(
        "--demo",
        choices=["basic", "streaming", "async", "batch", "performance", "error", "all"],
        default="basic",
        help="실행할 데모 타입 (기본값: basic)"
    )
    
    parser.add_argument(
        "--input-file",
        help="배치 처리용 입력 파일 (한 줄에 하나씩 프롬프트)"
    )
    
    parser.add_argument(
        "--create-sample",
        action="store_true",
        help="샘플 프롬프트 파일 생성"
    )
    
    args = parser.parse_args()
    
    # 샘플 파일 생성
    if args.create_sample:
        create_sample_prompts_file()
        return
    
    print("🚀 vLLM API 클라이언트 예제")
    print(f"📡 API 서버: {args.api_base}")
    print(f"🎭 데모 타입: {args.demo}")
    print("=" * 60)
    
    # 데모 실행기 생성
    runner = DemoRunner(args.api_base, args.api_key)
    
    try:
        if args.demo == "basic" or args.demo == "all":
            runner.run_basic_demo()
            
        if args.demo == "streaming" or args.demo == "all":
            if args.demo == "all":
                print("\n" + "=" * 60)
            runner.run_streaming_demo()
            
        if args.demo == "async" or args.demo == "all":
            if args.demo == "all":
                print("\n" + "=" * 60)
            await runner.run_async_demo()
            
        if args.demo == "batch" or args.demo == "all":
            if args.demo == "all":
                print("\n" + "=" * 60)
            runner.run_batch_demo(args.input_file)
            
        if args.demo == "performance" or args.demo == "all":
            if args.demo == "all":
                print("\n" + "=" * 60)
            runner.run_performance_test()
            
        if args.demo == "error" or args.demo == "all":
            if args.demo == "all":
                print("\n" + "=" * 60)
            runner.run_error_handling_demo()
        
        print(f"\n🎉 모든 데모가 완료되었습니다!")
        
    except KeyboardInterrupt:
        print(f"\n⚠️ 사용자에 의해 중단되었습니다.")
        sys.exit(130)
        
    except Exception as e:
        print(f"\n❌ 예기치 않은 오류 발생: {e}")
        sys.exit(1)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except Exception as e:
        print(f"실행 오류: {e}")
        sys.exit(1)