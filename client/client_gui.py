#!/usr/bin/env python3
"""COHEN Guatemala – KiSoft One HIS Client Simulator"""

import json, queue, sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from nicegui import ui
from classes import (
    ArticleMessage, ArticleTransmission,
    PartnerMessage, PartnerTransmission,
    RouteMessage,   RouteTransmission,
    OrderMessage,
    start_connections, stop_connections, drain_ui_queue,
)
from classes.order import INBOUND_TYPES
from classes.connection import STATION_LABELS
from server.scenarios import SCENARIOS

# ─────────────────────────────────────────────────────────────────────────────
# Constants
# ─────────────────────────────────────────────────────────────────────────────

CLIENTS = ['DEFAULT', 'A1201', 'A1301', 'A1401', 'A3601', 'A4101', 'A5101', '6111']
CLIENT_LABELS = {
    'DEFAULT': 'DEFAULT',
    'A1201':   'A1201 – JILOH',
    'A1301':   'A1301 – AJISA',
    'A1401':   'A1401 – ALISE',
    'A3601':   'A3601 – ELECTRON SERVICES',
    'A4101':   'A4101 – LE Recurso Corporativo',
    'A5101':   'A5101 – SOLIN',
    '6111':    '6111 – YVES ROCHER',
}
CLIENT_SELECT = {k: CLIENT_LABELS[k] for k in CLIENTS}

STATIONS   = ['001', '002', '003', '004', '010', '011', '061', '065', '199']
CHARS      = ['ROBOT_TREATABLE', 'COOLING_REQUIRED', 'CONTROLLED', 'UNMARKED']
PROPS      = [('01', 'Lot required'), ('02', 'Expiry required'), ('03', 'Serial required')]
DAY_SELECT = {'': '(none)', 'MON': 'MON', 'TUE': 'TUE', 'WED': 'WED',
              'THU': 'THU', 'FRI': 'FRI', 'SAT': 'SAT', 'SUN': 'SUN'}
RAMPS      = [f'{i:05d}' for i in range(1, 11)] + [f'{i:05d}' for i in range(21, 26)]

STOCK_TYPES  = ['STANDARD', 'B6', 'QQ', '2F', '1E', '1X', '1Z']
CARRIER_TYPES = ['LARGE', 'CARTON', 'FULL', 'HALF', 'QUARTER', 'EIGHTH']
QUALITY_SELECT = {'1': '1 – New', '2': '2 – Return'}
ORDER_TYPES = {
    '02': '02 – Transport (Open Shuttle)',
    '04': '04 – Bulk goods-in / Decanting',
    '05': '05 – Open goods-in',
    '10': '10 – Outbound delivery',
    '35': '35 – Withdrawal',
    '36': '36 – Full carton dispatch',
}
CONTROL_PARAMS_OPTS = [
    ('0001', 'Check carrier'),
    ('0012', 'Strap carrier'),
    ('9005', 'Private (PA001)'),
    ('9006', 'Marking (GPA001)'),
    ('9007', 'Verification (PA002)'),
]

TAB_MAP = {
    'Articles (14N)': 'article',
    'Partners (15N)': 'partner',
    'Routes (16N)':   'route',
    'Orders (12N)':   'order',
    'Scenarios':      'scenario',
}

ORDER_STATE_LABELS = {
    '0001': 'started',       '0002': 'completed',
    '0003': 'cancelled GUI', '0004': 'cancelled host',
    '0010': 'last carrier',
}

MODE_OPTIONS = {'recreate': 'Recreate All', 'partial': 'Partial Update'}

# ─────────────────────────────────────────────────────────────────────────────
# Application state
# ─────────────────────────────────────────────────────────────────────────────

art: dict = {'station': '001', 'client': 'DEFAULT', 'barcodes': [], 'mode': 'recreate'}
prt: dict = {'client': 'DEFAULT', 'mode': 'recreate'}
rte: dict = {'client': 'DEFAULT', 'day_of_week': '', 'ramps': [], 'mode': 'recreate'}
order: dict = {
    'client': 'DEFAULT', 'order_number': '', 'sheet_number': 0,
    'order_type': '10',
    # inbound
    'load_carrier_code': '', 'dest_stations': [], 'b_lines': [],
    # outbound
    'carrier_type': 'LARGE', 'partner_number': '', 'route_number': '',
    'priority': 0, 'control_params': [], 'z_lines': [],
}

scen: dict = {
    'scenario_id':  SCENARIOS[0]['id'],
    'client':       'A1301',
    'order_number': 'TEST001',
}

ctx: dict = {
    'tab':         'article',
    'preview_el':  None,
    'received_el': None,
    # connection
    'connected':   False,
    'stop_event':  None,
    'send_queue':  None,
    'btn_conn':    None,
    'btn_disc':    None,
}

ui_queue: queue.Queue = queue.Queue()   # threads → GUI bridge

_initial_preview = ''  # filled after helper functions are defined below

# ─────────────────────────────────────────────────────────────────────────────
# Friendly preview formatters
# ─────────────────────────────────────────────────────────────────────────────

_OT_NAMES = {
    '02': 'Transport (Open Shuttle)',
    '04': 'Bulk goods-in / Decanting',
    '05': 'Open goods-in',
    '10': 'Outbound delivery',
    '35': 'Withdrawal',
    '36': 'Full carton dispatch',
}

