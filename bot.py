
import asyncio
import os
import json
import logging
from datetime import datetime

try:
    from telethon import TelegramClient, events
    from telethon.tl.types import Channel, Chat
except ImportError:
    print("\n❌  Run first:  pip install telethon\n")
    exit(1)

# ─────────────────────────────────────────────
#   C O N F I G
# ─────────────────────────────────────────────
CONFIG_FILE = "elias_config.json"

def load_config():
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, "r") as f:
            return json.load(f)
    return {}

def save_config(data):
    with open(CONFIG_FILE, "w") as f:
        json.dump(data, f, indent=2)

logging.basicConfig(level=logging.WARNING)
os.makedirs("logs", exist_ok=True)

config      = load_config()
user_client = None
OWNER_ID    = config.get("owner_id")

def cfg(key, default=None):
    return config.get(key, default)

def is_owner(event):
    return event.sender_id == OWNER_ID

async def reply(event, text):
    await event.respond(text, parse_mode="md")

# ─────────────────────────────────────────────
#   U S E R B O T   L O G I C
# ─────────────────────────────────────────────
async def get_admin_chats():
    if not user_client or not user_client.is_connected():
        return None, None

    channels, groups = [], []

    async for dialog in user_client.iter_dialogs():
        entity = dialog.entity
        try:
            if isinstance(entity, Channel) and not entity.left:
                perms = await user_client.get_permissions(entity, await user_client.get_me())
                if perms.is_creator or perms.is_admin:
                    role = "👑 Creator" if perms.is_creator else "⚡ Admin"
                    link = f"https://t.me/{entity.username}" if entity.username else f"tg://openmessage?chat_id={entity.id}"
                    entry = {
                        "title":   entity.title,
                        "link":    link,
                        "members": getattr(entity, "participants_count", "?"),
                        "role":    role,
                        "type":    "Megagroup" if entity.megagroup else "Channel",
                    }
                    (groups if entity.megagroup else channels).append(entry)

            elif isinstance(entity, Chat) and not getattr(entity, 'left', False) and not getattr(entity, 'deactivated', False):
                groups.append({
                    "title":   entity.title,
                    "link":    f"tg://openmessage?chat_id={entity.id}",
                    "members": getattr(entity, "participants_count", "?"),
                    "role":    "⚡ Admin",
                    "type":    "Group",
                })
        except Exception:
            continue

    return channels, groups


async def connect_userbot(api_id, api_hash, phone):
    global user_client
    user_client = TelegramClient(f"session_{phone}", int(api_id), api_hash)
    await user_client.connect()
    if not await user_client.is_user_authorized():
        await user_client.send_code_request(phone)
        return "NEED_CODE"
    return "CONNECTED"


async def verify_code(phone, code, password=None):
    try:
        from telethon.errors import SessionPasswordNeededError
        try:
            await user_client.sign_in(phone, code)
        except SessionPasswordNeededError:
            if password:
                await user_client.sign_in(password=password)
            else:
                return "NEED_2FA"
        return "CONNECTED"
    except Exception as e:
        return f"ERROR: {e}"


