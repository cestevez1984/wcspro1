import socket
import threading
import queue
import time

from .protocol import encode_packet

STATION_LABELS = {
    '001': 'Manual M001',
    '002': 'Manual M002',
    '003': 'Manual M003',
    '004': 'Manual M004',
    '010': 'M010 Controlled substance',
    '011': 'M011 Cooling',
    '061': 'BULK001 Full carton',
    '065': 'OSR Shuttle (pick)',
    '091': 'CBS (SDA check station)',
    '092': 'OSR (check station)',
    '095': 'GPA001 Marking',
    '190': 'OS001 Start station',
    '199': 'Bulk station',
    '183': 'DIS001 Dispatch ramp',
    '184': 'DIS002 Dispatch ramp',
    '017': 'ST003 Non-reusable',
    '027': 'PA002 Verification',
}

# ACKs the server sends automatically for each message received on port 9802
ACK_MAP_9802 = {
    '3HR': '4HR',
    '32R': '42R',
    '3SC': '4SC',
    '3UE': '4UE',
    '3UU': '4UU',
    '3IR': '4IR',
    '3RR': '4RR',
}


# ─────────────────────────────────────────────────────────────────────────────
# Frame helpers
# ─────────────────────────────────────────────────────────────────────────────

def recv_frame(s: socket.socket) -> bytes:
    """Read exactly one complete HIS frame from an open socket.
    Returns the raw payload bytes (no LF/count/CR).
    """
    def read(n: int) -> bytes:
        buf = b''
        while len(buf) < n:
            chunk = s.recv(n - len(buf))
            if not chunk:
                raise ConnectionError('Connection closed by remote')
            buf += chunk
        return buf

    read(1)                     # consume LF
    count = int(read(5))        # byte count field → tells us payload length
    data  = read(count - 5)     # count includes itself (5 bytes), so payload = count - 5
    read(1)                     # consume CR
    return data


# ─────────────────────────────────────────────────────────────────────────────
# 32R field lookup tables
# ─────────────────────────────────────────────────────────────────────────────

_LINE_STATE = {
    '30': 'OK',                   '50': 'technical error',
    '51': 'qty mismatch',         '52': 'corrected at control',
    '53': 'unknown article',      '54': 'qty = 0',
    '55': 'qty > max',            '56': 'carrier full',
    '57': 'off sale',             '58': 'out of stock',
    '59': 'blocked',              '60': 'no suitable pack size',
    '65': 'vision belt read error','93': 'line deleted by host',
}
_ORDER_STATE = {
    '0001': 'started',            '0002': 'completed',
    '0003': 'cancelled (GUI)',    '0004': 'cancelled (host)',
    '0005': 'timeout',            '0010': 'last carrier',
}
_SCAN_STATE = {'0': 'not passed', '1': 'passed'}


def _fmt_ts(t: str) -> str:
    if len(t) == 14:
        return f'{t[0:4]}-{t[4:6]}-{t[6:8]}  {t[8:10]}:{t[10:12]}:{t[12:14]}'
    return t


