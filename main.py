# main.py
from flask import Flask, render_template, request, redirect, url_for, session, flash
from pymongo import MongoClient
from urllib.parse import quote_plus
import qrcode
import io
import base64
import sys
import traceback
from datetime import datetime, timedelta
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.secret_key = "secretkey123"

# =====================
# اتصال MongoDB
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
    print("✅ MongoDB Connected")
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
    """تحويل الصورة إلى Base64 وتخزينها داخل MongoDB"""
    try:
        data = photo_file.read()
        b64 = base64.b64encode(data).decode("utf-8")
        return f"data:image/png;base64,{b64}"
    except Exception:
        traceback.print_exc()
        return ""

def generate_qr_base64(data):
    """إنشاء QR كـ Base64 جاهز للعرض"""
    try:
        qr = qrcode.QRCode(box_size=6, border=2)
        qr.add_data(data)
        qr.make(fit=True)
        img = qr.make_image(fill_color="black", back_color="white")
        buffer = io.BytesIO()
        img.save(buffer, format="PNG")
        b64 = base64.b64encode(buffer.getvalue()).decode("utf-8")
        return f"data:image/png;base64,{b64}"
    except Exception:
        traceback.print_exc()
        return ""

def get_next_card_number():
    users = list(users_col.find({}, {"card_number": 1}))
    if users:
        last = max((u.get("card_number", 0) for u in users), default=0)
        return last + 1
    return 1

# =====================
# إنشاء الأدمن تلقائياً
# =====================
def ensure_admin():
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
        print("✅ Admin Created")
    else:
        print("ℹ️ Admin Exists")

# =====================
# Routes
# =====================
@app.route("/")
def index():
    try:
        players = list(players_col.find()) if "players" in db.list_collection_names() else []
        ads = list(ads_col.find()) if "ads" in db.list_collection_names() else []
    except:
        players, ads = [], []
    return render_template("index.html", players=players, ads=ads, user=session.get("user"))

# ----------------- صفحة الأدمن -----------------
@app.route("/admin")
def admin():
    user_session = session.get("user")
    if not user_session or user_session.get("role") != "admin":
        flash("❌ لا تمتلك صلاحية الدخول")
        return redirect(url_for("login"))

    users = list(users_col.find())
    tickets = list(tickets_col.find())
    return render_template("admin.html", users=users, tickets=tickets)

# ----------------- صفحة اليوزر -----------------
@app.route("/user")
def user_page():
    user_session = session.get("user")
    if not user_session or user_session.get("role") != "user":
        flash("❌ يجب تسجيل الدخول")
        return redirect(url_for("login"))

    username = user_session["username"]
    user = users_col.find_one({"username": username})

    if not user:
        flash("❌ الحساب غير موجود")
        return redirect(url_for("login"))

    # رقم البطاقة
    if not user.get("card_number"):
        user["card_number"] = get_next_card_number()
        users_col.update_one({"_id": user["_id"]}, {"$set": {"card_number": user["card_number"]}})

    # تاريخ التسجيل
    if not user.get("registration_date"):
        today = datetime.now().strftime("%Y-%m-%d")
        user["registration_date"] = today
        users_col.update_one({"_id": user["_id"]}, {"$set": {"registration_date": today}})

    reg_date = datetime.strptime(user["registration_date"], "%Y-%m-%d")
    expiry = reg_date + timedelta(days=180)

    # QR
    qr_url = f"{request.host_url}user_card/{user['card_number']}"
    qr_code = generate_qr_base64(qr_url)

    return render_template(
        "user.html",
        user=user,
        registration_date=reg_date.strftime("%d/%m/%Y"),
        expiry_date=expiry.strftime("%d/%m/%Y"),
        qr_code=qr_code
    )

# ----------------- صفحة البطاقة -----------------
@app.route("/user_card/<int:card_number>")
def user_card(card_number):
    user = users_col.find_one({"card_number": card_number})
    if not user:
        return "❌ البطاقة غير موجودة"
    return render_template("user_card.html", user=user)

# ----------------- تسجيل الدخول -----------------
# ----------------- تسجيل الدخول -----------------
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":

        # جلب البيانات وإزالة المسافات
        username = (request.form.get("username") or "").strip()
        password = (request.form.get("password") or "").strip()

        # التحقق من الحقول الفارغة
        if not username or not password:
            flash("❌ الرجاء تعبئة جميع الحقول")
            return redirect(url_for("login"))

        # التحقق من الأدمن
        if username == "admin" and password == "22@22":
            session["user"] = {"username": "admin", "role": "admin"}
            flash("✅ مرحباً مدير النظام")
            return redirect(url_for("admin"))

        # التحقق من المستخدم العادي
        user = users_col.find_one({
            "username": username,
            "password": password
        })

        if user:
            session["user"] = {"username": username, "role": "user"}
            flash("✅ تسجيل الدخول ناجح")
            return redirect(url_for("index"))

        # إذا لم تتطابق البيانات
        flash("❌ اسم المستخدم أو كلمة المرور غير صحيحة")
        return redirect(url_for("login"))

    return render_template("login.html")


# ----------------- تسجيل مستخدم جديد -----------------
@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = (request.form.get("username") or "").strip()

        if users_col.find_one({"username": username}):
            flash("❌ اسم المستخدم موجود")
            return redirect(url_for("register"))

        photo_file = request.files.get("photo")
        photo_url = save_photo_to_db(photo_file) if photo_file else ""

        new_user = {
            "username": username,
            "password": request.form.get("password"),
            "full_name": request.form.get("full_name"),
            "phone": request.form.get("phone"),
            "address": request.form.get("address"),
            "national_id": request.form.get("national_id"),
            "photo_url": photo_url,
            "role": "user",
            "card_number": get_next_card_number(),
            "registration_date": datetime.now().strftime("%Y-%m-%d")
        }

        users_col.insert_one(new_user)
        flash("✅ تم التسجيل بنجاح")
        return redirect(url_for("login"))

    return render_template("register.html")

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

