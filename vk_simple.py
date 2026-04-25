"""
vk_simple.py - Сборщик постов и комментариев (с пагинацией)
"""

import requests
import re
import time
from datetime import datetime
from typing import List, Dict
import config


def get_posts(community_url: str, max_posts: int = None) -> List[Dict]:
    """
    Сбор постов из сообщества с поддержкой пагинации
    Теперь может собрать больше 100 постов
    """

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

    # ============================================================
    # ПАГИНАЦИЯ: собираем посты по 100 штук за раз
    # ============================================================

    all_posts = []
    offset = 0
    batch_size = min(100, max_posts)  # VK API максимум 100 за раз

    print(f"   Нужно собрать: {max_posts} постов")

    while len(all_posts) < max_posts:
        # Сколько ещё нужно собрать
        remaining = max_posts - len(all_posts)
        current_count = min(batch_size, remaining)

        print(f"   Запрос {offset//100 + 1}: посты {offset+1}-{offset+current_count}...", end=" ")

        time.sleep(config.REQUEST_DELAY)
        resp = requests.get('https://api.vk.com/method/wall.get', params={
            'owner_id': group_id,
            'count': current_count,
            'offset': offset,
            'access_token': config.VK_TOKEN,
            'v': config.VK_API_VERSION
        }).json()

        if 'response' not in resp:
            print(f"❌ Ошибка: {resp}")
            break

        items = resp['response']['items']

        if not items:
            print("постов больше нет")
            break

        for item in items:
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
            all_posts.append(post)

        print(f"✅ +{len(items)} (всего: {len(all_posts)})")

        offset += len(items)

        # Если получили меньше, чем запрашивали — значит посты закончились
        if len(items) < current_count:
            print(f"   Достигнут конец стены")
            break

    print(f"\n   📦 ВСЕГО собрано постов: {len(all_posts)}")
    return all_posts


def get_comments(owner_id: int, post_id: int, max_comments: int = 100) -> List[Dict]:
    """Сбор комментариев к посту (тоже с пагинацией)"""

    all_comments = []
    offset = 0
    batch_size = min(100, max_comments)

    while len(all_comments) < max_comments:
        remaining = max_comments - len(all_comments)
        current_count = min(batch_size, remaining)

        time.sleep(config.REQUEST_DELAY)

        resp = requests.get('https://api.vk.com/method/wall.getComments', params={
            'owner_id': owner_id,
            'post_id': post_id,
            'count': current_count,
            'offset': offset,
            'need_likes': 1,
            'access_token': config.VK_TOKEN,
            'v': config.VK_API_VERSION
        }).json()

        if 'response' not in resp:
            break

        items = resp['response']['items']

        if not items:
            break

        for item in items:
            comment = {
                'comment_id': item['id'],
                'post_id': post_id,
                'owner_id': item.get('from_id', 0),
                'text': item.get('text', ''),
                'date': datetime.fromtimestamp(item['date']),
                'timestamp': item['date'],
                'likes': item.get('likes', {}).get('count', 0)
            }
            all_comments.append(comment)

        offset += len(items)

        if len(items) < current_count:
            break

    return all_comments