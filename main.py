from flask import Flask, render_template, request, redirect, url_for, session, flash
from pymongo import MongoClient
from urllib.parse import quote_plus
import qrcode
import io
import base64
import sys
import traceback
from datetime import datetime, timedelta

app = Flask(__name__)
app.secret_key = "secretkey123"

# =====================
# إعدادات الجلسة
# =====================
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SECURE'] = False
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
app.permanent_session_lifetime = timedelta(days=1)

# =====================
# إعدادات MongoDB
# =====================
username = "sahoor"
password = "Fad@0911923356"
password_escaped = quote_plus(password)
cluster = "cluster1.6wgwgl5.mongodb.net"
database_name = "sahoor"
uri = f"mongodb+srv://{username}:{password_escaped}@{cluster}/{database_name}?retryWrites=true&w=majority"

def get_db():
    try:
        client = MongoClient(uri, serverSelectionTimeoutMS=10000)
        db = client[database_name]
        return db
    except Exception as e:
        print("❌ MongoDB Connection Failed")
        print("Error:", e)
        sys.exit(1)

# =====================
# Helpers
# =====================
def save_photo_to_db(photo_file):
    try:
        data = photo_file.read()
        b64 = base64.b64encode(data).decode("utf-8")
        return f"data:image/png;base64,{b64}"
    except Exception:
        traceback.print_exc()
        return ""

def generate_qr_base64(data):
    try:
        qr = qrcode.QRCode(box_size=6, border=2)
        qr.add_data(data)
        qr.make(fit=True)
        img = qr.make_image(fill_color="black", back_color="white")
        buffer = io.BytesIO()
        img.save(buffer)
        b64 = base64.b64encode(buffer.getvalue()).decode("utf-8")
        return f"data:image/png;base64,{b64}"
    except Exception:
        traceback.print_exc()
        return ""

def get_next_card_number(users_col):
    try:
        users = list(users_col.find({}, {"card_number": 1}))
        if users:
            last = max((u.get("card_number", 0) for u in users), default=0)
            return last + 1
    except Exception:
        traceback.print_exc()
    return 1

# =====================
# كلمة سر الأدمن
# =====================
ADMIN_PASSWORD = "22@22"

# =====================
# Routes
# =====================

@app.route("/")
def index():
    db = get_db()
    players_col = db.players
    ads_col = db.ads
    try:
        players = list(players_col.find())
    except Exception:
        traceback.print_exc()
        players = []

    try:
        ads = list(ads_col.find())
    except Exception:
        traceback.print_exc()
        ads = []

    return render_template("index.html", players=players, ads=ads)

@app.route("/login", methods=["GET", "POST"])
def login():
    db = get_db()
    users_col = db.users

    if request.method == "POST":
        username = (request.form.get("username") or "").strip()
        password = (request.form.get("password") or "").strip()

        if not username or not password:
            flash("❌ الرجاء تعبئة جميع الحقول")
            return redirect(url_for("login"))

        try:
            user = users_col.find_one({"username": username})
        except Exception:
            traceback.print_exc()
            user = None

        if user and user.get("password") == password:
            session["user"] = {"username": username, "role": "user"}
            session.permanent = True
            flash(f"✅ تسجيل الدخول ناجح (user)")
            return redirect(url_for("user_page"))

        flash("❌ اسم المستخدم أو كلمة المرور غير صحيحة")
        return redirect(url_for("login"))

    return render_template("login.html")

# باقي الـ routes كما هي بدون أي تعديل...

# =====================
# لا تضع app.run عند التشغيل على Render
# Render سيشغل الـ app تلقائيًا
# =====================

# يمكنك اختبار تسجيل جميع الـ routes
print("Routes registered:")
for rule in app.url_map.iter_rules():
    print(rule.endpoint, rule)
