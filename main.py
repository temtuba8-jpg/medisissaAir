# main.py
from flask import Flask, render_template, request, redirect, url_for, session, flash, send_from_directory
from pymongo import MongoClient
from urllib.parse import quote_plus
import qrcode
import io
import base64
import sys
import os
import traceback
from datetime import datetime, timedelta
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.secret_key = "secretkey123"

# ------------ إعدادات الملفات المرفوعة ------------
UPLOAD_FOLDER = os.path.join(os.path.dirname(__file__), "static", "uploads")
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
ALLOWED_EXT = {"png", "jpg", "jpeg", "gif"}

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
    print("✅ تم الاتصال بقاعدة البيانات بنجاح")
except Exception as e:
    print("⚠️ فشل الاتصال بقاعدة البيانات")
    print("Error:", e)
    sys.exit(1)

# =====================
# Helpers
# =====================
def allowed_file(filename):
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    return ext in ALLOWED_EXT

def save_photo(file_storage):
    """
    يحفظ الصورة في static/uploads ويرجع مسار نسبي للعرض (مثال: /static/uploads/...)
    """
    if not file_storage:
        return ""
    filename = secure_filename(file_storage.filename)
    if filename == "" or not allowed_file(filename):
        return ""
    ts = datetime.now().strftime("%Y%m%d%H%M%S")
    filename = f"{ts}_{filename}"
    path = os.path.join(UPLOAD_FOLDER, filename)
    file_storage.save(path)
    # نعيد المسار النسبي للعرض في القالب
    return url_for("static", filename=f"uploads/{filename}")

def generate_qr_data_uri(data):
    """
    يولد صورة QR كـ data URI جاهزة للاستخدام في <img src="...">
    """
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
# إنشـاء أدمن افتراضي إن لم يكن موجود
# =====================
def ensure_admin():
    try:
        if users_col.count_documents({"username": "admin"}) == 0:
            admin_user = {
                "username": "admin",
                "password": "22@22",   # كما طلبت
                "full_name": "مدير النادي",
                "phone": "0000000000",
                "national_id": "000000000000",
                "address": "المدينة",
                "photo_url": "",
                "role": "admin",
                "card_number": 0,
                "registration_date": datetime.now().strftime("%Y-%m-%d")
            }
            users_col.insert_one(admin_user)
            print("✅ تم إنشاء الأدمن الافتراضي")
        else:
            print("ℹ️ الأدمن موجود بالفعل")
    except Exception:
        traceback.print_exc()

# =====================
# Routes
# =====================
@app.route("/")
def index():
    try:
        players = list(players_col.find()) if "players" in db.list_collection_names() else []
        ads = list(ads_col.find()) if "ads" in db.list_collection_names() else []
    except Exception:
        players, ads = [], []
    return render_template("index.html", players=players, ads=ads, user=session.get("user"))

# صفحة الأدمن (عرض كل المستخدمين والتذاكر)
@app.route("/admin")
def admin():
    user_session = session.get("user")
    if not user_session or user_session.get("role") != "admin":
        flash("❌ لا تمتلك صلاحية الوصول")
        return redirect(url_for("login"))
    try:
        users = list(users_col.find())
        tickets = list(tickets_col.find())
    except Exception:
        traceback.print_exc()
        users, tickets = [], []
    return render_template("admin.html", users=users, tickets=tickets, user=user_session)

