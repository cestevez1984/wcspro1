#!/usr/bin/env python3
"""COHEN Guatemala — KiSoft One WCS Mock Server"""

import pathlib, queue, sys, os, socket, threading, time
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from nicegui import ui
from classes.protocol import encode_packet
from classes.connection import recv_frame
from classes.order_response import OrderResponseMessage, parse_12n
from server.scenarios import SCENARIOS

# ─────────────────────────────────────────────────────────────────────────────
# ACK map — for every record the client sends on port 9801
# ─────────────────────────────────────────────────────────────────────────────

ACK_MAP_9801 = {
    '1HR': '2HR',
    '140': '240', '141': '241', '149': '249',
    '14N': '24N', '14D': '24D',
    '150': '250', '151': '251', '159': '259',
    '15N': '25N', '15D': '25D',
    '160': '260', '161': '261', '169': '269',
    '16N': '26N', '16D': '26D',
    '12N': '22N', '12D': '22D', '12U': '22U',
    '1IA': '2IA', '1RR': '2RR',
    '1UN': '2UN', '1UU': '2UU', '1UD': '2UD', '1SL': '2SL',
}

# ─────────────────────────────────────────────────────────────────────────────
# Scenario persistence — plain text file so that the NiceGUI process and
# the background socket threads always read the same value.
# ─────────────────────────────────────────────────────────────────────────────

SCENARIO_FILE = pathlib.Path(__file__).parent / 'active_scenario.txt'

def _get_active_id() -> str:
    try:
        sc_id = SCENARIO_FILE.read_text().strip()
        valid_ids = {sc['id'] for sc in SCENARIOS}
        return sc_id if sc_id in valid_ids else SCENARIOS[0]['id']
    except Exception:
        return SCENARIOS[0]['id']

def _set_active_id(sc_id: str) -> None:
    SCENARIO_FILE.write_text(sc_id)

if not SCENARIO_FILE.exists():       # only initialise on first run; preserve across restarts
    _set_active_id(SCENARIOS[0]['id'])

# ─────────────────────────────────────────────────────────────────────────────
# Shared state
# ─────────────────────────────────────────────────────────────────────────────

ui_queue        = queue.Queue()   # threads → GUI
trigger_queue   = queue.Queue()   # 9801 thread → 9802 thread (order_info)
_inbound_buffer = {}              # {order_number: count_received} for inbound accumulation

ctx = {
    'log_el':        None,
    'badge_9801':    None,
    'badge_9802':    None,
    'detail_panel':  None,
}

LINE_STATE_LABELS = {
    '30': '30 – OK', '58': '58 – Out of stock',
    '51': '51 – Qty mismatch', '57': '57 – Off sale',
}
ORDER_STATE_LABELS = {
    '0001': 'started', '0002': 'completed',
    '0003': 'cancelled (GUI)', '0004': 'cancelled (host)',
    '0010': 'last carrier',
}

# ─────────────────────────────────────────────────────────────────────────────
# Server threads
# ─────────────────────────────────────────────────────────────────────────────

def server_thread_9801() -> None:
    """Listen on 9801. Receive any HIS message, send ACK.
    When a 12N arrives: extract order_info, put (order_info, scenario) in trigger_queue.
    """
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as srv:
        srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        srv.bind(('', 9801))
        srv.listen(1)
        srv.settimeout(1)
        _log('9801 listening on port 9801')
        _badge('9801', 'listening', 'orange')

        while True:
            try:
                conn, addr = srv.accept()
                _log(f'9801 ← client connected  {addr[0]}')
                _badge('9801', 'connected', 'positive')
                try:
                    with conn:
                        conn.settimeout(30)
                        while True:
                            try:
                                data      = recv_frame(conn)
                                record_id = data[:3].decode()
                                ack_id    = ACK_MAP_9801.get(record_id, '00000')
                                conn.sendall(encode_packet(ack_id + '00'))
                                _log(f'← {record_id}   → {ack_id}')

                                if record_id == '12N':
                                    order_info = parse_12n(data)
                                    order_type = order_info.get('order_type', '10')
                                    scenario   = _get_selected()
                                    if order_type in ('02', '04', '05'):
                                        # Inbound — accumulate all loading units before triggering
                                        key      = order_info['order_number']
                                        expected = len(scenario.get('loading_units', [])) or 1
                                        _inbound_buffer[key] = _inbound_buffer.get(key, 0) + 1
                                        got = _inbound_buffer[key]
                                        _log(f'   inbound LU {got}/{expected}  ({key})')
                                        if got >= expected:
                                            trigger_queue.put(order_info)
                                            del _inbound_buffer[key]
                                            _log(f'   → all LUs received, queued: {scenario["name"]}')
                                    else:
                                        trigger_queue.put(order_info)
                                        _log(f'   queued for scenario: {scenario["name"]}')

                            except socket.timeout:
                                pass  # keep connection alive, wait for next message

                except Exception as e:
                    _log(f'9801 client error: {e}')

                _badge('9801', 'waiting', 'orange')

            except socket.timeout:
                pass  # no client yet, keep listening
            except Exception as e:
                _log(f'9801 server error: {e}')
                time.sleep(2)


