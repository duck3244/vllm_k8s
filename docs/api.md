# vLLM API 서버 문서

## 개요

vLLM API 서버는 대화형 AI 모델을 위한 REST API를 제공합니다. 이 문서는 API 엔드포인트, 요청/응답 형식, 그리고 사용 예제를 포함합니다.

## 기본 정보

- **Base URL**: `http://localhost:8000`
- **Content-Type**: `application/json`
- **인증**: 현재 인증 없음 (개발 환경)

## API 엔드포인트

### 1. 헬스 체크

서버 상태를 확인합니다.

```http
GET /health
```

**응답:**
```json
{
  "status": "healthy",
  "timestamp": "2025-06-14T10:30:00Z",
  "version": "1.0.0"
}
```

### 2. 모델 정보

사용 가능한 모델 목록을 조회합니다.

```http
GET /v1/models
```

**응답:**
```json
{
  "object": "list",
  "data": [
    {
      "id": "meta-llama/Llama-2-7b-chat-hf",
      "object": "model",
      "created": 1687882411,
      "owned_by": "meta"
    }
  ]
}
```

### 3. 채팅 완성 (Chat Completions)

대화형 AI와 상호작용합니다.

```http
POST /v1/chat/completions
```

**요청 본문:**
```json
{
  "model": "meta-llama/Llama-2-7b-chat-hf",
  "messages": [
    {
      "role": "system",
      "content": "You are a helpful assistant."
    },
    {
      "role": "user", 
      "content": "Hello, how are you?"
    }
  ],
  "temperature": 0.7,
  "max_tokens": 150,
  "stream": false
}
```

**요청 매개변수:**

| 매개변수 | 타입 | 필수 | 기본값 | 설명 |
|---------|------|------|--------|------|
| `model` | string | ✅ | - | 사용할 모델 ID |
| `messages` | array | ✅ | - | 대화 메시지 배열 |
| `temperature` | float | ❌ | 1.0 | 창의성 조절 (0.0-2.0) |
| `max_tokens` | integer | ❌ | 16 | 최대 토큰 수 |
| `stream` | boolean | ❌ | false | 스트리밍 응답 여부 |
| `top_p` | float | ❌ | 1.0 | 핵심 샘플링 매개변수 |
| `frequency_penalty` | float | ❌ | 0.0 | 빈도 페널티 |
| `presence_penalty` | float | ❌ | 0.0 | 존재 페널티 |

**응답:**
```json
{
  "id": "chatcmpl-123",
  "object": "chat.completion",
  "created": 1677652288,
  "model": "meta-llama/Llama-2-7b-chat-hf",
  "choices": [
    {
      "index": 0,
      "message": {
        "role": "assistant",
        "content": "Hello! I'm doing well, thank you for asking. How can I help you today?"
      },
      "finish_reason": "stop"
    }
  ],
  "usage": {
    "prompt_tokens": 10,
    "completion_tokens": 17,
    "total_tokens": 27
  }
}
```

### 4. 스트리밍 응답

실시간으로 응답을 받습니다.

```http
POST /v1/chat/completions
Content-Type: application/json

{
  "model": "meta-llama/Llama-2-7b-chat-hf",
  "messages": [{"role": "user", "content": "Count to 5"}],
  "stream": true
}
```

**스트리밍 응답:**
```
data: {"id":"chatcmpl-123","object":"chat.completion.chunk","created":1677652288,"model":"meta-llama/Llama-2-7b-chat-hf","choices":[{"index":0,"delta":{"content":"1"},"finish_reason":null}]}

data: {"id":"chatcmpl-123","object":"chat.completion.chunk","created":1677652288,"model":"meta-llama/Llama-2-7b-chat-hf","choices":[{"index":0,"delta":{"content":" 2"},"finish_reason":null}]}

data: [DONE]
```

### 5. 텍스트 완성 (Legacy)

텍스트 완성 API입니다.

```http
POST /v1/completions
```

**요청 본문:**
```json
{
  "model": "meta-llama/Llama-2-7b-chat-hf",
  "prompt": "The future of AI is",
  "max_tokens": 50,
  "temperature": 0.7
}
```

**응답:**
```json
{
  "id": "cmpl-123",
  "object": "text_completion",
  "created": 1677652288,
  "model": "meta-llama/Llama-2-7b-chat-hf",
  "choices": [
    {
      "text": "bright and full of possibilities...",
      "index": 0,
      "finish_reason": "length"
    }
  ],
  "usage": {
    "prompt_tokens": 5,
    "completion_tokens": 50,
    "total_tokens": 55
  }
}
```

