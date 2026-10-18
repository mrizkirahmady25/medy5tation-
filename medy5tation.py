import streamlit as st
import os
import io
import json
import html
import base64
import random
import string
import urllib.request
import urllib.error
from datetime import datetime, date
from urllib.parse import quote

try:
    from zoneinfo import ZoneInfo
    WIB = ZoneInfo("Asia/Jakarta")
except Exception:  # pragma: no cover
    WIB = None

# =====================================================================
# KONFIGURASI TOKO (Ubah sesuai kebutuhan)
# =====================================================================
WA_NUMBER = "6282289421650"
OPEN_HOUR, CLOSE_HOUR = 10, 21          # Jam buka toko (WIB)
OPEN_DAYS = [0, 1, 2, 3, 4, 5, 6]       # 0=Senin ... 6=Minggu
STORE_LAT, STORE_LON = -2.9761, 104.7754  # Titik koordinat peta Palembang
DATA_DIR = "data"
ORDERS_FILE = os.path.join(DATA_DIR, "orders.json")
REVIEWS_FILE = os.path.join(DATA_DIR, "reviews.json")

STATUS_FLOW = [
    "Diterima",
    "Sedang Dicek",
    "Menunggu Persetujuan",
    "Dikerjakan",
    "Selesai",
    "Sudah Diambil",
]

SERVICES = {
    "Jasa HEN PS4": 50_000,
    "Ganti Pasta Thermal + Deep Clean": 250_000,
    "Paket HDD Eksternal 500GB Full Game": 350_000,
    "Paket HDD Eksternal 1TB Full Game": 550_000,
}

PROMO_CODES = {
    "MEDY5HEMAT": ("Diskon Rp 15.000", 15_000),
    "PALEMBANGGG": ("Diskon Rp 10.000", 10_000),
}

# =====================================================================
# UTILITAS & SISTEM DATABASE HYBRID (SUPABASE CLOUD + JSON LOKAL)
# =====================================================================
def now():
    return datetime.now(WIB) if WIB else datetime.now()


def rupiah(n):
    try:
        return "Rp " + f"{int(n):,}".replace(",", ".")
    except Exception:
        return "Rp 0"


def wa_link(text=""):
    return f"https://wa.me/{WA_NUMBER}?text={quote(text)}"


def html_block(s):
    """Render HTML tanpa indentasi supaya tidak dibaca sebagai code block markdown."""
    clean = "\n".join(line.strip() for line in s.splitlines() if line.strip())
    st.markdown(clean, unsafe_allow_html=True)


def get_image_base64(path):
    if os.path.exists(path):
        with open(path, "rb") as f:
            return base64.b64encode(f.read()).decode()
    return None


def _supabase_creds():
    """Ambil kredensial Supabase dari st.secrets atau environment variable."""
    try:
        url = st.secrets.get("SUPABASE_URL", "").rstrip("/")
        key = st.secrets.get("SUPABASE_KEY", "")
        if url and key:
            return url, key
    except Exception:
        pass
    url = os.environ.get("SUPABASE_URL", "").rstrip("/")
    key = os.environ.get("SUPABASE_KEY", "")
    return (url, key) if (url and key) else (None, None)


def is_cloud_db_active():
    url, key = _supabase_creds()
    return bool(url and key)


def load_json(path, default):
    """Baca dari Supabase Cloud jika aktif, fallback ke file JSON lokal."""
    db_key = os.path.basename(path)
    url, key = _supabase_creds()

    if url and key:
        try:
            req_url = f"{url}/rest/v1/app_storage?key=eq.{quote(db_key)}&select=value"
            req = urllib.request.Request(
                req_url,
                headers={
                    "apikey": key,
                    "Authorization": f"Bearer {key}",
                    "Accept": "application/json",
                },
                method="GET",
            )
            with urllib.request.urlopen(req, timeout=5) as resp:
                rows = json.loads(resp.read().decode("utf-8"))
                if rows and isinstance(rows, list) and "value" in rows[0]:
                    return rows[0]["value"]
                return default
        except Exception:
            pass

    try:
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
    except Exception:
        pass
    return default


def save_json(path, data):
    """Simpan ke Supabase Cloud (Upsert) sekaligus simpan cadangan di file lokal."""
    db_key = os.path.basename(path)
    url, key = _supabase_creds()
    cloud_saved = False

    if url and key:
        try:
            req_url = f"{url}/rest/v1/app_storage"
            payload = json.dumps({
                "key": db_key,
                "value": data,
                "updated_at": now().isoformat()
            }).encode("utf-8")

            req = urllib.request.Request(
                req_url,
                data=payload,
                headers={
                    "apikey": key,
                    "Authorization": f"Bearer {key}",
                    "Content-Type": "application/json",
                    "Prefer": "resolution=merge-duplicates",
                },
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=5) as resp:
                if resp.status in (200, 201, 204):
                    cloud_saved = True
        except Exception:
            cloud_saved = False

    local_saved = False
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        local_saved = True
    except Exception:
        pass

    return cloud_saved or local_saved


def new_ticket(existing):
    while True:
        code = "MD-" + "".join(random.choices(string.ascii_uppercase + string.digits, k=5))
        if code not in existing:
            return code


def admin_password():
    try:
        pw = st.secrets.get("ADMIN_PASSWORD")
        if pw:
            return pw
    except Exception:
        pass
    return os.environ.get("ADMIN_PASSWORD", "medy5admin")


def store_status():
    t = now()
    is_open = t.weekday() in OPEN_DAYS and OPEN_HOUR <= t.hour < CLOSE_HOUR
    return is_open, t


def calc_pkg_install_price(game_count):
    if game_count <= 0:
        return 0
    bundles = game_count // 3
    remainder = game_count % 3
    return (bundles * 65_000) + (remainder * 25_000)


# =====================================================================
# LOGO STIK DS4 & TIPOGRAFI MEDY5TATION (SESUAI GAMBAR BARU)
# =====================================================================
CONTROLLER_SVG = """
<svg class="controller-logo" viewBox="0 0 360 220" xmlns="http://www.w3.org/2000/svg" role="img" aria-label="Logo Stik MEDY5TATION">
  <!-- Bumper L1 & R1 -->
  <path d="M 82 40 C 86 24, 118 24, 126 38" fill="none" stroke="#d92b5a" stroke-width="4" stroke-linecap="round"/>
  <path d="M 278 40 C 274 24, 242 24, 234 38" fill="none" stroke="#d92b5a" stroke-width="4" stroke-linecap="round"/>
  <path d="M 92 33 L 116 33" fill="none" stroke="#d92b5a" stroke-width="2.5" stroke-linecap="round"/>
  <path d="M 244 33 L 268 33" fill="none" stroke="#d92b5a" stroke-width="2.5" stroke-linecap="round"/>

  <!-- Bodi Utama Stik DualShock 4 -->
  <path d="M 126 38
           L 234 38
           C 256 38, 272 44, 282 60
           C 294 82, 305 128, 308 160
           C 311 190, 288 206, 268 198
           C 250 190, 240 162, 230 136
           L 130 136
           C 120 162, 110 190, 92 198
           C 72 206, 49 190, 52 160
           C 55 128, 66 82, 78 60
           C 88 44, 104 38, 126 38 Z"
        fill="#131924" stroke="#d92b5a" stroke-width="5.5" stroke-linejoin="round"/>

  <!-- Garis Lekukan Grip Bawah -->
  <path d="M 54 166 C 68 176, 86 174, 101 164" fill="none" stroke="#d92b5a" stroke-width="3.5" stroke-linecap="round"/>
  <path d="M 306 166 C 292 176, 274 174, 259 164" fill="none" stroke="#d92b5a" stroke-width="3.5" stroke-linecap="round"/>

  <!-- Touchpad Tengah & Lightbar -->
  <rect x="132" y="42" width="96" height="50" rx="6" fill="#131924" stroke="#d92b5a" stroke-width="4"/>
  <line x1="146" y1="42" x2="214" y2="42" stroke="#f43f5e" stroke-width="5" stroke-linecap="round"/>

  <!-- Tombol Share & Options -->
  <rect x="120" y="46" width="6" height="12" rx="3" fill="none" stroke="#d92b5a" stroke-width="2.2"/>
  <rect x="234" y="46" width="6" height="12" rx="3" fill="none" stroke="#d92b5a" stroke-width="2.2"/>

  <!-- Lubang Speaker Tengah -->
  <g fill="#d92b5a">
    <circle cx="172" cy="100" r="1.6"/><circle cx="177" cy="100" r="1.6"/><circle cx="183" cy="100" r="1.6"/><circle cx="188" cy="100" r="1.6"/>
    <circle cx="170" cy="104" r="1.6"/><circle cx="175" cy="104" r="1.6"/><circle cx="180" cy="104" r="1.6"/><circle cx="185" cy="104" r="1.6"/><circle cx="190" cy="104" r="1.6"/>
    <circle cx="174" cy="108" r="1.6"/><circle cx="180" cy="108" r="1.6"/><circle cx="186" cy="108" r="1.6"/>
  </g>

  <!-- Lingkaran Frame D-Pad (Kiri) & Action Buttons (Kanan) -->
  <circle cx="98" cy="82" r="32" fill="#131924" stroke="#d92b5a" stroke-width="3.5"/>
  <circle cx="262" cy="82" r="32" fill="#131924" stroke="#d92b5a" stroke-width="3.5"/>

  <!-- D-Pad (Arah Kiri) -->
  <g fill="none" stroke="#d92b5a" stroke-width="2.8" stroke-linejoin="round">
    <!-- Atas -->
    <path d="M 93 57 L 103 57 L 103 70 L 98 75 L 93 70 Z"/>
    <!-- Bawah -->
    <path d="M 93 107 L 103 107 L 103 94 L 98 89 L 93 94 Z"/>
    <!-- Kiri -->
    <path d="M 73 77 L 73 87 L 86 87 L 91 82 L 86 77 Z"/>
    <!-- Kanan -->
    <path d="M 123 77 L 123 87 L 110 87 L 105 82 L 110 77 Z"/>
  </g>

  <!-- Tombol Action (Segitiga Toska/Hijau, Bulat/Kotak/Silang Merah) -->
  <!-- Atas: Segitiga -->
  <circle cx="262" cy="61" r="8.5" fill="none" stroke="#d92b5a" stroke-width="2.2"/>
  <polygon points="262,55.5 257,64.5 267,64.5" fill="none" stroke="#2dd4bf" stroke-width="2.2" stroke-linejoin="round"/>
  <!-- Bawah: Silang (X) -->
  <circle cx="262" cy="103" r="8.5" fill="none" stroke="#d92b5a" stroke-width="2.2"/>
  <path d="M 258.5 99.5 L 265.5 106.5 M 265.5 99.5 L 258.5 106.5" stroke="#d92b5a" stroke-width="2.2" stroke-linecap="round"/>
  <!-- Kiri: Kotak -->
  <circle cx="241" cy="82" r="8.5" fill="none" stroke="#d92b5a" stroke-width="2.2"/>
  <rect x="237" y="78" width="8" height="8" rx="1" fill="none" stroke="#d92b5a" stroke-width="2.2"/>
  <!-- Kanan: Lingkaran -->
  <circle cx="283" cy="82" r="8.5" fill="none" stroke="#d92b5a" stroke-width="2.2"/>
  <circle cx="283" cy="82" r="4.5" fill="none" stroke="#d92b5a" stroke-width="2.2"/>

  <!-- Analog Kiri & Kanan (Multi-Ring) -->
  <g fill="#131924">
    <circle cx="142" cy="120" r="22" stroke="#d92b5a" stroke-width="4.5"/>
    <circle cx="142" cy="120" r="14" stroke="#d92b5a" stroke-width="3"/>
    <circle cx="142" cy="120" r="9" stroke="#d92b5a" stroke-width="1.8"/>

    <circle cx="218" cy="120" r="22" stroke="#d92b5a" stroke-width="4.5"/>
    <circle cx="218" cy="120" r="14" stroke="#d92b5a" stroke-width="3"/>
    <circle cx="218" cy="120" r="9" stroke="#d92b5a" stroke-width="1.8"/>
  </g>

  <!-- Tombol PS di Tengah Analog -->
  <rect x="173" y="116" width="14" height="13" rx="3" fill="#131924" stroke="#d92b5a" stroke-width="2.5"/>
  <path d="M 177 125 L 177 119 L 181 119 C 183 119, 183 122, 181 122 L 177 122 M 180 124 L 184 124" fill="none" stroke="#d92b5a" stroke-width="1.6" stroke-linecap="round"/>
</svg>
"""

