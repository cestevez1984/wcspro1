#!/usr/bin/env python3
"""COHEN Guatemala – KiSoft One HIS Client Simulator"""

import json, sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from nicegui import ui
from classes import (
    ArticleMessage, ArticleTransmission,
    PartnerMessage, PartnerTransmission,
    RouteMessage,   RouteTransmission,
)

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

TAB_MAP = {'Articles (14N)': 'article', 'Partners (15N)': 'partner', 'Routes (16N)': 'route'}

MODE_OPTIONS = {'recreate': 'Recreate All', 'partial': 'Partial Update'}

# ─────────────────────────────────────────────────────────────────────────────
# Application state
# ─────────────────────────────────────────────────────────────────────────────

art: dict = {'station': '001', 'client': 'DEFAULT', 'barcodes': [], 'mode': 'recreate'}
prt: dict = {'client': 'DEFAULT', 'mode': 'recreate'}
rte: dict = {'client': 'DEFAULT', 'day_of_week': '', 'ramps': [], 'mode': 'recreate'}

ctx: dict = {'tab': 'article', 'preview_el': None}

# Pre-compute initial preview (no event loop needed at this point)
try:
    _initial_preview = ArticleMessage(art).display()
except Exception as _e:
    _initial_preview = str(_e)

# ─────────────────────────────────────────────────────────────────────────────
# Preview helpers
# ─────────────────────────────────────────────────────────────────────────────

def _set_preview(text: str) -> None:
    el = ctx['preview_el']
    if el is not None:
        el.value = text
        el.update()

def refresh_preview() -> None:
    try:
        tab = ctx['tab']
        if tab == 'article':   msg = ArticleMessage(art)
        elif tab == 'partner': msg = PartnerMessage(prt)
        else:                  msg = RouteMessage(rte)
        _set_preview(msg.display())
    except Exception as exc:
        _set_preview(f'Error building message:\n{exc}')

def send_article() -> None:
    try:
        _set_preview(ArticleTransmission(art.get('mode', 'recreate'), art).display())
    except Exception as exc:
        _set_preview(f'Error building transmission:\n{exc}')

def send_partner() -> None:
    try:
        _set_preview(PartnerTransmission(prt.get('mode', 'recreate'), prt).display())
    except Exception as exc:
        _set_preview(f'Error building transmission:\n{exc}')

def send_route() -> None:
    try:
        _set_preview(RouteTransmission(rte.get('mode', 'recreate'), rte).display())
    except Exception as exc:
        _set_preview(f'Error building transmission:\n{exc}')

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


def preview_area() -> None:
    el = ui.textarea(value=_initial_preview).props(
        'readonly outlined dark rows=32'
    ).classes('w-full font-mono text-xs')
    ctx['preview_el'] = el

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
        ui.input('Host', value='89.207.120.100').props('dense outlined dark standout').classes('w-44')
        ui.number('Port', value=9801, min=1025, max=65535).props('dense outlined dark').classes('w-24')
        ui.button('Connect', icon='cable').props('flat color=positive')

# Split layout ────────────────────────────────────────────────────────────────
with ui.splitter(value=58).classes('w-full h-screen') as sp:

    # Left: tabs + forms ──────────────────────────────────────────────────────
    with sp.before:
        with ui.tabs(on_change=on_tab_change).classes('bg-grey-9 text-white w-full') as tabs:
            tab_art = ui.tab('Articles (14N)',  icon='inventory_2')
            tab_prt = ui.tab('Partners (15N)',  icon='people')
            tab_rte = ui.tab('Routes (16N)',    icon='route')

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

    # Right: message preview ──────────────────────────────────────────────────
    with sp.after:
        with ui.card().classes('w-full bg-grey-9 no-shadow q-pa-sm').style('height: calc(100vh - 55px)'):
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

# ─────────────────────────────────────────────────────────────────────────────

ui.run(title='KiSoft HIS Client', dark=True, port=8083, reload=False)
