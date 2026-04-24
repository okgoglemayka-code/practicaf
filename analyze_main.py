"""
analyze_main.py - Запуск анализа деструктивного контента
"""

import sys
import os

# Добавляем текущую директорию в путь
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from analysis.analyzer import DataAnalyzer


def main():
    print("=" * 70)
    print("🛡️  АНАЛИЗ ДЕСТРУКТИВНОГО КОНТЕНТА В ВКОНТАКТЕ")
    print("=" * 70)
    print()
    print("Выберите действие:")
    print("  1. Полный анализ (посты + комментарии)")
    print("  2. Только посты")
    print("  3. Только комментарии")
    print("  4. Показать статистику")
    print("  5. Экспорт опасных постов")
    print()

    choice = input("Ваш выбор (1-5): ").strip()

    analyzer = DataAnalyzer()

    if not analyzer.connect():
        print("❌ Не удалось подключиться к БД")
        return

    if choice == '1':
        # Полный анализ
        limit = int(input("Максимум постов для анализа (по умолч. 500): ").strip() or "500")
        analyzer.run_full_analysis(limit=limit)

    elif choice == '2':
        # Только посты
        analyzer.add_analysis_columns()
        limit = int(input("Максимум постов (по умолч. 500): ").strip() or "500")
        stats = analyzer.analyze_posts(limit=limit)
        print(f"\n✅ Проанализировано постов: {stats['processed']}")

    elif choice == '3':
        # Только комментарии
        analyzer.add_analysis_columns()
        analyzer._analyze_comments_for_analyzed_posts()
        print("✅ Анализ комментариев завершён")

    elif choice == '4':
        # Статистика
        stats = analyzer.get_statistics()
        analyzer.print_statistics(stats)

    elif choice == '5':
        # Экспорт опасных постов
        analyzer.cur.execute("""
            SELECT post_id, screen_name, text, url, destructive_category, destructive_level, destructive_confidence
            FROM posts
            WHERE destructive_level >= 2
            ORDER BY destructive_level DESC
        """)
        dangerous = analyzer.cur.fetchall()

        if dangerous:
            import csv
            with open('dangerous_posts.csv', 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow(['post_id', 'screen_name', 'text', 'url', 'category', 'level', 'confidence'])
                writer.writerows(dangerous)
            print(f"✅ Экспортировано {len(dangerous)} опасных постов в dangerous_posts.csv")
        else:
            print("⚠️ Опасных постов не найдено")

    analyzer.disconnect()


if __name__ == "__main__":
    main()