# Tipografi SVG "MEDY5TATION" dengan huruf 'D' terbuka di sisi kiri persis seperti gambar
BRAND_WORDMARK_SVG = """
<svg class="brand-wordmark" viewBox="0 0 540 56" xmlns="http://www.w3.org/2000/svg" role="img" aria-label="MEDY5TATION">
  <style>
    .md-txt { font-family: 'Kanit', 'Montserrat', sans-serif; font-size: 46px; font-weight: 800; fill: #ffffff; letter-spacing: 3px; }
  </style>
  <!-- M E -->
  <text x="22" y="44" class="md-txt">ME</text>
  <!-- Huruf D Custom (Tanpa garis vertikal kiri, melengkung seperti di gambar) -->
  <path d="M 108 13.5 L 130 13.5 C 142 13.5, 149 20, 149 28.5 C 149 37, 142 43.5, 130 43.5 L 108 43.5"
        fill="none" stroke="#ffffff" stroke-width="7.5" stroke-linecap="butt" stroke-linejoin="round"/>
  <!-- Y 5 T A T I O N -->
  <text x="158" y="44" class="md-txt">Y5TATION</text>
</svg>
"""

# =====================================================================
# STYLING (DARK NAVY & CRIMSON NEON SESUAI TEMA GAMBAR)
# =====================================================================
def set_page_styling():
    st.set_page_config(
        page_title="MEDY5TATION - Game Together",
        page_icon="🎮",
        layout="wide",
        initial_sidebar_state="collapsed",
    )
    st.markdown(
        '<link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/bootstrap-icons@1.11.3/font/bootstrap-icons.min.css">',
        unsafe_allow_html=True,
    )
    custom_css = """
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Kanit:wght@300;400;600;700;800&family=Satisfy&display=swap');

        .stApp { background-color: #131924 !important; color: #ffffff !important; font-family: 'Kanit', sans-serif !important; }
        .stApp label, .stApp p, .stApp span, .stApp li { font-family: 'Kanit', sans-serif; }

        .brand-container { text-align: center; padding: 10px 0 4px 0; }
        .controller-logo {
            width: 220px; max-width: 75%; height: auto; display: block; margin: 0 auto 4px auto;
            filter: drop-shadow(0 0 14px rgba(217, 43, 90, 0.35));
        }
        .brand-wordmark {
            width: 340px; max-width: 92%; height: auto; display: block; margin: 2px auto 0 auto;
        }
        @media (prefers-reduced-motion: no-preference) {
            .controller-logo { animation: mdFloat 4s ease-in-out infinite; }
            @keyframes mdFloat { 0%,100% { transform: translateY(0); } 50% { transform: translateY(-5px); } }
        }
        .brand-logo-img { max-width: 240px; width: 100%; height: auto; border-radius: 14px; display: block; margin: 0 auto 8px auto; }
        .cursive-title { font-family: 'Satisfy', cursive !important; color: #d92b5a !important; font-size: 2.6rem; line-height: 1.1; margin: 0; text-align: left; }
        .cursive-subtitle { font-family: 'Satisfy', cursive !important; color: #05d9e8 !important; font-size: 2.2rem; line-height: 1.1; margin: 0; text-align: right; }
        .brand-subtitle { font-size: .9rem; letter-spacing: 4px; color: #94a3b8; margin-top: 6px; margin-bottom: 18px; font-weight: 700; }

        .status-pill { display: inline-flex; align-items: center; gap: 8px; padding: 6px 14px; border-radius: 999px; font-size: .85rem; font-weight: 600; border: 1px solid; }
        .status-open { color: #10b981; border-color: #10b981; background: rgba(16,185,129,.08); }
        .status-closed { color: #f87171; border-color: #f87171; background: rgba(248,113,113,.08); }
        .dot { width: 8px; height: 8px; border-radius: 50%; background: currentColor; display: inline-block; }

        .feature-bar { display: flex; justify-content: space-around; text-align: center; margin-bottom: 25px; flex-wrap: wrap; gap: 12px; background: #0d121b; border: 1px solid #1e293b; border-radius: 16px; padding: 14px 10px; }
        .feature-item { display: flex; flex-direction: column; align-items: center; gap: 4px; color: #e2e8f0; font-size: .8rem; font-weight: 600; }

        div[data-baseweb="tab-list"] { gap: 8px !important; justify-content: flex-start !important; padding-bottom: 10px !important; border-bottom: 1px solid #1e293b !important; background: transparent !important; overflow-x: auto; }
        div[data-baseweb="tab"] { background: #0d121b !important; border: 1px solid #1e293b !important; border-radius: 8px !important; padding: 8px 14px !important; white-space: nowrap; transition: all .2s; }
        div[data-baseweb="tab"] p, div[data-baseweb="tab"] span { color: #cbd5e1 !important; font-weight: 600 !important; font-size: .9rem !important; }
        div[data-baseweb="tab"][aria-selected="true"] { border-color: #d92b5a !important; background: rgba(217,43,90,.14) !important; }
        div[data-baseweb="tab"][aria-selected="true"] p, div[data-baseweb="tab"][aria-selected="true"] span { color: #ff2a6d !important; font-weight: 700 !important; }
        div[data-baseweb="tab-highlight"] { display: none !important; }

        .card-box { border-radius: 14px; padding: 22px 18px; margin-bottom: 15px; height: 100%; background-color: #0d121b; color: #fff; transition: transform .2s, box-shadow .2s; }
        .card-box:hover { transform: translateY(-3px); box-shadow: 0 8px 24px rgba(0,0,0,.45); }
        .border-cyan { border: 1.5px solid #05d9e8 !important; }
        .border-pink { border: 1.5px solid #d92b5a !important; }
        .border-purple { border: 1.5px solid #a855f7 !important; }
        .border-green { border: 1.5px solid #10b981 !important; }

        .price-badge-cyan { color: #05d9e8 !important; font-size: 2.2rem; font-weight: 800; line-height: 1.1; }
        .price-badge-pink { color: #d92b5a !important; font-size: 2.2rem; font-weight: 800; line-height: 1.1; }
        .price-badge-purple { color: #c084fc !important; font-size: 1.6rem; font-weight: 800; }
        .promo-banner { background: linear-gradient(90deg,#d92b5a,#be123c); color: #fff; font-size: .8rem; font-weight: 700; padding: 6px; border-radius: 6px; margin-top: 12px; letter-spacing: .5px; }

        .list-item-dark { background: rgba(255,255,255,.04); border: 1px solid rgba(255,255,255,.08); padding: 10px 14px; border-radius: 8px; margin-bottom: 8px; font-size: .88rem; color: #fff; display: flex; justify-content: space-between; align-items: center; }

        .game-badge { background-color: #0d121b !important; border: 1px solid #1e293b !important; border-radius: 10px; padding: 10px 12px; margin-bottom: 8px; font-size: .85rem; display: flex; align-items: center; justify-content: space-between; gap: 8px; transition: all .15s; }
        .game-badge:hover { border-color: #d92b5a !important; background-color: #161f30 !important; }
        .game-num { color: #d92b5a !important; font-weight: 800; font-size: .82rem; min-width: 28px; }
        .size-pill { background: rgba(5,217,232,.12); color: #05d9e8; border: 1px solid rgba(5,217,232,.3); padding: 2px 7px; border-radius: 99px; font-size: .72rem; font-weight: 700; white-space: nowrap; }

        .hdd-bar-wrap { background: #1e293b; border-radius: 99px; height: 14px; width: 100%; overflow: hidden; margin: 8px 0; }
        .hdd-bar-fill { height: 100%; background: linear-gradient(90deg, #05d9e8, #d92b5a); transition: width .3s ease; }

        .social-link { display: inline-flex; align-items: center; justify-content: center; gap: 8px; padding: 10px 16px; border-radius: 8px; font-weight: 600; text-decoration: none !important; font-size: .9rem; margin-bottom: 8px; width: 100%; text-align: center; }
        .btn-wa { background-color: #25D366; color: #fff !important; }
        .btn-shopee { background-color: #EE4D2D; color: #fff !important; }
        .btn-tiktok { background-color: #000; border: 1px solid #374151; color: #fff !important; }
        .btn-ig { background: linear-gradient(45deg,#f09433 0%,#e6683c 25%,#dc2743 50%,#cc2366 75%,#bc1888 100%); color: #fff !important; }
        .btn-yt { background-color: #f00; color: #fff !important; }

        /* Tracker & Timeline */
        .track { display: flex; gap: 6px; margin: 14px 0 6px 0; }
        .track .step { flex: 1; height: 8px; border-radius: 4px; background: #1e293b; }
        .track .step.done { background: linear-gradient(90deg,#d92b5a,#05d9e8); }
        .ticket-code { font-size: 2.1rem; font-weight: 800; letter-spacing: 3px; color: #05d9e8; }
        .log-item { border-left: 2px solid #05d9e8; padding-left: 12px; margin-bottom: 8px; font-size: .83rem; color: #cbd5e1; }

        .review { background: #0d121b; border: 1px solid #1e293b; border-left: 3px solid #d92b5a; border-radius: 10px; padding: 12px 16px; margin-bottom: 10px; }
        .review .stars { color: #f59e0b; letter-spacing: 2px; font-size: 1.05rem; }
        .review small { color: #94a3b8; }

        .total-box { background: #0d121b; border: 1.5px solid #05d9e8; border-radius: 14px; padding: 18px; text-align: center; margin-bottom: 12px; }
        .total-box .amount { font-size: 2.2rem; font-weight: 800; color: #05d9e8; }

        /* Tombol WhatsApp melayang */
        .wa-float { position: fixed; right: 18px; bottom: 18px; z-index: 9999; background: #25D366; color: #fff !important; width: 54px; height: 54px; border-radius: 50%; display: flex; align-items: center; justify-content: center; font-size: 1.7rem; text-decoration: none !important; box-shadow: 0 6px 18px rgba(0,0,0,.5); }

        /* Input gelap */
        .stTextInput input, .stTextArea textarea, .stSelectbox div[data-baseweb="select"] > div, .stDateInput input, .stNumberInput input { background-color: #0d121b !important; color: #fff !important; }
        </style>
    """
    st.markdown(custom_css, unsafe_allow_html=True)


