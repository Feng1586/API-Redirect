import requests

url = "http://127.0.0.1:8000/api/v1/beta/models/gemini-2.5-flash:generateContent"

payload = {
    "contents": [
        {
            "role": "user",
            "parts": [
                {
                    "text": "你好，介绍一下自己"
                }
            ]
        }
    ]
}

headers = {
    "Authorization": "Bearer sk-qtaj1dixte6rc5mr3sxod149wpoke315",
    "Content-Type": "application/json"
}

response = requests.post(url, json=payload, headers=headers)

print(response.json())