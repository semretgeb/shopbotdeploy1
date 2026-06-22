import sqlite3

DB_NAME = "shopbot.db"

def init_db():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS shops (
        owner_id TEXT PRIMARY KEY,
        shop_name TEXT,
        delivery_info TEXT,
        payment_methods TEXT,
        payment_number TEXT
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS products (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        owner_id TEXT,
        name TEXT,
        price TEXT,
        description TEXT
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS conversations (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        customer_id TEXT,
        owner_id TEXT,
        role TEXT,
        message TEXT,
        timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS orders (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        customer_id TEXT,
        customer_name TEXT,
        owner_id TEXT,
        product TEXT,
        amount TEXT,
        address TEXT,
        status TEXT DEFAULT "pending_payment",
        timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
    )''')
    conn.commit()
    conn.close()

def save_shop(owner_id, shop_name, delivery, payment, payment_number):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute('''INSERT OR REPLACE INTO shops VALUES (?,?,?,?,?)''',
              (owner_id, shop_name, delivery, payment, payment_number))
    conn.commit()
    conn.close()

def add_product(owner_id, name, price, description):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute('''INSERT INTO products (owner_id, name, price, description)
                 VALUES (?,?,?,?)''',
              (owner_id, name, price, description))
    conn.commit()
    conn.close()

def get_shop_context(owner_id):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("SELECT * FROM shops WHERE owner_id=?", (owner_id,))
    shop = c.fetchone()
    c.execute("SELECT name, price, description FROM products WHERE owner_id=?", (owner_id,))
    products = c.fetchall()
    conn.close()
    return shop, products

def save_message(customer_id, owner_id, role, message):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute('''INSERT INTO conversations (customer_id, owner_id, role, message)
                 VALUES (?,?,?,?)''',
              (customer_id, owner_id, role, message))
    conn.commit()
    conn.close()

def get_conversation_history(customer_id, owner_id, limit=10):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute('''SELECT role, message FROM conversations 
                 WHERE customer_id=? AND owner_id=?
                 ORDER BY timestamp DESC LIMIT ?''',
              (customer_id, owner_id, limit))
    rows = c.fetchall()
    conn.close()
    rows.reverse()
    return [{"role": row[0], "content": row[1]} for row in rows]

def shop_exists(owner_id):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("SELECT shop_name FROM shops WHERE owner_id=?", (owner_id,))
    result = c.fetchone()
    conn.close()
    return result is not None

def delete_shop(owner_id):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("DELETE FROM shops WHERE owner_id=?", (owner_id,))
    c.execute("DELETE FROM products WHERE owner_id=?", (owner_id,))
    conn.commit()
    conn.close()

def create_order(customer_id, customer_name, owner_id, product, amount, address):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute('''INSERT INTO orders (customer_id, customer_name, owner_id, product, amount, address)
                 VALUES (?,?,?,?,?,?)''',
              (customer_id, customer_name, owner_id, product, amount, address))
    order_id = c.lastrowid
    conn.commit()
    conn.close()
    return order_id

def update_order_status(order_id, status):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("UPDATE orders SET status=? WHERE id=?", (status, order_id))
    conn.commit()
    conn.close()

def get_order(order_id):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("SELECT * FROM orders WHERE id=?", (order_id,))
    order = c.fetchone()
    conn.close()
    return order

def get_pending_orders(owner_id):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute('''SELECT * FROM orders 
                 WHERE owner_id=? AND status="pending_verification"
                 ORDER BY timestamp DESC''', (owner_id,))
    orders = c.fetchall()
    conn.close()
    return orders
