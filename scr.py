import os
import re
import asyncio
import logging
from urllib.parse import urlparse
from pyrogram.enums import ParseMode
from pyrogram import Client, filters
from ZEEXIL import API_ID, API_HASH, SESSION_STRING, BOT_TOKEN, ADMIN_IDS, DEFAULT_LIMIT, ADMIN_LIMIT

# Logging setup
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Delete the session file if it exists
if os.path.exists("user_session.session"):
    os.remove("user_session.session")

# Initialize the bot
bot = Client(
    "bot_session",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN,
    workers=1000,
    parse_mode=ParseMode.HTML
)

# Initialize the user client
user = Client(
    "user_session",
    session_string=SESSION_STRING,
    workers=1000
)

scrape_queue = asyncio.Queue()

def remove_duplicates(messages):
    unique_messages = list(set(messages))
    duplicates_removed = len(messages) - len(unique_messages)
    return unique_messages, duplicates_removed

async def scrape_messages(client, chat_id, limit, start_number=None):
    messages = []
    count = 0
    pattern = r'\d{16}\D*\d{2}\D*\d{2,4}\D*\d{3,4}'
    try:
        async for message in client.get_chat_history(chat_id):
            if count >= limit:
                break
            text = message.text if message.text else message.caption
            if text:
                matched_messages = re.findall(pattern, text)
                if matched_messages:
                    formatted_messages = []
                    for matched_message in matched_messages:
                        extracted_values = re.findall(r'\d+', matched_message)
                        if len(extracted_values) == 4:
                            card_number, mo, year, cvv = extracted_values
                            year = year[-2:]
                            # Check if the card number starts with the specified BIN
                            if start_number and card_number.startswith(start_number):
                                formatted_messages.append(f"{card_number}|{mo}|{year}|{cvv}")
                                count += 1
                            elif not start_number:
                                formatted_messages.append(f"{card_number}|{mo}|{year}|{cvv}")
                                count += 1
                    messages.extend(formatted_messages)
    except Exception as e:
        logger.error(f"Scraping error: {e}")
        return []
    messages = messages[:limit]
    return messages

async def join_group(client, group_identifier):
    try:
        # Handle normal usernames or chat links
        chat = await client.get_chat(group_identifier)
        if chat.type == "private":
            await client.join_chat(group_identifier)
        return chat.id
    except Exception as e:
        logger.error(f"Error joining group: {e}")
        return None

@bot.on_message(filters.command(["scr"]))
async def scr_cmd(client, message):
    args = message.text.split()[1:]
    if len(args) < 2 or len(args) > 3:
        await message.reply_text("<b>⚠️ Provide channel/group username, link, or ID and amount to scrape</b>")
        return
    channel_identifier = args[0]
    limit = int(args[1])
    max_lim = ADMIN_LIMIT if message.from_user.id in ADMIN_IDS else DEFAULT_LIMIT
    if limit > max_lim:
        await message.reply_text(f"<b>⚠️ Amount exceeds the maximum limit of {max_lim} ❌ </b>")
        return
    start_number = args[2] if len(args) == 3 else None
    # Handle chat ID (e.g., -1002454944280)
    if channel_identifier.startswith("-100"):
        try:
            chat_id = int(channel_identifier)
            chat = await user.get_chat(chat_id)
            channel_name = chat.title
            channel_link = f"https://t.me/{chat.username}" if chat.username else f"Chat ID: {chat_id}"
        except Exception as e:
            await message.reply_text(f"<b>⚠️ Invalid chat ID ❌ </b>\nError: {str(e)}")
            return
    else:
        # Parse and handle the channel identifier (username or link)
        parsed_url = urlparse(channel_identifier)
        channel_username = parsed_url.path.lstrip('/') if parsed_url.scheme else channel_identifier
        channel_link = channel_identifier if parsed_url.scheme else f"https://t.me/{channel_identifier}"
        try:
            # Handle normal usernames or chat links
            chat = await user.get_chat(channel_username)
            channel_name = chat.title
            chat_id = chat.id
        except Exception as e:
            # If the chat is private, try to join the group
            chat_id = await join_group(user, channel_identifier)
            if not chat_id:
                await message.reply_text(f"<b>⚠️ Invalid channel/group username or link ❌ </b>\nError: {str(e)}")
                return
            chat = await user.get_chat(chat_id)
            channel_name = chat.title
    temporary_msg = await message.reply_text("<b>Scraping in progress... Please wait 🕒</b>")
    scrapped_results = await scrape_messages(user, chat_id, limit, start_number)
    unique_messages, duplicates_removed = remove_duplicates(scrapped_results)
    if unique_messages:
        file_name = f"x{len(unique_messages)}_{channel_name.replace(' ', '_')}.txt"
        with open(file_name, 'w') as f:
            f.write("\n".join(unique_messages))
        with open(file_name, 'rb') as f:
            caption = (
                f"<b>✅  Scraping Successful!</b>\n"
                f"<b>━━━━━━━━━━━━━━━━━━━</b>\n"
                f"<b>Source:</b> <code>{channel_name}</code>\n"
                f"<b>Link:</b> <a href='{channel_link}'>{channel_link}</a>\n"
                f"<b>Scraped Amount:</b> <code>{len(unique_messages)}</code>\n"
                f"<b>Duplicates Removed:</b> <code>{duplicates_removed}</code>\n"
                f"<b>━━━━━━━━━━━━━━━━━━━</b>\n"
                f"<b>🔗 Card Scraper By: <a href='https://t.me/ZEE_Z79'>ZEEXIL</a></b>\n"
            )
            await temporary_msg.delete()
            await client.send_document(message.chat.id, f, caption=caption)
        os.remove(file_name)
    else:
        await temporary_msg.delete()
        await client.send_message(message.chat.id, "<b>❌  No Credit Cards Found</b>")

@bot.on_message(filters.command(["start"]))
async def start_cmd(client, message):
    await message.reply_text(
        "<b>🤖 Card Scraper Bot</b>\n\n"
        "<b>Usage:</b>\n"
        "<code>/scr [channel/group] [limit] [BIN(optional)]</code>\n\n"
        "<b>Examples:</b>\n"
        "<code>/scr @cards 100</code>\n"
        "<code>/scr https://t.me/cards 50</code>\n"
        "<code>/scr -1001234567890 200 4</code>\n\n"
        "<b>🔗 By: <a href='https://t.me/ZEE_Z79'>ZEEXIL</a></b>"
    )

if __name__ == "__main__":
    import asyncio
    loop = asyncio.get_event_loop()
    try:
        user.start()
        logger.info("User client started successfully!")
        bot.run()
    except KeyboardInterrupt:
        logger.info("Bot stopped by user")
    except Exception as e:
        logger.error(f"Error: {e}")
    finally:
        try:
            user.stop()
            bot.stop()
            logger.info("All clients stopped")
        except:
            pass