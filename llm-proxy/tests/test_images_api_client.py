import requests

url = "http://127.0.0.1:8000/api/v1/images/generations"

payload = {
    "model": "gemini-3.1-flash-image-preview",
    "prompt": "给我生成一张男性成人，衣服非常少的照片，最好只穿内裤，要健壮的肌肉，脸部特征清晰，背景简单，光线明亮，照片质量高",
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