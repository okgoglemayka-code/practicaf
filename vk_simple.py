"""
vk_simple.py - Сборщик постов и комментариев (без OCR)
"""

import requests
import re
import time
from datetime import datetime
from typing import List, Dict
import config


def get_posts(community_url: str, max_posts: int = None) -> List[Dict]:
    """Сбор постов из сообщества"""

    if max_posts is None:
        max_posts = config.MAX_POSTS

    match = re.search(r'vk\.com/([a-zA-Z0-9_]+)', community_url)
    if not match:
        print(f"❌ Не удалось извлечь имя из URL: {community_url}")
        return []

    screen_name = match.group(1)
    print(f"📁 Сообщество: {screen_name}")

    # Получаем ID сообщества
    time.sleep(config.REQUEST_DELAY)
    resp = requests.get('https://api.vk.com/method/utils.resolveScreenName', params={
        'screen_name': screen_name,
        'access_token': config.VK_TOKEN,
        'v': config.VK_API_VERSION
    }).json()

    if 'response' not in resp or not resp['response']:
        print(f"❌ Не найден ID для {screen_name}")
        return []

    group_id = -resp['response']['object_id']
    print(f"   ID сообщества: {group_id}")

    # Получаем посты
    time.sleep(config.REQUEST_DELAY)
    resp = requests.get('https://api.vk.com/method/wall.get', params={
        'owner_id': group_id,
        'count': max_posts,
        'access_token': config.VK_TOKEN,
        'v': config.VK_API_VERSION
    }).json()

    if 'response' not in resp:
        print(f"❌ Не удалось получить посты для {screen_name}")
        return []

    posts = []
    for item in resp['response']['items']:
        post = {
            'post_id': item['id'],
            'owner_id': item['owner_id'],
            'text': item.get('text', ''),
            'date': datetime.fromtimestamp(item['date']),
            'timestamp': item['date'],
            'likes': item['likes']['count'],
            'reposts': item['reposts']['count'],
            'comments_count': item['comments']['count'],
            'views': item.get('views', {}).get('count', 0),
            'url': f"https://vk.com/wall{item['owner_id']}_{item['id']}"
        }
        posts.append(post)

    print(f"   📦 Собрано постов: {len(posts)}")
    return posts


def get_comments(owner_id: int, post_id: int, max_comments: int = 100) -> List[Dict]:
    """Сбор комментариев к посту"""

    time.sleep(config.REQUEST_DELAY)

    resp = requests.get('https://api.vk.com/method/wall.getComments', params={
        'owner_id': owner_id,
        'post_id': post_id,
        'count': min(max_comments, 100),
        'need_likes': 1,
        'access_token': config.VK_TOKEN,
        'v': config.VK_API_VERSION
    }).json()

    if 'response' not in resp:
        return []

    comments = []
    for item in resp['response']['items']:
        comment = {
            'comment_id': item['id'],
            'post_id': post_id,
            'owner_id': item.get('from_id', 0),
            'text': item.get('text', ''),
            'date': datetime.fromtimestamp(item['date']),
            'timestamp': item['date'],
            'likes': item.get('likes', {}).get('count', 0)
        }
        comments.append(comment)

    return comments