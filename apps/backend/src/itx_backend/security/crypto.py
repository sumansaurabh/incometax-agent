import base64


def encrypt(value: str) -> str:
    return base64.b64encode(value.encode("utf-8")).decode("utf-8")


def decrypt(value: str) -> str:
    return base64.b64decode(value.encode("utf-8")).decode("utf-8")
