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
def generate_qr(data):
    qr = qrcode.QRCode(box_size=6, border=2)
    qr.add_data(data)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")

    buffer = io.BytesIO()
    img.save(buffer, format="PNG")
    return base64.b64encode(buffer.getvalue()).decode("utf-8")


def get_next_card_number():
    users = list(users_col.find())
    if users:
        last_user = max(users, key=lambda x: x.get("card_number", 0))
        return last_user.get("card_number", 0) + 1
    return 1


# =====================
# إنشاء أدمن افتراضي
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
        print("✅ تم إنشاء الأدمن الافتراضي")
    else:
        print("ℹ️ الأدمن موجود بالفعل")


# =====================
# Routes
# =====================

@app.route("/")
def index():
    return render_template("index.html", user=session.get("user"))


# ---------------------
# لوحة الأدمن
# ---------------------
@app.route("/admin")
def admin_dashboard():
    user_session = session.get("user")

    if not user_session or user_session.get("role") != "admin":
        flash("❌ لا تمتلك صلاحية الوصول")
        return redirect(url_for("login"))

    users = list(users_col.find())
    return render_template("admin.html", users=users, user=user_session)


# ---------------------
# صفحة المستخدم (user.html)
# ---------------------
@app.route("/user")
def user_dashboard():
    user_session = session.get("user")

    if not user_session or user_session.get("role") != "user":
        flash("❌ يجب تسجيل الدخول كمستخدم")
        return redirect(url_for("login"))

    user = users_col.find_one({"username": user_session["username"]})

    if not user:
        flash("❌ لم يتم العثور على المستخدم")
        return redirect(url_for("login"))

    # تأكيد وجود رقم البطاقة
    if not user.get("card_number"):
        new_card = get_next_card_number()
        users_col.update_one({"_id": user["_id"]}, {"$set": {"card_number": new_card}})
        user["card_number"] = new_card

    # تاريخ التسجيل
    if "registration_date" in user:
        try:
            reg_date = datetime.strptime(user["registration_date"], "%Y-%m-%d")
        except:
            reg_date = datetime.now()
    else:
        reg_date = datetime.now()
        users_col.update_one({"_id": user["_id"]}, {"$set": {"registration_date": reg_date.strftime("%Y-%m-%d")}})

    # الصلاحية 6 أشهر
    expiry = reg_date + timedelta(days=180)

    # توليد QR
    qr_data = f"{request.host_url}user_card/{user['card_number']}"
    qr_image = generate_qr(qr_data)

    return render_template(
        "user.html",
        user=user,
        registration_date=reg_date.strftime("%d/%m/%Y"),
        expiry_date=expiry.strftime("%d/%m/%Y"),
        qr_code=qr_image
    )


# ---------------------
# عرض بطاقة المستخدم عند مسح QR
# ---------------------
@app.route("/user_card/<int:card_number>")
def user_card(card_number):
    user = users_col.find_one({"card_number": card_number})
    if not user:
        return "❌ البطاقة غير موجودة"

    return render_template("user_card.html", user=user)


# ---------------------
# تسجيل الدخول
# ---------------------
@app.route("/login", methods=["GET", "POST"])
def login():

    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]

        # الأدمن
        if username == "admin" and password == "22@22":
            session["user"] = {"username": "admin", "role": "admin"}
            return redirect(url_for("admin_dashboard"))

        # المستخدم العادي
        user = users_col.find_one({"username": username, "password": password})
        if user:
            session["user"] = {"username": user["username"], "role": "user"}
            return redirect(url_for("user_dashboard"))

        flash("❌ اسم المستخدم أو كلمة المرور خاطئة")

    return render_template("login.html")


# ---------------------
# التسجيل
# ---------------------
@app.route("/register", methods=["GET", "POST"])
def register():

    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]
        full_name = request.form["full_name"]
        phone = request.form["phone"]
        national_id = request.form["national_id"]
        address = request.form["address"]
        photo_url = request.form["photo_url"]

        if users_col.find_one({"username": username}):
            flash("❌ اسم المستخدم موجود بالفعل")
            return redirect(url_for("register"))

        new_user = {
            "username": username,
            "password": password,
            "full_name": full_name,
            "phone": phone,
            "national_id": national_id,
            "address": address,
            "photo_url": photo_url,
            "role": "user",
            "card_number": get_next_card_number(),
            "registration_date": datetime.now().strftime("%Y-%m-%d")
        }

        users_col.insert_one(new_user)
        flash("✅ تم إنشاء الحساب بنجاح")
        return redirect(url_for("login"))

    return render_template("register.html")


# ---------------------
# تسجيل الخروج
# ---------------------
@app.route("/logout")
def logout():
    session.pop("user", None)
    flash("تم تسجيل الخروج")
    return redirect(url_for("index"))


# =====================
# تشغيل السيرفر
# =====================
if __name__ == "__main__":
    ensure_admin()
    app.run(host="0.0.0.0", port=5000, debug=True)