def server_thread_9802() -> None:
    """Listen on 9802. Hold client connection.
    When trigger_queue fires: send 32R(s) from the scenario, wait for 42R each time.
    """
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as srv:
        srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        srv.bind(('', 9802))
        srv.listen(1)
        srv.settimeout(1)
        _log('9802 listening on port 9802')
        _badge('9802', 'listening', 'orange')

        while True:
            try:
                conn, addr = srv.accept()
                _log(f'9802 ← client connected  {addr[0]}')
                _badge('9802', 'connected', 'positive')
                try:
                    with conn:
                        while True:
                            try:
                                order_info = trigger_queue.get(timeout=1)
                                scenario   = _get_selected()
                                responses  = scenario['responses']
                                highest    = max(r.get('sheet', 1) for r in responses)
                                _log(f'▶ scenario: {scenario["name"]}  ({highest} response(s))')

                                for i, resp in enumerate(responses, 1):
                                    time.sleep(0.8)
                                    _log(f'  sending 32R {i}/{highest} ...')
                                    msg = OrderResponseMessage(order_info, resp, highest)
                                    conn.sendall(msg.packet)
                                    sheet  = resp['sheet']
                                    stn    = resp['last_scan_station']
                                    states = ', '.join(
                                        ORDER_STATE_LABELS.get(s, s)
                                        for s in resp['order_states']
                                    )
                                    _log(f'→ 32R  sheet {sheet}  station {stn}  [{states}]')

                                    ack = recv_frame(conn)
                                    _log(f'← {ack[:3].decode()}  (waiting for next)')

                                _log(f'✓ all {highest} response(s) sent')

                            except queue.Empty:
                                pass  # no trigger yet, keep connection alive
                            except Exception as exc:
                                _log(f'9802 send error: {exc}')
                                trigger_queue.put(order_info)  # re-queue so new connection picks it up
                                break  # exit with conn: to accept new client

                except Exception as e:
                    _log(f'9802 client error: {e}')

                _badge('9802', 'waiting', 'orange')

            except socket.timeout:
                pass
            except Exception as e:
                _log(f'9802 server error: {e}')
                time.sleep(2)


# ─────────────────────────────────────────────────────────────────────────────
# Thread → GUI helpers (put items in ui_queue; timer drains it)
# ─────────────────────────────────────────────────────────────────────────────

def _log(text: str) -> None:
    ui_queue.put(('log', text))

def _badge(port: str, label: str, color: str) -> None:
    ui_queue.put(('badge', port, label, color))

def drain() -> None:
    while True:
        try:
            item = ui_queue.get_nowait()
            kind = item[0]

            if kind == 'log':
                el = ctx['log_el']
                if el:
                    ts      = datetime.now().strftime('%H:%M:%S')
                    entry   = f'[{ts}]  {item[1]}'
                    current = el.value or ''
                    el.value = (entry + ('\n' + current if current else ''))[:6000]
                    el.update()

            elif kind == 'badge':
                _, port, label, color = item
                el = ctx[f'badge_{port}']
                if el:
                    el.props(f'color={color}')
                    el.text = label
                    el.update()

        except queue.Empty:
            break


# ─────────────────────────────────────────────────────────────────────────────
# Scenario helpers
# ─────────────────────────────────────────────────────────────────────────────

def _get_selected() -> dict:
    active_id = _get_active_id()
    for sc in SCENARIOS:
        if sc['id'] == active_id:
            return sc
    return SCENARIOS[0]


