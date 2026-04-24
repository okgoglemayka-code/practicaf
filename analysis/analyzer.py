"""
analyzer.py- Анализ данных из PostgreSQL
"""

import psycopg2
from typing import List, Dict, Optional, Tuple
from datetime import datetime, timedelta
import sys
import os

# Добавляем родительскую директорию в путь
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config

from .classifier import DestructiveClassifier, DestructiveCategory, DestructiveLevel, ClassificationResult


class DataAnalyzer:
    """Анализатор данных из PostgreSQL"""

    def __init__(self):
        self.classifier = DestructiveClassifier()
        self.conn = None
        self.cur = None

    def connect(self) -> bool:
        """Подключение к БД"""
        try:
            self.conn = psycopg2.connect(**config.PG_CONFIG)
            self.cur = self.conn.cursor()
            print("✅ Подключено к PostgreSQL для анализа")
            return True
        except Exception as e:
            print(f"❌ Ошибка подключения: {e}")
            return False

    def disconnect(self):
        """Отключение от БД"""
        if self.cur:
            self.cur.close()
        if self.conn:
            self.conn.close()
        print("🔌 Отключено от PostgreSQL")

    def add_analysis_columns(self):
        """Добавление колонок для результатов анализа"""
        columns = [
            ("is_analyzed", "BOOLEAN DEFAULT FALSE"),
            ("destructive_category", "VARCHAR(50)"),
            ("destructive_level", "INTEGER DEFAULT 0"),
            ("destructive_confidence", "FLOAT"),
            ("destructive_reason", "TEXT"),
            ("matched_words", "TEXT"),
            ("sentiment_score", "FLOAT"),
            ("analyzed_at", "TIMESTAMP")
        ]

        for col_name, col_type in columns:
            try:
                # Для posts
                self.cur.execute(f"""
                    DO $$ 
                    BEGIN 
                        IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                                       WHERE table_name='posts' AND column_name='{col_name}') 
                        THEN 
                            ALTER TABLE posts ADD COLUMN {col_name} {col_type};
                        END IF;
                    END $$;
                """)

                # Для comments
                self.cur.execute(f"""
                    DO $$ 
                    BEGIN 
                        IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                                       WHERE table_name='comments' AND column_name='{col_name}') 
                        THEN 
                            ALTER TABLE comments ADD COLUMN {col_name} {col_type};
                        END IF;
                    END $$;
                """)
            except Exception as e:
                print(f"⚠️ Ошибка добавления колонки {col_name}: {e}")

        self.conn.commit()
        print("✅ Колонки для анализа добавлены")

    def analyze_posts(self, limit: int = 1000, force_reanalyze: bool = False) -> Dict:
        """
        Анализ постов из БД

        Args:
            limit: максимальное количество постов для анализа
            force_reanalyze: принудительный повторный анализ (игнорирует is_analyzed)

        Returns:
            Словарь со статистикой анализа
        """
        if force_reanalyze:
            # Сбрасываем флаги для повторного анализа
            self.cur.execute("UPDATE posts SET is_analyzed = FALSE")
            self.conn.commit()
            print("🔄 Сброшены флаги для повторного анализа")

        # Получаем необработанные посты
        self.cur.execute("""
            SELECT id, text, post_id, screen_name, views, likes, reposts
            FROM posts 
            WHERE is_analyzed = FALSE 
              AND text IS NOT NULL 
              AND text != ''
            ORDER BY date DESC
            LIMIT %s
        """, (limit,))

        posts = self.cur.fetchall()
        print(f"\n📊 Найдено постов для анализа: {len(posts)}")

        stats = {
            'total': len(posts),
            'processed': 0,
            'by_category': {},
            'by_level': {0: 0, 1: 0, 2: 0, 3: 0}
        }

        for row in posts:
            post_id, text, vk_post_id, screen_name, views, likes, reposts = row

            # Классифицируем
            result = self.classifier.classify(text)

            # Обновляем запись
            self.cur.execute("""
                UPDATE posts 
                SET destructive_category = %s,
                    destructive_level = %s,
                    destructive_confidence = %s,
                    destructive_reason = %s,
                    matched_words = %s,
                    sentiment_score = %s,
                    is_analyzed = TRUE,
                    analyzed_at = NOW()
                WHERE id = %s
            """, (
                result.category.value,
                result.level.value,
                result.confidence,
                result.reason,
                ', '.join(result.matched_words[:5]),
                result.sentiment_score,
                post_id
            ))

            # Статистика
            cat = result.category.value
            stats['by_category'][cat] = stats['by_category'].get(cat, 0) + 1
            stats['by_level'][result.level.value] = stats['by_level'].get(result.level.value, 0) + 1
            stats['processed'] += 1

            # Коммит каждые 100 записей
            if stats['processed'] % 100 == 0:
                self.conn.commit()
                print(f"   Обработано: {stats['processed']}/{stats['total']}")

        self.conn.commit()

        # Обновим статистику по комментариям
        self._analyze_comments_for_analyzed_posts()

        return stats

    def _analyze_comments_for_analyzed_posts(self):
        """Анализ комментариев к проанализированным постам"""
        self.cur.execute("""
            UPDATE comments c
            SET is_analyzed = FALSE
            FROM posts p
            WHERE c.post_id = p.id 
              AND p.is_analyzed = TRUE
              AND c.is_analyzed = FALSE
        """)
        self.conn.commit()

        # Анализируем комментарии
        self.cur.execute("""
            SELECT id, text 
            FROM comments 
            WHERE is_analyzed = FALSE 
              AND text IS NOT NULL 
              AND text != ''
            LIMIT 5000
        """)

        comments = self.cur.fetchall()
        print(f"\n💬 Анализ комментариев: {len(comments)}")

        processed = 0
        for comment_id, text in comments:
            result = self.classifier.classify(text)

            self.cur.execute("""
                UPDATE comments 
                SET destructive_category = %s,
                    destructive_level = %s,
                    destructive_confidence = %s,
                    destructive_reason = %s,
                    matched_words = %s,
                    sentiment_score = %s,
                    is_analyzed = TRUE,
                    analyzed_at = NOW()
                WHERE id = %s
            """, (
                result.category.value,
                result.level.value,
                result.confidence,
                result.reason,
                ', '.join(result.matched_words[:5]),
                result.sentiment_score,
                comment_id
            ))

            processed += 1
            if processed % 500 == 0:
                self.conn.commit()
                print(f"   Комментариев: {processed}/{len(comments)}")

        self.conn.commit()

    def get_statistics(self) -> Dict:
        """Получение статистики анализа"""
        stats = {}

        # Статистика по постам
        self.cur.execute("""
            SELECT 
                destructive_category,
                COUNT(*) as count,
                ROUND(AVG(destructive_confidence)::numeric, 2) as avg_confidence
            FROM posts
            WHERE is_analyzed = TRUE
            GROUP BY destructive_category
            ORDER BY count DESC
        """)
        stats['posts_by_category'] = self.cur.fetchall()

        self.cur.execute("""
            SELECT 
                destructive_level,
                COUNT(*) as count
            FROM posts
            WHERE is_analyzed = TRUE AND destructive_level > 0
            GROUP BY destructive_level
            ORDER BY destructive_level
        """)
        stats['posts_by_level'] = self.cur.fetchall()

        self.cur.execute("""
            SELECT 
                destructive_category,
                COUNT(*) as count
            FROM comments
            WHERE is_analyzed = TRUE
            GROUP BY destructive_category
            ORDER BY count DESC
        """)
        stats['comments_by_category'] = self.cur.fetchall()

        # Топ опасных постов
        self.cur.execute("""
            SELECT post_id, screen_name, text, destructive_category, destructive_level
            FROM posts
            WHERE destructive_level >= 2
            ORDER BY destructive_level DESC, destructive_confidence DESC
            LIMIT 20
        """)
        stats['dangerous_posts'] = self.cur.fetchall()

        return stats

    def print_statistics(self, stats: Dict):
        """Вывод статистики в консоль"""
        print("\n" + "=" * 70)
        print("📊 СТАТИСТИКА АНАЛИЗА ДЕСТРУКТИВНОГО КОНТЕНТА")
        print("=" * 70)

        print("\n📝 ПОСТЫ:")
        print("-" * 40)
        for cat, count, conf in stats['posts_by_category']:
            if cat == 'safe':
                print(f"   • Безопасные: {count}")
            else:
                print(f"   • {cat}: {count} (сред. уверенность: {conf})")

        print("\n⚠️ ПО УРОВНЯМ КРИТИЧНОСТИ (посты):")
        level_names = {0: "Нет угрозы", 1: "Низкий", 2: "Средний", 3: "Высокий"}
        for level, count in stats['posts_by_level']:
            print(f"   • Уровень {level} ({level_names.get(level, '?')}): {count}")

        print("\n💬 КОММЕНТАРИИ:")
        print("-" * 40)
        for cat, count in stats['comments_by_category']:
            if cat == 'safe':
                print(f"   • Безопасные: {count}")
            else:
                print(f"   • {cat}: {count}")

        print("\n🚨 ТОП-10 ОПАСНЫХ ПОСТОВ:")
        print("-" * 40)
        for i, (post_id, screen_name, text, category, level) in enumerate(stats['dangerous_posts'][:10], 1):
            text_preview = text[:80].replace('\n', ' ') + ('...' if len(text) > 80 else '')
            level_icon = "🔴" if level >= 3 else "🟠" if level >= 2 else "🟡"
            print(f"   {i}. {level_icon} [{category}] @{screen_name}")
            print(f"      {text_preview}")
            print(f"      (пост ID: {post_id})")
            print()

    def run_full_analysis(self, limit: int = 500) -> Dict:
        """Запуск полного анализа"""
        print("\n" + "=" * 70)
        print("🔍 ЗАПУСК АНАЛИЗА ДЕСТРУКТИВНОГО КОНТЕНТА")
        print("=" * 70)

        # Добавляем колонки
        self.add_analysis_columns()

        # Анализируем посты
        analyze_stats = self.analyze_posts(limit=limit)

        # Получаем статистику
        stats = self.get_statistics()

        # Выводим
        self.print_statistics(stats)

        print("\n" + "=" * 70)
        print(f"✅ АНАЛИЗ ЗАВЕРШЁН")
        print(f"   Обработано постов: {analyze_stats['processed']}")
        print("=" * 70)

        return stats