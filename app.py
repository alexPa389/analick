from flask import Flask, render_template
from flask_restx import Api, Resource, fields, reqparse
import sqlite3
import os
from werkzeug.security import generate_password_hash
from datetime import datetime

app = Flask(__name__, template_folder='templates')
api = Api(app, 
          doc='/swagger/',
          version='1.0',
          title='Account API',
          description='API для управления учетными записями')

# Конфигурация
app.config['DATABASE'] = 'accounts.db'
app.config['SECRET_KEY'] = 'your-secret-key-here'

# Модели для Swagger
account_model = api.model('Account', {
    'id': fields.Integer(readonly=True),
    'username': fields.String(required=True, min_length=3, max_length=20),
    'email': fields.String(required=True),
    'created_at': fields.DateTime(readonly=True)
})

create_account_model = api.model('CreateAccount', {
    'username': fields.String(required=True, min_length=3, max_length=20),
    'email': fields.String(required=True),
    'password': fields.String(required=True, min_length=6)
})

# Функция для создания/проверки БД
def init_db():
    with sqlite3.connect(app.config['DATABASE']) as conn:
        cursor = conn.cursor()
        
        # Проверяем существование таблицы
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='accounts'")
        table_exists = cursor.fetchone()
        
        if not table_exists:
            cursor.execute('''
                CREATE TABLE accounts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    username TEXT NOT NULL UNIQUE,
                    email TEXT NOT NULL UNIQUE,
                    password_hash TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            print("База данных успешно создана")
            
            # Добавляем тестового пользователя (опционально)
            test_password = generate_password_hash('test123')
            cursor.execute('''
                INSERT INTO accounts (username, email, password_hash)
                VALUES (?, ?, ?)
            ''', ('testuser', 'test@example.com', test_password))
            
            conn.commit()
            print("Тестовый пользователь добавлен")

# Парсер для запросов
parser = reqparse.RequestParser()
parser.add_argument('username', type=str, required=True)
parser.add_argument('email', type=str, required=True)
parser.add_argument('password', type=str, required=True)

# Главный роут
@app.route('/')
def home():
    """Главная страница"""
    return render_template('index.html')

@api.route('/accounts')
class AccountsResource(Resource):
    @api.doc('list_accounts')
    @api.marshal_list_with(account_model)
    def get(self):
        """Получить все учетные записи"""
        with sqlite3.connect(app.config['DATABASE']) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute('SELECT id, username, email, created_at FROM accounts')
            return [dict(row) for row in cursor.fetchall()]

    @api.doc('create_account')
    @api.expect(create_account_model)
    @api.marshal_with(account_model, code=201)
    @api.response(400, 'Некорректные данные')
    @api.response(409, 'Пользователь уже существует')
    def post(self):
        """Создать новую учетную запись"""
        args = parser.parse_args()
        
        if len(args['password']) < 6:
            api.abort(400, 'Пароль должен содержать минимум 6 символов')
        
        try:
            with sqlite3.connect(app.config['DATABASE']) as conn:
                cursor = conn.cursor()
                password_hash = generate_password_hash(args['password'])
                
                cursor.execute('''
                    INSERT INTO accounts (username, email, password_hash)
                    VALUES (?, ?, ?)
                ''', (args['username'], args['email'], password_hash))
                
                conn.commit()
                account_id = cursor.lastrowid
                
                cursor.execute('''
                    SELECT id, username, email, created_at 
                    FROM accounts WHERE id = ?
                ''', (account_id,))
                
                return dict(cursor.fetchone()), 201
                
        except sqlite3.IntegrityError as e:
            if 'username' in str(e):
                api.abort(409, 'Имя пользователя уже занято')
            elif 'email' in str(e):
                api.abort(409, 'Email уже зарегистрирован')
            api.abort(500, 'Ошибка базы данных')

# Создаем БД при запуске приложения
if __name__ == '__main__':
    # Проверяем и создаем БД если нужно
    if not os.path.exists(app.config['DATABASE']):
        print(f"Создаем новую базу данных: {app.config['DATABASE']}")
    
    init_db()
    
    # Запускаем сервер
    app.run(debug=True, host='0.0.0.0')