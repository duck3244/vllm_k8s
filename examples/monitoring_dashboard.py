#!/usr/bin/env python3
"""
examples/monitoring_dashboard.py
vLLM API 서버 모니터링 대시보드 예제

이 스크립트는 Streamlit을 사용하여 vLLM API 서버의 상태를 
실시간으로 모니터링하는 웹 대시보드를 제공합니다.

실행 방법:
    streamlit run examples/monitoring_dashboard.py

필요한 패키지:
    pip install streamlit plotly pandas requests
"""

import streamlit as st
import requests
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from datetime import datetime, timedelta
import time
import json
import asyncio
import aiohttp
from typing import Dict, List, Optional, Any
import logging

# 로깅 설정
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 페이지 설정
st.set_page_config(
    page_title="vLLM API 서버 모니터링",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

# 전역 설정
DEFAULT_API_BASE = "http://localhost:8000"
REFRESH_INTERVAL = 5  # 초
MAX_HISTORY_POINTS = 100

class VLLMMonitor:
    """vLLM API 서버 모니터링 클래스"""
    
    def __init__(self, api_base: str):
        self.api_base = api_base.rstrip('/')
        self.session = requests.Session()
        self.session.timeout = 10
        
    def check_health(self) -> Dict[str, Any]:
        """서버 헬스 체크"""
        try:
            response = self.session.get(f"{self.api_base}/health")
            return {
                "status": "healthy" if response.status_code == 200 else "unhealthy",
                "response_time": response.elapsed.total_seconds(),
                "timestamp": datetime.now()
            }
        except Exception as e:
            return {
                "status": "error",
                "error": str(e),
                "response_time": None,
                "timestamp": datetime.now()
            }
    
    def get_model_info(self) -> Optional[Dict[str, Any]]:
        """모델 정보 조회"""
        try:
            response = self.session.get(f"{self.api_base}/v1/models")
            if response.status_code == 200:
                return response.json()
            return None
        except Exception as e:
            logger.error(f"모델 정보 조회 실패: {e}")
            return None
    
    def get_server_stats(self) -> Optional[Dict[str, Any]]:
        """서버 통계 정보 조회"""
        try:
            # vLLM의 메트릭 엔드포인트 (실제 구현에 따라 다를 수 있음)
            response = self.session.get(f"{self.api_base}/metrics")
            if response.status_code == 200:
                return {"raw_metrics": response.text}
            return None
        except Exception as e:
            logger.error(f"서버 통계 조회 실패: {e}")
            return None
    
    async def test_completion(self, prompt: str = "Hello, how are you?") -> Dict[str, Any]:
        """완성 API 테스트"""
        try:
            async with aiohttp.ClientSession() as session:
                payload = {
                    "model": "default",
                    "prompt": prompt,
                    "max_tokens": 100,
                    "temperature": 0.7
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
                            "status": "success",
                            "response_time": end_time - start_time,
                            "tokens_generated": len(result.get("choices", [{}])[0].get("text", "").split()),
                            "result": result
                        }
                    else:
                        return {
                            "status": "error",
                            "response_time": end_time - start_time,
                            "error": f"HTTP {response.status}"
                        }
        except Exception as e:
            return {
                "status": "error",
                "error": str(e),
                "response_time": None
            }

def init_session_state():
    """세션 상태 초기화"""
    if 'health_history' not in st.session_state:
        st.session_state.health_history = []
    if 'response_time_history' not in st.session_state:
        st.session_state.response_time_history = []
    if 'completion_history' not in st.session_state:
        st.session_state.completion_history = []
    if 'last_update' not in st.session_state:
        st.session_state.last_update = None

def update_history(history_list: List, new_data: Any, max_points: int = MAX_HISTORY_POINTS):
    """히스토리 데이터 업데이트"""
    history_list.append(new_data)
    if len(history_list) > max_points:
        history_list.pop(0)

def create_health_chart(health_history: List[Dict]) -> go.Figure:
    """헬스 상태 차트 생성"""
    if not health_history:
        return go.Figure()
    
    timestamps = [entry["timestamp"] for entry in health_history]
    statuses = [1 if entry["status"] == "healthy" else 0 for entry in health_history]
    
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=timestamps,
        y=statuses,
        mode='lines+markers',
        name='서버 상태',
        line=dict(color='green', width=2),
        marker=dict(size=6)
    ))
    
    fig.update_layout(
        title="서버 헬스 상태",
        xaxis_title="시간",
        yaxis_title="상태",
        yaxis=dict(tickmode='array', tickvals=[0, 1], ticktext=['Unhealthy', 'Healthy']),
        height=300
    )
    
    return fig

