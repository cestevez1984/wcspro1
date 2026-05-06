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
| OS001 | 190 | Output station (always start_station in 32R) |
| CS001 | 091 | CBS check station (SDA) |
| CS002 | 092 | OSR check station |
| RL002 | 086 | Manual pick consolidation point |
| FCS001 | 093 | Final control station |
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
- **CRITICAL**: drain logic must separate queue-get from processing into two separate try/except
  blocks. A single combined try/except will silently stop draining if a non-`queue.Empty`
  exception is raised during processing, leaving the rest of the queue unread.

### NiceGUI shared state pitfalls
- **Module-level Python state is NOT shared** between NiceGUI event callbacks and background
  threads, even within the same PID. NiceGUI re-executes module-level layout code in its own
  internal context; changes made there are invisible to daemon threads started before `ui.run()`.
- **Workaround**: use a file, a socket, or `multiprocessing.Manager` for any state that must
  be read by both NiceGUI callbacks and background threads. In this project: `active_scenario.txt`.
- **`@ui.refreshable` rule**: never place interactive widgets (especially `ui.select` with
  `on_change`) inside a `@ui.refreshable` function. The widget is destroyed and recreated on
  `.refresh()`, which can fire while the widget's own callback is still executing, breaking
  the event chain. Place the widget outside the refreshable; put only the display-only content
  inside it.

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

## Project Status & File Reference

### How to run

```bash
# Terminal 1 — mock server (KiSoft One simulator)
.pro1/Scripts/python server/server_mock.py    →  http://localhost:8084

# Terminal 2 — client simulator (Host)
.pro1/Scripts/python client/client_gui.py     →  http://localhost:8083
```

Default host in client is `127.0.0.1` (localhost for local testing).
For KNAPP's real system use `89.207.120.100`.

---

### Confirmed station assignments (COHEN Guatemala physical layout)

| Station | Number | Notes |
|---------|--------|-------|
| Start station | 190 | **Always** the `start_station` (segment B) in every 32R |
| CBS (SDA) | 091 | Conveyor belt station — check station SDA |
| OSR | 092 | Automated storage/retrieval check station |
| RL002 | 086 | Manual pick consolidation — **all manual station picks (001-004) produce ONE 32R here**; geocodes identify racks |
| FCS001 | 093 | Final control station — **always the last 32R** in every outbound order; carries `['0002','0010']`; consolidates all Z-lines except cooling, controlled, and bulk |
| Bulk | 199 | Full-carton area — **always a separate loading unit**; ramp 00025; **never included in FCS001 Z-lines** |
| Manual M001 | 001 | Has two racks — geocode required to identify rack |
| Manual M002 | 002 | Has two racks — geocode required |
| Manual M003 | 003 | Has two racks — geocode required |
| Manual M004 | 004 | Has two racks — geocode required |
| Controlled | 010 | Controlled substance station — **isolated**: own 32R, **not included** in FCS001 Z-lines |
| Cooling | 011 | Refrigerated items station — **isolated**: own 32R, **not included** in FCS001 Z-lines |

**Carrier codes**: HU00001 – HU00999 (format for outbound loading units), HU00010+ for inbound receiving units

**OSR inbound storage units**: SU00001–SU00999 (carrier_code in 32R responses for inbound)

**Dispatch ramps**: `00025` for Bulk (199), `00001`–`00010` for all other stations

**Default test values**: client = `A1301` (AJISA), order_number = `TEST001`

---

### Complete file structure

```
wcspro1/
  classes/
    __init__.py           # exports everything below
    protocol.py           # encode_packet, pad_alpha, pad_num
    message.py            # base Message class
    transmission.py       # base Transmission class (open + data + close)
    article.py            # ArticleMessage (14N), ArticleTransmission (140/141→14N→149)
    partner.py            # PartnerMessage (15N), PartnerTransmission (150/151→15N→159)
    route.py              # RouteMessage (16N), RouteTransmission (160/161→16N→169)
    order.py              # OrderMessage (12N) — standalone, no wrapper
    order_response.py     # OrderResponseMessage (32R) + parse_12n()
    connection.py         # recv_frame, thread_9801, thread_9802,
                          # start_connections, stop_connections,
                          # drain_ui_queue, format_received
  client/
    client_gui.py         # main client GUI  (port 8083)
    client_gui_v2.py      # backup before Orders tab
    client_gui_backup.py  # backup before class refactor
  server/
    __init__.py
    scenarios.py             # static scenario definitions (SCENARIOS list)
    server_mock.py           # KiSoft One mock server GUI  (port 8084)
    active_scenario.txt      # persists selected scenario ID across NiceGUI re-initializations
  CLAUDE.md
```

