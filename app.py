from flask import Flask, render_template, request, redirect, url_for, session, flash
import sqlite3
from functools import wraps
from datetime import datetime
import os

import os
import json
from flask_socketio import SocketIO, emit, join_room, leave_room
import eventlet

app = Flask(__name__)
app.secret_key = 'micro_erp_secret_key_2024'

# Chat globals
online_users = set()
sio = SocketIO(app, cors_allowed_origins="*", async_mode='eventlet')

# Database configuration - works locally and on cloud
DB_PATH = os.environ.get('DATABASE_URL', os.path.join(os.path.dirname(__file__), 'instance', 'erp.db'))

def init_db():
    """Initialize the database with all required tables."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Create users table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            name TEXT,
            dob TEXT,
            mobile TEXT,
            role TEXT NOT NULL DEFAULT 'staff'
        )
    ''')
    
    # Add missing columns if they don't exist (for existing databases)
    try:
        cursor.execute("ALTER TABLE users ADD COLUMN name TEXT")
    except:
        pass
    
    try:
        cursor.execute("ALTER TABLE users ADD COLUMN dob TEXT")
    except:
        pass
    
    try:
        cursor.execute("ALTER TABLE users ADD COLUMN mobile TEXT")
    except:
        pass
    
    # Create suppliers table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS suppliers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            contact TEXT,
            email TEXT,
            phone TEXT,
            user_id INTEGER,
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
    ''')
    
    # Add user_id column if it doesn't exist (for existing databases)
    try:
        cursor.execute("ALTER TABLE suppliers ADD COLUMN user_id INTEGER")
    except:
        pass
    
    # Create products table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS products (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            quantity INTEGER DEFAULT 0,
            price REAL DEFAULT 0,
            supplier_id INTEGER,
            FOREIGN KEY (supplier_id) REFERENCES suppliers (id)
        )
    ''')
    
    # Create orders table with status and supplier_id
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            product_id INTEGER NOT NULL,
            quantity INTEGER NOT NULL,
            total_price REAL NOT NULL,
            order_date TEXT NOT NULL,
            status TEXT DEFAULT 'pending',
            created_by INTEGER,
            supplier_id INTEGER,
            picked_up_by INTEGER,
            picked_up_at TEXT,
            FOREIGN KEY (product_id) REFERENCES products (id),
            FOREIGN KEY (created_by) REFERENCES users (id),
            FOREIGN KEY (supplier_id) REFERENCES suppliers (id),
            FOREIGN KEY (picked_up_by) REFERENCES users (id)
        )
    ''')
    
    # Add status column if not exists
    try:
        cursor.execute("ALTER TABLE orders ADD COLUMN status TEXT DEFAULT 'pending'")
    except:
        pass
    
    # Add supplier_id column if not exists
    try:
        cursor.execute("ALTER TABLE orders ADD COLUMN supplier_id INTEGER")
    except:
        pass
    
    # Add picked_up_by and picked_up_at columns if not exists
    try:
        cursor.execute("ALTER TABLE orders ADD COLUMN picked_up_by INTEGER")
    except:
        pass
    
    try:
        cursor.execute("ALTER TABLE orders ADD COLUMN picked_up_at TEXT")
    except:
        pass
    
# Create order tracking table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS order_tracking (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            order_id INTEGER NOT NULL,
            status TEXT NOT NULL,
            notes TEXT,
            updated_by INTEGER,
            updated_at TEXT NOT NULL,
            FOREIGN KEY (order_id) REFERENCES orders (id),
            FOREIGN KEY (updated_by) REFERENCES users (id)
        )
    ''')
    
    # === CHAT TABLES ===
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS chats (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user1_id INTEGER NOT NULL,
            user2_id INTEGER NOT NULL,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(user1_id, user2_id),
            FOREIGN KEY (user1_id) REFERENCES users (id),
            FOREIGN KEY (user2_id) REFERENCES users (id)
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            chat_id INTEGER NOT NULL,
            sender_id INTEGER NOT NULL,
            content TEXT NOT NULL,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            is_read BOOLEAN DEFAULT 0,
            FOREIGN KEY (chat_id) REFERENCES chats (id),
            FOREIGN KEY (sender_id) REFERENCES users (id)
        )
    ''')
    
    # Create default admin user if not exists
    cursor.execute("SELECT * FROM users WHERE username = 'admin'")
    if not cursor.fetchone():
        cursor.execute("INSERT INTO users (username, password, name, dob, mobile, role) VALUES (?, ?, ?, ?, ?, ?)",
                      ('admin', 'admin123', 'Admin User', '1990-01-01', '+919999999999', 'admin'))
    
    # Create default supplier user if not exists
    cursor.execute("SELECT * FROM users WHERE username = 'supplier'")
    if not cursor.fetchone():
        cursor.execute("INSERT INTO users (username, password, name, role) VALUES (?, ?, ?, ?)",
                      ('supplier', 'supplier123', 'Default Supplier', 'supplier'))
    
    conn.commit()
    conn.close()

def get_db_connection():
    """Get database connection."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def login_required(f):
    """Decorator to require login."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('Please log in first.', 'error')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

def role_required(roles):
    """Decorator to require specific roles."""
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if 'role' not in session or session['role'] not in roles:
                flash('You do not have permission to access this page.', 'error')
                return redirect(url_for('dashboard'))
            return f(*args, **kwargs)
        return decorated_function
    return decorator

# Authentication Routes
@app.route('/')
def index():
    if 'user_id' in session:
        return redirect(url_for('dashboard'))
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        conn = get_db_connection()
        user = conn.execute('SELECT * FROM users WHERE username = ? AND password = ?', 
                           (username, password)).fetchone()
        
        if user:
            session['user_id'] = user['id']
            session['username'] = user['username']
            session['role'] = user['role']
            
            # If supplier, get their supplier_id and check for pending orders
            if user['role'] == 'supplier':
                supplier = conn.execute('SELECT * FROM suppliers WHERE user_id = ?', (user['id'],)).fetchone()
                if supplier:
                    session['supplier_id'] = supplier['id']
                    
                    # Check for pending orders assigned to this supplier
                    pending_orders = conn.execute('''
                        SELECT COUNT(*) as count FROM orders 
                        WHERE supplier_id = ? AND status = 'pending'
                    ''', (supplier['id'],)).fetchone()['count']
                    
                    if pending_orders > 0:
                        flash(f'You have {pending_orders} new order(s) waiting for pickup!', 'info')
            
            conn.close()
            flash(f'Login successful! Welcome, {user["username"]} ({user["role"]})', 'success')
            return redirect(url_for('dashboard'))
        else:
            flash('Invalid username or password.', 'error')
            conn.close()
    
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    flash('You have been logged out.', 'success')
    return redirect(url_for('login'))

# Dashboard Route
@app.route('/dashboard')
@login_required
def dashboard():
    conn = get_db_connection()
    
    # Get user's role
    user_role = session.get('role')
    
    # If supplier, show different dashboard
    if user_role == 'supplier':
        supplier_id = session.get('supplier_id')
        
        # Get orders assigned to this supplier
        assigned_orders = conn.execute('''
            SELECT o.*, p.name as product_name
            FROM orders o
            LEFT JOIN products p ON o.product_id = p.id
            WHERE o.supplier_id = ? AND o.status != 'picked_up'
            ORDER BY o.order_date DESC
        ''', (supplier_id,)).fetchall()
        
        # Count pending pickups
        pending_pickup = conn.execute('''
            SELECT COUNT(*) as count FROM orders 
            WHERE supplier_id = ? AND status = 'pending'
        ''', (supplier_id,)).fetchone()['count']
        
        picked_up_today = conn.execute('''
            SELECT COUNT(*) as count FROM orders 
            WHERE supplier_id = ? AND picked_up_at >= date('now')
        ''', (supplier_id,)).fetchone()['count']
        
        conn.close()
        
        return render_template('dashboard.html', 
                            stats={'assigned_orders': len(assigned_orders),
                                   'pending_pickup': pending_pickup,
                                   'picked_up_today': picked_up_today},
                            assigned_orders=assigned_orders,
                            is_supplier=True)
    
    # Regular dashboard for admin/manager/staff
    products_count = conn.execute('SELECT COUNT(*) as count FROM products').fetchone()['count']
    orders_count = conn.execute('SELECT COUNT(*) as count FROM orders').fetchone()['count']
    suppliers_count = conn.execute('SELECT COUNT(*) as count FROM suppliers').fetchone()['count']
    users_count = conn.execute('SELECT COUNT(*) as count FROM users').fetchone()['count']
    inventory_value = conn.execute('SELECT COALESCE(SUM(quantity * price), 0) as total FROM products').fetchone()['total']
    
    # Orders pending pickup (assigned to suppliers but not picked up)
    pending_pickup_count = conn.execute('''
        SELECT COUNT(*) as count FROM orders 
        WHERE supplier_id IS NOT NULL AND status = 'pending'
    ''').fetchone()['count']
    
    # Sales data for charts - Monthly sales (last 6 months)
    monthly_sales = conn.execute('''
        SELECT strftime('%Y-%m', order_date) as month, 
               SUM(total_price) as total,
               COUNT(*) as order_count
        FROM orders 
        WHERE order_date >= date('now', '-6 months')
        GROUP BY strftime('%Y-%m', order_date)
        ORDER BY month
    ''').fetchall()
    
    # Product-wise sales
    product_sales = conn.execute('''
        SELECT p.name, SUM(o.quantity) as total_qty, SUM(o.total_price) as total_sales
        FROM orders o
        JOIN products p ON o.product_id = p.id
        GROUP BY p.id
        ORDER BY total_sales DESC
        LIMIT 5
    ''').fetchall()
    
    # Supplier-wise product count
    supplier_products = conn.execute('''
        SELECT s.name, COUNT(p.id) as product_count
        FROM suppliers s
        LEFT JOIN products p ON s.id = p.supplier_id
        GROUP BY s.id
        ORDER BY product_count DESC
    ''').fetchall()
    
    # Get additional sales data
    total_sales = conn.execute('SELECT COALESCE(SUM(total_price), 0) as total FROM orders').fetchone()['total']
    total_orders = conn.execute('SELECT COUNT(*) as count FROM orders').fetchone()['count']
    avg_order_value = total_sales / total_orders if total_orders > 0 else 0
    
    # Daily sales (last 30 days)
    daily_sales = conn.execute('''
        SELECT DATE(order_date) as date, 
               SUM(total_price) as total,
               COUNT(*) as order_count
        FROM orders 
        WHERE order_date >= date('now', '-30 days')
        GROUP BY DATE(order_date)
        ORDER BY date
    ''').fetchall()
    
    # Get low stock and out of stock products
    low_stock_products = conn.execute('''
        SELECT p.*, s.name as supplier_name
        FROM products p LEFT JOIN suppliers s ON p.supplier_id = s.id
        WHERE p.quantity > 0 AND p.quantity < 10 ORDER BY p.quantity ASC
    ''').fetchall()
    
    out_of_stock_products = conn.execute('''
        SELECT p.*, s.name as supplier_name
        FROM products p LEFT JOIN suppliers s ON p.supplier_id = s.id
        WHERE p.quantity = 0 ORDER BY p.name ASC
    ''').fetchall()
    
    conn.close()
    
    stats = {
        'products': products_count,
        'orders': orders_count,
        'suppliers': suppliers_count,
        'users': users_count,
        'inventory_value': inventory_value,
        'low_stock_count': len(low_stock_products),
        'out_of_stock_count': len(out_of_stock_products),
        'pending_pickup': pending_pickup_count
    }
    
    # Prepare chart data
    chart_data = {
        'monthly_labels': [row['month'] for row in monthly_sales],
        'monthly_sales': [float(row['total']) for row in monthly_sales],
        'monthly_orders': [row['order_count'] for row in monthly_sales],
        'product_names': [row['name'] for row in product_sales],
        'product_sales': [float(row['total_sales']) for row in product_sales],
        'supplier_names': [row['name'] for row in supplier_products],
        'supplier_counts': [row['product_count'] for row in supplier_products],
        'daily_labels': [row['date'] for row in daily_sales],
        'daily_sales': [float(row['total']) for row in daily_sales],
        'total_sales': total_sales,
        'total_orders': total_orders,
        'avg_order_value': avg_order_value
    }
    
    return render_template('dashboard.html', stats=stats, chart_data=chart_data)

# Users Routes (Admin only)
@app.route('/users')
@login_required
@role_required(['admin'])
def users():
    conn = get_db_connection()
    users = conn.execute('SELECT id, username, name, dob, mobile, role FROM users ORDER BY role, username').fetchall()
    conn.close()
    return render_template('users.html', users=users)

@app.route('/users/add', methods=['GET', 'POST'])
@login_required
@role_required(['admin'])
def add_user():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        name = request.form.get('name', '')
        dob = request.form.get('dob', '')
        mobile = request.form.get('mobile', '')
        role = request.form['role']
        
        conn = get_db_connection()
        try:
            user_id = conn.execute('INSERT INTO users (username, password, name, dob, mobile, role) VALUES (?, ?, ?, ?, ?, ?)',
                        (username, password, name, dob, mobile, role)).lastrowid
            conn.commit()
            
            # If creating a supplier user, also create supplier record
            if role == 'supplier':
                supplier_name = request.form.get('supplier_name', name)
                supplier_contact = request.form.get('supplier_contact', '')
                supplier_email = request.form.get('supplier_email', '')
                supplier_phone = request.form.get('supplier_phone', '')
                
                conn.execute('''
                    INSERT INTO suppliers (name, contact, email, phone, user_id) 
                    VALUES (?, ?, ?, ?, ?)
                ''', (supplier_name, supplier_contact, supplier_email, supplier_phone, user_id))
                conn.commit()
            
            flash(f'User ({role}) added successfully!', 'success')
        except sqlite3.IntegrityError:
            flash('Username already exists!', 'error')
        finally:
            conn.close()
        
        return redirect(url_for('users'))
    
    return render_template('add_user.html', user=None)

@app.route('/users/delete/<int:id>')
@login_required
@role_required(['admin'])
def delete_user(id):
    if id == session.get('user_id'):
        flash('You cannot delete your own account!', 'error')
        return redirect(url_for('users'))
    
    conn = get_db_connection()
    conn.execute('DELETE FROM users WHERE id = ?', (id,))
    conn.commit()
    conn.close()
    
    flash('User deleted successfully!', 'success')
    return redirect(url_for('users'))

# Products Routes (Admin & Manager)
@app.route('/products')
@login_required
def products():
    conn = get_db_connection()
    products = conn.execute('''
        SELECT p.*, s.name as supplier_name 
        FROM products p 
        LEFT JOIN suppliers s ON p.supplier_id = s.id
    ''').fetchall()
    conn.close()
    return render_template('products.html', products=products)

@app.route('/products/add', methods=['GET', 'POST'])
@login_required
@role_required(['admin', 'manager'])
def add_product():
    conn = get_db_connection()
    suppliers = conn.execute('SELECT * FROM suppliers').fetchall()
    
    if request.method == 'POST':
        name = request.form['name']
        quantity = int(request.form['quantity'])
        price = float(request.form['price'])
        supplier_id = request.form['supplier_id'] if request.form['supplier_id'] else None
        
        conn.execute('INSERT INTO products (name, quantity, price, supplier_id) VALUES (?, ?, ?, ?)',
                    (name, quantity, price, supplier_id))
        conn.commit()
        conn.close()
        
        flash('Product added successfully!', 'success')
        return redirect(url_for('products'))
    
    conn.close()
    return render_template('add_product.html', suppliers=suppliers, product=None)

@app.route('/products/edit/<int:id>', methods=['GET', 'POST'])
@login_required
@role_required(['admin', 'manager'])
def edit_product(id):
    conn = get_db_connection()
    suppliers = conn.execute('SELECT * FROM suppliers').fetchall()
    product = conn.execute('SELECT * FROM products WHERE id = ?', (id,)).fetchone()
    
    if request.method == 'POST':
        name = request.form['name']
        quantity = int(request.form['quantity'])
        price = float(request.form['price'])
        supplier_id = request.form['supplier_id'] if request.form['supplier_id'] else None
        
        conn.execute('UPDATE products SET name = ?, quantity = ?, price = ?, supplier_id = ? WHERE id = ?',
                    (name, quantity, price, supplier_id, id))
        conn.commit()
        conn.close()
        
        flash('Product updated successfully!', 'success')
        return redirect(url_for('products'))
    
    conn.close()
    return render_template('add_product.html', suppliers=suppliers, product=product)

@app.route('/products/delete/<int:id>')
@login_required
@role_required(['admin', 'manager'])
def delete_product(id):
    conn = get_db_connection()
    conn.execute('DELETE FROM products WHERE id = ?', (id,))
    conn.commit()
    conn.close()
    
    flash('Product deleted successfully!', 'success')
    return redirect(url_for('products'))

# Orders Routes (All users)
@app.route('/orders')
@login_required
def orders():
    conn = get_db_connection()
    
    # If supplier, show only their assigned orders
    if session.get('role') == 'supplier':
        supplier_id = session.get('supplier_id')
        orders_list = conn.execute('''
            SELECT o.*, p.name as product_name, s.name as supplier_name, u.username as created_by_name
            FROM orders o 
            LEFT JOIN products p ON o.product_id = p.id
            LEFT JOIN suppliers s ON o.supplier_id = s.id
            LEFT JOIN users u ON o.created_by = u.id
            WHERE o.supplier_id = ?
            ORDER BY o.order_date DESC
        ''', (supplier_id,)).fetchall()
    else:
        orders_list = conn.execute('''
            SELECT o.*, p.name as product_name, s.name as supplier_name, u.username as created_by_name
            FROM orders o 
            LEFT JOIN products p ON o.product_id = p.id
            LEFT JOIN suppliers s ON o.supplier_id = s.id
            LEFT JOIN users u ON o.created_by = u.id
            ORDER BY o.order_date DESC
        ''').fetchall()
    
    conn.close()
    return render_template('orders.html', orders=orders_list)

@app.route('/orders/add', methods=['GET', 'POST'])
@login_required
def add_order():
    conn = get_db_connection()
    products = conn.execute('SELECT * FROM products WHERE quantity > 0').fetchall()
    suppliers = conn.execute('SELECT * FROM suppliers').fetchall()
    
    if request.method == 'POST':
        product_id = int(request.form['product_id'])
        quantity = int(request.form['quantity'])
        supplier_id = request.form['supplier_id'] if request.form['supplier_id'] else None
        
        product = conn.execute('SELECT price, quantity FROM products WHERE id = ?', (product_id,)).fetchone()
        
        if product and product['quantity'] >= quantity:
            total_price = product['price'] * quantity
            order_date = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            created_by = session.get('user_id')
            
            conn.execute('INSERT INTO orders (product_id, quantity, total_price, order_date, created_by, supplier_id, status) VALUES (?, ?, ?, ?, ?, ?, ?)',
                        (product_id, quantity, total_price, order_date, created_by, supplier_id, 'pending' if supplier_id else 'pending'))
            
            conn.execute('UPDATE products SET quantity = quantity - ? WHERE id = ?', (quantity, product_id))
            conn.commit()
            conn.close()
            
            flash('Order created successfully!', 'success')
            return redirect(url_for('orders'))
        else:
            conn.close()
            flash('Insufficient quantity available!', 'error')
            return redirect(url_for('add_order'))
    
    conn.close()
    return render_template('add_order.html', products=products, suppliers=suppliers)

# Mark order as picked up (for suppliers)
@app.route('/orders/pickup/<int:order_id>')
@login_required
@role_required(['supplier'])
def pickup_order(order_id):
    conn = get_db_connection()
    
    # Verify this order belongs to this supplier
    order = conn.execute('SELECT * FROM orders WHERE id = ? AND supplier_id = ?', 
                         (order_id, session.get('supplier_id'))).fetchone()
    
    if not order:
        flash('Order not found or not assigned to you!', 'error')
        conn.close()
        return redirect(url_for('orders'))
    
    if order['status'] == 'picked_up':
        flash('Order already picked up!', 'warning')
        conn.close()
        return redirect(url_for('orders'))
    
    # Update order status
    picked_up_at = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    conn.execute('''
        UPDATE orders 
        SET status = 'picked_up', picked_up_by = ?, picked_up_at = ?
        WHERE id = ?
    ''', (session.get('user_id'), picked_up_at, order_id))
    
    # Add tracking record
    conn.execute('''
        INSERT INTO order_tracking (order_id, status, notes, updated_by, updated_at)
        VALUES (?, ?, ?, ?, ?)
    ''', (order_id, 'picked_up', 'Order picked up by supplier', session.get('user_id'), picked_up_at))
    
    conn.commit()
    conn.close()
    
    flash('Order marked as picked up successfully!', 'success')
    return redirect(url_for('orders'))

# Suppliers Routes (Admin & Manager)
@app.route('/suppliers')
@login_required
def suppliers():
    conn = get_db_connection()
    suppliers = conn.execute('''
        SELECT s.*, u.username as user_username
        FROM suppliers s
        LEFT JOIN users u ON s.user_id = u.id
    ''').fetchall()
    conn.close()
    return render_template('suppliers.html', suppliers=suppliers)

@app.route('/suppliers/add', methods=['GET', 'POST'])
@login_required
@role_required(['admin', 'manager'])
def add_supplier():
    if request.method == 'POST':
        name = request.form['name']
        contact = request.form['contact']
        email = request.form['email']
        phone = request.form['phone']
        
        # Create supplier user account
        username = request.form.get('username', name.lower().replace(' ', '_'))
        password = request.form.get('password', 'supplier123')
        
        conn = get_db_connection()
        
        # Check if user already exists
        existing_user = conn.execute('SELECT * FROM users WHERE username = ?', (username,)).fetchone()
        
        if existing_user:
            # Use existing user
            user_id = existing_user['id']
        else:
            # Create new user
            user_id = conn.execute('INSERT INTO users (username, password, name, role) VALUES (?, ?, ?, ?)',
                        (username, password, name, 'supplier')).lastrowid
            conn.commit()
        
        # Create supplier record
        conn.execute('INSERT INTO suppliers (name, contact, email, phone, user_id) VALUES (?, ?, ?, ?, ?)',
                    (name, contact, email, phone, user_id))
        conn.commit()
        conn.close()
        
        flash(f'Supplier added successfully! Login: {username} / {password}', 'success')
        return redirect(url_for('suppliers'))
    
    return render_template('add_supplier.html', supplier=None)

@app.route('/suppliers/delete/<int:id>')
@login_required
@role_required(['admin', 'manager'])
def delete_supplier(id):
    conn = get_db_connection()
    
    products = conn.execute('SELECT COUNT(*) as count FROM products WHERE supplier_id = ?', (id,)).fetchone()
    if products['count'] > 0:
        flash('Cannot delete supplier with associated products!', 'error')
        conn.close()
        return redirect(url_for('suppliers'))
    
    conn.execute('DELETE FROM suppliers WHERE id = ?', (id,))
    conn.commit()
    conn.close()
    
    flash('Supplier deleted successfully!', 'success')
    return redirect(url_for('suppliers'))

# Sales Analytics Route
@app.route('/sales')
@login_required
def sales():
    conn = get_db_connection()
    
    # Monthly sales (last 12 months)
    monthly_sales = conn.execute('''
        SELECT strftime('%Y-%m', order_date) as month, 
               SUM(total_price) as total,
               COUNT(*) as order_count
        FROM orders 
        WHERE order_date >= date('now', '-12 months')
        GROUP BY strftime('%Y-%m', order_date)
        ORDER BY month
    ''').fetchall()
    
    # Product-wise sales
    product_sales = conn.execute('''
        SELECT p.name, SUM(o.quantity) as total_qty, SUM(o.total_price) as total_sales
        FROM orders o
        JOIN products p ON o.product_id = p.id
        GROUP BY p.id
        ORDER BY total_sales DESC
        LIMIT 10
    ''').fetchall()
    
    # Supplier-wise product count
    supplier_products = conn.execute('''
        SELECT s.name, COUNT(p.id) as product_count
        FROM suppliers s
        LEFT JOIN products p ON s.id = p.supplier_id
        GROUP BY s.id
        ORDER BY product_count DESC
    ''').fetchall()
    
    # Daily sales (last 30 days)
    daily_sales = conn.execute('''
        SELECT DATE(order_date) as date, 
               SUM(total_price) as total,
               COUNT(*) as order_count
        FROM orders 
        WHERE order_date >= date('now', '-30 days')
        GROUP BY DATE(order_date)
        ORDER BY date
    ''').fetchall()
    
    # Total sales stats
    total_sales = conn.execute('SELECT COALESCE(SUM(total_price), 0) as total FROM orders').fetchone()['total']
    total_orders = conn.execute('SELECT COUNT(*) as count FROM orders').fetchone()['count']
    avg_order_value = total_sales / total_orders if total_orders > 0 else 0
    
    conn.close()
    
    chart_data = {
        'monthly_labels': [row['month'] for row in monthly_sales],
        'monthly_sales': [float(row['total']) for row in monthly_sales],
        'monthly_orders': [row['order_count'] for row in monthly_sales],
        'product_names': [row['name'] for row in product_sales],
        'product_sales': [float(row['total_sales']) for row in product_sales],
        'supplier_names': [row['name'] for row in supplier_products],
        'supplier_counts': [row['product_count'] for row in supplier_products],
        'daily_labels': [row['date'] for row in daily_sales],
        'daily_sales': [float(row['total']) for row in daily_sales],
        'total_sales': total_sales,
        'total_orders': total_orders,
        'avg_order_value': avg_order_value
    }
    
    return render_template('sales.html', chart_data=chart_data)

# Order Tracking Route
@app.route('/track-order', methods=['GET', 'POST'])
@login_required
def track_order():
    search_id = None
    order = None
    
    if request.method == 'POST':
        search_id = request.form.get('order_id')
        if search_id:
            conn = get_db_connection()
            order = conn.execute('''
                SELECT o.*, p.name as product_name, u.username as created_by_name, s.name as supplier_name
                FROM orders o 
                LEFT JOIN products p ON o.product_id = p.id
                LEFT JOIN users u ON o.created_by = u.id
                LEFT JOIN suppliers s ON o.supplier_id = s.id
                WHERE o.id = ?
            ''', (search_id,)).fetchone()
            conn.close()
    
    # Get recent orders
    conn = get_db_connection()
    recent_orders = conn.execute('''
        SELECT o.*, p.name as product_name
        FROM orders o 
        LEFT JOIN products p ON o.product_id = p.id
        ORDER BY o.order_date DESC
        LIMIT 10
    ''').fetchall()
    conn.close()
    
    return render_template('track_order.html', order=order, search_id=search_id, recent_orders=recent_orders)

@app.route('/track-order/<int:order_id>')
@login_required
def track_order_by_id(order_id):
    conn = get_db_connection()
    order = conn.execute('''
        SELECT o.*, p.name as product_name, u.username as created_by_name, s.name as supplier_name,
               pu.username as picked_up_by_name
        FROM orders o 
        LEFT JOIN products p ON o.product_id = p.id
        LEFT JOIN users u ON o.created_by = u.id
        LEFT JOIN suppliers s ON o.supplier_id = s.id
        LEFT JOIN users pu ON o.picked_up_by = pu.id
        WHERE o.id = ?
    ''', (order_id,)).fetchone()
    
    recent_orders = conn.execute('''
        SELECT o.*, p.name as product_name
        FROM orders o 
        LEFT JOIN products p ON o.product_id = p.id
        ORDER BY o.order_date DESC
        LIMIT 10
    ''').fetchall()
    conn.close()
    
    return render_template('track_order.html', order=order, search_id=order_id, recent_orders=recent_orders)

# Update Order Status Route (Admin/Manager only)
@app.route('/order/update-status/<int:order_id>', methods=['POST'])
@login_required
@role_required(['admin', 'manager'])
def update_order_status(order_id):
    new_status = request.form.get('status')
    notes = request.form.get('notes', '')
    
    conn = get_db_connection()
    
    # Update order status
    conn.execute('UPDATE orders SET status = ? WHERE id = ?', (new_status, order_id))
    
    # Add tracking record
    updated_at = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    conn.execute('''
        INSERT INTO order_tracking (order_id, status, notes, updated_by, updated_at)
        VALUES (?, ?, ?, ?, ?)
    ''', (order_id, new_status, notes, session.get('user_id'), updated_at))
    
    conn.commit()
    conn.close()
    
    flash(f'Order status updated to {new_status}!', 'success')
    return redirect(url_for('track_order_by_id', order_id=order_id))

# Pending Orders Route
@app.route('/pending-orders')
@login_required
@role_required(['admin', 'manager'])
def pending_orders():
    conn = get_db_connection()
    pending_orders_list = conn.execute('''
        SELECT o.*, p.name as product_name, p.quantity as stock_qty, u.username as created_by_name, s.name as supplier_name
        FROM orders o LEFT JOIN products p ON o.product_id = p.id
        LEFT JOIN users u ON o.created_by = u.id
        LEFT JOIN suppliers s ON o.supplier_id = s.id
        WHERE o.status IN ('pending', 'processing') ORDER BY o.order_date DESC
    ''').fetchall()
    status_counts = conn.execute('SELECT status, COUNT(*) as count FROM orders GROUP BY status').fetchall()
    conn.close()
    return render_template('pending_orders.html', pending_orders=pending_orders_list, status_counts=status_counts)

# Inventory Levels Route
@app.route('/inventory')
@login_required
def inventory():
    conn = get_db_connection()
    products_list = conn.execute('''
        SELECT p.*, s.name as supplier_name,
        CASE WHEN p.quantity = 0 THEN 'Out of Stock' WHEN p.quantity < 10 THEN 'Low Stock' ELSE 'In Stock' END as stock_status
        FROM products p LEFT JOIN suppliers s ON p.supplier_id = s.id ORDER BY p.quantity ASC
    ''').fetchall()
    stock_summary = {
        'total_products': conn.execute('SELECT COUNT(*) as count FROM products').fetchone()['count'],
        'total_stock': conn.execute('SELECT COALESCE(SUM(quantity), 0) as total FROM products').fetchone()['total'],
        'out_of_stock': conn.execute('SELECT COUNT(*) as count FROM products WHERE quantity = 0').fetchone()['count'],
        'low_stock': conn.execute('SELECT COUNT(*) as count FROM products WHERE quantity > 0 AND quantity < 10').fetchone()['count'],
        'in_stock': conn.execute('SELECT COUNT(*) as count FROM products WHERE quantity >= 10').fetchone()['count']
    }
    conn.close()
    return render_template('inventory.html', products=products_list, stock_summary=stock_summary)

# Profit Reports Route
@app.route('/profit-reports')
@login_required
@role_required(['admin', 'manager'])
def profit_reports():
    conn = get_db_connection()
    total_revenue = conn.execute('SELECT COALESCE(SUM(total_price), 0) as total FROM orders WHERE status != "cancelled"').fetchone()['total']
    total_orders = conn.execute('SELECT COUNT(*) as count FROM orders WHERE status != "cancelled"').fetchone()['count']
    avg_order_value = total_revenue / total_orders if total_orders > 0 else 0
    product_revenue = conn.execute('''
        SELECT p.name, SUM(o.quantity) as total_qty_sold, SUM(o.total_price) as revenue,
        p.price as unit_price, p.quantity as current_stock FROM orders o
        JOIN products p ON o.product_id = p.id WHERE o.status != 'cancelled' GROUP BY p.id ORDER BY revenue DESC
    ''').fetchall()
    monthly_profit = conn.execute('''
        SELECT strftime('%Y-%m', order_date) as month, SUM(total_price) as revenue, COUNT(*) as order_count
        FROM orders WHERE status != 'cancelled' AND order_date >= date('now', '-6 months')
        GROUP BY strftime('%Y-%m', order_date) ORDER BY month
    ''').fetchall()
    orders_by_status = conn.execute('SELECT status, COUNT(*) as count, COALESCE(SUM(total_price), 0) as total FROM orders GROUP BY status').fetchall()
    conn.close()
    profit_data = {'total_revenue': total_revenue, 'total_orders': total_orders, 'avg_order_value': avg_order_value,
        'product_revenue': product_revenue, 'monthly_profit': monthly_profit, 'orders_by_status': orders_by_status}
    return render_template('profit_reports.html', profit_data=profit_data)

# === CHAT ROUTES ===
@app.route('/chat')
@login_required
def chat():
    return render_template('chat.html')

@app.route('/api/users')
@login_required
def api_users():
    conn = get_db_connection()
    users = conn.execute('''
        SELECT id, username, role FROM users 
        WHERE id != ? ORDER BY username
    ''', (session['user_id'],)).fetchall()
    conn.close()
    
    # Mark online users
    user_list = []
    for user in users:
        user_list.append({
            'id': user['id'],
            'username': user['username'],
            'role': user['role'],
            'online': user['id'] in online_users
        })
    
    return jsonify(user_list)

@app.route('/api/messages/<int:partner_id>')
@login_required
def api_messages(partner_id):
    user1 = min(session['user_id'], partner_id)
    user2 = max(session['user_id'], partner_id)
    
    conn = get_db_connection()
    chat = conn.execute('''
        SELECT id FROM chats WHERE (user1_id = ? AND user2_id = ?) OR (user1_id = ? AND user2_id = ?)
    ''', (user1, user2, user2, user1)).fetchone()
    
    chat_id = chat['id'] if chat else None
    
    if chat_id:
        messages = conn.execute('''
            SELECT m.*, u.username FROM messages m
            JOIN users u ON m.sender_id = u.id
            WHERE m.chat_id = ? ORDER BY m.timestamp ASC
        ''', (chat_id,)).fetchall()
    else:
        messages = []
    
    conn.close()
    return jsonify([dict(msg) for msg in messages])

@app.route('/api/messages/<int:message_id>/read', methods=['POST'])
@login_required
def api_mark_read(message_id):
    conn = get_db_connection()
    conn.execute('UPDATE messages SET is_read = 1 WHERE id = ? AND chat_id IN (SELECT id FROM chats WHERE user1_id = ? OR user2_id = ?)', 
                (message_id, session['user_id'], session['user_id']))
    conn.commit()
    conn.close()
    return jsonify({'success': True})

# === SOCKETIO EVENTS ===
@sio.on('connect')
def handle_connect():
    if 'user_id' in session:
        online_users.add(int(session['user_id']))
        emit('user_online', {'user_id': session['user_id']}, broadcast=True)

@sio.on('disconnect')
def handle_disconnect():
    if 'user_id' in session:
        user_id = int(session['user_id'])
        if user_id in online_users:
            online_users.remove(user_id)
            emit('user_offline', {'user_id': user_id}, broadcast=True)

@sio.on('join_chat')
def handle_join_chat(data):
    room = data.get('chat_id')
    if room:
        join_room(room)
        emit('status', {'msg': f'Joined chat {room}'})

@sio.on('send_message')
def handle_send_message(data):
    chat_id = data.get('chat_id')
    partner_id = data.get('partner_id')
    content = data.get('content')
    
    if not all([chat_id, partner_id, content, 'user_id' in session]):
        return
    
    sender_id = session['user_id']
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    
    conn = get_db_connection()
    
    # Get or create chat
    user1 = min(sender_id, partner_id)
    user2 = max(sender_id, partner_id)
    chat = conn.execute('''
        SELECT id FROM chats WHERE (user1_id = ? AND user2_id = ?) OR (user1_id = ? AND user2_id = ?)
    ''', (user1, user2, user2, user1)).fetchone()
    
    if chat:
        chat_id = chat['id']
    else:
        conn.execute('INSERT INTO chats (user1_id, user2_id) VALUES (?, ?)', (user1, user2))
        chat_id = conn.lastrowid
        conn.commit()
    
    # Save message
    message_id = conn.execute('''
        INSERT INTO messages (chat_id, sender_id, content) VALUES (?, ?, ?)
    ''', (chat_id, sender_id, content)).lastrowid
    
    conn.commit()
    conn.close()
    
    # Emit to room
    message_data = {
        'message_id': message_id,
        'chat_id': chat_id,
        'sender_id': sender_id,
        'content': content,
        'timestamp': timestamp
    }
    emit('message', message_data, room=f'chat_{user1}_{user2}')

@sio.on('typing')
def handle_typing(data):
    chat_id = data.get('chat_id')
    emit('typing', {'username': session.get('username')}, room=chat_id)

@sio.on('stop_typing')
def handle_stop_typing(data):
    chat_id = data.get('chat_id')
    emit('stop_typing', {}, room=chat_id)

if __name__ == '__main__':
    os.makedirs(os.path.join(os.path.dirname(__file__), 'instance'), exist_ok=True)
    init_db()
    
    print("=" * 50)
    print("Micro ERP System Starting...")
    print("=" * 50)
    print("🚀 NEW: Live Chat Feature!")
    print("  - Real-time 1-on-1 messaging")
    print("  - Online status indicators") 
    print("  - Chat from sidebar")
    print("=" * 50)
    print("Features:")
    print("  - Admin creates Manager/Staff accounts")
    print("  - Supplier can pick up orders")
    print("  - Role-based access control") 
    print("  - Supplier notification on login")
    print("  - 💬 Live Chat between users")
    print("=" * 50)
    print("Default credentials:")
    print("  Admin: admin / admin123")
    print("  Supplier: supplier / supplier123")
    print("=" * 50)
    print("Access URL: http://127.0.0.1:5000")
    print("=" * 50)
    sio.run(app, host='0.0.0.0', port=5000, debug=True)
