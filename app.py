from flask import Flask
from flask_restx import Api, Resource, fields, reqparse
import sqlite3
import re
from werkzeug.security import generate_password_hash, check_password_hash
import logging

# Настройка логирования
logging.basicConfig(level=logging.DEBUG)

app = Flask(__name__)
app.config['DATABASE'] = 'accounts.db'
app.config['SECRET_KEY'] = 'supersecretkey'
app.config['ERROR_404_HELP'] = False

api = Api(app, 
          version='1.0', 
          title='Account API',
          description='API для управления учетными записями',
          doc='/swagger/')

# Модели для Swagger
account_model = api.model('Account', {
    'id': fields.Integer(readonly=True),
    'username': fields.String(required=True),
    'email': fields.String(required=True),
    'created_at': fields.DateTime(readonly=True)
})

create_account_model = api.model('CreateAccount', {
    'username': fields.String(required=True, description='Имя пользователя (3-20 символов)'),
    'email': fields.String(required=True, description='Валидный email адрес'),
    'password': fields.String(required=True, description='Пароль (минимум 6 символов)')
})

# Парсер запросов
parser = reqparse.RequestParser()
parser.add_argument('username', type=str, required=True, help='Имя пользователя обязательно')
parser.add_argument('email', type=str, required=True, help='Email обязателен')
parser.add_argument('password', type=str, required=True, help='Пароль обязателен')

def get_db():
    """Возвращает соединение с базой данных"""
    conn = sqlite3.connect(app.config['DATABASE'])
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    """Инициализирует базу данных"""
    with get_db() as conn:
        conn.execute('''
            CREATE TABLE IF NOT EXISTS accounts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL UNIQUE,
                email TEXT NOT NULL UNIQUE,
                password_hash TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        conn.commit()

def validate_email(email):
    """Проверяет валидность email адреса"""
    pattern = r'^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$'
    return re.match(pattern, email) is not None

@api.route('/accounts')
class AccountsResource(Resource):
    @api.doc('list_accounts')
    @api.marshal_list_with(account_model)
    def get(self):
        """Получить все учетные записи"""
        try:
            with get_db() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT id, username, email 
                    FROM accounts
                ''')
                return [dict(row) for row in cursor.fetchall()], 200
        except sqlite3.Error as e:
            api.abort(500, 'Ошибка базы данных')

    @api.doc('create_account')
    @api.expect(create_account_model)
    @api.marshal_with(account_model, code=201)
    @api.response(400, 'Некорректные данные')
    @api.response(409, 'Конфликт данных')
    def post(self):
        """Создать новую учетную запись"""
        args = parser.parse_args()
        
        # Валидация данных
        errors = {}
        
        # Проверка имени пользователя
        if len(args['username']) < 3 or len(args['username']) > 20:
            errors['username'] = 'Длина имени пользователя должна быть от 3 до 20 символов'
        
        # Проверка email
        if not validate_email(args['email']):
            errors['email'] = 'Некорректный формат email'
        
        # Проверка пароля
        if len(args['password']) < 6:
            errors['password'] = 'Пароль должен содержать минимум 6 символов'
        
        if errors:
            api.abort(400, errors)
        
        try:
            with get_db() as conn:
                cursor = conn.cursor()
                password_hash = generate_password_hash(args['password'])
                
                cursor.execute('''
                    INSERT INTO accounts (username, email, password_hash)
                    VALUES (?, ?, ?)
                ''', (args['username'], args['email'], password_hash))
                
                conn.commit()
                print(cursor.lastrowid)
                # Получаем созданную запись
                cursor.execute('''
                    SELECT id, username, email, 
                    FROM accounts 
                    WHERE id = ?
                ''', (cursor.lastrowid,))
                print()
                new_account = cursor.fetchall()
                print(new_account)
                return new_account, 201
                
        except sqlite3.IntegrityError as e:
            error_msg = 'Ошибка уникальности: '
            if 'username' in str(e):
                error_msg += 'Имя пользователя уже существует'
            elif 'email' in str(e):
                error_msg += 'Email уже зарегистрирован'
            api.abort(409, error_msg)
       

# Инициализация базы данных
if __name__ == '__main__':
    init_db()
    app.run(debug=True)