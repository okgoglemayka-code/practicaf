"""
Dash Dashboard для визуализации анализа деструктивного контента
Запуск: python dashboard/app.py
"""

import sys
import os
from pathlib import Path

# Добавляем корневую директорию в путь
sys.path.append(str(Path(__file__).parent.parent))

import dash
from dash import dcc, html, Input, Output, callback
import plotly.graph_objs as go
import plotly.express as px
import pandas as pd
import psycopg2
from datetime import datetime
import config

# Настройка приложения
app = dash.Dash(
    __name__,
    title="Анализ деструктивного контента VK",
    update_title="Обновление данных...",
    suppress_callback_exceptions=True
)

server = app.server

# Цветовая схема
COLORS = {
    'primary': '#2c3e50',
    'danger_high': '#e74c3c',
    'danger_medium': '#e67e22',
    'danger_low': '#f39c12',
    'safe': '#27ae60',
    'background': '#ecf0f1',
    'text': '#2c3e50',
    'info': '#3498db'
}

# Категории для отображения
CATEGORY_NAMES_RU = {
    'safe': 'Безопасно',
    'aggression': 'Агрессия',
    'suicide': 'Суицидальные',
    'hate_speech': 'Язык вражды',
    'extremism': 'Экстремизм',
    'misinformation': 'Дезинформация',
    'manipulation': 'Манипуляция',
    'negative': 'Негатив'
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


def get_db_connection():
    """Подключение к БД"""
    try:
        conn = psycopg2.connect(**config.PG_CONFIG)
        return conn
    except Exception as e:
        print(f"Ошибка подключения: {e}")
        return None


def get_statistics_data():
    """Получение всех данных для дашборда"""
    conn = get_db_connection()
    if not conn:
        return {}

    data = {}

    try:
        # 1. Посты по категориям
        posts_cat_df = pd.read_sql("""
            SELECT 
                destructive_category,
                COUNT(*) as count,
                ROUND(AVG(destructive_confidence)::numeric, 2) as avg_confidence
            FROM posts
            WHERE is_analyzed = TRUE
            GROUP BY destructive_category
            ORDER BY count DESC
        """, conn)
        data['posts_by_category'] = posts_cat_df

        # 2. Посты по уровням
        posts_level_df = pd.read_sql("""
            SELECT 
                destructive_level,
                COUNT(*) as count
            FROM posts
            WHERE is_analyzed = TRUE
            GROUP BY destructive_level
            ORDER BY destructive_level
        """, conn)
        data['posts_by_level'] = posts_level_df

        # 3. Комментарии по категориям
        comments_cat_df = pd.read_sql("""
            SELECT 
                destructive_category,
                COUNT(*) as count
            FROM comments
            WHERE is_analyzed = TRUE
            GROUP BY destructive_category
            ORDER BY count DESC
        """, conn)
        data['comments_by_category'] = comments_cat_df

        # 4. Динамика по времени (посты по дням)
        daily_df = pd.read_sql("""
            SELECT 
                DATE(date) as day,
                COUNT(*) as total,
                SUM(CASE WHEN destructive_level >= 2 THEN 1 ELSE 0 END) as dangerous
            FROM posts
            WHERE is_analyzed = TRUE
            GROUP BY DATE(date)
            ORDER BY day DESC
            LIMIT 30
        """, conn)
        data['daily_stats'] = daily_df

        # 5. Топ опасных постов
        dangerous_posts = pd.read_sql("""
            SELECT 
                post_id,
                screen_name,
                LEFT(text, 150) as text_preview,
                destructive_category,
                destructive_level,
                destructive_confidence,
                likes,
                comments_count,
                views,
                url,
                date
            FROM posts
            WHERE destructive_level >= 2 AND is_analyzed = TRUE
            ORDER BY destructive_level DESC, destructive_confidence DESC
            LIMIT 20
        """, conn)
        data['dangerous_posts'] = dangerous_posts

        # 6. Топ опасных комментариев
        dangerous_comments = pd.read_sql("""
            SELECT 
                c.comment_id,
                c.screen_name,
                LEFT(c.text, 150) as text_preview,
                c.destructive_category,
                c.destructive_level,
                c.destructive_confidence,
                c.likes,
                p.post_id as post_vk_id,
                c.date
            FROM comments c
            JOIN posts p ON c.post_id = p.id
            WHERE c.destructive_level >= 2 AND c.is_analyzed = TRUE
            ORDER BY c.destructive_level DESC, c.destructive_confidence DESC
            LIMIT 20
        """, conn)
        data['dangerous_comments'] = dangerous_comments

        # 7. Общая статистика
        total_stats = pd.read_sql("""
            SELECT 
                (SELECT COUNT(*) FROM posts WHERE is_analyzed = TRUE) as total_posts,
                (SELECT COUNT(*) FROM comments WHERE is_analyzed = TRUE) as total_comments,
                (SELECT COUNT(*) FROM posts WHERE destructive_level >= 2) as dangerous_posts,
                (SELECT COUNT(*) FROM comments WHERE destructive_level >= 2) as dangerous_comments,
                (SELECT ROUND(AVG(destructive_confidence)::numeric, 2) FROM posts WHERE destructive_level > 0) as avg_confidence,
                (SELECT COUNT(*) FROM posts WHERE destructive_level = 3) as critical_posts,
                (SELECT COUNT(*) FROM posts WHERE destructive_level = 2) as medium_posts
        """, conn)
        data['total_stats'] = total_stats

        # 8. Категории с самыми опасными постами
        extreme_cats = pd.read_sql("""
            SELECT 
                destructive_category,
                COUNT(*) as count,
                ROUND(AVG(destructive_level)::numeric, 1) as avg_level,
                MAX(destructive_confidence) as max_confidence
            FROM posts
            WHERE destructive_level >= 2 AND is_analyzed = TRUE
            GROUP BY destructive_category
            ORDER BY avg_level DESC, count DESC
        """, conn)
        data['extreme_cats'] = extreme_cats

        # 9. Активность по часам
        hourly_df = pd.read_sql("""
            SELECT 
                EXTRACT(HOUR FROM date) as hour,
                COUNT(*) as count
            FROM posts
            WHERE is_analyzed = TRUE
            GROUP BY EXTRACT(HOUR FROM date)
            ORDER BY hour
        """, conn)
        data['hourly_stats'] = hourly_df

    except Exception as e:
        print(f"Ошибка получения данных: {e}")
    finally:
        conn.close()

    return data


# Layout приложения
app.layout = html.Div([
    # Header
    html.Div([
        html.Div([
            html.H1("🛡️ Анализ деструктивного контента",
                    style={'color': 'white', 'margin': 0, 'fontSize': '28px'}),
            html.P("ВКонтакте | Мониторинг и аналитика",
                   style={'color': '#bdc3c7', 'margin': '5px 0 0 0'})
        ], style={'display': 'inline-block'}),

        html.Div([
            html.Button("🔄 Обновить данные", id="refresh-btn",
                        style={
                            'backgroundColor': COLORS['info'],
                            'color': 'white',
                            'border': 'none',
                            'padding': '10px 25px',
                            'borderRadius': '8px',
                            'cursor': 'pointer',
                            'fontSize': '14px',
                            'fontWeight': 'bold',
                            'marginRight': '10px'
                        }),
            html.Span(id="update-time",
                      style={'color': '#bdc3c7', 'fontSize': '12px'})
        ], style={'float': 'right', 'marginTop': '10px'})
    ], style={
        'backgroundColor': COLORS['primary'],
        'padding': '20px 30px',
        'borderRadius': '12px',
        'marginBottom': '25px',
        'overflow': 'hidden'
    }),

    # Основной контент
    html.Div(id="dashboard-content", children=[
        html.Div([
            html.Div(style={'textAlign': 'center', 'padding': '50px'},
                     children=[
                         html.Div(style={'fontSize': '48px', 'marginBottom': '20px'}, children="📊"),
                         html.H3("Загрузка данных...", style={'color': COLORS['primary']}),
                         html.P("Пожалуйста, подождите", style={'color': '#7f8c8d'})
                     ])
        ])
    ])
], style={
    'fontFamily': '-apple-system, BlinkMacSystemFont, "Segoe UI", Arial, sans-serif',
    'backgroundColor': '#f0f2f5',
    'minHeight': '100vh',
    'padding': '20px'
})


@callback(
    [Output("dashboard-content", "children"),
     Output("update-time", "children")],
    Input("refresh-btn", "n_clicks"),
    prevent_initial_call=False
)
def update_dashboard(n_clicks):
    """Обновление дашборда"""
    data = get_statistics_data()

    update_time = f"Обновлено: {datetime.now().strftime('%H:%M:%S')}"

    if not data or data.get('total_stats', pd.DataFrame()).empty:
        return html.Div([
            html.Div([
                html.Div(style={'fontSize': '64px', 'marginBottom': '20px'}, children="📭"),
                html.H3("Нет данных для отображения",
                        style={'color': COLORS['danger_medium'], 'textAlign': 'center'}),
                html.P("Запустите сбор и анализ данных:",
                       style={'textAlign': 'center', 'color': '#7f8c8d'}),
                html.Pre("""
    python main.py          # Сбор данных
    python analyze_main.py  # Анализ
                """, style={'textAlign': 'center', 'backgroundColor': '#2c3e50',
                            'color': '#ecf0f1', 'padding': '10px',
                            'borderRadius': '8px', 'display': 'inline-block'}),
            ], style={'textAlign': 'center', 'padding': '50px'})
        ]), update_time

    total = data['total_stats']

    # Главный контент
    return html.Div([
        # Карточки с метриками
        html.Div([
            html.Div([
                html.Div("📝", style={'fontSize': '32px', 'marginBottom': '10px'}),
                html.H3(f"{total['total_posts'].iloc[0]:,}",
                        style={'margin': '0', 'fontSize': '32px', 'color': COLORS['primary']}),
                html.P("Всего постов", style={'margin': '5px 0 0 0', 'color': '#7f8c8d'})
            ], style=card_style),

            html.Div([
                html.Div("💬", style={'fontSize': '32px', 'marginBottom': '10px'}),
                html.H3(f"{total['total_comments'].iloc[0]:,}",
                        style={'margin': '0', 'fontSize': '32px', 'color': COLORS['primary']}),
                html.P("Всего комментариев", style={'margin': '5px 0 0 0', 'color': '#7f8c8d'})
            ], style=card_style),

            html.Div([
                html.Div("🔴", style={'fontSize': '32px', 'marginBottom': '10px'}),
                html.H3(f"{total['critical_posts'].iloc[0] if 'critical_posts' in total else 0}",
                        style={'margin': '0', 'fontSize': '32px', 'color': COLORS['danger_high']}),
                html.P("Критический уровень", style={'margin': '5px 0 0 0', 'color': '#7f8c8d'})
            ], style=card_style),

            html.Div([
                html.Div("🟠", style={'fontSize': '32px', 'marginBottom': '10px'}),
                html.H3(f"{total['medium_posts'].iloc[0] if 'medium_posts' in total else 0}",
                        style={'margin': '0', 'fontSize': '32px', 'color': COLORS['danger_medium']}),
                html.P("Средний уровень", style={'margin': '5px 0 0 0', 'color': '#7f8c8d'})
            ], style=card_style),
        ], style={'display': 'grid', 'gridTemplateColumns': 'repeat(4, 1fr)', 'gap': '20px',
                  'marginBottom': '25px'}),

        # Первый ряд графиков
        html.Div([
            html.Div([
                html.H3("📊 Распределение по категориям",
                        style={'color': COLORS['primary'], 'marginBottom': '15px'}),
                dcc.Graph(figure=create_category_chart(data['posts_by_category'], 'posts'),
                          config={'displayModeBar': False})
            ], style={'flex': 1, 'marginRight': '12.5px', **card_style}),

            html.Div([
                html.H3("⚠️ Уровни критичности",
                        style={'color': COLORS['primary'], 'marginBottom': '15px'}),
                dcc.Graph(figure=create_level_chart(data['posts_by_level']),
                          config={'displayModeBar': False})
            ], style={'flex': 1, 'marginLeft': '12.5px', **card_style})
        ], style={'display': 'flex', 'marginBottom': '25px'}),

        # Комментарии и активность по часам
        html.Div([
            html.Div([
                html.H3("💬 Комментарии по категориям",
                        style={'color': COLORS['primary'], 'marginBottom': '15px'}),
                dcc.Graph(figure=create_category_chart(data['comments_by_category'], 'comments'),
                          config={'displayModeBar': False})
            ], style={'flex': 1, 'marginRight': '12.5px', **card_style}),

            html.Div([
                html.H3("⏰ Активность по часам",
                        style={'color': COLORS['primary'], 'marginBottom': '15px'}),
                dcc.Graph(figure=create_hourly_chart(data['hourly_stats']),
                          config={'displayModeBar': False})
            ], style={'flex': 1, 'marginLeft': '12.5px', **card_style})
        ], style={'display': 'flex', 'marginBottom': '25px'}),

        # Динамика
        html.Div([
            html.H3("📈 Динамика активности (30 дней)",
                    style={'color': COLORS['primary'], 'marginBottom': '15px'}),
            dcc.Graph(figure=create_timeline_chart(data['daily_stats']),
                      config={'displayModeBar': False})
        ], style=card_style),

        # Самые опасные категории
        html.Div([
            html.H3("🔥 Рейтинг опасности категорий",
                    style={'color': COLORS['primary'], 'marginBottom': '15px'}),
            dcc.Graph(figure=create_extreme_chart(data['extreme_cats']),
                      config={'displayModeBar': False})
        ], style=card_style),

        # Топ опасных постов
        html.Div([
            html.H3("🚨 ТОП-20 ОПАСНЫХ ПОСТОВ",
                    style={'color': COLORS['danger_high'], 'marginBottom': '15px'}),
            create_posts_table(data['dangerous_posts'])
        ], style=card_style),

        # Топ опасных комментариев
        html.Div([
            html.H3("⚠️ ТОП-20 ОПАСНЫХ КОММЕНТАРИЕВ",
                    style={'color': COLORS['danger_medium'], 'marginBottom': '15px'}),
            create_comments_table(data['dangerous_comments'])
        ], style=card_style),
    ]), update_time


card_style = {
    'backgroundColor': 'white',
    'borderRadius': '12px',
    'padding': '20px',
    'boxShadow': '0 1px 3px rgba(0,0,0,0.1)',
    'marginBottom': '0'
}


def create_category_chart(df, type_name):
    """Создание круговой диаграммы по категориям"""
    if df.empty:
        return go.Figure()

    df['display_name'] = df['destructive_category'].map(CATEGORY_NAMES_RU)

    colors = []
    for cat in df['destructive_category']:
        if cat == 'safe':
            colors.append(COLORS['safe'])
        elif cat in ['extremism', 'suicide']:
            colors.append(COLORS['danger_high'])
        elif cat in ['aggression', 'hate_speech']:
            colors.append(COLORS['danger_medium'])
        else:
            colors.append(COLORS['danger_low'])

    fig = go.Figure(data=[go.Pie(
        labels=df['display_name'],
        values=df['count'],
        hole=0.4,
        marker_colors=colors,
        textinfo='label+percent',
        textposition='auto',
        textfont_size=12
    )])

    fig.update_layout(
        height=400,
        showlegend=False,
        margin=dict(l=20, r=20, t=40, b=20),
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(0,0,0,0)'
    )

    return fig


def create_level_chart(df):
    """Создание столбчатой диаграммы по уровням"""
    if df.empty:
        return go.Figure()

    df['level_name'] = df['destructive_level'].map(LEVEL_NAMES_RU)

    colors_map = {0: COLORS['safe'], 1: COLORS['danger_low'],
                  2: COLORS['danger_medium'], 3: COLORS['danger_high']}

    fig = go.Figure(data=[go.Bar(
        x=df['level_name'],
        y=df['count'],
        marker_color=[colors_map[lvl] for lvl in df['destructive_level']],
        text=df['count'],
        textposition='auto',
        textfont=dict(size=14, color='white'),
        hovertemplate='<b>%{x}</b><br>Количество: %{y}<extra></extra>'
    )])

    fig.update_layout(
        height=400,
        xaxis_title="Уровень критичности",
        yaxis_title="Количество постов",
        showlegend=False,
        margin=dict(l=20, r=20, t=40, b=20),
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(0,0,0,0)'
    )

    return fig


def create_timeline_chart(df):
    """Создание временной диаграммы"""
    if df.empty:
        return go.Figure()

    df = df.sort_values('day')

    fig = go.Figure()

    fig.add_trace(go.Scatter(
        x=df['day'],
        y=df['total'],
        name='Всего постов',
        line=dict(color=COLORS['primary'], width=3),
        fill='tozeroy',
        fillcolor='rgba(44, 62, 80, 0.1)',
        mode='lines+markers',
        marker=dict(size=6)
    ))

    fig.add_trace(go.Bar(
        x=df['day'],
        y=df['dangerous'],
        name='Опасные посты',
        marker_color=COLORS['danger_medium'],
        opacity=0.7,
        hovertemplate='<b>%{x}</b><br>Опасные: %{y}<extra></extra>'
    ))

    fig.update_layout(
        height=400,
        xaxis_title="Дата",
        yaxis_title="Количество",
        legend=dict(x=0, y=1, orientation='h', bgcolor='rgba(0,0,0,0)'),
        margin=dict(l=20, r=20, t=40, b=20),
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(0,0,0,0)',
        hovermode='x unified'
    )

    return fig


def create_extreme_chart(df):
    """Создание диаграммы самых опасных категорий"""
    if df.empty:
        return go.Figure()

    df['display_name'] = df['destructive_category'].map(CATEGORY_NAMES_RU)

    fig = go.Figure(data=[go.Bar(
        x=df['display_name'],
        y=df['avg_level'],
        marker_color=[COLORS['danger_high'] if lvl >= 2.5
                      else COLORS['danger_medium'] for lvl in df['avg_level']],
        text=[f"{lvl:.1f}" for lvl in df['avg_level']],
        textposition='outside',
        textfont=dict(size=12),
        hovertemplate='<b>%{x}</b><br>Средний уровень: %{y:.1f}<br>Кол-во: %{text}<extra></extra>'
    )])

    fig.update_layout(
        height=400,
        xaxis_title="Категория",
        yaxis_title="Средний уровень критичности",
        yaxis=dict(range=[0, 3.5], tickmode='linear', tick0=0, dtick=0.5),
        showlegend=False,
        margin=dict(l=20, r=20, t=40, b=20),
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(0,0,0,0)'
    )

    return fig


def create_hourly_chart(df):
    """Создание диаграммы активности по часам"""
    if df.empty:
        return go.Figure()

    fig = go.Figure(data=[go.Scatter(
        x=df['hour'],
        y=df['count'],
        mode='lines+markers',
        line=dict(color=COLORS['info'], width=3),
        marker=dict(size=8, color=COLORS['info']),
        fill='tozeroy',
        fillcolor='rgba(52, 152, 219, 0.2)',
        hovertemplate='<b>%{x}:00</b><br>Постов: %{y}<extra></extra>'
    )])

    fig.update_layout(
        height=400,
        xaxis_title="Час дня",
        yaxis_title="Количество постов",
        xaxis=dict(tickmode='linear', tick0=0, dtick=2),
        showlegend=False,
        margin=dict(l=20, r=20, t=40, b=20),
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(0,0,0,0)'
    )

    return fig


def create_posts_table(df):
    """Создание таблицы опасных постов"""
    if df.empty:
        return html.Div("✅ Опасных постов не обнаружено",
                        style={'textAlign': 'center', 'padding': '30px', 'color': COLORS['safe']})

    rows = []
    for _, row in df.iterrows():
        level_name = LEVEL_NAMES_RU.get(row['destructive_level'], 'Неизвестно')
        category_ru = CATEGORY_NAMES_RU.get(row['destructive_category'], row['destructive_category'])
        icon = LEVEL_ICONS.get(row['destructive_level'], '⚪')

        # Цвет строки в зависимости от уровня
        row_color = '#fff5f5' if row['destructive_level'] == 3 else '#fffaf0' if row[
                                                                                     'destructive_level'] == 2 else 'white'

        rows.append(html.Tr([
            html.Td(icon, style={'fontSize': '24px', 'textAlign': 'center'}),
            html.Td(row['screen_name'], style={'fontWeight': 'bold'}),
            html.Td(category_ru),
            html.Td(level_name,
                    style={'color': COLORS['danger_high'] if row['destructive_level'] == 3
                    else COLORS['danger_medium'] if row['destructive_level'] == 2
                    else COLORS['danger_low']}),
            html.Td(f"{row['destructive_confidence'] * 100:.0f}%"),
            html.Td(row['likes'] if pd.notna(row['likes']) else 0, style={'textAlign': 'center'}),
            html.Td(row['comments_count'] if pd.notna(row['comments_count']) else 0, style={'textAlign': 'center'}),
            html.Td(html.A("🔗 Открыть", href=row['url'], target='_blank',
                           style={'color': COLORS['info'], 'textDecoration': 'none'})),
            html.Td(row['text_preview'][:70] + ('...' if len(row['text_preview']) > 70 else ''),
                    style={'fontSize': '12px', 'color': '#555'})
        ], style={'backgroundColor': row_color, 'borderBottom': '1px solid #eee'}))

    return html.Div([
        html.Table([
            html.Thead(html.Tr([
                html.Th("", style={'width': '40px'}),
                html.Th("Паблик", style={'textAlign': 'left'}),
                html.Th("Категория", style={'textAlign': 'left'}),
                html.Th("Уровень", style={'textAlign': 'left'}),
                html.Th("Уверенность", style={'textAlign': 'left'}),
                html.Th("❤️", style={'textAlign': 'center'}),
                html.Th("💬", style={'textAlign': 'center'}),
                html.Th("Ссылка", style={'textAlign': 'left'}),
                html.Th("Текст", style={'textAlign': 'left'})
            ], style={'backgroundColor': COLORS['primary'], 'color': 'white',
                      'padding': '12px', 'position': 'sticky', 'top': 0})),
            html.Tbody(rows)
        ], style={'width': '100%', 'borderCollapse': 'collapse', 'fontSize': '13px'})
    ], style={'overflowX': 'auto', 'maxHeight': '500px', 'overflowY': 'auto'})


def create_comments_table(df):
    """Создание таблицы опасных комментариев"""
    if df.empty:
        return html.Div("✅ Опасных комментариев не обнаружено",
                        style={'textAlign': 'center', 'padding': '30px', 'color': COLORS['safe']})

    rows = []
    for _, row in df.iterrows():
        level_name = LEVEL_NAMES_RU.get(row['destructive_level'], 'Неизвестно')
        category_ru = CATEGORY_NAMES_RU.get(row['destructive_category'], row['destructive_category'])
        icon = LEVEL_ICONS.get(row['destructive_level'], '⚪')

        row_color = '#fff5f5' if row['destructive_level'] == 3 else '#fffaf0' if row[
                                                                                     'destructive_level'] == 2 else 'white'

        rows.append(html.Tr([
            html.Td(icon, style={'fontSize': '24px', 'textAlign': 'center'}),
            html.Td(row['screen_name'], style={'fontWeight': 'bold'}),
            html.Td(category_ru),
            html.Td(level_name,
                    style={'color': COLORS['danger_high'] if row['destructive_level'] == 3
                    else COLORS['danger_medium'] if row['destructive_level'] == 2
                    else COLORS['danger_low']}),
            html.Td(f"{row['destructive_confidence'] * 100:.0f}%"),
            html.Td(row['likes'] if pd.notna(row['likes']) else 0, style={'textAlign': 'center'}),
            html.Td(row['text_preview'][:80] + ('...' if len(row['text_preview']) > 80 else ''),
                    style={'fontSize': '12px', 'color': '#555'})
        ], style={'backgroundColor': row_color, 'borderBottom': '1px solid #eee'}))

    return html.Div([
        html.Table([
            html.Thead(html.Tr([
                html.Th("", style={'width': '40px'}),
                html.Th("Автор", style={'textAlign': 'left'}),
                html.Th("Категория", style={'textAlign': 'left'}),
                html.Th("Уровень", style={'textAlign': 'left'}),
                html.Th("Уверенность", style={'textAlign': 'left'}),
                html.Th("❤️", style={'textAlign': 'center'}),
                html.Th("Текст", style={'textAlign': 'left'})
            ], style={'backgroundColor': COLORS['primary'], 'color': 'white',
                      'padding': '12px', 'position': 'sticky', 'top': 0})),
            html.Tbody(rows)
        ], style={'width': '100%', 'borderCollapse': 'collapse', 'fontSize': '13px'})
    ], style={'overflowX': 'auto', 'maxHeight': '500px', 'overflowY': 'auto'})


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