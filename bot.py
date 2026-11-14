import asyncio
import time
from datetime import datetime, timedelta
import requests
from bs4 import BeautifulSoup
import re
import threading
import os
from zoneinfo import ZoneInfo

from flask import Flask
from PIL import Image, ImageDraw, ImageFont
import arabic_reshaper
from bidi.algorithm import get_display

from baleio import Bot, Dispatcher, md
from baleio.client.default import DefaultBotProperties
from baleio.enums import ParseMode
from baleio.types import Message, FSInputFile

# ================== تنظیمات ==================
BOT_TOKEN = "1436036233:o6TSrXuG9yq1XpP7ujDDBpD8orszsYgShw0"
CHAT_ID   = "5344687354"
# =============================================

IMAGE_URLS = [
    "https://i.ibb.co/Lqs54wz/file-0000000069f481f49a808a3c7d123ae6.jpg",
    "https://i.ibb.co/wFDwB3fj/image3.jpg",
    "https://i.ibb.co/ymZ91Fdy/image4.jpg",
    "https://i.ibb.co/B5Z2PKCC/image5.jpg",
    "https://i.ibb.co/tw4qsZC7/8357946797662674688-105240833956724.jpg",
    "https://i.ibb.co/1GDfjK6b/file-00000000a4188246982f6f39b5f58f5a.jpg",
]
image_index = 0

# 🕒 تنظیمات زمان‌بندی (۹ صبح تا ۹ شب)
SEND_TIMES = ["09:00", "11:00", "13:00", "15:00", "17:00", "19:00", "21:00"]
ALLOWED_START_HOUR = 9
ALLOWED_END_HOUR   = 21

TEHRAN_TZ = ZoneInfo("Asia/Tehran")
FONT_PATH = "Vazir-Bold.ttf"
LOGO_PATH = "logo.png"

app = Flask(__name__)
bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.MARKDOWN))
dp = Dispatcher()

@app.route('/')
def home():
    return "GoldBot is running!"

def run_web_server():
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)

def is_allowed_time():
    now = datetime.now(TEHRAN_TZ)
    return ALLOWED_START_HOUR <= now.hour < ALLOWED_END_HOUR

def get_next_image():
    global image_index
    url = IMAGE_URLS[image_index]
    image_index = (image_index + 1) % len(IMAGE_URLS)
    return url

def clean_num(num_str):
    if not num_str:
        return None
    num_str = num_str.replace(",", "").replace("٫", "").replace(".", "").strip()
    persian = "۰۱۲۳۴۵۶۷۸۹"
    english = "0123456789"
    num_str = num_str.translate(str.maketrans(persian, english))
    try:
        return int(num_str)
    except:
        return None

def get_prices_from_estjt():
    url = "https://www.estjt.ir/"
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
    prices = {
        "ons": None, "mazane": None, "gold18": None, "gold24": None,
        "sekke_jadid": None, "sekke_ghadim": None, "nim_sekke": None,
        "rob_sekke": None, "sekke_gerami": None
    }
    for attempt in range(3):
        try:
            response = requests.get(url, headers=headers, timeout=(5, 20))
            response.raise_for_status()
            soup = BeautifulSoup(response.text, "html.parser")
            page_text = soup.get_text()
            patterns = {
                "ons": r"انس\s*طلا[\s\S]*?([\d۰-۹]+[٫,\.][\d۰-۹٫,\.]+)",
                "mazane": r"مظنه\s*تهران[\s\S]*?([\d۰-۹]+[٫,\.][\d۰-۹٫,\.]+)",
                "gold18": r"طلا\s*۱۸\s*عیار[\s\S]*?([\d۰-۹]+[٫,\.][\d۰-۹٫,\.]+)",
                "gold24": r"طلای\s*۲۴\s*عیار[\s\S]*?([\d۰-۹]+[٫,\.][\d۰-۹٫,\.]+)",
                "sekke_jadid": r"سکه\s*طرح\s*جدید[\s\S]*?([\d۰-۹]+[٫,\.][\d۰-۹٫,\.]+)",
                "sekke_ghadim": r"سکه\s*طرح\s*قدیم[\s\S]*?([\d۰-۹]+[٫,\.][\d۰-۹٫,\.]+)",
                "nim_sekke": r"نیم\s*سکه[\s\S]*?([\d۰-۹]+[٫,\.][\d۰-۹٫,\.]+)",
                "rob_sekke": r"ربع\s*سکه[\s\S]*?([\d۰-۹]+[٫,\.][\d۰-۹٫,\.]+)",
                "sekke_gerami": r"سکه\s*گرمی[\s\S]*?([\d۰-۹]+[٫,\.][\d۰-۹٫,\.]+)",
            }
            for key, pat in patterns.items():
                match = re.search(pat, page_text)
                if match:
                    val = clean_num(match.group(1))
                    if val:
                        prices[key] = val
            print(f"[PRICE] Fetched: {prices}")
            return prices
        except requests.exceptions.ReadTimeout:
            print(f"[RETRY] ReadTimeout, attempt {attempt+1}/3")
            time.sleep(2)
        except requests.exceptions.ConnectionError:
            print(f"[RETRY] ConnectionError, attempt {attempt+1}/3")
            time.sleep(2)
        except Exception as e:
            print(f"[ERROR] estjt.ir: {e}")
            return None
    print("[ERROR] estjt.ir: all retries failed")
    return None