@ui.refreshable
def scenario_detail() -> None:
    sc = _get_selected()
    cat = sc.get('category', 'Outbound')
    cat_color = 'orange-4' if cat == 'Outbound' else 'blue-4'
    with ui.row().classes('items-center gap-2 q-mb-xs'):
        ui.badge(cat).props(f'color={"orange" if cat == "Outbound" else "blue"}')
        ui.label(sc['name']).classes('text-subtitle1 text-bold text-blue-3')
    ui.label(sc['description']).classes('text-caption text-grey-4 q-mb-sm')
    ui.separator()

    if cat == 'Inbound':
        # ── Loading units (12N messages the client will send) ─────────────────
        ui.label('Loading Units (12N × sent)').classes('text-caption text-grey-5 q-mt-xs q-mb-xs')
        for lu in sc.get('loading_units', []):
            with ui.card().classes('bg-grey-8 no-shadow q-pa-sm q-mb-sm w-full'):
                with ui.row().classes('items-center gap-3 q-mb-xs'):
                    ui.badge(lu['carrier_code']).props('color=deep-orange')
                    ui.label('12N  order_type 04').classes('text-caption text-grey-5')
                for ln in lu.get('b_lines', []):
                    with ui.row().classes('items-center gap-3 q-mt-xs'):
                        ui.label(ln['article']).classes('font-mono text-caption text-white')
                        ui.label(f'qty {ln["quantity"]}').classes('text-caption text-grey-3')
                        if ln.get('lot'):
                            ui.label(f'lot {ln["lot"]}').classes('text-caption text-orange-4')
                        if ln.get('expiry'):
                            ui.label(f'exp {ln["expiry"]}').classes('text-caption text-teal-4')

        ui.separator().classes('q-my-sm')

        # ── Storage unit responses (32R KiSoft will send back) ────────────────
        ui.label('Storage Units (32R × received)').classes('text-caption text-grey-5 q-mb-xs')
        for resp in sc.get('responses', []):
            states_text = '  ·  '.join(ORDER_STATE_LABELS.get(s, s) for s in resp.get('order_states', []))
            with ui.card().classes('bg-grey-8 no-shadow q-pa-sm q-mb-sm w-full'):
                with ui.row().classes('items-center gap-4 q-mb-xs'):
                    ui.badge(resp['carrier_code']).props('color=blue-grey')
                    ui.badge(f'Station {resp["last_scan_station"]}').props('color=teal')
                    ui.label(states_text).classes('text-caption text-grey-4')
                for ln in resp.get('b_lines', []):
                    state_label = LINE_STATE_LABELS.get(str(ln['line_state']), str(ln['line_state']))
                    color = 'positive' if str(ln['line_state']) == '30' else 'negative'
                    with ui.row().classes('items-center gap-3 q-mt-xs'):
                        ui.badge(state_label).props(f'color={color}')
                        ui.label(ln['article']).classes('font-mono text-caption')
                        ui.label(f'qty {ln["quantity"]}').classes('text-caption text-grey-3')
                        if ln.get('lot'):
                            ui.label(f'lot {ln["lot"]}').classes('text-caption text-orange-4')

    else:
        # ── Outbound: existing response display ───────────────────────────────
        for resp in sc.get('responses', []):
            states_text = '  ·  '.join(
                ORDER_STATE_LABELS.get(s, s) for s in resp.get('order_states', [])
            )
            with ui.card().classes('bg-grey-8 no-shadow q-pa-sm q-mb-sm w-full'):
                with ui.row().classes('items-center gap-4 q-mb-xs'):
                    ui.badge(f'Sheet {resp["sheet"]}').props('color=blue-grey')
                    ui.badge(f'Station {resp["last_scan_station"]}').props('color=teal')
                    ui.badge(resp.get('carrier_type', '')).props('color=purple')
                    ui.label(states_text).classes('text-caption text-grey-4')

                for ln in resp.get('z_lines', []):
                    state_label = LINE_STATE_LABELS.get(str(ln['line_state']), str(ln['line_state']))
                    color = 'positive' if str(ln['line_state']) == '30' else 'negative'
                    with ui.row().classes('items-center gap-3 q-mt-xs'):
                        ui.badge(state_label).props(f'color={color}')
                        ui.label(ln['article']).classes('font-mono text-caption')
                        ui.label(f'qty {ln["quantity"]}').classes('text-caption text-grey-3')
                        ui.label(ln['stock_type']).classes('text-caption text-grey-5')


