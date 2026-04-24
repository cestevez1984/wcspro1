from .protocol import encode_packet


class Message:
    """A single HIS protocol message: record identifier + optional fields, wrapped in a frame."""

    def __init__(self, record_id: str, data: str = ''):
        self.record_id = record_id
        self.data      = data if data else record_id   # simple records: DATA = record_id only
        self.packet    = encode_packet(self.data)

    def display(self) -> str:
        raw      = self.packet
        symbolic = f'[LF]{raw[1:-1].decode("utf-8")}[CR]'
        hex_str  = ' '.join(f'{b:02X}' for b in raw)
        return f'{symbolic}\n{hex_str}'
