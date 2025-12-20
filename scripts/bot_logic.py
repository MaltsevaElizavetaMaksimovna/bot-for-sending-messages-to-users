from datetime import datetime, timezone
from bot.bot import Bot
from bot.handler import MessageHandler

from .config import TOKEN, DEFAULT_CHAT_IDS
from .db import fetch_pending_messages, insert_feedback, get_delivered_chat_ids, mark_delivered
import logging


logger = logging.getLogger(__name__)
def resolve_recipients(users_group: int) -> list[str]:
    """Пока просто хардкодим список чатов."""
    return DEFAULT_CHAT_IDS


def should_send(message_time_str: str, now_utc: datetime) -> bool:
    """Логика 'now' или время <= текущего UTC."""
    if not message_time_str:
        return False

    mt = message_time_str.strip().lower()
    if mt == "now":
        return True

    try:
        dt = datetime.strptime(message_time_str, "%Y-%m-%d %H:%M")
        dt = dt.replace(tzinfo=timezone.utc)
        return dt <= now_utc
    except ValueError:
        logger.warning("bad message_time=%r", message_time_str)
        return False


def send_message_to_recipients(bot: Bot, row) -> tuple[int, int]:
    """
    Отправляем одно сообщение всем получателям (кроме уже доставленных).
    Возвращаем (sent_success, total_recipients).
    """
    msg_id = row["id"]
    text = row["message"] or ""
    users_group = row["users_group"] or 1

    recipients = resolve_recipients(users_group)
    delivered = get_delivered_chat_ids(msg_id)

    to_send = [chat_id for chat_id in recipients if chat_id not in delivered]
    if not to_send:
        # Уже всё доставлено (на всякий случай)
        return (len(delivered), len(recipients))

    sent_count = 0
    for chat_id in to_send:
        try:
            bot.send_text(chat_id=chat_id, text=text)
            mark_delivered(msg_id, chat_id)   #важно: фиксируем успех по каждому
            sent_count += 1
        except Exception:
            logger.exception("send failed msg_id=%s chat_id=%s", msg_id, chat_id)

    logger.info("msg_id=%s: sent %s/%s", msg_id, sent_count, len(recipients))
    return (len(delivered) + sent_count, len(recipients))


def check_and_send_messages(bot: Bot):
    now_utc = datetime.now(timezone.utc)
    rows = fetch_pending_messages()
    if not rows:
        return

    logger.info("check_and_send_messages: %s candidate(s)", len(rows))
    for row in rows:
        if should_send(row["message_time"], now_utc):
            delivered_total, total = send_message_to_recipients(bot, row)

            #финализируем только когда доставили всем
            if delivered_total >= total:
                insert_feedback(row["id"], delivered_total, 0)
            else:
                logger.warning("msg_id=%s: partial delivery %s/%s, will retry", row["id"], delivered_total, total)

# ========== инициализация бота и handler'ов ==========

def on_message(bot_obj: Bot, event):
    """Простой обработчик /ping."""
    text = (getattr(event, "text", "") or "").strip().lower()
    if text == "/ping":
        bot_obj.send_text(chat_id=event.from_chat, text="Бот активен!")


def init_bot() -> Bot:
    """Создаём Bot, регистрируем handler и возвращаем готовый объект."""
    bot = Bot(token=TOKEN, is_myteam=True)

    bot.dispatcher.add_handler(MessageHandler(callback=on_message))
    return bot