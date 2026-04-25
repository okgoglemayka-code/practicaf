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


MAX_POSTS = 320
MAX_COMMENTS = 1000

# НАСТРОЙКИ АНАЛИЗА
ANALYSIS_BATCH_SIZE = 500
SENTIMENT_THRESHOLD_NEGATIVE = 0.7
MIN_TEXT_LENGTH_ANALYSIS = 5