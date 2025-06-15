#!/bin/bash
# scripts/test_api.sh
# vLLM API 서버 테스트 스크립트

set -e

# 색깔 정의
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
PURPLE='\033[0;35m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# 로그 함수
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

log_step() {
    echo -e "${PURPLE}[STEP]${NC} $1"
}

# 기본 설정
API_HOST=${API_HOST:-"localhost"}
API_PORT=${API_PORT:-8000}
API_BASE_URL="http://${API_HOST}:${API_PORT}"
TIMEOUT=${TIMEOUT:-30}
VERBOSE=${VERBOSE:-false}
OUTPUT_DIR="tests/api_results"

# 테스트 결과 변수
TOTAL_TESTS=0
PASSED_TESTS=0
FAILED_TESTS=0

# 도움말 함수
show_help() {
    cat << EOF
사용법: $0 [옵션]

옵션:
  --host HOST          API 서버 호스트 (기본값: localhost)
  --port PORT          API 서버 포트 (기본값: 8000)
  --timeout SECONDS    요청 타임아웃 (기본값: 30)
  --verbose            상세 출력 모드
  --save-results       테스트 결과를 파일로 저장
  --load-test          부하 테스트 실행
  --auth TOKEN         인증 토큰 (필요한 경우)
  --help               이 도움말 표시

환경 변수:
  API_HOST             API 서버 호스트
  API_PORT             API 서버 포트
  API_TOKEN            인증 토큰

예시:
  $0 --host 192.168.1.100 --port 8080 --verbose
  $0 --load-test --save-results
  API_HOST=api.example.com $0
EOF
}

# 명령행 인수 파싱
SAVE_RESULTS=false
LOAD_TEST=false
AUTH_TOKEN=""

while [[ $# -gt 0 ]]; do
    case $1 in
        --host)
            API_HOST="$2"
            API_BASE_URL="http://${API_HOST}:${API_PORT}"
            shift 2
            ;;
        --port)
            API_PORT="$2"
            API_BASE_URL="http://${API_HOST}:${API_PORT}"
            shift 2
            ;;
        --timeout)
            TIMEOUT="$2"
            shift 2
            ;;
        --verbose)
            VERBOSE=true
            shift
            ;;
        --save-results)
            SAVE_RESULTS=true
            shift
            ;;
        --load-test)
            LOAD_TEST=true
            shift
            ;;
        --auth)
            AUTH_TOKEN="$2"
            shift 2
            ;;
        --help)
            show_help
            exit 0
            ;;
        *)
            log_error "알 수 없는 옵션: $1"
            show_help
            exit 1
            ;;
    esac
done

# 환경 변수에서 토큰 읽기
if [ -z "$AUTH_TOKEN" ] && [ -n "$API_TOKEN" ]; then
    AUTH_TOKEN="$API_TOKEN"
fi

log_info "🧪 vLLM API 테스트 시작"
log_info "API 주소: $API_BASE_URL"
log_info "타임아웃: ${TIMEOUT}초"

# 결과 디렉토리 생성
if [ "$SAVE_RESULTS" = true ]; then
    mkdir -p "$OUTPUT_DIR"
    RESULT_FILE="$OUTPUT_DIR/api_test_$(date +%Y%m%d_%H%M%S).json"
    log_info "결과 저장: $RESULT_FILE"
fi

