"""
Dash Dashboard для визуализации анализа деструктивного контента
Запуск: python dashboard/app.py

Обновлённая версия:
- сводка по каналу в начале;
- общий вывод о деструктивности сообщества;
- полезные графики без лишнего шума;
- раскрытие полного текста постов и комментариев;
- ссылки на посты / комментарии;
- экспорт выявленных деструктивных постов и комментариев в Excel/JSON.
"""

import sys
import io
import json
from pathlib import Path
from datetime import datetime

# Добавляем корневую директорию в путь
sys.path.append(str(Path(__file__).parent.parent))

import dash
from dash import dcc, html, Input, Output, callback
import plotly.graph_objs as go
import pandas as pd
import psycopg2
from flask import Response
import config


app = dash.Dash(
    __name__,
    title="Анализ деструктивного контента VK",
    update_title="Обновление данных...",
    suppress_callback_exceptions=True
)

server = app.server


COLORS = {
    'primary': '#111827',
    'primary_light': '#374151',
    'danger_high': '#b91c1c',
    'danger_medium': '#b45309',
    'danger_low': '#a16207',
    'safe': '#166534',
    'background': '#f3f4f6',
    'text': '#111827',
    'muted': '#6b7280',
    'info': '#1d4ed8',
    'card': '#ffffff',
    'border': '#d1d5db'
}


CATEGORY_NAMES_RU = {
    'safe': 'Безопасно',
    'aggression': 'Агрессия',
    'suicide': 'Суицидальный контент',
    'suicide_calls': 'Призывы к суициду',
    'hate_speech': 'Язык вражды',
    'extremism': 'Экстремизм',
    'misinformation': 'Дезинформация',
    'manipulation': 'Манипуляция',
    'drugs': 'Наркотики',
    'violence_calls': 'Призывы к насилию',
    'bullying': 'Буллинг',
    'negative': 'Негатив',
    None: 'Не определено'
}


LEVEL_NAMES_RU = {
    0: 'Безопасно',
    1: 'Низкий',
    2: 'Средний',
    3: 'Высокий'
}

LEVEL_ICONS = {
    0: '⚪',
    1: '🟡',
    2: '🟠',
    3: '🔴'
}

LEVEL_COLORS = {
    0: COLORS['safe'],
    1: COLORS['danger_low'],
    2: COLORS['danger_medium'],
    3: COLORS['danger_high']
}


card_style = {
    'backgroundColor': COLORS['card'],
    'borderRadius': '8px',
    'padding': '22px',
    'boxShadow': 'none',
    'border': f"1px solid {COLORS['border']}",
    'marginBottom': '24px'
}

small_card_style = {
    **card_style,
    'marginBottom': '0',
    'textAlign': 'center'
}

button_style = {
    'display': 'inline-block',
    'padding': '10px 14px',
    'borderRadius': '6px',
    'textDecoration': 'none',
    'fontWeight': '700',
    'fontSize': '13px',
    'marginRight': '8px',
    'marginTop': '8px'
}


def get_db_connection():
    """Подключение к БД."""
    try:
        return psycopg2.connect(**config.PG_CONFIG)
    except Exception as e:
        print(f"Ошибка подключения: {e}")
        return None


def read_sql_safe(query: str, conn, default=None):
    """Безопасное чтение SQL в DataFrame."""
    try:
        return pd.read_sql(query, conn)
    except Exception as e:
        print(f"SQL error: {e}\nQUERY:\n{query}")
        return pd.DataFrame() if default is None else default


def ru_category(category):
    return CATEGORY_NAMES_RU.get(category, category or 'Не определено')


def ru_level(level):
    try:
        return LEVEL_NAMES_RU.get(int(level), 'Неизвестно')
    except Exception:
        return 'Неизвестно'


def pct(value, total):
    if not total:
        return 0
    return round(float(value) / float(total) * 100, 1)


def get_status(total_posts, destructive_posts, critical_posts, avg_level):
    """Итоговая оценка сообщества."""
    destructive_ratio = destructive_posts / total_posts if total_posts else 0

    if critical_posts > 0 or destructive_ratio >= 0.30 or avg_level >= 1.8:
        return {
            'label': 'Сообщество потенциально деструктивное',
            'icon': '🚨',
            'color': COLORS['danger_high'],
            'bg': '#fef2f2',
            'description': 'Обнаружена высокая доля деструктивных материалов или критические публикации.'
        }
    if destructive_ratio >= 0.10 or avg_level >= 0.8:
        return {
            'label': 'Сообщество требует внимания',
            'icon': '⚠️',
            'color': COLORS['danger_medium'],
            'bg': '#fffbeb',
            'description': 'Есть заметная доля публикаций с признаками деструктивности.'
        }
    return {
        'label': 'Явных признаков деструктивного сообщества не выявлено',
        'icon': '✅',
        'color': COLORS['safe'],
        'bg': '#f0fdf4',
        'description': 'Деструктивный контент отсутствует или встречается редко.'
    }