# =====================================================================
# DATA KATALOG & META UKURAN GAME
# =====================================================================
PS4_GAMES = [
    "GOW 3", "GTA 5 MOD SUB INDO", "THE LAST OF US 1", "THE LAST OF US 2", "NARUTO CONNECTION",
    "DAYS GONE", "DEVIL MAY CRY 5", "A WAY OUT", "IT TAKES TWO", "SEKIRO",
    "RESIDENT EVIL 2", "GOD OF WAR 2018", "Hogwarts legacy", "Assasins creed syndicate", "Assasins creed valhala",
    "Resident evil 3", "Resident evil 7", "Resident evil 8", "Watch dog 2", "Resident evil 4",
    "Uncharted 4", "Uncharted lost legacy", "The Witcher", "Stray", "Fatal frame",
    "Kena", "Assasins creed unity", "Elden ring", "Gta SA definitif edition", "Sleeping dog",
    "Assasin creed mirage", "GTA 3 DEFINITIF EDITION", "GTA VICE CITY DEFINITIF EDITION", "Gow Ragnarok", "Assassin creed ezio collection",
    "assassin creed origins", "visage", "Assassin Black Flag", "Bayonetta", "Harvest moon AWL spesial",
    "Harvest moon sth", "Sifu", "Resident evil 5", "Assassin creed 3", "Lies op P",
    "assasins creed Oddysey", "ghost of tsusima", "Basara 4 sumeragi", "dead island 2", "mafia 1",
    "mafia 2", "mafia 3", "Cyberpunk", "Resident evil 6", "Evil west",
    "Watchdog 1", "nier automata", "plague tale", "persona 3", "The calisto protocol",
    "Bloodborne", "Mortal kombat 11", "Stody of season", "Stars wars jedi survivor", "Tomb raider 1-3 remastered",
    "Gta 5 daeng nuansa Indonesia", "Uncharted nathan Drake", "Immortal hinyx", "Ghost recob", "Lego City Undercover",
    "Death Door", "One piece Oddysey", "Yakuza 3", "Control", "Judghment",
    "Horizon zero down", "Spiderman", "Spiderman Miles morales", "detroit", "death stranding",
]


def get_game_meta(title):
    t = title.lower()
    if any(k in t for k in ["ragnarok", "tlou 2", "last of us 2", "valhala", "cyberpunk", "jedi survivor", "oddysey"]):
        size = 85
    elif any(k in t for k in ["gta 5", "god of war 2018", "days gone", "hogwarts", "elden", "spiderman", "horizon", "ghost of", "uncharted 4", "witcher", "death stranding", "mortal kombat"]):
        size = 52
    elif any(k in t for k in ["resident evil", "assassin", "mafia", "devil may cry", "it takes two", "bloodborne", "calisto", "dead island", "naruto", "nier", "persona", "control", "judghment"]):
        size = 34
    elif any(k in t for k in ["stray", "sifu", "kena", "harvest moon", "stody of season", "bayonetta", "visage", "fatal frame", "death door", "tomb raider"]):
        size = 14
    else:
        size = 25

    if any(k in t for k in ["resident evil", "visage", "fatal frame", "calisto", "dead island", "last of us"]):
        cat = "Horror / Survival"
    elif any(k in t for k in ["assassin", "gta", "watch", "sleeping dog", "cyberpunk", "mafia", "horizon", "ghost", "spiderman", "days gone", "witcher"]):
        cat = "Open World / Action"
    elif any(k in t for k in ["it takes two", "a way out", "naruto", "mortal kombat", "basara", "lego"]):
        cat = "Co-op / Multiplayer"
    elif any(k in t for k in ["elden", "sekiro", "bloodborne", "lies", "persona", "one piece", "hogwarts"]):
        cat = "RPG / Adventure"
    else:
        cat = "Action / Story"
    return size, cat


PS4_HEN_UPDATES = [
    "Monster patch summer 2027",
    "Eleven Patch summer 2027 Final Update",
    "Bitbox patch summer 2027",
    "Leader patch summer 2027",
    "monster 2018 patch summer 2027",
]
PS3_BOLA_UPDATES = ["Bitbox patch", "Vr patch"]
ANDROID_SERVICES = ["Spotify mod premium", "Netflix (Nonton film gabungan vidio viu dkk)"]
SWITCH_GAMES = ["DREDGE", "STRAY", "RDR", "Zelda BOTW"]

FAQ = [
    ("Berapa lama pengerjaan servis?",
     "Tergantung jenis dan tingkat kerusakan. Ganti pasta thermal dan servis stik biasanya lebih cepat dari kerusakan mesin. "
     "Estimasi pasti diberikan setelah unit dicek lewat WhatsApp atau di workshop."),
    ("Apakah bisa konsultasi dulu sebelum servis?",
     "Bisa. Kirim keluhan dan foto/video kondisi unit lewat WhatsApp, lalu kami bantu perkiraan penyebab dan biayanya."),
    ("Bagaimana cara memantau progres servis?",
     "Setelah booking lewat tab Booking Servis, kamu mendapat kode tiket. Masukkan kode itu di tab Cek Status kapan saja."),
    ("Apa saja yang dikerjakan di Jasa HEN PS4?",
     "Instalasi sistem HEN, setting dan tes game lengkap, serta panduan pemakaian sampai paham."),
    ("Kapan sebaiknya ganti pasta thermal?",
     "Jika kipas makin bising, mesin cepat panas, atau game mulai patah-patah dan konsol mati sendiri."),
    ("Bagaimana cara order game Sub Indo?",
     "Bisa langsung centang judul game di tab Katalog & Pilih Game, pilih metode (Via Drive / Install di PS / Paket HDD), lalu klik pesan via WhatsApp."),
]

