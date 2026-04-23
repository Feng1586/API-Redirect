from openai import OpenAI

client = OpenAI(
    api_key="sk-qtaj1dixte6rc5mr3sxod149wpoke315",
    base_url="http://127.0.0.1:8000/api/v1",  # 替换为你需要的地址
)

# client = OpenAI(
#     api_key="sk-An7bxzzKGHsqNs9b8U4ZGvXfmiL3utujmbPflSro0UUmU9Xu",
#     base_url="https://api.apimart.ai/v1"  # 替换为你需要的地址
# )

response = client.chat.completions.create(
    model="gpt-5",
    messages=[{"role": "user", "content": "你好"}],
    #stream=True,  # 流式响应
)

#必须遍历才能获取数据
for chunk in response:
    print(chunk)

#print(response)