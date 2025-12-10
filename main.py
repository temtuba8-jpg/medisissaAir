from flask import Flask, render_template, request, redirect, url_for, session, flash
from pymongo import MongoClient
from urllib.parse import quote_plus
import qrcode
import io
import base64
import sys

app = Flask(__name__)
app.secret_key = "secretkey123"

# =====================
# إعداد اتصال MongoDB Atlas
# =====================
username = "sahoor"
password = "Fad@0911923356"
password_escaped = quote_plus(password)
cluster = "cluster1.6wgwgl5.mongodb.net"
database_name = "sahoor"

uri = f"mongodb+srv://{username}:{password_escaped}@{cluster}/{database_name}?retryWrites=true&w=majority"

try:
    client = MongoClient(uri, serverSelectionTimeoutMS=10000)
    db = client[database_name]
    users_col = db.users
    tickets_col = db.tickets
    players_col = db.players
    ads_col = db.ads
    client.server_info()  # التأكد من الاتصال
    print("✅ تم الاتصال بقاعدة البيانات بنجاح")
except Exception as e:
    print("⚠️ لم يتم الاتصال بقاعدة البيانات")
    print("Error:", e)
    sys.exit(1)

# =====================
# Helpers
# =====================
def generate_qr(data):
    qr = qrcode.QRCode(box_size=8, border=2)
    qr.add_data(data)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    buffer = io.BytesIO()
    img.save(buffer, format="PNG")
    return base64.b64encode(buffer.getvalue()).decode("utf-8")

def find(collection, query={}):
    return list(db[collection].find(query))

def insert_one(collection, document):
    return db[collection].insert_one(document)

def get_next_ticket_number():
    tickets = list(tickets_col.find())
    if tickets:
        last_ticket = max(tickets, key=lambda x: x["ticket_number"])
        return last_ticket["ticket_number"] + 1
    return 1

# =====================
# إنشاء حساب أدمن افتراضي
# =====================
def ensure_admin():
    if users_col.count_documents({"username": "admin"}) == 0:
        admin_user = {
            "username": "admin",
            "password": "admin123",
            "full_name": "مدير النادي",
            "phone": "0000000000",
            "national_id": "000000000000",
            "address": "المدينة",
            "photo_url": "",
            "role": "admin"
        }
        users_col.insert_one(admin_user)
        print("✅ تم إنشاء حساب الأدمن الافتراضي: admin / admin123")
    else:
        print("ℹ️ حساب الأدمن موجود بالفعل.")

# =====================
# Routes
# =====================
@app.route("/")
def index():
    players = find("players")
    ads = find("ads")
    return render_template("index.html", players=players, ads=ads, user=session.get("user"))

@app.route("/admin")
def admin_dashboard():
    if "user" not in session or session["user"]["role"] != "admin":
        flash("❌ لا تمتلك صلاحية الوصول لهذه الصفحة")
        return redirect(url_for("login"))
    users = find("users")
    tickets = find("tickets")
    return render_template("admin.html", users=users, tickets=tickets, user=session.get("user"))

@app.route("/user")
def user_dashboard():
    if "user" not in session or session["user"]["role"] != "user":
        flash("❌ يجب تسجيل الدخول كمستخدم للوصول لهذه الصفحة")
        return redirect(url_for("login"))
    return render_template("user.html", user=session.get("user"))

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]
        user = users_col.find_one({"username": username, "password": password})
        if user:
            session["user"] = {
                "username": user["username"],
                "role": user.get("role", "user")
            }
            flash(f"✅ تم تسجيل الدخول بنجاح كـ {user['username']}")
            if user.get("role") == "admin":
                return redirect(url_for("admin_dashboard"))
            else:
                return redirect(url_for("user_dashboard"))
        else:
            flash("❌ اسم المستخدم أو كلمة المرور خاطئة")
            return redirect(url_for("login"))
    return render_template("login.html", user=session.get("user"))

@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]
        full_name = request.form.get("full_name", "")
        phone = request.form.get("phone", "")
        if users_col.find_one({"username": username}):
            flash("❌ اسم المستخدم موجود بالفعل")
            return redirect(url_for("register"))
        new_user = {
            "username": username,
            "password": password,
            "full_name": full_name,
            "phone": phone,
            "role": "user"
        }
        users_col.insert_one(new_user)
        flash(f"✅ تم إنشاء الحساب بنجاح: {username}")
        return redirect(url_for("login"))
    return render_template("register.html", user=session.get("user"))

@app.route("/logout")
def logout():
    session.pop("user", None)
    flash("✅ تم تسجيل الخروج")
    return redirect(url_for("index"))

@app.route("/tickets/new", methods=["POST"])
def new_ticket():
    if "user" not in session:
        flash("❌ يجب تسجيل الدخول لإنشاء تذكرة")
        return redirect(url_for("login"))
    ticket_number = get_next_ticket_number()
    ticket_data = {
        "ticket_number": ticket_number,
        "user": session["user"]["username"]
    }
    insert_one("tickets", ticket_data)
    qr_code = generate_qr(str(ticket_number))
    return render_template("ticket.html", ticket=ticket_data, qr_code=qr_code, user=session.get("user"))

