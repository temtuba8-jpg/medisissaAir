from flask import Flask, render_template, request, redirect, url_for, session, flash
from pymongo import MongoClient
from bson import ObjectId
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
        return client[database_name]
    except Exception as e:
        print("❌ MongoDB Connection Failed:", e)
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
    players = list(players_col.find())
    ads = list(ads_col.find())
    return render_template("index.html", players=players, ads=ads)

@app.route("/admin")
def admin():
    if not session.get("is_admin"):
        flash("❌ الرجاء إدخال كلمة سر الأدمن أولاً")
        return redirect(url_for("index"))
    db = get_db()
    users = list(db.users.find())
    players = list(db.players.find())
    ads = list(db.ads.find())
    return render_template("admin.html", users=users, players=players, ads=ads)

@app.route("/admin_verify", methods=["POST"])
def admin_verify():
    password = request.form.get("password", "")
    if password == ADMIN_PASSWORD:
        session["is_admin"] = True
        flash("✅ تم تسجيل الدخول كأدمن")
        return redirect(url_for("admin"))
    flash("❌ كلمة السر غير صحيحة")
    return redirect(url_for("index"))

@app.route("/logout_admin")
def logout_admin():
    session.pop("is_admin", None)
    flash("✅ تم تسجيل الخروج من الإدارة")
    return redirect(url_for("index"))

# =====================
# إدارة المستخدمين
# =====================
@app.route("/edit_user/<username>", methods=["GET", "POST"])
def edit_user(username):
    if "is_admin" not in session:
        return redirect(url_for("index"))
    db = get_db()
    user = db.users.find_one({"username": username})
    if not user:
        flash("المستخدم غير موجود")
        return redirect(url_for("admin"))
    if request.method == "POST":
        new_password = request.form.get("new_password", "")
        db.users.update_one({"username": username}, {"$set": {"password": new_password}})
        flash("✅ تم تحديث كلمة المرور")
        return redirect(url_for("admin"))
    return render_template("edit_user.html", user=user)

@app.route("/delete_user/<username>")
def delete_user(username):
    if "is_admin" not in session:
        return redirect(url_for("index"))
    db = get_db()
    db.users.delete_one({"username": username})
    flash("✅ تم حذف المستخدم")
    return redirect(url_for("admin"))

# =====================
# إضافة وإدارة اللاعبين
# =====================
@app.route("/add_player", methods=["GET", "POST"])
def add_player():
    if "is_admin" not in session:
        flash("❌ يجب تسجيل الدخول كأدمن")
        return redirect(url_for("index"))
    db = get_db()
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        position = request.form.get("position", "").strip()
        if not name or not position:
            flash("❌ الرجاء تعبئة جميع الحقول")
            return redirect(url_for("add_player"))
        db.players.insert_one({"name": name, "position": position, "added_date": datetime.now().strftime("%Y-%m-%d")})
        flash("✅ تم إضافة اللاعب")
        return redirect(url_for("admin"))
    return render_template("add_player.html")

# =====================
# إضافة وتحرير وحذف الإعلانات
# =====================
@app.route("/add_ad", methods=["GET", "POST"])
def add_ad():
    if "is_admin" not in session:
        flash("❌ يجب تسجيل الدخول كأدمن")
        return redirect(url_for("index"))
    db = get_db()
    if request.method == "POST":
        title = request.form.get("title", "").strip()
        description = request.form.get("description", "").strip()
        if not title or not description:
            flash("❌ الرجاء تعبئة جميع الحقول")
            return redirect(url_for("add_ad"))
        db.ads.insert_one({"title": title, "description": description, "date": datetime.now().strftime("%Y-%m-%d")})
        flash("✅ تم إضافة الإعلان")
        return redirect(url_for("admin"))
    return render_template("add_ad.html")

@app.route("/edit_ad/<ad_id>", methods=["GET", "POST"])
def edit_ad(ad_id):
    if "is_admin" not in session:
        flash("❌ يجب تسجيل الدخول كأدمن")
        return redirect(url_for("index"))
    db = get_db()
    ad = db.ads.find_one({"_id": ObjectId(ad_id)})
    if not ad:
        flash("❌ الإعلان غير موجود")
        return redirect(url_for("admin"))
    if request.method == "POST":
        title = request.form.get("title", "").strip()
        description = request.form.get("description", "").strip()
        db.ads.update_one({"_id": ObjectId(ad_id)}, {"$set": {"title": title, "description": description}})
        flash("✅ تم تعديل الإعلان")
        return redirect(url_for("admin"))
    return render_template("edit_ad.html", ad=ad)

@app.route("/delete_ad/<ad_id>")
def delete_ad(ad_id):
    if "is_admin" not in session:
        flash("❌ يجب تسجيل الدخول كأدمن")
        return redirect(url_for("index"))
    db = get_db()
    db.ads.delete_one({"_id": ObjectId(ad_id)})
    flash("✅ تم حذف الإعلان")
    return redirect(url_for("admin"))

# =====================
# تشغيل السيرفر
# =====================
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
