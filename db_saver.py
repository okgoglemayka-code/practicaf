"""
db_saver.py - Сохранение данных в PostgreSQL (простая версия)
"""

import psycopg2
import re
from datetime import datetime
from typing import List, Dict, Optional
import config


class DatabaseSaver:
    """Класс для сохранения данных в PostgreSQL"""

    def __init__(self):
        self.conn = None
        self.cur = None

    def connect(self) -> bool:
        try:
            self.conn = psycopg2.connect(**config.PG_CONFIG)
            self.cur = self.conn.cursor()
            print("✅ Подключено к PostgreSQL")
            return True
        except Exception as e:
            print(f"❌ Ошибка подключения: {e}")
            return False

    def disconnect(self):
        if self.cur:
            self.cur.close()
        if self.conn:
            self.conn.close()
        print("🔌 Отключено от PostgreSQL")

    def drop_all_tables(self):
        """Удаление всех таблиц"""
        print(f"\n🗑️ УДАЛЕНИЕ СТАРЫХ ТАБЛИЦ")
        print("-" * 40)

        self.cur.execute("DROP TABLE IF EXISTS comments CASCADE")
        self.cur.execute("DROP TABLE IF EXISTS posts CASCADE")
        self.conn.commit()
        print(f"   ✅ Таблицы удалены")
        print("-" * 40)

    def create_tables(self):
        """Создание таблиц"""

        # Таблица постов
        self.cur.execute("""
            CREATE TABLE IF NOT EXISTS posts (
                id SERIAL PRIMARY KEY,
                post_id INTEGER NOT NULL UNIQUE,
                screen_name VARCHAR(100),
                text TEXT,
                date TIMESTAMP,
                timestamp INTEGER,
                likes INTEGER DEFAULT 0,
                reposts INTEGER DEFAULT 0,
                comments_count INTEGER DEFAULT 0,
                views INTEGER DEFAULT 0,
                url VARCHAR(500),
                text_length INTEGER,
                has_links BOOLEAN DEFAULT FALSE,
                collected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Таблица комментариев
        self.cur.execute("""
            CREATE TABLE IF NOT EXISTS comments (
                id SERIAL PRIMARY KEY,
                comment_id INTEGER NOT NULL UNIQUE,
                post_id INTEGER REFERENCES posts(id),
                screen_name VARCHAR(100),
                text TEXT,
                date TIMESTAMP,
                timestamp INTEGER,
                likes INTEGER DEFAULT 0,
                text_length INTEGER,
                has_links BOOLEAN DEFAULT FALSE,
                collected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        self.conn.commit()
        print("✅ Таблицы созданы")
        print("   - posts (посты)")
        print("   - comments (комментарии)")

    def add_post(self, post: Dict) -> Optional[int]:
        """Добавление поста"""

        text_length = len(post.get('text', ''))
        has_links = 'http' in post.get('text', '').lower()

        self.cur.execute("""
            INSERT INTO posts 
            (post_id, screen_name, text, date, timestamp,
             likes, reposts, comments_count, views, url, 
             text_length, has_links)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (post_id) DO UPDATE SET
                likes = EXCLUDED.likes,
                reposts = EXCLUDED.reposts,
                comments_count = EXCLUDED.comments_count,
                views = EXCLUDED.views
            RETURNING id
        """, (
            post['post_id'], post.get('screen_name'), post['text'], post['date'],
            post['timestamp'], post['likes'], post['reposts'], post['comments_count'],
            post['views'], post['url'], text_length, has_links
        ))

        self.conn.commit()
        return self.cur.fetchone()[0]

    def add_comment(self, comment: Dict, post_db_id: int) -> Optional[int]:
        """Добавление комментария"""

        text_length = len(comment.get('text', ''))
        has_links = 'http' in comment.get('text', '').lower()

        try:
            self.cur.execute("""
                INSERT INTO comments 
                (comment_id, post_id, screen_name, text, date, timestamp, likes, text_length, has_links)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (comment_id) DO NOTHING
                RETURNING id
            """, (
                comment['comment_id'], post_db_id, comment.get('screen_name'),
                comment.get('text', ''), comment.get('date'), comment.get('timestamp'),
                comment.get('likes', 0), text_length, has_links
            ))

            self.conn.commit()
            return self.cur.fetchone()[0] if self.cur.rowcount > 0 else None
        except Exception as e:
            return None

    def add_posts_batch(self, posts: List[Dict], screen_name: str) -> int:
        added = 0
        for post in posts:
            if post.get('text'):
                post['screen_name'] = screen_name
                result = self.add_post(post)
                if result:
                    added += 1
        print(f"✅ Добавлено постов в БД: {added}")
        return added

    def add_comments_batch(self, comments: List[Dict], screen_name: str, post_db_id: int) -> int:
        added = 0
        for comment in comments:
            if comment.get('text'):
                comment['screen_name'] = screen_name
                result = self.add_comment(comment, post_db_id)
                if result:
                    added += 1
        return added

    def get_post_by_vk_id(self, post_id: int) -> Optional[int]:
        self.cur.execute("SELECT id FROM posts WHERE post_id = %s", (post_id,))
        row = self.cur.fetchone()
        return row[0] if row else None

    def get_statistics(self) -> Dict:
        stats = {}

        self.cur.execute("SELECT COUNT(*) FROM posts")
        stats['total_posts'] = self.cur.fetchone()[0] or 0

        self.cur.execute("SELECT COUNT(*) FROM comments")
        stats['total_comments'] = self.cur.fetchone()[0] or 0

        self.cur.execute("SELECT COALESCE(SUM(likes), 0) FROM posts")
        stats['total_likes'] = self.cur.fetchone()[0] or 0

        self.cur.execute("SELECT COALESCE(AVG(likes), 0) FROM posts")
        stats['avg_likes'] = round(self.cur.fetchone()[0] or 0, 1)

        return stats


def load_community_data(community_url: str = None, max_posts: int = 50, max_comments: int = 30):
    """Загрузка данных для сообщества"""
    from vk_simple import get_posts, get_comments

    # Запрашиваем ссылку
    if community_url is None:
        print("\n" + "=" * 70)
        print("📌 ВВЕДИТЕ ССЫЛКУ НА ПАБЛИК ВКОНТАКТЕ")
        print("=" * 70)
        print("Примеры:")
        print("  - https://vk.com/durov")
        print("  - https://vk.com/whyprojectrus")
        print("-" * 70)
        community_url = input("🔗 Ссылка: ").strip()

        if not community_url:
            print("❌ Ссылка не введена!")
            return False

    # Извлекаем имя
    match = re.search(r'vk\.com/([a-zA-Z0-9_]+)', community_url)
    if not match:
        print(f"❌ Неверный формат URL: {community_url}")
        return False

    screen_name = match.group(1)

    print("=" * 70)
    print(f"🛡️ ЗАГРУЗКА ДАННЫХ ДЛЯ @{screen_name}")
    print("=" * 70)
    print("\n⚠️ ВНИМАНИЕ: СТАРЫЕ ДАННЫЕ БУДУТ УДАЛЕНЫ!")
    print("=" * 70)

    # Подключаемся к БД
    db = DatabaseSaver()
    if not db.connect():
        return False

    # Удаляем старые таблицы и создаём новые
    db.drop_all_tables()
    db.create_tables()

    # Собираем посты
    print(f"\n📥 СБОР ПОСТОВ...")
    posts = get_posts(community_url, max_posts)

    if not posts:
        print("❌ Не удалось собрать посты")
        db.disconnect()
        return False

    # Сохраняем посты
    print(f"\n💾 СОХРАНЕНИЕ ПОСТОВ...")
    db.add_posts_batch(posts, screen_name)

    # Собираем и сохраняем комментарии
    print(f"\n💬 СБОР КОММЕНТАРИЕВ...")
    total_comments = 0

    for i, post in enumerate(posts, 1):
        print(f"   Пост {i}/{len(posts)} (ID: {post['post_id']})...", end=" ")
        comments = get_comments(post['owner_id'], post['post_id'], max_comments)

        post_db_id = db.get_post_by_vk_id(post['post_id'])

        if post_db_id:
            added = db.add_comments_batch(comments, screen_name, post_db_id)
            total_comments += added
            print(f"✅ {added} комментариев")
        else:
            print(f"⚠️ Пост не найден")

    # Статистика
    stats = db.get_statistics()

    print("\n" + "=" * 70)
    print("📊 ИТОГОВАЯ СТАТИСТИКА")
    print("=" * 70)
    print(f"📁 Сообщество: @{screen_name}")
    print(f"📝 Постов: {stats['total_posts']}")
    print(f"💬 Комментариев: {stats['total_comments']}")
    print(f"❤️ Всего лайков: {stats['total_likes']}")
    print(f"📊 Среднее лайков на пост: {stats['avg_likes']}")

    db.disconnect()

    print("\n" + "=" * 70)
    print("✅ ГОТОВО!")
    print("=" * 70)

    return True


if __name__ == "__main__":
    load_community_data(max_posts=20, max_comments=20)