---

### `classes/` architecture decisions

- **All non-GUI logic lives in `classes/`** — including socket/connection code
- **Entity-specific classes** inherit from base `Message` / `Transmission`
  - Adding a field to one entity → edit only that entity's file
- **Base `Message`**: `record_id` + `data` string → `packet` bytes + `display()` (symbolic only)
- **Base `Transmission`**: holds `open_msg / data_msg / close_msg` → `display()` joins all three
- **Open/close records** (140, 150, 160…): `data = record_id` only → `COUNT = 00008` always
- **`OrderMessage` (12N)**: standalone — no Transmission wrapper
  - `order_type` in `{'02','04','05'}` → inbound → `b`-lines
  - `order_type` in `{'10','35','36'}` → outbound → `Z`-lines
- **`OrderResponseMessage` (32R)**: built from `order_info` dict + one `response` dict from a scenario
  - `parse_12n(data: bytes) → dict` extracts client/order_number/sheet/type from received 12N bytes
  - Z-line wire order: article(12) · pack_size(4) · stock_type(8) · lot(00 or 20) · expiry(00) · quantity(4) · quality(1) · line_state(2) · geocode(00 or 12)
  - lot and geocode use variable-length encoding: `'00'` when empty, `'20'`/`'12'` + value when present
  - Both always emitted (even as `'00'`) so the parser has a fixed-offset contract

---

### `client/client_gui.py` — current state

**Left panel — 5 tabs:**

| Tab | Record | Mode toggle | Dynamic lists |
|-----|--------|-------------|---------------|
| Articles (14N) | 14N | Recreate / Partial | Barcodes (add/remove) |
| Partners (15N) | 15N | Recreate / Partial | — |
| Routes (16N) | 16N | Recreate / Partial | Ramps (add/remove, max 20) |
| Orders (12N) | 12N | — (standalone) | Dest stations, b-lines or Z-lines |
| Scenarios | 12N | — | Scenario picker, auto-builds 12N from scenario |

- Scenarios tab: dropdown uses `[OUT]`/`[IN]` prefix to distinguish outbound vs inbound scenarios
- Inbound scenarios: **Send Matching Order** sends one 12N per loading unit (N packets total)
- Outbound scenarios: **Send Matching Order** sends one 12N
- Default client in Scenarios tab: `A1301`

**Right panel — vertically split (38% / 62%):**
- **Top: Message Preview** (38%) — shows **friendly field-by-field breakdown** above the raw frame
- **Bottom: Received Messages** (62%) — shows ACKs and pushed messages with `← PORT 9801/9802` tag;
  `append_received(text, port)` prepends newest with timestamp + port tag + separator
  - Copy uses `ui.run_javascript(f'navigator.clipboard.writeText(...)')` — preserves all formatting

**Header — Connect / Disconnect toggle:**
- Connect → calls `start_connections(host, ui_queue)`, stores `stop_event` + `send_queue` in `ctx`
- Disconnect → calls `stop_connections(stop_event)`, clears ctx
- Both buttons exist in DOM; one hidden at a time via `.classes('hidden')`

**Connection wiring:**
- `ui_queue: queue.Queue` at module level — shared between GUI and socket threads
- `ui.timer(0.1, drain_ui_queue(...))` drains 10×/s into `append_received()`
- `_enqueue(*packets)` puts frames into `ctx['send_queue']` only when connected

**UI patterns:**
- `@ui.refreshable` for dynamic lists (barcodes, ramps, direction_section, scenario_tab_content)
- Direct element reference (`ctx['preview_el']`, `el.value = text; el.update()`) for preview
- `bind_input / bind_number / bind_select` helpers: update state dict + call `refresh_preview()`

**Friendly preview formatters:**
- `_friendly_article(s)` → human-readable 14N breakdown
- `_friendly_partner(s)` → human-readable 15N breakdown
- `_friendly_route(s)` → human-readable 16N breakdown
- `_friendly_order(s, title_suffix='')` → human-readable 12N breakdown (inbound or outbound)
- `_preview_text(friendly, msg)` → joins friendly text + `·` divider + `msg.display()`
- All `send_*` and `refresh_preview` functions use `_preview_text(friendly, msg)`
- **CRITICAL ordering rule**: `_initial_preview` must be computed **after** all helper functions are
  defined (after `_preview_text`). Computing it at the wrong point causes a `NameError` caught
  silently by try/except, leaving the panel showing an error string instead of the article preview.