def get_statistics_data():
    """Получение всех данных для дашборда."""
    conn = get_db_connection()
    if not conn:
        return {}

    data = {}
    try:
        data['summary'] = read_sql_safe("""
            SELECT
                COALESCE((SELECT screen_name FROM posts WHERE screen_name IS NOT NULL LIMIT 1), '') AS screen_name,
                (SELECT COUNT(*) FROM posts WHERE is_analyzed = TRUE) AS total_posts,
                (SELECT COUNT(*) FROM comments WHERE is_analyzed = TRUE) AS total_comments,
                (SELECT COUNT(*) FROM posts WHERE is_analyzed = TRUE AND destructive_level > 0) AS destructive_posts,
                (SELECT COUNT(*) FROM comments WHERE is_analyzed = TRUE AND destructive_level > 0) AS destructive_comments,
                (SELECT COUNT(*) FROM posts WHERE is_analyzed = TRUE AND destructive_level >= 2) AS dangerous_posts,
                (SELECT COUNT(*) FROM comments WHERE is_analyzed = TRUE AND destructive_level >= 2) AS dangerous_comments,
                (SELECT COUNT(*) FROM posts WHERE is_analyzed = TRUE AND destructive_level = 3) AS critical_posts,
                COALESCE((SELECT ROUND(AVG(destructive_level)::numeric, 2) FROM posts WHERE is_analyzed = TRUE), 0) AS avg_post_level,
                COALESCE((SELECT ROUND(AVG(destructive_confidence)::numeric, 2) FROM posts WHERE is_analyzed = TRUE AND destructive_level > 0), 0) AS avg_confidence
        """, conn)

        data['posts_by_category'] = read_sql_safe("""
            SELECT destructive_category, COUNT(*) AS count,
                   ROUND(AVG(destructive_confidence)::numeric, 2) AS avg_confidence
            FROM posts
            WHERE is_analyzed = TRUE
            GROUP BY destructive_category
            ORDER BY count DESC
        """, conn)

        data['comments_by_category'] = read_sql_safe("""
            SELECT destructive_category, COUNT(*) AS count,
                   ROUND(AVG(destructive_confidence)::numeric, 2) AS avg_confidence
            FROM comments
            WHERE is_analyzed = TRUE
            GROUP BY destructive_category
            ORDER BY count DESC
        """, conn)

        data['content_by_level'] = read_sql_safe("""
            SELECT destructive_level, 'Посты' AS source, COUNT(*) AS count
            FROM posts
            WHERE is_analyzed = TRUE
            GROUP BY destructive_level
            UNION ALL
            SELECT destructive_level, 'Комментарии' AS source, COUNT(*) AS count
            FROM comments
            WHERE is_analyzed = TRUE
            GROUP BY destructive_level
            ORDER BY destructive_level, source
        """, conn)

        data['risk_ratio'] = read_sql_safe("""
            SELECT 'Посты' AS source,
                   COUNT(*) AS total,
                   SUM(CASE WHEN destructive_level > 0 THEN 1 ELSE 0 END) AS destructive,
                   SUM(CASE WHEN destructive_level >= 2 THEN 1 ELSE 0 END) AS dangerous
            FROM posts
            WHERE is_analyzed = TRUE
            UNION ALL
            SELECT 'Комментарии' AS source,
                   COUNT(*) AS total,
                   SUM(CASE WHEN destructive_level > 0 THEN 1 ELSE 0 END) AS destructive,
                   SUM(CASE WHEN destructive_level >= 2 THEN 1 ELSE 0 END) AS dangerous
            FROM comments
            WHERE is_analyzed = TRUE
        """, conn)

        # Новая полезная визуализация: категории риска по постам и комментариям вместе
        data['top_categories_combined'] = read_sql_safe("""
            SELECT destructive_category,
                   SUM(posts_count) AS posts_count,
                   SUM(comments_count) AS comments_count,
                   SUM(posts_count + comments_count) AS total_count
            FROM (
                SELECT destructive_category, COUNT(*) AS posts_count, 0 AS comments_count
                FROM posts
                WHERE is_analyzed = TRUE AND destructive_level > 0
                GROUP BY destructive_category
                UNION ALL
                SELECT destructive_category, 0 AS posts_count, COUNT(*) AS comments_count
                FROM comments
                WHERE is_analyzed = TRUE AND destructive_level > 0
                GROUP BY destructive_category
            ) t
            GROUP BY destructive_category
            ORDER BY total_count DESC
            LIMIT 10
        """, conn)

        data['dangerous_posts'] = read_sql_safe("""
            SELECT post_id, screen_name, text AS full_text, destructive_category,
                   destructive_level, destructive_confidence, destructive_reason,
                   matched_words, likes, comments_count, views, url, date
            FROM posts
            WHERE destructive_level >= 1 AND is_analyzed = TRUE
            ORDER BY destructive_level DESC, destructive_confidence DESC NULLS LAST, date DESC
            LIMIT 30
        """, conn)

        data['dangerous_comments'] = read_sql_safe("""
            SELECT c.comment_id,
                   c.text AS full_text,
                   c.destructive_category,
                   c.destructive_level,
                   c.destructive_confidence,
                   c.destructive_reason,
                   c.matched_words,
                   c.likes,
                   c.date,
                   p.post_id AS post_vk_id,
                   p.url AS post_url,
                   p.screen_name AS post_screen_name
            FROM comments c
            JOIN posts p ON c.post_id = p.id
            WHERE c.destructive_level >= 1 AND c.is_analyzed = TRUE
            ORDER BY c.destructive_level DESC, c.destructive_confidence DESC NULLS LAST, c.date DESC
            LIMIT 30
        """, conn)

    except Exception as e:
        print(f"Ошибка получения данных: {e}")
    finally:
        conn.close()

    return data


