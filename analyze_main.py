"""
analyze_main.py - Запуск анализа деструктивного контента
"""

import sys
import os
import json
import csv
from datetime import datetime

# Добавляем текущую директорию в путь
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from analysis.analyzer import DataAnalyzer


def print_menu():
    """Вывод главного меню"""
    print("\n" + "=" * 70)
    print("🛡️  АНАЛИЗ ДЕСТРУКТИВНОГО КОНТЕНТА В ВКОНТАКТЕ")
    print("=" * 70)
    print()
    print("  📊 1. Запустить полный анализ (посты + комментарии)")
    print("  📈 2. Показать статистику")
    print("  📤 3. Экспорт результатов")
    print("  🚪 0. Выход")
    print()
    print("=" * 70)


def print_export_menu():
    """Вывод меню экспорта"""
    print("\n" + "-" * 40)
    print("📤 ЭКСПОРТ РЕЗУЛЬТАТОВ")
    print("-" * 40)
    print("  1. Экспорт всех деструктивных постов (CSV)")
    print("  2. Экспорт всех деструктивных комментариев (CSV)")
    print("  3. Экспорт сводной статистики (JSON)")
    print("  4. Экспорт отчёта по категориям (TXT)")
    print("  5. Экспорт опасных постов (уровень 2-3) (CSV)")
    print("  . Назад")
    print("-" * 40)


def export_to_csv(data, filename, headers):
    """Экспорт в CSV"""
    with open(filename, 'w', newline='', encoding='utf-8-sig') as f:
        writer = csv.writer(f)
        writer.writerow(headers)
        writer.writerows(data)
    print(f"   ✅ Экспортировано в {filename}")


def export_to_json(data, filename):
    """Экспорт в JSON"""
    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2, default=str)
    print(f"   ✅ Экспортировано в {filename}")


def export_to_txt(content, filename):
    """Экспорт в TXT"""
    with open(filename, 'w', encoding='utf-8') as f:
        f.write(content)
    print(f"   ✅ Экспортировано в {filename}")


