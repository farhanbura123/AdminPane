from flask import Flask, render_template, jsonify, request, session, redirect, url_for
from datetime import datetime, timedelta
from pymongo import MongoClient
from bson import ObjectId
from os.path import join, dirname
from dotenv import load_dotenv
import hashlib
import base64
import jwt
import os

dotenv_path = join(dirname(__file__), '.env')
load_dotenv(dotenv_path)

MONGODB_URI = os.environ.get("MONGODB_URI")
DB_NAME = os.environ.get("DB_NAME")

client = MongoClient(MONGODB_URI)
db = client[DB_NAME]
pendaftar_collection = db['pendaftar']

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY")

# route home/index
@app.route("/", methods=["GET"])
def index():
    token_receive = request.cookies.get("mytoken")
    try:
        payload = jwt.decode(token_receive, app.secret_key, algorithms=["HS256"])
        user_info = db.user.find_one({'nick': payload['nick']})
        menunggu_konfirmasi = pendaftar_collection.count_documents({'pendaftaran.status': 'Menunggu Konfirmasi'})
        diterima = pendaftar_collection.count_documents({'pendaftaran.status': 'Diterima'})
        ditolak = pendaftar_collection.count_documents({'pendaftaran.status': 'Ditolak'})
        return render_template('index.html', nickname=user_info['nick'], 
                               menunggu_konfirmasi=menunggu_konfirmasi, 
                               diterima=diterima, 
                               ditolak=ditolak)
    except jwt.ExpiredSignatureError:  
        return redirect(url_for('login', msg="Sesi login telah berakhir"))
    except jwt.DecodeError:
        return redirect(url_for('login', msg="Ada masalah dengan sesi login, mohon login ulang"))

# route tables
@app.route("/tables", methods=["GET"])
def pendaftar():
    token_receive = request.cookies.get("mytoken")
    try:
        payload = jwt.decode(token_receive, app.secret_key, algorithms=["HS256"])
        user_info = db.user.find_one({"nick": payload.get("nick")})

        # Ambil semua data pendaftaran
        pendaftar_list = list(pendaftar_collection.find({}, {'namaSiswa': 1, 'pendaftaran': 1}))

        return render_template("tables.html", nickname=user_info['nick'], pendaftar_list=pendaftar_list, enumerate=enumerate)
    except (jwt.ExpiredSignatureError, jwt.DecodeError):
        return redirect(url_for("index"))

@app.route("/terima/<pendaftar_id>/<int:pendaftaran_index>", methods=["POST"])
def terima_pendaftar(pendaftar_id, pendaftaran_index):
    try:
        pendaftar = pendaftar_collection.find_one({"_id": ObjectId(pendaftar_id)})
        if pendaftar:
            if 0 <= pendaftaran_index < len(pendaftar['pendaftaran']):
                pendaftaran = pendaftar['pendaftaran'][pendaftaran_index]
                if pendaftaran['status'] == 'Menunggu Konfirmasi':
                    pendaftaran['status'] = 'Diterima'
                    pendaftar_collection.update_one(
                        {"_id": ObjectId(pendaftar_id)},
                        {"$set": {f"pendaftaran.{pendaftaran_index}": pendaftaran}}
                    )
                    return redirect(url_for("detail"))
            return jsonify({"message": "Pendaftaran tidak ditemukan atau sudah dikonfirmasi."}), 404
        else:
            return jsonify({"message": "Data pendaftar tidak ditemukan."}), 404
    except Exception as e:
        return jsonify({"message": str(e)}), 500

@app.route("/tolak/<pendaftar_id>/<int:pendaftaran_index>", methods=["POST"])
def tolak_pendaftar(pendaftar_id, pendaftaran_index):
    try:
        pendaftar = pendaftar_collection.find_one({"_id": ObjectId(pendaftar_id)})
        if pendaftar:
            if 0 <= pendaftaran_index < len(pendaftar['pendaftaran']):
                pendaftaran = pendaftar['pendaftaran'][pendaftaran_index]
                if pendaftaran['status'] == 'Menunggu Konfirmasi':
                    pendaftaran['status'] = 'Ditolak'
                    pendaftar_collection.update_one(
                        {"_id": ObjectId(pendaftar_id)},
                        {"$set": {f"pendaftaran.{pendaftaran_index}": pendaftaran}}
                    )
                    return redirect(url_for("detail"))
            return jsonify({"message": "Pendaftaran tidak ditemukan atau sudah dikonfirmasi."}), 404
        else:
            return jsonify({"message": "Data pendaftar tidak ditemukan."}), 404
    except Exception as e:
        return jsonify({"message": str(e)}), 500

# route detail
@app.route("/detail", methods=["GET"])
def detail():
    token_receive = request.cookies.get("mytoken")
    try:
        payload = jwt.decode(token_receive, app.secret_key, algorithms=["HS256"])
        user_info = db.user.find_one({"nick": payload.get("nick")})
        pendaftar_list = list(pendaftar_collection.find({}, {'pendaftaran': 1, 'email': 1}))

        all_pendaftar_list = []
        for pendaftar in pendaftar_list:
            if 'pendaftaran' in pendaftar:
                for detail in pendaftar['pendaftaran']:
                    detail['_id'] = pendaftar['_id']
                    detail['email'] = pendaftar['email']
                    all_pendaftar_list.append(detail)

        print(all_pendaftar_list)
        return render_template("detail.html", nickname=user_info['nick'], pendaftar_list=all_pendaftar_list)
    except (jwt.ExpiredSignatureError, jwt.DecodeError):
        return redirect(url_for("index"))

@app.route("/login", methods=['GET'])
def login():
    msg = request.args.get('msg')
    return render_template('login.html', msg=msg)

@app.route("/api/login", methods=['POST'])
def api_login():
    username_receive = request.form.get('username_give')
    pw_receive = request.form.get('pw_give')
    pw_hash = hashlib.sha256(pw_receive.encode('utf-8')).hexdigest()
    result = db.user.find_one({
        'nick': username_receive,
        'pw': pw_hash,
    })

    if result:
        user_id = str(result.get('_id'))
        payload = {
            'user_id': user_id,
            'nick': username_receive,
            'exp': datetime.utcnow() + timedelta(minutes=60)
        }
        token = jwt.encode(payload, app.secret_key, algorithm='HS256')
        return jsonify({
            'result': 'success', 
            'token': token
        })
    else:
        return jsonify({
            'result': 'fail',
            'msg': 'Either your username or your password is incorrect'
        })
    
if __name__ == "__main__":
    app.run("0.0.0.0", port=5000, debug=True)
