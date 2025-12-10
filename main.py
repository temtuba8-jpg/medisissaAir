from flask import Flask, render_template, request, redirect, url_for, session
from pymongo import MongoClient
from urllib.parse import quote_plus
import qrcode
import io
import base64
import os
import sys

app = Flask(__name__)
app.secret_key = "secretkey123"

# =====================
# إعداد اتصال MongoDB Atlas مع تجاوز SSL للتحقق
# =====================
username = "sahoor"
password = "Fad@0911923356"
password_escaped = quote_plus(password)
cluster = "cluster1.6wgwgl5.mongodb.net"
database_name = "sahoor"

# URI مع تجاوز SSL
uri = f"mongodb+srv://{username}:{password_escaped}@{cluster}/{database_name}?retryWrites=true&w=majority&tls=true&tlsAllowInvalidCertificates=true"

try:
    # إنشاء العميل مع تجاوز SSL
    client = MongoClient(uri, serverSelectionTimeoutMS=10000, connect=True)
    db = client[database_name]
    users_col = db.users
    tickets_col = db.tickets
    players_col = db.players
    ads_col = db.ads
    client.server_info()  # التحقق من الاتصال
    print("✅ تم الاتصال بقاعدة البيانات بنجاح")
except Exception as e:
    print(
        "⚠️ لم يتم الاتصال بقاعدة البيانات، تحقق من MongoDB Atlas و IP Whitelist"
    )
    print("Error:", e)
    sys.exit(1)  # توقف السيرفر إذا فشل الاتصال


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
# جميع Routes كما هي (نسخ الكود السابق)
# =====================


# مثال:
@app.route("/")
def index():
    players = find("players")
    ads = find("ads")
    return render_template("index.html", players=players, ads=ads)


# ... بقية Routes كما في الكود السابق ...

# =====================
# Run Server
# =====================
if __name__ == "__main__":
    ensure_admin()
    print("كل المستخدمين الحاليين:", find("users"))
    app.run(host="0.0.0.0", port=5000, debug=True)