def run_exports(analyzer):
    """Обработка экспорта"""
    while True:
        print_export_menu()
        choice = input("\n👉 Ваш выбор: ").strip()

        if choice == '0':
            break

        elif choice == '1':
            # Экспорт всех деструктивных постов в CSV
            analyzer.cur.execute("""
                SELECT post_id, screen_name, text, url, date, 
                       destructive_category, destructive_level, destructive_confidence,
                       views, likes, reposts, comments_count
                FROM posts
                WHERE destructive_level > 0 AND is_analyzed = TRUE
                ORDER BY destructive_level DESC, destructive_confidence DESC
            """)
            data = analyzer.cur.fetchall()
            if data:
                filename = f"export_destructive_posts_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
                headers = ['post_id', 'screen_name', 'text', 'url', 'date',
                          'category', 'level', 'confidence', 'views', 'likes', 'reposts', 'comments']
                export_to_csv(data, filename, headers)
            else:
                print("   ⚠️ Деструктивных постов не найдено")

        elif choice == '2':
            # Экспорт всех деструктивных комментариев в CSV
            analyzer.cur.execute("""
                SELECT c.comment_id, c.screen_name, c.text, c.date,
                       c.destructive_category, c.destructive_level, c.destructive_confidence,
                       c.likes, p.post_id as post_vk_id
                FROM comments c
                JOIN posts p ON c.post_id = p.id
                WHERE c.destructive_level > 0 AND c.is_analyzed = TRUE
                ORDER BY c.destructive_level DESC, c.destructive_confidence DESC
            """)
            data = analyzer.cur.fetchall()
            if data:
                filename = f"export_destructive_comments_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
                headers = ['comment_id', 'screen_name', 'text', 'date',
                          'category', 'level', 'confidence', 'likes', 'post_vk_id']
                export_to_csv(data, filename, headers)
            else:
                print("   ⚠️ Деструктивных комментариев не найдено")

        elif choice == '3':
            # Экспорт сводной статистики в JSON
            stats = analyzer.get_statistics()

            # Преобразуем данные для JSON
            export_data = {
                "export_date": datetime.now().isoformat(),
                "posts": {
                    "by_category": [(cat, int(count), float(conf) if conf else 0)
                                   for cat, count, conf in stats['posts_by_category']],
                    "by_level": [(int(level), int(count)) for level, count in stats['posts_by_level']]
                },
                "comments": {
                    "by_category": [(cat, int(count)) for cat, count in stats['comments_by_category']]
                }
            }

            filename = f"export_statistics_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            export_to_json(export_data, filename)

        elif choice == '4':
            # Экспорт отчёта по категориям в TXT
            stats = analyzer.get_statistics()

            report = []
            report.append("=" * 70)
            report.append("ОТЧЁТ ПО АНАЛИЗУ ДЕСТРУКТИВНОГО КОНТЕНТА")
            report.append(f"Дата: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            report.append("=" * 70)

            report.append("\n📝 ПОСТЫ ПО КАТЕГОРИЯМ:")
            for cat, count, conf in stats['posts_by_category']:
                report.append(f"   • {cat}: {count} (сред. уверенность: {conf})")

            report.append("\n⚠️ ПОСТЫ ПО УРОВНЯМ КРИТИЧНОСТИ:")
            level_names = {0: "Нет угрозы", 1: "Низкий", 2: "Средний", 3: "Высокий"}
            for level, count in stats['posts_by_level']:
                report.append(f"   • Уровень {level} ({level_names.get(level, '?')}): {count}")

            report.append("\n💬 КОММЕНТАРИИ ПО КАТЕГОРИЯМ:")
            for cat, count in stats['comments_by_category']:
                report.append(f"   • {cat}: {count}")

            # Добавляем топ опасных постов
            analyzer.cur.execute("""
                SELECT post_id, screen_name, text, destructive_category, destructive_level
                FROM posts
                WHERE destructive_level >= 2
                ORDER BY destructive_level DESC
                LIMIT 15
            """)
            dangerous = analyzer.cur.fetchall()

            if dangerous:
                report.append("\n🚨 ТОП-15 ОПАСНЫХ ПОСТОВ:")
                for i, (post_id, screen_name, text, category, level) in enumerate(dangerous, 1):
                    text_preview = (text[:100] if text else '').replace('\n', ' ')
                    if len(text) > 100:
                        text_preview += "..."
                    report.append(f"\n   {i}. [{category}] уровень {level}")
                    report.append(f"      @{screen_name}")
                    report.append(f"      {text_preview}")

            filename = f"export_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
            export_to_txt('\n'.join(report), filename)

        elif choice == '5':
            # Экспорт опасных постов (уровень 2 и 3)
            analyzer.cur.execute("""
                SELECT post_id, screen_name, text, url, date,
                       destructive_category, destructive_level, destructive_confidence,
                       views, likes, reposts
                FROM posts
                WHERE destructive_level >= 2 AND is_analyzed = TRUE
                ORDER BY destructive_level DESC, destructive_confidence DESC
            """)
            data = analyzer.cur.fetchall()
            if data:
                filename = f"export_dangerous_posts_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
                headers = ['post_id', 'screen_name', 'text', 'url', 'date',
                          'category', 'level', 'confidence', 'views', 'likes', 'reposts']
                export_to_csv(data, filename, headers)
            else:
                print("   ⚠️ Опасных постов (уровень 2-3) не найдено")

        else:
            print("   ❌ Неверный выбор")

        input("\n   Нажмите Enter для продолжения...")


def main():
    analyzer = DataAnalyzer()

    if not analyzer.connect():
        print("❌ Не удалось подключиться к БД")
        return

    while True:
        print_menu()
        choice = input("👉 Ваш выбор: ").strip()

        if choice == '0':
            print("\n👋 До свидания!")
            break

        elif choice == '1':
            # Полный анализ
            print("\n" + "-" * 40)
            limit = input("Максимум постов для анализа (Enter = 500): ").strip()
            limit = int(limit) if limit else 500

            analyzer.run_full_analysis(limit=limit)
            input("\n   Нажмите Enter для продолжения...")

        elif choice == '2':
            # Показать статистику
            stats = analyzer.get_statistics()
            analyzer.print_statistics(stats)
            input("\n   Нажмите Enter для продолжения...")

        elif choice == '3':
            # Экспорт результатов
            run_exports(analyzer)

        else:
            print("❌ Неверный выбор. Попробуйте снова.")

    analyzer.disconnect()


if __name__ == "__main__":
    main()