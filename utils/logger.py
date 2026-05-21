import logging
import sys

def get_logger(name: str):
    """
    Configura y devuelve un logger estándar con formato.
    En una implementación real, aquí se integraría el hook para Telegram.
    """
    logger = logging.getLogger(name)
    if not logger.handlers:
        logger.setLevel(logging.INFO)
        handler = logging.StreamHandler(sys.stdout)
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)
    return logger

# Placeholder para el hook de Telegram
def critical_alert_handler(message: str):
    """
    Placeholder para enviar alertas críticas a través de Telegram.
    """
    root_logger = get_logger('CRITICAL_ALERT')
    root_logger.critical("TELEGRAM ALERT: %s", message)