def _parse_32r(s: str) -> str:
    """Parse every field of a 32R payload and return a labeled breakdown.

    Offsets match exactly the build order in OrderResponseMessage._build().
    """
    SEP = '  —  '
    L = []

    # ── Fixed header ──────────────────────────────────────────────────────────
    client        = s[5:21].strip()
    order_number  = s[23:35].strip()
    sheet         = s[37:41]
    order_type    = s[44:46]
    highest_sheet = s[49:53]
    start_stn     = s[58:61]
    carrier_type  = s[64:74].strip()
    carrier_code  = s[77:85].strip()
    ramp          = s[88:93]
    start_time    = s[96:110]
    end_time      = s[113:127]
    last_scan_stn = s[130:133]
    scan_time     = s[135:149]
    scan_state    = s[151]

    L += [
        f'     client        {client}',
        f'     order_number  {order_number}',
        f'     sheet         {sheet}  (highest: {highest_sheet})',
        f'  T  order_type    {order_type}',
        f'  B  start_stn     {start_stn}  —  {STATION_LABELS.get(start_stn, "")}',
        f'  C  carrier_type  {carrier_type}',
        f'  D  carrier_code  {carrier_code}',
        f'  G  ramp          {ramp}',
        f'  s  start_time    {_fmt_ts(start_time)}',
        f'  e  end_time      {_fmt_ts(end_time)}',
        f'  t  last_stn      {last_scan_stn}  —  {STATION_LABELS.get(last_scan_stn, "")}',
        f'     scan_time     {_fmt_ts(scan_time)}',
        f'     scan_state    {scan_state}{SEP}{_SCAN_STATE.get(scan_state, "?")}',
        '',
    ]

    # ── O — order states ──────────────────────────────────────────────────────
    pos = 152
    if s[pos] != 'O':
        L.append(f'[parse error: expected O at pos {pos}, got "{s[pos]}"]')
        return '\n'.join(L)
    cnt = int(s[pos + 1:pos + 3])
    pos += 3
    L.append(f'  O  states ({cnt}):')
    for _ in range(cnt):
        val = s[pos + 2:pos + 6]
        L.append(f'       {val}{SEP}{_ORDER_STATE.get(val, val)}')
        pos += 6
    L.append('')

    # ── Z — processed lines ───────────────────────────────────────────────────
    if s[pos] != 'Z':
        L.append(f'[parse error: expected Z at pos {pos}, got "{s[pos]}"]')
        return '\n'.join(L)
    zcnt = int(s[pos + 1:pos + 3])
    pos += 3
    L.append(f'  Z  lines ({zcnt}):')
    for i in range(zcnt):
        if i > 0:
            L.append('')
        article    = s[pos + 2:pos + 14].strip();  pos += 14
        pack_size  = s[pos + 2:pos + 6];           pos += 6
        stock_type = s[pos + 2:pos + 10].strip();  pos += 10
        lot_len    = int(s[pos:pos + 2]);           pos += 2   # '00' or '20'
        lot        = s[pos:pos + lot_len].strip();  pos += lot_len
        expiry_len = int(s[pos:pos + 2]);           pos += 2
        expiry     = s[pos:pos + expiry_len];       pos += expiry_len
        quantity   = s[pos + 2:pos + 6];           pos += 6
        quality    = s[pos + 2:pos + 3];           pos += 3
        line_state   = s[pos + 2:pos + 4].strip();   pos += 4
        geocode_len  = int(s[pos:pos + 2]);           pos += 2   # '00' or '12'
        geocode      = s[pos:pos + geocode_len].strip(); pos += geocode_len
        mark       = '✓' if line_state == '30' else '✗'
        state_desc = _LINE_STATE.get(line_state, '')
        row = [
            f'       [{i + 1}]  article     {article}',
            f'            pack_size   {pack_size}',
            f'            stock_type  {stock_type}',
        ]
        if lot:
            row.append(f'            lot         {lot}')
        row += [
            f'            quantity    {quantity}',
            f'            quality     {quality}',
            f'            line_state  {line_state}  {mark}  {state_desc}',
        ]
        if geocode:
            row.append(f'            geocode     {geocode}')
        L += row

    return '\n'.join(L)


def format_received(data: bytes) -> str:
    """Format raw payload bytes for display.

    Always shows the raw symbolic frame first, then — for 32R — appends a
    field-by-field breakdown so every segment can be validated against the spec.
    """
    text      = data.decode('utf-8')
    packet    = encode_packet(text)
    raw_line  = f'[LF]{packet[1:-1].decode("utf-8")}[CR]'

    if text[:3] == '32R':
        # Extract carrier and station directly from fixed offsets (no parser needed)
        carrier_code      = text[77:85].strip()
        last_scan_station = text[130:133].strip()
        station_label     = STATION_LABELS.get(last_scan_station, last_scan_station)
        banner = (
            '▶▶▶  ' + carrier_code +
            '  ·  STATION ' + last_scan_station +
            '  —  ' + station_label +
            '  ◀◀◀'
        )
        bar = '═' * len(banner)
        try:
            parsed = _parse_32r(text)
        except Exception as exc:
            parsed = f'[parse error: {exc}]'
        divider = '·' * 44
        return f'{bar}\n{banner}\n{bar}\n\n{raw_line}\n\n{divider}\n\n32R — Order Response\n\n{parsed}'

    return raw_line


# ─────────────────────────────────────────────────────────────────────────────
# Socket threads
# ─────────────────────────────────────────────────────────────────────────────

