import logging


logger = logging.getLogger("itx_backend")


def setup_tracing() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    logger.info("Tracing initialized")
