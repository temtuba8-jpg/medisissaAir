from flask import Flask, render_template, request, redirect, url_for, session, flash
from pymongo import MongoClient
from urllib.parse import quote_plus
import uuid
import qrcode
import io
import base64
import sys
import traceback
from datetime import datetime, timedelta
from bson.objectid import ObjectId  # لإدارة _id في MongoDB
from datetime import date

app = Flask(__name__)
app.secret_key = "secretkey123"

# =====================
# إعدادات الجلسة (تعمل على localhost و HTTPS)
# =====================
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SECURE'] = False  # أثناء التطوير على localhost
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
def deduct_coins_for_certificate(user_username, db):
    """
    تخصم 6 عملات من المستخدم عند مشاهدة شهادة السكن.
    """
    users_col = db.users
    user = users_col.find_one({"username": user_username})
    if not user:
        return False, "المستخدم غير موجود"

    balance = user.get("balance", 0)
    amount_to_deduct = 6

    if balance < amount_to_deduct:
        return False, "رصيد العملات غير كافٍ"

    new_balance = balance - amount_to_deduct
    users_col.update_one({"_id": user["_id"]}, {"$set": {"balance": new_balance}})

    return True, new_balance

#====================
def deduct_coins_for_service(username, db, service_name):
    users_col = db.users
    user = users_col.find_one({"username": username})
    if not user:
        return False, "المستخدم غير موجود"

    services_cost = {
        "🏠 شهادة السكن": 6,
        "🏆 مشاهدة كأس العالم": 4,
        "🎓 شهادة مدرسية": 10
    }

    amount_to_deduct = services_cost.get(service_name)
    if amount_to_deduct is None:
        return False, "الخدمة غير موجودة"

    balance = user.get("balance", 0)
    if balance < amount_to_deduct:
        return False, "رصيد العملات غير كافٍ"

    new_balance = balance - amount_to_deduct
    users_col.update_one({"_id": user["_id"]}, {"$set": {"balance": new_balance}})
    return True, new_balance

#====================
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

# صفحة الأدمن
@app.route("/admin")
def admin():
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
# تعديل وحذف المستخدمين
# =====================
@app.route("/edit_user/<username>", methods=["GET", "POST"])
def edit_user(username):
    if "is_admin" not in session:
        return redirect(url_for("index"))

    db = get_db()
    users_collection = db.users
    user = users_collection.find_one({"username": username})

    if not user:
        flash("المستخدم غير موجود")
        return redirect(url_for("admin"))

    if request.method == "POST":
        new_password = request.form.get("new_password", "")
        users_collection.update_one(
            {"username": username},
            {"$set": {"password": new_password}}
        )
        flash("تم تحديث كلمة المرور بنجاح")
        return redirect(url_for("admin"))

    return render_template("edit_user.html", user=user)

@app.route("/delete_user/<username>")
def delete_user(username):
    if "is_admin" not in session:
        return redirect(url_for("index"))

    db = get_db()
    users_collection = db.users
    users_collection.delete_one({"username": username})
    flash("تم حذف المستخدم بنجاح")
    return redirect(url_for("admin"))

# =====================
# =====================
# المستخدمين العاديين (Register)
# =====================
@app.route("/register", methods=["GET", "POST"])
def register():
    db = get_db()
    users_col = db.users

    if request.method == "POST":
        username = (request.form.get("username") or "").strip()
        password = (request.form.get("password") or "").strip()
        full_name = (request.form.get("full_name") or "").strip()
        phone = (request.form.get("phone") or "").strip()
        address = (request.form.get("address") or "").strip()
        national_id = (request.form.get("national_id") or "").strip()

        if not username or not password:
            flash("❌ الرجاء تعبئة جميع الحقول")
            return redirect(url_for("register"))

        if users_col.find_one({"username": username}):
            flash("❌ اسم المستخدم موجود مسبقاً")
            return redirect(url_for("register"))

        # حفظ الصورة
        photo_file = request.files.get("photo")
        photo_url = save_photo_to_db(photo_file) if photo_file else ""

        # إنشاء المستخدم مع رمز تحقق فريد ورصيد 0
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
            "verify_token": str(__import__("uuid").uuid4()),
            "active": True,
            "registration_date": datetime.now().strftime("%Y-%m-%d"),
            "balance": 0  # الرصيد الابتدائي صفر
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

#==================
@app.route("/verify/<token>")
def verify_card(token):
    db = get_db()
    users_col = db.users

    user = users_col.find_one({
        "verify_token": token,
        "active": True
    })

    if not user:
        return render_template("verify_invalid.html")

    expiry = datetime.strptime(
        user["registration_date"], "%Y-%m-%d"
    ) + timedelta(days=180)

    return render_template(
        "verify_valid.html",
        user=user,
        expiry_date=expiry.strftime("%Y-%m-%d")
    )

