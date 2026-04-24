# COHEN Guatemala – KiSoft One Host Interface Specification (HIS)
## Context for Claude Code

This project implements the **Host Interface System** between **J.I. COHEN Guatemala** (Host)
and **KNAPP KiSoft One** (Warehouse Management System) via **TCP/IP Sockets**.

---

## Architecture Overview

- **KiSoft One** = TCP/IP **Server** (listens)
- **Host (our app)** = TCP/IP **Client** (connects and reconnects on failure)
- **Character encoding**: UTF-8
- **Two channels**:
  - Port **9801**: Host → KiSoftOne (we send, they respond)
  - Port **9802**: KiSoftOne → Host (they send, we respond)
- Communication is **synchronous**: each message must be acknowledged before sending the next

---

## Packet (Frame) Structure

Every message is wrapped in a frame:

```
[LF (1 byte)][byte_count (5 bytes, e.g. "00012")][data][CR (1 byte)]
```

- `LF` = Line Feed = `\n` = byte `0x0A`
- `CR` = Carriage Return = `\r` = byte `0x0D`
- `byte_count` = total bytes of (byte_count field itself + data) — 5 digits, zero-padded
  - Formula: `byte_count = len(byte_count_field) + len(data)` = `5 + len(data)`
- Data = the record identifier + field values

**Example packet encoding:**
```python
def encode_packet(data: str) -> bytes:
    data_bytes = data.encode('utf-8')
    byte_count = 5 + len(data_bytes)          # 5 = len of the count field itself
    count_str = f"{byte_count:05d}"
    return b'\n' + count_str.encode() + data_bytes + b'\r'

def decode_packet(raw: bytes) -> str:
    # raw starts with \n, then 5-byte count, then data, then \r
    data = raw[6:-1]                          # skip LF + 5 count bytes + CR
    return data.decode('utf-8')
```

---

## Record (Message) Structure

Each data record consists of:
1. **Record identifier** (3 chars) — always first
2. **Fields**: each field has: `[2-char length prefix][value padded to that length]`
3. Fields with identifier chars (1 char tag) prefix their length/value group

**Padding rules:**
- Alphanumeric fields: pad with trailing spaces `" "`
- Numeric fields: pad with leading zeros `"0"`
- Empty date fields: use `"0"` (not spaces)

**Loops**: some fields repeat — marked by `LOOP START` / `LOOP END` in the spec.

---

## Connection & Protocol Rules

1. **Client (Host) must reconnect** if connection drops — it is always responsible for reconnection
2. **Synchronous**: wait for status message (ACK) before sending next record
3. **Heartbeat (every 60 seconds of silence)**:
   - Host sends `1HR` on port 9801 if no data sent for 60s
   - KiSoft sends `3HR` on port 9802 if no data sent for 60s
   - If no heartbeat ACK within timeout → disconnect and reconnect
   - Double timeout (120s): KiSoft closes port → Host must reconnect
4. **Status message timeout**: 10 seconds — if no status received, disconnect
5. Status messages (ACKs) must be sent on the **same port** as the received record

---

## Status / ACK Message Format

When Host receives a record from KiSoft, it must reply with a status message.
When Host sends a record, KiSoft replies with a status message.

Status format:
```
[record_id (3 chars)][status_code (2 chars)]
```

Status `"00"` = OK. Any other value = error.

