from .message import Message
from .transmission import Transmission
from .protocol import pad_alpha


class RouteMessage(Message):
    """16N — New theoretical route master data record."""

    def __init__(self, state: dict):
        super().__init__('16N', self._build(state))

    def _build(self, s: dict) -> str:
        r   = '16N'
        r  += '16' + pad_alpha(s.get('client', 'DEFAULT'), 16)
        r  += '08' + pad_alpha(s.get('route_number', ''), 8)
        day = s.get('day_of_week', '')
        r  += 'Z'
        r  += '06' + '06' + ('03' if day else '00')
        r  += pad_alpha(s.get('departure_time', '000000'), 6)
        r  += pad_alpha(s.get('availability_time', '000000'), 6)
        if day:
            r += pad_alpha(day, 3)
        ramps = [rp for rp in s.get('ramps', []) if rp]
        r += 'R' + f'{len(ramps):02d}' + '05'
        for rp in ramps:
            r += pad_alpha(rp, 5)
        return r


class RouteTransmission(Transmission):
    """Full route master data transmission: 160/161 → 16N → 169."""

    def __init__(self, mode: str, state: dict):
        open_id = '160' if mode == 'recreate' else '161'
        super().__init__(
            Message(open_id),
            RouteMessage(state),
            Message('169'),
        )