def fmt(num):
    if num is None:
        return "—"
    return f"{num:,}"

def round_to_thousand(value):
    return (int(value) // 1000) * 1000

def fix_persian(text):
    reshaped = arabic_reshaper.reshape(text)
    return get_display(reshaped)

def create_price_image(prices, output_path="price_image.png"):
    width, height = 1100, 780
    img = Image.new("RGB", (width, height), color=(253, 252, 248))
    draw = ImageDraw.Draw(img)
    
    try:
        font_title = ImageFont.truetype(FONT_PATH, 40)
        font_box_header = ImageFont.truetype(FONT_PATH, 32)
        font_row = ImageFont.truetype(FONT_PATH, 26)
        font_small = ImageFont.truetype(FONT_PATH, 20)
        font_brand = ImageFont.truetype(FONT_PATH, 36)
        font_slogan = ImageFont.truetype(FONT_PATH, 24)
    except Exception as e:
        print(f"[ERROR] Font not found: {e}")
        return None

    COLOR_GOLD = (184, 134, 11)
    COLOR_TITLE = (25, 45, 90)
    COLOR_RED = (200, 30, 40)
    COLOR_BOX_BG = (248, 245, 235)
    COLOR_SLOGAN = (120, 85, 50)

    draw.text((width - 50, 45), fix_persian("قیمت لحظه ای گلدماند"), fill=COLOR_TITLE, font=font_title, anchor="rm")

    brand_x = 120
    brand_y = 45
    
    if os.path.exists(LOGO_PATH):
        try:
            logo_img = Image.open(LOGO_PATH).convert("RGBA")
            logo_size = 50
            logo_img = logo_img.resize((logo_size, logo_size), Image.Resampling.LANCZOS)
            img.paste(logo_img, (50, 20), logo_img)
        except Exception as e:
            print(f"[ERROR] Logo read failed: {e}")
            cx, cy = 70, 45
            draw.polygon([(cx, cy - 22), (cx + 25, cy), (cx, cy + 22), (cx - 25, cy)], outline=COLOR_GOLD, width=4)
            draw.polygon([(cx, cy - 12), (cx + 14, cy), (cx, cy + 12), (cx - 14, cy)], fill=COLOR_GOLD)
    else:
        cx, cy = 70, 45
        draw.polygon([(cx, cy - 22), (cx + 25, cy), (cx, cy + 22), (cx - 25, cy)], outline=COLOR_GOLD, width=4)
        draw.polygon([(cx, cy - 12), (cx + 14, cy), (cx, cy + 12), (cx - 14, cy)], fill=COLOR_GOLD)
    
    draw.text((brand_x, brand_y), "GOLDMIND", fill=COLOR_GOLD, font=font_brand, anchor="lm")

    draw.line([(50, 100), (width - 50, 100)], fill=COLOR_GOLD, width=4)
    mid_x = width // 2
    draw.line([(mid_x, 130), (mid_x, height - 140)], fill=COLOR_GOLD, width=2)

    def draw_rounded_rect(x1, y1, x2, y2, radius, fill):
        draw.rounded_rectangle([(x1, y1), (x2, y2)], radius=radius, fill=fill)

    start_y = 140
    row_gap = 85
    box_h = 65

    draw_rounded_rect(mid_x + 20, start_y, width - 40, start_y + box_h, 30, COLOR_BOX_BG)
    draw.text(((mid_x + 20 + width - 40) // 2, start_y + box_h // 2), fix_persian("قیمت طلا"), fill=COLOR_TITLE, font=font_box_header, anchor="mm")
    draw_rounded_rect(40, start_y, mid_x - 20, start_y + box_h, 30, COLOR_BOX_BG)
    draw.text(((40 + mid_x - 20) // 2, start_y + box_h // 2), fix_persian("قیمت سکه"), fill=COLOR_TITLE, font=font_box_header, anchor="mm")

    raw_gold18 = prices.get('gold18')
    gold18_plus = (raw_gold18 + 100_000) if raw_gold18 else None

    gold_rows = [
        ("انس طلا", f"{fmt(prices.get('ons'))} $"),
        ("مظنه تهران", f"{fmt(prices.get('mazane'))} ت"),
        ("طلا ۱۸ عیار", f"{fmt(gold18_plus)} ت"),
        ("طلای ۲۴ عیار", f"{fmt(prices.get('gold24'))} ت"),
    ]
    coin_rows = [
        ("سکه طرح جدید", f"{fmt(prices.get('sekke_jadid'))} ت"),
        ("سکه طرح قدیم", f"{fmt(prices.get('sekke_ghadim'))} ت"),
        ("نیم سکه", f"{fmt(prices.get('nim_sekke'))} ت"),
        ("ربع سکه", f"{fmt(prices.get('rob_sekke'))} ت"),
        ("سکه گرمی", f"{fmt(prices.get('sekke_gerami'))} ت"),
    ]

    y = start_y + box_h + 25
    for label, value in gold_rows:
        draw_rounded_rect(mid_x + 20, y, width - 40, y + box_h, 30, COLOR_BOX_BG)
        draw.ellipse([(width - 70, y + 18), (width - 40, y + 48)], fill=COLOR_GOLD)
        draw.ellipse([(width - 60, y + 28), (width - 50, y + 38)], fill=(255, 255, 255))
        draw.text((width - 90, y + box_h // 2), fix_persian(label), fill=COLOR_TITLE, font=font_row, anchor="rm")
        draw.text((mid_x + 60, y + box_h // 2), value, fill=COLOR_RED, font=font_row, anchor="lm")
        y += row_gap

    y = start_y + box_h + 25
    for label, value in coin_rows:
        draw_rounded_rect(40, y, mid_x - 20, y + box_h, 30, COLOR_BOX_BG)
        draw.ellipse([(70, y + 18), (100, y + 48)], fill=COLOR_GOLD)
        draw.ellipse([(80, y + 28), (90, y + 38)], fill=(255, 255, 255))
        draw.text((mid_x - 60, y + box_h // 2), fix_persian(label), fill=COLOR_TITLE, font=font_row, anchor="rm")
        draw.text((120, y + box_h // 2), value, fill=COLOR_RED, font=font_row, anchor="lm")
        y += row_gap

    footer_y = height - 130
    draw.line([(50, footer_y), (width - 50, footer_y)], fill=COLOR_GOLD, width=4)

    now_str = datetime.now(TEHRAN_TZ).strftime("%Y-%m-%d  %H:%M")
    draw.text((width - 50, footer_y + 30), fix_persian(f"آخرین بروزرسانی:  {now_str}"), fill=(100, 100, 100), font=font_small, anchor="rm")
    draw.text((50, footer_y + 30), "www.goldmind.gold", fill=(120, 120, 120), font=font_small, anchor="lm")

    slogan_text = fix_persian("گلدمایند نمادی از تفکر، قدرت، ثروت")
    draw.text((width // 2, height - 40), slogan_text, fill=COLOR_SLOGAN, font=font_slogan, anchor="mm")

    img.save(output_path, "PNG")
    print(f"[IMG] Price image created: {output_path}")
    return output_path

def calculate_and_build_text(gheimat):
    payeh = gheimat + 100_000
    nim_gerami  = payeh * 1.07  * 0.5
    yek_gerami  = payeh * 1.05  * 1
    do_gerami   = payeh * 1.04  * 2
    se_gerami   = payeh * 1.04  * 3
    panj_gerami = payeh * 1.036 * 5
    payeh_fmt = f"{round_to_thousand(payeh):,.0f}"
    nim       = f"{round_to_thousand(nim_gerami):,.0f}"
    yek       = f"{round_to_thousand(yek_gerami):,.0f}"
    do        = f"{round_to_thousand(do_gerami):,.0f}"
    se        = f"{round_to_thousand(se_gerami):,.0f}"
    panj      = f"{round_to_thousand(panj_gerami):,.0f}"
    return (
        f"💸 قیمت امروز شمش های گلدمایند به ازای هرگرم طلا ی عیار ۷۵۰\n"
        f"✔️در وزن های ۰/۵ تا ۵ گرم موجود است\n"
        f"💸 قیمت لحظه ای یک گرم طلا : {md.bold(payeh_fmt)}\n\n"
        f"✓ ۰/۵گرمی گلدمایند : {md.bold(nim)}ت\n\n"
        f"✓ ۱ گرم : {md.bold(yek)}ت\n\n"
        f"✓ ۲ گرم : {md.bold(do)}ت\n\n"
        f"✓ ۳ گرم : {md.bold(se)} ت\n\n"
        f"✓ ۵ گرم : {md.bold(panj)} ت\n\n"
        f"💎ارتباط با ما:\n@GOLDMIND_ADMIN\n\n"
        f"☎️تماس:09121202331 قاسمی\n\n"
        f"🆔: ble.ir/join/2pqRkYqS17\n"
        f"#شمش\n"
        f"#گلدمایند"
    )

async def send_to_channel():
    if not is_allowed_time():
        print(f"[SKIP] Outside allowed hours ({ALLOWED_START_HOUR}:00 - {ALLOWED_END_HOUR}:00 Tehran)")
        return
    try:
        prices = get_prices_from_estjt()
        if prices is None or prices.get("gold18") is None:
            print(f"[ERROR] Price (gold18) not fetched, sending cancelled")
            return

        img_path = create_price_image(prices)
        if img_path and os.path.exists(img_path):
            try:
                photo_file = FSInputFile(img_path, filename="price_image.png")
                await bot.send_photo(chat_id=CHAT_ID, photo=photo_file, caption="💎 نرخ لحظه‌ای طلا و سکه | Goldmind 💎")
                print(f"[OK] Price image sent")
            except Exception as e:
                print(f"[WARN] Image send failed: {e}")
        else:
            print("[WARN] Price image not created, skipping first message")

        text = calculate_and_build_text(prices.get("gold18"))
        image_url = get_next_image()
        try:
            await bot.send_photo(chat_id=CHAT_ID, photo=image_url, caption=text)
            print(f"[OK] Second message (shomsh + rotating image) sent")
        except Exception as e:
            print(f"[WARN] Second photo failed: {e} -> text only")
            await bot.send_message(chat_id=CHAT_ID, text=text)
            print(f"[OK] Second message (text only) sent")

    except Exception as e:
        print(f"[ERROR] {e}")

# ================== زمان‌بند دقیق Asyncio ==================
async def scheduler_loop():
    print("[SCHEDULER] Started.")
    last_sent_minute = -1

    while True:
        now = datetime.now(TEHRAN_TZ)
        current_time_str = now.strftime("%H:%M")
        current_minute = now.hour * 60 + now.minute

        if current_time_str in SEND_TIMES and current_minute != last_sent_minute:
            last_sent_minute = current_minute
            print(f"[SCHEDULER] ⏰ Time matched {current_time_str}! Sending...")
            asyncio.create_task(send_to_channel())
        
        # هر ۳۰ ثانیه یکبار زمان را چک می‌کند
        await asyncio.sleep(30)

@dp.message()
async def handle_private_message(message: Message):
    if message.chat.type == "private" and message.text and message.text.strip() == "/price":
        prices = get_prices_from_estjt()
        if prices is None or prices.get("gold18") is None:
            await message.answer("❌ قیمت در دسترس نیست")
            return
        await message.answer(calculate_and_build_text(prices.get("gold18")))

async def main_async():
    threading.Thread(target=run_web_server, daemon=True).start()
    print(f"[WEB] Port {os.environ.get('PORT', 8080)}")
    
    asyncio.create_task(scheduler_loop())
    
    print("[BOT] Starting polling...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    main_loop = asyncio.new_event_loop()
    asyncio.set_event_loop(main_loop)
    try:
        main_loop.run_until_complete(main_async())
    except KeyboardInterrupt:
        print("Stopping bot...")
    finally:
        main_loop.close()