"""
main.py - Главный файл запуска
"""

from db_saver import load_community_data
import config


def main():
    print("=" * 70)
    print("🛡️  АНАЛИЗ ДЕСТРУКТИВНОГО КОНТЕНТА В ВКОНТАКТЕ")
    print("=" * 70)
    print("\nПрограмма собирает посты и комментарии из указанного паблика")
    print("и сохраняет их в PostgreSQL.\n")

    result = load_community_data(
        community_url=None,  # None = запросить у пользователя
        max_posts=config.MAX_POSTS,
        max_comments=config.MAX_COMMENTS
    )

    if not result:
        print("\n❌ ОШИБКА! Проверьте:")
        print("   1. Токен VK API (в config.py)")
        print("   2. Подключение к PostgreSQL")
        print("   3. Правильность ссылки на паблик")


if __name__ == "__main__":
    main()