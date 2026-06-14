import requests
import os

# 1. 强制让 Python 忽略系统代理，直连本机
os.environ['NO_PROXY'] = 'localhost,127.0.0.1,::1'

# 2. 我们直接用 127.0.0.1 试试，绕过 localhost 单词的解析
url = "http://127.0.0.1:11434/api/generate"

payload = {
    "model": "qwen2.5:7b",
    "prompt": "说一句你好",
    "stream": False
}

print("开始向 Ollama 发送请求，请稍等...")

try:
    # 增加更长的超时时间
    response = requests.post(url, json=payload, timeout=40)
    print(f"✅ 请求成功！状态码: {response.status_code}")
    print(f"🤖 AI 回复: {response.json().get('response')}")

except Exception as e:
    # 把之前遮盖起来的真实错误暴露出来
    print(f"❌ 请求失败，抓到了真正的错误原因：")
    print(f"错误类型: {type(e).__name__}")
    print(f"详细信息: {e}")