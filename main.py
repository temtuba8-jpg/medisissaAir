from flask import Flask, render_template, request, redirect, url_for, session, flash
from pymongo import MongoClient
from urllib.parse import quote_plus
import qrcode
import io
import base64
import sys
from datetime import datetime, timedelta

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
    qr = qrcode.QRCode(box_size=6, border=2)
    qr.add_data(data)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    buffer = io.BytesIO()
    img.save(buffer, format="PNG")
    return base64.b64encode(buffer.getvalue()).decode("utf-8")

def find(collection, query={}):
    try:
        return list(db[collection].find(query))
    except:
        return []

def get_next_card_number():
    users = list(users_col.find())
    if users:
        last_user = max(users, key=lambda x: x.get("card_number", 0))
        return last_user.get("card_number", 0) + 1
    return 1

# =====================
# إنشاء حساب أدمن افتراضي
# =====================
def ensure_admin():
    if users_col.count_documents({"username": "admin"}) == 0:
        admin_user = {
            "username": "admin",
            "password": "22@22",
            "full_name": "مدير النادي",
            "phone": "0000000000",
            "national_id": "000000000000",
            "address": "المدينة",
            "photo_url": "",
            "role": "admin"
        }
        users_col.insert_one(admin_user)
        print("✅ تم إنشاء حساب الأدمن الافتراضي: admin / 22@22")
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

# ---------------------
# لوحة تحكم الأدمن
# ---------------------
@app.route("/admin")
def admin_dashboard():
    user_session = session.get("user")
    if not user_session or user_session.get("role") != "admin":
        flash("❌ لا تمتلك صلاحية الوصول لهذه الصفحة")
        return redirect(url_for("login"))

    users = find("users")
    tickets = find("tickets")
    safe_users = []
    for u in users:
        safe_users.append({
            "username": u.get("username", ""),
            "full_name": u.get("full_name", ""),
            "phone": u.get("phone", ""),
            "address": u.get("address", ""),
            "national_id": u.get("national_id", ""),
            "photo_url": u.get("photo_url", ""),
            "card_number": u.get("card_number", ""),
            "registration_date": u.get("registration_date", ""),
            "role": u.get("role", "user")
        })
    return render_template("admin.html", users=safe_users, tickets=tickets, user=user_session)

# ---------------------
# صفحة المستخدم العادي
# ---------------------
@app.route("/user")
def user_dashboard():
    user_session = session.get("user")
    if not user_session or user_session.get("role") != "user":
        flash("❌ يجب تسجيل الدخول كمستخدم للوصول لهذه الصفحة")
        return redirect(url_for("login"))

    username = user_session.get("username")
    user = users_col.find_one({"username": username})
    if not user:
        flash("❌ خطأ في جلب بيانات المستخدم")
        return redirect(url_for("login"))

    # توليد رقم العضوية إذا لم يكن موجود
    if "card_number" not in user:
        card_number = get_next_card_number()
        users_col.update_one({"_id": user["_id"]}, {"$set": {"card_number": card_number}})
        user["card_number"] = card_number

    registration_date_str = user.get("registration_date")
    if registration_date_str:
        try:
            registration_date = datetime.strptime(registration_date_str, "%Y-%m-%d")
        except:
            registration_date = datetime.now()
    else:
        registration_date = datetime.now()
        users_col.update_one({"_id": user["_id"]}, {"$set": {"registration_date": registration_date.strftime("%Y-%m-%d")}})

    expiry_date = registration_date + timedelta(days=180)
    qr_code = generate_qr(f"{request.host_url}user_card/{user['card_number']}")

    safe_user = {
        "full_name": user.get("full_name", ""),
        "card_number": user.get("card_number", ""),
        "phone": user.get("phone", ""),
        "address": user.get("address", ""),
        "national_id": user.get("national_id", ""),
        "photo_url": user.get("photo_url", "")
    }

    return render_template(
        "user.html",
        user=safe_user,
        registration_date=registration_date.strftime("%d/%m/%Y"),
        expiry_date=expiry_date.strftime("%d/%m/%Y"),
        qr_code=qr_code
    )

# ---------------------
# تسجيل الدخول
# ---------------------
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")

        # تحقق من الأدمن أولاً
        if username == "admin" and password == "22@22":
            session["user"] = {"username": "admin", "role": "admin"}
            flash("✅ تم تسجيل الدخول كأدمن")
            return redirect(url_for("admin_dashboard"))

        # تحقق من المستخدم العادي
        user = users_col.find_one({"username": username, "password": password})
        if user:
            session["user"] = {"username": user["username"], "role": "user"}
            flash(f"✅ تم تسجيل الدخول بنجاح كـ {user['username']}")
            return redirect(url_for("user_dashboard"))

        flash("❌ اسم المستخدم أو كلمة المرور خاطئة")
        return render_template("login.html")

    return render_template("login.html")

# ---------------------
# تسجيل مستخدم جديد
# ---------------------
@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]
        full_name = request.form.get("full_name", "")
        phone = request.form.get("phone", "")
        address = request.form.get("address", "")
        national_id = request.form.get("national_id", "")
        photo_url = request.form.get("photo_url", "")

        if users_col.find_one({"username": username}):
            flash("❌ اسم المستخدم موجود بالفعل")
            return redirect(url_for("register"))

        card_number = get_next_card_number()
        registration_date = datetime.now().strftime("%Y-%m-%d")

        new_user = {
            "username": username,
            "password": password,
            "full_name": full_name,
            "phone": phone,
            "address": address,
            "national_id": national_id,
            "photo_url": photo_url,
            "role": "user",
            "card_number": card_number,
            "registration_date": registration_date
        }

        users_col.insert_one(new_user)
        flash(f"✅ تم إنشاء الحساب بنجاح: {username}")
        return redirect(url_for("login"))

    return render_template("register.html")

# ---------------------
# تسجيل الخروج
# ---------------------
@app.route("/logout")
def logout():
    session.pop("user", None)
    flash("✅ تم تسجيل الخروج")
    return redirect(url_for("index"))

# =====================
# تشغيل السيرفر
# =====================
if __name__ == "__main__":
    ensure_admin()
    app.run(host="0.0.0.0", port=5000, debug=True)