# =====================
# Run Server
# =====================from flask import Flask, render_template, request, redirect, url_for, session, flash
from pymongo import MongoClient
from urllib.parse import quote_plus
import qrcode
import io
import base64
import sys

app = Flask(__name__)
app.secret_key = "secretkey123"

# =====================
# إعداد اتصال MongoDB Atlas
# =====================
username = "sahoor"
password = "Fad@0911923356"
password_escaped = quote_plus(password)
cluster = "cluster1.6wgwgl5.mongodb.net"
database_name = "sahoor"

uri = f"mongodb+srv://{username}:{password_escaped}@{cluster}/{database_name}?retryWrites=true&w=majority"

try:
    client = MongoClient(uri, serverSelectionTimeoutMS=10000)
    db = client[database_name]
    users_col = db.users
    tickets_col = db.tickets
    players_col = db.players
    ads_col = db.ads
    client.server_info()
    print("✅ تم الاتصال بقاعدة البيانات بنجاح")
except Exception as e:
    print("⚠️ لم يتم الاتصال بقاعدة البيانات")
    print("Error:", e)
    sys.exit(1)

# =====================
# Helpers
# =====================
def generate_qr(data):
    qr = qrcode.QRCode(box_size=8, border=2)
    qr.add_data(data)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    buffer = io.BytesIO()
    img.save(buffer, format="PNG")
    return base64.b64encode(buffer.getvalue()).decode("utf-8")

def find(collection, query={}):
    return list(db[collection].find(query))

def insert_one(collection, document):
    return db[collection].insert_one(document)

def get_next_ticket_number():
    tickets = list(tickets_col.find())
    if tickets:
        last_ticket = max(tickets, key=lambda x: x["ticket_number"])
        return last_ticket["ticket_number"] + 1
    return 1

# =====================
# Routes
# =====================
@app.route("/")
def index():
    # صفحة عامة للزوار فقط
    players = find("players")
    ads = find("ads")
    return render_template("index.html", players=players, ads=ads, user=session.get("user"))

@app.route("/admin")
def admin_dashboard():
    if "user" not in session or session["user"]["role"] != "admin":
        flash("❌ لا تمتلك صلاحية الوصول لهذه الصفحة")
        return redirect(url_for("login"))
    users = find("users")
    tickets = find("tickets")
    return render_template("admin.html", users=users, tickets=tickets, user=session.get("user"))

@app.route("/user")
def user_dashboard():
    if "user" not in session or session["user"]["role"] != "user":
        flash("❌ يجب تسجيل الدخول كمستخدم للوصول لهذه الصفحة")
        return redirect(url_for("login"))
    return render_template("user.html", user=session.get("user"))

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]

        # ===============================
        # التحقق من الأدمن مباشرة
        # ===============================
        if username == "admin" and password == "22@22":
            session["user"] = {
                "username": "admin",
                "role": "admin"
            }
            flash("✅ تم تسجيل الدخول كأدمن")
            return redirect(url_for("admin_dashboard"))

        # ===============================
        # التحقق من المستخدمين العاديين
        # ===============================
        user = users_col.find_one({"username": username, "password": password})
        if user:
            session["user"] = {
                "username": user["username"],
                "role": "user"
            }
            flash(f"✅ تم تسجيل الدخول بنجاح كـ {user['username']}")
            return redirect(url_for("user_dashboard"))

        # بيانات خاطئة
        flash("❌ اسم المستخدم أو كلمة المرور خاطئة")
        return render_template("login.html")

    return render_template("login.html")

@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]
        full_name = request.form.get("full_name", "")
        phone = request.form.get("phone", "")
        if users_col.find_one({"username": username}):
            flash("❌ اسم المستخدم موجود بالفعل")
            return redirect(url_for("register"))
        new_user = {
            "username": username,
            "password": password,
            "full_name": full_name,
            "phone": phone,
            "role": "user"
        }
        users_col.insert_one(new_user)
        flash(f"✅ تم إنشاء الحساب بنجاح: {username}")
        return redirect(url_for("login"))
    return render_template("register.html")

@app.route("/logout")
def logout():
    session.pop("user", None)
    flash("✅ تم تسجيل الخروج")
    return redirect(url_for("login"))

@app.route("/tickets/new", methods=["POST"])
def new_ticket():
    if "user" not in session:
        flash("❌ يجب تسجيل الدخول لإنشاء تذكرة")
        return redirect(url_for("login"))
    ticket_number = get_next_ticket_number()
    ticket_data = {
        "ticket_number": ticket_number,
        "user": session["user"]["username"]
    }
    insert_one("tickets", ticket_data)
    qr_code = generate_qr(str(ticket_number))
    return render_template("ticket.html", ticket=ticket_data, qr_code=qr_code, user=session.get("user"))

# =====================
# Run Server
# =====================
if __name__ == "__main__":
    print("كل المستخدمين الحاليين:", find("users"))
    app.run(host="0.0.0.0", port=5000, debug=True)

if __name__ == "__main__":
    ensure_admin()
    print("كل المستخدمين الحاليين:", find("users"))
    app.run(host="0.0.0.0", port=5000, debug=True)

