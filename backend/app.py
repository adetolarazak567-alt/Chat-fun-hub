import os
import json
import time
import uuid
from pathlib import Path
from flask import Flask, request, send_file, jsonify, redirect, abort

# ---- Config ----
PORT = int(os.getenv("PORT", 5000))
DEBUG = os.getenv("DEBUG", "true").lower() in ("1", "true", "yes")

BASE_DIR = Path(__file__).parent.resolve()   # backend/
FRONTEND_DIR = BASE_DIR.parent               # root (frontend lives here)
UPLOAD_DIR = BASE_DIR / "uploads"
PACKS_FILE = BASE_DIR / "packs.json"
DL_FILE = BASE_DIR / "dl_counts.json"

# Create dirs
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

# ---- Helpers ----
def load_packs():
    if not PACKS_FILE.exists():
        seed = [
            {"id":"p1","cat":"stickers","title":"Nollywood Meme Pack","desc":"30 reaction stickers from Nollywood scenes.","thumb":"/uploads/default.png","files":["/uploads/sample1.zip"],"size":"1.2 MB","downloads":0},
            {"id":"p2","cat":"ringtones","title":"Afrobeats Short Clips","desc":"10 short royalty-free beats for ringtones.","thumb":"/uploads/default.png","files":["/uploads/sample2.mp3"],"size":"3.4 MB","downloads":0}
        ]
        PACKS_FILE.write_text(json.dumps(seed, indent=2))
        return seed
    return json.loads(PACKS_FILE.read_text())

def save_packs(packs):
    PACKS_FILE.write_text(json.dumps(packs, indent=2))

def find_pack(pack_id):
    for p in load_packs():
        if p["id"] == pack_id:
            return p
    return None

# ---- Flask app ----
app = Flask(
    __name__,
    static_folder=str(FRONTEND_DIR),
    static_url_path="/"
)

@app.route("/", defaults={"path": ""})
@app.route("/<path:path>")
def static_proxy(path):
    target = FRONTEND_DIR / (path or "index.html")
    if target.exists():
        return app.send_static_file(path or "index.html")
    abort(404)

@app.route("/api/packs", methods=["GET"])
def api_packs():
    packs = load_packs()
    dl_counts = json.loads(DL_FILE.read_text()) if DL_FILE.exists() else {}
    for p in packs:
        p["_dl"] = dl_counts.get(p["id"], 0)
    return jsonify(packs)

@app.route("/api/upload", methods=["POST"])
def api_upload():
    title = request.form.get("title", "").strip()
    cat = request.form.get("category", "stickers").strip()
    desc = request.form.get("description", "").strip()
    file = request.files.get("file")
    thumb = request.files.get("thumb")

    if not title or not file:
        return jsonify({"error": "title and file required"}), 400

    pid = f"p{int(time.time())}{uuid.uuid4().hex[:6]}"
    ext = Path(file.filename).suffix or ".bin"
    dest_file = f"{pid}{ext}"
    file.save(UPLOAD_DIR / dest_file)

    if thumb:
        t_ext = Path(thumb.filename).suffix or ".png"
        t_file = f"{pid}-thumb{t_ext}"
        thumb.save(UPLOAD_DIR / t_file)
        thumb_url = f"/uploads/{t_file}"
    else:
        thumb_url = "/uploads/default.png"

    new_pack = {
        "id": pid,
        "cat": cat,
        "title": title,
        "desc": desc,
        "thumb": thumb_url,
        "files": [f"/uploads/{dest_file}"],
        "size": f"{os.path.getsize(UPLOAD_DIR/dest_file)//1024} KB",
        "downloads": 0
    }

    packs = load_packs()
    packs.insert(0, new_pack)
    save_packs(packs)
    return jsonify({"ok": True, "pack": new_pack})

@app.route("/uploads/<path:filename>")
def serve_uploads(filename):
    fpath = UPLOAD_DIR / filename
    if not fpath.exists():
        abort(404)
    return send_file(fpath, as_attachment=True)

@app.route("/api/download/<pack_id>")
def api_download(pack_id):
    p = find_pack(pack_id)
    if not p:
        return jsonify({"error":"not found"}), 404

    dl_counts = json.loads(DL_FILE.read_text()) if DL_FILE.exists() else {}
    dl_counts[pack_id] = dl_counts.get(pack_id, 0) + 1
    DL_FILE.write_text(json.dumps(dl_counts, indent=2))

    file_url = p["files"][0]
    if file_url.startswith("/uploads/"):
        fname = file_url.replace("/uploads/","")
        return send_file(UPLOAD_DIR/fname, as_attachment=True)
    return redirect(file_url)

if __name__ == "__main__":
    print(f"Starting Flask app on port {PORT}")
    app.run(host="0.0.0.0", port=PORT, debug=DEBUG)