def _friendly_order(s: dict, title_suffix: str = '') -> str:
    ot        = str(s.get('order_type', '10'))
    direction = 'Inbound' if ot in INBOUND_TYPES else 'Outbound'
    L = [
        f'12N — {direction} Order{title_suffix}',
        '─' * 44,
        f'  client        {str(s.get("client", "")).strip()}',
        f'  order_number  {str(s.get("order_number", "")).strip()}',
        f'  sheet         {int(s.get("sheet_number", 0)):04d}',
        f'  order_type    {ot}  —  {_OT_NAMES.get(ot, ot)}',
    ]
    if ot in INBOUND_TYPES:
        lcc = str(s.get('load_carrier_code', '')).strip()
        if lcc:
            L.append(f'  load_carrier  {lcc}')
        stations = [st for st in s.get('dest_stations', []) if st]
        if stations:
            L.append(f'  dest_stations {",  ".join(stations)}')
        b_lines = s.get('b_lines', [])
        L += ['', f'  b  lines ({len(b_lines)}):']
        for i, ln in enumerate(b_lines, 1):
            if i > 1:
                L.append('')
            L += [
                f'    [{i}]  article     {ln.get("article", "")}',
                f'         station     {ln.get("station", "")}',
                f'         pack_size   {ln.get("pack_size", 0)}',
                f'         stock_type  {ln.get("stock_type", "")}',
                f'         quantity    {ln.get("quantity", 0)}',
            ]
            if ln.get('lot'):
                L.append(f'         lot         {ln["lot"]}')
            if ln.get('expiry'):
                L.append(f'         expiry      {ln["expiry"]}')
            L.append(f'         quality     {ln.get("stock_quality", "1")}')
    else:
        L.append(f'  carrier_type  {s.get("carrier_type", "LARGE")}')
        pn = str(s.get('partner_number', '')).strip()
        if pn:
            L.append(f'  partner       {pn}')
        rn = str(s.get('route_number', '')).strip()
        if rn:
            L.append(f'  route         {rn}')
        L.append(f'  priority      {int(s.get("priority", 0)):03d}')
        params = [p for p in s.get('control_params', []) if p]
        if params:
            L.append(f'  control       {",  ".join(params)}')
        z_lines = s.get('z_lines', [])
        L += ['', f'  Z  lines ({len(z_lines)}):']
        for i, ln in enumerate(z_lines, 1):
            if i > 1:
                L.append('')
            L += [
                f'    [{i}]  article     {ln.get("article", "")}',
                f'         stock_type  {ln.get("stock_type", "")}',
                f'         quantity    {ln.get("quantity", 0)}',
            ]
    return '\n'.join(L)


def _friendly_article(s: dict) -> str:
    L = [
        f'14N — Article Master Data  [{s.get("mode", "recreate")}]',
        '─' * 44,
        f'  station       {s.get("station", "")}',
        f'  client        {str(s.get("client", "")).strip()}',
        f'  article       {str(s.get("article_number", "")).strip()}',
        f'  pack_size     {s.get("pack_size", 0)}',
        f'  ejection_#    {s.get("ejection_number", 0)}',
        f'  max_qty       {s.get("max_quantity", 0)}',
        f'  dimensions    L {s.get("length_mm", 0)}  W {s.get("width_mm", 0)}  H {s.get("height_mm", 0)}  mm',
        f'  weight        {s.get("weight", 0)} × 0.1 g',
        f'  article_name  {str(s.get("article_name", "")).strip()}',
        f'  geocode       {str(s.get("geocode", "")).strip()}',
        f'  stock         min {s.get("min_stock", 0)}  max {s.get("max_stock", 0)}',
    ]
    chars = [c for c in ['ROBOT_TREATABLE', 'COOLING_REQUIRED', 'CONTROLLED', 'UNMARKED']
             if s.get(f'char_{c}')]
    if chars:
        L.append(f'  chars         {",  ".join(chars)}')
    props = [lbl for code, lbl in [('01', 'lot req'), ('02', 'expiry req'), ('03', 'serial req')]
             if s.get(f'prop_{code}')]
    if props:
        L.append(f'  properties    {",  ".join(props)}')
    bcs = [bc for bc in s.get('barcodes', []) if bc]
    if bcs:
        L.append(f'  barcodes ({len(bcs)}):')
        for bc in bcs:
            L.append(f'    {bc}')
    repl = str(s.get('repl_station', '')).strip()
    if repl:
        L += [f'  repl_station  {repl}',
              f'  repl_geocode  {str(s.get("repl_geocode", "")).strip()}']
    return '\n'.join(L)


def _friendly_partner(s: dict) -> str:
    first = str(s.get('first_name', '')).strip()
    last  = str(s.get('last_name',  '')).strip()
    treat = str(s.get('treatment',  '')).strip()
    name  = ' '.join(p for p in [treat, first, last] if p)
    L = [
        f'15N — Partner Master Data  [{s.get("mode", "recreate")}]',
        '─' * 44,
        f'  client        {str(s.get("client", "")).strip()}',
        f'  partner       {str(s.get("partner_number", "")).strip()}',
        f'  company       {str(s.get("company", "")).strip()}',
        f'  name          {name}',
        f'  street        {str(s.get("street", "")).strip()}',
        f'  city          {str(s.get("zip_code", "")).strip()} {str(s.get("city", "")).strip()}',
        f'  region        {str(s.get("region", "")).strip()}',
        f'  country       {str(s.get("country_code", "")).strip()}',
        f'  email         {str(s.get("email", "")).strip()}',
        f'  phone         {str(s.get("phone", "")).strip()}',
    ]
    return '\n'.join(L)


def _friendly_route(s: dict) -> str:
    L = [
        f'16N — Theoretical Route  [{s.get("mode", "recreate")}]',
        '─' * 44,
        f'  client        {str(s.get("client", "")).strip()}',
        f'  route_number  {str(s.get("route_number", "")).strip()}',
        f'  departure     {str(s.get("departure_time", "")).strip()}',
        f'  availability  {str(s.get("availability_time", "")).strip()}',
        f'  day_of_week   {s.get("day_of_week", "") or "(none)"}',
    ]
    ramps = [r for r in s.get('ramps', []) if r]
    L.append(f'  ramps ({len(ramps)}):')
    for rp in ramps:
        L.append(f'    {rp}')
    return '\n'.join(L)


def _preview_text(friendly: str, msg) -> str:
    divider = '·' * 44
    return f'{friendly}\n\n{divider}\n\n{msg.display()}'


try:
    _msg0 = ArticleMessage(art)
    _initial_preview = _preview_text(_friendly_article(art), _msg0)
except Exception as _e:
    _initial_preview = str(_e)


# ─────────────────────────────────────────────────────────────────────────────
# Preview helpers
# ─────────────────────────────────────────────────────────────────────────────

def _get_scenario(sc_id: str) -> dict:
    for sc in SCENARIOS:
        if sc['id'] == sc_id:
            return sc
    return SCENARIOS[0]