@ui.refreshable
def scenario_list() -> None:
    categories: dict = {}
    for sc in SCENARIOS:
        categories.setdefault(sc['category'], []).append(sc)

    for cat, items in categories.items():
        ui.label(cat).classes('text-caption text-grey-5 q-mt-md q-mb-xs')
        for sc in items:
            is_sel = sc['id'] == _get_active_id()
            with ui.card().classes(
                'w-full no-shadow q-pa-sm q-mb-xs ' +
                ('bg-grey-7 border-left' if is_sel else 'bg-grey-9')
            ):
                with ui.row().classes('items-center gap-2'):
                    if is_sel:
                        ui.icon('radio_button_checked').classes('text-orange-4 text-sm')
                    else:
                        ui.icon('radio_button_unchecked').classes('text-grey-6 text-sm')
                    ui.label(sc['name']).classes(
                        'text-caption ' + ('text-white' if is_sel else 'text-grey-4')
                    )


# ─────────────────────────────────────────────────────────────────────────────
# Layout
# ─────────────────────────────────────────────────────────────────────────────

ui.add_css('.font-mono { font-family: "Courier New", Courier, monospace !important; }')

# Header ──────────────────────────────────────────────────────────────────────
with ui.header().classes('bg-grey-10 text-white px-4 gap-3 items-center'):
    ui.icon('dns').classes('text-orange-4 text-2xl')
    ui.label('KiSoft One — WCS Mock Server').classes('text-h6 font-bold')
    ui.space()
    with ui.row().classes('items-center gap-4'):
        ui.label('9801').classes('text-caption text-grey-4')
        ctx['badge_9801'] = ui.badge('starting').props('color=grey')
        ui.label('9802').classes('text-caption text-grey-4')
        ctx['badge_9802'] = ui.badge('starting').props('color=grey')

# Main layout ─────────────────────────────────────────────────────────────────
with ui.splitter(value=35).classes('w-full').style('height: calc(100vh - 55px)') as sp:

    # Left — scenario list ────────────────────────────────────────────────────
    with sp.before:
        with ui.scroll_area().classes('w-full h-full q-pa-md'):
            ui.label('Scenarios').classes('text-subtitle2 text-bold text-orange-4 q-mb-sm')

            def _on_select(e):
                _set_active_id(e.value)
                _log(f'scenario → {_get_selected()["name"]}')
                scenario_list.refresh()
                scenario_detail.refresh()

            ui.select(
                {sc['id']: ('[OUT]' if sc['category'] == 'Outbound' else '[IN] ') + '  ' + sc['name'] for sc in SCENARIOS},
                value=_get_active_id(),
                label='Active Scenario',
                on_change=_on_select,
            ).classes('w-full q-mb-md').props('outlined dark dense')

            scenario_list()

    # Right — detail + log ────────────────────────────────────────────────────
    with sp.after:
        with ui.splitter(value=55, horizontal=True).classes('w-full h-full') as rsp:

            # Scenario detail (top) ───────────────────────────────────────────
            with rsp.before:
                with ui.card().classes('w-full bg-grey-9 no-shadow q-pa-md h-full'):
                    scenario_detail()

            # Connection log (bottom) ─────────────────────────────────────────
            with rsp.after:
                with ui.card().classes('w-full bg-grey-9 no-shadow q-pa-sm h-full'):
                    with ui.row().classes('items-center justify-between w-full q-mb-xs'):
                        with ui.row().classes('items-center gap-2'):
                            ui.icon('terminal').classes('text-orange-4 text-sm')
                            ui.label('Connection Log').classes('text-subtitle2 text-bold text-orange-4')
                        def _clear_log():
                            el = ctx['log_el']
                            if el:
                                el.value = ''
                                el.update()
                        ui.button('Clear', icon='delete_sweep', on_click=_clear_log).props(
                            'flat dense color=negative size=sm'
                        )
                    ui.separator()
                    log_el = ui.textarea(value='').props(
                        'readonly outlined dark rows=12'
                    ).classes('w-full font-mono text-xs')
                    ctx['log_el'] = log_el

# Timer: drain ui_queue into GUI elements
ui.timer(0.1, drain)

# ─────────────────────────────────────────────────────────────────────────────
# Start server threads (daemon — die when process exits)
# ─────────────────────────────────────────────────────────────────────────────

threading.Thread(target=server_thread_9801, daemon=True, name='mock-9801').start()
threading.Thread(target=server_thread_9802, daemon=True, name='mock-9802').start()

ui.run(title='KiSoft Mock Server', dark=True, port=8084, reload=False)
