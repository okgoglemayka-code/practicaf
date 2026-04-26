"""
config.py - Конфигурация проекта
"""

# VK НАСТРОЙКИ
VK_TOKEN = "aae35cf6aae35cf6aae35cf6f7a9a32db5aaae3aae35cf6c3057e2412c3f06a87858e98"
VK_API_VERSION = "5.131"
REQUEST_DELAY = 0.34

# POSTGRESQL НАСТРОЙКИ
PG_CONFIG = {
    'host': 'localhost',
    'port': 5432,
    'database': 'vk_analysis',
    'user': 'postgres',
    'password': '1234'
}


MAX_POSTS = 100
MAX_COMMENTS = 100

# НАСТРОЙКИ АНАЛИЗА
ANALYSIS_BATCH_SIZE = 500
SENTIMENT_THRESHOLD_NEGATIVE = 0.7
MIN_TEXT_LENGTH_ANALYSIS = 5
# ДОПОЛНИТЕЛЬНЫЙ NLP/ИИ-МОДУЛЬ
# По умолчанию выключен, чтобы проект запускался без внешних моделей.
# Для включения установите Ollama, скачайте модель и поставьте ENABLE_NLP_AI = True.
# Пример команды: ollama pull qwen2.5:7b-instruct
ENABLE_NLP_AI = True
NLP_AI_PROVIDER = "ollama"
NLP_AI_MODEL = "qwen2.5:7b-instruct"
NLP_AI_URL = "http://localhost:11434/api/generate"
NLP_AI_TIMEOUT = 30
NLP_AI_TEMPERATURE = 0.0
NLP_AI_MAX_TEXT_LENGTH = 1200

# Если True, NLP/ИИ-модель вызывается для каждого текста достаточной длины.
# Если False, модель вызывается только для спорных случаев.
NLP_AI_ALWAYS_ANALYZE = False
