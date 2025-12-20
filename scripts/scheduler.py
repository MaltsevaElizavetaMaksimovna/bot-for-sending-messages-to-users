
import logging
import time
import schedule
from .bot_logic import check_and_send_messages
from bot.bot import Bot

logger = logging.getLogger(__name__)

def setup_schedule(bot: Bot):
    """Регистрируем job в schedule."""
    schedule.every(1).minutes.do(check_and_send_messages, bot=bot)
    logger.info("scheduler: job registered (every 1 minute)")


def schedule_loop():
    """Бесконечный цикл для фонового потока."""
    logger.info("scheduler: loop started")
    while True:
        try:
            schedule.run_pending()
        except Exception:
            logger.exception("scheduler: run_pending failed")
        time.sleep(5)