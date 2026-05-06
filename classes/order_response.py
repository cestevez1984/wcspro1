from datetime import datetime
from .message import Message
from .protocol import pad_alpha, pad_num


def parse_12n(data: bytes) -> dict:
    """Extract key fields from a received 12N payload.

    12N layout (fixed header):
      [0:3]   record id  '12N'
      [3:5]   '16'       length tag for client
      [5:21]  client     16 chars
      [21:23] '12'       length tag for order_number
      [23:35] order_num  12 chars
      [35:37] '04'       length tag for sheet_number
      [37:41] sheet      4 chars
      [41]    'T'        identifier
      [42:44] '02'       length tag for order_type
      [44:46] type       2 chars
    """
    s = data.decode('utf-8')
    return {
        'client':       s[5:21].strip(),
        'order_number': s[23:35].strip(),
        'sheet_number': s[37:41].strip(),
        'order_type':   s[44:46].strip(),
    }


class OrderResponseMessage(Message):
    """32R — Order response pushed by KiSoft to Host on port 9802.

    Args:
        order_info:    dict extracted from the received 12N (client, order_number, etc.)
        response:      one response entry from a scenario (sheet, carrier_type,
                       last_scan_station, order_states, z_lines, …)
        highest_sheet: total number of carriers/sheets in this order
    """

    def __init__(self, order_info: dict, response: dict, highest_sheet: int):
        super().__init__('32R', self._build(order_info, response, highest_sheet))

    def _build(self, o: dict, r: dict, highest_sheet: int) -> str:
        now = datetime.now().strftime('%Y%m%d%H%M%S')

        rec  = '32R'
        rec += '16' + pad_alpha(o.get('client', 'DEFAULT'), 16)
        rec += '12' + pad_alpha(o.get('order_number', ''), 12)
        rec += '04' + pad_num(r.get('sheet', 1), 4)

        rec += 'T' + '02' + pad_num(o.get('order_type', '10'), 2)

        # A — highest sheet number + reserved empty field
        rec += 'A' + '04' + pad_num(highest_sheet, 4) + '00'

        # B — start station (where picking began)
        rec += 'B' + '03' + pad_alpha(r.get('start_station', '001'), 3)

        # C — carrier type
        rec += 'C' + '10' + pad_alpha(r.get('carrier_type', 'LARGE'), 10)

        # D — carrier code (loading unit ID)
        rec += 'D' + '08' + pad_alpha(r.get('carrier_code', 'UC000001'), 8)

        # G — dispatch ramp
        rec += 'G' + '05' + pad_alpha(r.get('dispatch_ramp', '00183'), 5)

        # s — start time,  e — end time
        rec += 's' + '14' + now
        rec += 'e' + '14' + now

        # t — last scan station + scan time + scan state
        rec += 't' + '03' + pad_alpha(r.get('last_scan_station', '091'), 3)
        rec +=       '14' + now
        rec +=       '01' + pad_alpha(r.get('scan_state', '0'), 1)

        # O — order states (e.g. 0001=started, 0002=completed, 0010=last carrier)
        states = r.get('order_states', [])
        rec += 'O' + f'{len(states):02d}'
        for st in states:
            rec += '04' + pad_alpha(str(st), 4)

        # Z — processed lines
        z_lines = r.get('z_lines', [])
        rec += 'Z' + f'{len(z_lines):02d}'
        for ln in z_lines:
            rec += '12' + pad_alpha(ln.get('article', ''), 12)
            rec += '04' + pad_num(ln.get('pack_size', 1), 4)
            rec += '08' + pad_alpha(ln.get('stock_type', 'STANDARD'), 8)
            lot = ln.get('lot', '')
            if lot:
                rec += '20' + pad_alpha(lot, 20)
            else:
                rec += '00'
            rec += '00'  # expiry (empty)
            rec += '04' + pad_num(ln.get('quantity', 0), 4)
            rec += '01' + pad_alpha(ln.get('quality', '1'), 1)
            rec += '02' + pad_alpha(str(ln.get('line_state', '30')), 2)
            geocode = ln.get('geocode', '')
            if geocode:
                rec += '12' + pad_alpha(geocode, 12)
            else:
                rec += '00'  # geocode (empty)

        # b — storage lines (inbound)
        b_lines = r.get('b_lines', [])
        rec += 'b' + f'{len(b_lines):02d}'
        for ln in b_lines:
            rec += '12' + pad_alpha(ln.get('article', ''), 12)
            rec += '04' + pad_num(ln.get('pack_size', 1), 4)
            rec += '08' + pad_alpha(ln.get('stock_type', 'STANDARD'), 8)
            lot = ln.get('lot', '')
            rec += ('20' + pad_alpha(lot, 20)) if lot else '00'
            expiry = ln.get('expiry', '')
            rec += ('08' + pad_alpha(expiry, 8)) if expiry else '00'
            rec += '04' + pad_num(ln.get('quantity', 0), 4)
            rec += '01' + pad_alpha(ln.get('quality', '1'), 1)
            rec += '02' + pad_alpha(str(ln.get('line_state', '30')), 2)

        return rec
