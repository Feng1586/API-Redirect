import requests
import os

url = "http://127.0.0.1:8000/api/v1/responses"

payload = {
    "model": "gpt-5",
    "input": [
        {
            "role": "user",
            "content": [
                {
                    "type": "input_text",
                    "text": "这张图片里有什么？"
                },
                {
                    "type": "input_image",
                    "image_url": "https://openai-documentation.vercel.app/images/cat_and_otter.png"
                }
            ]
        }
    ],
    "stream": False
}

headers = {
    "Authorization": "Bearer sk-qtaj1dixte6rc5mr3sxod149wpoke315",
    "Content-Type": "application/json"
}

response = requests.post(url, json=payload, headers=headers)

print(response.json())