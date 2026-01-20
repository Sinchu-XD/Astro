from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from datetime import datetime
import swisseph as swe
import sqlite3, os
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from cities import CITIES
from states import STATES


API_ID = 123456
API_HASH = "YOUR_API_HASH"
BOT_TOKEN = "YOUR_BOT_TOKEN"

app = Client("astro_final_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

# ================= DATABASE =================
db = sqlite3.connect("astro.db", check_same_thread=False)
cur = db.cursor()
cur.execute("""
CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY,
    name TEXT, dob TEXT, time TEXT, city TEXT,
    nak TEXT, rashi TEXT, lagna TEXT, grah TEXT
)
""")
db.commit()

SESSION = {}
ASK_MODE = set()

SIGNS = ["Mesh","Vrishabha","Mithun","Karka","Simha","Kanya",
         "Tula","Vrishchik","Dhanu","Makar","Kumbh","Meen"]

NAKSHATRAS = [
"Ashwini","Bharani","Krittika","Rohini","Mrigashira","Ardra","Punarvasu","Pushya",
"Ashlesha","Magha","Purva Phalguni","Uttara Phalguni","Hasta","Chitra","Swati",
"Vishakha","Anuradha","Jyeshtha","Mula","Purva Ashadha","Uttara Ashadha",
"Shravana","Dhanishta","Shatabhisha","Purva Bhadrapada","Uttara Bhadrapada","Revati"
]

PLANETS = {
    "Surya": swe.SUN, "Chandra": swe.MOON, "Mangal": swe.MARS,
    "Budh": swe.MERCURY, "Guru": swe.JUPITER,
    "Shukra": swe.VENUS, "Shani": swe.SATURN
}

def sign(d): return SIGNS[int(d//30)]

def resolve_location(place: str):
    place = place.lower().strip()

    # 1️⃣ City priority
    if place in CITIES:
        return CITIES[place]

    # 2️⃣ State fallback
    if place in STATES:
        return STATES[place]

    # 3️⃣ Default (Delhi)
    return (28.6139, 77.2090)
  

def calculate(dob, time, city_or_state):
    lat, lon = resolve_location(city_or_state)

    dt = datetime.strptime(dob + " " + time, "%d-%m-%Y %H:%M")
    jd = swe.julday(
        dt.year,
        dt.month,
        dt.day,
        dt.hour + dt.minute / 60
    )

    # Moon → Nakshatra & Rashi
    moon = swe.calc_ut(jd, swe.MOON)[0][0]
    nak = NAKSHATRAS[int(moon / 13.3333)]
    rashi = sign(moon)

    # Lagna / Houses
    houses, ascmc = swe.houses(jd, lat, lon)
    lagna = sign(ascmc[0])

    # Planets
    grah = {}
    for k, v in PLANETS.items():
        grah[k] = sign(swe.calc_ut(jd, v)[0][0])

    # Rahu / Ketu
    rahu = swe.calc_ut(jd, swe.MEAN_NODE)[0][0]
    grah["Rahu"] = sign(rahu)
    grah["Ketu"] = sign((rahu + 180) % 360)

    return nak, rashi, lagna, grah


# ================= PREDICT =================
@app.on_message(filters.command("predict"))
async def predict(_, m):
    if m.chat.type != "private":
        await m.reply("Prediction ke liye DM kare")
        return
    SESSION[m.from_user.id] = {}
    await m.reply("Naam likhiye")

# ================= INPUT FLOW =================
@app.on_message(filters.text & filters.private)
async def flow(_, m):
    uid = m.from_user.id

    # ---------- MULTI QUESTION MODE ----------
    if uid in ASK_MODE:
        q = m.text.lower()
        if q in ["stop", "done", "thanks", "thank you"]:
            ASK_MODE.remove(uid)
            await m.reply("Conversation end 👍\nDobara sawal ke liye Ask Question dabaye.")
            return

        row = cur.execute(
            "SELECT nak, lagna, grah FROM users WHERE user_id=?",
            (uid,)
        ).fetchone()

        if not row:
            await m.reply("Pehle /predict kare")
            return

        nak, lagna, grah_raw = row
        grah = eval(grah_raw)

        lines = []

        if "career" in q or "job" in q:
            lines.append(
                "Career par Shani ka prabhav delay deta hai lekin stability deta hai."
                if grah["Shani"] in ["Mesh","Karka"]
                else "Career me gradual aur stable growth ka yog hai."
            )
            if grah["Guru"] in ["Dhanu","Meen"]:
                lines.append("Guru strong hone se growth aur guidance milti hai.")

        elif "marriage" in q or "shaadi" in q:
            lines.append(
                "Shukra strong hone se emotional aur loyal relationship banta hai."
                if grah["Shukra"] in ["Tula","Meen","Karka"]
                else "Relationship me patience aur understanding zaruri hogi."
            )

        elif "money" in q or "paisa" in q:
            lines.append(
                "Rahu sudden income ke chances deta hai."
                if grah["Rahu"] in ["Kumbh","Mithun"]
                else "Paisa slow but secure tareeke se aata hai."
            )

        elif "health" in q:
            lines.append(
                "Chandra balanced hone se mental strength achi rehti hai."
                if grah["Chandra"] in ["Karka","Vrishabha"]
                else "Stress aur routine par dhyan dena zaruri hai."
            )

        else:
            lines.append(
                "Sawal thoda clear likhiye.\nExample: Career, Marriage, Money, Health"
            )

        await m.reply(
            "🔮 Aapke janam grahon ke anusaar:\n\n"
            + "\n".join(f"• {x}" for x in lines)
            + "\n\n(Type **stop** to end conversation)\n"
            "This Prediction By @NotYourAbhii"
        )
        return

    # ---------- NORMAL INPUT FLOW ----------
    s = SESSION.get(uid)
    if not s:
        return

    if "name" not in s:
        s["name"] = m.text
        await m.reply("DOB (DD-MM-YYYY)")
    elif "dob" not in s:
        s["dob"] = m.text
        await m.reply("Time (HH:MM)")
    elif "time" not in s:
        s["time"] = m.text
        await m.reply("Birth City")
    elif "city" not in s:
        s["city"] = m.text
        nak,rashi,lagna,grah = calculate(s["dob"],s["time"],s["city"])
        cur.execute("REPLACE INTO users VALUES (?,?,?,?,?,?,?,?,?)",
            (uid,s["name"],s["dob"],s["time"],s["city"],nak,rashi,lagna,str(grah)))
        db.commit()

        text = f"""
🔮 Prediction Report

👤 {s['name']}
🌙 Nakshatra: {nak}
♈ Rashi: {rashi}
⬆️ Lagna: {lagna}

🪐 Grah:
""" + "\n".join([f"{k}: {v}" for k,v in grah.items()]) + """

This Prediction By @NotYourAbhii
If You Have Any Question Then Ask To Him
Thank You
"""
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("📜 Full Details", callback_data="full")],
            [InlineKeyboardButton("📄 Kundli PDF", callback_data="pdf")],
            [InlineKeyboardButton("❓ Ask Question", callback_data="ask")]
        ])
        await m.reply_text(text, reply_markup=kb)
        SESSION.pop(uid)