# ─────────────────────────────────────────────
#   H A N D L E R S
# ─────────────────────────────────────────────
def setup_handlers(bot):

    @bot.on(events.NewMessage(pattern="/start"))
    async def start(event):
        global OWNER_ID
        if not OWNER_ID:
            OWNER_ID = event.sender_id
            config["owner_id"] = OWNER_ID
            save_config(config)

        if not is_owner(event):
            await reply(event, "⛔ **Unauthorized.**")
            return

        await reply(event, (
            "⚡ **ELIAS RECOVERY BOT**\n"
            "━━━━━━━━━━━━━━━━━━━━━\n\n"
            "Recover channels & groups you removed from chat list.\n\n"
            "**Quick Start:**\n"
            "**1.** `/setup <api_id> <api_hash>`\n"
            "**2.** `/login <phone>`\n"
            "**3.** `/code <otp>`\n"
            "**4.** `/recover`\n\n"
            "Type /help for full guide ⚡"
        ))

    @bot.on(events.NewMessage(pattern="/help"))
    async def help_cmd(event):
        if not is_owner(event): return
        await reply(event, (
            "📖 **ELIAS — Full Guide**\n"
            "━━━━━━━━━━━━━━━━━━━━━\n\n"
            "**Step 1 — Get API credentials**\n"
            "Go to my.telegram.org → API Dev Tools\n"
            "Then: `/setup <api_id> <api_hash>`\n\n"
            "**Step 2 — Login to your account**\n"
            "`/login +9665xxxxxxxx`\n\n"
            "**Step 3 — Enter OTP**\n"
            "`/code 12345`\n\n"
            "**Step 4 — Recover chats**\n"
            "`/recover`\n\n"
            "━━━━━━━━━━━━━━━━━━━━━\n"
            "`/status` — Connection status\n"
            "`/2fa <pass>` — Enter 2FA password\n"
            "`/logout` — Disconnect account\n"
        ))

    @bot.on(events.NewMessage(pattern=r"/setup (.+)"))
    async def setup(event):
        if not is_owner(event): return
        args = event.pattern_match.group(1).split()
        if len(args) < 2:
            await reply(event, "❌ **Usage:** `/setup <api_id> <api_hash>`")
            return
        api_id, api_hash = args[0], args[1]
        if not api_id.isdigit():
            await reply(event, "❌ **API ID must be a number.**")
            return
        config["api_id"]   = api_id
        config["api_hash"] = api_hash
        save_config(config)
        await reply(event, (
            "✅ **API credentials saved!**\n\n"
            f"├ API ID   : `{api_id}`\n"
            f"└ API Hash : `{api_hash[:6]}...{api_hash[-4:]}`\n\n"
            "Next: `/login <your_phone>`"
        ))

    @bot.on(events.NewMessage(pattern=r"/login (.+)"))
    async def login(event):
        if not is_owner(event): return
        phone = event.pattern_match.group(1).strip()
        if not cfg("api_id") or not cfg("api_hash"):
            await reply(event, "❌ **Setup API first:**\n`/setup <api_id> <api_hash>`")
            return
        await reply(event, f"🔄 **Connecting...**\nPhone: `{phone}`")
        try:
            status = await connect_userbot(cfg("api_id"), cfg("api_hash"), phone)
            config["phone"] = phone
            save_config(config)
            if status == "NEED_CODE":
                await reply(event, "📱 **OTP sent to your Telegram!**\n\nEnter it with:\n`/code <your_code>`")
            elif status == "CONNECTED":
                await reply(event, "✅ **Already logged in!**\nRun `/recover` to start.")
        except Exception as e:
            await reply(event, f"❌ **Failed:** `{e}`")

    @bot.on(events.NewMessage(pattern=r"/code (.+)"))
    async def code_cmd(event):
        if not is_owner(event): return
        code  = event.pattern_match.group(1).strip()
        phone = cfg("phone")
        if not phone:
            await reply(event, "❌ **Run `/login <phone>` first.**")
            return
        await reply(event, "🔄 **Verifying...**")
        status = await verify_code(phone, code)
        if status == "CONNECTED":
            me   = await user_client.get_me()
            name = f"{me.first_name or ''} {me.last_name or ''}".strip()
            await reply(event, (
                f"✅ **Logged in!**\n\n"
                f"👤 **{name}**\n"
                f"🆔 `{me.id}`\n"
                f"⭐ Premium: {'Yes' if getattr(me, 'premium', False) else 'No'}\n\n"
                f"Now run `/recover` ⚡"
            ))
        elif status == "NEED_2FA":
            await reply(event, "🔐 **2FA is enabled.**\nSend: `/2fa <password>`")
        else:
            await reply(event, f"❌ **Error:** `{status}`")

    @bot.on(events.NewMessage(pattern=r"/2fa (.+)"))
    async def twofa(event):
        if not is_owner(event): return
        password = event.pattern_match.group(1).strip()
        await reply(event, "🔄 **Verifying 2FA...**")
        status = await verify_code(cfg("phone"), "", password=password)
        if status == "CONNECTED":
            me   = await user_client.get_me()
            name = f"{me.first_name or ''} {me.last_name or ''}".strip()
            await reply(event, f"✅ **2FA verified!**\nWelcome, **{name}**!\nRun `/recover` ⚡")
        else:
            await reply(event, f"❌ **2FA failed:** `{status}`")

    @bot.on(events.NewMessage(pattern="/status"))
    async def status_cmd(event):
        if not is_owner(event): return
        api_ok     = "✅" if cfg("api_id") and cfg("api_hash") else "❌"
        is_auth    = user_client and await user_client.is_user_authorized()
        login_ok   = "✅" if is_auth else "❌"
        name       = "—"
        if is_auth:
            me   = await user_client.get_me()
            name = f"{me.first_name or ''} {me.last_name or ''}".strip()
        await reply(event, (
            "📊 **ELIAS STATUS**\n"
            "━━━━━━━━━━━━━━━━━\n\n"
            f"API Credentials : {api_ok}\n"
            f"Account Login   : {login_ok}\n"
            f"Logged in as    : **{name}**\n"
        ))

    @bot.on(events.NewMessage(pattern="/recover"))
    async def recover(event):
        if not is_owner(event): return
        if not user_client or not await user_client.is_user_authorized():
            await reply(event, "❌ **Not logged in.**\nRun `/login <phone>` first.")
            return

        msg = await reply(event, "🔍 **Scanning your chats...**\n_This may take a moment._")

        try:
            channels, groups = await get_admin_chats()
            total = len(channels) + len(groups)

            if total == 0:
                await msg.edit("⚠️ **No admin chats found.**")
                return

            await msg.delete()

            # إرسال القنوات
            if channels:
                chunk = f"📢 **CHANNELS** `({len(channels)} found)`\n━━━━━━━━━━━━━━━━━\n\n"
                for i, ch in enumerate(channels, 1):
                    chunk += (
                        f"**{i}. {ch['title']}**\n"
                        f"├ {ch['role']}  |  👥 {ch['members']}\n"
                        f"└ {ch['link']}\n\n"
                    )
                    if i % 8 == 0:
                        await event.respond(chunk, parse_mode="md")
                        chunk = f"📢 **CHANNELS** _(continued)_\n\n"
                if chunk.strip():
                    await event.respond(chunk, parse_mode="md")

            # إرسال الجروبات
            if groups:
                chunk = f"👥 **GROUPS** `({len(groups)} found)`\n━━━━━━━━━━━━━━━━━\n\n"
                for i, g in enumerate(groups, 1):
                    chunk += (
                        f"**{i}. {g['title']}**\n"
                        f"├ {g['role']}  |  👥 {g['members']}\n"
                        f"└ {g['link']}\n\n"
                    )
                    if i % 8 == 0:
                        await event.respond(chunk, parse_mode="md")
                        chunk = f"👥 **GROUPS** _(continued)_\n\n"
                if chunk.strip():
                    await event.respond(chunk, parse_mode="md")

            # ملخص
            await event.respond(
                f"✅ **SCAN COMPLETE**\n"
                f"━━━━━━━━━━━━━━━━━\n\n"
                f"📢 Channels : `{len(channels)}`\n"
                f"👥 Groups   : `{len(groups)}`\n"
                f"📊 Total    : `{total}`\n\n"
                f"_Elias Recovery Bot ⚡_",
                parse_mode="md"
            )

        except Exception as e:
            await event.respond(f"❌ **Error:** `{e}`", parse_mode="md")

    @bot.on(events.NewMessage(pattern="/logout"))
    async def logout(event):
        if not is_owner(event): return
        if user_client and user_client.is_connected():
            await user_client.log_out()
            await reply(event, "✅ **Logged out.**")
        else:
            await reply(event, "⚠️ **No active session.**")


# ─────────────────────────────────────────────
#   M A I N
# ─────────────────────────────────────────────
async def main():
    print("╔══════════════════════════════════╗")
    print("║     ⚡ ELIAS RECOVERY BOT ⚡      ║")
    print("╚══════════════════════════════════╝\n")

    bot_token = cfg("bot_token")

    if not bot_token:
        print("🔧 First-time setup!\n")
        bot_token = "8163855423:AAEIrNaDvO-6B5X3S6Wb7UDbZqVFKEwN17k"
        if not bot_token:
            print("❌ No token. Exiting.")
            return
        config["bot_token"] = bot_token
        save_config(config)
        print("\n✅ Token saved!\n")

    # استخدام api_id و api_hash للبوت من التيليثون المدمج
    bot = TelegramClient("elias_bot", 2040, "b18441a1ff607e10a989891a5462e627")
    await bot.start(bot_token=bot_token)
    setup_handlers(bot)

    me = await bot.get_me()
    print(f"✅ Bot running: @{me.username}")
    print(f"📁 Config: {CONFIG_FILE}")
    print(f"💬 Open the bot and send /start")
    print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    print("  Ctrl+C to stop\n")

    await bot.run_until_disconnected()


if __name__ == "__main__":
    asyncio.run(main())