"""
生图 & 生视频接口测试脚本
用法: python tests/media_tests/test_image_video.py
"""

import asyncio
import json
import sys
import time
import httpx

# ========== 配置 ==========
BASE_URL = "http://127.0.0.1:8000/api/v1"
API_KEY = "sk-qtaj1dixte6rc5mr3sxod149wpoke315"
AUTH_HEADER = {
    "Authorization": f"Bearer {API_KEY}",
    "Content-Type": "application/json",
}

POLL_INTERVAL = 5       # 轮询间隔（秒）
POLL_TIMEOUT = 600      # 最大等待时间（秒），视频可能较久
TERMINAL_STATUSES = {"completed", "failed", "cancelled"}


def print_header(text: str) -> None:
    print(f"\n{'='*70}")
    print(f"  {text}")
    print(f"{'='*70}")


# =====================================================================
#  创建任务（POST）
# =====================================================================
async def create_task(
    label: str, url: str, body: dict
) -> str | None:
    """创建生图/生视频任务，返回 task_id 或 None"""
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.post(url, json=body, headers=AUTH_HEADER)
    data = resp.json()
    print(f"\n  [创建] {label}")
    print(f"  状态码: {resp.status_code}")
    print(f"  响应: {json.dumps(data, indent=2, ensure_ascii=False)}")

    if resp.status_code == 200:
        # 兼容两种响应格式：
        # 1. data 是列表: {"code": 200, "data": [{"status": "submitted", "task_id": "..."}]}
        # 2. data 是对象: {"code": 200, "data": {"id": "...", "status": "..."}}
        inner = data.get("data")
        if isinstance(inner, list) and len(inner) > 0:
            task_id = inner[0].get("task_id")
        elif isinstance(inner, dict):
            task_id = inner.get("id") or inner.get("task_id")
        else:
            task_id = None
        if task_id:
            print(f"  ✅ 获得 task_id: {task_id}")
            return task_id
    print(f"  ❌ 创建失败")
    return None


# =====================================================================
#  轮询查询任务
# =====================================================================
async def poll_task(
    label: str, task_id: str, task_type: str
) -> dict | None:
    """
    轮询查询任务进度，直到终态或超时。
    返回最终的 data dict，或 None 表示超时/失败。
    """
    query_url = f"{BASE_URL}/tasks/{task_id}"
    params = {"language": "zh"}
    headers = {"Authorization": f"Bearer {API_KEY}"}
    start = time.time()

    print(f"\n  [轮询] {label} ({task_type}) - task_id: {task_id}")

    async with httpx.AsyncClient(timeout=30.0) as client:
        while True:
            elapsed = time.time() - start
            if elapsed > POLL_TIMEOUT:
                print(f"  ⏰ 超时 ({POLL_TIMEOUT}s)，停止轮询")
                return None

            resp = await client.get(query_url, headers=headers, params=params)
            data = resp.json()

            # 兼容查询的三种响应格式：
            # 1. {"code": 200, "data": {"id": "...", "status": "...", "progress": 0}}
            # 2. {"code": "success", "data": [{"task_id": "...", "status": "..."}]}
            # 3. 直接返回 {"id": "...", "status": "...", ...}
            inner = data.get("data", data)
            if isinstance(inner, list):
                inner = inner[0] if inner else {}
            status = inner.get("status", "unknown")
            progress = inner.get("progress", 0)

            print(f"  [{elapsed:5.0f}s] 状态: {status:12s}  进度: {progress}%")

            if status in TERMINAL_STATUSES:
                return inner

            await asyncio.sleep(POLL_INTERVAL)


# =====================================================================
#  打印结果
# =====================================================================
def print_image_result(data: dict) -> None:
    """打印图片生成结果"""
    result = data.get("result", {})
    images = result.get("images", [])
    print(f"\n  {'─'*60}")
    print(f"  📷 图片生成完成")
    print(f"  耗时: {data.get('actual_time', '?')}s  (预估: {data.get('estimated_time', '?')}s)")
    for i, img in enumerate(images):
        urls = img.get("url", [])
        expires = img.get("expires_at", "?")
        for u in urls:
            print(f"  图片[{i}]: {u}")
        if expires:
            print(f"  过期时间: {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(expires))}")


