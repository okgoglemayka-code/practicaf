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
    'password': '1234'  # ИЗМЕНИТЕ НА ВАШ ПАРОЛЬ
}

# НАСТРОЙКИ СБОРА
MAX_POSTS = 30
MAX_COMMENTS = 20