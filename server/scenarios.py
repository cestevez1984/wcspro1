"""Static scenario definitions for the KiSoft One mock server.

Each scenario has a 'responses' list — one entry per station scan event.
The server sends one 32R per entry, in order, with a small delay between them.

Key rules:
  - One 32R per station the carrier passes through (last_scan_station = that station)
  - Multiple articles at the same station → multiple Z-lines in ONE 32R
  - Multiple stations → multiple response entries (one 32R each)
  - start_station is always 190 (OS001 Output — the conveyor start)
  - Carrier codes: HU00001 – HU00999
  - Bulk (199) ramp: 00025   |   all others: 00001–00010
  - sheet = loading unit number (HU00001=1, HU00002=2, …)
  - highest_sheet = max(sheet) across all responses = total loading units in the order

order_states codes:
  0001 = order started  ← first response only
  0002 = order completed
  0010 = last carrier   ← always on the final response
  (intermediate responses carry no order_states — empty list)

line_state codes:
  30 = processed correctly
  58 = out of stock
  51 = quantity mismatch

Default test values: client=A1301  order_number=TEST001
"""

SCENARIOS = [

    # ── 101 ──────────────────────────────────────────────────────────────────

    {
        'id':          'out_101_cbs_1art',
        'category':    'Outbound',
        'name':        '101 — 1 article CBS (1 carrier)',
        'description': 'ARCBS01 picked at CBS (091). '
                       '1 loading unit HU00001. 1 × 32R.',
        'responses': [
            {
                'sheet':              1,
                'carrier_type':       'LARGE',
                'carrier_code':       'HU00001',
                'start_station':      '190',
                'last_scan_station':  '091',
                'scan_state':         '1',
                'dispatch_ramp':      '00001',
                'order_states':       ['0001', '0002', '0010'],
                'z_lines': [
                    {
                        'article':    'ARCBS01',
                        'pack_size':  1,
                        'stock_type': 'STANDARD',
                        'lot':        'LTC001',
                        'quantity':   3,
                        'quality':    '1',
                        'line_state': '30',
                        'geocode':    '',
                    },
                ],
            },
        ],
    },

    # ── 102 ──────────────────────────────────────────────────────────────────

    {
        'id':          'out_102_cbs_osr_1carrier',
        'category':    'Outbound',
        'name':        '102 — CBS + OSR (1 carrier, 2 × 32R)',
        'description': 'ARCBS01 from CBS (091) + AROSR01 from OSR (092). '
                       '1 loading unit HU00001. 2 × 32R — one per station.',
        'responses': [
            {
                'sheet':              1,
                'carrier_type':       'LARGE',
                'carrier_code':       'HU00001',
                'start_station':      '190',
                'last_scan_station':  '091',
                'scan_state':         '1',
                'dispatch_ramp':      '00001',
                'order_states':       ['0001'],
                'z_lines': [
                    {
                        'article':    'ARCBS01',
                        'pack_size':  1,
                        'stock_type': 'STANDARD',
                        'lot':        'LTC001',
                        'quantity':   3,
                        'quality':    '1',
                        'line_state': '30',
                        'geocode':    '',
                    },
                ],
            },
            {
                'sheet':              1,
                'carrier_type':       'LARGE',
                'carrier_code':       'HU00001',
                'start_station':      '190',
                'last_scan_station':  '092',
                'scan_state':         '1',
                'dispatch_ramp':      '00001',
                'order_states':       ['0002', '0010'],
                'z_lines': [
                    {
                        'article':    'AROSR01',
                        'pack_size':  1,
                        'stock_type': 'STANDARD',
                        'lot':        'LTC001',
                        'quantity':   3,
                        'quality':    '1',
                        'line_state': '30',
                        'geocode':    '',
                    },
                ],
            },
        ],
    },

    # ── 103 ──────────────────────────────────────────────────────────────────

    {
        'id':          'out_103_partial_oos',
        'category':    'Outbound',
        'name':        '103 — Partial pick, article 2 out of stock',
        'description': 'ARCBS01 picked correctly (state 30). '
                       'ARCBS02 out of stock (state 58). '
                       '1 carrier HU00001 at CBS (091). 1 × 32R.',
        'responses': [
            {
                'sheet':              1,
                'carrier_type':       'LARGE',
                'carrier_code':       'HU00001',
                'start_station':      '190',
                'last_scan_station':  '091',
                'scan_state':         '1',
                'dispatch_ramp':      '00001',
                'order_states':       ['0001', '0002', '0010'],
                'z_lines': [
                    {
                        'article':    'ARCBS01',
                        'pack_size':  1,
                        'stock_type': 'STANDARD',
                        'lot':        '',
                        'quantity':   2,
                        'quality':    '1',
                        'line_state': '30',
                        'geocode':    '',
                    },
                    {
                        'article':    'ARCBS02',
                        'pack_size':  1,
                        'stock_type': 'STANDARD',
                        'lot':        '',
                        'quantity':   0,
                        'quality':    '1',
                        'line_state': '58',
                        'geocode':    '',
                    },
                ],
            },
        ],
    },

    # ── 104 ──────────────────────────────────────────────────────────────────

    {
        'id':          'out_104_3art_cbs',
        'category':    'Outbound',
        'name':        '104 — 3 articles CBS, 1 carrier, all correct',
        'description': 'ARCBS01 + ARCBS02 + ARCBS03 all picked at CBS (091). '
                       '1 carrier HU00001. All lines state 30. 1 × 32R.',
        'responses': [
            {
                'sheet':              1,
                'carrier_type':       'LARGE',
                'carrier_code':       'HU00001',
                'start_station':      '190',
                'last_scan_station':  '091',
                'scan_state':         '1',
                'dispatch_ramp':      '00001',
                'order_states':       ['0001', '0002', '0010'],
                'z_lines': [
                    {
                        'article':    'ARCBS01',
                        'pack_size':  1,
                        'stock_type': 'STANDARD',
                        'lot':        '',
                        'quantity':   3,
                        'quality':    '1',
                        'line_state': '30',
                        'geocode':    '',
                    },
                    {
                        'article':    'ARCBS02',
                        'pack_size':  1,
                        'stock_type': 'STANDARD',
                        'lot':        '',
                        'quantity':   1,
                        'quality':    '1',
                        'line_state': '30',
                        'geocode':    '',
                    },
                    {
                        'article':    'ARCBS03',
                        'pack_size':  1,
                        'stock_type': 'STANDARD',
                        'lot':        '',
                        'quantity':   2,
                        'quality':    '1',
                        'line_state': '30',
                        'geocode':    '',
                    },
                ],
            },
        ],
    },

    # ── 105 ──────────────────────────────────────────────────────────────────

    {
        'id':          'out_105_manual_osr_3msg',
        'category':    'Outbound',
        'name':        '105 — Manual M001 + M002 + OSR (1 carrier, 3 × 32R)',
        'description': 'ARM0011 from Manual M001 (001, geocode 001XXXYYYZZZ), '
                       'ARM0021 from Manual M002 (002, geocode 002XXXYYYZZZ), '
                       'AROSR01 from OSR (092). 1 loading unit HU00001. '
                       '3 × 32R — one per station.',
        'responses': [
            {
                'sheet':              1,
                'carrier_type':       'LARGE',
                'carrier_code':       'HU00001',
                'start_station':      '190',
                'last_scan_station':  '001',
                'scan_state':         '1',
                'dispatch_ramp':      '00001',
                'order_states':       ['0001'],
                'z_lines': [
                    {
                        'article':    'ARM0011',
                        'pack_size':  1,
                        'stock_type': 'STANDARD',
                        'lot':        'LTC001',
                        'quantity':   1,
                        'quality':    '1',
                        'line_state': '30',
                        'geocode':    '001XXXYYYZZZ',
                    },
                ],
            },
            {
                'sheet':              1,
                'carrier_type':       'LARGE',
                'carrier_code':       'HU00001',
                'start_station':      '190',
                'last_scan_station':  '002',
                'scan_state':         '1',
                'dispatch_ramp':      '00001',
                'order_states':       [],
                'z_lines': [
                    {
                        'article':    'ARM0021',
                        'pack_size':  1,
                        'stock_type': 'STANDARD',
                        'lot':        'LTC001',
                        'quantity':   1,
                        'quality':    '1',
                        'line_state': '30',
                        'geocode':    '002XXXYYYZZZ',
                    },
                ],
            },
            {
                'sheet':              1,
                'carrier_type':       'LARGE',
                'carrier_code':       'HU00001',
                'start_station':      '190',
                'last_scan_station':  '092',
                'scan_state':         '1',
                'dispatch_ramp':      '00001',
                'order_states':       ['0002', '0010'],
                'z_lines': [
                    {
                        'article':    'AROSR01',
                        'pack_size':  1,
                        'stock_type': 'STANDARD',
                        'lot':        'LTC001',
                        'quantity':   1,
                        'quality':    '1',
                        'line_state': '30',
                        'geocode':    '',
                    },
                ],
            },
        ],
    },

    # ── 106 ──────────────────────────────────────────────────────────────────

    {
        'id':          'out_106_bulk_osr_2carriers',
        'category':    'Outbound',
        'name':        '106 — Bulk + OSR (2 carriers, 2 × 32R)',
        'description': 'AR0001 from Bulk (199) pack=12 qty=24 → HU00001 ramp 00025. '
                       'AR0002 from OSR (092) pack=1 qty=3 → HU00002. '
                       '2 × 32R — one per loading unit.',
        'responses': [
            {
                'sheet':              1,
                'carrier_type':       'LARGE',
                'carrier_code':       'HU00001',
                'start_station':      '190',
                'last_scan_station':  '199',
                'scan_state':         '1',
                'dispatch_ramp':      '00025',
                'order_states':       ['0001'],
                'z_lines': [
                    {
                        'article':    'AR0001',
                        'pack_size':  12,
                        'stock_type': 'STANDARD',
                        'lot':        'LTC001',
                        'quantity':   24,
                        'quality':    '1',
                        'line_state': '30',
                        'geocode':    '',
                    },
                ],
            },
            {
                'sheet':              2,
                'carrier_type':       'LARGE',
                'carrier_code':       'HU00002',
                'start_station':      '190',
                'last_scan_station':  '092',
                'scan_state':         '1',
                'dispatch_ramp':      '00001',
                'order_states':       ['0002', '0010'],
                'z_lines': [
                    {
                        'article':    'AR0002',
                        'pack_size':  1,
                        'stock_type': 'STANDARD',
                        'lot':        'LTC001',
                        'quantity':   3,
                        'quality':    '1',
                        'line_state': '30',
                        'geocode':    '',
                    },
                ],
            },
        ],
    },

    # ── 107 ──────────────────────────────────────────────────────────────────

    {
        'id':          'out_107_mixed_2carriers',
        'category':    'Outbound',
        'name':        '107 — Mixed: Bulk + CBS/OSR/Manual (2 carriers, 5 × 32R)',
        'description': 'HU00001: AR0001 from Bulk (199, ramp 00025). '
                       'HU00002: AR0001 from CBS (091), AROSR01 from OSR (092), '
                       'ARM0011 from Manual M001 (001), ARM0031 from Manual M003 (003). '
                       '5 × 32R total — one per station.',
        'responses': [
            {
                'sheet':              1,
                'carrier_type':       'LARGE',
                'carrier_code':       'HU00001',
                'start_station':      '190',
                'last_scan_station':  '199',
                'scan_state':         '1',
                'dispatch_ramp':      '00025',
                'order_states':       ['0001'],
                'z_lines': [
                    {
                        'article':    'AR0001',
                        'pack_size':  12,
                        'stock_type': 'STANDARD',
                        'lot':        'LTC001',
                        'quantity':   2,
                        'quality':    '1',
                        'line_state': '30',
                        'geocode':    '',
                    },
                ],
            },
            {
                'sheet':              2,
                'carrier_type':       'LARGE',
                'carrier_code':       'HU00002',
                'start_station':      '190',
                'last_scan_station':  '091',
                'scan_state':         '1',
                'dispatch_ramp':      '00001',
                'order_states':       [],
                'z_lines': [
                    {
                        'article':    'AR0001',
                        'pack_size':  1,
                        'stock_type': 'STANDARD',
                        'lot':        'LTC001',
                        'quantity':   6,
                        'quality':    '1',
                        'line_state': '30',
                        'geocode':    '',
                    },
                ],
            },
            {
                'sheet':              2,
                'carrier_type':       'LARGE',
                'carrier_code':       'HU00002',
                'start_station':      '190',
                'last_scan_station':  '092',
                'scan_state':         '1',
                'dispatch_ramp':      '00001',
                'order_states':       [],
                'z_lines': [
                    {
                        'article':    'AROSR01',
                        'pack_size':  1,
                        'stock_type': 'STANDARD',
                        'lot':        'LTC001',
                        'quantity':   10,
                        'quality':    '1',
                        'line_state': '30',
                        'geocode':    '',
                    },
                ],
            },
            {
                'sheet':              2,
                'carrier_type':       'LARGE',
                'carrier_code':       'HU00002',
                'start_station':      '190',
                'last_scan_station':  '001',
                'scan_state':         '1',
                'dispatch_ramp':      '00001',
                'order_states':       [],
                'z_lines': [
                    {
                        'article':    'ARM0011',
                        'pack_size':  1,
                        'stock_type': 'STANDARD',
                        'lot':        'LTC001',
                        'quantity':   5,
                        'quality':    '1',
                        'line_state': '30',
                        'geocode':    '001XXXYYYZZZ',
                    },
                ],
            },
            {
                'sheet':              2,
                'carrier_type':       'LARGE',
                'carrier_code':       'HU00002',
                'start_station':      '190',
                'last_scan_station':  '003',
                'scan_state':         '1',
                'dispatch_ramp':      '00001',
                'order_states':       ['0002', '0010'],
                'z_lines': [
                    {
                        'article':    'ARM0031',
                        'pack_size':  1,
                        'stock_type': 'STANDARD',
                        'lot':        'LTC001',
                        'quantity':   8,
                        'quality':    '1',
                        'line_state': '30',
                        'geocode':    '003XXXYYYZZZ',
                    },
                ],
            },
        ],
    },

]

# Quick lookup by id
SCENARIO_MAP = {sc['id']: sc for sc in SCENARIOS}