def destructive_posts_df():
    conn = get_db_connection()
    if not conn:
        return pd.DataFrame()
    try:
        return read_sql_safe("""
            SELECT post_id, screen_name, text, url, date,
                   destructive_category, destructive_level, destructive_confidence,
                   destructive_reason, matched_words, sentiment_score,
                   views, likes, reposts, comments_count
            FROM posts
            WHERE is_analyzed = TRUE AND destructive_level > 0
            ORDER BY destructive_level DESC, destructive_confidence DESC NULLS LAST, date DESC
        """, conn)
    finally:
        conn.close()


def destructive_comments_df():
    conn = get_db_connection()
    if not conn:
        return pd.DataFrame()
    try:
        return read_sql_safe("""
            SELECT c.comment_id, c.text, c.date,
                   c.destructive_category, c.destructive_level, c.destructive_confidence,
                   c.destructive_reason, c.matched_words, c.sentiment_score,
                   c.likes, p.post_id AS post_vk_id, p.url AS post_url, p.screen_name AS post_screen_name
            FROM comments c
            JOIN posts p ON c.post_id = p.id
            WHERE c.is_analyzed = TRUE AND c.destructive_level > 0
            ORDER BY c.destructive_level DESC, c.destructive_confidence DESC NULLS LAST, c.date DESC
        """, conn)
    finally:
        conn.close()


def dataframe_response(df: pd.DataFrame, filename: str, fmt: str):
    """Формирование файла экспорта: Excel или JSON."""
    export_df = df.copy()

    # Для Excel сразу показываем русские названия категорий и уровней.
    if 'destructive_category' in export_df.columns:
        export_df['category_ru'] = export_df['destructive_category'].apply(ru_category)
    if 'destructive_level' in export_df.columns:
        export_df['level_ru'] = export_df['destructive_level'].apply(ru_level)

    if fmt == 'json':
        payload = export_df.to_json(orient='records', force_ascii=False, date_format='iso')
        return Response(
            payload,
            mimetype='application/json; charset=utf-8',
            headers={'Content-Disposition': f'attachment; filename={filename}.json'}
        )

    if fmt in ('xlsx', 'xls'):
        output = io.BytesIO()
        try:
            with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                export_df.to_excel(writer, sheet_name='data', index=False)
                workbook = writer.book
                worksheet = writer.sheets['data']

                header_format = workbook.add_format({
                    'bold': True,
                    'bg_color': '#111827',
                    'font_color': '#FFFFFF',
                    'border': 1,
                    'align': 'center',
                    'valign': 'vcenter'
                })
                body_format = workbook.add_format({
                    'border': 1,
                    'valign': 'top',
                    'text_wrap': True
                })

                for col_num, value in enumerate(export_df.columns.values):
                    worksheet.write(0, col_num, value, header_format)
                    sample_values = export_df[value].astype(str).head(50).tolist() if not export_df.empty else []
                    max_len = max([len(str(value))] + [len(v) for v in sample_values])
                    width = min(max(max_len + 2, 12), 45)
                    worksheet.set_column(col_num, col_num, width, body_format)
                worksheet.freeze_panes(1, 0)
                worksheet.autofilter(0, 0, max(len(export_df), 1), max(len(export_df.columns) - 1, 0))
        except Exception as e:
            return Response(f'Excel export error: {e}', status=500)

        output.seek(0)
        return Response(
            output.getvalue(),
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            headers={'Content-Disposition': f'attachment; filename={filename}.xlsx'}
        )

    return Response('Unsupported format', status=400)


