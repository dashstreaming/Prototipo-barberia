from flask import Flask, request, jsonify, render_template_string, session, redirect, url_for
from flask_cors import CORS
import sqlite3
import hashlib
import datetime
import json
from functools import wraps
import os

app = Flask(__name__)
app.secret_key = 'montana-barber-shop-secret-key-2024'
CORS(app)

# Configuración de la base de datos
DATABASE = 'montana_barber.db'

def get_db_connection():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    """Inicializar la base de datos con las tablas necesarias"""
    conn = get_db_connection()
    
    # Tabla de usuarios (admin)
    conn.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            role TEXT DEFAULT 'admin',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Tabla de servicios
    conn.execute('''
        CREATE TABLE IF NOT EXISTS services (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            description TEXT,
            price DECIMAL(10,2) NOT NULL,
            duration INTEGER NOT NULL,
            active BOOLEAN DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Tabla de citas
    conn.execute('''
        CREATE TABLE IF NOT EXISTS appointments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            service_id INTEGER,
            customer_name TEXT NOT NULL,
            customer_phone TEXT NOT NULL,
            appointment_date DATE NOT NULL,
            appointment_time TIME NOT NULL,
            status TEXT DEFAULT 'pending',
            deposit_amount DECIMAL(10,2) DEFAULT 50.00,
            deposit_status TEXT DEFAULT 'pending',
            notes TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (service_id) REFERENCES services (id)
        )
    ''')
    
    # Tabla de horarios de negocio
    conn.execute('''
        CREATE TABLE IF NOT EXISTS business_hours (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            day_of_week INTEGER NOT NULL,
            opening_time TIME,
            closing_time TIME,
            is_closed BOOLEAN DEFAULT 0
        )
    ''')
    
    # Tabla de configuraciones
    conn.execute('''
        CREATE TABLE IF NOT EXISTS settings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            key TEXT UNIQUE NOT NULL,
            value TEXT NOT NULL,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Tabla de días cerrados especiales
    conn.execute('''
        CREATE TABLE IF NOT EXISTS closed_days (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date DATE NOT NULL,
            reason TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Insertar datos iniciales si no existen
    
    # Usuario admin por defecto
    conn.execute('''
        INSERT OR IGNORE INTO users (username, password_hash, role) 
        VALUES (?, ?, ?)
    ''', ('admin', hashlib.sha256('admin123'.encode()).hexdigest(), 'admin'))
    
    # Servicios por defecto
    services_data = [
        ('Corte Clásico', 'Corte tradicional con tijera y máquina, incluye diseño básico.', 200.00, 45),
        ('Corte Premium', 'Corte detallado con acabado perfecto, incluye diseño y arreglo de barba.', 300.00, 60),
        ('Afeitado Clásico', 'Afeitado tradicional con navaja, incluye toallas calientes y productos premium.', 250.00, 40),
        ('Corte y Barba', 'Combo completo: corte premium más arreglo de barba con acabado profesional.', 350.00, 75),
        ('Tinte de Barba', 'Tinte profesional para barba con productos de alta calidad.', 180.00, 30),
        ('Servicio Infantil', 'Corte especial para niños con ambiente amigable y diseño a elección.', 150.00, 35)
    ]
    
    for service in services_data:
        conn.execute('''
            INSERT OR IGNORE INTO services (name, description, price, duration) 
            VALUES (?, ?, ?, ?)
        ''', service)
    
    # Horarios de negocio por defecto (Lunes=1, Domingo=0)
    business_hours_data = [
        (1, '09:00', '19:00', 0),  # Lunes
        (2, '09:00', '19:00', 0),  # Martes
        (3, '09:00', '19:00', 0),  # Miércoles
        (4, '09:00', '19:00', 0),  # Jueves
        (5, '09:00', '19:00', 0),  # Viernes
        (6, '09:00', '17:00', 0),  # Sábado
        (0, None, None, 1)         # Domingo - Cerrado
    ]
    
    for hours in business_hours_data:
        conn.execute('''
            INSERT OR IGNORE INTO business_hours (day_of_week, opening_time, closing_time, is_closed) 
            VALUES (?, ?, ?, ?)
        ''', hours)
    
    # Configuraciones por defecto
    settings_data = [
        ('deposit_amount', '50.00'),
        ('advance_booking_days', '7'),
        ('minimum_advance_hours', '1'),
        ('slot_duration', '30'),
        ('reminder_24h', 'true'),
        ('reminder_3h', 'true'),
        ('confirmation_message', 'Hola {{nombre}}, tu cita para {{servicio}} está confirmada para el {{fecha}} a las {{hora}}. ¡Te esperamos!'),
        ('reminder_message', 'Hola {{nombre}}, recuerda que tienes cita para {{servicio}} mañana a las {{hora}}. ¡Te esperamos!')
    ]
    
    for setting in settings_data:
        conn.execute('''
            INSERT OR IGNORE INTO settings (key, value) 
            VALUES (?, ?)
        ''', setting)
    
    conn.commit()
    conn.close()
    print("Base de datos inicializada correctamente")

def require_auth(f):
    """Decorador para rutas que requieren autenticación"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return jsonify({'error': 'Authentication required'}), 401
        return f(*args, **kwargs)
    return decorated_function

# ==================== RUTAS DE AUTENTICACIÓN ====================

@app.route('/api/login', methods=['POST'])
def login():
    data = request.get_json()
    username = data.get('username')
    password = data.get('password')
    
    if not username or not password:
        return jsonify({'error': 'Username and password required'}), 400
    
    conn = get_db_connection()
    user = conn.execute(
        'SELECT * FROM users WHERE username = ? AND password_hash = ?',
        (username, hashlib.sha256(password.encode()).hexdigest())
    ).fetchone()
    conn.close()
    
    if user:
        session['user_id'] = user['id']
        session['username'] = user['username']
        return jsonify({'message': 'Login successful', 'user': {'id': user['id'], 'username': user['username']}}), 200
    else:
        return jsonify({'error': 'Invalid credentials'}), 401

@app.route('/api/logout', methods=['POST'])
def logout():
    session.clear()
    return jsonify({'message': 'Logout successful'}), 200

@app.route('/api/check-auth', methods=['GET'])
def check_auth():
    if 'user_id' in session:
        return jsonify({'authenticated': True, 'username': session['username']}), 200
    else:
        return jsonify({'authenticated': False}), 200

# ==================== RUTAS DE SERVICIOS ====================

@app.route('/api/services', methods=['GET'])
def get_services():
    """Obtener todos los servicios (activos para cliente, todos para admin)"""
    show_all = request.args.get('all', 'false').lower() == 'true'
    
    conn = get_db_connection()
    if show_all and 'user_id' in session:
        # Admin ve todos los servicios
        services = conn.execute('SELECT * FROM services ORDER BY name').fetchall()
    else:
        # Cliente ve solo servicios activos
        services = conn.execute(
            'SELECT * FROM services WHERE active = 1 ORDER BY name'
        ).fetchall()
    conn.close()
    
    return jsonify([dict(service) for service in services])

@app.route('/api/services', methods=['POST'])
@require_auth
def create_service():
    """Crear un nuevo servicio"""
    data = request.get_json()
    
    required_fields = ['name', 'price', 'duration']
    if not all(field in data for field in required_fields):
        return jsonify({'error': 'Missing required fields'}), 400
    
    conn = get_db_connection()
    cursor = conn.execute(
        'INSERT INTO services (name, description, price, duration, active) VALUES (?, ?, ?, ?, ?)',
        (data['name'], data.get('description', ''), data['price'], data['duration'], data.get('active', True))
    )
    service_id = cursor.lastrowid
    conn.commit()
    conn.close()
    
    return jsonify({'id': service_id, 'message': 'Service created successfully'}), 201

@app.route('/api/services/<int:service_id>', methods=['PUT'])
@require_auth
def update_service(service_id):
    """Actualizar un servicio"""
    data = request.get_json()
    
    conn = get_db_connection()
    conn.execute(
        'UPDATE services SET name = ?, description = ?, price = ?, duration = ?, active = ? WHERE id = ?',
        (data['name'], data.get('description', ''), data['price'], data['duration'], data.get('active', True), service_id)
    )
    conn.commit()
    conn.close()
    
    return jsonify({'message': 'Service updated successfully'}), 200

@app.route('/api/services/<int:service_id>', methods=['DELETE'])
@require_auth
def delete_service(service_id):
    """Eliminar un servicio (soft delete)"""
    conn = get_db_connection()
    conn.execute('UPDATE services SET active = 0 WHERE id = ?', (service_id,))
    conn.commit()
    conn.close()
    
    return jsonify({'message': 'Service deleted successfully'}), 200

# ==================== RUTAS DE CITAS ====================

@app.route('/api/appointments', methods=['GET'])
def get_appointments():
    """Obtener citas - acceso público con filtros para cliente"""
    date_filter = request.args.get('date')
    status_filter = request.args.get('status')
    
    query = '''
        SELECT a.*, s.name as service_name, s.price as service_price 
        FROM appointments a 
        JOIN services s ON a.service_id = s.id
    '''
    params = []
    conditions = []
    
    if date_filter:
        conditions.append('a.appointment_date = ?')
        params.append(date_filter)
    
    if status_filter:
        conditions.append('a.status = ?')
        params.append(status_filter)
    
    if conditions:
        query += ' WHERE ' + ' AND '.join(conditions)
    
    query += ' ORDER BY a.appointment_date DESC, a.appointment_time DESC'
    
    conn = get_db_connection()
    appointments = conn.execute(query, params).fetchall()
    conn.close()
    
    # Si no es admin, solo mostrar datos mínimos necesarios para disponibilidad
    if 'user_id' not in session and date_filter:
        simplified = []
        for apt in appointments:
            simplified.append({
                'appointment_time': apt['appointment_time'],
                'status': apt['status'],
                'appointment_date': apt['appointment_date']
            })
        return jsonify(simplified)
    
    return jsonify([dict(appointment) for appointment in appointments])

@app.route('/api/appointments', methods=['POST'])
def create_appointment():
    """Crear una nueva cita"""
    data = request.get_json()
    
    required_fields = ['service_id', 'customer_name', 'customer_phone', 'appointment_date', 'appointment_time']
    if not all(field in data for field in required_fields):
        return jsonify({'error': 'Missing required fields'}), 400
    
    # Verificar que el horario esté disponible
    conn = get_db_connection()
    existing = conn.execute(
        'SELECT id FROM appointments WHERE appointment_date = ? AND appointment_time = ? AND status != "cancelled"',
        (data['appointment_date'], data['appointment_time'])
    ).fetchone()
    
    if existing:
        conn.close()
        return jsonify({'error': 'Time slot not available'}), 409
    
    # Crear la cita
    cursor = conn.execute(
        '''INSERT INTO appointments 
           (service_id, customer_name, customer_phone, appointment_date, appointment_time, deposit_amount, notes) 
           VALUES (?, ?, ?, ?, ?, ?, ?)''',
        (data['service_id'], data['customer_name'], data['customer_phone'], 
         data['appointment_date'], data['appointment_time'], 
         data.get('deposit_amount', 50.00), data.get('notes', ''))
    )
    appointment_id = cursor.lastrowid
    conn.commit()
    conn.close()
    
    return jsonify({'id': appointment_id, 'message': 'Appointment created successfully'}), 201

@app.route('/api/appointments/<int:appointment_id>', methods=['PUT'])
@require_auth
def update_appointment(appointment_id):
    """Actualizar una cita"""
    data = request.get_json()
    
    conn = get_db_connection()
    conn.execute(
        '''UPDATE appointments 
           SET service_id = ?, customer_name = ?, customer_phone = ?, 
               appointment_date = ?, appointment_time = ?, status = ?, notes = ?
           WHERE id = ?''',
        (data['service_id'], data['customer_name'], data['customer_phone'],
         data['appointment_date'], data['appointment_time'], data['status'], 
         data.get('notes', ''), appointment_id)
    )
    conn.commit()
    conn.close()
    
    return jsonify({'message': 'Appointment updated successfully'}), 200

@app.route('/api/appointments/<int:appointment_id>/status', methods=['PUT'])
@require_auth
def update_appointment_status(appointment_id):
    """Actualizar solo el estado de una cita"""
    data = request.get_json()
    status = data.get('status')
    
    if status not in ['pending', 'confirmed', 'completed', 'cancelled', 'no-show']:
        return jsonify({'error': 'Invalid status'}), 400
    
    conn = get_db_connection()
    conn.execute('UPDATE appointments SET status = ? WHERE id = ?', (status, appointment_id))
    conn.commit()
    conn.close()
    
    return jsonify({'message': 'Appointment status updated successfully'}), 200

@app.route('/api/appointments/<int:appointment_id>', methods=['DELETE'])
@require_auth
def delete_appointment(appointment_id):
    """Eliminar una cita"""
    conn = get_db_connection()
    conn.execute('DELETE FROM appointments WHERE id = ?', (appointment_id,))
    conn.commit()
    conn.close()
    
    return jsonify({'message': 'Appointment deleted successfully'}), 200

# ==================== RUTAS DE HORARIOS DISPONIBLES ====================

@app.route('/api/available-times', methods=['GET'])
def get_available_times():
    """Obtener horarios disponibles para una fecha específica"""
    date = request.args.get('date')
    service_id = request.args.get('service_id')
    
    if not date or not service_id:
        return jsonify({'error': 'Date and service_id required'}), 400
    
    # Convertir la fecha para obtener el día de la semana
    date_obj = datetime.datetime.strptime(date, '%Y-%m-%d')
    day_of_week = date_obj.weekday() + 1  # Python: 0=Monday, SQL: 1=Monday
    if day_of_week == 7:  # Sunday
        day_of_week = 0
    
    conn = get_db_connection()
    
    # Obtener horarios de negocio para ese día
    business_hours = conn.execute(
        'SELECT opening_time, closing_time, is_closed FROM business_hours WHERE day_of_week = ?',
        (day_of_week,)
    ).fetchone()
    
    if not business_hours or business_hours['is_closed']:
        conn.close()
        return jsonify([])  # Día cerrado
    
    # Obtener duración del servicio
    service = conn.execute('SELECT duration FROM services WHERE id = ?', (service_id,)).fetchone()
    if not service:
        conn.close()
        return jsonify({'error': 'Service not found'}), 404
    
    # Obtener citas ya reservadas para esa fecha
    booked_times = conn.execute(
        'SELECT appointment_time FROM appointments WHERE appointment_date = ? AND status != "cancelled"',
        (date,)
    ).fetchall()
    
    conn.close()
    
    # Generar slots disponibles
    available_slots = []
    opening_time = datetime.datetime.strptime(business_hours['opening_time'], '%H:%M').time()
    closing_time = datetime.datetime.strptime(business_hours['closing_time'], '%H:%M').time()
    
    # Obtener configuración de duración de slot
    slot_duration = 30  # minutos por defecto
    
    current_time = datetime.datetime.combine(date_obj.date(), opening_time)
    end_time = datetime.datetime.combine(date_obj.date(), closing_time)
    
    booked_times_set = {time['appointment_time'] for time in booked_times}
    
    while current_time < end_time:
        # Verificar que hay tiempo suficiente para el servicio
        service_end_time = current_time + datetime.timedelta(minutes=service['duration'])
        if service_end_time.time() <= closing_time:
            time_str = current_time.strftime('%H:%M')
            if time_str not in booked_times_set:
                available_slots.append(time_str)
        
        current_time += datetime.timedelta(minutes=slot_duration)
    
    return jsonify(available_slots)

# ==================== RUTAS DE DASHBOARD ====================

@app.route('/api/dashboard/stats', methods=['GET'])
@require_auth
def get_dashboard_stats():
    """Obtener estadísticas para el dashboard"""
    conn = get_db_connection()
    
    today = datetime.date.today()
    week_start = today - datetime.timedelta(days=today.weekday())
    month_start = today.replace(day=1)
    
    # Citas de hoy
    today_stats = conn.execute(
        '''SELECT 
           COUNT(*) as total,
           SUM(CASE WHEN status = 'completed' THEN 1 ELSE 0 END) as completed,
           SUM(CASE WHEN status = 'pending' THEN 1 ELSE 0 END) as pending
           FROM appointments 
           WHERE appointment_date = ?''',
        (today,)
    ).fetchone()
    
    # Citas de esta semana
    week_stats = conn.execute(
        '''SELECT 
           COUNT(*) as total,
           SUM(CASE WHEN status = 'completed' THEN 1 ELSE 0 END) as completed,
           SUM(CASE WHEN status = 'pending' THEN 1 ELSE 0 END) as pending
           FROM appointments 
           WHERE appointment_date >= ?''',
        (week_start,)
    ).fetchone()
    
    # Citas de este mes
    month_stats = conn.execute(
        '''SELECT 
           COUNT(*) as total,
           SUM(CASE WHEN status = 'completed' THEN 1 ELSE 0 END) as completed,
           SUM(CASE WHEN status = 'cancelled' THEN 1 ELSE 0 END) as cancelled
           FROM appointments 
           WHERE appointment_date >= ?''',
        (month_start,)
    ).fetchone()
    
    # Próximas citas de hoy
    upcoming_today = conn.execute(
        '''SELECT a.*, s.name as service_name 
           FROM appointments a 
           JOIN services s ON a.service_id = s.id
           WHERE a.appointment_date = ? AND a.status = 'pending'
           ORDER BY a.appointment_time''',
        (today,)
    ).fetchall()
    
    conn.close()
    
    return jsonify({
        'today': dict(today_stats),
        'week': dict(week_stats),
        'month': dict(month_stats),
        'upcoming_today': [dict(appointment) for appointment in upcoming_today]
    })

# ==================== RUTAS DE CONFIGURACIÓN ====================

@app.route('/api/settings', methods=['GET'])
@require_auth
def get_settings():
    """Obtener todas las configuraciones"""
    conn = get_db_connection()
    settings = conn.execute('SELECT key, value FROM settings').fetchall()
    business_hours = conn.execute('SELECT * FROM business_hours ORDER BY day_of_week').fetchall()
    closed_days = conn.execute('SELECT date, reason FROM closed_days ORDER BY date').fetchall()
    conn.close()
    
    settings_dict = {setting['key']: setting['value'] for setting in settings}
    
    return jsonify({
        'settings': settings_dict,
        'business_hours': [dict(hours) for hours in business_hours],
        'closed_days': [dict(day) for day in closed_days]
    })

@app.route('/api/settings', methods=['PUT'])
@require_auth
def update_settings():
    """Actualizar configuraciones"""
    data = request.get_json()
    
    conn = get_db_connection()
    
    # Actualizar configuraciones generales
    if 'settings' in data:
        for key, value in data['settings'].items():
            conn.execute(
                'INSERT OR REPLACE INTO settings (key, value, updated_at) VALUES (?, ?, CURRENT_TIMESTAMP)',
                (key, value)
            )
    
    # Actualizar horarios de negocio
    if 'business_hours' in data:
        for hours in data['business_hours']:
            conn.execute(
                'UPDATE business_hours SET opening_time = ?, closing_time = ?, is_closed = ? WHERE day_of_week = ?',
                (hours['opening_time'], hours['closing_time'], hours['is_closed'], hours['day_of_week'])
            )
    
    # Actualizar días cerrados especiales
    if 'closed_days' in data:
        # Eliminar días cerrados existentes
        conn.execute('DELETE FROM closed_days')
        
        # Insertar nuevos días cerrados
        for day in data['closed_days']:
            conn.execute(
                'INSERT INTO closed_days (date, reason) VALUES (?, ?)',
                (day['date'], day.get('reason', ''))
            )
    
    conn.commit()
    conn.close()
    
    return jsonify({'message': 'Settings updated successfully'}), 200

# ==================== RUTAS ESTÁTICAS ====================

@app.route('/')
def index():
    """Página principal - redireccionar al cliente"""
    return redirect('/client')

@app.route('/client')
def client():
    """Servir la página del cliente"""
    try:
        with open('Prototipo_solo_cita.html', 'r', encoding='utf-8') as f:
            return f.read()
    except FileNotFoundError:
        return "Archivo Prototipo_solo_cita.html no encontrado", 404

@app.route('/admin')
def admin():
    """Servir la página del admin"""
    try:
        with open('admin_pannel.html', 'r', encoding='utf-8') as f:
            return f.read()
    except FileNotFoundError:
        return "Archivo admin_pannel.html no encontrado", 404

# ==================== MANEJO DE ERRORES ====================

@app.errorhandler(404)
def not_found(error):
    return jsonify({'error': 'Endpoint not found'}), 404

@app.errorhandler(500)
def internal_error(error):
    return jsonify({'error': 'Internal server error'}), 500

# ==================== INICIALIZACIÓN ====================

if __name__ == '__main__':
    init_db()
    print("Servidor iniciado en http://localhost:5000")
    print("Cliente: http://localhost:5000/client")
    print("Admin: http://localhost:5000/admin")
    print("Login admin: usuario='admin', contraseña='admin123'")
    app.run(debug=True, host='0.0.0.0', port=5000)