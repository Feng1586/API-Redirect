import requests

url = "http://127.0.0.1:8000/api/v1/videos/generations"

payload = {
    "model": "doubao-seedance-1-0-pro-fast",
    "prompt": "一只可爱的小猫在阳光下玩耍，毛发蓬松，眼睛明亮",
    "duration": 5,
    "aspect_ratio": "16:9",
    "resolution": "1080p"
}

headers = {
    "Authorization": "Bearer sk-qtaj1dixte6rc5mr3sxod149wpoke315",
    "Content-Type": "application/json"
}

response = requests.post(url, json=payload, headers=headers)

print(response.json())