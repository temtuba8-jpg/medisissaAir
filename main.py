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

# تحسين إعدادات الجلسة
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
app.config['SESSION_COOKIE_SECURE'] = True  # لأن Render يستخدم HTTPS
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
    """دالة للحصول على اتصال MongoDB"""
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
def allowed_file(filename):
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    return ext in {"png", "jpg", "jpeg", "gif"}

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
# إنشاء الأدمن تلقائياً
# =====================
def ensure_admin():
    db = get_db()
    users_col = db.users
    try:
        if users_col.count_documents({"username": "admin"}) == 0:
            admin = {
                "username": "admin",
                "password": "22@22",
                "full_name": "مدير النادي",
                "phone": "0000000000",
                "address": "المدينة",
                "national_id": "000000000000",
                "photo_url": "",
                "role": "admin",
                "card_number": 0,
                "registration_date": datetime.now().strftime("%Y-%m-%d")
            }
            users_col.insert_one(admin)
            print("✅ Admin Created in DB")
        else:
            print("ℹ️ Admin already exists in DB")
    except Exception:
        traceback.print_exc()

# =====================
# Routes
# =====================

# الصفحة الرئيسية
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

    return render_template("index.html", players=players, ads=ads, user=session.get("user"))

# ----------------- صفحة الأدمن -----------------
@app.route("/admin")
def admin():
    user_session = session.get("user")
    if not user_session or user_session.get("role") != "admin":
        flash("❌ لا تمتلك صلاحية الدخول")
        return redirect(url_for("login"))

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

# ----------------- صفحة تسجيل المستخدم -----------------
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

# ----------------- تسجيل الدخول -----------------
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
            role = user.get("role", "user")
            session["user"] = {"username": username, "role": role}
            flash(f"✅ تسجيل الدخول ناجح ({role})")
            if role == "admin":
                return redirect(url_for("admin"))
            else:
                return redirect(url_for("user_page"))

        flash("❌ اسم المستخدم أو كلمة المرور غير صحيحة")
        return redirect(url_for("login"))

    return render_template("login.html")

# ----------------- صفحة اليوزر -----------------
@app.route("/user")
def user_page():
    user_session = session.get("user")
    if not user_session or user_session.get("role") != "user":
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

    # إنشاء QR للبطاقة
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

# ----------------- صفحة بطاقة المستخدم -----------------
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

# ----------------- تسجيل الخروج -----------------
@app.route("/logout")
def logout():
    session.pop("user", None)
    flash("تم تسجيل الخروج")
    return redirect(url_for("index"))

# ----------------- تشغيل السيرفر -----------------
if __name__ == "__main__":
    ensure_admin()
    app.run(host="0.0.0.0", port=5000, debug=True)
