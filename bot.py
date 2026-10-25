#!/usr/bin/env python3
"""بوت المكتبة الإسلامية — Telegram Bot API عبر long polling."""
import json
import os
import time
import urllib.parse
import urllib.request
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
TOKEN = os.environ.get("BOT_TOKEN", "").strip()
ADMIN_ID = int(os.environ.get("ADMIN_ID", "0") or "0")
CONTENT_PATH = Path(os.environ.get("CONTENT_FILE", str(BASE_DIR / "content.json")))
CATEGORIES = {
    "quran": "📖 القرآن الكريم",
    "sheikhs": "🎙️ صوتيات الشيوخ والعلماء",
    "podcasts": "🎧 بودكاست",
    "nasheeds": "🎵 أناشيد",
    "library": "📚 المكتبة الإسلامية",
}

def save_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    with temp.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    temp.replace(path)

def load_content():
    try:
        with CONTENT_PATH.open("r", encoding="utf-8") as f:
            data = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        data = {key: [] for key in CATEGORIES}
        save_json(CONTENT_PATH, data)
    for key in CATEGORIES:
        data.setdefault(key, [])
    return data

if not TOKEN:
    raise SystemExit("Missing BOT_TOKEN environment variable. Set it in your hosting provider settings.")
content = load_content()

