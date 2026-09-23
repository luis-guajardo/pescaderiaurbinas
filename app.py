from datetime import datetime
from functools import wraps
from pathlib import Path
import sqlite3

from flask import Flask, flash, g, jsonify, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash
from werkzeug.utils import secure_filename

BASE_DIR = Path(__file__).resolve().parent
DATABASE = BASE_DIR / "pescaderia.db"

app = Flask(__name__)
app.config["SECRET_KEY"] = "cambia-esta-clave-en-produccion"
app.config["DATABASE"] = DATABASE
app.config["UPLOAD_FOLDER"] = BASE_DIR / "static" / "products"


def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(app.config["DATABASE"])
        g.db.row_factory = sqlite3.Row
    return g.db


@app.teardown_appcontext
def close_db(_error=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db():
    db = get_db()
    db.executescript(
        """
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT NOT NULL UNIQUE,
            password_hash TEXT NOT NULL,
            role TEXT NOT NULL CHECK (role IN ('seller', 'buyer'))
        );
        CREATE TABLE IF NOT EXISTS products (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            category TEXT NOT NULL,
            description TEXT DEFAULT '',
            price REAL NOT NULL CHECK (price >= 0),
            stock REAL NOT NULL DEFAULT 0 CHECK (stock >= 0),
            unit TEXT NOT NULL DEFAULT 'kg',
            image_path TEXT DEFAULT '',
            active INTEGER NOT NULL DEFAULT 1
        );
        CREATE TABLE IF NOT EXISTS vouchers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            code TEXT NOT NULL UNIQUE,
            description TEXT NOT NULL,
            discount_percent REAL NOT NULL CHECK (discount_percent >= 0 AND discount_percent <= 100),
            valid_until TEXT NOT NULL,
            active INTEGER NOT NULL DEFAULT 1
        );
        CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            buyer_id INTEGER NOT NULL,
            voucher_id INTEGER,
            status TEXT NOT NULL DEFAULT 'Pendiente',
            total REAL NOT NULL,
            created_at TEXT NOT NULL,
            FOREIGN KEY (buyer_id) REFERENCES users (id),
            FOREIGN KEY (voucher_id) REFERENCES vouchers (id)
        );
        CREATE TABLE IF NOT EXISTS order_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            order_id INTEGER NOT NULL,
            product_id INTEGER NOT NULL,
            quantity REAL NOT NULL,
            unit_price REAL NOT NULL,
            FOREIGN KEY (order_id) REFERENCES orders (id),
            FOREIGN KEY (product_id) REFERENCES products (id)
        );
        """
    )
    product_columns = {row[1] for row in db.execute("PRAGMA table_info(products)").fetchall()}
    if "image_path" not in product_columns:
        db.execute("ALTER TABLE products ADD COLUMN image_path TEXT DEFAULT ''")
    seller_accounts = [
        ("Bastian Urbina", "bastian@urbina.cl"),
        ("Ignacio Urbina", "ignacio@urbinas.cl"),
        ("Lorena Urbina", "lorena@urbina.cl"),
    ]
    db.execute("DELETE FROM users WHERE email = ?", ("vendedor@urbinas.local",))
    for seller_name, seller_email in seller_accounts:
        seller = db.execute("SELECT id FROM users WHERE email = ?", (seller_email,)).fetchone()
        if seller is None:
            db.execute(
                "INSERT INTO users (name, email, password_hash, role) VALUES (?, ?, ?, ?)",
                (seller_name, seller_email, generate_password_hash("12345678"), "seller"),
            )
    buyer = db.execute("SELECT id FROM users WHERE email = ?", ("cliente@urbinas.local",)).fetchone()
    if buyer is None:
        db.execute(
            "INSERT INTO users (name, email, password_hash, role) VALUES (?, ?, ?, ?)",
            ("Cliente de prueba", "cliente@urbinas.local", generate_password_hash("cliente123"), "buyer"),
        )
    if db.execute("SELECT COUNT(*) AS total FROM products").fetchone()["total"] == 0:
        db.executemany(
            "INSERT INTO products (name, category, description, price, stock, unit) VALUES (?, ?, ?, ?, ?, ?)",
            [
                ("Reineta", "Pescado", "Reineta fresca, lista para preparar.", 5800.00, 30, "kg"),
                ("Salmon", "Pescado", "Salmon fresco de seleccion.", 16800.00, 25, "kg"),
                ("Pescada", "Pescado", "Pescada fresca, lista para preparar.", 3400.00, 30, "kg"),
                ("Choritos", "Mariscos", "Choritos frescos y refrigerados.", 1800.00, 20, "kg"),
                ("Almejas", "Mariscos", "Almejas frescas del dia.", 2400.00, 18, "kg"),
                ("Choro Malton", "Mariscos", "Choro Malton fresco del dia.", 2400.00, 18, "kg"),
            ],
        )
    if db.execute("SELECT COUNT(*) AS total FROM vouchers").fetchone()["total"] == 0:
        db.execute(
            "INSERT INTO vouchers (code, description, discount_percent, valid_until) VALUES (?, ?, ?, ?)",
            ("BIENVENIDA10", "Descuento de bienvenida", 10, "2026-12-31"),
        )
    db.commit()


def login_required(view):
    @wraps(view)
    def wrapped_view(**kwargs):
        if g.user is None:
            return redirect(url_for("login"))
        return view(**kwargs)

    return wrapped_view


def role_required(role):
    def decorator(view):
        @wraps(view)
        def wrapped_view(**kwargs):
            if g.user is None:
                return redirect(url_for("login"))
            if g.user["role"] != role:
                flash("No tienes permisos para acceder a esa sección.", "error")
                return redirect(url_for("index"))
            return view(**kwargs)

        return wrapped_view

    return decorator


@app.before_request
def load_user():
    user_id = session.get("user_id")
    g.user = get_db().execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone() if user_id else None


@app.context_processor
def inject_cart_count():
    return {
        "cart_count": sum(item["quantity"] for item in session.get("cart", {}).values()),
        "database_version": app.config["DATABASE"].stat().st_mtime_ns,
    }


@app.template_filter("clp")
def format_clp(value):
    return f"${int(round(float(value))):,}".replace(",", ".")


@app.get("/api/version")
def database_version():
    return jsonify(version=app.config["DATABASE"].stat().st_mtime_ns)


@app.route("/")
def index():
    products = get_db().execute("SELECT * FROM products WHERE active = 1 ORDER BY category, name").fetchall()
    return render_template("index.html", products=products)


@app.route("/login", methods=("GET", "POST"))
def login():
    if request.method == "POST":
        user = get_db().execute("SELECT * FROM users WHERE email = ?", (request.form["email"].strip().lower(),)).fetchone()
        if user and check_password_hash(user["password_hash"], request.form["password"]):
            session.clear()
            session["user_id"] = user["id"]
            return redirect(url_for("seller_dashboard" if user["role"] == "seller" else "index"))
        flash("Correo o contraseña incorrectos.", "error")
    return render_template("login.html")


@app.route("/registro", methods=("GET", "POST"))
def register():
    if request.method == "POST":
        name = request.form["name"].strip()
        email = request.form["email"].strip().lower()
        password = request.form["password"]
        if not name or len(password) < 6:
            flash("Completa tu nombre y usa una contraseña de al menos 6 caracteres.", "error")
            return render_template("register.html")
        db = get_db()
        try:
            db.execute(
                "INSERT INTO users (name, email, password_hash, role) VALUES (?, ?, ?, ?)",
                (name, email, generate_password_hash(password), "buyer"),
            )
            db.commit()
        except sqlite3.IntegrityError:
            flash("Ese correo ya tiene una cuenta.", "error")
            return render_template("register.html")
        flash("Cuenta creada. Ya puedes iniciar sesión.", "success")
        return redirect(url_for("login"))
    return render_template("register.html")


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("index"))


