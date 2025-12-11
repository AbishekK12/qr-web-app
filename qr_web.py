# qr_web.py full content placeholder due to size limits
# qr_web.py
# Single-file Flask app with MySQL storage for generated QR codes.
# Usage:
# 1) Set DATABASE_URL env var (optional). Default uses:
#    mysql+pymysql://qruser:StrongPass123@localhost/qrapp
# 2) pip install flask flask-sqlalchemy pymysql qrcode[pil] pillow
# 3) python qr_web.py
# 4) Open http://127.0.0.1:5000
#
# Note: create DB and user in MySQL beforehand:
#   CREATE DATABASE qrapp;
#   CREATE USER 'qruser'@'localhost' IDENTIFIED BY 'StrongPass123';
#   GRANT ALL ON qrapp.* TO 'qruser'@'localhost';
#   FLUSH PRIVILEGES;

import os
import base64
from io import BytesIO
from datetime import datetime
from flask import (
    Flask, request, redirect, url_for, render_template_string,
    send_file, abort
)
from werkzeug.utils import secure_filename
import qrcode
import qrcode.constants
from PIL import Image
from flask_sqlalchemy import SQLAlchemy

# ---------- Config ----------
APP_ROOT = os.path.dirname(os.path.abspath(__file__))
OUT_DIR = os.path.join(APP_ROOT, "generated")
UPLOADS_DIR = os.path.join(APP_ROOT, "uploads")
os.makedirs(OUT_DIR, exist_ok=True)
os.makedirs(UPLOADS_DIR, exist_ok=True)

ALLOWED_LOGO_EXT = {"png", "jpg", "jpeg", "gif", "webp"}

def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_LOGO_EXT

app = Flask(__name__)
db_url = os.environ.get(
    "DATABASE_URL",
    "mysql+pymysql://qruser:StrongPass123@localhost/qrapp"
)
app.config["SQLALCHEMY_DATABASE_URI"] = db_url
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["MAX_CONTENT_LENGTH"] = 2 * 1024 * 1024  # 2 MB upload cap for logos
db = SQLAlchemy(app)