TROUBLESHOOT = {
    "PS4 cepat panas / kipas bising": [
        "Pastikan ventilasi belakang dan samping tidak tertutup, jarak minimal 10 cm dari dinding.",
        "Letakkan konsol di tempat datar dan tidak di dalam rak tertutup.",
        "Bersihkan debu pada lubang udara dengan blower atau vacuum dari luar.",
        "Jika masih panas atau bising, kemungkinan pasta thermal sudah kering dan perlu diganti.",
    ],
    "Stik drift (kursor bergerak sendiri)": [
        "Masuk Settings - Devices - Controllers dan cek apakah gerakan muncul tanpa disentuh.",
        "Matikan stik, lepas dari charger, lalu tekan tombol reset kecil di bagian belakang stik.",
        "Bersihkan area sekitar analog dengan isopropil alkohol.",
        "Jika masih drift, modul analog biasanya perlu diganti lewat Servis Stik.",
    ],
    "Stik tidak mau connect / cepat habis": [
        "Pakai kabel USB data yang bagus, sambungkan ke konsol, lalu tekan tombol PS.",
        "Lakukan reset stik dengan jarum pada lubang reset di belakang.",
        "Baterai yang drop cepat biasanya perlu diganti.",
    ],
    "Konsol mati sendiri saat main": [
        "Cek suhu dan ventilasi lebih dulu.",
        "Coba kabel power lain dan stop kontak lain (hindari colokan bertumpuk).",
        "Jika berulang, bawa untuk dicek: bisa karena overheat APU atau masalah power supply (PSU).",
    ],
    "Download / loading game lambat": [
        "Cek ruang penyimpanan, sisakan minimal 15-20% ruang kosong.",
        "Gunakan kabel LAN jika memungkinkan untuk koneksi lebih stabil.",
        "HDD internal yang sudah lemah (health turun) bisa diganti SSD atau HDD baru.",
    ],
}

# =====================================================================
# KOMPONEN HALAMAN UTAMA
# =====================================================================
def render_header():
    col_h1, col_h2, col_h3 = st.columns([1.2, 3, 1.2])
    with col_h1:
        st.markdown('<p class="cursive-title">Good Games<br>Better Days</p>', unsafe_allow_html=True)
    with col_h2:
        # Render langsung SVG Stik DS4 Merah + Tipografi MEDY5TATION sesuai gambar baru
        html_block(
            f'<div class="brand-container">'
            f'{CONTROLLER_SVG}'
            f'{BRAND_WORDMARK_SVG}'
            f'<div class="brand-subtitle">PLAY MORE • GAME TOGETHER</div>'
            f'</div>'
        )
    with col_h3:
        st.markdown(
            '''
            <div style="text-align: right; color: #94a3b8; font-size: 0.85rem; margin-bottom: 8px;">
                <b>PS4 &bull; PS3 &bull; SWITCH &bull; ANDROID</b>
            </div>
            <p class="cursive-subtitle">Game<br>Tanpa<br>Batas</p>
            ''',
            unsafe_allow_html=True,
        )

    is_open, t = store_status()
    cls, label = ("status-open", f"Workshop Buka · Tutup {CLOSE_HOUR}:00 WIB") if is_open else (
        "status-closed", f"Workshop Tutup · Buka {OPEN_HOUR}:00 WIB")
    html_block(
        f'<div style="text-align:center; margin-bottom:16px;">'
        f'<span class="status-pill {cls}"><span class="dot"></span>{label} (Waktu Lokal: {t.strftime("%H:%M")} WIB)</span></div>'
    )


def render_feature_bar():
    html_block('''
        <div class="feature-bar">
            <div class="feature-item"><i class="bi bi-disc" style="font-size:1.5rem;color:#d92b5a;"></i><span>GAME ORIGINAL &amp; HEN</span></div>
            <div class="feature-item"><i class="bi bi-translate" style="font-size:1.5rem;color:#05d9e8;"></i><span>80+ PATCH SUB INDO</span></div>
            <div class="feature-item"><i class="bi bi-device-hdd" style="font-size:1.5rem;color:#a855f7;"></i><span>HDD FULL GAME PNP</span></div>
            <div class="feature-item"><i class="bi bi-tools" style="font-size:1.5rem;color:#f59e0b;"></i><span>SERVIS &amp; MAINTENANCE</span></div>
            <div class="feature-item"><i class="bi bi-shield-check" style="font-size:1.5rem;color:#10b981;"></i><span>AMAN &amp; BERGARANSI</span></div>
        </div>
    ''')


# ---------------- Tab 1: Paket & Layanan ----------------
def tab_paket():
    st.write("")
    p1, p2, p3 = st.columns(3)
    with p1:
        html_block('''
            <div class="card-box border-cyan" style="text-align:center;">
                <i class="bi bi-cloud-arrow-down-fill" style="font-size:2.2rem;color:#05d9e8;"></i>
                <div style="font-size:.95rem;font-weight:700;margin-top:10px;">VIA GOOGLE DRIVE</div>
                <div class="price-badge-cyan">15K</div>
                <small style="color:#94a3b8;font-weight:600;">PER GAME</small>
                <p style="font-size:.82rem;color:#cbd5e1;margin-top:16px;">File Patch Sub Indo &amp; Link Download GDrive berkecepatan tinggi sesuai CUSA game kamu.</p>
            </div>''')
    with p2:
        html_block('''
            <div class="card-box border-pink" style="text-align:center;">
                <i class="bi bi-box-arrow-in-down" style="font-size:2.2rem;color:#d92b5a;"></i>
                <div style="font-size:.95rem;font-weight:700;margin-top:10px;">PKG &amp; INSTAL DI PS</div>
                <div class="price-badge-pink">25K</div>
                <small style="color:#94a3b8;font-weight:600;">PER GAME</small>
                <div class="promo-banner">🔥 PROMO: 3 GAME HANYA 65K</div>
                <small style="color:#94a3b8;display:block;margin-top:10px;">Bawa konsol ke Workshop Palembang, terima beres siap main.</small>
            </div>''')
    with p3:
        html_block('''
            <div class="card-box border-purple" style="text-align:center;">
                <i class="bi bi-hdd-network-fill" style="font-size:2.2rem;color:#a855f7;"></i>
                <div style="font-size:.95rem;font-weight:700;margin-top:10px;">HDD FULL GAME (PKG/PNP)</div>
                <div style="display:flex;justify-content:space-around;margin-top:12px;">
                    <div><span style="background:#fff;color:#0b0f19;padding:2px 8px;border-radius:4px;font-size:.75rem;font-weight:800;">500GB</span>
                    <div class="price-badge-purple" style="margin-top:4px;">350RB</div></div>
                    <div><span style="background:#fff;color:#0b0f19;padding:2px 8px;border-radius:4px;font-size:.75rem;font-weight:800;">1TB</span>
                    <div class="price-badge-purple" style="margin-top:4px;">550RB</div></div>
                </div>
                <small style="color:#94a3b8;display:block;margin-top:16px;">Bebas pilih judul game di tab Katalog sampai kapasitas penuh!</small>
            </div>''')

    st.write("")
    s1, s2, s3 = st.columns(3)
    with s1:
        html_block('''
            <div class="card-box border-cyan">
                <i class="bi bi-cpu" style="font-size:1.8rem;color:#05d9e8;"></i>
                <div style="font-size:.95rem;font-weight:700;margin-top:8px;">JASA HEN PS4</div>
                <div class="price-badge-cyan">50K</div>
                <ul style="font-size:.82rem;padding-left:18px;margin:10px 0 0 0;color:#cbd5e1;line-height:1.6;">
                    <li>Instalasi Sistem GoldHEN Stabil</li>
                    <li>Setting &amp; Tes Game Lengkap</li>
                    <li>Panduan Pemakaian Sampai Paham</li>
                </ul>
            </div>''')
    with s2:
        html_block('''
            <div class="card-box border-pink">
                <i class="bi bi-thermometer-half" style="font-size:1.8rem;color:#d92b5a;"></i>
                <div style="font-size:.95rem;font-weight:700;margin-top:8px;">GANTI PASTA THERMAL</div>
                <div class="price-badge-pink">250RB</div>
                <ul style="font-size:.82rem;padding-left:18px;margin:10px 0 0 0;color:#cbd5e1;line-height:1.6;">
                    <li>Deep Cleaning / Pembersihan Total Debu Heatsink</li>
                    <li>Aplikasi Thermal Paste Kualitas Tinggi</li>
                    <li>Meredam Kipas Bising (Jet Engine) &amp; Cegah Overheat</li>
                </ul>
            </div>''')
    with s3:
        html_block('''
            <div class="card-box border-purple">
                <i class="bi bi-joystick" style="font-size:1.8rem;color:#a855f7;"></i>
                <div style="font-size:.95rem;font-weight:700;margin-top:8px;">SERVIS STIK PS4 / PS5</div>
                <div class="price-badge-purple" style="margin-bottom:6px;">KONSULTASI</div>
                <ul style="font-size:.82rem;padding-left:18px;margin:6px 0 0 0;color:#cbd5e1;line-height:1.6;">
                    <li>Perbaikan Analog Drift / Upgrade Hall Effect</li>
                    <li>Ganti Karet Konduktif / Film PCB / Baterai</li>
                    <li>Kustomisasi Casing &amp; Tombol</li>
                </ul>
            </div>''')