def _build_order_from_scenario(sc: dict, client: str, order_number: str) -> dict:
    """Build a single outbound 12N from a scenario (deduplicates Z-lines)."""
    z_lines, seen = [], set()
    for resp in sc.get('responses', []):
        for ln in resp.get('z_lines', []):
            art = ln.get('article', '')
            if art and art not in seen:
                seen.add(art)
                z_lines.append({
                    'article':    art,
                    'stock_type': ln.get('stock_type', 'STANDARD'),
                    'quantity':   ln.get('quantity', 1),
                })
    carrier = sc['responses'][0].get('carrier_type', 'LARGE') if sc.get('responses') else 'LARGE'
    return {
        'client': client, 'order_number': order_number, 'sheet_number': 0,
        'order_type': '10', 'carrier_type': carrier,
        'partner_number': '', 'route_number': '', 'priority': 0,
        'control_params': [], 'z_lines': z_lines,
        'load_carrier_code': '', 'dest_stations': [], 'b_lines': [],
    }


def _build_inbound_12n(lu: dict, client: str, order_number: str) -> dict:
    """Build one inbound 12N from a loading_unit entry."""
    stations = list({ln.get('station', '065') for ln in lu.get('b_lines', [])})
    return {
        'client':            client,
        'order_number':      order_number,
        'sheet_number':      0,
        'order_type':        '04',
        'load_carrier_code': lu['carrier_code'],
        'dest_stations':     stations,
        'b_lines':           lu.get('b_lines', []),
        'carrier_type': 'LARGE', 'partner_number': '', 'route_number': '',
        'priority': 0, 'control_params': [], 'z_lines': [],
    }


def _set_preview(text: str) -> None:
    el = ctx['preview_el']
    if el is not None:
        el.value = text
        el.update()

def refresh_preview() -> None:
    try:
        tab = ctx['tab']
        if tab == 'article':
            msg = ArticleMessage(art)
            _set_preview(_preview_text(_friendly_article(art), msg))
        elif tab == 'partner':
            msg = PartnerMessage(prt)
            _set_preview(_preview_text(_friendly_partner(prt), msg))
        elif tab == 'route':
            msg = RouteMessage(rte)
            _set_preview(_preview_text(_friendly_route(rte), msg))
        elif tab == 'order':
            msg = OrderMessage(order)
            _set_preview(_preview_text(_friendly_order(order), msg))
        elif tab == 'scenario':
            sc = _get_scenario(scen['scenario_id'])
            if sc.get('category') == 'Inbound':
                lus = sc.get('loading_units', [])
                if not lus:
                    _set_preview('No loading units defined')
                    return
                n   = len(lus)
                od  = _build_inbound_12n(lus[0], scen['client'], scen['order_number'])
                msg = OrderMessage(od)
                suf = f'  [1/{n}]  {lus[0]["carrier_code"]}' if n > 1 else ''
                hdr = f'— {n} × 12N will be sent —\n\n' if n > 1 else ''
                _set_preview(hdr + _preview_text(_friendly_order(od, suf), msg))
            else:
                od  = _build_order_from_scenario(sc, scen['client'], scen['order_number'])
                msg = OrderMessage(od)
                _set_preview(_preview_text(_friendly_order(od), msg))
    except Exception as exc:
        _set_preview(f'Error building message:\n{exc}')

def _enqueue(*packets) -> None:
    """Put one or more encoded packets in send_queue if connected."""
    sq = ctx.get('send_queue')
    if ctx.get('connected') and sq:
        for pkt in packets:
            sq.put(pkt)

def send_article() -> None:
    try:
        tx = ArticleTransmission(art.get('mode', 'recreate'), art)
        _set_preview(_preview_text(_friendly_article(art), tx.data_msg) + '\n\n' + tx.display())
        _enqueue(tx.open_msg.packet, tx.data_msg.packet, tx.close_msg.packet)
    except Exception as exc:
        _set_preview(f'Error building transmission:\n{exc}')

def send_partner() -> None:
    try:
        tx = PartnerTransmission(prt.get('mode', 'recreate'), prt)
        _set_preview(_preview_text(_friendly_partner(prt), tx.data_msg) + '\n\n' + tx.display())
        _enqueue(tx.open_msg.packet, tx.data_msg.packet, tx.close_msg.packet)
    except Exception as exc:
        _set_preview(f'Error building transmission:\n{exc}')

def send_route() -> None:
    try:
        tx = RouteTransmission(rte.get('mode', 'recreate'), rte)
        _set_preview(_preview_text(_friendly_route(rte), tx.data_msg) + '\n\n' + tx.display())
        _enqueue(tx.open_msg.packet, tx.data_msg.packet, tx.close_msg.packet)
    except Exception as exc:
        _set_preview(f'Error building transmission:\n{exc}')

def send_scenario_order() -> None:
    try:
        sc = _get_scenario(scen['scenario_id'])
        if sc.get('category') == 'Inbound':
            lus = sc.get('loading_units', [])
            packets, previews = [], []
            n = len(lus)
            for i, lu in enumerate(lus, 1):
                od  = _build_inbound_12n(lu, scen['client'], scen['order_number'])
                msg = OrderMessage(od)
                packets.append(msg.packet)
                suf = f'  [{i}/{n}]  {lu["carrier_code"]}' if n > 1 else f'  {lu["carrier_code"]}'
                previews.append(_preview_text(_friendly_order(od, suf), msg))
            sep = '\n\n' + '═' * 44 + '\n\n'
            hdr = f'— sending {n} × 12N —\n\n' if n > 1 else ''
            _set_preview(hdr + sep.join(previews))
            _enqueue(*packets)
        else:
            od  = _build_order_from_scenario(sc, scen['client'], scen['order_number'])
            msg = OrderMessage(od)
            _set_preview(_preview_text(_friendly_order(od), msg))
            _enqueue(msg.packet)
    except Exception as exc:
        _set_preview(f'Error building scenario order:\n{exc}')

def send_order() -> None:
    try:
        msg = OrderMessage(order)
        _set_preview(_preview_text(_friendly_order(order), msg))
        _enqueue(msg.packet)
    except Exception as exc:
        _set_preview(f'Error building message:\n{exc}')

# ─────────────────────────────────────────────────────────────────────────────
# Bound widget helpers
# ─────────────────────────────────────────────────────────────────────────────

def bind_input(label: str, state: dict, key: str, **kw):
    def _on(e): state[key] = e.value; refresh_preview()
    return ui.input(label, value=state.get(key, ''), on_change=_on, **kw)

def bind_number(label: str, state: dict, key: str, **kw):
    def _on(e): state[key] = e.value; refresh_preview()
    return ui.number(label, value=state.get(key, 0), on_change=_on, **kw)

def bind_select(label: str, options, state: dict, key: str, **kw):
    def _on(e): state[key] = e.value; refresh_preview()
    return ui.select(options, label=label, value=state.get(key), on_change=_on, **kw)