@app.post("/cart/add/<int:product_id>")
def add_to_cart(product_id):
    product = get_db().execute("SELECT * FROM products WHERE id = ? AND active = 1", (product_id,)).fetchone()
    if product is None:
        flash("Producto no disponible.", "error")
        return redirect(url_for("index"))
    cart = session.setdefault("cart", {})
    item = cart.setdefault(str(product_id), {"name": product["name"], "price": product["price"], "unit": product["unit"], "quantity": 0})
    item["quantity"] += float(request.form.get("quantity", 1))
    session.modified = True
    flash(f"{product['name']} agregado al pedido.", "success")
    return redirect(url_for("index"))


@app.route("/cart")
def cart():
    return render_template("cart.html", cart=session.get("cart", {}))


@app.post("/cart/remove/<product_id>")
def remove_from_cart(product_id):
    session.get("cart", {}).pop(str(product_id), None)
    session.modified = True
    return redirect(url_for("cart"))


@app.post("/orders/create")
@role_required("buyer")
def create_order():
    cart = session.get("cart", {})
    if not cart:
        flash("Agrega al menos un producto.", "error")
        return redirect(url_for("cart"))
    db = get_db()
    voucher = db.execute(
        "SELECT * FROM vouchers WHERE code = ? AND active = 1 AND valid_until >= date('now')",
        (request.form.get("voucher", "").strip().upper(),),
    ).fetchone()
    subtotal = sum(item["price"] * item["quantity"] for item in cart.values())
    total = round(subtotal * (1 - (voucher["discount_percent"] / 100 if voucher else 0)), 2)
    order = db.execute(
        "INSERT INTO orders (buyer_id, voucher_id, status, total, created_at) VALUES (?, ?, ?, ?, ?)",
        (g.user["id"], voucher["id"] if voucher else None, "Pendiente", total, datetime.now().isoformat(timespec="minutes")),
    )
    for product_id, item in cart.items():
        db.execute("INSERT INTO order_items (order_id, product_id, quantity, unit_price) VALUES (?, ?, ?, ?)", (order.lastrowid, product_id, item["quantity"], item["price"]))
    db.commit()
    session.pop("cart", None)
    flash("Pedido registrado correctamente.", "success")
    return redirect(url_for("buyer_orders"))