#================

@app.route("/login", methods=["GET", "POST"])
def login():
    db = get_db()
    users_col = db.users
    error = None  # متغير لتخزين رسالة الخطأ

    if request.method == "POST":
        username = (request.form.get("username") or "").strip()
        password = (request.form.get("password") or "").strip()

        if not username or not password:
            error = "❌ الرجاء تعبئة جميع الحقول"
        else:
            try:
                user = users_col.find_one({"username": username})
            except Exception:
                traceback.print_exc()
                user = None

            if not user:
                error = "❌ اسم المستخدم غير موجود"
            elif user.get("password") != password:
                error = "❌ كلمة المرور خاطئة"
            else:
                session["user"] = {"username": username, "role": "user"}
                session.permanent = True
                flash("✅ تسجيل الدخول ناجح")
                return redirect(url_for("user_page"))

    return render_template("login.html", error=error)

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

    # ✅ التأكد من وجود verify_token لكل مستخدم
    if "verify_token" not in user or not user["verify_token"]:
        new_token = str(uuid.uuid4())
        users_col.update_one(
            {"_id": user["_id"]},
            {"$set": {"verify_token": new_token}}
        )
        user["verify_token"] = new_token

    # 🔐 رابط التحقق الرسمي (عام)
    verify_url = f"{request.host_url}verify/{user['verify_token']}"

    # توليد QR
    qr_code = generate_qr_base64(verify_url)

    # الصلاحية 6 شهور
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
@app.route("/ticket/<user_id>")
def ticket(user_id):
    db = get_db()
    users_col = db.users
    user = users_col.find_one({"username": user_id})
    if not user:
        flash("المستخدم غير موجود")
        return redirect(url_for("admin"))

    return render_template("ticket.html", user=user)

#====================
# إضافة اللاعبين
#====================
# إضافة اللاعبين مع حماية كاملة وتشخيص الأخطاء
@app.route("/add_player", methods=["GET", "POST"])
def add_player():
    # تحقق من صلاحية الأدمن
    if not session.get("is_admin"):
        flash("❌ يجب تسجيل الدخول كأدمن")
        return redirect(url_for("index"))

    db = get_db()

    # تحقق من وجود collection players
    if "players" not in db.list_collection_names():
        db.create_collection("players")
    players_col = db.players

    if request.method == "POST":
        name = request.form.get("name", "").strip()
        position = request.form.get("position", "").strip()

        if not name or not position:
            flash("❌ الرجاء تعبئة جميع الحقول")
            return redirect(url_for("add_player"))

        try:
            players_col.insert_one({
                "name": name,
                "position": position,
                "added_date": datetime.now().strftime("%Y-%m-%d")
            })
            flash("✅ تم إضافة اللاعب بنجاح")
        except Exception as e:
            # طباعة الخطأ في اللوج لتعرف السبب
            print("❌ خطأ أثناء إضافة اللاعب:", e)
            flash(f"❌ خطأ أثناء إضافة اللاعب: {e}")

        return redirect(url_for("add_player"))

    # GET request يعرض النموذج
    try:
        players_list = list(players_col.find())
    except Exception as e:
        print("❌ خطأ عند جلب اللاعبين:", e)
        flash(f"❌ خطأ عند جلب قائمة اللاعبين: {e}")
        players_list = []

    return render_template("add_player.html", players=players_list)


@app.route("/edit_player/<player_id>", methods=["GET", "POST"])
def edit_player(player_id):
    if "is_admin" not in session:
        flash("❌ يجب تسجيل الدخول كأدمن")
        return redirect(url_for("index"))

    db = get_db()
    players_col = db.players
    player = players_col.find_one({"_id": ObjectId(player_id)})

    if not player:
        flash("❌ اللاعب غير موجود")
        return redirect(url_for("admin"))

    if request.method == "POST":
        name = request.form.get("name", "").strip()
        position = request.form.get("position", "").strip()
        players_col.update_one({"_id": ObjectId(player_id)}, {"$set": {"name": name, "position": position}})
        flash("✅ تم تعديل اللاعب")
        return redirect(url_for("admin"))

    return render_template("edit_player.html", player=player)

@app.route("/delete_player/<player_id>")
def delete_player(player_id):
    if "is_admin" not in session:
        flash("❌ يجب تسجيل الدخول كأدمن")
        return redirect(url_for("index"))

    db = get_db()
    players_col = db.players
    players_col.delete_one({"_id": ObjectId(player_id)})
    flash("✅ تم حذف اللاعب")
    return redirect(url_for("admin"))

