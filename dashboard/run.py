"""
Запуск дашборда
Использование: python dashboard/run.py
или: python -m dashboard.run
"""

import sys
import os
from pathlib import Path

# Добавляем корневую директорию в путь
sys.path.append(str(Path(__file__).parent.parent))

from dashboard.app import app

if __name__ == "__main__":
    print("\n" + "=" * 60)
    print("🛡️  ЗАПУСК DASHBOARD ДЕСТРУКТИВНОГО КОНТЕНТА")
    print("=" * 60)
    print("\n🌐 Открыть в браузере: http://localhost:8050")
    print("\n📊 Доступные разделы:")
    print("   • Общая статистика (посты/комментарии)")
    print("   • Распределение по категориям")
    print("   • Уровни критичности")
    print("   • Динамика активности")
    print("   • Рейтинг опасных категорий")
    print("   • ТОП-20 опасных постов и комментариев")
    print("\n" + "=" * 60)

    app.run(debug=True, host="0.0.0.0", port=8050)