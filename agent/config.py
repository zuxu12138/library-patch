"""C 主维护的共享配置模块。所有配置从环境变量读取，缺失时给合理默认值，
不因缺少环境变量而在导入期报错。B/A 需要新配置项时请追加新的 os.getenv 行，
不要删除已有行。
"""
import os

SERVICE_BASE_URL = os.getenv("SERVICE_BASE_URL", "http://127.0.0.1:8080")
LLM_BASE_URL = os.getenv("LLM_BASE_URL", "")
LLM_API_KEY = os.getenv("LLM_API_KEY", "")
LLM_MODEL = os.getenv("LLM_MODEL", "gpt-4o-mini")
INTERNAL_TOKEN = os.getenv("INTERNAL_TOKEN", "")
SEATS_DB_PATH = os.getenv("SEATS_DB_PATH", "collector/data/seats.db")
MEMORY_DB_PATH = os.getenv("MEMORY_DB_PATH", "agent/memory.db")