#====================
# إضافة الإعلانات
@app.route("/add_ad", methods=["GET", "POST"])
def add_ad():
    if "is_admin" not in session:
        flash("❌ يجب تسجيل الدخول كأدمن")
        return redirect(url_for("index"))

    db = get_db()
    ads_col = db.ads

    if request.method == "POST":
        title = request.form.get("title", "").strip()
        description = request.form.get("description", "").strip()

        if not title or not description:
            flash("❌ الرجاء تعبئة جميع الحقول")
            return redirect(url_for("add_ad"))

        ads_col.insert_one({
            "title": title,
            "description": description,
            "date": datetime.now().strftime("%Y-%m-%d")
        })
        flash("✅ تم إضافة الإعلان بنجاح")
        return redirect(url_for("admin"))

    return render_template("add_ad.html")

@app.route("/edit_ad/<ad_id>", methods=["GET", "POST"])
def edit_ad(ad_id):
    if "is_admin" not in session:
        flash("❌ يجب تسجيل الدخول كأدمن")
        return redirect(url_for("index"))

    db = get_db()
    ads_col = db.ads
    ad = ads_col.find_one({"_id": ObjectId(ad_id)})

    if not ad:
        flash("❌ الإعلان غير موجود")
        return redirect(url_for("admin"))

    if request.method == "POST":
        title = request.form.get("title", "").strip()
        description = request.form.get("description", "").strip()
        ads_col.update_one({"_id": ObjectId(ad_id)}, {"$set": {"title": title, "description": description}})
        flash("✅ تم تعديل الإعلان")
        return redirect(url_for("admin"))

    return render_template("edit_ad.html", ad=ad)

@app.route("/delete_ad/<ad_id>")
def delete_ad(ad_id):
    if "is_admin" not in session:
        flash("❌ يجب تسجيل الدخول كأدمن")
        return redirect(url_for("index"))

    db = get_db()
    ads_col = db.ads
    ads_col.delete_one({"_id": ObjectId(ad_id)})
    flash("✅ تم حذف الإعلان")
    return redirect(url_for("admin"))

#===========================
# =====================
# ADMIN - إضافة رصيد للمستخدم
# =====================
@app.route("/admin/add_balance", methods=["POST"])
def admin_add_balance():
    if not session.get("is_admin"):
        flash("❌ غير مصرح")
        return redirect(url_for("index"))

    username = request.form.get("username", "").strip()
    amount = int(request.form.get("amount", 0))

    if amount <= 0:
        flash("❌ قيمة غير صحيحة")
        return redirect(url_for("admin"))

    db = get_db()
    users_col = db.users

    user = users_col.find_one({"username": username})
    if not user:
        flash("❌ المستخدم غير موجود")
        return redirect(url_for("admin"))

    users_col.update_one(
        {"_id": user["_id"]},
        {"$inc": {"balance": amount}}
    )

    flash(f"✅ تم إضافة {amount} عملات للمستخدم {username}")
    return redirect(url_for("admin"))
#=====================
# =====================
# USER - خصم 10 عملات عند إزالة الفوكس
# =====================
@app.route("/remove_focus", methods=["POST"])
def remove_focus():
    if "user" not in session:
        return {"status": "error", "msg": "غير مسجل دخول"}, 401

    db = get_db()
    users_col = db.users

    user = users_col.find_one({"username": session["user"]["username"]})
    if not user:
        return {"status": "error", "msg": "المستخدم غير موجود"}, 404

    balance = user.get("balance", 0)
    if balance < 10:
        return {"status": "error", "msg": "رصيد غير كافي"}, 400

    # خصم الرصيد وفتح الفوكس
    new_balance = balance - 10
    users_col.update_one(
        {"_id": user["_id"]},
        {"$set": {"pdfCleared": True, "balance": new_balance}}
    )

    return {
        "status": "success",
        "new_balance": new_balance,
        "pdfCleared": True
    }


@app.route("/worldcup")
def worldcup():
    return render_template("worldcup.html")


#===============
@app.route("/user_data")
def user_data():
    user_session = session.get("user")
    if not user_session:
        return {"balance": 0, "pdfCleared": False}, 401

    db = get_db()
    users_col = db.users
    user = users_col.find_one({"username": user_session["username"]})
    if not user:
        return {"balance": 0, "pdfCleared": False}, 404

    return {
        "balance": user.get("balance", 0),
        "pdfCleared": user.get("pdfCleared", False)
    }

