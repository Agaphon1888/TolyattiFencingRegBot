from flask import Flask, request, jsonify, render_template_string
import logging
import sqlite3
from datetime import datetime
import os

app = Flask(__name__)

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Конфигурация
class Config:
    WEAPON_TYPES = ['Сабля', 'Шпага', 'Рапира']
    CATEGORIES = ['Юниоры', 'Взрослые', 'Ветераны']
    AGE_GROUPS = ['до 12 лет', '13-15 лет', '16-18 лет', '19+ лет']

app.config.from_object(Config)

# Простая база данных
def init_db():
    conn = sqlite3.connect('registrations.db')
    cursor = conn.cursor()
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS registrations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            telegram_id INTEGER NOT NULL,
            username TEXT,
            full_name TEXT NOT NULL,
            weapon_type TEXT NOT NULL,
            category TEXT NOT NULL,
            age_group TEXT NOT NULL,
            phone TEXT NOT NULL,
            experience TEXT,
            status TEXT DEFAULT 'pending',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    conn.commit()
    conn.close()
    logger.info("База данных инициализирована")

def add_registration(data):
    conn = sqlite3.connect('registrations.db')
    cursor = conn.cursor()
    
    cursor.execute('''
        INSERT INTO registrations 
        (telegram_id, username, full_name, weapon_type, category, age_group, phone, experience)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    ''', (
        data['telegram_id'],
        data.get('username'),
        data['full_name'],
        data['weapon_type'],
        data['category'],
        data['age_group'],
        data['phone'],
        data['experience']
    ))
    
    registration_id = cursor.lastrowid
    conn.commit()
    conn.close()
    
    logger.info(f"Добавлена новая регистрация ID: {registration_id}")
    return registration_id

def get_all_registrations():
    conn = sqlite3.connect('registrations.db')
    cursor = conn.cursor()
    
    cursor.execute('SELECT * FROM registrations ORDER BY created_at DESC')
    
    registrations = []
    for row in cursor.fetchall():
        registrations.append({
            'id': row[0],
            'telegram_id': row[1],
            'username': row[2],
            'full_name': row[3],
            'weapon_type': row[4],
            'category': row[5],
            'age_group': row[6],
            'phone': row[7],
            'experience': row[8],
            'status': row[9],
            'created_at': row[10]
        })
    
    conn.close()
    return registrations

# HTML шаблон
ADMIN_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>Регистрации на соревнования</title>
    <style>
        body { font-family: Arial, sans-serif; margin: 20px; }
        table { width: 100%; border-collapse: collapse; margin-top: 20px; }
        th, td { border: 1px solid #ddd; padding: 8px; text-align: left; }
        th { background-color: #f2f2f2; }
    </style>
</head>
<body>
    <h1>🤺 Заявки на соревнования по фехтованию</h1>
    <p>Всего заявок: {{ registrations|length }}</p>
    
    <table>
        <thead>
            <tr>
                <th>ID</th>
                <th>ФИО</th>
                <th>Оружие</th>
                <th>Категория</th>
                <th>Возраст</th>
                <th>Телефон</th>
                <th>Опыт</th>
                <th>Статус</th>
                <th>Дата</th>
            </tr>
        </thead>
        <tbody>
            {% for reg in registrations %}
            <tr>
                <td>{{ reg.id }}</td>
                <td>{{ reg.full_name }}</td>
                <td>{{ reg.weapon_type }}</td>
                <td>{{ reg.category }}</td>
                <td>{{ reg.age_group }}</td>
                <td>{{ reg.phone }}</td>
                <td>{{ reg.experience or 'Не указан' }}</td>
                <td>{{ reg.status }}</td>
                <td>{{ reg.created_at }}</td>
            </tr>
            {% endfor %}
        </tbody>
    </table>
</body>
</html>
"""

@app.route('/')
def home():
    return jsonify({
        "status": "Fencing Registration Bot API is running!",
        "version": "1.0",
        "admin_panel": "/admin"
    })

@app.route('/admin')
def admin():
    """Админка для просмотра всех заявок"""
    try:
        registrations = get_all_registrations()
        return render_template_string(ADMIN_TEMPLATE, registrations=registrations)
    except Exception as e:
        return f"Ошибка: {str(e)}", 500

@app.route('/health')
def health_check():
    return jsonify({"status": "healthy"})

# Инициализация при запуске
@app.before_first_request
def initialize():
    init_db()

if __name__ == '__main__':
    init_db()
    app.run(host='0.0.0.0', port=5000)