def thread_9801(host: str, stop_event: threading.Event,
                send_queue: queue.Queue, ui_queue: queue.Queue) -> None:
    """Port 9801 — send frames from send_queue, block until ACK arrives for each.

    Flow per frame:
      1. GUI puts an encoded frame into send_queue
      2. This thread picks it up (get with 1s timeout so stop_event is checked regularly)
      3. Sends it with sendall()
      4. Blocks on recv_frame() until the full ACK arrives
      5. Puts the ACK in ui_queue for the GUI timer to display
    """
    while not stop_event.is_set():
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.connect((host, 9801))   # TCP three-way handshake with KiSoft
                s.settimeout(10)          # ACK must arrive within 10 s (spec requirement)
                ui_queue.put(('log', '9801 connected'))

                while not stop_event.is_set():
                    try:
                        frame = send_queue.get(timeout=1)  # wait up to 1 s for work
                        s.sendall(frame)                   # send the complete HIS frame
                        ack = recv_frame(s)                # block until ACK frame arrives
                        ui_queue.put(('ack', ack))         # hand result to GUI
                    except queue.Empty:
                        pass                               # nothing to send — loop again

        except Exception as e:
            ui_queue.put(('log', f'9801 error: {e}'))
            if not stop_event.is_set():
                time.sleep(3)                              # wait before reconnecting


def thread_9802(host: str, stop_event: threading.Event,
                ui_queue: queue.Queue) -> None:
    """Port 9802 — connect and wait. KiSoft pushes messages here; we ACK each one.

    Flow per received message:
      1. recv_frame() blocks until KiSoft sends something (32R, 3SC, 3HR, …)
      2. Payload is put in ui_queue for the GUI timer to display
      3. ACK is sent back immediately on the same socket (same port 9802)
      4. Back to blocking on recv_frame()

    There is no send_queue here — this thread never initiates communication.
    """
    while not stop_event.is_set():
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.connect((host, 9802))   # TCP handshake — then we just listen
                s.settimeout(120)         # 120 s = double heartbeat timeout (spec)
                ui_queue.put(('log', '9802 connected'))

                while not stop_event.is_set():
                    data      = recv_frame(s)          # BLOCKS — waiting for KiSoft
                    record_id = data[:3].decode()
                    ui_queue.put(('received', data))   # give to GUI
                    ack_id    = ACK_MAP_9802.get(record_id, '000')
                    s.sendall(encode_packet(ack_id + '00'))  # ACK on same socket

        except Exception as e:
            ui_queue.put(('log', f'9802 error: {e}'))
            if not stop_event.is_set():
                time.sleep(3)


# ─────────────────────────────────────────────────────────────────────────────
# GUI bridge
# ─────────────────────────────────────────────────────────────────────────────

def drain_ui_queue(ui_queue: queue.Queue, on_received, on_log) -> None:
    """Drain all pending items from ui_queue.

    Called by a ui.timer(0.1) inside NiceGUI — never call from a thread directly.

    ui_queue item types:
      ('received', bytes)  — message received on port 9802
      ('ack',      bytes)  — ACK received on port 9801 after a send
      ('log',      str)    — connection status / error text
    """
    while True:
        try:
            kind, payload = ui_queue.get_nowait()
        except queue.Empty:
            break
        try:
            if kind in ('received', 'ack'):
                on_received(format_received(payload))
            elif kind == 'log':
                on_log(payload)
        except Exception as exc:
            on_log(f'display error: {exc}')


# ─────────────────────────────────────────────────────────────────────────────
# Lifecycle
# ─────────────────────────────────────────────────────────────────────────────

def start_connections(host: str, ui_queue: queue.Queue):
    """Start both socket threads. Returns (stop_event, send_queue).

    The GUI keeps both handles:
      stop_event  → pass to stop_connections() on Disconnect
      send_queue  → put encode_packet(...) frames here to send on port 9801
    """
    stop_event = threading.Event()
    send_queue = queue.Queue()

    threading.Thread(
        target=thread_9801,
        args=(host, stop_event, send_queue, ui_queue),
        daemon=True,
        name='his-9801',
    ).start()

    threading.Thread(
        target=thread_9802,
        args=(host, stop_event, ui_queue),
        daemon=True,
        name='his-9802',
    ).start()

    return stop_event, send_queue


def stop_connections(stop_event: threading.Event) -> None:
    """Signal both threads to exit on their next loop iteration."""
    stop_event.set()