# ---------------- Tab 2: Katalog Game & Simulator HDD ----------------
def tab_games():
    st.write("")
    if "cart_games" not in st.session_state:
        st.session_state["cart_games"] = []

    with st.expander("🛒 **Keranjang Pilih Game & Simulator Kapasitas HDD** (Klik untuk buka/tutup)", expanded=bool(st.session_state["cart_games"])):
        col_b1, col_b2 = st.columns([2, 1.2])
        with col_b1:
            selected = st.multiselect(
                "Pilih game yang ingin kamu pesan / masukkan ke HDD:",
                options=PS4_GAMES,
                default=st.session_state["cart_games"],
                placeholder="Ketik atau pilih beberapa judul game...",
            )
            st.session_state["cart_games"] = selected

            mode_order = st.radio(
                "Metode Pemesanan Game:",
                ["Via Google Drive (15K/game)", "Install Langsung di PS (25K/game · Promo 3 Game 65K)", "Paket HDD 500GB (350RB)", "Paket HDD 1TB (550RB)"],
                horizontal=True,
            )

        with col_b2:
            total_gb = sum(get_game_meta(g)[0] for g in selected)
            jml = len(selected)

            if "500GB" in mode_order:
                max_gb = 460
                est_harga = 350_000
            elif "1TB" in mode_order:
                max_gb = 930
                est_harga = 550_000
            elif "Drive" in mode_order:
                max_gb = 0
                est_harga = jml * 15_000
            else:
                max_gb = 0
                est_harga = calc_pkg_install_price(jml)

            html_block(f'''
                <div class="total-box" style="margin-bottom:8px;">
                    <small style="color:#94a3b8;">{jml} GAME DIPILIH (~{total_gb} GB)</small>
                    <div class="amount">{rupiah(est_harga)}</div>
                </div>
            ''')

            if max_gb > 0:
                pct = min(100, int((total_gb / max_gb) * 100))
                status_hdd = f"Terpakai ~{total_gb} GB dari {max_gb} GB ({pct}%)"
                html_block(f'''
                    <div class="hdd-bar-wrap"><div class="hdd-bar-fill" style="width:{pct}%;"></div></div>
                    <small style="color:{"#f87171" if total_gb > max_gb else "#94a3b8"};">{status_hdd}</small>
                ''')
                if total_gb > max_gb:
                    st.warning("Kapasitas melebihi batas efektif HDD! Kurangi beberapa game atau upgrade ke 1TB.")

            if selected:
                game_list_str = "\n".join(f"{i+1}. {g} (~{get_game_meta(g)[0]}GB)" for i, g in enumerate(selected))
                wa_msg = (
                    f"Halo MEDY5TATION, saya mau order game Sub Indo:\n"
                    f"Metode: *{mode_order}*\n"
                    f"Jumlah: {jml} Game (Estimasi ~{total_gb} GB)\n"
                    f"Estimasi Biaya: *{rupiah(est_harga)}*\n\n"
                    f"Daftar Game:\n{game_list_str}"
                )
                st.link_button("📲 Pesan Daftar Game Ini via WhatsApp", wa_link(wa_msg), use_container_width=True)

    c1, c2, c3 = st.columns([2.2, 1.2, 1])
    with c1:
        q = st.text_input("🔍 Cari Judul Game Patch Bahasa Indonesia:", placeholder="Contoh: God of War, Spiderman, Resident Evil...")
    with c2:
        cat_filter = st.selectbox("Kategori / Genre", ["Semua Genre", "Action / Story", "Open World / Action", "RPG / Adventure", "Horror / Survival", "Co-op / Multiplayer"])
    with c3:
        sort_mode = st.selectbox("Urutkan", ["Sesuai Daftar", "A → Z", "Z → A", "Ukuran Terbesar", "Ukuran Terkecil"])

    items = []
    for i, g in enumerate(PS4_GAMES):
        sz, cat = get_game_meta(g)
        items.append((i + 1, g, sz, cat))

    if q:
        items = [x for x in items if q.lower() in x[1].lower()]
    if cat_filter != "Semua Genre":
        items = [x for x in items if x[3] == cat_filter]

    if sort_mode == "A → Z":
        items.sort(key=lambda x: x[1].lower())
    elif sort_mode == "Z → A":
        items.sort(key=lambda x: x[1].lower(), reverse=True)
    elif sort_mode == "Ukuran Terbesar":
        items.sort(key=lambda x: x[2], reverse=True)
    elif sort_mode == "Ukuran Terkecil":
        items.sort(key=lambda x: x[2])

    st.caption(f"Menampilkan **{len(items)}** dari **{len(PS4_GAMES)}** judul game Sub Indo")
    if not items:
        st.info("Game yang dicari belum ada di daftar. Tanyakan langsung lewat WhatsApp, kami siap bantu carikan!")
        st.link_button("Tanya Ketersediaan Game via WhatsApp", wa_link(f"Halo MEDY5TATION, apakah ada game Sub Indo: {q}?"))
        return

    cols = st.columns(4)
    chunk = (len(items) + 3) // 4
    for ci, col in enumerate(cols):
        with col:
            for n, g, sz, cat in items[ci * chunk:(ci + 1) * chunk]:
                html_block(f'''
                    <div class="game-badge">
                        <div style="display:flex;align-items:center;gap:8px;">
                            <span class="game-num">#{n}</span>
                            <div>
                                <div style="color:#fff;font-weight:600;line-height:1.2;">{html.escape(g)}</div>
                                <small style="color:#64748b;font-size:.7rem;">{cat}</small>
                            </div>
                        </div>
                        <span class="size-pill">~{sz} GB</span>
                    </div>''')


# ---------------- Tab 3 & 4: Bola, Android & Switch ----------------
def _list_card(title, icon, color_cls, color, rows):
    items = "".join(
        f'<div class="list-item-dark"><span><b style="color:{color};margin-right:6px;">{i + 1}.</b> {html.escape(r)}</span>'
        f'<i class="bi bi-check2-circle" style="color:{color};"></i></div>'
        for i, r in enumerate(rows)
    )
    html_block(f'''
        <div class="card-box {color_cls}">
            <div style="font-size:1.05rem;font-weight:700;color:{color};margin-bottom:15px;">
                <i class="bi {icon}"></i> {title}
            </div>{items}
        </div>''')


def tab_bola():
    st.write("")
    b1, b2 = st.columns(2)
    with b1:
        _list_card("UPDATE BOLA PS4 HEN (SUMMER 2027)", "bi-dribbble", "border-pink", "#d92b5a", PS4_HEN_UPDATES)
    with b2:
        _list_card("UPDATE BOLA PS3", "bi-controller", "border-cyan", "#05d9e8", PS3_BOLA_UPDATES)
    st.write("")
    st.link_button("⚽ Pesan Update Patch Bola via WhatsApp", wa_link("Halo MEDY5TATION, saya ingin tanya/order Update Patch Bola terbaru."))


def tab_extra():
    st.write("")
    e1, e2 = st.columns(2)
    with e1:
        _list_card("ANDROID APPS &amp; STREAMING", "bi-android2", "border-green", "#10b981", ANDROID_SERVICES)
    with e2:
        _list_card("NINTENDO SWITCH SUB INDO", "bi-nintendo-switch", "border-pink", "#d92b5a", SWITCH_GAMES)
    st.write("")
    st.link_button("📱 Tanya Layanan Android / Switch via WhatsApp", wa_link("Halo MEDY5TATION, saya ingin order layanan Android / Game Switch Sub Indo."))


