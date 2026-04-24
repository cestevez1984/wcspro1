from .message import Message
from .transmission import Transmission
from .protocol import pad_alpha


class PartnerMessage(Message):
    """15N — New partner master data record."""

    def __init__(self, state: dict):
        super().__init__('15N', self._build(state))

    def _build(self, s: dict) -> str:
        r  = '15N'
        r += '16' + pad_alpha(s.get('client', 'DEFAULT'), 16)
        r += '12' + pad_alpha(s.get('partner_number', ''), 12)
        r += 'C' + '30' + pad_alpha(s.get('company', ''), 30)
        r += 'A' + '30' + pad_alpha(s.get('treatment', ''), 30)
        r += 'N' + '30' + pad_alpha(s.get('last_name', ''), 30)
        r += 'M' + '30' + pad_alpha(s.get('first_name', ''), 30)
        r += 'S' + '30' + pad_alpha(s.get('street', ''), 30)
        r += 'P' + '30' + pad_alpha(s.get('city', ''), 30)
        r += 'Z' + '06' + pad_alpha(s.get('zip_code', ''), 6)
        r += 'R' + '30' + pad_alpha(s.get('region', ''), 30)
        r += 'O' + '02' + pad_alpha(s.get('country_code', ''), 2)
        r += 'E' + '30' + pad_alpha(s.get('email', ''), 30)
        r += 'L' + '30' + pad_alpha(s.get('phone', ''), 30)
        return r


class PartnerTransmission(Transmission):
    """Full partner master data transmission: 150/151 → 15N → 159."""

    def __init__(self, mode: str, state: dict):
        open_id = '150' if mode == 'recreate' else '151'
        super().__init__(
            Message(open_id),
            PartnerMessage(state),
            Message('159'),
        )