@app.route("/mis-pedidos")
@role_required("buyer")
def buyer_orders():
    orders = get_db().execute("SELECT * FROM orders WHERE buyer_id = ? ORDER BY created_at DESC", (g.user["id"],)).fetchall()
    return render_template("buyer_orders.html", orders=orders)


@app.route("/vendedor")
@role_required("seller")
def seller_dashboard():
    db = get_db()
    products = db.execute("SELECT * FROM products ORDER BY active DESC, name").fetchall()
    orders = db.execute("SELECT orders.*, users.name AS buyer_name FROM orders JOIN users ON users.id = orders.buyer_id ORDER BY created_at DESC").fetchall()
    order_items = {
        order["id"]: db.execute(
            "SELECT order_items.*, products.name AS product_name, products.unit FROM order_items JOIN products ON products.id = order_items.product_id WHERE order_items.order_id = ?",
            (order["id"],),
        ).fetchall()
        for order in orders
    }
    vouchers = db.execute("SELECT * FROM vouchers ORDER BY valid_until DESC").fetchall()
    return render_template("seller.html", products=products, orders=orders, order_items=order_items, vouchers=vouchers)


@app.post("/vendedor/productos")
@role_required("seller")
def create_product():
    db = get_db()
    image = request.files.get("image")
    image_path = ""
    if image and image.filename:
        safe_name = secure_filename(image.filename)
        if safe_name:
            app.config["UPLOAD_FOLDER"].mkdir(parents=True, exist_ok=True)
            image_path = f"products/{datetime.now().strftime('%Y%m%d%H%M%S')}_{safe_name}"
            image.save(BASE_DIR / "static" / image_path)
    db.execute("INSERT INTO products (name, category, description, price, stock, unit, image_path) VALUES (?, ?, ?, ?, ?, ?, ?)", (request.form["name"], request.form["category"], request.form["description"], float(request.form["price"]), float(request.form["stock"]), request.form["unit"], image_path))
    db.commit()
    return redirect(url_for("seller_dashboard"))


@app.post("/vendedor/productos/<int:product_id>/editar")
@role_required("seller")
def update_product(product_id):
    db = get_db()
    product = db.execute("SELECT image_path FROM products WHERE id = ?", (product_id,)).fetchone()
    if product is None:
        flash("Producto no encontrado.", "error")
        return redirect(url_for("seller_dashboard"))
    image_path = product["image_path"] or ""
    image = request.files.get("image")
    if image and image.filename:
        safe_name = secure_filename(image.filename)
        if safe_name:
            app.config["UPLOAD_FOLDER"].mkdir(parents=True, exist_ok=True)
            image_path = f"products/{datetime.now().strftime('%Y%m%d%H%M%S')}_{safe_name}"
            image.save(BASE_DIR / "static" / image_path)
    db.execute(
        "UPDATE products SET name = ?, category = ?, description = ?, price = ?, stock = ?, unit = ?, image_path = ? WHERE id = ?",
        (request.form["name"], request.form["category"], request.form["description"], float(request.form["price"]), float(request.form["stock"]), request.form["unit"], image_path, product_id),
    )
    db.commit()
    flash("Producto actualizado.", "success")
    return redirect(url_for("seller_dashboard"))


@app.post("/vendedor/productos/<int:product_id>/eliminar")
@role_required("seller")
def delete_product(product_id):
    db = get_db()
    db.execute("DELETE FROM products WHERE id = ?", (product_id,))
    db.commit()
    flash("Producto eliminado del catalogo.", "success")
    return redirect(url_for("seller_dashboard"))


@app.post("/vendedor/vales")
@role_required("seller")
def create_voucher():
    db = get_db()
    db.execute("INSERT INTO vouchers (code, description, discount_percent, valid_until) VALUES (?, ?, ?, ?)", (request.form["code"].strip().upper(), request.form["description"], float(request.form["discount_percent"]), request.form["valid_until"]))
    db.commit()
    return redirect(url_for("seller_dashboard"))


@app.post("/vendedor/pedidos/<int:order_id>/estado")
@role_required("seller")
def update_order_status(order_id):
    get_db().execute("UPDATE orders SET status = ? WHERE id = ?", (request.form["status"], order_id))
    get_db().commit()
    return redirect(url_for("seller_dashboard"))


with app.app_context():
    init_db()


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