**Inbound multi-packet preview:**
- When sending an inbound scenario with N loading units, the preview shows N blocks separated by
  `═══` dividers, each with `[1/N] HU00010` suffix so the user can see each 12N clearly.

---

### `server/server_mock.py` — current state

**Two listener threads** (server-side: bind/listen/accept, not connect):

```
server_thread_9801:
  bind(9801) → accept client → recv any HIS frame → send ACK
  if 12N outbound (order_type NOT in {'02','04','05'}): put order_info in trigger_queue immediately
  if 12N inbound  (order_type in {'02','04','05'}):     accumulate in _inbound_buffer;
                                                         trigger only when all LUs received

server_thread_9802:
  bind(9802) → accept client → wait on trigger_queue
  dequeue order_info → call _get_selected() at that moment (reads file)
  for each response in scenario: send 32R → recv 42R ACK
```

**`_inbound_buffer`** — module-level dict `{order_number: count_received}`. Single writer thread
(server_thread_9801) so no lock needed. Entry deleted after trigger fires.

**Inbound trigger detection** uses `order_type` from the parsed 12N, **not** `scenario.get('category')`.
Using the scenario category was wrong because the selected scenario might be outbound even when
the arriving 12N is inbound-typed.

```python
if order_type in ('02', '04', '05'):   # inbound
    key = order_info['order_number']
    expected = len(scenario.get('loading_units', [])) or 1
    _inbound_buffer[key] = _inbound_buffer.get(key, 0) + 1
    if _inbound_buffer[key] >= expected:
        trigger_queue.put(order_info)
        del _inbound_buffer[key]
else:                                   # outbound
    trigger_queue.put(order_info)
```

**`trigger_queue`** carries **only `order_info`** (not the scenario). Scenario is resolved at
processing time by `_get_selected()` reading `active_scenario.txt` — always gets the freshest selection.

**`highest_sheet`** is computed as `max(r.get('sheet', 1) for r in responses)` — the number of
distinct loading units. This is NOT `len(responses)` (which counts station scans, not carriers).

**`_get_active_id()` validation**: reads `active_scenario.txt`, checks the stored ID against
`{sc['id'] for sc in SCENARIOS}` — falls back to `SCENARIOS[0]['id']` if stale. Prevents
`ValueError: Invalid value` crash on server startup when scenarios are renamed.

**Reconnect safety in `server_thread_9802`:** on any send/recv exception: re-queue `order_info`,
then `break` to accept new client. Without re-queue the trigger was silently lost.

**Scenario persistence — `server/active_scenario.txt`:**
- NiceGUI re-executes module-level layout code in a context isolated from background threads.
  Module-level Python dict changes are invisible to the socket threads — even in the same PID.
- Fix: selection stored in `active_scenario.txt`. `_on_select` writes; `_get_selected()` reads.
- Initialized to `SCENARIOS[0]['id']` only if the file does not already exist.

**`format_received()` in `classes/connection.py`:**
- For `32R`: prepends a station/carrier banner extracted from fixed offsets before the raw frame:
  ```
  ═══════════════════════════════════════════════════
  ▶▶▶  HU00001  ·  STATION 091  —  CBS (SDA check station)  ◀◀◀
  ═══════════════════════════════════════════════════
  ```
  Carrier code from `s[77:85]`, last_scan_station from `s[130:133]`, label from `STATION_LABELS`.
- For non-32R messages: simpler banner `▶  record_id  OK/error_code`.
- Then shows `[LF]…[CR]` raw frame, then full field-by-field breakdown including lot + geocode + b-lines.
- `_parse_32r()` reads lot and geocode with variable-length tags (always present, even as `'00'`).

**`drain_ui_queue()` port detection:**
- Tuples from threads: `('received', data)` = from port 9802, `('ack', data)` = from port 9801.
- The drain function maps these to a port string and passes it to `on_received(text, port)`.
- `append_received(text, port)` adds `← PORT 9801` or `← PORT 9802` to the timestamp line.

---

### `server/scenarios.py` — scenario structure

Each outbound scenario has a `responses` list — **one entry per station scan event** (one 32R per entry).
Each inbound scenario has both `loading_units` (drives 12N messages) and `responses` (drives 32R).
The mock sends one `32R` per entry with 0.8s delay.