# ---------- DB model ----------
class QRRecord(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    data = db.Column(db.Text, nullable=False)
    filename = db.Column(db.String(255), nullable=False)
    box_size = db.Column(db.Integer, default=10)
    border = db.Column(db.Integer, default=4)
    error_correction = db.Column(db.String(1), default="M")
    fg_color = db.Column(db.String(7), default="#000000")
    bg_color = db.Column(db.String(7), default="#ffffff")
    logo_path = db.Column(db.String(400), nullable=True)
    image_path = db.Column(db.String(400), nullable=False)
    download_count = db.Column(db.Integer, default=0)
    user_ip = db.Column(db.String(45), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

# ---------- HTML template ----------
HTML = """
<!doctype html>
<html>
<head>
  <meta charset="utf-8">
  <title>QR Code Generator</title>
  <style>
    body{font-family:Arial,Helvetica,sans-serif; max-width:900px; margin:24px auto; padding:0 16px}
    label{display:block;margin-top:10px}
    input, select{width:100%;padding:8px;margin-top:6px}
    button{padding:10px 14px;margin-top:12px}
    .row{display:flex;gap:10px}
    .col{flex:1}
    img{margin-top:12px;max-width:100%}
    table{width:100%;border-collapse:collapse;margin-top:18px}
    th,td{padding:8px;border:1px solid #ddd;text-align:left;font-size:14px}
    footer{margin-top:18px;color:#666;font-size:13px}
  </style>
</head>
<body>
  <h2>QR Code Generator</h2>
  <form method="post" action="/generate" enctype="multipart/form-data">
    <label>Text or URL</label>
    <input name="data" required placeholder="https://example.com or some text">

    <div class="row">
      <div class="col">
        <label>Box size (px)</label>
        <input name="box_size" type="number" value="10" min="1">
      </div>
      <div class="col">
        <label>Border (boxes)</label>
        <input name="border" type="number" value="4" min="0">
      </div>
    </div>

    <label>Error correction</label>
    <select name="ec">
      <option value="M" selected>M (15%)</option>
      <option value="L">L (7%)</option>
      <option value="Q">Q (25%)</option>
      <option value="H">H (30%)</option>
    </select>

    <div class="row">
      <div class="col">
        <label>Foreground color (hex)</label>
        <input name="fg" placeholder="#000000" value="#000000">
      </div>
      <div class="col">
        <label>Background color (hex)</label>
        <input name="bg" placeholder="#ffffff" value="#ffffff">
      </div>
    </div>

    <label>Optional logo (center). PNG/JPG/GIF. Max 2MB</label>
    <input type="file" name="logo">

    <label>Filename (optional)</label>
    <input name="filename" placeholder="qrcode.png">

    <button type="submit">Generate</button>
  </form>

  {% if img_url %}
    <h3>Result</h3>
    <img src="{{ img_url }}" alt="QR">
    <p><a href="/download/{{ record.id }}">Download PNG</a></p>
  {% endif %}

  <footer>
    <a href="/records">View saved records</a>
    <div>Generated files stored in /generated. Logos in /uploads.</div>
  </footer>
</body>
</html>
"""

# ---------- Helper functions ----------
EC_MAP = {
    "L": qrcode.constants.ERROR_CORRECT_L,
    "M": qrcode.constants.ERROR_CORRECT_M,
    "Q": qrcode.constants.ERROR_CORRECT_Q,
    "H": qrcode.constants.ERROR_CORRECT_H,
}

def make_qr_image(data, box_size, border, ec, fg, bg):
    qr = qrcode.QRCode(
        version=None,
        error_correction=ec,
        box_size=box_size,
        border=border,
    )
    qr.add_data(data)
    qr.make(fit=True)
    img = qr.make_image(fill_color=fg, back_color=bg).convert("RGBA")
    return img

def overlay_logo(base_img: Image.Image, logo_path: str, max_ratio=0.25):
    try:
        logo = Image.open(logo_path).convert("RGBA")
    except Exception:
        return base_img
    bw, bh = base_img.size
    max_w = int(bw * max_ratio)
    max_h = int(bh * max_ratio)
    logo.thumbnail((max_w, max_h), Image.ANTIALIAS)
    lw, lh = logo.size
    pos = ((bw - lw) // 2, (bh - lh) // 2)
    base_img.paste(logo, pos, logo)
    return base_img

def unique_filename(prefix="qrcode", ext=".png"):
    ts = datetime.utcnow().strftime("%Y%m%d%H%M%S%f")
    return f"{prefix}_{ts}{ext}"

def save_bytesio_to_disk(buf: BytesIO, folder: str, filename: str):
    path = os.path.join(folder, filename)
    with open(path, "wb") as f:
        f.write(buf.getvalue())
    return path

# ---------- Routes ----------
@app.route("/", methods=["GET"])
def index():
    return render_template_string(HTML, img_url=None)

@app.route("/generate", methods=["POST"])
def generate():
    data = (request.form.get("data") or "").strip()
    if not data:
        return redirect(url_for("index"))

    try:
        box_size = int(request.form.get("box_size", 10))
    except ValueError:
        box_size = 10
    try:
        border = int(request.form.get("border", 4))
    except ValueError:
        border = 4

    ec_key = request.form.get("ec", "M")
    ec = EC_MAP.get(ec_key, qrcode.constants.ERROR_CORRECT_M)

    fg = (request.form.get("fg") or "#000000").strip()
    bg = (request.form.get("bg") or "#ffffff").strip()

    # create base QR
    img = make_qr_image(data, box_size, border, ec, fg, bg)

    # handle logo upload
    logo_file = request.files.get("logo")
    logo_path = None
    if logo_file and logo_file.filename:
        filename_secure = secure_filename(logo_file.filename)
        if allowed_file(filename_secure):
            saved_logo_name = unique_filename("logo", os.path.splitext(filename_secure)[1])
            logo_path = os.path.join(UPLOADS_DIR, saved_logo_name)
            logo_file.save(logo_path)
            # overlay
            img = overlay_logo(img, logo_path)
        else:
            # ignore invalid extensions, proceed without logo
            logo_path = None

    # save image to buffer and disk
    buf = BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)

    fname = request.form.get("filename") or unique_filename("qrcode", ".png")
    if not fname.lower().endswith(".png"):
        fname += ".png"
    file_path = save_bytesio_to_disk(buf, OUT_DIR, fname)

    # record in DB
    user_ip = request.remote_addr
    rec = QRRecord(
        data=data,
        filename=fname,
        box_size=box_size,
        border=border,
        error_correction=ec_key,
        fg_color=fg,
        bg_color=bg,
        logo_path=logo_path,
        image_path=file_path,
        user_ip=user_ip
    )
    db.session.add(rec)
    db.session.commit()

    # encode for inline preview
    buf2 = BytesIO()
    img.save(buf2, format="PNG")
    data_url = "data:image/png;base64," + base64.b64encode(buf2.getvalue()).decode("ascii")

    return render_template_string(HTML, img_url=data_url, record=rec)

@app.route("/records", methods=["GET"])
def records():
    rows = QRRecord.query.order_by(QRRecord.created_at.desc()).limit(200).all()
    html = "<h2>Saved Records</h2>"
    html += ("<table><tr><th>ID</th><th>Data</th><th>Image</th><th>Downloads</th>"
             "<th>Logo</th><th>Created</th></tr>")
    for r in rows:
        html += "<tr>"
        html += f"<td>{r.id}</td>"
        html += f"<td style='max-width:300px;word-break:break-word'>{r.data}</td>"
        html += f"<td><a href='/view/{r.id}'>View</a> | <a href='/download/{r.id}'>Download</a></td>"
        html += f"<td>{r.download_count}</td>"
        html += f"<td>{('Yes' if r.logo_path else 'No')}</td>"
        html += f"<td>{r.created_at}</td>"
        html += "</tr>"
    html += "</table>"
    html += "<p><a href='/'>Back</a></p>"
    return html

@app.route("/view/<int:rec_id>", methods=["GET"])
def view_qr(rec_id):
    rec = QRRecord.query.get_or_404(rec_id)
    if not os.path.exists(rec.image_path):
        abort(404)
    return send_file(rec.image_path, mimetype="image/png")

@app.route("/download/<int:rec_id>", methods=["GET"])
def download_qr(rec_id):
    rec = QRRecord.query.get_or_404(rec_id)
    if not os.path.exists(rec.image_path):
        abort(404)
    rec.download_count = (rec.download_count or 0) + 1
    db.session.commit()
    return send_file(rec.image_path, mimetype="image/png", as_attachment=True, download_name=rec.filename)

# ---------- DB init helper (run once) ----------
def create_tables():
    with app.app_context():
        db.create_all()
        print("Tables created")

# ---------- Run ----------
if __name__ == "__main__":
    # If DB empty, create tables automatically on first run.
    try:
        create_tables()
    except Exception as e:
        print("Warning: create_tables failed. Check DB config.", e)
    app.run(debug=True)