def api(method, params=None, timeout=40):
    url = f"https://api.telegram.org/bot{TOKEN}/{method}"
    request = urllib.request.Request(
        url,
        data=urllib.parse.urlencode(params or {}).encode("utf-8"),
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        result = json.loads(response.read().decode("utf-8"))
    if not result.get("ok"):
        raise RuntimeError(result.get("description", "Telegram API error"))
    return result.get("result")

def send_message(chat_id, text, keyboard=None):
    params = {"chat_id": chat_id, "text": text, "disable_web_page_preview": "true"}
    if keyboard:
        params["reply_markup"] = json.dumps({"inline_keyboard": keyboard}, ensure_ascii=False)
    return api("sendMessage", params)

def main_keyboard():
    keys = list(CATEGORIES.items())
    rows = [
        [{"text": label, "callback_data": f"cat:{key}"} for key, label in keys[i:i+2]]
        for i in range(0, len(keys), 2)
    ]
    rows.append([{"text": "🔎 طريقة البحث", "callback_data": "search_help"}])
    return rows

def show_home(chat_id):
    send_message(
        chat_id,
        "أهلًا بيك في المكتبة الإسلامية 🌿\n\n"
        "اختار القسم اللي محتاجه من الأزرار تحت. تقدر تبحث باستخدام الأمر:\n"
        "/search كلمة البحث\n\n"
        "المحتوى بيُضاف من مصادر وروابط متاحة للاستخدام.",
        main_keyboard(),
    )

def show_category(chat_id, key):
    if key not in CATEGORIES:
        send_message(chat_id, "القسم غير موجود.", main_keyboard())
        return
    items = content.get(key, [])
    if not items:
        send_message(
            chat_id,
            f"{CATEGORIES[key]}\n\nالقسم لسه مفيهوش روابط. مدير البوت يقدر يضيف محتوى بالأمر:\n"
            f"/add {key}|عنوان المحتوى|https://example.com\n\n"
            "استخدم رابطًا تملك حق مشاركته أو رابطًا رسميًا للمصدر.",
            [[{"text": "⬅️ القائمة الرئيسية", "callback_data": "home"}]],
        )
        return
    keyboard = [
        [{"text": str(item.get("title", "محتوى"))[:60], "url": item["url"]}]
        for item in items[:50] if item.get("url")
    ]
    keyboard.append([{"text": "⬅️ القائمة الرئيسية", "callback_data": "home"}])
    send_message(chat_id, f"{CATEGORIES[key]}\nاختار المحتوى اللي عايزه:", keyboard)

def search_items(chat_id, query):
    query = query.strip().casefold()
    if not query:
        send_message(chat_id, "اكتب كلمة بعد الأمر، مثال:\n/search تفسير")
        return
    found = [
        (key, item)
        for key, items in content.items()
        for item in items
        if query in item.get("title", "").casefold()
        or query in CATEGORIES.get(key, "").casefold()
    ]
    if not found:
        send_message(chat_id, f"ملقتش محتوى مطابق لـ «{query}». جرّب كلمة تانية.", main_keyboard())
        return
    keyboard = [
        [{"text": f"{CATEGORIES.get(key, key)} — {item.get('title', 'محتوى')}"[:60], "url": item["url"]}]
        for key, item in found[:50] if item.get("url")
    ]
    keyboard.append([{"text": "⬅️ القائمة الرئيسية", "callback_data": "home"}])
    send_message(chat_id, f"نتائج البحث عن «{query}»: {len(found)} نتيجة.", keyboard)

def add_item(user_id, chat_id, args):
    if ADMIN_ID == 0 or user_id != ADMIN_ID:
        send_message(
            chat_id,
            "إضافة المحتوى متاحة لمدير البوت فقط. أرسل /id لمعرفة رقم حسابك، "
            "ثم ضعه في متغير ADMIN_ID بإعدادات الاستضافة.",
        )
        return
    parts = args.split("|", 2)
    if len(parts) != 3:
        send_message(
            chat_id,
            "الصيغة الصحيحة:\n/add quran|اسم المحتوى|https://example.com\n\n"
            "الأقسام: quran, sheikhs, podcasts, nasheeds, library",
        )
        return
    key, title, url = [part.strip() for part in parts]
    if key not in CATEGORIES:
        send_message(chat_id, "القسم غير صحيح. الأقسام المتاحة: quran, sheikhs, podcasts, nasheeds, library")
        return
    if not title:
        send_message(chat_id, "اكتب عنوانًا للمحتوى.")
        return
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme not in ("https", "http") or not parsed.netloc:
        send_message(chat_id, "الرابط مش صحيح. لازم يبدأ بـ https:// أو http://")
        return
    content.setdefault(key, []).append({"title": title, "url": url})
    save_json(CONTENT_PATH, content)
    send_message(chat_id, f"✅ تمت إضافة «{title}» إلى قسم {CATEGORIES[key]}.")

def handle_message(message):
    chat_id = message["chat"]["id"]
    user_id = message.get("from", {}).get("id", 0)
    text = message.get("text", "").strip()
    if not text:
        send_message(chat_id, "حاليًا البوت بيستقبل أوامر وروابط نصية. افتح /start لعرض الأقسام.")
        return
    parts = text.split(maxsplit=1)
    command = parts[0].split("@", 1)[0].lower()
    args = parts[1] if len(parts) > 1 else ""
    if command in ("/start", "/menu"):
        show_home(chat_id)
    elif command == "/help":
        send_message(
            chat_id,
            "الأوامر المتاحة:\n/start — القائمة الرئيسية\n/search كلمة — البحث\n/id — رقم حسابك\n"
            "/add القسم|العنوان|الرابط — إضافة رابط (للمدير فقط)\n\n"
            "أقسام المحتوى: quran, sheikhs, podcasts, nasheeds, library",
        )
    elif command == "/id":
        send_message(
            chat_id,
            f"رقم حسابك في تيليجرام هو: {user_id}\n\n"
            "لو أنت مدير البوت، ضعه في متغير ADMIN_ID بإعدادات الاستضافة.",
        )
    elif command == "/search":
        search_items(chat_id, args)
    elif command == "/add":
        add_item(user_id, chat_id, args)
    else:
        send_message(chat_id, "استخدم /start لعرض الأقسام أو /search كلمة للبحث.", main_keyboard())

def handle_callback(callback):
    try:
        api("answerCallbackQuery", {"callback_query_id": callback.get("id")})
    except Exception:
        pass
    message = callback.get("message") or {}
    chat_id = (message.get("chat") or {}).get("id")
    if not chat_id:
        return
    data = callback.get("data", "")
    if data == "home":
        show_home(chat_id)
    elif data == "search_help":
        send_message(chat_id, "للبحث عن محتوى مضاف اكتب مثلًا:\n/search سورة البقرة\n/search تفسير\n/search بودكاست")
    elif data.startswith("cat:"):
        show_category(chat_id, data.split(":", 1)[1])

def main():
    print("Islamic library bot is running.", flush=True)
    offset = None
    while True:
        try:
            params = {"timeout": 30, "allowed_updates": json.dumps(["message", "callback_query"])}
            if offset is not None:
                params["offset"] = offset
            for update in api("getUpdates", params, timeout=40):
                offset = update["update_id"] + 1
                if "message" in update:
                    handle_message(update["message"])
                elif "callback_query" in update:
                    handle_callback(update["callback_query"])
        except KeyboardInterrupt:
            break
        except Exception as error:
            print(f"Connection or API error: {error}; retrying in 5 seconds.", flush=True)
            time.sleep(5)

if __name__ == "__main__":
    main()