# صفحة المستخدم (يعرض بيانات المستخدم المسجل)
@app.route("/user")
def user_page():
    user_session = session.get("user")
    if not user_session or user_session.get("role") != "user":
        flash("❌ يجب تسجيل الدخول كمستخدم")
        return redirect(url_for("login"))

    username = user_session.get("username")
    try:
        user = users_col.find_one({"username": username})
        if not user:
            flash("❌ لم يتم العثور على المستخدم")
            return redirect(url_for("login"))

        # ضمان وجود رقم بطاقه
        if not user.get("card_number"):
            card_number = get_next_card_number()
            users_col.update_one({"_id": user["_id"]}, {"$set": {"card_number": card_number}})
            user["card_number"] = card_number

        # ضمان وجود تاريخ تسجيل
        if not user.get("registration_date"):
            reg = datetime.now().strftime("%Y-%m-%d")
            users_col.update_one({"_id": user["_id"]}, {"$set": {"registration_date": reg}})
            user["registration_date"] = reg

        # تجهيز التواريخ
        try:
            reg_date = datetime.strptime(user["registration_date"], "%Y-%m-%d")
        except Exception:
            reg_date = datetime.now()
        expiry = reg_date + timedelta(days=180)

        # QR data-uri (يوجه لعرض البطاقة عبر رابط)
        qr_uri = generate_qr_data_uri(f"{request.host_url}user_card/{user['card_number']}")

        return render_template(
            "user.html",
            user=user,
            registration_date=reg_date.strftime("%d/%m/%Y"),
            expiry_date=expiry.strftime("%d/%m/%Y"),
            qr_code=qr_uri
        )
    except Exception:
        traceback.print_exc()
        flash("❌ حدث خطأ أثناء جلب بيانات المستخدم")
        return redirect(url_for("index"))

# عرض البطاقة عبر رابط (بعد مسح QR)
@app.route("/user_card/<int:card_number>")
def user_card(card_number):
    try:
        user = users_col.find_one({"card_number": card_number})
        if not user:
            return "❌ البطاقة غير موجودة"
        return render_template("user_card.html", user=user)
    except Exception:
        traceback.print_exc()
        return "❌ خطأ داخلي"

# تسجيل الدخول
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = (request.form.get("username") or "").strip()
        password = request.form.get("password") or ""

        # تحقق الأدمن الثابت
        if username == "admin" and password == "22@22":
            session["user"] = {"username": "admin", "role": "admin"}
            return redirect(url_for("admin"))

        # تحقق المستخدم من قاعدة البيانات
        try:
            user = users_col.find_one({"username": username, "password": password})
        except Exception:
            traceback.print_exc()
            user = None

        if user:
            session["user"] = {"username": user["username"], "role": user.get("role", "user")}
            return redirect(url_for("user_page"))
        else:
            flash("❌ اسم المستخدم أو كلمة المرور خاطئة")
    return render_template("login.html")

# تسجيل مستخدم جديد (يدعم رفع صورة عبر حقل input name="photo")
@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        try:
            username = (request.form.get("username") or "").strip()
            password = request.form.get("password") or ""
            full_name = request.form.get("full_name") or ""
            phone = request.form.get("phone") or ""
            address = request.form.get("address") or ""
            national_id = request.form.get("national_id") or ""

            # صورة: نسمح بالرفع حقل name="photo"
            photo_file = request.files.get("photo")
            photo_url = ""
            if photo_file and allowed_file(photo_file.filename):
                photo_url = save_photo(photo_file)
            else:
                # إن لم تقم برفع صورة قد يرسل العميل رابط في حقل "photo_url"
                photo_url = request.form.get("photo_url") or ""

            if users_col.find_one({"username": username}):
                flash("❌ اسم المستخدم موجود بالفعل")
                return redirect(url_for("register"))

            new_user = {
                "username": username,
                "password": password,
                "full_name": full_name,
                "phone": phone,
                "address": address,
                "national_id": national_id,
                "photo_url": photo_url,
                "role": "user",
                "card_number": get_next_card_number(),
                "registration_date": datetime.now().strftime("%Y-%m-%d")
            }
            users_col.insert_one(new_user)
            flash("✅ تم إنشاء الحساب بنجاح")
            return redirect(url_for("login"))
        except Exception:
            traceback.print_exc()
            flash("❌ حدث خطأ أثناء التسجيل")
            return redirect(url_for("register"))
    return render_template("register.html")

# تسجيل الخروج
@app.route("/logout")
def logout():
    session.pop("user", None)
    flash("✅ تم تسجيل الخروج")
    return redirect(url_for("index"))

# =====================
# بدء السيرفر
# =====================
if __name__ == "__main__":
    ensure_admin()
    app.run(host="0.0.0.0", port=5000, debug=True)
