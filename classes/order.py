from .message import Message
from .protocol import pad_alpha, pad_num

INBOUND_TYPES = {'02', '04', '05'}


class OrderMessage(Message):
    """12N — New order data (inbound: 02/04/05 with b-lines; outbound: 10/35/36 with Z-lines)."""

    def __init__(self, state: dict):
        super().__init__('12N', self._build(state))

    def _build(self, s: dict) -> str:
        ot = str(s.get('order_type', '10'))
        if ot in INBOUND_TYPES:
            return self._build_inbound(s, ot)
        return self._build_outbound(s, ot)

    def _build_inbound(self, s: dict, ot: str) -> str:
        r  = '12N'
        r += '16' + pad_alpha(s.get('client', 'DEFAULT'), 16)
        r += '12' + pad_alpha(s.get('order_number', ''), 12)
        r += '04' + pad_num(s.get('sheet_number', 0), 4)
        r += 'T' + '02' + pad_num(ot, 2)
        lcc = s.get('load_carrier_code', '')
        if lcc:
            r += 'D' + '08' + pad_alpha(lcc, 8)
        stations = [st for st in s.get('dest_stations', []) if st]
        r += 'K' + f'{len(stations):02d}'
        for st in stations:
            r += '03' + pad_alpha(st, 3)
        lines = s.get('b_lines', [])
        r += 'b' + f'{len(lines):02d}'
        for ln in lines:
            r += '00'
            r += '03' + pad_alpha(ln.get('station', '001'), 3)
            r += '12' + pad_alpha(ln.get('article', ''), 12)
            r += '04' + pad_num(ln.get('pack_size', 0), 4)
            r += '08' + pad_alpha(ln.get('stock_type', 'STANDARD'), 8)
            r += '00'  # lot
            r += '00'  # expiry
            r += '00'  # reservation
            r += '04' + pad_num(ln.get('quantity', 0), 4)
            r += '01' + pad_alpha(ln.get('stock_quality', '1'), 1)
        return r

    def _build_outbound(self, s: dict, ot: str) -> str:
        r  = '12N'
        r += '16' + pad_alpha(s.get('client', 'DEFAULT'), 16)
        r += '12' + pad_alpha(s.get('order_number', ''), 12)
        r += '04' + pad_num(s.get('sheet_number', 0), 4)
        r += 'T' + '02' + pad_num(ot, 2)
        r += 'C' + '10' + pad_alpha(s.get('carrier_type', 'LARGE'), 10)
        partner = s.get('partner_number', '')
        if partner:
            r += 'E' + '12' + pad_alpha(partner, 12)
        route = s.get('route_number', '')
        if route:
            r += 'F' + '08' + pad_alpha(route, 8)
        r += 'U' + '03' + pad_num(s.get('priority', 0), 3)
        params = [p for p in s.get('control_params', []) if p]
        if params:
            r += 'O' + f'{len(params):02d}'
            for p in params:
                r += '04' + pad_alpha(str(p), 4)
        lines = s.get('z_lines', [])
        r += 'Z' + f'{len(lines):02d}'
        for ln in lines:
            r += '12' + pad_alpha(ln.get('article', ''), 12)
            r += '08' + pad_alpha(ln.get('stock_type', 'STANDARD'), 8)
            r += '04' + pad_num(ln.get('quantity', 0), 4)
            r += '00'  # processing_note
        return r