def create_response_time_chart(response_time_history: List[Dict]) -> go.Figure:
    """응답 시간 차트 생성"""
    if not response_time_history:
        return go.Figure()
    
    timestamps = [entry["timestamp"] for entry in response_time_history if entry["response_time"]]
    response_times = [entry["response_time"] * 1000 for entry in response_time_history if entry["response_time"]]
    
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=timestamps,
        y=response_times,
        mode='lines+markers',
        name='응답 시간',
        line=dict(color='blue', width=2),
        marker=dict(size=4)
    ))
    
    fig.update_layout(
        title="응답 시간 추이",
        xaxis_title="시간",
        yaxis_title="응답 시간 (ms)",
        height=300
    )
    
    return fig

def create_completion_performance_chart(completion_history: List[Dict]) -> go.Figure:
    """완성 API 성능 차트 생성"""
    if not completion_history:
        return go.Figure()
    
    successful_completions = [entry for entry in completion_history if entry["status"] == "success"]
    
    if not successful_completions:
        return go.Figure()
    
    timestamps = [entry["timestamp"] for entry in successful_completions]
    response_times = [entry["response_time"] for entry in successful_completions]
    tokens_per_second = [
        entry.get("tokens_generated", 0) / entry["response_time"] 
        if entry["response_time"] > 0 else 0
        for entry in successful_completions
    ]
    
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=timestamps,
        y=tokens_per_second,
        mode='lines+markers',
        name='토큰/초',
        line=dict(color='orange', width=2),
        marker=dict(size=4)
    ))
    
    fig.update_layout(
        title="토큰 생성 속도",
        xaxis_title="시간",
        yaxis_title="토큰/초",
        height=300
    )
    
    return fig

