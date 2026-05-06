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
  - Manual stations (001-004) consolidate into ONE 32R at RL002 (086); geocode
    in each Z-line identifies the specific rack
  - FCS001 (093) is ALWAYS the final response for every order:
      · Normal orders: Z-lines are ALL lines from non-cooling/non-controlled stations
      · Cooling (011) and controlled (010) orders: 32R sent but with 0 Z-lines
      · Bulk (199) lines are excluded from FCS001 (Bulk dispatches to its own ramp)
      · order_states ['0002', '0010'] belong exclusively on the FCS001 response

order_states codes:
  0001 = order started  ← first response only
  0002 = order completed
  0010 = last carrier   ← always on the FCS001 (final) response
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
        'name':        '101 — 1 article CBS (1 carrier, 2 × 32R)',
        'description': 'ARCBS01 picked at CBS (091). '
                       '1 loading unit HU00001. 2 × 32R (091 + FCS001).',
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
                'last_scan_station':  '093',
                'scan_state':         '1',
                'dispatch_ramp':      '00001',
                'order_states':       ['0002', '0010'],
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
        'name':        '102 — CBS + OSR (1 carrier, 3 × 32R)',
        'description': 'ARCBS01 from CBS (091) + AROSR01 from OSR (092). '
                       '1 loading unit HU00001. 3 × 32R (091 + 092 + FCS001).',
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
                'order_states':       [],
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
            {
                'sheet':              1,
                'carrier_type':       'LARGE',
                'carrier_code':       'HU00001',
                'start_station':      '190',
                'last_scan_station':  '093',
                'scan_state':         '1',
                'dispatch_ramp':      '00001',
                'order_states':       ['0002', '0010'],
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
        'name':        '103 — Partial pick, article 2 out of stock (2 × 32R)',
        'description': 'ARCBS01 picked correctly (state 30). '
                       'ARCBS02 out of stock (state 58). '
                       '1 carrier HU00001 at CBS (091). 2 × 32R (091 + FCS001).',
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
            {
                'sheet':              1,
                'carrier_type':       'LARGE',
                'carrier_code':       'HU00001',
                'start_station':      '190',
                'last_scan_station':  '093',
                'scan_state':         '1',
                'dispatch_ramp':      '00001',
                'order_states':       ['0002', '0010'],
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
        'name':        '104 — 3 articles CBS, 1 carrier, all correct (2 × 32R)',
        'description': 'ARCBS01 + ARCBS02 + ARCBS03 all picked at CBS (091). '
                       '1 carrier HU00001. All lines state 30. 2 × 32R (091 + FCS001).',
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
            {
                'sheet':              1,
                'carrier_type':       'LARGE',
                'carrier_code':       'HU00001',
                'start_station':      '190',
                'last_scan_station':  '093',
                'scan_state':         '1',
                'dispatch_ramp':      '00001',
                'order_states':       ['0002', '0010'],
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
        'description': 'ARM0011 (M001, geocode 001XXXYYYZZZ) + ARM0021 (M002, geocode 002XXXYYYZZZ) '
                       'consolidated at RL002 (086). AROSR01 from OSR (092). '
                       '1 loading unit HU00001. 3 × 32R (086 + 092 + FCS001).',
        'responses': [
            {
                'sheet':              1,
                'carrier_type':       'LARGE',
                'carrier_code':       'HU00001',
                'start_station':      '190',
                'last_scan_station':  '086',
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
                'order_states':       [],
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
            {
                'sheet':              1,
                'carrier_type':       'LARGE',
                'carrier_code':       'HU00001',
                'start_station':      '190',
                'last_scan_station':  '093',
                'scan_state':         '1',
                'dispatch_ramp':      '00001',
                'order_states':       ['0002', '0010'],
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
        'name':        '106 — Bulk + OSR (2 carriers, 3 × 32R)',
        'description': 'AR0001 from Bulk (199) pack=12 qty=24 → HU00001 ramp 00025. '
                       'AR0002 from OSR (092) pack=1 qty=3 → HU00002. '
                       '3 × 32R (199 + 092 + FCS001). Bulk excluded from FCS001.',
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
                'order_states':       [],
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
            {
                'sheet':              2,
                'carrier_type':       'LARGE',
                'carrier_code':       'HU00002',
                'start_station':      '190',
                'last_scan_station':  '093',
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
                       'ARM0011+ARM0031 consolidated at RL002 (086). '
                       '5 × 32R (199 + 091 + 092 + 086 + FCS001). Bulk excluded from FCS001.',
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
                'last_scan_station':  '086',
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
            {
                'sheet':              2,
                'carrier_type':       'LARGE',
                'carrier_code':       'HU00002',
                'start_station':      '190',
                'last_scan_station':  '093',
                'scan_state':         '1',
                'dispatch_ramp':      '00001',
                'order_states':       ['0002', '0010'],
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

    # ── 108 ──────────────────────────────────────────────────────────────────

    {
        'id':          'out_108_cooling',
        'category':    'Outbound',
        'name':        '108 — Cooling M011 (1 carrier, 2 × 32R)',
        'description': 'Isolated cooling order. ARCOOL01 + ARCOOL02 picked at M011 (011). '
                       '1 loading unit HU00001. 2 × 32R (011 + FCS001 with 0 Z-lines).',
        'responses': [
            {
                'sheet':              1,
                'carrier_type':       'LARGE',
                'carrier_code':       'HU00001',
                'start_station':      '190',
                'last_scan_station':  '011',
                'scan_state':         '1',
                'dispatch_ramp':      '00001',
                'order_states':       ['0001'],
                'z_lines': [
                    {
                        'article':    'ARCOOL01',
                        'pack_size':  1,
                        'stock_type': 'STANDARD',
                        'lot':        'LTC010',
                        'quantity':   4,
                        'quality':    '1',
                        'line_state': '30',
                        'geocode':    '',
                    },
                    {
                        'article':    'ARCOOL02',
                        'pack_size':  1,
                        'stock_type': 'STANDARD',
                        'lot':        'LTC011',
                        'quantity':   2,
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
                'last_scan_station':  '093',
                'scan_state':         '1',
                'dispatch_ramp':      '00001',
                'order_states':       ['0002', '0010'],
                'z_lines':            [],
            },
        ],
    },

    # ── 109 ──────────────────────────────────────────────────────────────────

    {
        'id':          'out_109_controlled',
        'category':    'Outbound',
        'name':        '109 — Controlled substance M010 (1 carrier, 2 × 32R)',
        'description': 'Isolated controlled substance order. ARCONT01 + ARCONT02 picked at M010 (010). '
                       '1 loading unit HU00001. 2 × 32R (010 + FCS001 with 0 Z-lines).',
        'responses': [
            {
                'sheet':              1,
                'carrier_type':       'LARGE',
                'carrier_code':       'HU00001',
                'start_station':      '190',
                'last_scan_station':  '010',
                'scan_state':         '1',
                'dispatch_ramp':      '00001',
                'order_states':       ['0001'],
                'z_lines': [
                    {
                        'article':    'ARCONT01',
                        'pack_size':  1,
                        'stock_type': 'STANDARD',
                        'lot':        'LTC020',
                        'quantity':   1,
                        'quality':    '1',
                        'line_state': '30',
                        'geocode':    '',
                    },
                    {
                        'article':    'ARCONT02',
                        'pack_size':  1,
                        'stock_type': 'STANDARD',
                        'lot':        'LTC021',
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
                'last_scan_station':  '093',
                'scan_state':         '1',
                'dispatch_ramp':      '00001',
                'order_states':       ['0002', '0010'],
                'z_lines':            [],
            },
        ],
    },

    # ── IN-101 ───────────────────────────────────────────────────────────────

    {
        'id':          'in_101_osr_decanting',
        'category':    'Inbound',
        'name':        '101 — OSR Decanting (2 pallets → 3 storage units)',
        'description': '2 × 12N sent (one per loading unit). '
                       'KiSoft deconsolidates into 3 OSR storage units and returns 3 × 32R.',

        # loading_units → one 12N per entry sent by the client
        'loading_units': [
            {
                'carrier_code': 'HU00010',
                'b_lines': [
                    {
                        'article':       'AROSR04',
                        'pack_size':     1,
                        'stock_type':    'STANDARD',
                        'lot':           'LTC001',
                        'expiry':        '20300101',
                        'station':       '065',
                        'quantity':      10,
                        'stock_quality': '1',
                    },
                    {
                        'article':       'AROSR05',
                        'pack_size':     1,
                        'stock_type':    'STANDARD',
                        'lot':           'LTC001',
                        'expiry':        '20300101',
                        'station':       '065',
                        'quantity':      5,
                        'stock_quality': '1',
                    },
                ],
            },
            {
                'carrier_code': 'HU00011',
                'b_lines': [
                    {
                        'article':       'AROSR06',
                        'pack_size':     1,
                        'stock_type':    'STANDARD',
                        'lot':           'LTC001',
                        'expiry':        '20300101',
                        'station':       '065',
                        'quantity':      20,
                        'stock_quality': '1',
                    },
                    {
                        'article':       'AROSR07',
                        'pack_size':     1,
                        'stock_type':    'STANDARD',
                        'lot':           'LTC001',
                        'expiry':        '20300101',
                        'station':       '065',
                        'quantity':      25,
                        'stock_quality': '1',
                    },
                ],
            },
        ],

        # responses → one 32R per storage unit sent by KiSoft
        'responses': [
            {
                'sheet':              1,
                'carrier_type':       '',
                'carrier_code':       'SU00001',
                'start_station':      '065',
                'last_scan_station':  '065',
                'scan_state':         '1',
                'dispatch_ramp':      '00000',
                'order_states':       ['0002'],
                'z_lines':            [],
                'b_lines': [
                    {
                        'article':    'AROSR04',
                        'pack_size':  1,
                        'stock_type': 'STANDARD',
                        'lot':        'LTC001',
                        'expiry':     '20300101',
                        'quantity':   10,
                        'quality':    '1',
                        'line_state': '30',
                    },
                    {
                        'article':    'AROSR05',
                        'pack_size':  1,
                        'stock_type': 'STANDARD',
                        'lot':        'LTC001',
                        'expiry':     '20300101',
                        'quantity':   5,
                        'quality':    '1',
                        'line_state': '30',
                    },
                ],
            },
            {
                'sheet':              2,
                'carrier_type':       '',
                'carrier_code':       'SU00002',
                'start_station':      '065',
                'last_scan_station':  '065',
                'scan_state':         '1',
                'dispatch_ramp':      '00000',
                'order_states':       ['0002'],
                'z_lines':            [],
                'b_lines': [
                    {
                        'article':    'AROSR06',
                        'pack_size':  1,
                        'stock_type': 'STANDARD',
                        'lot':        'LTC001',
                        'expiry':     '20300101',
                        'quantity':   20,
                        'quality':    '1',
                        'line_state': '30',
                    },
                ],
            },
            {
                'sheet':              3,
                'carrier_type':       '',
                'carrier_code':       'SU00003',
                'start_station':      '065',
                'last_scan_station':  '065',
                'scan_state':         '1',
                'dispatch_ramp':      '00000',
                'order_states':       ['0002'],
                'z_lines':            [],
                'b_lines': [
                    {
                        'article':    'AROSR07',
                        'pack_size':  1,
                        'stock_type': 'STANDARD',
                        'lot':        'LTC001',
                        'expiry':     '20300101',
                        'quantity':   25,
                        'quality':    '1',
                        'line_state': '30',
                    },
                ],
            },
        ],
    },

]

# Quick lookup by id
SCENARIO_MAP = {sc['id']: sc for sc in SCENARIOS}