#==============
@app.route("/certificate/residence")
def certificate_residence():
    if "user" not in session:
        flash("❌ يجب تسجيل الدخول")
        return redirect(url_for("login"))

    db = get_db()
    users_col = db.users
    username = session["user"]["username"]

    user = users_col.find_one({"username": username})
    if not user:
        flash("❌ المستخدم غير موجود")
        return redirect(url_for("login"))

    # =============================
    # خصم 6 عملات مرة واحدة فقط
    # =============================
    if not session.get("residence_certificate_paid"):
        success, result = deduct_coins_for_certificate(username, db)

        if not success:
            return render_template(
                "user.html",
                user=user,
                error_message=f"❌ {result}"
            )

        # حفظ أن الخصم تم
        session["residence_certificate_paid"] = True

        # تحديث الرصيد في بيانات المستخدم
        user["balance"] = result

    today = date.today().strftime("%Y/%m/%d")

    return render_template(
        "certificate_residence.html",
        user=user,
        today=today,
        balance_after=user.get("balance")
    )


#####========
@app.route("/transactions")
def transactions():
    if "user" not in session:
        flash("❌ يجب تسجيل الدخول")
        return redirect(url_for("login"))

    db = get_db()
    username = session["user"]["username"]
    transactions_col = db.transactions

    try:
        # جلب كل العمليات الخاصة بالمستخدم مرتبة حسب التاريخ
        user_transactions = list(transactions_col.find({"username": username}).sort("date", -1))
        
        # تحويل التاريخ إلى نص قابل للعرض
        for t in user_transactions:
            if "date" in t and isinstance(t["date"], datetime):
                t["date_str"] = t["date"].strftime("%Y-%m-%d %H:%M:%S")
            else:
                t["date_str"] = ""

    except Exception as e:
        print("❌ خطأ عند جلب العمليات:", e)
        user_transactions = []

    return render_template("transactions.html", transactions=user_transactions)


#==================

@app.route("/pay_service", methods=["POST"])
def pay_service():
    if "user" not in session:
        return {"status":"error","msg":"❌ يجب تسجيل الدخول"}, 401

    data = request.get_json()
    service_name = data.get("service")

    db = get_db()
    username = session["user"]["username"]

    success, result = deduct_coins_for_service(username, db, service_name)

    if not success:
        return {"status":"error","msg": result}, 400

    # تحديد صفحة التحويل
    redirect_map = {
        "🏠 شهادة السكن": "/certificate/residence",
        "🏆 مشاهدة كأس العالم": "/worldcup",
        "🎓 شهادة مدرسية": "/certificate/school"
    }

    return {
        "status": "success",
        "new_balance": result,
        "redirect_url": redirect_map.get(service_name, "/user")
    }
#========
@app.route("/certificate/school")
def certificate_school():
    if "user" not in session:
        flash("❌ يجب تسجيل الدخول")
        return redirect(url_for("login"))

    db = get_db()
    users_col = db.users
    username = session["user"]["username"]

    user = users_col.find_one({"username": username})
    if not user:
        flash("❌ المستخدم غير موجود")
        return redirect(url_for("login"))

    # =============================
    # خصم 10 عملات مرة واحدة فقط للشهادة المدرسية
    # =============================
    if not session.get("school_certificate_paid"):
        success, result = deduct_coins_for_service(username, db, "🎓 شهادة مدرسية")

        if not success:
            return render_template(
                "user.html",
                user=user,
                error_message=f"❌ {result}"
            )

        # حفظ أن الخصم تم
        session["school_certificate_paid"] = True

        # تحديث الرصيد في بيانات المستخدم
        user["balance"] = result

    today = date.today().strftime("%Y/%m/%d")

    return render_template(
        "certificate_school.html",
        user=user,
        today=today,
        balance_after=user.get("balance")
    )
#=====================
import requests
from flask import Response

NGROK_STREAM = "https://semihardened-freeman-incorruptibly.ngrok-free.dev/live/stream1.m3u8"

@app.route("/proxy/stream.m3u8")
def proxy_stream():
    """
    Proxy لمشاهدة بث كأس العالم من ngrok بدون مشاكل CORS
    """
    try:
        r = requests.get(NGROK_STREAM, stream=True, timeout=10)
        headers = {
            "Content-Type": r.headers.get("Content-Type", "application/vnd.apple.mpegurl"),
            "Access-Control-Allow-Origin": "*"
        }
        return Response(r.iter_content(chunk_size=1024), headers=headers)
    except Exception as e:
        return f"❌ خطأ في البث: {e}", 500


# تشغيل السيرفر
#============================
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)






