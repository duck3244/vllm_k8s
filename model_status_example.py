#!/usr/bin/env python3
"""
모델 상태 체크 사용 예제
"""

import requests
import time
import json
from datetime import datetime

# API 기본 URL
BASE_URL = "http://localhost:8000/api/v1"

def check_model_status():
    """모델 현재 상태 확인"""
    try:
        response = requests.get(f"{BASE_URL}/model/status")
        response.raise_for_status()
        
        data = response.json()
        print("🤖 모델 상태 정보")
        print("=" * 50)
        print(f"상태: {data['status']}")
        print(f"마지막 체크: {data['last_check']}")
        print(f"수행된 체크 수: {data['checks_performed']}")
        print(f"평균 응답시간: {data['response_time_avg']:.2f}초")
        print(f"95% 응답시간: {data['response_time_p95']:.2f}초")
        print(f"에러율: {data['error_rate']:.1%}")
        print(f"처리량: {data['throughput']:.1f} tokens/sec")
        
        if data['gpu_memory_usage']:
            print(f"GPU 메모리 사용률: {data['gpu_memory_usage']:.1f}%")
        if data['gpu_temperature']:
            print(f"GPU 온도: {data['gpu_temperature']:.1f}°C")
        
        print(f"활성 요청 수: {data['active_requests']}")
        
        # 알림 정보
        if data['alerts']:
            print("\n⚠️  활성 알림:")
            for alert in data['alerts']:
                print(f"  - {alert['severity'].upper()}: {alert['message']}")
        else:
            print("\n✅ 활성 알림 없음")
        
        return data
        
    except requests.exceptions.RequestException as e:
        print(f"❌ 모델 상태 조회 실패: {e}")
        return None

def run_health_check(include_inference=False, test_prompt=None):
    """수동 헬스체크 실행"""
    try:
        payload = {
            "include_inference_test": include_inference
        }
        if test_prompt:
            payload["test_prompt"] = test_prompt
        
        response = requests.post(
            f"{BASE_URL}/model/health-check",
            json=payload,
            headers={"Content-Type": "application/json"}
        )
        response.raise_for_status()
        
        data = response.json()
        print("\n🔍 헬스체크 결과")
        print("=" * 50)
        print(f"상태: {data['status']}")
        print(f"체크 시간: {datetime.fromtimestamp(data['timestamp']).strftime('%Y-%m-%d %H:%M:%S')}")
        
        metrics = data['metrics']
        print("\n📊 상세 메트릭:")
        print(f"  평균 응답시간: {metrics['response_time_avg']:.2f}초")
        print(f"  95% 응답시간: {metrics['response_time_p95']:.2f}초")
        print(f"  에러율: {metrics['error_rate']:.1%}")
        print(f"  메모리 사용률: {metrics['memory_usage']:.1f}%")
        if metrics.get('gpu_memory_usage'):
            print(f"  GPU 메모리 사용률: {metrics['gpu_memory_usage']:.1f}%")
        if metrics.get('gpu_temperature'):
            print(f"  GPU 온도: {metrics['gpu_temperature']:.1f}°C")
        print(f"  처리량: {metrics['throughput']:.1f} tokens/sec")
        print(f"  활성 요청: {metrics['active_requests']}")
        
        # 추론 테스트 결과
        if data.get('inference_test'):
            test = data['inference_test']
            print(f"\n🧪 추론 테스트:")
            if test['success']:
                print(f"  ✅ 성공")
                print(f"  응답시간: {test['response_time']:.2f}초")
                print(f"  생성 토큰 수: {test['tokens_generated']}")
            else:
                print(f"  ❌ 실패: {test['error']}")
        
        return data
        
    except requests.exceptions.RequestException as e:
        print(f"❌ 헬스체크 실행 실패: {e}")
        return None

def get_system_metrics():
    """시스템 메트릭 조회"""
    try:
        response = requests.get(f"{BASE_URL}/model/metrics/system")
        response.raise_for_status()
        
        data = response.json()
        print("\n💻 시스템 메트릭")
        print("=" * 50)
        print(f"CPU 사용률: {data['cpu_usage_percent']:.1f}%")
        print(f"메모리 사용률: {data['memory_usage_percent']:.1f}%")
        print(f"디스크 사용률: {data['disk_usage_percent']:.1f}%")
        print(f"로드 평균: {data['load_average']}")
        
        if data.get('gpu_utilization') is not None:
            print(f"GPU 사용률: {data['gpu_utilization']:.1f}%")
        if data.get('gpu_memory_total'):
            gpu_memory_gb = data['gpu_memory_total'] / (1024**3)
            gpu_used_gb = data['gpu_memory_used'] / (1024**3)
            print(f"GPU 메모리: {gpu_used_gb:.1f}GB / {gpu_memory_gb:.1f}GB ({data['gpu_memory_percent']:.1f}%)")
        if data.get('gpu_temperature'):
            print(f"GPU 온도: {data['gpu_temperature']:.1f}°C")
        
        return data
        
    except requests.exceptions.RequestException as e:
        print(f"❌ 시스템 메트릭 조회 실패: {e}")
        return None