def mode_toggle(state: dict) -> None:
    def _on(e): state['mode'] = e.value
    ui.toggle(MODE_OPTIONS, value=state.get('mode', 'recreate'), on_change=_on).props('dense')

# ─────────────────────────────────────────────────────────────────────────────
# Dynamic lists (refreshable)
# ─────────────────────────────────────────────────────────────────────────────

@ui.refreshable
def barcode_list() -> None:
    for i, bc in enumerate(art['barcodes']):
        with ui.row().classes('items-center w-full gap-2'):
            def _ch(e, idx=i): art['barcodes'][idx] = e.value; refresh_preview()
            ui.input(f'Barcode {i + 1}', value=bc, on_change=_ch).classes('flex-1')
            def _del(idx=i):
                art['barcodes'].pop(idx); barcode_list.refresh(); refresh_preview()
            ui.button(icon='delete', on_click=_del).props('flat round dense color=negative')
    if not art['barcodes']:
        ui.label('No barcodes added').classes('text-grey-6 text-caption')

def add_barcode() -> None:
    art['barcodes'].append(''); barcode_list.refresh(); refresh_preview()


@ui.refreshable
def ramp_list() -> None:
    for i, rp in enumerate(rte['ramps']):
        with ui.row().classes('items-center gap-2'):
            def _ch(e, idx=i): rte['ramps'][idx] = e.value; refresh_preview()
            ui.select(RAMPS, value=rp, on_change=_ch).classes('w-52')
            def _del(idx=i):
                rte['ramps'].pop(idx); ramp_list.refresh(); refresh_preview()
            ui.button(icon='delete', on_click=_del).props('flat round dense color=negative')
    if not rte['ramps']:
        ui.label('No ramps added').classes('text-grey-6 text-caption')

def add_ramp() -> None:
    if len(rte['ramps']) < 20:
        rte['ramps'].append(RAMPS[0]); ramp_list.refresh(); refresh_preview()


@ui.refreshable
def direction_section() -> None:
    ot = str(order.get('order_type', '10'))

    if ot in INBOUND_TYPES:
        # ── Inbound (02 / 04 / 05) ───────────────────────────────────────────
        def _ch_lcc(e): order['load_carrier_code'] = e.value; refresh_preview()
        ui.input('Load Carrier Code (D)', value=order.get('load_carrier_code', ''),
                 on_change=_ch_lcc).classes('w-full q-mt-sm')

        ui.separator().classes('q-my-sm')
        with ui.row().classes('items-center gap-2'):
            ui.label('Destination Stations (K)').classes('text-caption text-grey-4')
            def _add_ds():
                order['dest_stations'].append('001')
                direction_section.refresh(); refresh_preview()
            ui.button('Add', icon='add', on_click=_add_ds).props('flat dense color=primary size=sm')

        for i, st in enumerate(order.get('dest_stations', [])):
            with ui.row().classes('items-center gap-2'):
                def _ch_st(e, idx=i): order['dest_stations'][idx] = e.value; refresh_preview()
                ui.select(STATIONS, value=st, on_change=_ch_st).classes('w-32')
                def _del_st(idx=i):
                    order['dest_stations'].pop(idx); direction_section.refresh(); refresh_preview()
                ui.button(icon='delete', on_click=_del_st).props('flat round dense color=negative')
        if not order.get('dest_stations'):
            ui.label('No stations added').classes('text-grey-6 text-caption')

        ui.separator().classes('q-my-sm')
        with ui.row().classes('items-center gap-2'):
            ui.label('Order Lines (b)').classes('text-caption text-grey-4')
            def _add_bl():
                order['b_lines'].append({
                    'station': '001', 'article': '', 'pack_size': 0,
                    'stock_type': 'STANDARD', 'quantity': 1, 'stock_quality': '1',
                })
                direction_section.refresh(); refresh_preview()
            ui.button('Add', icon='add', on_click=_add_bl).props('flat dense color=primary size=sm')

        for i, ln in enumerate(order.get('b_lines', [])):
            with ui.row().classes('items-center gap-1 w-full flex-wrap q-mt-xs'):
                def _ch_bst(e, idx=i): order['b_lines'][idx]['station'] = e.value; refresh_preview()
                ui.select(STATIONS, value=ln.get('station', '001'), label='St',
                          on_change=_ch_bst).classes('w-20')
                def _ch_bart(e, idx=i): order['b_lines'][idx]['article'] = e.value; refresh_preview()
                ui.input('Article', value=ln.get('article', ''), on_change=_ch_bart).classes('w-28')
                def _ch_bps(e, idx=i): order['b_lines'][idx]['pack_size'] = e.value; refresh_preview()
                ui.number('Pk', value=ln.get('pack_size', 0), min=0, max=9999,
                          on_change=_ch_bps).classes('w-16')
                def _ch_bstype(e, idx=i): order['b_lines'][idx]['stock_type'] = e.value; refresh_preview()
                ui.select(STOCK_TYPES, value=ln.get('stock_type', 'STANDARD'), label='Stock Type',
                          on_change=_ch_bstype).classes('w-28')
                def _ch_bqty(e, idx=i): order['b_lines'][idx]['quantity'] = e.value; refresh_preview()
                ui.number('Qty', value=ln.get('quantity', 1), min=0, max=9999,
                          on_change=_ch_bqty).classes('w-16')
                def _ch_bq(e, idx=i): order['b_lines'][idx]['stock_quality'] = e.value; refresh_preview()
                ui.select(QUALITY_SELECT, value=ln.get('stock_quality', '1'), label='Q',
                          on_change=_ch_bq).classes('w-24')
                def _del_bl(idx=i):
                    order['b_lines'].pop(idx); direction_section.refresh(); refresh_preview()
                ui.button(icon='delete', on_click=_del_bl).props('flat round dense color=negative')
        if not order.get('b_lines'):
            ui.label('No order lines added').classes('text-grey-6 text-caption')

    else:
        # ── Outbound (10 / 35 / 36) ──────────────────────────────────────────
        def _ch_ct(e): order['carrier_type'] = e.value; refresh_preview()
        ui.select(CARRIER_TYPES, label='Carrier Type (C)',
                  value=order.get('carrier_type', 'LARGE'), on_change=_ch_ct).classes('w-full q-mt-sm')

        with ui.grid(columns=2).classes('w-full gap-3 q-mt-sm'):
            def _ch_pn(e): order['partner_number'] = e.value; refresh_preview()
            ui.input('Partner Number (E)', value=order.get('partner_number', ''),
                     on_change=_ch_pn).classes('w-full')
            def _ch_rn(e): order['route_number'] = e.value; refresh_preview()
            ui.input('Route Number (F)', value=order.get('route_number', ''),
                     on_change=_ch_rn).classes('w-full')

        def _ch_pri(e): order['priority'] = e.value; refresh_preview()
        ui.number('Priority (U)', value=order.get('priority', 0), min=0, max=999,
                  on_change=_ch_pri).classes('w-full q-mt-sm')

        ui.separator().classes('q-my-sm')
        ui.label('Control Parameters (O)').classes('text-caption text-grey-4')
        with ui.row().classes('flex-wrap gap-3 q-mt-xs'):
            for code, label in CONTROL_PARAMS_OPTS:
                checked = code in order.get('control_params', [])
                def _mkcp(c=code):
                    def _on(e):
                        params = order.setdefault('control_params', [])
                        if e.value:
                            if c not in params: params.append(c)
                        else:
                            if c in params: params.remove(c)
                        refresh_preview()
                    return _on
                ui.checkbox(f'{code} – {label}', value=checked, on_change=_mkcp())

        ui.separator().classes('q-my-sm')
        with ui.row().classes('items-center gap-2'):
            ui.label('Order Lines (Z)').classes('text-caption text-grey-4')
            def _add_zl():
                order['z_lines'].append({'article': '', 'stock_type': 'STANDARD', 'quantity': 1})
                direction_section.refresh(); refresh_preview()
            ui.button('Add', icon='add', on_click=_add_zl).props('flat dense color=primary size=sm')

        for i, ln in enumerate(order.get('z_lines', [])):
            with ui.row().classes('items-center gap-2 w-full q-mt-xs'):
                def _ch_zart(e, idx=i): order['z_lines'][idx]['article'] = e.value; refresh_preview()
                ui.input('Article', value=ln.get('article', ''), on_change=_ch_zart).classes('flex-1')
                def _ch_zstype(e, idx=i): order['z_lines'][idx]['stock_type'] = e.value; refresh_preview()
                ui.select(STOCK_TYPES, value=ln.get('stock_type', 'STANDARD'), label='Stock Type',
                          on_change=_ch_zstype).classes('w-32')
                def _ch_zqty(e, idx=i): order['z_lines'][idx]['quantity'] = e.value; refresh_preview()
                ui.number('Qty', value=ln.get('quantity', 1), min=0, max=9999,
                          on_change=_ch_zqty).classes('w-20')
                def _del_zl(idx=i):
                    order['z_lines'].pop(idx); direction_section.refresh(); refresh_preview()
                ui.button(icon='delete', on_click=_del_zl).props('flat round dense color=negative')
        if not order.get('z_lines'):
            ui.label('No order lines added').classes('text-grey-6 text-caption')