**CRITICAL — confirmed outbound 32R semantics:**
- One `32R` per station the carrier passes through (`last_scan_station` = that station)
- Multiple articles at the same station → multiple Z-lines in ONE 32R (not multiple 32Rs)
- Multiple stations → multiple `responses` entries, each a separate 32R
- `start_station` = always `'190'` (start station, segment B)
- `sheet` = loading unit number (HU00001=1, HU00002=2 …)
- `highest_sheet` = `max(sheet)` = total loading units for the order
- Bulk (199) always goes in a **separate** loading unit from everything else
- Manual stations (001-004) always consolidate into **one 32R** at RL002 (086) with geocodes per rack
- Cooling (011) and Controlled (010) each get their own isolated 32R, **never merged** into FCS001
- **FCS001 (093) is always the last `response` entry** in every outbound scenario; it carries
  `order_states=['0002','0010']` and consolidates all Z-lines from non-cooling/non-controlled/non-bulk stations
- First response: `order_states=['0001']`; intermediate: `[]`; last (FCS001): `['0002', '0010']`
- Single-response scenarios: `order_states=['0001', '0002', '0010']` (all in one, FCS001 only)

**Outbound response entry structure:**
```python
{
    'sheet':              1,          # loading unit number
    'carrier_type':       'LARGE',
    'carrier_code':       'HU00001',  # HU00001 – HU00999
    'start_station':      '190',      # always 190
    'last_scan_station':  '091',      # station that triggered this 32R
    'scan_state':         '1',        # 1=passed, 0=not passed
    'dispatch_ramp':      '00001',    # 00025 for Bulk; 00001-00010 for others
    'order_states':       ['0001'],
    'z_lines': [
        {
            'article':    'ARCBS01',
            'pack_size':  1,
            'stock_type': 'STANDARD',
            'lot':        'LTC001',       # '' for no lot
            'quantity':   3,
            'quality':    '1',
            'line_state': '30',
            'geocode':    '001XXXYYYZZZ', # '' for no geocode; required for manual stations
        },
    ],
}
```

**Inbound scenario structure:**
```python
{
    'id': 'in_101_osr_decanting',
    'category': 'Inbound',
    'loading_units': [             # one entry per 12N message sent by client
        {
            'carrier_code': 'HU00010',
            'b_lines': [
                {
                    'article': 'AROSR04', 'quantity': 10, 'pack_size': 1,
                    'stock_type': 'STANDARD', 'lot': 'LTC001', 'expiry': '20300101',
                    'station': '065', 'stock_quality': '1',
                },
            ],
        },
    ],
    'responses': [                 # one entry per 32R pushed by KiSoft on 9802
        {
            'sheet':             1,
            'carrier_code':      'SU00001',  # OSR storage unit code
            'carrier_type':      '',
            'last_scan_station': '065',
            'order_states':      ['0002'],
            'z_lines':           [],
            'b_lines': [         # items stored (mirror of what was received)
                {'article': 'AROSR04', 'quantity': 10, 'pack_size': 1,
                 'stock_type': 'STANDARD', 'lot': 'LTC001', 'expiry': '20300101',
                 'quality': '1', 'line_state': '30'},
            ],
        },
    ],
}
```

**Current scenarios (9 outbound + 1 inbound):**

| Code | Category | ID | 32R msgs | Carriers | Description |
|------|----------|----|----------|----------|-------------|
| 101 | OUT | `out_101_cbs_1art` | 2 | HU00001 | ARCBS01 from CBS (091) → FCS001 (093) |
| 102 | OUT | `out_102_cbs_osr_1carrier` | 3 | HU00001 | CBS (091) + OSR (092) → FCS001 (093) |
| 103 | OUT | `out_103_partial_oos` | 2 | HU00001 | ARCBS01 OK + ARCBS02 OOS (58) → FCS001 (093) |
| 104 | OUT | `out_104_3art_cbs` | 2 | HU00001 | 3 CBS articles → FCS001 (093) |
| 105 | OUT | `out_105_manual_osr` | 3 | HU00001 | Manual M001+M002 → RL002 (086) + OSR (092) → FCS001 (093) |
| 106 | OUT | `out_106_bulk_osr_2carriers` | 3 | HU00001+HU00002 | Bulk (199) → OSR (092) → FCS001 (093) |
| 107 | OUT | `out_107_mixed_2carriers` | 6 | HU00001+HU00002 | HU00001: Bulk (199); HU00002: CBS+OSR+Manual → FCS001 |
| 108 | OUT | `out_108_cooling` | 2 | HU00001 | Cooling station (011) only → FCS001 (093) |
| 109 | OUT | `out_109_controlled` | 2 | HU00001 | Controlled substance (010) only → FCS001 (093) |
| IN-101 | IN | `in_101_osr_decanting` | 3 | HU00010+HU00011 (recv) / SU00001-SU00003 (stored) | 2× 12N → 3× 32R storage confirmations |