@server.route('/download/destructive_posts/<fmt>')
def download_posts(fmt):
    if fmt not in ('xlsx', 'xls', 'json'):
        return Response('Unsupported format', status=400)
    return dataframe_response(destructive_posts_df(), 'destructive_posts', fmt)


@server.route('/download/destructive_comments/<fmt>')
def download_comments(fmt):
    if fmt not in ('xlsx', 'xls', 'json'):
        return Response('Unsupported format', status=400)
    return dataframe_response(destructive_comments_df(), 'destructive_comments', fmt)


app.layout = html.Div([
    html.Div([
        html.Div([
            html.H1("Анализ деструктивного контента", style={
                'color': 'white', 'margin': 0, 'fontSize': '30px', 'fontWeight': 800
            }),
            html.P("ВКонтакте | Мониторинг сообщества и выявление рисков", style={
                'color': '#d6dde5', 'margin': '6px 0 0 0', 'fontSize': '15px'
            })
        ], style={'display': 'inline-block'}),

        html.Div([
            html.Button("🔄 Обновить", id="refresh-btn", style={
                'backgroundColor': COLORS['primary_light'], 'color': 'white', 'border': '1px solid #4b5563',
                'padding': '11px 22px', 'borderRadius': '6px', 'cursor': 'pointer',
                'fontSize': '14px', 'fontWeight': '700', 'marginRight': '12px'
            }),
            html.Span(id="update-time", style={'color': '#d6dde5', 'fontSize': '12px'})
        ], style={'float': 'right', 'marginTop': '10px'})
    ], style={
        'backgroundColor': COLORS['primary'],
        'padding': '24px 30px', 'borderRadius': '8px', 'marginBottom': '26px',
        'overflow': 'hidden', 'boxShadow': 'none', 'border': '1px solid #111827'
    }),

    html.Div(id="dashboard-content", children=[
        html.Div([
            html.Div("📊", style={'fontSize': '48px', 'marginBottom': '16px'}),
            html.H3("Загрузка данных...", style={'color': COLORS['primary']}),
        ], style={'textAlign': 'center', 'padding': '50px'})
    ])
], style={
    'fontFamily': '-apple-system, BlinkMacSystemFont, "Segoe UI", Arial, sans-serif',
    'backgroundColor': COLORS['background'], 'minHeight': '100vh', 'padding': '22px'
})


@callback(
    [Output("dashboard-content", "children"), Output("update-time", "children")],
    Input("refresh-btn", "n_clicks"),
    prevent_initial_call=False
)
def update_dashboard(n_clicks):
    data = get_statistics_data()
    update_time = f"Обновлено: {datetime.now().strftime('%H:%M:%S')}"

    if not data or data.get('summary', pd.DataFrame()).empty:
        return empty_state(), update_time

    summary = data['summary'].iloc[0]
    total_posts = int(summary.get('total_posts') or 0)
    total_comments = int(summary.get('total_comments') or 0)

    if total_posts == 0 and total_comments == 0:
        return empty_state(), update_time

    return html.Div([
        create_summary_block(summary),

        html.Div([
            html.Div([
                html.H3("Распределение деструктивности в постах", style=section_title_style()),
                dcc.Graph(figure=create_category_chart(data['posts_by_category']), config={'displayModeBar': False})
            ], style={'flex': '1', **card_style}),
            html.Div([
                html.H3("Распределение деструктивности в комментариях", style=section_title_style()),
                dcc.Graph(figure=create_category_chart(data['comments_by_category']), config={'displayModeBar': False})
            ], style={'flex': '1', **card_style}),
        ], style={'display': 'grid', 'gridTemplateColumns': 'repeat(2, minmax(0, 1fr))', 'gap': '24px'}),

        html.Div([
            html.Div([
                html.H3("Уровни критичности", style=section_title_style()),
                dcc.Graph(figure=create_level_chart(data['content_by_level']), config={'displayModeBar': False})
            ], style={'flex': '1', **card_style}),
            html.Div([
                html.H3("Доля выявленного деструктивного контента", style=section_title_style()),
                dcc.Graph(figure=create_risk_ratio_chart(data['risk_ratio']), config={'displayModeBar': False})
            ], style={'flex': '1', **card_style}),
        ], style={'display': 'grid', 'gridTemplateColumns': 'repeat(2, minmax(0, 1fr))', 'gap': '24px'}),

        html.Div([
            html.H3("Наиболее частые деструктивные категории", style=section_title_style()),
            dcc.Graph(figure=create_combined_categories_chart(data['top_categories_combined']), config={'displayModeBar': False})
        ], style=card_style),

        html.Div([
            html.Div([
                html.H3("Топ выявленных деструктивных постов", style={**section_title_style(), 'color': COLORS['danger_high']}),
                html.P("Показаны публикации с уровнем выше 0, отсортированные по критичности и уверенности.", style=muted_text_style()),
            ]),
            create_posts_table(data['dangerous_posts'])
        ], style=card_style),

        html.Div([
            html.Div([
                html.H3("Топ выявленных деструктивных комментариев", style={**section_title_style(), 'color': COLORS['danger_medium']}),
                html.P("Автор комментария скрыт, так как в текущей структуре БД хранится screen_name паблика, а не имя комментатора.", style=muted_text_style()),
            ]),
            create_comments_table(data['dangerous_comments'])
        ], style=card_style),
    ]), update_time