@ui.refreshable
def scenario_tab_content() -> None:
    sc  = _get_scenario(scen['scenario_id'])
    cat = sc.get('category', 'Outbound')

    with ui.row().classes('items-center gap-2 q-mb-xs'):
        ui.badge(cat).props(f'color={"orange" if cat == "Outbound" else "blue"}')
        ui.label(sc['name']).classes('text-subtitle2 text-bold text-blue-3')
    ui.label(sc.get('description', '')).classes('text-caption text-grey-4 q-mb-sm')
    ui.separator().classes('q-my-sm')

    if cat == 'Inbound':
        # ── Loading units ─────────────────────────────────────────────────────
        lus = sc.get('loading_units', [])
        ui.label(f'Loading Units → {len(lus)} × 12N will be sent').classes('text-caption text-grey-5 q-mb-xs')
        for lu in lus:
            with ui.card().classes('bg-grey-8 no-shadow q-pa-sm q-mb-xs w-full'):
                with ui.row().classes('items-center gap-3 q-mb-xs'):
                    ui.badge(lu['carrier_code']).props('color=deep-orange')
                    ui.label('order_type 04 — Decanting').classes('text-caption text-grey-5')
                for ln in lu.get('b_lines', []):
                    with ui.row().classes('items-center gap-2 q-mt-xs flex-wrap'):
                        ui.label(ln.get('article', '')).classes('font-mono text-caption text-white')
                        ui.label(f'qty {ln.get("quantity", 0)}').classes('text-caption text-grey-3')
                        ui.label(f'st {ln.get("station", "")}').classes('text-caption text-grey-5')
                        if ln.get('lot'):
                            ui.label(f'lot {ln["lot"]}').classes('text-caption text-orange-4')
                        if ln.get('expiry'):
                            ui.label(f'exp {ln["expiry"]}').classes('text-caption text-teal-4')

        ui.separator().classes('q-my-sm')

        # ── Expected responses ────────────────────────────────────────────────
        resps = sc.get('responses', [])
        ui.label(f'Expected Responses → {len(resps)} × 32R from KiSoft').classes('text-caption text-grey-5 q-mb-xs')
        for resp in resps:
            stn     = resp.get('last_scan_station', '')
            stn_lbl = STATION_LABELS.get(stn, '')
            states_txt = '  ·  '.join(ORDER_STATE_LABELS.get(s, s) for s in resp.get('order_states', []))
            with ui.card().classes('bg-grey-8 no-shadow q-pa-sm q-mb-xs w-full'):
                with ui.row().classes('items-center gap-3 q-mb-xs'):
                    ui.badge(resp.get('carrier_code', '')).props('color=blue-grey')
                    ui.badge(f'{stn} — {stn_lbl}' if stn_lbl else stn).props('color=teal')
                    ui.label(states_txt).classes('text-caption text-grey-4')
                for ln in resp.get('b_lines', []):
                    state = str(ln.get('line_state', '30'))
                    color = 'positive' if state == '30' else 'negative'
                    with ui.row().classes('items-center gap-2 q-mt-xs flex-wrap'):
                        ui.badge(state).props(f'color={color}')
                        ui.label(ln.get('article', '')).classes('font-mono text-caption')
                        ui.label(f'qty {ln.get("quantity", 0)}').classes('text-caption text-grey-3')
                        if ln.get('lot'):
                            ui.label(f'lot {ln["lot"]}').classes('text-caption text-orange-4')
                        if ln.get('expiry'):
                            ui.label(f'exp {ln["expiry"]}').classes('text-caption text-teal-4')

    else:
        # ── Outbound: responses (32R) ─────────────────────────────────────────
        ui.label('Responses').classes('text-caption text-grey-5 q-mb-xs')
        for resp in sc.get('responses', []):
            stn       = resp.get('last_scan_station', '')
            stn_lbl   = STATION_LABELS.get(stn, '')
            states_txt = '  ·  '.join(ORDER_STATE_LABELS.get(s, s) for s in resp.get('order_states', []))
            with ui.card().classes('bg-grey-8 no-shadow q-pa-sm q-mb-xs w-full'):
                with ui.row().classes('items-center gap-3 q-mb-xs'):
                    ui.badge(f'Sheet {resp["sheet"]}').props('color=blue-grey')
                    ui.badge(f'{stn} — {stn_lbl}' if stn_lbl else stn).props('color=teal')
                    ui.badge(resp.get('carrier_type', 'LARGE')).props('color=purple')
                    ui.label(states_txt).classes('text-caption text-grey-4')
                for ln in resp.get('z_lines', []):
                    state = str(ln.get('line_state', '30'))
                    color = 'positive' if state == '30' else 'negative'
                    with ui.row().classes('items-center gap-2 q-mt-xs flex-wrap'):
                        ui.badge(state).props(f'color={color}')
                        ui.label(ln.get('article', '')).classes('font-mono text-caption')
                        ui.label(f'qty {ln.get("quantity", 0)}').classes('text-caption text-grey-3')
                        ui.label(ln.get('stock_type', '')).classes('text-caption text-grey-5')
                        if ln.get('lot'):
                            ui.label(f'lot {ln["lot"]}').classes('text-caption text-orange-4')
                        if ln.get('geocode'):
                            ui.label(f'geo {ln["geocode"]}').classes('text-caption text-teal-4')

        ui.separator().classes('q-my-sm')
        ui.label('12N that will be sent').classes('text-caption text-grey-5 q-mb-xs')
        od = _build_order_from_scenario(sc, scen['client'], scen['order_number'])
        ui.label(
            f'Type 10 — Outbound delivery  ·  Carrier: {od["carrier_type"]}'
        ).classes('text-caption text-grey-3')
        for i, ln in enumerate(od.get('z_lines', []), 1):
            ui.label(
                f'  {i}.  {ln["article"]}   qty {ln["quantity"]}   {ln["stock_type"]}'
            ).classes('font-mono text-caption text-grey-3 q-mt-xs')
        if not od.get('z_lines'):
            ui.label('No lines').classes('text-caption text-grey-6')


