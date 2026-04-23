import requests

url = "http://127.0.0.1:8000/api/v1/tasks/task_01KPX76G579SZQ68N5HW25ZKKQ"

headers = {
    "Authorization": "Bearer sk-qtaj1dixte6rc5mr3sxod149wpoke315"
}

params = {
    "language": "zh"
}

response = requests.get(url, headers=headers, params=params)

print(response.json())