def get_model_history(hours=24):
    """모델 과거 데이터 조회"""
    try:
        response = requests.get(f"{BASE_URL}/model/history?hours={hours}")
        response.raise_for_status()
        
        data = response.json()
        print(f"\n📈 모델 히스토리 ({hours}시간)")
        print("=" * 50)
        print(f"데이터 포인트: {data['data_points']}개")
        
        summary = data['summary']
        print(f"평균 응답시간: {summary['avg_response_time']:.2f}초")
        print(f"최대 응답시간: {summary['max_response_time']:.2f}초")
        print(f"평균 에러율: {summary['avg_error_rate']:.1%}")
        print(f"업타임: {summary['uptime_percentage']:.1f}%")
        
        print("\n상태 분포:")
        for status, count in summary['status_distribution'].items():
            percentage = (count / data['data_points']) * 100
            print(f"  {status}: {count}회 ({percentage:.1f}%)")
        
        return data
        
    except requests.exceptions.RequestException as e:
        print(f"❌ 모델 히스토리 조회 실패: {e}")
        return None

def get_alerts():
    """현재 알림 조회"""
    try:
        response = requests.get(f"{BASE_URL}/model/alerts")
        response.raise_for_status()
        
        data = response.json()
        print("\n🚨 모델 알림")
        print("=" * 50)
        print(f"총 알림 수: {data['total_alerts']}")
        print(f"크리티컬: {data['critical_count']}")
        print(f"경고: {data['warning_count']}")
        
        if data['critical_alerts']:
            print("\n🔴 크리티컬 알림:")
            for alert in data['critical_alerts']:
                print(f"  - {alert['message']}")
        
        if data['warning_alerts']:
            print("\n🟡 경고 알림:")
            for alert in data['warning_alerts']:
                print(f"  - {alert['message']}")
        
        if not data['alerts']:
            print("✅ 현재 활성 알림이 없습니다")
        
        return data
        
    except requests.exceptions.RequestException as e:
        print(f"❌ 알림 조회 실패: {e}")
        return None

def start_monitoring(interval=30):
    """모니터링 시작"""
    try:
        response = requests.post(
            f"{BASE_URL}/model/monitoring/start?interval={interval}",
            headers={"Authorization": "Bearer your-api-key"}  # API 키가 필요한 경우
        )
        response.raise_for_status()
        
        data = response.json()
        print(f"\n✅ 모니터링 시작됨")
        print(f"모니터링 간격: {data['monitoring_interval']}초")
        
        return data
        
    except requests.exceptions.RequestException as e:
        print(f"❌ 모니터링 시작 실패: {e}")
        return None

def stop_monitoring():
    """모니터링 중지"""
    try:
        response = requests.post(
            f"{BASE_URL}/model/monitoring/stop",
            headers={"Authorization": "Bearer your-api-key"}  # API 키가 필요한 경우
        )
        response.raise_for_status()
        
        data = response.json()
        print(f"\n🛑 모니터링 중지됨")
        
        return data
        
    except requests.exceptions.RequestException as e:
        print(f"❌ 모니터링 중지 실패: {e}")
        return None

def continuous_monitoring(interval=10, duration=300):
    """연속 모니터링 (지정된 시간 동안)"""
    print(f"🔄 {duration}초 동안 {interval}초마다 모니터링 시작...")
    
    start_time = time.time()
    iteration = 0
    
    while time.time() - start_time < duration:
        iteration += 1
        print(f"\n--- 모니터링 {iteration}회차 ({datetime.now().strftime('%H:%M:%S')}) ---")
        
        # 모델 상태 확인
        status = check_model_status()
        
        if status:
            # 상태에 따른 대응
            if status['status'] == 'unhealthy':
                print("🚨 모델 상태가 비정상입니다!")
                get_alerts()
            elif status['status'] == 'degraded':
                print("⚠️ 모델 성능이 저하되었습니다.")
            
            # 임계값 체크
            if status['response_time_p95'] > 5.0:
                print(f"⚠️ 응답시간이 높습니다: {status['response_time_p95']:.2f}초")
            
            if status['error_rate'] > 0.05:
                print(f"⚠️ 에러율이 높습니다: {status['error_rate']:.1%}")
            
            if status.get('gpu_memory_usage', 0) > 90:
                print(f"⚠️ GPU 메모리 사용률이 높습니다: {status['gpu_memory_usage']:.1f}%")
        
        # 다음 체크까지 대기
        time.sleep(interval)
    
    print(f"\n✅ 모니터링 완료 ({iteration}회 체크)")

