from .message import Message
from .transmission import Transmission
from .protocol import pad_alpha, pad_num

_CHARS = ['ROBOT_TREATABLE', 'COOLING_REQUIRED', 'CONTROLLED', 'UNMARKED']
_PROPS = [('01', 'Lot required'), ('02', 'Expiry required'), ('03', 'Serial required')]


class ArticleMessage(Message):
    """14N — New article master data record."""

    def __init__(self, state: dict):
        super().__init__('14N', self._build(state))

    def _build(self, s: dict) -> str:
        r  = '14N'
        r += '03' + pad_alpha(s.get('station', '001'), 3)
        r += 'L'
        r += '16' + pad_alpha(s.get('client', 'DEFAULT'), 16)
        r += '12' + pad_alpha(s.get('article_number', ''), 12)
        r += '04' + pad_num(s.get('pack_size', 0), 4)
        r += '00'
        r += 'Y' + '02' + pad_num(s.get('ejection_number', 10), 2)
        r += 'M' + '04' + pad_num(s.get('max_quantity', 0), 4)
        r += 'D'
        r += '04' + pad_num(s.get('length_mm', 0), 4)
        r += '04' + pad_num(s.get('width_mm', 0), 4)
        r += '04' + pad_num(s.get('height_mm', 0), 4)
        r += '00'
        r += 'G' + '06' + pad_num(s.get('weight', 1), 6)
        barcodes = [b for b in s.get('barcodes', []) if str(b).strip()]
        r += 'B' + f'{len(barcodes):02d}'
        for bc in barcodes:
            r += '20' + pad_alpha(bc, 20)
        r += 'K'
        r += '40' + pad_alpha(s.get('article_name', ''), 40)
        r += '12' + pad_alpha(s.get('geocode', ''), 12)
        r += 'S'
        r += '04' + pad_num(s.get('min_stock', 0), 4)
        r += '04' + pad_num(s.get('max_stock', 0), 4)
        chars = [c for c in _CHARS if s.get(f'char_{c}', False)]
        r += 'F' + f'{len(chars):02d}'
        for c in chars:
            r += '17' + pad_alpha(c, 17)
        props = [p for p, _ in _PROPS if s.get(f'prop_{p}', False)]
        r += 'E' + f'{len(props):02d}'
        for p in props:
            r += '02' + p
        r += 'T'
        r += '03' + pad_alpha(s.get('repl_station', ''), 3)
        r += '12' + pad_alpha(s.get('repl_geocode', ''), 12)
        return r


class ArticleTransmission(Transmission):
    """Full article master data transmission: 140/141 → 14N → 149."""

    def __init__(self, mode: str, state: dict):
        open_id = '140' if mode == 'recreate' else '141'
        super().__init__(
            Message(open_id),
            ArticleMessage(state),
            Message('149'),
        )