def preview_area() -> None:
    el = ui.textarea(value=_initial_preview).props(
        'readonly outlined dark rows=20'
    ).classes('w-full font-mono text-xs')
    ctx['preview_el'] = el


def received_area() -> None:
    el = ui.textarea(value='').props(
        'readonly outlined dark rows=10'
    ).classes('w-full font-mono text-xs')
    ctx['received_el'] = el


def append_received(text: str, port: str = '') -> None:
    from datetime import datetime
    el = ctx['received_el']
    if el is None:
        return
    ts       = datetime.now().strftime('%H:%M:%S')
    sep      = '─' * 44
    port_tag = f'  ←  PORT {port}' if port else ''
    entry    = f'[{ts}]{port_tag}\n{text}'
    current  = el.value or ''
    el.value = entry + ('\n\n' + sep + '\n\n' + current if current else '')
    el.update()


def _clear_received() -> None:
    el = ctx['received_el']
    if el is not None:
        el.value = ''
        el.update()

# ─────────────────────────────────────────────────────────────────────────────
# Tab change
# ─────────────────────────────────────────────────────────────────────────────

def on_tab_change(e) -> None:
    ctx['tab'] = TAB_MAP.get(e.value, 'article')
    refresh_preview()

# ─────────────────────────────────────────────────────────────────────────────
# Layout
# ─────────────────────────────────────────────────────────────────────────────

ui.add_css('''
    .font-mono { font-family: "Courier New", Courier, monospace !important; }
    .q-field__native { font-family: "Courier New", Courier, monospace !important; }
''')

# Header ──────────────────────────────────────────────────────────────────────
with ui.header().classes('bg-grey-10 text-white px-4 gap-3 items-center'):
    ui.icon('electrical_services').classes('text-blue-4 text-2xl')
    ui.label('KiSoft One HIS — Client Simulator').classes('text-h6 font-bold')
    ui.space()
    with ui.row().classes('items-center gap-2'):
        host_input = ui.input('Host', value='127.0.0.1').props(
            'dense outlined dark standout'
        ).classes('w-44')

        def _connect():
            host = host_input.value or '127.0.0.1'
            stop_ev, send_q = start_connections(host, ui_queue)
            ctx['stop_event'] = stop_ev
            ctx['send_queue'] = send_q
            ctx['connected']  = True
            ctx['btn_conn'].classes('hidden')
            ctx['btn_disc'].classes(remove='hidden')
            append_received(f'— connecting to {host} —')

        def _disconnect():
            if ctx.get('stop_event'):
                stop_connections(ctx['stop_event'])
            ctx['stop_event'] = None
            ctx['send_queue'] = None
            ctx['connected']  = False
            ctx['btn_disc'].classes('hidden')
            ctx['btn_conn'].classes(remove='hidden')
            append_received('— disconnected —')

        ctx['btn_conn'] = ui.button('Connect',    icon='cable',    on_click=_connect).props('flat color=positive')
        ctx['btn_disc'] = ui.button('Disconnect', icon='link_off', on_click=_disconnect).props('flat color=negative').classes('hidden')