def empty_state():
    return html.Div([
        html.Div("📭", style={'fontSize': '64px', 'marginBottom': '20px'}),
        html.H3("Нет данных для отображения", style={'color': COLORS['danger_medium'], 'textAlign': 'center'}),
        html.P("Сначала запустите сбор и анализ данных:", style={'textAlign': 'center', 'color': COLORS['muted']}),
        html.Pre("python main.py\npython analyze_main.py", style={
            'textAlign': 'left', 'backgroundColor': COLORS['primary'], 'color': '#ecf0f1',
            'padding': '14px', 'borderRadius': '6px', 'display': 'inline-block'
        })
    ], style={'textAlign': 'center', 'padding': '55px', **card_style})


def section_title_style():
    return {'color': COLORS['primary'], 'margin': '0 0 16px 0', 'fontSize': '20px', 'fontWeight': 800}


def muted_text_style():
    return {'color': COLORS['muted'], 'fontSize': '13px', 'margin': '0 0 14px 0'}


def create_summary_block(summary):
    screen_name = summary.get('screen_name') or ''
    channel_url = f"https://vk.com/{screen_name}" if screen_name else None

    total_posts = int(summary.get('total_posts') or 0)
    total_comments = int(summary.get('total_comments') or 0)
    destructive_posts = int(summary.get('destructive_posts') or 0)
    destructive_comments = int(summary.get('destructive_comments') or 0)
    dangerous_posts = int(summary.get('dangerous_posts') or 0)
    dangerous_comments = int(summary.get('dangerous_comments') or 0)
    critical_posts = int(summary.get('critical_posts') or 0)
    avg_level = float(summary.get('avg_post_level') or 0)
    avg_confidence = float(summary.get('avg_confidence') or 0)

    status = get_status(total_posts, destructive_posts, critical_posts, avg_level)

    return html.Div([
        html.Div([
            html.Div([
                html.Div("Сводка по каналу", style={'fontSize': '22px', 'fontWeight': 800, 'color': COLORS['primary']}),
                html.Div([
                    html.Span("Сообщество: ", style={'fontWeight': 700}),
                    html.A(channel_url, href=channel_url, target='_blank', style={'color': COLORS['info'], 'fontWeight': 700})
                    if channel_url else html.Span("не определено", style={'color': COLORS['muted']})
                ], style={'marginTop': '8px', 'fontSize': '15px'})
            ]),
            html.Div([
                html.Div(status['icon'], style={'fontSize': '34px', 'marginRight': '14px'}),
                html.Div([
                    html.Div(status['label'], style={'fontWeight': 800, 'color': status['color'], 'fontSize': '18px'}),
                    html.Div(status['description'], style={'color': COLORS['muted'], 'fontSize': '13px', 'marginTop': '4px'})
                ])
            ], style={
                'display': 'flex', 'alignItems': 'center', 'backgroundColor': status['bg'],
                'border': f"1px solid {status['color']}", 'borderRadius': '8px', 'padding': '14px 16px'
            })
        ], style={'display': 'grid', 'gridTemplateColumns': '1.1fr 1.4fr', 'gap': '22px', 'marginBottom': '22px'}),

        html.Div([
            metric_card('📝', total_posts, 'Постов проанализировано'),
            metric_card('💬', total_comments, 'Комментариев проанализировано'),
            metric_card('⚠️', destructive_posts, f"Деструктивных постов ({pct(destructive_posts, total_posts)}%)", COLORS['danger_medium']),
            metric_card('🚩', destructive_comments, f"Деструктивных комментариев ({pct(destructive_comments, total_comments)}%)", COLORS['danger_medium']),
            metric_card('🔴', dangerous_posts + dangerous_comments, 'Опасных объектов уровня 2–3', COLORS['danger_high']),
            metric_card('🎯', f"{avg_confidence:.2f}", 'Средняя уверенность'),
        ], style={'display': 'grid', 'gridTemplateColumns': 'repeat(6, minmax(0, 1fr))', 'gap': '14px'}),

        html.Div([
            html.Div('Экспорт выявленных деструктивных материалов', style={'fontWeight': 800, 'fontSize': '14px', 'color': COLORS['primary'], 'marginBottom': '6px'}),
            create_download_buttons('posts'),
            create_download_buttons('comments')
        ], style={'marginTop': '18px', 'borderTop': f"1px solid {COLORS['border']}", 'paddingTop': '14px'})
    ], style=card_style)