## 에러 응답

API는 표준 HTTP 상태 코드를 사용합니다:

- `200`: 성공
- `400`: 잘못된 요청
- `401`: 인증되지 않음
- `429`: 요청 한도 초과
- `500`: 서버 내부 오류

**에러 응답 형식:**
```json
{
  "error": {
    "message": "Invalid request format",
    "type": "invalid_request_error",
    "code": "invalid_format"
  }
}
```

## 사용 예제

### Python 클라이언트

```python
import requests
import json

# 기본 설정
base_url = "http://localhost:8000"
headers = {"Content-Type": "application/json"}

# 채팅 완성 요청
def chat_completion(messages, model="meta-llama/Llama-2-7b-chat-hf"):
    payload = {
        "model": model,
        "messages": messages,
        "temperature": 0.7,
        "max_tokens": 150
    }
    
    response = requests.post(
        f"{base_url}/v1/chat/completions",
        headers=headers,
        json=payload
    )
    
    return response.json()

# 사용 예제
messages = [
    {"role": "system", "content": "You are a helpful assistant."},
    {"role": "user", "content": "What is machine learning?"}
]

result = chat_completion(messages)
print(result["choices"][0]["message"]["content"])
```

### JavaScript/Node.js 클라이언트

```javascript
const axios = require('axios');

const baseURL = 'http://localhost:8000';

async function chatCompletion(messages, model = 'meta-llama/Llama-2-7b-chat-hf') {
  try {
    const response = await axios.post(`${baseURL}/v1/chat/completions`, {
      model: model,
      messages: messages,
      temperature: 0.7,
      max_tokens: 150
    });
    
    return response.data;
  } catch (error) {
    console.error('Error:', error.response.data);
    throw error;
  }
}

// 사용 예제
const messages = [
  { role: 'system', content: 'You are a helpful assistant.' },
  { role: 'user', content: 'Explain quantum computing briefly.' }
];

chatCompletion(messages)
  .then(result => {
    console.log(result.choices[0].message.content);
  })
  .catch(error => {
    console.error('Failed to get response:', error.message);
  });
```

### cURL 예제

```bash
# 채팅 완성
curl -X POST http://localhost:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "meta-llama/Llama-2-7b-chat-hf",
    "messages": [
      {"role": "system", "content": "You are a helpful assistant."},
      {"role": "user", "content": "Hello!"}
    ],
    "temperature": 0.7,
    "max_tokens": 100
  }'

# 스트리밍 응답
curl -X POST http://localhost:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "meta-llama/Llama-2-7b-chat-hf", 
    "messages": [{"role": "user", "content": "Count to 3"}],
    "stream": true
  }' \
  --no-buffer
```

## 성능 최적화

### 배치 처리

여러 요청을 동시에 처리하려면:

```python
import asyncio
import aiohttp

async def batch_chat_completion(messages_list):
    async with aiohttp.ClientSession() as session:
        tasks = []
        for messages in messages_list:
            task = session.post(
                "http://localhost:8000/v1/chat/completions",
                json={
                    "model": "meta-llama/Llama-2-7b-chat-hf",
                    "messages": messages,
                    "temperature": 0.7
                }
            )
            tasks.append(task)
        
        responses = await asyncio.gather(*tasks)
        return [await resp.json() for resp in responses]
```

### 캐싱

동일한 요청의 응답을 캐싱하여 성능을 향상시킬 수 있습니다:

```python
import hashlib
import json
from functools import lru_cache

@lru_cache(maxsize=100)
def cached_chat_completion(messages_hash, temperature=0.7):
    # 실제 API 호출
    return chat_completion(json.loads(messages_hash), temperature)

def get_response_with_cache(messages, temperature=0.7):
    messages_hash = hashlib.md5(
        json.dumps(messages, sort_keys=True).encode()
    ).hexdigest()
    
    return cached_chat_completion(messages_hash, temperature)
```

## 제한사항

- **요청 크기**: 최대 32,768 토큰
- **응답 크기**: 최대 4,096 토큰  
- **동시 연결**: 최대 100개
- **요청 속도**: 분당 최대 1,000회

## 지원 및 문의

- **GitHub Issues**: [프로젝트 저장소](https://github.com/your-repo/vllm-api-server)
- **이메일**: support@yourcompany.com
- **문서**: [전체 문서](https://docs.yourcompany.com)

## 버전 정보

현재 API 버전: `v1`

- `v1.0.0` (2025-06-14): 초기 릴리스
- 향후 변경사항은 이 문서에서 업데이트됩니다.
