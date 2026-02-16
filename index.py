python-telegram-bot==21.6
fastapi==0.115.0
uvicorn==0.30.6
web: uvicorn index:api --host 0.0.0.0 --port $PORTimport os
import sqlite3
from datetime import datetime, timedelta
from fastapi import FastAPI, Request
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    ContextTypes,
    ConversationHandler,
    filters,
)

# ===================== SHOP SETTINGS =====================
SHOP_NAME = "𝐒𝐞𝐜𝐮𝐫𝐞 𝐒𝐮𝐫𝐟 𝐙𝐨𝐧𝐞"
BKASH_NUMBER = "01642012385"
NAGAD_NUMBER = "01788098356"
DB_PATH = "shop.db"

TOKEN = os.environ["8315570920:AAEVbhuUhCFpJYVW8Ls-92H2VzCn1oW7Reg"]
PUBLIC_URL = os.environ["PUBLIC_URL"].rstrip("/")
ADMIN_CHAT_ID = int(os.environ["8315570920"]
# Checkout states
NAME, PHONE, PAYMENT, TRX = range(4)

api = FastAPI()
tg_app = Application.builder().token(TOKEN).build()


# ===================== DB HELPERS =====================
def db():
    return sqlite3.connect(DB_PATH)


def init_db():
    con = db()
    cur = con.cursor()

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS products(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            price INTEGER NOT NULL,
            stock INTEGER NOT NULL DEFAULT 0,
            duration_days INTEGER NOT NULL DEFAULT 30,
            desc TEXT DEFAULT ''
        )
        """
    )

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS orders(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            phone TEXT NOT NULL,
            product_id INTEGER NOT NULL,
            product_name TEXT NOT NULL,
            duration_days INTEGER NOT NULL,
            total INTEGER NOT NULL,
            payment_method TEXT NOT NULL,
            trx_id TEXT NOT NULL,
            expiry_date TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'Pending',
            created_at TEXT NOT NULL
        )
        """
    )

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS user_state(
            user_id INTEGER PRIMARY KEY,
            live_chat INTEGER NOT NULL DEFAULT 0
        )
        """
    )

    con.commit()

    cur.execute("SELECT COUNT(*) FROM products")
    if cur.fetchone()[0] == 0:
        seed = [
            ("Adobe Explore (1 Month) — Available", 500, 300, 30, "Adobe Explore premium access. Delivery after verification."),
            ("Adobe Explore (3 Month) — Available", 1350, 200, 90, "Adobe Explore premium access. Delivery after verification."),
            ("Premium VPN (1 Month)", 250, 999, 30, "High-speed VPN account/config. Delivery after verification."),
            ("ChatGPT Account (1 Month)", 450, 200, 30, "ChatGPT account delivery after verification."),
            ("Gemini Pro (1 Month)", 400, 200, 30, "Gemini Pro access delivery after verification."),
        ]
        cur.executemany(
            "INSERT INTO products(name,price,stock,duration_days,desc) VALUES (?,?,?,?,?)",
            seed,
        )
        con.commit()

    con.close()


def set_live_chat(user_id: int, enabled: bool):
    con = db()
    cur = con.cursor()
    cur.execute(
        """
        INSERT INTO user_state(user_id, live_chat)
        VALUES (?,?)
        ON CONFLICT(user_id) DO UPDATE SET live_chat=excluded.live_chat
        """,
        (user_id, 1 if enabled else 0),
    )
    con.commit()
    con.close()


def is_live_chat(user_id: int) -> bool:
    con = db()
    cur = con.cursor()
    cur.execute("SELECT live_chat FROM user_state WHERE user_id=?", (user_id,))
    row = cur.fetchone()
    con.close()
    return bool(row and row[0] == 1)


# ===================== UI HELPERS =====================
def money(n: int) -> str:
    return f"{n}৳"


def is_admin(update: Update) -> bool:
    return update.effective_chat and update.effective_chat.id == ADMIN_CHAT_ID


def kb_main():
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("🛍 Shop", callback_data="shop")],
            [InlineKeyboardButton("💬 Live Chat", callback_data="livechat")],
            [InlineKeyboardButton("ℹ️ Help", callback_data="help")],
        ]
    )


def kb_shop():
    con = db()
    cur = con.cursor()
    cur.execute("SELECT id, name, price FROM products WHERE stock > 0 ORDER BY id DESC")
    rows = cur.fetchall()
    con.close()

    buttons = []
    for pid, name, price in rows:
        buttons.append([InlineKeyboardButton(f"{name} — {money(price)}", callback_data=f"p:{pid}")])
    buttons.append([InlineKeyboardButton("⬅ Back", callback_data="back")])
    return InlineKeyboardMarkup(buttons)


def kb_admin_panel():
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("📦 Products List", callback_data="admin:products")],
            [InlineKeyboardButton("➕ Add Product (Template)", callback_data="admin:addp")],
            [InlineKeyboardButton("💰 Update Price (Template)", callback_data="admin:price")],
            [InlineKeyboardButton("📦 Update Stock (Template)", callback_data="admin:stock")],
            [InlineKeyboardButton("⏳ Update Duration (Template)", callback_data="admin:duration")],
            [InlineKeyboardButton("🗑 Delete Product (Template)", callback_data="admin:delp")],
            [InlineKeyboardButton("🕒 Pending Orders", callback_data="admin:pending")],
            [InlineKeyboardButton("⚙️ Activation Guide", callback_data="admin:activate")],
        ]
    )


# ===================== USER COMMANDS =====================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    set_live_chat(update.effective_user.id, False)
    await update.message.reply_text(
        f"👋 Welcome to {SHOP_NAME}\nSelect an option below:",
        reply_markup=kb_main(),
    )


async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = (
        f"ℹ️ Help — {SHOP_NAME}\n\n"
        "• Shop থেকে প্রোডাক্ট সিলেক্ট করুন\n"
        "• Buy Now → নাম/ফোন → payment → TRX দিন\n"
        "• Verification শেষে delivery message পাবেন ✅\n\n"
        f"bKash: {BKASH_NUMBER}\n"
        f"Nagad: {NAGAD_NUMBER}\n\n"
        "Support দরকার হলে 💬 Live Chat চাপুন"
    )
    await update.message.reply_text(msg, reply_markup=kb_main())


async def endchat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    set_live_chat(update.effective_user.id, False)
    await update.message.reply_text("✅ Live Chat বন্ধ করা হয়েছে।", reply_markup=kb_main())


# ===================== ADMIN PANEL COMMANDS =====================
async def admin_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update):
        await update.message.reply_text("❌ Admin only.")
        return
    await update.message.reply_text("🧰 Admin Panel:", reply_markup=kb_admin_panel())


async def activate_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update):
        await update.message.reply_text("❌ Admin only.")
        return
    msg = (
        "✅ Activation (Render)\n\n"
        "Start Command:\n"
        "uvicorn index:api --host 0.0.0.0 --port $PORT\n\n"
        "ENV vars:\n"
        "BOT_TOKEN\nADMIN_CHAT_ID\nPUBLIC_URL\n\n"
        "Webhook URL হবে:\n"
        f"{PUBLIC_URL}/webhook\n\n"
        "24/7 (Free): UptimeRobot দিয়ে আপনার Render URL ping করুন প্রতি 5 মিনিটে।"
    )
    await update.message.reply_text(msg)


async def pending_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update):
        return
    con = db()
    cur = con.cursor()
    cur.execute(
        "SELECT id,user_id,product_name,total,expiry_date,created_at FROM orders WHERE status='Pending' ORDER BY id DESC LIMIT 30"
    )
    rows = cur.fetchall()
    con.close()

    if not rows:
        await update.message.reply_text("✅ No pending orders.")
        return

    lines = ["🕒 Pending Orders:"]
    for oid, uid, pname, total, expiry, created in rows:
        lines.append(f"#{oid} | User:{uid} | {pname} | {money(total)} | Exp:{expiry} | {created}")
    await update.message.reply_text("\n".join(lines))


# ===================== BUTTON ROUTER (NO BUY, NO PAY) =====================
async def on_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    data = q.data
    uid = q.from_user.id

    if data == "back":
        await q.edit_message_text(f"🏠 {SHOP_NAME} Menu", reply_markup=kb_main())
        return

    if data == "help":
        msg = (
            f"ℹ️ Help — {SHOP_NAME}\n\n"
            "• Shop থেকে প্রোডাক্ট সিলেক্ট করুন\n"
            "• Buy Now → নাম/ফোন → payment → TRX দিন\n"
            "• Verification শেষে delivery message পাবেন ✅\n\n"
            f"bKash: {BKASH_NUMBER}\n"
            f"Nagad: {NAGAD_NUMBER}\n\n"
            "Support দরকার হলে 💬 Live Chat চাপুন"
        )
        await q.edit_message_text(msg, reply_markup=kb_main())
        return

    if data == "shop":
        await q.edit_message_text("🛍 Available Products:", reply_markup=kb_shop())
        return

    if data == "livechat":
        set_live_chat(uid, True)
        await q.edit_message_text(
            "💬 Live Chat ON ✅\nএখন আপনার সমস্যা/প্রশ্ন লিখুন—এডমিনের কাছে যাবে।\n\nবন্ধ করতে /endchat লিখুন।",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅ Back", callback_data="back")]]),
        )
        return

    # Admin panel buttons (templates/list)
    if data.startswith("admin:"):
        if uid != ADMIN_CHAT_ID:
            await q.edit_message_text("❌ Admin only.")
            return
        action = data.split("admin:")[1]

        if action == "products":
            con = db()
            cur = con.cursor()
            cur.execute("SELECT id,name,price,stock,duration_days FROM products ORDER BY id DESC LIMIT 200")
            rows = cur.fetchall()
            con.close()
            if not rows:
                await q.edit_message_text("No products.")
                return
            lines = ["📦 Products:"]
            for pid, name, price, stock, dur in rows:
                lines.append(f"#{pid} | {name} | {money(price)} | stock:{stock} | {dur} days")
            await q.edit_message_text("\n".join(lines))
            return

        if action == "addp":
            await q.edit_message_text(
                "/addp Name | price | stock | duration_days | description\n"
                "Example:\n/addp Netflix (1 Month) | 350 | 50 | 30 | Netflix premium"
            )
            return

        if action == "price":
            await q.edit_message_text("/price <product_id> <new_price>\nExample:\n/price 1 550")
            return

        if action == "stock":
            await q.edit_message_text("/stock <product_id> <new_stock>\nExample:\n/stock 1 999")
            return

        if action == "duration":
            await q.edit_message_text("/duration <product_id> <days>\nExample:\n/duration 1 60")
            return

        if action == "delp":
            await q.edit_message_text("/delp <product_id>\nExample:\n/delp 7")
            return

        if action == "pending":
            # (same as /pending but via button)
            con = db()
            cur = con.cursor()
            cur.execute(
                "SELECT id,user_id,product_name,total,expiry_date,created_at FROM orders WHERE status='Pending' ORDER BY id DESC LIMIT 30"
            )
            rows = cur.fetchall()
            con.close()
            if not rows:
                await q.edit_message_text("✅ No pending orders.")
                return
            lines = ["🕒 Pending Orders:"]
            for oid, uid2, pname, total, expiry, created in rows:
                lines.append(f"#{oid} | User:{uid2} | {pname} | {money(total)} | Exp:{expiry} | {created}")
            await q.edit_message_text("\n".join(lines))
            return

        if action == "activate":
            await q.edit_message_text(
                "Start Command:\nuvicorn index:api --host 0.0.0.0 --port $PORT\n\n"
                "ENV:\nBOT_TOKEN\nADMIN_CHAT_ID\nPUBLIC_URL\n\n"
                f"Webhook: {PUBLIC_URL}/webhook"
            )
            return

    # Product detail (shows Buy button)
    if data.startswith("p:"):
        pid = int(data.split(":")[1])
        con = db()
        cur = con.cursor()
        cur.execute("SELECT id,name,price,stock,duration_days,desc FROM products WHERE id=?", (pid,))
        row = cur.fetchone()
        con.close()

        if not row:
            await q.edit_message_text("❌ Product not found.", reply_markup=kb_shop())
            return

        pid, name, price, stock, duration, desc = row
        expiry_preview = (datetime.now() + timedelta(days=duration)).strftime("%Y-%m-%d")

        context.user_data["selected_product"] = {"id": pid, "name": name, "price": price, "duration": duration}

        text = (
            f"📦 {name}\n\n"
            f"💰 Price: {money(price)}\n"
            f"⏳ Validity: {duration} days\n"
            f"📅 Expiry After Purchase: {expiry_preview}\n"
            f"📦 Stock: {stock}\n\n"
            f"📝 {desc}"
        )

        kb = InlineKeyboardMarkup(
            [
                [InlineKeyboardButton("💳 Buy Now", callback_data="buy")],  # handled by ConversationHandler
                [InlineKeyboardButton("⬅ Back to Shop", callback_data="shop")],
            ]
        )
        await q.edit_message_text(text, reply_markup=kb)
        return


# ===================== CHECKOUT ENTRY (FIXED) =====================
async def buy_entry(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    uid = q.from_user.id

    # Must have selected product
    product = context.user_data.get("selected_product")
    if not product:
        await q.edit_message_text("❌ Product select করা হয়নি। Shop থেকে সিলেক্ট করুন।", reply_markup=kb_shop())
        return ConversationHandler.END

    set_live_chat(uid, False)
    await q.edit_message_text("✅ Checkout শুরু\nআপনার নাম লিখুন:")
    return NAME


async def checkout_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["cust_name"] = update.message.text.strip()
    await update.message.reply_text("📞 আপনার ফোন নম্বর লিখুন:")
    return PHONE


async def checkout_phone(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["cust_phone"] = update.message.text.strip()

    kb = InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("bKash", callback_data="pay:bkash"), InlineKeyboardButton("Nagad", callback_data="pay:nagad")],
            [InlineKeyboardButton("❌ Cancel", callback_data="pay:cancel")],
        ]
    )
    await update.message.reply_text(
        f"💳 Payment method সিলেক্ট করুন:\n\nbKash: {BKASH_NUMBER}\nNagad: {NAGAD_NUMBER}",
        reply_markup=kb,
    )
    return PAYMENT


async def checkout_payment(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    choice = q.data.split(":")[1]

    if choice == "cancel":
        await q.edit_message_text("❌ Checkout cancelled.", reply_markup=kb_main())
        return ConversationHandler.END

    method = "bKash" if choice == "bkash" else "Nagad"
    number = BKASH_NUMBER if choice == "bkash" else NAGAD_NUMBER
    context.user_data["payment_method"] = method

    await q.edit_message_text(
        f"✅ {method} selected.\nSend money to: {number}\n\nএখন আপনার Transaction ID (TRX) লিখুন:"
    )
    return TRX


async def checkout_trx(update: Update, context: ContextTypes.DEFAULT_TYPE):
    trx = update.message.text.strip()
    if len(trx) < 4:
        await update.message.reply_text("TRX ID ঠিক করে আবার দিন:")
        return TRX

    product = context.user_data.get("selected_product")
    if not product:
        await update.message.reply_text("❌ Product select করা হয়নি। আবার /start দিন।", reply_markup=kb_main())
        return ConversationHandler.END

    pid = int(product["id"])
    pname = product["name"]
    price = int(product["price"])
    duration = int(product["duration"])

    # Reduce stock
    con = db()
    cur = con.cursor()
    cur.execute("SELECT stock FROM products WHERE id=?", (pid,))
    row = cur.fetchone()
    if not row or row[0] <= 0:
        con.close()
        await update.message.reply_text("❌ Stock শেষ। অন্য প্রোডাক্ট সিলেক্ট করুন।", reply_markup=kb_shop())
        return ConversationHandler.END
    cur.execute("UPDATE products SET stock = stock - 1 WHERE id=?", (pid,))
    con.commit()
    con.close()

    uid = update.effective_user.id
    name = context.user_data["cust_name"]
    phone = context.user_data["cust_phone"]
    payment = context.user_data["payment_method"]

    expiry = (datetime.now() + timedelta(days=duration)).strftime("%Y-%m-%d")
    created_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    con = db()
    cur = con.cursor()
    cur.execute(
        """
        INSERT INTO orders(user_id,name,phone,product_id,product_name,duration_days,total,payment_method,trx_id,expiry_date,status,created_at)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
        """,
        (uid, name, phone, pid, pname, duration, price, payment, trx, expiry, "Pending", created_at),
    )
    oid = cur.lastrowid
    con.commit()
    con.close()

    await update.message.reply_text(
        f"✅ Order Confirmed — #{oid}\n\n"
        f"📦 Product: {pname}\n"
        f"💰 Price: {money(price)}\n"
        f"⏳ Validity: {duration} days\n"
        f"📅 Expiry Date: {expiry}\n\n"
        f"Payment: {payment} (TRX: {trx})\n"
        f"Status: Pending",
        reply_markup=kb_main(),
    )

    try:
        await context.bot.send_message(
            chat_id=ADMIN_CHAT_ID,
            text=(
                f"🔔 NEW ORDER #{oid}\n"
                f"User ID: {uid}\nName: {name}\nPhone: {phone}\n\n"
                f"Product: {pname}\nPrice: {money(price)}\nValidity: {duration} days\nExpiry: {expiry}\n\n"
                f"Payment: {payment}\nTRX: {trx}\n\n"
                f"Deliver with:\n/deliver {oid} <delivery_message>"
            ),
        )
    except Exception:
        pass

    return ConversationHandler.END


# ===================== LIVE CHAT FORWARD =====================
async def forward_live_chat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if uid == ADMIN_CHAT_ID:
        return
    if not is_live_chat(uid):
        return
    user = update.effective_user
    username = f"@{user.username}" if user.username else "(no username)"
    text = update.message.text.strip()
    admin_text = (
        "💬 LIVE CHAT MESSAGE\n"
        f"From: {user.full_name} {username}\n"
        f"User ID: {uid}\n"
        f"Message: {text}\n\n"
        f"Reply with:\n/reply {uid} <your_message>\n"
        f"Stop their chat:\n/stopchat {uid}"
    )
    await context.bot.send_message(chat_id=ADMIN_CHAT_ID, text=admin_text)
    await update.message.reply_text("✅ আপনার মেসেজ সাপোর্টে পাঠানো হয়েছে।")


# ===================== ADMIN COMMANDS (same as your code) =====================
async def cmd_reply(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update):
        return
    if len(context.args) < 2:
        await update.message.reply_text("Usage: /reply <user_id> <message>")
        return
    user_id = int(context.args[0])
    msg = " ".join(context.args[1:]).strip()
    await context.bot.send_message(chat_id=user_id, text=f"💬 Support:\n{msg}")
    await update.message.reply_text("✅ Replied.")


async def cmd_stopchat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update):
        return
    if len(context.args) != 1:
        await update.message.reply_text("Usage: /stopchat <user_id>")
        return
    user_id = int(context.args[0])
    set_live_chat(user_id, False)
    try:
        await context.bot.send_message(chat_id=user_id, text="✅ Support chat closed.")
    except Exception:
        pass
    await update.message.reply_text("✅ Stopped.")


async def cmd_deliver(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update):
        return
    if len(context.args) < 2:
        await update.message.reply_text("Usage: /deliver <order_id> <delivery_message>")
        return

    order_id = int(context.args[0])
    delivery_message = " ".join(context.args[1:]).strip()

    con = db()
    cur = con.cursor()
    cur.execute("SELECT user_id FROM orders WHERE id=?", (order_id,))
    row = cur.fetchone()
    if not row:
        con.close()
        await update.message.reply_text("❌ Order not found.")
        return

    user_id = row[0]
    cur.execute("UPDATE orders SET status=? WHERE id=?", ("Delivered", order_id))
    con.commit()
    con.close()

    try:
        await context.bot.send_message(chat_id=user_id, text=f"✅ Delivered #{order_id}\n\n{delivery_message}")
    except Exception:
        pass
    await update.message.reply_text("✅ Delivered.")


# ===================== WEBHOOK =====================
@api.on_event("startup")
async def on_startup():
    init_db()
    await tg_app.initialize()
    await tg_app.bot.set_webhook(url=f"{PUBLIC_URL}/webhook")
    await tg_app.start()


@api.get("/")
def home():
    return {"status": "running"}


@api.post("/webhook")
async def webhook(req: Request):
    data = await req.json()
    update = Update.de_json(data, tg_app.bot)
    await tg_app.process_update(update)
    return {"ok": True}


# ===================== HANDLERS (IMPORTANT ORDER) =====================
tg_app.add_handler(CommandHandler("start", start))
tg_app.add_handler(CommandHandler("help", help_cmd))
tg_app.add_handler(CommandHandler("endchat", endchat))

tg_app.add_handler(CommandHandler("admin", admin_cmd))
tg_app.add_handler(CommandHandler("activate", activate_cmd))
tg_app.add_handler(CommandHandler("pending", pending_cmd))

tg_app.add_handler(CommandHandler("reply", cmd_reply))
tg_app.add_handler(CommandHandler("stopchat", cmd_stopchat))
tg_app.add_handler(CommandHandler("deliver", cmd_deliver))

# ✅ ConversationHandler must come BEFORE general callback handler
checkout_conv = ConversationHandler(
    entry_points=[CallbackQueryHandler(buy_entry, pattern="^buy$")],
    states={
        NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, checkout_name)],
        PHONE: [MessageHandler(filters.TEXT & ~filters.COMMAND, checkout_phone)],
        PAYMENT: [CallbackQueryHandler(checkout_payment, pattern="^pay:")],
        TRX: [MessageHandler(filters.TEXT & ~filters.COMMAND, checkout_trx)],
    },
    fallbacks=[],
    allow_reentry=True,
)
tg_app.add_handler(checkout_conv)

# ✅ Now general callbacks (no buy/pay here)
tg_app.add_handler(CallbackQueryHandler(on_button))

# Live chat forwarding
tg_app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, forward_live_chat), group=1)
/ (root)
  index.py
  requirements.txt
  Procfile