def benchmark_model_performance(requests_count=10):
    """모델 성능 벤치마크"""
    print(f"\n⚡ 모델 성능 벤치마크 ({requests_count}회 요청)")
    print("=" * 50)
    
    test_prompts = [
        "Python이란 무엇인가요?",
        "머신러닝에 대해 설명해주세요.",
        "데이터베이스의 종류를 알려주세요.",
        "웹 개발의 기본 개념을 설명해주세요.",
        "클라우드 컴퓨팅이란 무엇인가요?"
    ]
    
    response_times = []
    success_count = 0
    
    for i in range(requests_count):
        prompt = test_prompts[i % len(test_prompts)]
        
        try:
            start_time = time.time()
            
            response = requests.post(
                f"{BASE_URL}/generate",
                json={
                    "prompt": prompt,
                    "max_tokens": 50,
                    "temperature": 0.7
                },
                headers={"Content-Type": "application/json"},
                timeout=30
            )
            
            end_time = time.time()
            response_time = end_time - start_time
            
            if response.status_code == 200:
                success_count += 1
                response_times.append(response_time)
                print(f"  요청 {i+1}: ✅ {response_time:.2f}초")
            else:
                print(f"  요청 {i+1}: ❌ HTTP {response.status_code}")
            
        except requests.exceptions.Timeout:
            print(f"  요청 {i+1}: ⏰ 타임아웃")
        except requests.exceptions.RequestException as e:
            print(f"  요청 {i+1}: ❌ 오류: {e}")
        
        # 요청 간 간격
        time.sleep(0.5)
    
    # 결과 분석
    if response_times:
        avg_time = sum(response_times) / len(response_times)
        min_time = min(response_times)
        max_time = max(response_times)
        success_rate = (success_count / requests_count) * 100
        
        print(f"\n📊 벤치마크 결과:")
        print(f"  성공률: {success_rate:.1f}% ({success_count}/{requests_count})")
        print(f"  평균 응답시간: {avg_time:.2f}초")
        print(f"  최소 응답시간: {min_time:.2f}초")
        print(f"  최대 응답시간: {max_time:.2f}초")
        print(f"  초당 요청 수: {1/avg_time:.1f} RPS")
    else:
        print("❌ 성공한 요청이 없습니다")

def main():
    """메인 함수"""
    print("🤖 vLLM 모델 상태 체크 도구")
    print("=" * 60)
    
    while True:
        print("\n옵션을 선택하세요:")
        print("1. 모델 상태 확인")
        print("2. 헬스체크 실행")
        print("3. 추론 테스트 포함 헬스체크")
        print("4. 시스템 메트릭 조회")
        print("5. 모델 히스토리 조회")
        print("6. 알림 조회")
        print("7. 모니터링 시작")
        print("8. 모니터링 중지")
        print("9. 연속 모니터링 (5분)")
        print("10. 성능 벤치마크")
        print("0. 종료")
        
        try:
            choice = input("\n선택 (0-10): ").strip()
            
            if choice == "0":
                print("👋 종료합니다.")
                break
            elif choice == "1":
                check_model_status()
            elif choice == "2":
                run_health_check()
            elif choice == "3":
                test_prompt = input("테스트 프롬프트 (엔터: 기본값): ").strip()
                run_health_check(include_inference=True, test_prompt=test_prompt or None)
            elif choice == "4":
                get_system_metrics()
            elif choice == "5":
                hours = input("조회할 시간 (기본: 24): ").strip()
                hours = int(hours) if hours.isdigit() else 24
                get_model_history(hours)
            elif choice == "6":
                get_alerts()
            elif choice == "7":
                interval = input("모니터링 간격 초 (기본: 30): ").strip()
                interval = int(interval) if interval.isdigit() else 30
                start_monitoring(interval)
            elif choice == "8":
                stop_monitoring()
            elif choice == "9":
                continuous_monitoring(interval=10, duration=300)
            elif choice == "10":
                count = input("요청 수 (기본: 10): ").strip()
                count = int(count) if count.isdigit() else 10
                benchmark_model_performance(count)
            else:
                print("❌ 잘못된 선택입니다.")
                
        except KeyboardInterrupt:
            print("\n\n👋 사용자가 중단했습니다.")
            break
        except ValueError:
            print("❌ 올바른 숫자를 입력해주세요.")
        except Exception as e:
            print(f"❌ 오류 발생: {e}")

if __name__ == "__main__":
    main()