# ---------------- Tab 5: Kalkulator Biaya All-in-One ----------------
def tab_kalkulator():
    st.write("")
    st.subheader("🧮 Kalkulator Estimasi Biaya (Layanan & Game)")
    st.caption("Gabungkan layanan servis, pembelian paket game, dan gunakan kode promo jika ada.")

    left, right = st.columns([1.8, 1.2])
    lines = []

    with left:
        st.markdown("##### 1. Layanan Servis & Paket HDD")
        for name, price in SERVICES.items():
            c1, c2 = st.columns([3, 1])
            with c1:
                use = st.checkbox(f"{name} ({rupiah(price)})", key=f"calc_{name}")
            with c2:
                qty = st.number_input("Jml", 1, 10, 1, key=f"qty_{name}", label_visibility="collapsed", disabled=not use)
            if use:
                lines.append((name, qty, qty * price))

        st.markdown("##### 2. Satuan Game Sub Indo")
        cg1, cg2 = st.columns(2)
        with cg1:
            jml_drive = st.number_input("Jumlah Game Via Google Drive (15K/game)", 0, 50, 0)
            if jml_drive > 0:
                lines.append(("Game Sub Indo Via GDrive", jml_drive, jml_drive * 15_000))
        with cg2:
            jml_pkg = st.number_input("Jumlah Game Install di PS (25K / 3=65K)", 0, 50, 0)
            if jml_pkg > 0:
                harga_pkg = calc_pkg_install_price(jml_pkg)
                lines.append(("Game Install Langsung di PS (Promo diterapkan)", jml_pkg, harga_pkg))

        st.markdown("##### 3. Servis Stik & Voucher Promo")
        cs1, cs2 = st.columns(2)
        with cs1:
            stik_qty = st.number_input("Jumlah Stik Diservis (Harga Konsultasi)", 0, 10, 0)
            keluhan_stik = st.selectbox("Keluhan Utama Stik", ["Analog Drift", "Tombol Tidak Responsif / Keras", "Mati Total / Tidak Connect", "Ganti Baterai / Casing"]) if stik_qty else ""
        with cs2:
            kode_promo = st.text_input("Kode Voucher Promo (Opsional)", placeholder="Contoh: MEDY5HEMAT").strip().upper()

    subtotal = sum(sub for _, _, sub in lines)
    diskon = 0
    ket_promo = ""
    if kode_promo and kode_promo in PROMO_CODES and subtotal >= 50_000:
        ket_promo, diskon = PROMO_CODES[kode_promo]
    elif kode_promo and kode_promo not in PROMO_CODES:
        st.toast("Kode promo tidak ditemukan.", icon="⚠️")

    total = max(0, subtotal - diskon)

    with right:
        html_block(f'''
            <div class="total-box">
                <small style="color:#94a3b8;">ESTIMASI TOTAL BIAYA</small>
                <div class="amount">{rupiah(total)}</div>
                {f'<small style="color:#10b981;">Hemat {rupiah(diskon)} ({ket_promo})</small>' if diskon else ''}
            </div>
        ''')

        if lines or stik_qty:
            st.markdown("**Rincian Pesanan:**")
            msg = "Halo MEDY5TATION, saya ingin memesan layanan berikut:\n"
            for n, q, sub in lines:
                st.write(f"• {n} (x{q}) = **{rupiah(sub)}**")
                msg += f"- {n} x{q} = {rupiah(sub)}\n"
            if stik_qty:
                st.write(f"• Servis Stik x{stik_qty} ({keluhan_stik}) = **Konsultasi**")
                msg += f"- Servis Stik x{stik_qty} ({keluhan_stik}) = Konsultasi\n"
            if diskon:
                msg += f"Promo ({kode_promo}): -{rupiah(diskon)}\n"
            msg += f"\n*Total Estimasi: {rupiah(total)}*"

            st.link_button("📲 Kirim Rincian ke WhatsApp", wa_link(msg), use_container_width=True)
        else:
            st.info("Centang layanan atau masukkan jumlah game di sebelah kiri untuk melihat rincian harga.")


# ---------------- Tab 6: Booking Servis ----------------
def tab_booking():
    st.write("")
    st.subheader("🔧 Form Booking Servis & Instalasi")
    st.caption("Isi data unit konsol/stik kamu untuk mendapatkan Kode Tiket pelacakan progres.")

    with st.form("booking_form", clear_on_submit=True):
        c1, c2 = st.columns(2)
        with c1:
            nama = st.text_input("Nama Lengkap *")
            wa = st.text_input("Nomor WhatsApp Aktif *", placeholder="08xxxxxxxxxx")
            perangkat = st.selectbox("Jenis Perangkat", ["PS4 Fat", "PS4 Slim", "PS4 Pro", "PS3", "Stik PS4 (DS4)", "Stik PS5 (DualSense)", "Nintendo Switch", "HDD Eksternal", "Lainnya"])
            metode_antar = st.selectbox("Metode Penyerahan Unit", ["Datang Langsung ke Workshop", "Kirim via Kurir Instan (Gojek/Grab/Maxim)", "Kirim Ekspedisi Luar Kota"])
        with c2:
            layanan = st.selectbox("Layanan Utama", ["Jasa HEN PS4", "Ganti Pasta Thermal + Deep Clean", "Isi Game PS4 Sub Indo", "Servis Stik PS4 / PS5", "Cek / Diagnosa Kerusakan", "Lainnya"])
            tgl = st.date_input("Rencana Tanggal Datang / Kirim", min_value=date.today())
            keluhan = st.text_area("Detail Keluhan / Catatan Tambahan", placeholder="Contoh: Mesin cepat panas dan bunyi kipas kencang, atau daftar game yang ingin diisi...")
        kirim = st.form_submit_button("🚀 Buat Tiket Servis Sekarang")

    if kirim:
        if not nama.strip() or not wa.strip():
            st.error("Nama dan nomor WhatsApp wajib diisi.")
            return
        orders = load_json(ORDERS_FILE, {})
        code = new_ticket(orders)
        waktu_skrg = now().strftime("%Y-%m-%d %H:%M")
        orders[code] = {
            "nama": nama.strip(),
            "wa": wa.strip(),
            "perangkat": perangkat,
            "metode": metode_antar,
            "layanan": layanan,
            "tanggal": str(tgl),
            "keluhan": keluhan.strip(),
            "status": STATUS_FLOW[0],
            "catatan": "Tiket berhasil dibuat. Silakan konfirmasi via WhatsApp.",
            "biaya_final": 0,
            "dibuat": waktu_skrg,
            "riwayat": [{"waktu": waktu_skrg, "status": STATUS_FLOW[0], "ket": "Booking dibuat oleh pelanggan"}],
        }
        saved = save_json(ORDERS_FILE, orders)
        st.session_state["last_ticket"] = code
        st.session_state["last_ticket_saved"] = saved
        st.session_state["last_ticket_msg"] = (
            f"Halo MEDY5TATION, saya *{nama.strip()}*.\n"
            f"Saya sudah buat Tiket Servis: *{code}*\n"
            f"- Perangkat: {perangkat}\n"
            f"- Layanan: {layanan}\n"
            f"- Metode: {metode_antar}\n"
            f"- Rencana Tanggal: {tgl}\n"
            f"- Keluhan/Catatan: {keluhan.strip() or '-'}"
        )

    if st.session_state.get("last_ticket"):
        code = st.session_state["last_ticket"]
        html_block(f'''
            <div class="card-box border-cyan" style="text-align:center;height:auto;">
                <small style="color:#94a3b8;">KODE TIKET SERVIS KAMU</small>
                <div class="ticket-code">{code}</div>
                <p style="color:#cbd5e1;font-size:.88rem;margin:6px 0;">Simpan atau screenshot kode ini untuk memantau progres di tab <b>Cek Status</b>.</p>
            </div>''')
        if not st.session_state.get("last_ticket_saved"):
            st.warning("Catatan: Penyimpanan lokal server sedang terbatas. Pastikan kamu menekan tombol Konfirmasi WhatsApp di bawah ini.")
        st.link_button("📲 Konfirmasi Tiket via WhatsApp", wa_link(st.session_state["last_ticket_msg"]), use_container_width=True)


# ---------------- Tab 7: Cek Status & Cetak Nota ----------------
def generate_receipt_html(code, o):
    biaya = rupiah(o.get("biaya_final", 0)) if o.get("biaya_final") else "Menunggu Konfirmasi"
    return f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"><title>Struk Servis {code}</title>
