import torch
from transformers import AutoTokenizer, AutoModelForCausalLM

model_id = 'torchtorchkimtorch/Llama-3.2-Korean-GGACHI-1B-Instruct-v1'

tokenizer = AutoTokenizer.from_pretrained(model_id)
model = AutoModelForCausalLM.from_pretrained(
    model_id,
    torch_dtype=torch.bfloat16,
    device_map="auto",
)
instruction = "철수가 20개의 연필을 가지고 있었는데 영희가 절반을 가져가고 민수가 남은 5개를 가져갔으면 철수에게 남은 연필의 갯수는 몇개인가요?"

messages = [
    {"role": "user", "content": f"{instruction}"}
    ]

input_ids = tokenizer.apply_chat_template(
    messages,
    add_generation_prompt=True,
    return_tensors="pt"
).to(model.device)

terminators = [
    tokenizer.convert_tokens_to_ids("<|end_of_text|>"),
    tokenizer.convert_tokens_to_ids("<|eot_id|>")
]

outputs = model.generate(
    input_ids,
    max_new_tokens=1024,
    eos_token_id=terminators,
    do_sample=True,
    temperature=0.6,
    top_p=0.9
)

print(tokenizer.decode(outputs[0][input_ids.shape[-1]:], skip_special_tokens=True))

# 로컬에 모델 저장
model_save_path = "./models/torchtorchkimtorch-Llama-3.2-Korean-GGACHI-1B-Instruct-v1"
tokenizer_save_path = "./models/torchtorchkimtorch-Llama-3.2-Korean-GGACHI-1B-Instruct-v1"

model.save_pretrained(model_save_path)
tokenizer.save_pretrained(tokenizer_save_path)

print(f"모델이 {model_save_path}에 저장되었습니다.")
print(f"토크나이저가 {tokenizer_save_path}에 저장되었습니다.")