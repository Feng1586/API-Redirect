import requests

url = "http://127.0.0.1:8000/api/v1/images/generations"

payload = {
    "model": "gemini-3.1-flash-image-preview",
    "prompt": "赛博朋克风格的城市夜景，霓虹灯闪烁",
    "size": "16:9",
    "resolution": "2K",
    "n": 1
}

headers = {
    "Authorization": "Bearer sk-qtaj1dixte6rc5mr3sxod149wpoke315",
    "Content-Type": "application/json"
}

response = requests.post(url, json=payload, headers=headers)

print(response.json())