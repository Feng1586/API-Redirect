#!/usr/bin/env python3
import subprocess
import time
import signal
import sys
import os
import asyncio
import httpx

def start_gemini_api():
    """启动test_gemini_api.py服务"""
    print("启动Gemini API代理服务...")
    # 使用uvicorn启动服务
    process = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "test_gemini_api:app", "--host", "127.0.0.1", "--port", "8000", "--reload"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True
    )
    
    # 等待服务启动
    time.sleep(3)
    
    # 检查服务是否启动
    try:
        response = httpx.get("http://127.0.0.1:8000/docs", timeout=5)
        if response.status_code == 200:
            print("服务启动成功")
            return process
    except:
        print("服务启动可能失败，检查日志...")
    
    return process

def stop_gemini_api(process):
    """停止服务"""
    print("\n停止Gemini API代理服务...")
    process.terminate()
    process.wait(timeout=5)

async def run_client_tests():
    """运行客户端测试"""
    print("\n运行客户端测试...")
    
    # 直接运行test_gemini_api_client.py
    result = subprocess.run(
        [sys.executable, "test_gemini_api_client.py"],
        capture_output=True,
        text=True
    )
    
    print("客户端测试输出:")
    print(result.stdout)
    if result.stderr:
        print("客户端测试错误:")
        print(result.stderr)
    
    return result.returncode

def main():
    """主函数"""
    print("Gemini API流式传输测试")
    print("=" * 50)
    
    # 检查test_gemini_api.py是否存在
    if not os.path.exists("test_gemini_api.py"):
        print("错误: test_gemini_api.py不存在")
        return 1
    
    # 检查test_gemini_api_client.py是否存在
    if not os.path.exists("test_gemini_api_client.py"):
        print("错误: test_gemini_api_client.py不存在")
        return 1
    
    # 启动服务
    api_process = start_gemini_api()
    
    try:
        # 等待服务完全启动
        time.sleep(5)
        
        # 运行客户端测试
        exit_code = asyncio.run(run_client_tests())
        
        # 如果需要，可以添加更多的测试
        print("\n" + "=" * 50)
        print(f"测试完成，退出码: {exit_code}")
        
        return exit_code
    finally:
        # 确保停止服务
        stop_gemini_api(api_process)

if __name__ == "__main__":
    sys.exit(main())