def metric_card(icon, value, label, color=None):
    color = color or COLORS['primary']
    return html.Div([
        html.Div(icon, style={'fontSize': '24px', 'marginBottom': '7px'}),
        html.Div(f"{value:,}" if isinstance(value, int) else value, style={'fontSize': '24px', 'fontWeight': 900, 'color': color}),
        html.Div(label, style={'fontSize': '12px', 'color': COLORS['muted'], 'marginTop': '4px', 'lineHeight': '1.25'})
    ], style={
        'backgroundColor': '#f8fafc', 'border': f"1px solid {COLORS['border']}",
        'borderRadius': '8px', 'padding': '14px 10px', 'textAlign': 'center'
    })


def create_download_buttons(kind):
    if kind == 'posts':
        label = 'посты'
        base = '/download/destructive_posts'
        color = COLORS['danger_high']
    else:
        label = 'комментарии'
        base = '/download/destructive_comments'
        color = COLORS['danger_medium']

    return html.Div([
        html.A(f"Скачать {label} XLSX", href=f"{base}/xlsx", target='_blank', style={
            **button_style, 'backgroundColor': COLORS['primary'], 'color': 'white', 'border': '1px solid #111827'
        }),
        html.A(f"Скачать {label} JSON", href=f"{base}/json", target='_blank', style={
            **button_style, 'backgroundColor': '#ffffff', 'color': COLORS['primary'], 'border': f"1px solid {COLORS['border']}"
        })
    ], style={'display': 'inline-block', 'marginRight': '12px'})


def category_colors(categories):
    colors = []
    for cat in categories:
        if cat == 'safe':
            colors.append(COLORS['safe'])
        elif cat in ['extremism', 'suicide', 'suicide_calls', 'violence_calls']:
            colors.append(COLORS['danger_high'])
        elif cat in ['aggression', 'hate_speech', 'bullying', 'drugs']:
            colors.append(COLORS['danger_medium'])
        else:
            colors.append(COLORS['danger_low'])
    return colors


def create_category_chart(df):
    if df.empty:
        return empty_figure('Нет данных')

    df = df.copy()
    df['display_name'] = df['destructive_category'].apply(ru_category)

    fig = go.Figure(data=[go.Pie(
        labels=df['display_name'],
        values=df['count'],
        hole=0.52,
        marker_colors=category_colors(df['destructive_category']),
        textinfo='label+percent',
        textposition='auto',
        hovertemplate='<b>%{label}</b><br>Количество: %{value}<br>Доля: %{percent}<extra></extra>'
    )])
    fig.update_layout(
        height=390, showlegend=False, margin=dict(l=15, r=15, t=25, b=15),
        paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)'
    )
    return fig


def create_level_chart(df):
    if df.empty:
        return empty_figure('Нет данных')

    df = df.copy()
    df['level_name'] = df['destructive_level'].apply(lambda x: f"{LEVEL_ICONS.get(int(x), '⚪')} {ru_level(x)}")

    fig = go.Figure()
    for source in ['Посты', 'Комментарии']:
        sub = df[df['source'] == source]
        fig.add_trace(go.Bar(
            x=sub['level_name'], y=sub['count'], name=source,
            text=sub['count'], textposition='auto',
            marker_color=COLORS['primary'] if source == 'Посты' else COLORS['info'],
            hovertemplate=f'<b>{source}</b><br>%{{x}}<br>Количество: %{{y}}<extra></extra>'
        ))

    fig.update_layout(
        height=390, barmode='group', xaxis_title='Уровень критичности', yaxis_title='Количество',
        legend=dict(orientation='h', y=1.08, x=0), margin=dict(l=20, r=20, t=45, b=20),
        paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)'
    )
    return fig


def create_risk_ratio_chart(df):
    if df.empty:
        return empty_figure('Нет данных')

    df = df.copy()
    df['safe'] = df['total'] - df['destructive']
    df['destructive_pct'] = df.apply(lambda r: pct(r['destructive'], r['total']), axis=1)
    df['dangerous_pct'] = df.apply(lambda r: pct(r['dangerous'], r['total']), axis=1)

    fig = go.Figure()
    fig.add_trace(go.Bar(
        y=df['source'], x=df['safe'], name='Безопасно', orientation='h', marker_color=COLORS['safe'],
        hovertemplate='<b>%{y}</b><br>Безопасно: %{x}<extra></extra>'
    ))
    fig.add_trace(go.Bar(
        y=df['source'], x=df['destructive'], name='Деструктивно', orientation='h', marker_color=COLORS['danger_medium'],
        text=[f"{v}%" for v in df['destructive_pct']], textposition='auto',
        hovertemplate='<b>%{y}</b><br>Деструктивно: %{x}<extra></extra>'
    ))

    fig.update_layout(
        height=390, barmode='stack', xaxis_title='Количество', yaxis_title='',
        legend=dict(orientation='h', y=1.08, x=0), margin=dict(l=20, r=20, t=45, b=20),
        paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)'
    )
    return fig