def main():
    """메인 대시보드"""
    st.title("📊 vLLM API 서버 모니터링 대시보드")
    
    # 사이드바 설정
    st.sidebar.header("⚙️ 설정")
    
    api_base = st.sidebar.text_input(
        "API 서버 주소",
        value=DEFAULT_API_BASE,
        help="vLLM API 서버의 기본 URL"
    )
    
    auto_refresh = st.sidebar.checkbox(
        "자동 새로고침",
        value=True,
        help=f"{REFRESH_INTERVAL}초마다 자동 새로고침"
    )
    
    test_prompt = st.sidebar.text_area(
        "테스트 프롬프트",
        value="안녕하세요, 오늘 날씨는 어떤가요?",
        help="완성 API 테스트용 프롬프트"
    )
    
    # 수동 새로고침 버튼
    if st.sidebar.button("🔄 수동 새로고침"):
        st.rerun()
    
    # 히스토리 초기화 버튼
    if st.sidebar.button("🗑️ 히스토리 초기화"):
        st.session_state.health_history = []
        st.session_state.response_time_history = []
        st.session_state.completion_history = []
        st.success("히스토리가 초기화되었습니다.")
        st.rerun()
    
    # 세션 상태 초기화
    init_session_state()
    
    # 모니터 인스턴스 생성
    monitor = VLLMMonitor(api_base)
    
    # 데이터 수집
    current_time = datetime.now()
    
    # 헬스 체크
    health_data = monitor.check_health()
    update_history(st.session_state.health_history, health_data)
    update_history(st.session_state.response_time_history, health_data)
    
    # 상태 표시 섹션
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        status_color = "🟢" if health_data["status"] == "healthy" else "🔴"
        st.metric(
            label=f"{status_color} 서버 상태",
            value=health_data["status"].upper(),
            delta=None
        )
    
    with col2:
        if health_data["response_time"]:
            st.metric(
                label="⚡ 응답 시간",
                value=f"{health_data['response_time']*1000:.1f} ms",
                delta=None
            )
        else:
            st.metric(
                label="⚡ 응답 시간",
                value="N/A",
                delta=None
            )
    
    with col3:
        # 최근 1분간 가동시간 계산
        recent_health = [
            entry for entry in st.session_state.health_history
            if entry["timestamp"] > current_time - timedelta(minutes=1)
        ]
        healthy_count = sum(1 for entry in recent_health if entry["status"] == "healthy")
        uptime = (healthy_count / len(recent_health) * 100) if recent_health else 0
        
        st.metric(
            label="📈 가동률 (1분)",
            value=f"{uptime:.1f}%",
            delta=None
        )
    
    with col4:
        st.metric(
            label="🕐 마지막 업데이트",
            value=current_time.strftime("%H:%M:%S"),
            delta=None
        )
    
    # 모델 정보 섹션
    st.header("🤖 모델 정보")
    model_info = monitor.get_model_info()
    
    if model_info and "data" in model_info:
        for model in model_info["data"]:
            with st.expander(f"모델: {model.get('id', 'Unknown')}"):
                st.json(model)
    else:
        st.warning("모델 정보를 가져올 수 없습니다.")
    
    # 차트 섹션
    st.header("📈 성능 차트")
    
    col1, col2 = st.columns(2)
    
    with col1:
        health_chart = create_health_chart(st.session_state.health_history)
        st.plotly_chart(health_chart, use_container_width=True)
        
        response_time_chart = create_response_time_chart(st.session_state.response_time_history)
        st.plotly_chart(response_time_chart, use_container_width=True)
    
    with col2:
        # 완성 API 테스트
        st.subheader("🧪 완성 API 테스트")
        
        if st.button("테스트 실행"):
            with st.spinner("완성 API 테스트 중..."):
                # 비동기 함수를 동기적으로 실행
                import asyncio
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                
                try:
                    completion_result = loop.run_until_complete(
                        monitor.test_completion(test_prompt)
                    )
                    completion_result["timestamp"] = current_time
                    update_history(st.session_state.completion_history, completion_result)
                    
                    if completion_result["status"] == "success":
                        st.success(f"✅ 테스트 성공! ({completion_result['response_time']:.2f}초)")
                        if "result" in completion_result:
                            st.write("**응답:**")
                            response_text = completion_result["result"].get("choices", [{}])[0].get("text", "")
                            st.write(response_text[:200] + "..." if len(response_text) > 200 else response_text)
                    else:
                        st.error(f"❌ 테스트 실패: {completion_result.get('error', 'Unknown error')}")
                finally:
                    loop.close()
        
        # 완성 성능 차트
        completion_chart = create_completion_performance_chart(st.session_state.completion_history)
        st.plotly_chart(completion_chart, use_container_width=True)
    
    # 최근 로그 섹션
    st.header("📋 최근 활동 로그")
    
    # 최근 10개 이벤트 표시
    recent_events = []
    
    for entry in st.session_state.health_history[-10:]:
        recent_events.append({
            "시간": entry["timestamp"].strftime("%H:%M:%S"),
            "타입": "헬스체크",
            "상태": entry["status"],
            "응답시간": f"{entry['response_time']*1000:.1f}ms" if entry["response_time"] else "N/A"
        })
    
    for entry in st.session_state.completion_history[-5:]:
        recent_events.append({
            "시간": entry["timestamp"].strftime("%H:%M:%S"),
            "타입": "완성 테스트",
            "상태": entry["status"],
            "응답시간": f"{entry['response_time']:.2f}s" if entry["response_time"] else "N/A"
        })
    
    # 시간순 정렬
    recent_events.sort(key=lambda x: x["시간"], reverse=True)
    
    if recent_events:
        df = pd.DataFrame(recent_events[:10])
        st.dataframe(df, use_container_width=True)
    else:
        st.info("아직 로그 데이터가 없습니다.")
    
    # 서버 통계 (선택사항)
    with st.expander("🔧 서버 통계 (고급)"):
        server_stats = monitor.get_server_stats()
        if server_stats:
            st.text(server_stats.get("raw_metrics", "통계 정보가 없습니다."))
        else:
            st.info("서버 통계를 가져올 수 없습니다.")
    
    # 자동 새로고침
    if auto_refresh:
        time.sleep(REFRESH_INTERVAL)
        st.rerun()
    
    # 푸터
    st.markdown("---")
    st.markdown(
        "💡 **사용 팁:** 사이드바에서 설정을 조정하고, 자동 새로고침을 활성화하여 실시간 모니터링을 경험하세요."
    )

if __name__ == "__main__":
    main()