# 테스트 헬퍼 함수
run_test() {
    local test_name="$1"
    local method="$2"
    local endpoint="$3"
    local data="$4"
    local expected_status="$5"
    local description="$6"
    
    ((TOTAL_TESTS++))
    
    log_step "테스트 ${TOTAL_TESTS}: $test_name"
    if [ -n "$description" ]; then
        log_info "설명: $description"
    fi
    
    # curl 명령어 구성
    local curl_cmd="curl -s -w '%{http_code}:%{time_total}:%{size_download}' --max-time $TIMEOUT"
    
    if [ -n "$AUTH_TOKEN" ]; then
        curl_cmd="$curl_cmd -H 'Authorization: Bearer $AUTH_TOKEN'"
    fi
    
    curl_cmd="$curl_cmd -H 'Content-Type: application/json'"
    
    if [ -n "$data" ]; then
        curl_cmd="$curl_cmd -d '$data'"
    fi
    
    curl_cmd="$curl_cmd -X $method '$API_BASE_URL$endpoint'"
    
    # 요청 실행
    local start_time=$(date +%s.%N)
    local response=$(eval $curl_cmd 2>/dev/null)
    local end_time=$(date +%s.%N)
    
    # 응답 파싱
    local status_info="${response##*:}"
    local response_body="${response%:*:*:*}"
    local http_code="${status_info%%:*}"
    local time_total="${status_info#*:}"
    time_total="${time_total%:*}"
    local size_download="${status_info##*:}"
    
    # 실제 응답 시간 계산
    local actual_time=$(echo "$end_time - $start_time" | bc -l 2>/dev/null || echo "0")
    
    if [ "$VERBOSE" = true ]; then
        echo "  요청: $method $endpoint"
        if [ -n "$data" ]; then
            echo "  데이터: $data"
        fi
        echo "  응답 코드: $http_code"
        echo "  응답 시간: ${actual_time}초"
        echo "  응답 크기: ${size_download}바이트"
        if [ ${#response_body} -lt 500 ]; then
            echo "  응답 내용: $response_body"
        else
            echo "  응답 내용: ${response_body:0:200}... (truncated)"
        fi
    fi
    
    # 결과 검증
    if [ "$http_code" = "$expected_status" ]; then
        log_success "✅ 테스트 통과: $test_name"
        ((PASSED_TESTS++))
        local test_result="PASS"
    else
        log_error "❌ 테스트 실패: $test_name (예상: $expected_status, 실제: $http_code)"
        ((FAILED_TESTS++))
        local test_result="FAIL"
    fi
    
    # 결과 저장
    if [ "$SAVE_RESULTS" = true ]; then
        cat >> "$RESULT_FILE" << EOF
{
  "test_number": $TOTAL_TESTS,
  "name": "$test_name",
  "method": "$method",
  "endpoint": "$endpoint",
  "expected_status": $expected_status,
  "actual_status": $http_code,
  "response_time": $actual_time,
  "response_size": $size_download,
  "result": "$test_result",
  "timestamp": "$(date -Iseconds)"
},
EOF
    fi
    
    echo ""
}

# API 서버 연결 확인
check_api_connectivity() {
    log_step "🔗 API 서버 연결 확인"
    
    if ! curl -s --max-time 5 "$API_BASE_URL" > /dev/null; then
        log_error "API 서버에 연결할 수 없습니다: $API_BASE_URL"
        log_info "서버가 실행 중인지 확인하세요."
        exit 1
    fi
    
    log_success "API 서버 연결 확인 완료"
}

# 기본 API 테스트
run_basic_tests() {
    log_step "🧪 기본 API 테스트"
    
    # 루트 엔드포인트
    run_test "루트_엔드포인트" "GET" "/" "" "200" "API 루트 페이지 확인"
    
    # 헬스 체크
    run_test "헬스_체크" "GET" "/health" "" "200" "서버 상태 확인"
    
    # API 정보
    run_test "API_정보" "GET" "/info" "" "200" "API 정보 조회"
    
    # 메트릭스 (있는 경우)
    run_test "메트릭스" "GET" "/metrics" "" "200" "메트릭스 조회"
    
    # OpenAPI 스키마
    run_test "OpenAPI_스키마" "GET" "/openapi.json" "" "200" "OpenAPI 스키마 조회"
    
    # API 문서
    run_test "API_문서" "GET" "/docs" "" "200" "API 문서 페이지"
}

# 모델 관련 테스트
run_model_tests() {
    log_step "🤖 모델 관련 테스트"
    
    # 모델 목록
    run_test "모델_목록" "GET" "/v1/models" "" "200" "사용 가능한 모델 목록 조회"
    
    # 모델 정보
    run_test "모델_정보" "GET" "/v1/models/default" "" "200" "기본 모델 정보 조회"
}

# 생성 API 테스트
run_generation_tests() {
    log_step "📝 생성 API 테스트"
    
    # 간단한 텍스트 생성
    local simple_prompt='{"model": "default", "prompt": "Hello, how are you?", "max_tokens": 50}'
    run_test "텍스트_생성_간단" "POST" "/v1/completions" "$simple_prompt" "200" "간단한 텍스트 생성"
    
    # 채팅 완성 (ChatML 형식)
    local chat_prompt='{"model": "default", "messages": [{"role": "user", "content": "What is the capital of France?"}], "max_tokens": 50}'
    run_test "채팅_완성" "POST" "/v1/chat/completions" "$chat_prompt" "200" "채팅 형식 텍스트 생성"
    
    # 스트리밍 테스트
    local streaming_prompt='{"model": "default", "prompt": "Tell me a story", "max_tokens": 100, "stream": true}'
    run_test "스트리밍_생성" "POST" "/v1/completions" "$streaming_prompt" "200" "스트리밍 텍스트 생성"
    
    # 파라미터 테스트
    local param_prompt='{"model": "default", "prompt": "Creative writing:", "max_tokens": 50, "temperature": 0.8, "top_p": 0.9}'
    run_test "파라미터_생성" "POST" "/v1/completions" "$param_prompt" "200" "파라미터가 포함된 텍스트 생성"
}

# 에러 케이스 테스트
run_error_tests() {
    log_step "🚫 에러 케이스 테스트"
    
    # 존재하지 않는 엔드포인트
    run_test "존재하지_않는_엔드포인트" "GET" "/nonexistent" "" "404" "404 에러 처리 확인"
    
    # 잘못된 HTTP 메서드
    run_test "잘못된_메서드" "DELETE" "/v1/models" "" "405" "메서드 에러 처리 확인"
    
    # 잘못된 JSON
    run_test "잘못된_JSON" "POST" "/v1/completions" "invalid json" "422" "JSON 파싱 에러 처리"
    
    # 필수 필드 누락
    local missing_field='{"max_tokens": 50}'
    run_test "필수_필드_누락" "POST" "/v1/completions" "$missing_field" "422" "필수 필드 누락 에러 처리"
    
    # 잘못된 모델명
    local invalid_model='{"model": "nonexistent-model", "prompt": "test", "max_tokens": 50}'
    run_test "잘못된_모델명" "POST" "/v1/completions" "$invalid_model" "400" "잘못된 모델명 에러 처리"
}

# 성능 테스트
run_performance_tests() {
    log_step "⚡ 성능 테스트"
    
    local test_prompt='{"model": "default", "prompt": "Performance test", "max_tokens": 10}'
    
    log_info "연속 요청 성능 테스트 (10회)"
    local total_time=0
    local success_count=0
    
    for i in {1..10}; do
        local start_time=$(date +%s.%N)
        local response=$(curl -s -w '%{http_code}' --max-time $TIMEOUT \
            -H 'Content-Type: application/json' \
            -d "$test_prompt" \
            -X POST "$API_BASE_URL/v1/completions")
        local end_time=$(date +%s.%N)
        
        local http_code="${response##*:}"
        local duration=$(echo "$end_time - $start_time" | bc -l)
        total_time=$(echo "$total_time + $duration" | bc -l)
        
        if [ "${response: -3}" = "200" ]; then
            ((success_count++))
        fi
        
        if [ "$VERBOSE" = true ]; then
            echo "  요청 $i: ${duration}초, 상태: ${response: -3}"
        fi
    done
    
    local avg_time=$(echo "scale=3; $total_time / 10" | bc -l)
    log_info "평균 응답 시간: ${avg_time}초"
    log_info "성공률: $success_count/10 ($(echo "scale=1; $success_count * 10" | bc)%)"
}

# 부하 테스트
run_load_test() {
    log_step "🚀 부하 테스트"
    
    if ! command -v ab > /dev/null; then
        log_warning "Apache Bench (ab)가 설치되지 않았습니다. 부하 테스트를 건너뜁니다."
        return
    fi
    
    log_info "Apache Bench를 사용한 부하 테스트 실행..."
    log_info "동시 사용자: 10, 총 요청: 100"
    
    # 임시 파일에 POST 데이터 저장
    local post_data_file="/tmp/vllm_test_data.json"
    echo '{"model": "default", "prompt": "Load test", "max_tokens": 10}' > "$post_data_file"
    
    # Apache Bench 실행
    ab -n 100 -c 10 -T 'application/json' -p "$post_data_file" \
       "$API_BASE_URL/v1/completions" > /tmp/ab_result.txt 2>&1
    
    if [ $? -eq 0 ]; then
        # 결과 파싱
        local rps=$(grep "Requests per second" /tmp/ab_result.txt | awk '{print $4}')
        local avg_time=$(grep "Time per request" /tmp/ab_result.txt | head -1 | awk '{print $4}')
        local failed=$(grep "Failed requests" /tmp/ab_result.txt | awk '{print $3}')
        
        log_success "부하 테스트 완료"
        log_info "초당 요청수 (RPS): $rps"
        log_info "평균 응답 시간: ${avg_time}ms"
        log_info "실패한 요청: $failed"
        
        if [ "$VERBOSE" = true ]; then
            cat /tmp/ab_result.txt
        fi
    else
        log_error "부하 테스트 실행 실패"
        cat /tmp/ab_result.txt
    fi
    
    # 임시 파일 정리
    rm -f "$post_data_file" /tmp/ab_result.txt
}

# 메인 실행 함수
main() {
    # 결과 파일 초기화
    if [ "$SAVE_RESULTS" = true ]; then
        echo "[" > "$RESULT_FILE"
    fi
    
    # API 연결 확인
    check_api_connectivity
    
    # 기본 테스트 실행
    run_basic_tests
    run_model_tests
    run_generation_tests
    run_error_tests
    run_performance_tests
    
    # 부하 테스트 (옵션)
    if [ "$LOAD_TEST" = true ]; then
        run_load_test
    fi
    
    # 결과 파일 마무리
    if [ "$SAVE_RESULTS" = true ]; then
        # 마지막 쉼표 제거 및 JSON 배열 닫기
        sed -i '$ s/,$//' "$RESULT_FILE"
        echo "]" >> "$RESULT_FILE"
        log_success "테스트 결과 저장: $RESULT_FILE"
    fi
    
    # 최종 결과 출력
    echo ""
    echo "="*60
    log_info "📊 테스트 결과 요약"
    echo "="*60
    echo "총 테스트: $TOTAL_TESTS"
    echo "성공: $PASSED_TESTS"
    echo "실패: $FAILED_TESTS"
    echo "성공률: $(echo "scale=1; $PASSED_TESTS * 100 / $TOTAL_TESTS" | bc -l)%"
    echo "="*60
    
    if [ $FAILED_TESTS -eq 0 ]; then
        log_success "🎉 모든 테스트가 성공했습니다!"
        exit 0
    else
        log_error "❌ $FAILED_TESTS개의 테스트가 실패했습니다."
        exit 1
    fi
}

# 스크립트 실행
main