# ================= BUTTONS =================
@app.on_callback_query(filters.regex("ask"))
async def ask(_, c):
    ASK_MODE.add(c.from_user.id)
    await c.message.reply(
        "❓ Apna sawal likhiye.\n"
        "Aap multiple sawal pooch sakte ho.\n"
        "Conversation end karne ke liye **stop** likhe."
    )

@app.on_callback_query(filters.regex("full"))
async def full(_, c):
    uid = c.from_user.id
    row = cur.execute(
        "SELECT name,nak,lagna,grah FROM users WHERE user_id=?",
        (uid,)
    ).fetchone()
    if not row:
        return
    name,nak,lagna,grah_raw = row
    grah = eval(grah_raw)

    await c.message.reply(
        f"📜 Full Prediction\n\n"
        f"Name: {name}\n"
        f"Nakshatra: {nak}\n"
        f"Lagna: {lagna}\n\n"
        f"Grah impact ke hisaab se aapka life path "
        f"slow start ke baad strong stability ki taraf jata hai.\n\n"
        f"This Prediction By @NotYourAbhii"
    )

@app.on_callback_query(filters.regex("pdf"))
async def pdf(_, c):
    uid = c.from_user.id
    row = cur.execute("SELECT * FROM users WHERE user_id=?", (uid,)).fetchone()
    if not row:
        return

    file = f"kundli_{uid}.pdf"
    p = canvas.Canvas(file, pagesize=A4)
    y = 800
    for lbl,val in zip(
        ["Name","DOB","Time","City","Nakshatra","Rashi","Lagna"],
        row[1:8]
    ):
        p.drawString(50,y,f"{lbl}: {val}")
        y -= 20

    p.drawString(50,y,"Grah:")
    y -= 20
    for g,v in eval(row[8]).items():
        p.drawString(70,y,f"{g}: {v}")
        y -= 15

    p.save()
    await c.message.reply_document(file)
    os.remove(file)

# ================= RUN =================
app.run()