**Frame validation errors** (KiSoft → Host):
- `"000" + "10"` = byte count error
- `"000" + "11"` = data format error
- `"2XX" + "91"` = invalid record identifier (XX = received ID's last 2 chars)

---

## Message Reference Table

### Host → KiSoftOne (Port 9801)

| Record ID | Description | ACK ID |
|-----------|-------------|--------|
| `1HR` | Heartbeat | `2HR` |
| `140` | Article master data — recreate all | `240` |
| `141` | Article master data — partial update | `241` |
| `149` | End of article master data transmission | `249` |
| `14N` | New article master data record | `24N` |
| `14D` | Delete article master data | `24D` |
| `150` | Partner master data — recreate all | `250` |
| `151` | Partner master data — partial update | `251` |
| `159` | End of partner master data | `259` |
| `15N` | New partner master data | `25N` |
| `15D` | Delete partner master data | `25D` |
| `160` | Theoretical route master — recreate all | `260` |
| `161` | Theoretical route master — partial update | `261` |
| `169` | End of theoretical route master | `269` |
| `16N` | New theoretical route | `26N` |
| `16D` | Delete theoretical route | `26D` |
| `12N` | New order data (inbound delivery / outbound order) | `22N` |
| `12D` | Delete order data | `22D` |
| `12U` | Update order data | `22U` |
| `1IA` | Inventory request | `2IA` |
| `1RR` | Real-time inventory view request | `2RR` |
| `1UN` | Storage unit available | `2UN` |
| `1UU` | Modify storage unit | `2UU` |
| `1UD` | Delete storage unit | `2UD` |
| `1SL` | Block/unblock stock | `2SL` |

### KiSoftOne → Host (Port 9802)

| Record ID | Description | ACK ID |
|-----------|-------------|--------|
| `3HR` | Heartbeat | `4HR` |
| `32R` | Order response message | `42R` |
| `3IR` | Inventory request response | `4IR` |
| `3RR` | Real-time inventory view ready (file via SFTP) | `4RR` |
| `3SC` | Stock adjustment | `4SC` |
| `3UE` | Storage unit empty | `4UE` |
| `3UU` | Stock change response | `4UU` |
| `3IS` | Real-time inventory snapshot (file content) | — |

---

## Key Message Structures

### Heartbeat — Host → KiSoft (`1HR`)
```
Record: "1HR"
```
Just the 3-char identifier, no additional fields.

ACK from KiSoft:
```
Record: "2HR"
Status: "00" = OK, "99" = internal error
```

### New Article Master Data (`14N`) — Key Fields
```
14N
[02][03] station_number (001-004, 010, 011, 061, 065, 199)
[optional shelf system, rack, module, channel, level fields]
L [16] client [12] article_number [04] pack_size [00]reserved
Y [02] ejection_number (10-80)
M [04] max_quantity (0001-9999)
D [04] length_mm [04] width_mm [04] height_mm [00]
G [06] weight_tenth_grams (000001-300000)
B [count] [20] barcode × N
K [40] article_name [12] geocode
S [04] min_stock [04] max_stock
F [count] [17] characteristic × N  (e.g. "ROBOT_TREATABLE", "COOLING_REQUIRED", "CONTROLLED", "UNMARKED")
E [count] [02] property × N  (01=lot required, 02=expiry required, 03=serial required)
T [03] replenishment_station [12] replenishment_geocode
```

### New Inbound Order (`12N`) — Inbound delivery
```
12N
[16] client [12] order_number [04] sheet_number (0000=delivery, 0001=transport)
T [02] order_type (01-99)
D [08] load_carrier_code
K [count] [03] destination_station × N
b [count_lines]
  [00/20] line_ref [03] station [12] article [04] pack_size [08] stock_type
  [00/20] lot [00/08] expiry_date [00] reservation_code [04] quantity [01] stock_quality
  [media] [carrier_code] [slot] [block_status] [max quantities...]
```

### New Outbound Order (`12N`) — Outbound delivery
```
12N
[16] client [12] order_number [04] sheet_number (0000)
T [02] order_type (01=pick, 10=delivery, 35=withdrawal, 36=full_carton_dispatch)
C [10] load_carrier_type  (LARGE, CARTON)
E [12] partner_number
F [08] route_number
S [lines] text_lines
U [03] priority (000-999)
O [count] control_params (0001=check carrier, 0012=strap, 9005=private, 9006=mark, 9007=verify)
Z [count_lines]
  [12] article_number [08] stock_type [04] quantity [00/99] processing_note
```

### Order Response (`32R`) — KiSoft → Host
```
32R
[16] client [12] order_number [04] sheet_number
T [02] order_type
f [04] original_sheet (if additional box)
A [04] highest_sheet [00]
B [03] start_station
C [10] carrier_type
D [08] carrier_code
E [12] partner_number
G [05] dispatch_ramp
s [14] start_time (YYYYMMDDhhmmss)
e [14] end_time
t [03] last_scan_station [14] scan_time [01] scan_state (0=pass, 1=diverted)
O [count] order_states  (0000=created, 0001=started, 0002=completed, 0003=cancelled_gui, 0004=cancelled_host, 0005=timeout, 0010=last_carrier)
Z [count_lines] processed_lines  (each line has: article, pack_size, stock_type, lot, expiry, qty, quality, line_state, operator, timestamp...)
b [count_lines] storage_lines  (article, lot, expiry, qty, quality, carrier_code, slot, line_state...)
```

### Stock Adjustment (`3SC`) — KiSoft → Host
```
3SC
[14] correction_number (SC00000001-SC99999999)
K [03] station_number
T [02] message_type (41=block_added, 42=block_removed, 43=stock_corrected, 40=received, 45=reassigned)
B [06] storage_unit_code [00/02] slot
L [16] client [12] article [04] pack_size [08] stock_type
C [20] lot
E [08] expiry_date
F [01] stock_quality (1=new, 2=return)
v [20] block_reason_token
V [count] block_reason_list
r [15] reason [00] additional_reason
t [14] timestamp
U [08] warehouse_operator
X [01+04] sign+difference (+0001 or -0001)
```

### Inventory Request (`1IA`) — Host → KiSoft
```
1IA
[16] client [07] inventory_request_number [00]
Y [count_filters]
  [00/03] station [00] geocode [00/12] article [00/04] pack_size
  [00/08] stock_type [00/20] lot [00/08] expiry [00] reservation [00/08] carrier [00/02] slot
```

---

## Order Types

| Value | Meaning |
|-------|---------|
| 01 | Pick order (outbound) |
| 02 | Transport (Open Shuttle) |
| 03 | Inbound storage (goods-in) |
| 04 | Bulk goods-in / decanting |
| 05 | Open goods-in |
| 06 | Goods-add |
| 07 | Goods-add by pallet |
| 10 | Outbound delivery |
| 15 | Internal transport |
| 24 | Empty carrier request |
| 35 | Withdrawal |
| 36 | Full carton to dispatch |

---

## Stock Types

| Value | Meaning |
|-------|---------|
| STANDARD | New item |
| B6 | Not yet available for sale in SAP |
| QQ | Quality control hold |
| 2F | Near-expiry (< 6 months) |
| 1E | Promotional / special clients |
| 1X | Wildcard_1 |
| 1Z | Wildcard_2 |

---

## Client (Mandante) Codes

| Code | Client Name |
|------|-------------|
| DEFAULT | — |
| A1201 | JILOH |
| A1301 | AJISA |
| A1401 | ALISE |
| A3601 | ELECTRON SERVICES |
| A4101 | LE Recurso Corporativo |
| A5101 | SOLIN |
| 6111 | YVES ROCHER |

---

## Load Carrier Types (C field)

| Type | Description |
|------|-------------|
| LARGE | Large plastic carrier (conveyor picking) |
| CARTON | Cardboard carrier (conveyor picking) |
| FULL | OSR 1/1 storage unit (1 slot) |
| HALF | OSR 2/2 storage unit (2 slots) |
| QUARTER | OSR 4/4 storage unit (4 slots) |
| EIGHTH | OSR 8/8 storage unit (8 slots) |

---

## Station Numbers

| Station | Number | Description |
|---------|--------|-------------|
| CBS001 | 001-004 | Manual stations |
| M010, M011 | 010, 011 | Controlled/refrigerated items |
| BULK001 | 061 | Full carton station |
| OSR Shuttle | 065 | Automated storage/retrieval |
| Full carton | 199 | Full carton area |
| ST003_PUT | 017 | Non-reusable items destination |
| OS001 | 190 | Output station |
| CS001 | 091 | Check station 1 |
| CS002 | 092 | Check station 2 |
| GPA001 | 095 | Marking station |
| PA002 | 027 | Verification station |
| Flow rack L | 244 | SDA left (replenishment) |
| Flow rack R | 245 | SDA right (replenishment) |
| DIS001 | 183 | Dispatch ramp 1 |
| DIS002 | 184 | Dispatch ramp 2 |

---

## Order Line States

| Code | Meaning |
|------|---------|
| 01 | Not yet picked |
| 30 | Processed correctly |
| 50 | Technical error (quantity may be wrong) |
| 51 | Quantity mismatch |
| 52 | Corrected at control station |
| 53 | Unknown article |
| 54 | Requested quantity = 0 |
| 55 | Quantity > max quantity |
| 56 | Carrier full |
| 57 | Article "OFF SALE" |
| 58 | Article "OUT OF STOCK" |
| 59 | Article blocked |
| 60 | VOLUMETRIX: no suitable pack size |
| 65 | Vision belt read error |
| 93 | Line deleted by Host |

---

## Block/Unblock Reasons

| Token | Description |
|-------|-------------|
| DEFAULT | Default block reason |
| HOST | Host-imposed block |
| EXPIRED | Stock past expiry |
| TIME_TO_EXPIRE | Below minimum days before expiry |
| QS_REQUIRED | Quality control required |

---

## SFTP Access (Print Data & Inventory Snapshot)

**Print data** (Host → KiSoft):
- User: `sftpuser` / Password: `customer`
- File naming: `{order_number}.{sheet}.{doc_type}.{extra}.{page_num}`
  - doc_type 001 = delivery note (PDF), 008 = address label (ZPL)
- After all pages, send empty `.end` file

**Inventory snapshot** (KiSoft → Host):
- User: `customer_osr` / Password: `customer`
- File: `InventorySnapshot_065.f`
- Trigger: send `1RR` with station `065` and type `31`; KiSoft replies `3RR` when file is ready

---

## Control Parameters (O field in outbound orders)

| Code | Meaning |
|------|---------|
| 0001 | Check carrier |
| 0012 | Strap carrier |
| 9005 | Private (PA001) |
| 9006 | Marking (GPA001) |
| 9007 | Verification (PA002) |

---

## Remote Testing

- KNAPP public IP: `89.207.120.100`
- Ports: 9801 and 9802
- Ports 1-1024 are forbidden

---

## Python Implementation Notes

### Suggested file structure
```
his_client/
  __init__.py
  protocol.py      # packet encode/decode, field parsing
  connection.py    # TCP client, reconnect logic, heartbeat
  messages.py      # message builder/parser for each record type
  client.py        # high-level API (send_article_master, send_order, etc.)
  server_mock.py   # mock KiSoft server for testing
main.py
```

### Core encoding logic
```python
import struct, socket, threading, time

def encode_packet(data: str) -> bytes:
    body = data.encode('utf-8')
    byte_count = 5 + len(body)
    return b'\n' + f"{byte_count:05d}".encode() + body + b'\r'

def decode_packet(raw: bytes) -> str:
    return raw[6:-1].decode('utf-8')

def pad_alpha(value: str, length: int) -> str:
    return value.ljust(length)[:length]

def pad_num(value: int, length: int) -> str:
    return str(value).zfill(length)[:length]

def field(identifier: str, value: str, declared_length: int) -> str:
    return identifier + f"{declared_length:02d}" + value

def build_heartbeat_host() -> str:
    return "1HR"

def build_heartbeat_ack_host() -> str:
    return "2HR" + "00"
```

### Connection requirements
- Two persistent TCP connections (one per channel)
- Heartbeat thread: send `1HR` / `3HR` every 60s of silence
- If status not received in 10s → close and reconnect
- If double heartbeat timeout (120s) → KiSoft closes, we must reconnect
- Client must always reconnect — never wait for the server to initiate

---

## Message Structures — 15N and 16N (complete field specs)

### New Partner Master Data (`15N`)

| Bytes | Description | Content / Range |
|-------|-------------|-----------------|
| 3 | Record identifier | `15N` |
| 2 | Length of client (mandante) | `16` |
| 2 | Length of partner number | `12` |
| 16 | Client (mandante) | 0–9, A–Z, a–z, `-`, `_` |
| 12 | Partner number | 0–9, A–Z, a–z, `-`, `_` |
| 1 | Company identifier | `C` |
| 2 | Company length | `30` |
| 30 | Company name | TEXT |
| 1 | Treatment identifier | `A` |
| 2 | Treatment length | `30` |
| 30 | Treatment / title | TEXT |
| 1 | Last name identifier | `N` |
| 2 | Last name length | `30` |
| 30 | Last name | TEXT |
| 1 | First name identifier | `M` |
| 2 | First name length | `30` |
| 30 | First name | TEXT |
| 1 | Street identifier | `S` |
| 2 | Street length | `30` |
| 30 | Street | TEXT |
| 1 | City identifier | `P` |
| 2 | City length | `30` |
| 30 | City / place | TEXT |
| 1 | ZIP identifier | `Z` |
| 2 | ZIP length | `06` |
| 6 | ZIP code | TEXT |
| 1 | Region identifier | `R` |
| 2 | Region length | `30` |
| 30 | Region | TEXT |
| 1 | Country code identifier | `O` |
| 2 | Country code length | `02` |
| 2 | Country code | ISO 3166 ALPHA-2 |
| 1 | Email identifier | `E` |
| 2 | Email length | `30` |
| 30 | Email | TEXT |
| 1 | Phone identifier | `L` |
| 2 | Phone length | `30` |
| 30 | Phone number | TEXT |

### New Theoretical Route (`16N`)

| Bytes | Description | Content / Range |
|-------|-------------|-----------------|
| 3 | Record identifier | `16N` |
| 2 | Length of client | `16` |
| 2 | Length of route number | `08` |
| 16 | Client (mandante) | 0–9, A–Z, a–z, `-`, `_` |
| 8 | Route number | 0–9, A–Z, a–z, `-`, `_` |
| 1 | Departure time identifier | `Z` |
| 2 | Length of departure time | `06` |
| 2 | Length of availability time | `06` |
| 2 | Length of day of week | `00` (or `03` if present) |
| 6 | Departure time | `HHmmss` |
| 6 | Availability time | `HHmmss` |
| 0–3 | Day of week (optional) | `MON` `TUE` `WED` `THU` `FRI` `SAT` `SUN` |
| 1 | Ramp identifier | `R` |
| 2 | Number of ramps | `01`–`20` |
| 2 | Length of each ramp number | `05` |
| LOOP | Ramp numbers (× count) | `00001`–`00010` (DIS001), `00021`–`00025` (DIS002) |

---

## Connection Architecture — Key Decisions

### Socket library choice: `socket` + `threading` (NOT asyncio)
- **Reason**: simpler to reason about; no coroutines, no event loop concerns
- NiceGUI runs on asyncio internally but threads work fine alongside it via the queue bridge

### Two persistent daemon threads, one per port
```
thread_9801  →  port 9801: send frames from send_queue, recv ACK (synchronous)
thread_9802  →  port 9802: connect and wait, recv 32R/3SC/3HR, send ACK immediately
```

### Port 9801 — synchronous request-response
Client sends a frame, then **blocks on the same socket** waiting for the ACK:
```python
s.sendall(encode_packet("12N..."))
ack = recv_frame(s)   # blocks until 22N arrives
```
The thread drains `send_queue` one frame at a time. No next frame is sent until the ACK is received.

### Port 9802 — connect and wait
Client connects but does **not send** proactively. It sits in a blocking `recv_frame()` loop. When KiSoft pushes a message (32R, 3SC, 3HR…), the thread:
1. Receives the complete frame
2. Puts it in `ui_queue` (for the UI to display)
3. Immediately sends the ACK back on the **same socket** (same port 9802)

### Thread → UI bridge: `queue.Queue` + `ui.timer`
Threads never touch UI elements directly. Instead:
- Threads put `('received', data)` or `('log', text)` tuples into `ui_queue`
- A `ui.timer(interval=0.1)` runs inside NiceGUI, drains the queue, calls `append_received()`
- This avoids all thread-safety issues with NiceGUI's asyncio event loop

### `recv_frame()` — reads exactly one complete frame
Never use `s.recv(N)` directly — TCP can fragment. Always use:
```python
def recv_frame(s):
    def read(n):
        buf = b''
        while len(buf) < n:
            chunk = s.recv(n - len(buf))
            if not chunk: raise ConnectionError('disconnected')
            buf += chunk
        return buf
    read(1)                      # LF
    count = int(read(5))         # byte count
    data  = read(count - 5)      # payload
    read(1)                      # CR
    return data                  # raw payload bytes
```

### Auto-reconnect
Each thread loops with `while not stop_event.is_set()`. On any exception it logs the error to `ui_queue` and sleeps 3 seconds before reconnecting. The `stop_event` (a `threading.Event`) is set by the Disconnect button.

### ACK map for port 9802 (auto-sent by thread)
```python
ACK_MAP = {
    '3HR': '4HR', '32R': '42R', '3SC': '4SC',
    '3UE': '4UE', '3UU': '4UU', '3IR': '4IR', '3RR': '4RR',
}
```

---

## Project Build Plan & Current Status

### Approach
Build the simulator **block by block**: client GUI → TCP connection logic → server mock.

### Tech stack
- **Language**: Python 3.11 (venv at `.pro1/`)
- **GUI**: NiceGUI 2.x/3.x — web-based UI served on `localhost:8083`
- **GUI style**: dark mode, NiceGUI
- **Sockets**: stdlib `socket` + `threading`
- Run: `.pro1/Scripts/python client/client_gui.py` → open `http://localhost:8083`

---

### File structure (current)

```
wcspro1/
  classes/
    __init__.py          # exports all message/transmission classes
    protocol.py          # encode_packet, pad_alpha, pad_num
    message.py           # base Message class (record_id + data → packet + display)
    transmission.py      # base Transmission class (open + data + close)
    article.py           # ArticleMessage (14N), ArticleTransmission (140/141→14N→149)
    partner.py           # PartnerMessage (15N), PartnerTransmission (150/151→15N→159)
    route.py             # RouteMessage (16N), RouteTransmission (160/161→16N→169)
    order.py             # OrderMessage (12N) — standalone, no transmission wrapper
  client/
    client_gui.py        # main GUI (current)
    client_gui_v2.py     # backup before Orders tab was added
    client_gui_backup.py # earlier backup before class refactor
  CLAUDE.md
```

---

### `classes/` architecture decisions

- **Entity-specific classes** inherit from base `Message` / `Transmission`
  - Why: adding a field to Articles means editing only `article.py`, not a shared builder
- **Base `Message`**: takes `record_id` + `data` string → builds packet bytes → `display()` returns symbolic + hex
- **Base `Transmission`**: holds open/data/close `Message` objects → `display()` joins all three
- **Open/close records** (140, 150, 160…): `data = record_id` only — produces `COUNT = 00008` always
- **`OrderMessage` (12N)**: standalone — no Transmission wrapper
  - `order_type` in `{'02','04','05'}` → inbound with `b`-lines
  - `order_type` in `{'10','35','36'}` → outbound with `Z`-lines
  - Scope: only these 6 order types implemented

---

### `client/client_gui.py` — current state

**Left panel — 4 tabs:**

| Tab | Record | Mode toggle | Dynamic lists |
|-----|--------|-------------|---------------|
| Articles (14N) | 14N | Recreate / Partial | Barcodes (add/remove) |
| Partners (15N) | 15N | Recreate / Partial | — |
| Routes (16N) | 16N | Recreate / Partial | Ramps (add/remove, max 20) |
| Orders (12N) | 12N | — (standalone) | Dest stations, b-lines or Z-lines |

- Orders tab uses `@ui.refreshable direction_section()` that rebuilds when order type changes
- Send Message on Articles/Partners/Routes → shows full Transmission (open + data + close)
- Send Message on Orders → shows single 12N packet only

**Right panel — vertically split (58% / 42%):**
- **Top: Message Preview** — live preview updates on every field change, Copy + Clear buttons
- **Bottom: Received Messages** — for incoming frames from port 9802; `append_received(text)` prepends newest with timestamp and separator line; Clear button

**UI patterns used:**
- `@ui.refreshable` for dynamic lists (barcodes, ramps, direction_section)
- Direct element reference (`ctx['preview_el']`, `el.value = text; el.update()`) for preview — avoids event-loop timing issues with refreshable
- `bind_input / bind_number / bind_select` helpers update state dict + call `refresh_preview()` on every change
- `ctx['tab']` tracks active tab so `refresh_preview()` knows which message to build

---

### What comes next

1. **`client/connection.py`** — socket layer
   - `recv_frame(s)` shared helper
   - `thread_9801(host, stop_event, send_queue, ui_queue)`
   - `thread_9802(host, stop_event, ui_queue)`
   - `start_connections(host)` / `stop_connections()`

2. **Wire into GUI**
   - Connect button → `start_connections(host)`; start `ui.timer` to drain `ui_queue`
   - Send Message buttons → put encoded frame in `send_queue` instead of just showing preview
   - Header shows connection status (connected / disconnected / error) per port

3. **`server/server_mock.py`** — KiSoft One simulator
   - Listens on ports 9801 and 9802
   - Receives 12N on 9801, sends 22N ACK, then sends scenario's 32R on 9802
   - **Scenario approach**: static Python dicts, selected in mock GUI before client sends
   - Example scenario: "Three articles — one loading unit" → 32R with 3 Z-lines, state 30, one carrier code
   - Heartbeat: leave for after basic send/receive is working
