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
# إعدادات الجلسة HTTPS
# =====================
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'None'
app.config['SESSION_COOKIE_SECURE'] = True
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
# كلمة سر الأدمن الثابتة
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

@app.route("/admin")
def admin():
    # تحقق من الأدمن الثابت
    if not session.get("is_admin"):
        flash("❌ الرجاء إدخال كلمة سر الأدمن أولاً")
        return redirect(url_for("index"))

    db = get_db()
    users_col = db.users
    players_col = db.players
    ads_col = db.ads
    try:
        users = list(users_col.find())
        players = list(players_col.find())
        ads = list(ads_col.find())
    except Exception as e:
        print("❌ Error in /admin:", e)
        users, players, ads = [], [], []

    return render_template("admin.html", users=users, players=players, ads=ads)

# تحقق كلمة سر الأدمن الثابتة
@app.route("/admin_verify", methods=["POST"])
def admin_verify():
    password = request.form.get("password", "")
    if password == ADMIN_PASSWORD:
        session["is_admin"] = True
        return redirect(url_for("admin"))
    flash("❌ كلمة السر غير صحيحة")
    return redirect(url_for("index"))

# تسجيل خروج الأدمن
@app.route("/logout_admin")
def logout_admin():
    session.pop("is_admin", None)
    flash("✅ تم تسجيل الخروج من الإدارة")
    return redirect(url_for("index"))

# =====================
# Routes للمستخدمين العاديين
# =====================
@app.route("/register", methods=["GET", "POST"])
def register():
    db = get_db()
    users_col = db.users

    if request.method == "POST":
        username = (request.form.get("username") or "").strip()
        password = (request.form.get("password") or "").strip()
        full_name = request.form.get("full_name")
        phone = request.form.get("phone")
        address = request.form.get("address")
        national_id = request.form.get("national_id")

        if not username or not password:
            flash("❌ الرجاء تعبئة جميع الحقول")
            return redirect(url_for("register"))

        if users_col.find_one({"username": username}):
            flash("❌ اسم المستخدم موجود")
            return redirect(url_for("register"))

        photo_file = request.files.get("photo")
        photo_url = save_photo_to_db(photo_file) if photo_file else ""

        new_user = {
            "username": username,
            "password": password,
            "full_name": full_name,
            "phone": phone,
            "address": address,
            "national_id": national_id,
            "photo_url": photo_url,
            "role": "user",
            "card_number": get_next_card_number(users_col),
            "registration_date": datetime.now().strftime("%Y-%m-%d")
        }

        try:
            users_col.insert_one(new_user)
            flash("✅ تم التسجيل بنجاح")
            return redirect(url_for("login"))
        except Exception:
            traceback.print_exc()
            flash("❌ خطأ في حفظ المستخدم")
            return redirect(url_for("register"))

    return render_template("register.html")

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
            session.permanent = True
            session["user"] = {"username": username, "role": "user"}
            flash(f"✅ تسجيل الدخول ناجح (user)")
            return redirect(url_for("user_page"))

        flash("❌ اسم المستخدم أو كلمة المرور غير صحيحة")
        return redirect(url_for("login"))

    return render_template("login.html")

@app.route("/user")
def user_page():
    user_session = session.get("user")
    if not user_session:
        flash("❌ يجب تسجيل الدخول")
        return redirect(url_for("login"))

    db = get_db()
    users_col = db.users

    try:
        user = users_col.find_one({"username": user_session["username"]})
    except Exception:
        traceback.print_exc()
        flash("❌ خطأ في جلب بيانات المستخدم")
        return redirect(url_for("login"))

    if not user:
        flash("❌ الحساب غير موجود")
        return redirect(url_for("login"))

    qr_url = f"{request.host_url}user_card/{user['card_number']}"
    qr_code = generate_qr_base64(qr_url)
    expiry = datetime.strptime(user["registration_date"], "%Y-%m-%d") + timedelta(days=180)

    return render_template(
        "user.html",
        user=user,
        registration_date=user["registration_date"],
        expiry_date=expiry.strftime("%Y-%m-%d"),
        qr_code=qr_code
    )

@app.route("/user_card/<int:card_number>")
def user_card(card_number):
    db = get_db()
    users_col = db.users
    try:
        user = users_col.find_one({"card_number": card_number})
    except Exception:
        traceback.print_exc()
        user = None

    if not user:
        return "❌ البطاقة غير موجودة"
    return render_template("user_card.html", user=user)

@app.route("/logout")
def logout():
    session.pop("user", None)
    flash("✅ تم تسجيل الخروج")
    return redirect(url_for("index"))

# =====================
# تشغيل السيرفر
# =====================
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
