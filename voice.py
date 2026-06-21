"""
voice.py —— 语音播报与台词生成

负责"AI 该说什么、怎么说出来"，跟棋盘逻辑无关。
"""

import os
import subprocess
import sys
import threading

import requests

# 强制直连，避免本地代理干扰 Ollama / TTS 请求
os.environ['NO_PROXY'] = 'localhost,127.0.0.1,::1'

VOICE_NAME = "zh-CN-XiaoyiNeural"  # 晓伊：可爱傲娇的少女音
TTS_OUTPUT_FILE = "current_taunt.mp3"
OLLAMA_URL = "http://127.0.0.1:11434/api/generate"
OLLAMA_MODEL = "qwen2.5:7b"


def _play_edge_tts_thread(text):
    try:
        if os.path.exists(TTS_OUTPUT_FILE):
            os.remove(TTS_OUTPUT_FILE)  # 强制清空缓存防幽灵音

        subprocess.run([
            sys.executable, '-m', 'edge_tts',
            '--voice', VOICE_NAME,
            '--rate=+5%',
            '--pitch=+10Hz',
            '--text', text,
            '--write-media', TTS_OUTPUT_FILE
        ], check=True)

        if os.path.exists(TTS_OUTPUT_FILE):
            subprocess.run(['afplay', TTS_OUTPUT_FILE])
    except Exception as e:
        print(f"⚠️ 语音播报异常: {e}")


def speak_taunt(text):
    """异步播报一句话，不阻塞主循环。"""
    threading.Thread(target=_play_edge_tts_thread, args=(text,), daemon=True).start()


def call_ollama(prompt, model_name=OLLAMA_MODEL, fallback="哼。"):
    try:
        response = requests.post(
            OLLAMA_URL,
            json={"model": model_name, "prompt": prompt, "stream": False},
            timeout=5,
        )
        if response.status_code == 200:
            return response.json().get("response", "").strip()
    except Exception:
        pass
    return fallback


def generate_taunt(human_pos, ai_pos):
    return call_ollama(
        f"你是一个傲娇、毒舌的五子棋AI少女。人类下在{human_pos}，我极其轻蔑地下在{ai_pos}。请用15字以内嘲讽：",
        fallback="破绽百出，大笨蛋！",
    )


def generate_checkmate_taunt(is_human_threat):
    if is_human_threat:
        return call_ollama(
            "你是一个傲娇的五子棋少女，人类刚走出必赢活四，请用15字以内找个极其荒谬的借口死不认输。",
            fallback="不公平，肯定是风把棋子吹跑了！",
        )
    return call_ollama(
        "你是一个傲娇的五子棋少女，你刚走出必赢活四。请用15字以内发表极其嚣张的宣告。",
        fallback="放弃挣扎吧，本小姐赢定了！",
    )


def generate_endgame_taunt(is_human_win):
    if is_human_win:
        return call_ollama(
            "你是一个傲娇的五子棋少女，你彻底输给了人类。用15字找极其傲娇的破防借口。",
            fallback="哼，这次只是本小姐让你而已！",
        )
    return call_ollama(
        "你是一个傲娇的五子棋少女，你连成5子碾压了人类。发表终极胜利宣言。",
        fallback="这就是惹怒本小姐的下场！",
    )