# Split layout ────────────────────────────────────────────────────────────────
with ui.splitter(value=58).classes('w-full h-screen') as sp:

    # Left: tabs + forms ──────────────────────────────────────────────────────
    with sp.before:
        with ui.tabs(on_change=on_tab_change).classes('bg-grey-9 text-white w-full') as tabs:
            tab_art  = ui.tab('Articles (14N)', icon='inventory_2')
            tab_prt  = ui.tab('Partners (15N)', icon='people')
            tab_rte  = ui.tab('Routes (16N)',   icon='route')
            tab_ord  = ui.tab('Orders (12N)',   icon='shopping_cart')
            tab_scen = ui.tab('Scenarios',      icon='play_circle')

        with ui.tab_panels(tabs, value=tab_art).classes('w-full bg-grey-10'):

            # 14N ─────────────────────────────────────────────────────────────
            with ui.tab_panel(tab_art):
                with ui.scroll_area().classes('w-full').style('height: calc(100vh - 115px)'):
                    with ui.card().classes('w-full bg-grey-9 no-shadow q-pa-md'):

                        with ui.row().classes('items-center justify-between w-full'):
                            ui.label('Article Master Data — 14N').classes('text-subtitle1 text-bold text-blue-3')
                            mode_toggle(art)
                        ui.separator()

                        with ui.grid(columns=3).classes('w-full gap-3'):
                            bind_select('Station', STATIONS, art, 'station').classes('w-full')
                            bind_select('Client', CLIENT_SELECT, art, 'client').classes('col-span-2 w-full')

                        with ui.grid(columns=3).classes('w-full gap-3 q-mt-sm'):
                            bind_input('Article Number (12)', art, 'article_number').classes('w-full')
                            bind_number('Pack Size', art, 'pack_size', min=0, max=9999).classes('w-full')
                            bind_number('Ejection # (10–80)', art, 'ejection_number', min=10, max=80).classes('w-full')
                            bind_number('Max Quantity', art, 'max_quantity', min=1, max=9999).classes('w-full')
                            bind_number('Length mm', art, 'length_mm', min=0, max=9999).classes('w-full')
                            bind_number('Width mm', art, 'width_mm', min=0, max=9999).classes('w-full')
                            bind_number('Height mm', art, 'height_mm', min=0, max=9999).classes('w-full')
                            bind_number('Weight (1/10 g)', art, 'weight', min=1, max=300000).classes('w-full')

                        with ui.grid(columns=2).classes('w-full gap-3 q-mt-sm'):
                            bind_input('Article Name (40)', art, 'article_name').classes('w-full')
                            bind_input('Geocode (12)', art, 'geocode').classes('w-full')
                            bind_number('Min Stock', art, 'min_stock', min=0, max=9999).classes('w-full')
                            bind_number('Max Stock', art, 'max_stock', min=0, max=9999).classes('w-full')
                            bind_input('Replenishment Station (3)', art, 'repl_station').classes('w-full')
                            bind_input('Replenishment Geocode (12)', art, 'repl_geocode').classes('w-full')

                        ui.separator().classes('q-my-sm')
                        ui.label('Characteristics').classes('text-caption text-grey-4')
                        with ui.row().classes('flex-wrap gap-3 q-mt-xs'):
                            for char in CHARS:
                                def _mkchar(c=char):
                                    def _on(e): art[f'char_{c}'] = e.value; refresh_preview()
                                    return _on
                                ui.checkbox(char, on_change=_mkchar())

                        ui.label('Properties').classes('text-caption text-grey-4 q-mt-sm')
                        with ui.row().classes('flex-wrap gap-3 q-mt-xs'):
                            for code, label in PROPS:
                                def _mkprop(p=code):
                                    def _on(e): art[f'prop_{p}'] = e.value; refresh_preview()
                                    return _on
                                ui.checkbox(label, on_change=_mkprop())

                        ui.separator().classes('q-my-sm')
                        with ui.row().classes('items-center gap-2'):
                            ui.label('Barcodes').classes('text-caption text-grey-4')
                            ui.button('Add', icon='add', on_click=add_barcode).props('flat dense color=primary size=sm')
                        barcode_list()

                        ui.separator().classes('q-my-md')
                        ui.button('Send Message', icon='send', on_click=send_article).props(
                            'color=primary'
                        ).classes('w-full')

            # 15N ─────────────────────────────────────────────────────────────
            with ui.tab_panel(tab_prt):
                with ui.scroll_area().classes('w-full').style('height: calc(100vh - 115px)'):
                    with ui.card().classes('w-full bg-grey-9 no-shadow q-pa-md'):

                        with ui.row().classes('items-center justify-between w-full'):
                            ui.label('Partner Master Data — 15N').classes('text-subtitle1 text-bold text-blue-3')
                            mode_toggle(prt)
                        ui.separator()

                        with ui.grid(columns=2).classes('w-full gap-3'):
                            bind_select('Client', CLIENT_SELECT, prt, 'client').classes('w-full')
                            bind_input('Partner Number (12)', prt, 'partner_number').classes('w-full')
                            bind_input('Company', prt, 'company').classes('w-full')
                            bind_input('Title / Treatment', prt, 'treatment').classes('w-full')
                            bind_input('Last Name', prt, 'last_name').classes('w-full')
                            bind_input('First Name', prt, 'first_name').classes('w-full')
                            bind_input('Street', prt, 'street').classes('w-full')
                            bind_input('City', prt, 'city').classes('w-full')
                            bind_input('ZIP Code (6)', prt, 'zip_code').classes('w-full')
                            bind_input('Region', prt, 'region').classes('w-full')
                            bind_input('Country Code (ISO 3166)', prt, 'country_code').classes('w-full')
                            bind_input('Email', prt, 'email').classes('w-full')
                        bind_input('Phone', prt, 'phone').classes('w-full q-mt-xs')

                        ui.separator().classes('q-my-md')
                        ui.button('Send Message', icon='send', on_click=send_partner).props(
                            'color=primary'
                        ).classes('w-full')

            # 16N ─────────────────────────────────────────────────────────────
            with ui.tab_panel(tab_rte):
                with ui.scroll_area().classes('w-full').style('height: calc(100vh - 115px)'):
                    with ui.card().classes('w-full bg-grey-9 no-shadow q-pa-md'):

                        with ui.row().classes('items-center justify-between w-full'):
                            ui.label('Theoretical Route Master — 16N').classes('text-subtitle1 text-bold text-blue-3')
                            mode_toggle(rte)
                        ui.separator()

                        with ui.grid(columns=2).classes('w-full gap-3'):
                            bind_select('Client', CLIENT_SELECT, rte, 'client').classes('w-full')
                            bind_input('Route Number (8)', rte, 'route_number').classes('w-full')
                            bind_input('Departure Time (HHmmss)', rte, 'departure_time').props('placeholder="080000"').classes('w-full')
                            bind_input('Availability Time (HHmmss)', rte, 'availability_time').props('placeholder="070000"').classes('w-full')
                            bind_select('Day of Week', DAY_SELECT, rte, 'day_of_week').classes('w-full')

                        ui.separator().classes('q-my-sm')
                        with ui.row().classes('items-center gap-2'):
                            ui.label('Dispatch Ramps').classes('text-caption text-grey-4')
                            ui.label('(max 20)').classes('text-caption text-grey-6')
                            ui.button('Add', icon='add', on_click=add_ramp).props('flat dense color=primary size=sm')
                        ramp_list()

                        ui.separator().classes('q-my-md')
                        ui.button('Send Message', icon='send', on_click=send_route).props(
                            'color=primary'
                        ).classes('w-full')

            # 12N ─────────────────────────────────────────────────────────────
            with ui.tab_panel(tab_ord):
                with ui.scroll_area().classes('w-full').style('height: calc(100vh - 115px)'):
                    with ui.card().classes('w-full bg-grey-9 no-shadow q-pa-md'):

                        ui.label('Order Data — 12N').classes('text-subtitle1 text-bold text-blue-3')
                        ui.separator()

                        with ui.grid(columns=3).classes('w-full gap-3'):
                            bind_select('Client', CLIENT_SELECT, order, 'client').classes('w-full')
                            bind_input('Order Number (12)', order, 'order_number').classes('w-full')
                            bind_number('Sheet Number', order, 'sheet_number', min=0, max=9999).classes('w-full')

                        def _on_ot(e):
                            order['order_type'] = e.value
                            direction_section.refresh()
                            refresh_preview()
                        ui.select(ORDER_TYPES, label='Order Type (T)',
                                  value=order.get('order_type', '10'),
                                  on_change=_on_ot).classes('w-full q-mt-sm')

                        ui.separator().classes('q-my-sm')
                        direction_section()

                        ui.separator().classes('q-my-md')
                        ui.button('Send Message', icon='send', on_click=send_order).props(
                            'color=primary'
                        ).classes('w-full')

            # Scenarios ──────────────────────────────────────────────────────
            with ui.tab_panel(tab_scen):
                with ui.scroll_area().classes('w-full').style('height: calc(100vh - 115px)'):
                    with ui.card().classes('w-full bg-grey-9 no-shadow q-pa-md'):

                        ui.label('Quick Send — Scenarios').classes('text-subtitle1 text-bold text-blue-3')
                        ui.separator()

                        def _on_scen_sel(e):
                            scen['scenario_id'] = e.value
                            scenario_tab_content.refresh()
                            refresh_preview()

                        def _sc_label(sc):
                            tag = '[OUT]' if sc['category'] == 'Outbound' else '[IN] '
                            return f'{tag}  {sc["name"]}'
                        ui.select(
                            {sc['id']: _sc_label(sc) for sc in SCENARIOS},
                            value=scen['scenario_id'],
                            label='Scenario',
                            on_change=_on_scen_sel,
                        ).classes('w-full q-mt-sm').props('outlined dark dense')

                        with ui.grid(columns=2).classes('w-full gap-3 q-mt-sm'):
                            def _ch_scen_client(e):
                                scen['client'] = e.value
                                scenario_tab_content.refresh()
                                refresh_preview()
                            ui.select(CLIENT_SELECT, label='Client',
                                      value=scen['client'],
                                      on_change=_ch_scen_client).classes('w-full')

                            def _ch_scen_order(e):
                                scen['order_number'] = e.value
                                scenario_tab_content.refresh()
                                refresh_preview()
                            ui.input('Order Number', value=scen['order_number'],
                                     on_change=_ch_scen_order).classes('w-full')

                        ui.separator().classes('q-my-sm')
                        scenario_tab_content()

                        ui.separator().classes('q-my-md')
                        ui.button('Send Matching Order', icon='send',
                                  on_click=send_scenario_order).props('color=primary').classes('w-full')

    # Right: preview (top) + received (bottom) ───────────────────────────────
    with sp.after:
        with ui.splitter(value=38, horizontal=True).classes('w-full').style('height: calc(100vh - 55px)') as rsp:

            # ── Message Preview (top) ─────────────────────────────────────────
            with rsp.before:
                with ui.card().classes('w-full bg-grey-9 no-shadow q-pa-sm h-full'):
                    with ui.row().classes('items-center justify-between w-full q-mb-xs'):
                        ui.label('Message Preview').classes('text-subtitle2 text-bold text-blue-3')
                        def _copy():
                            el = ctx['preview_el']
                            text = el.value if el is not None else ''
                            ui.run_javascript(f'navigator.clipboard.writeText({json.dumps(text)})')
                            ui.notify('Copied!', type='positive', position='top-right')
                        def _clear():
                            _set_preview('')
                        ui.button('Copy', icon='content_copy', on_click=_copy).props('flat dense color=primary size=sm')
                        ui.button('Clear', icon='delete_sweep', on_click=_clear).props('flat dense color=negative size=sm')
                    ui.separator()
                    preview_area()

            # ── Received Messages (bottom) ────────────────────────────────────
            with rsp.after:
                with ui.card().classes('w-full bg-grey-9 no-shadow q-pa-sm h-full'):
                    with ui.row().classes('items-center justify-between w-full q-mb-xs'):
                        with ui.row().classes('items-center gap-2'):
                            ui.icon('call_received').classes('text-green-4 text-sm')
                            ui.label('Received Messages').classes('text-subtitle2 text-bold text-green-4')
                        with ui.row().classes('items-center gap-1'):
                            def _copy_rx():
                                el = ctx['received_el']
                                text = el.value if el is not None else ''
                                ui.run_javascript(f'navigator.clipboard.writeText({json.dumps(text)})')
                                ui.notify('Copied!', type='positive', position='top-right')
                            def _clear_rx():
                                _clear_received()
                            ui.button('Copy', icon='content_copy', on_click=_copy_rx).props('flat dense color=primary size=sm')
                            ui.button('Clear', icon='delete_sweep', on_click=_clear_rx).props('flat dense color=negative size=sm')
                    ui.separator()
                    received_area()

# ─────────────────────────────────────────────────────────────────────────────
# Drain socket queues into the Received Messages panel (10×/s)
# ─────────────────────────────────────────────────────────────────────────────

def _on_log(text: str) -> None:
    append_received(f'— {text} —')

ui.timer(0.1, lambda: drain_ui_queue(ui_queue, append_received, _on_log))

ui.run(title='KiSoft HIS Client', dark=True, port=8083, reload=False)