def create_combined_categories_chart(df):
    if df.empty:
        return empty_figure('Деструктивные категории не найдены')

    df = df.copy().sort_values('total_count', ascending=True)
    df['display_name'] = df['destructive_category'].apply(ru_category)

    fig = go.Figure()
    fig.add_trace(go.Bar(
        y=df['display_name'], x=df['posts_count'], name='Посты', orientation='h', marker_color=COLORS['danger_high'],
        hovertemplate='<b>%{y}</b><br>Постов: %{x}<extra></extra>'
    ))
    fig.add_trace(go.Bar(
        y=df['display_name'], x=df['comments_count'], name='Комментарии', orientation='h', marker_color=COLORS['danger_medium'],
        hovertemplate='<b>%{y}</b><br>Комментариев: %{x}<extra></extra>'
    ))
    fig.update_layout(
        height=420, barmode='stack', xaxis_title='Количество выявлений', yaxis_title='',
        legend=dict(orientation='h', y=1.06, x=0), margin=dict(l=20, r=20, t=45, b=20),
        paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)'
    )
    return fig


def empty_figure(message):
    fig = go.Figure()
    fig.add_annotation(text=message, showarrow=False, x=0.5, y=0.5, font=dict(size=16, color=COLORS['muted']))
    fig.update_layout(height=360, xaxis={'visible': False}, yaxis={'visible': False},
                      paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)')
    return fig


def badge(text, color):
    return html.Span(text, style={
        'display': 'inline-block', 'backgroundColor': color, 'color': 'white',
        'padding': '4px 8px', 'borderRadius': '4px', 'fontSize': '12px', 'fontWeight': 800
    })


def details_text(summary_label, full_text):
    full_text = full_text or ''
    preview = full_text.replace('\n', ' ')
    if len(preview) > 120:
        preview = preview[:120] + '…'

    return html.Details([
        html.Summary(summary_label, style={
            'cursor': 'pointer', 'fontWeight': 800, 'color': COLORS['info'], 'marginBottom': '8px'
        }),
        html.Div(full_text, style={
            'whiteSpace': 'pre-wrap', 'lineHeight': '1.45', 'fontSize': '13px', 'color': '#394b59',
            'backgroundColor': '#f8fafc', 'border': f"1px solid {COLORS['border']}",
            'borderRadius': '6px', 'padding': '12px', 'maxWidth': '780px'
        })
    ])


def create_posts_table(df):
    if df.empty:
        return html.Div("✅ Деструктивных постов не обнаружено", style={
            'textAlign': 'center', 'padding': '30px', 'color': COLORS['safe'], 'fontWeight': 800
        })

    cards = []
    for i, row in df.iterrows():
        level = int(row['destructive_level'] or 0)
        confidence = row['destructive_confidence'] if pd.notna(row['destructive_confidence']) else 0
        url = row.get('url') or '#'
        date_text = row['date'].strftime('%d.%m.%Y %H:%M') if hasattr(row.get('date'), 'strftime') else str(row.get('date') or '')
        reason = row.get('destructive_reason') or 'Причина не указана'
        matched = row.get('matched_words') or '—'

        cards.append(html.Div([
            html.Div([
                html.Div([
                    html.Span(f"#{len(cards)+1}", style={'fontWeight': 900, 'marginRight': '8px'}),
                    html.Span(LEVEL_ICONS.get(level, '⚪'), style={'fontSize': '20px', 'marginRight': '8px'}),
                    badge(ru_category(row['destructive_category']), LEVEL_COLORS.get(level, COLORS['danger_low'])),
                    html.Span(f"Уровень: {ru_level(level)}", style={'marginLeft': '10px', 'fontWeight': 700}),
                    html.Span(f"Уверенность: {confidence * 100:.0f}%", style={'marginLeft': '10px', 'color': COLORS['muted']})
                ]),
                html.A("🔗 Открыть пост", href=url, target='_blank', style={
                    'color': COLORS['info'], 'fontWeight': 800, 'textDecoration': 'none'
                })
            ], style={'display': 'flex', 'justifyContent': 'space-between', 'gap': '12px', 'alignItems': 'center'}),

            html.Div([
                html.Span(f"@{row.get('screen_name') or 'unknown'}", style={'fontWeight': 800}),
                html.Span(f" • {date_text}", style={'color': COLORS['muted']}),
                html.Span(f" • ❤️ {int(row['likes'] or 0)}", style={'color': COLORS['muted']}),
                html.Span(f" • 💬 {int(row['comments_count'] or 0)}", style={'color': COLORS['muted']}),
                html.Span(f" • 👁️ {int(row['views'] or 0)}", style={'color': COLORS['muted']})
            ], style={'fontSize': '13px', 'marginTop': '10px'}),

            html.Div([
                html.Div(f"Причина: {reason}", style={'marginBottom': '4px'}),
                html.Div(f"Маркеры: {matched}", style={'color': COLORS['muted']})
            ], style={'fontSize': '13px', 'marginTop': '10px'}),

            html.Div(details_text('▸ Развернуть полный текст поста', row.get('full_text')), style={'marginTop': '12px'})
        ], style={
            'border': f"1px solid {COLORS['border']}", 'borderLeft': f"5px solid {LEVEL_COLORS.get(level, COLORS['danger_low'])}",
            'borderRadius': '8px', 'padding': '16px', 'marginBottom': '14px', 'backgroundColor': '#fff'
        }))

    return html.Div(cards)