def print_video_result(data: dict) -> None:
    """打印视频生成结果"""
    result = data.get("result", {})
    thumbnail = result.get("thumbnail_url", "")
    videos = result.get("videos", [])
    print(f"\n  {'─'*60}")
    print(f"  🎬 视频生成完成")
    print(f"  耗时: {data.get('actual_time', '?')}s  (预估: {data.get('estimated_time', '?')}s)")
    if thumbnail:
        print(f"  缩略图: {thumbnail}")
    for i, vid in enumerate(videos):
        urls = vid.get("url", [])
        expires = vid.get("expires_at", "?")
        for u in urls:
            print(f"  视频[{i}]: {u}")
        if expires:
            print(f"  过期时间: {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(expires))}")


def print_failed(data: dict) -> None:
    """打印失败信息"""
    print(f"\n  ❌ 任务失败")
    print(f"  状态: {data.get('status', '?')}")
    print(f"  完整响应: {json.dumps(data, indent=2, ensure_ascii=False)}")


# =====================================================================
#  主流程
# =====================================================================
async def main() -> None:
    print_header("生图 & 生视频接口测试")
    print(f"  Base URL : {BASE_URL}")
    print(f"  API Key  : {API_KEY[:20]}...")
    print(f"  轮询间隔 : {POLL_INTERVAL}s | 超时: {POLL_TIMEOUT}s")

    # ---- 1. 生图 ----
    print_header("1. 创建图片生成任务")

    image_task_id = await create_task(
        "图片生成",
        f"{BASE_URL}/images/generations",
        {
            "model": "gemini-2.5-flash-image-preview",
            "prompt": "月光下的竹林小径",
            "size": "1:1",
            "n": 1,
        },
    )

    # ---- 2. 生视频 ----
    print_header("2. 创建视频生成任务")

    video_task_id = await create_task(
        "视频生成",
        f"{BASE_URL}/videos/generations",
        {
            "model": "grok-imagine-1.0-video-apimart",
            "prompt": "一只狗在海滩上奔跑，阳光明媚，慢镜头",
            "size": "16:9",
            "duration": 6,
            "quality": "720p",
        },
    )

    # ---- 3. 并行轮询 ----
    if not image_task_id and not video_task_id:
        print("\n❌ 没有成功创建任何任务，退出")
        return

    print_header("3. 轮询任务进度（并行）")

    polls = []
    if image_task_id:
        polls.append(poll_task("图片生成", image_task_id, "image"))
    if video_task_id:
        polls.append(poll_task("视频生成", video_task_id, "video"))

    poll_results = await asyncio.gather(*polls)

    # ---- 4. 汇总 ----
    print_header("4. 结果汇总")

    if image_task_id and poll_results[0]:
        data = poll_results[0]
        status = data.get("status")
        if status == "completed":
            print_image_result(data)
        elif status in ("failed", "cancelled"):
            print_failed(data)
        else:
            print(f"\n  图片任务终态: {status}")
    elif image_task_id:
        print(f"\n  📷 图片任务未完成（超时或创建失败）")

    vid_idx = 1 if image_task_id else 0
    if video_task_id and len(poll_results) > vid_idx and poll_results[vid_idx]:
        data = poll_results[vid_idx]
        status = data.get("status")
        if status == "completed":
            print_video_result(data)
        elif status in ("failed", "cancelled"):
            print_failed(data)
        else:
            print(f"\n  视频任务终态: {status}")
    elif video_task_id:
        print(f"\n  🎬 视频任务未完成（超时或创建失败）")

    print(f"\n{'='*70}")
    print(f"  测试结束: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'='*70}\n")


if __name__ == "__main__":
    asyncio.run(main())
