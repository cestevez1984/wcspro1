def pad_alpha(value, length: int) -> str:
    return str(value or '').ljust(length)[:length]

def pad_num(value, length: int) -> str:
    try:
        return str(int(value or 0)).zfill(length)[:length]
    except (ValueError, TypeError):
        return '0' * length

def encode_packet(data: str) -> bytes:
    body  = data.encode('utf-8')
    count = 5 + len(body)
    return b'\n' + f'{count:05d}'.encode() + body + b'\r'