def create_comments_table(df):
    if df.empty:
        return html.Div("✅ Деструктивных комментариев не обнаружено", style={
            'textAlign': 'center', 'padding': '30px', 'color': COLORS['safe'], 'fontWeight': 800
        })

    cards = []
    for _, row in df.iterrows():
        level = int(row['destructive_level'] or 0)
        confidence = row['destructive_confidence'] if pd.notna(row['destructive_confidence']) else 0
        post_url = row.get('post_url') or '#'
        comment_url = f"{post_url}?reply={int(row['comment_id'])}" if post_url != '#' and pd.notna(row.get('comment_id')) else post_url
        date_text = row['date'].strftime('%d.%m.%Y %H:%M') if hasattr(row.get('date'), 'strftime') else str(row.get('date') or '')
        reason = row.get('destructive_reason') or 'Причина не указана'
        matched = row.get('matched_words') or '—'

        cards.append(html.Div([
            html.Div([
                html.Div([
                    html.Span(f"#{len(cards)+1}", style={'fontWeight': 900, 'marginRight': '8px'}),
                    html.Span(LEVEL_ICONS.get(level, '⚪'), style={'fontSize': '20px', 'marginRight': '8px'}),
                    badge(ru_category(row['destructive_category']), LEVEL_COLORS.get(level, COLORS['danger_low'])),
                    html.Span(f"Уровень: {ru_level(level)}", style={'marginLeft': '10px', 'fontWeight': 700}),
                    html.Span(f"Уверенность: {confidence * 100:.0f}%", style={'marginLeft': '10px', 'color': COLORS['muted']})
                ]),
                html.Div([
                    html.A("🔗 Открыть комментарий", href=comment_url, target='_blank', style={
                        'color': COLORS['info'], 'fontWeight': 800, 'textDecoration': 'none', 'marginRight': '12px'
                    }),
                    html.A("Пост", href=post_url, target='_blank', style={
                        'color': COLORS['muted'], 'fontWeight': 700, 'textDecoration': 'none'
                    })
                ])
            ], style={'display': 'flex', 'justifyContent': 'space-between', 'gap': '12px', 'alignItems': 'center'}),

            html.Div([
                html.Span(f"Пост VK ID: {row.get('post_vk_id') or '—'}", style={'fontWeight': 700}),
                html.Span(f" • {date_text}", style={'color': COLORS['muted']}),
                html.Span(f" • ❤️ {int(row['likes'] or 0)}", style={'color': COLORS['muted']})
            ], style={'fontSize': '13px', 'marginTop': '10px'}),

            html.Div([
                html.Div(f"Причина: {reason}", style={'marginBottom': '4px'}),
                html.Div(f"Маркеры: {matched}", style={'color': COLORS['muted']})
            ], style={'fontSize': '13px', 'marginTop': '10px'}),

            html.Div(details_text('▸ Развернуть полный текст комментария', row.get('full_text')), style={'marginTop': '12px'})
        ], style={
            'border': f"1px solid {COLORS['border']}", 'borderLeft': f"5px solid {LEVEL_COLORS.get(level, COLORS['danger_low'])}",
            'borderRadius': '8px', 'padding': '16px', 'marginBottom': '14px', 'backgroundColor': '#fff'
        }))

    return html.Div(cards)


if __name__ == "__main__":
    print("=" * 60)
    print("🛡️  ЗАПУСК DASHBOARD АНАЛИЗА ДЕСТРУКТИВНОГО КОНТЕНТА")
    print("=" * 60)
    print("\n📊 Дашборд доступен по адресу: http://localhost:8050")
    print("\n⚠️ Требования:")
    print("   1. PostgreSQL запущен")
    print("   2. Данные собраны (python main.py)")
    print("   3. Анализ выполнен (python analyze_main.py)")
    print("\n💡 Для остановки нажмите Ctrl+C")
    print("=" * 60)

    app.run(debug=True, host="0.0.0.0", port=8050)