**Pending scenarios to add:** physical inventory, replenishment, cancelled order, quantity mismatch,
heartbeat scenarios.

---

### End-to-end test flow

1. Start mock server → `http://localhost:8084` → select a scenario
2. Start client → `http://localhost:8083` → **Scenarios** tab
3. Set client=A1301, order_number=TEST001 → **Send Matching Order**
4. Mock 9801 receives 12N → sends 22N ACK → appears in Received Messages
5. Mock 9802 fires one 32R per response entry → each appears with station banner + field breakdown
6. Client 9802 auto-sends 42R ACK for each → mock logs it

---

### SAP/ABAP integration — discussion notes

A future Host client could be built several ways:

- **ABAP native TCP** (`CL_TCP_SOCKET` or `SOCKET` function group): doable, but port 9802 needs a
  blocking listener waiting for KiSoft pushes — this fights ABAP's synchronous dialog model.
  Would require a background job or RFC server for port 9802.
- **Java/.NET middleware (PI/PO or BTP Integration Suite)**: SAP posts IDocs/BAPIs, middleware
  translates to HIS. Clean separation but more moving parts.
- **RFC + Python (recommended)**: keep the Python client as the TCP layer, expose it via RFC or
  REST, call from ABAP. SAP stays in its lane; Python handles the async complexity already solved here.

---

### What comes next

1. **More scenarios** — physical inventory, replenishment, cancelled order, quantity mismatch
2. **Heartbeat** — `1HR` sent every 60s of silence on port 9801; mock sends `3HR` on 9802
3. **Connection status badges** — per-port indicators in client header (connected / error)
4. **Real KNAPP connection** — switch host to `89.207.120.100`, test against live system
5. **SAP client** — RFC+Python bridge when ready to integrate with ECC/S4

---

### Bugs fixed during development

| Bug | Root cause | Fix |
|-----|-----------|-----|
| `parse_12n` wrong client field | Offset `s[7:23]` should be `s[5:21]` — the `'16'` length tag is 2 chars, not 4 | Fixed in `classes/order_response.py` |
| 22N / 32R not appearing in client panel | `drain_ui_queue` used one try/except for both queue-get and processing — a display error silently stopped the drain loop | Split into two separate try/except blocks |
| Hex dump shown in preview and received panels | `Message.display()` and `format_received()` included raw hex | Removed; now symbolic only |
| Scenario selection always returned scenario 1 | NiceGUI re-executes layout code in a context isolated from background threads | Replaced module-level dict with `active_scenario.txt` |
| Stale scenario in trigger_queue | `server_thread_9801` stored scenario at receive time | `trigger_queue` holds only `order_info`; scenario resolved at send time |
| `@ui.refreshable` dropdown breaking itself | `ui.select` inside refreshable destroyed mid-callback | Moved `ui.select` outside refreshable |
| Second send yields no 32R after reconnect | Dead `conn` held `with conn:` block; trigger consumed but `sendall` silently failed | Re-queue `order_info` + `break` on exception |
| scan_state semantics inverted | Scenarios used `'0'` for passed; spec is `'1'`=passed | Corrected all scenario values; updated `_SCAN_STATE` labels |
| `highest_sheet` wrong for multi-station single-carrier | Used `len(responses)` (counts 32R messages) instead of max sheet number | Changed to `max(r.get('sheet', 1) for r in responses)` |
| Server crash on startup with stale `active_scenario.txt` | `_get_active_id()` returned an ID no longer in SCENARIOS; `ui.select` raised `ValueError: Invalid value` | Added validation: check stored ID against current scenario list; fall back to `SCENARIOS[0]` |
| Inbound 12N triggered too many 32Rs | Server checked `scenario.get('category') == 'Inbound'` but an outbound scenario was selected, so condition was False and every 12N triggered immediately | Changed detection to use `order_type` from the parsed 12N (`if order_type in ('02','04','05')`) |
| `_initial_preview` showed error string on startup | `_initial_preview` computed at module level before helper functions (`_friendly_article`, `_preview_text`) were defined; try/except caught NameError silently | Moved computation to after all helpers are defined |
| Scenario Message Preview showed raw `msg.display()` | `send_scenario_order` was not updated when friendly formatters were added | Fixed outbound and inbound branches to use `_preview_text(_friendly_order(...), msg)` |
| Inbound preview didn't distinguish multiple 12N packets | Used `msg.display()` per LU without context | Fixed with `═══` separators, `[1/N] HU000xx` suffix per block, and `— sending N × 12N —` header |