<style>
body {{ font-family: Arial, sans-serif; background:#f8fafc; padding:30px; color:#0f172a; }}
.box {{ max-width:500px; margin:auto; background:#fff; padding:24px; border-radius:12px; border:2px solid #0f172a; }}
h2 {{ margin:0; color:#d92b5a; letter-spacing:2px; }}
.row {{ display:flex; justify-content:space-between; padding:8px 0; border-bottom:1px dashed #cbd5e1; font-size:14px; }}
.footer {{ text-align:center; margin-top:20px; font-size:12px; color:#64748b; }}
</style></head><body>
<div class="box">
  <h2>MEDY5TATION PALEMBANG</h2>
  <p style="margin:4px 0 16px 0;font-size:12px;">Tegal Binangun Sasana Patra · WA: +{WA_NUMBER}</p>
  <div class="row"><b>KODE TIKET</b><b>{html.escape(code)}</b></div>
  <div class="row"><span>Nama Pelanggan</span><span>{html.escape(o.get('nama','-'))}</span></div>
  <div class="row"><span>Perangkat</span><span>{html.escape(o.get('perangkat','-'))}</span></div>
  <div class="row"><span>Layanan</span><span>{html.escape(o.get('layanan','-'))}</span></div>
  <div class="row"><span>Status Terakhir</span><b>{html.escape(o.get('status','-'))}</b></div>
  <div class="row"><span>Tanggal Dibuat</span><span>{html.escape(o.get('dibuat','-'))}</span></div>
  <div class="row"><span>Total Biaya</span><b>{biaya}</b></div>
  <p style="font-size:13px;margin-top:14px;"><b>Catatan Teknisi:</b><br>{html.escape(o.get('catatan') or '-')}</p>
  <div class="footer">Terima kasih telah mempercayakan konsol Anda di MEDY5TATION!</div>
</div></body></html>"""


def tab_status():
    st.write("")
    st.subheader("🔎 Lacak Status Servis Real-Time")
    default_code = st.session_state.get("last_ticket", "")
    code = st.text_input("Masukkan Kode Tiket (Contoh: MD-XXXXX)", value=default_code, placeholder="MD-XXXXX").strip().upper()
    if not code:
        st.caption("Kode tiket didapat setelah kamu mengisi form di tab Booking Servis.")
        return

    orders = load_json(ORDERS_FILE, {})
    o = orders.get(code)
    if not o:
        st.error("Kode tiket tidak ditemukan. Pastikan penulisan benar (menggunakan awalan MD-) atau hubungi admin via WhatsApp.")
        return

    idx = STATUS_FLOW.index(o["status"]) if o["status"] in STATUS_FLOW else 0
    steps = "".join(f'<div class="step {"done" if i <= idx else ""}"></div>' for i in range(len(STATUS_FLOW)))
    biaya_str = rupiah(o["biaya_final"]) if o.get("biaya_final", 0) > 0 else "Menunggu Pengecekan"
    note = f'<div style="background:rgba(5,217,232,.08);border-left:3px solid #05d9e8;padding:10px;margin-top:12px;border-radius:6px;font-size:.88rem;"><b>Catatan Teknisi:</b> {html.escape(o["catatan"])}</div>' if o.get("catatan") else ""

    html_block(f'''
        <div class="card-box border-pink" style="height:auto;">
            <div style="display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;">
                <small style="color:#94a3b8;">TIKET #{code} · {html.escape(o.get("nama", ""))}</small>
                <span class="size-pill">Biaya: {biaya_str}</span>
            </div>
            <div style="font-size:1.5rem;font-weight:800;color:#d92b5a;margin-top:4px;">{html.escape(o["status"])}</div>
            <div class="track">{steps}</div>
            <small style="color:#94a3b8;">Tahap {idx + 1} dari {len(STATUS_FLOW)}: {" → ".join(STATUS_FLOW)}</small>
            <p style="margin:12px 0 4px 0;font-weight:600;">{html.escape(o["layanan"])} · {html.escape(o["perangkat"])}</p>
            <small style="color:#94a3b8;">Dibuat pada: {o["dibuat"]} | Metode: {html.escape(o.get("metode", "Workshop"))}</small>
            {note}
        </div>''')

    if o.get("riwayat"):
        with st.expander("🕒 Lihat Riwayat Update Tiket", expanded=True):
            for log in reversed(o["riwayat"]):
                html_block(f'''
                    <div class="log-item">
                        <b style="color:#05d9e8;">{html.escape(log.get("status", ""))}</b> — <small>{html.escape(log.get("waktu", ""))}</small><br>
                        <span>{html.escape(log.get("ket", ""))}</span>
                    </div>
                ''')

    c_btn1, c_btn2 = st.columns(2)
    with c_btn1:
        st.link_button("📲 Tanya Teknisi via WhatsApp", wa_link(f"Halo MEDY5TATION, mau tanya progres tiket servis {code} atas nama {o.get('nama', '')}."), use_container_width=True)
    with c_btn2:
        receipt_html = generate_receipt_html(code, o)
        st.download_button("🧾 Unduh Struk / Nota Digital (HTML)", receipt_html, file_name=f"Nota_{code}.html", mime="text/html", use_container_width=True)


# ---------------- Tab 8: Bantuan & Lokasi ----------------
def tab_bantuan():
    st.write("")
    c1, c2 = st.columns([3, 2])
    with c1:
        st.subheader("❓ Pertanyaan Umum (FAQ)")
        for q, a in FAQ:
            with st.expander(q):
                st.write(a)
        st.subheader("🩺 Diagnosa Mandiri Kerusakan Konsol")
        masalah = st.selectbox("Pilih gejala yang kamu alami:", list(TROUBLESHOOT.keys()))
        for step in TROUBLESHOOT[masalah]:
            st.markdown(f"- {step}")
        st.caption("Jika langkah di atas belum menyelesaikan masalah, silakan buat tiket di tab Booking Servis.")
    with c2:
        st.subheader("📍 Lokasi Workshop & Jam Operasional")
        html_block(f'''
            <div class="card-box border-purple" style="height:auto;">
                <b><i class="bi bi-geo-alt-fill" style="color:#d92b5a;"></i> TEGAL BINANGUN SASANA PATRA</b>
                <p style="color:#94a3b8;margin:4px 0 10px 0;">Plaju / Jakabaring, Kota Palembang, Sumatera Selatan</p>
                <p style="margin:0;">🕒 Jam Operasional: <b>{OPEN_HOUR}:00 – {CLOSE_HOUR}:00 WIB</b> (Setiap Hari)</p>
            </div>''')
        st.map({"lat": [STORE_LAT], "lon": [STORE_LON]}, zoom=12)
        st.link_button("🗺️ Minta Shareloc Presisi via WhatsApp", wa_link("Halo MEDY5TATION, boleh minta shareloc workshop Tegal Binangun?"), use_container_width=True)


# ---------------- Tab 9: Testimoni Pelanggan ----------------
def tab_testimoni():
    st.write("")
    reviews = load_json(REVIEWS_FILE, [])
    st.subheader("⭐ Testimoni & Ulasan Pelanggan")

    if reviews:
        avg = sum(int(r.get("rating", 5)) for r in reviews) / len(reviews)
        st.markdown(f"### ⭐ **{avg:.1f} / 5.0** dari **{len(reviews)}** ulasan pelanggan")

    left, right = st.columns([2, 1])
    with left:
        if not reviews:
            st.info("Belum ada ulasan. Jadilah pelanggan pertama yang memberikan ulasan!")
        for r in reversed(reviews[-20:]):
            rt = max(1, min(5, int(r.get("rating", 5))))
            stars = ("★" * rt) + ("☆" * (5 - rt))
            layanan_tag = f' · <span style="color:#05d9e8;">{html.escape(r.get("layanan", "Pelanggan"))}</span>' if r.get("layanan") else ""
            html_block(f'''
                <div class="review">
                    <div class="stars">{stars}</div>
                    <div style="margin:6px 0;font-size:.92rem;">{html.escape(r.get("teks", ""))}</div>
                    <small><b>{html.escape(r.get("nama", "Anonim"))}</b>{layanan_tag} · {html.escape(r.get("waktu", ""))}</small>
                </div>''')

    with right:
        with st.form("review_form", clear_on_submit=True):
            st.markdown("##### Tulis Ulasan Kamu")
            nama = st.text_input("Nama Kamu *")
            layanan_ulasan = st.selectbox("Layanan yang Digunakan", ["Isi Game Sub Indo", "Paket HDD Full Game", "Jasa HEN PS4", "Ganti Pasta Thermal", "Servis Stik", "Update Bola / Lainnya"])
            rating = st.slider("Rating Kepuasan", 1, 5, 5)
            teks = st.text_area("Pengalaman Kamu *", max_chars=300, placeholder="Pelayanan ramah, game lancar jaya...")
            ok = st.form_submit_button("🌟 Kirim Ulasan")
        if ok:
            if not nama.strip() or not teks.strip():
                st.error("Nama dan isi ulasan wajib diisi.")
            else:
                reviews.append({
                    "nama": nama.strip()[:40],
                    "layanan": layanan_ulasan,
                    "rating": int(rating),
                    "teks": teks.strip(),
                    "waktu": now().strftime("%d %b %Y"),
                })
                if save_json(REVIEWS_FILE, reviews):
                    st.success("Terima kasih atas ulasan positifmu!")
                    st.rerun()
                else:
                    st.error("Ulasan belum bisa disimpan di server.")


# ---------------- Tab 10: Panel Admin Pro ----------------
def tab_admin():
    st.write("")
    st.subheader("🔐 Panel Admin & Manajemen Workshop")
    if not st.session_state.get("is_admin"):
        c_login, _ = st.columns([1, 2])
        with c_login:
            pw = st.text_input("Password Admin", type="password")
            if st.button("Masuk Panel Admin", use_container_width=True):
                if pw == admin_password():
                    st.session_state["is_admin"] = True
                    st.rerun()
                else:
                    st.error("Password salah!")
            st.caption("Default password lokal: `medy5admin` (Ubah via `st.secrets['ADMIN_PASSWORD']`).")
        return

    top1, top2 = st.columns([5, 1])
    with top2:
        if st.button("🚪 Keluar Admin", use_container_width=True):
            st.session_state["is_admin"] = False
            st.rerun()

    if is_cloud_db_active():
        st.success("☁️ **Status Database: Terhubung ke Supabase Cloud (Penyimpanan Permanen Aktif)**")
    else:
        st.warning("📁 **Status Database: Penyimpanan Lokal (Sementara)** — Tambahkan `SUPABASE_URL` & `SUPABASE_KEY` di Secrets agar permanen.")

    orders = load_json(ORDERS_FILE, {})
    reviews = load_json(REVIEWS_FILE, [])

    total_omzet = sum(int(o.get("biaya_final", 0)) for o in orders.values())
    aktif_count = sum(1 for o in orders.values() if o.get("status") not in STATUS_FLOW[-2:])
    selesai_count = sum(1 for o in orders.values() if o.get("status") in STATUS_FLOW[-2:])

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Total Tiket Masuk", len(orders))
    m2.metric("Sedang Dikerjakan", aktif_count)
    m3.metric("Selesai / Diambil", selesai_count)
    m4.metric("Total Omzet Tercatat", rupiah(total_omzet))

    st.markdown("---")
    st.markdown("#### 📋 Kelola Tiket Servis")

    if not orders:
        st.info("Belum ada data tiket servis yang masuk.")
    else:
        fc1, fc2 = st.columns(2)
        with fc1:
            filt = st.selectbox("Filter Status", ["Semua"] + STATUS_FLOW)
        with fc2:
            cari_tiket = st.text_input("Cari Nama / Nomor WA / Kode Tiket").strip().lower()

        rows = []
        for k, v in orders.items():
            if filt != "Semua" and v.get("status") != filt:
                continue
            if cari_tiket and not (cari_tiket in k.lower() or cari_tiket in v.get("nama", "").lower() or cari_tiket in v.get("wa", "").lower()):
                continue
            rows.append({
                "Tiket": k,
                "Nama": v.get("nama", ""),
                "WA": v.get("wa", ""),
                "Perangkat": v.get("perangkat", ""),
                "Layanan": v.get("layanan", ""),
                "Status": v.get("status", ""),
                "Biaya (Rp)": v.get("biaya_final", 0),
                "Tanggal": v.get("tanggal", ""),
            })

        st.dataframe(rows, use_container_width=True, hide_index=True)

        st.markdown("##### ✏️ Update Tiket Pelanggan")
        pick = st.selectbox("Pilih Kode Tiket untuk Diedit:", list(orders.keys()))
        o = orders[pick]

        c1, c2, c3 = st.columns([1.2, 1.2, 2])
        with c1:
            new_status = st.selectbox("Status Baru", STATUS_FLOW, index=STATUS_FLOW.index(o["status"]) if o["status"] in STATUS_FLOW else 0)
        with c2:
            new_biaya = st.number_input("Biaya Final / Tagihan (Rp)", min_value=0, step=10_000, value=int(o.get("biaya_final", 0)))
        with c3:
            new_note = st.text_input("Catatan Teknisi untuk Pelanggan", value=o.get("catatan", ""))

        b1, b2, b3 = st.columns(3)
        if b1.button("💾 Simpan Perubahan Tiket", use_container_width=True):
            waktu_up = now().strftime("%Y-%m-%d %H:%M")
            orders[pick]["status"] = new_status
            orders[pick]["biaya_final"] = new_biaya
            orders[pick]["catatan"] = new_note
            if "riwayat" not in orders[pick]:
                orders[pick]["riwayat"] = []
            orders[pick]["riwayat"].append({
                "waktu": waktu_up,
                "status": new_status,
                "ket": f"{new_note} (Biaya: {rupiah(new_biaya)})" if new_biaya else new_note,
            })
            save_json(ORDERS_FILE, orders)
            st.success(f"Tiket {pick} berhasil diperbarui!")
            st.rerun()

        wa_to = "".join(ch for ch in o.get("wa", "") if ch.isdigit())
        if wa_to.startswith("0"):
            wa_to = "62" + wa_to[1:]
        pesan_wa_pelanggan = (
            f"Halo Kak *{o.get('nama', '')}*, update untuk Tiket Servis *{pick}* ({o.get('perangkat', '')}):\n"
            f"- Status Saat Ini: *{new_status}*\n"
            f"- Biaya: *{rupiah(new_biaya) if new_biaya else 'Menunggu konfirmasi'}*\n"
            f"- Catatan Teknisi: {new_note or '-'}\n\n"
            f"Terima kasih! — *MEDY5TATION Palembang*"
        )
        b2.link_button("📲 Kirim Notifikasi WA ke Pelanggan", f"https://wa.me/{wa_to}?text=" + quote(pesan_wa_pelanggan), use_container_width=True)

        if b3.button("🗑️ Hapus Tiket Ini", use_container_width=True):
            orders.pop(pick, None)
            save_json(ORDERS_FILE, orders)
            st.rerun()

        buf = io.StringIO()
        buf.write("tiket,nama,wa,perangkat,layanan,tanggal,status,biaya_final,catatan,dibuat,keluhan\n")
        for k, v in orders.items():
            vals = [k, v.get("nama", ""), v.get("wa", ""), v.get("perangkat", ""), v.get("layanan", ""), v.get("tanggal", ""), v.get("status", ""),
                    v.get("biaya_final", 0), v.get("catatan", ""), v.get("dibuat", ""), v.get("keluhan", "")]
            buf.write(",".join('"' + str(x).replace('"', '""') + '"' for x in vals) + "\n")
        st.download_button("📥 Unduh Laporan Semua Tiket (CSV)", buf.getvalue(), "laporan_tiket_medy5tation.csv", "text/csv")

    st.markdown("---")
    col_mod, col_bak = st.columns(2)

    with col_mod:
        st.markdown("#### ⭐ Moderasi Ulasan")
        if not reviews:
            st.caption("Belum ada ulasan.")
        for i, r in enumerate(reviews):
            c1, c2 = st.columns([5, 1])
            rt = max(1, min(5, int(r.get("rating", 5))))
            bintang_str = "★" * rt
            c1.write(f"{bintang_str} **{r.get('nama', '')}**: {r.get('teks', '')}")
            if c2.button("Hapus", key=f"delrev_{i}"):
                reviews.pop(i)
                save_json(REVIEWS_FILE, reviews)
                st.rerun()

    with col_bak:
        st.markdown("#### 💾 Backup & Restore Database JSON")
        st.caption("Gunakan fitur ini untuk mem-backup atau memulihkan seluruh data tiket & ulasan.")
        full_db = json.dumps({"orders": orders, "reviews": reviews}, ensure_ascii=False, indent=2)
        st.download_button("⬇️ Backup Database (JSON)", full_db, file_name=f"medy5_backup_{now().strftime('%Y%m%d')}.json", mime="application/json", use_container_width=True)

        up_file = st.file_uploader("⬆️ Restore dari File Backup JSON", type=["json"])
        if up_file is not None:
            if st.button("Proses Restore Database", use_container_width=True):
                try:
                    loaded = json.loads(up_file.read().decode("utf-8"))
                    if "orders" in loaded:
                        save_json(ORDERS_FILE, loaded["orders"])
                    if "reviews" in loaded:
                        save_json(REVIEWS_FILE, loaded["reviews"])
                    st.success("Database berhasil di-restore!")
                    st.rerun()
                except Exception as e:
                    st.error(f"File JSON tidak valid: {e}")


# ---------------- Footer ----------------
def render_footer():
    st.markdown('<hr style="border-color:#1e293b;margin:35px 0 25px 0;">', unsafe_allow_html=True)
    sec_lokasi, sec_order, sec_social = st.columns([1.5, 2, 2.5])
    with sec_lokasi:
        html_block('''
            <div style="margin-bottom:8px;">
                <small style="color:#94a3b8;letter-spacing:1px;font-weight:700;">LOKASI WORKSHOP</small>
                <div style="font-weight:800;font-size:1.25rem;margin-top:4px;">
                    <i class="bi bi-geo-alt-fill" style="color:#d92b5a;"></i> PALEMBANG</div>
                <div style="font-size:.88rem;color:#94a3b8;margin-top:2px;">TEGAL BINANGUN SASANA PATRA</div>
            </div>''')
    with sec_order:
        html_block(f'''
            <small style="color:#94a3b8;letter-spacing:1px;font-weight:700;">ORDER &amp; OFFICIAL STORE</small><br>
            <div style="display:flex;flex-direction:column;gap:8px;margin-top:8px;">
                <a href="{wa_link()}" target="_blank" class="social-link btn-wa"><i class="bi bi-whatsapp"></i> Chat WhatsApp</a>
                <a href="https://id.shp.ee/FdsB8oxh" target="_blank" class="social-link btn-shopee"><i class="bi bi-bag-fill"></i> Shopee Store</a>
            </div>''')
    with sec_social:
        html_block('''
            <small style="color:#94a3b8;letter-spacing:1px;font-weight:700;">SOSIAL MEDIA</small><br>
            <div style="display:grid;grid-template-columns:1fr 1fr;gap:8px;margin-top:8px;">
                <a href="https://www.tiktok.com/@xtboy?_r=1&_t=ZS-9AIx1XJuxP8" target="_blank" class="social-link btn-tiktok"><i class="bi bi-tiktok"></i> TikTok</a>
                <a href="https://www.instagram.com/m.rizkirahmady?stkn=ZGxoZjRxYWc4dWs2" target="_blank" class="social-link btn-ig"><i class="bi bi-instagram"></i> Instagram</a>
            </div>
            <a href="https://youtube.com/@medy5tation?si=UhuJ79xJ212_mUGL" target="_blank" class="social-link btn-yt"><i class="bi bi-youtube"></i> YouTube Channel</a>''')

    html_block('''
        <div style="display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:8px;margin-top:40px;padding:15px 0;border-top:1px solid #1e293b;color:#64748b;font-size:.8rem;font-weight:600;">
            <div><b>MEDY5TATION</b> &copy; ''' + str(now().year) + '''</div>
            <div>&ldquo; GAME IS ALWAYS A GOOD IDEA &rdquo;</div>
            <div style="letter-spacing:2px;color:#05d9e8;">&#9651; &#9675; &#10005; &#9633; PLAY &bull; SHARE &bull; TOGETHER</div>
        </div>
        <a class="wa-float" href="''' + wa_link("Halo MEDY5TATION, saya mau tanya layanan game/servis.") + '''" target="_blank" aria-label="Chat WhatsApp"><i class="bi bi-whatsapp"></i></a>''')


# =====================================================================
# MAIN ENTRYPOINT
# =====================================================================
def main():
    set_page_styling()
    render_header()
    render_feature_bar()

    tabs = st.tabs([
        "📦 Paket & Layanan",
        f"🎮 Katalog & Pilih Game ({len(PS4_GAMES)})",
        "⚽ Update Patch Bola",
        "📱 Android & Switch",
        "🧮 Kalkulator Biaya",
        "🔧 Booking Servis",
        "🔎 Cek Status",
        "❓ Bantuan & Lokasi",
        "⭐ Testimoni",
        "🔐 Admin",
    ])
    for tab, fn in zip(tabs, [
        tab_paket, tab_games, tab_bola, tab_extra, tab_kalkulator,
        tab_booking, tab_status, tab_bantuan, tab_testimoni, tab_admin
    ]):
        with tab:
            fn()

    render_footer()


if __name__ == "__main__":
    main()