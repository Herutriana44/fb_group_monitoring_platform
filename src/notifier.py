import logging

logger = logging.getLogger(__name__)

class Notifier:
    def notify(self, message):
        logger.info(f"NOTIFICATION: {message}")
        print(f"\n[ALERT] {message}\n")
