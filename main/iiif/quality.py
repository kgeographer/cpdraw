"""Advisory checks on a IIIF image's fitness for close tracing.

Not validation — nothing here blocks ingest. The notes surface in the UI so a
user can decide to look for a better source (real-world IIIF is uneven,
scoping doc §6a).

    assess(width, height, info_json) -> [{'level', 'code', 'message'}, ...]
"""

# Pixel-on-the-long-edge bands. Long-edge px is a crude proxy — it knows
# nothing about the map's geographic coverage (6762 px is fine for one
# province, thin for a whole continent) and can't tell "too few pixels" from
# "slow service that needs a warm-up". So only the very-low band gates the add;
# the middle band is an advisory ⚠ that still lets the source through.
_LOWRES_VERY = 6000     # gating warning
_LOWRES = 10000         # advisory info note

# IIIF tile size above which first paint noticeably drags.
_BIG_TILE = 1024


def assess(width=None, height=None, info_json=None):
    notes = []
    long_edge = max(width or 0, height or 0)

    if long_edge:
        if long_edge < _LOWRES_VERY:
            notes.append(_note(
                'warning', 'very_low_res',
                f'Very low resolution ({width}×{height}). Fine detail on a '
                f'dense map will be illegible — find a better source.'))
        elif long_edge < _LOWRES:
            notes.append(_note(
                'info', 'low_res',
                f'Moderate resolution ({width}×{height}). Legibility depends on '
                f'the map’s coverage; on a slow service (e.g. LUNA) it may take '
                f'a warm-up load to sharpen.'))

    if isinstance(info_json, dict):
        tiles = info_json.get('tiles')
        if not tiles:
            notes.append(_note(
                'warning', 'not_tiled',
                'The image service advertises no tiles — deep zoom will be '
                'limited and loading may be slow.'))
        else:
            biggest = max((_int(t.get('width')) for t in tiles), default=0)
            if biggest > _BIG_TILE:
                notes.append(_note(
                    'info', 'large_tiles',
                    f'Large tiles ({biggest}px) — first paint and zoom steps '
                    f'will be slower than a 256–512px service.'))
        if _profile_level(info_json) == 0:
            notes.append(_note(
                'info', 'level0',
                'Level 0 image service — only pre-generated sizes, no arbitrary '
                'region requests.'))

    return notes


def _note(level, code, message):
    return {'level': level, 'code': code, 'message': message}


def _int(v):
    try:
        return int(v)
    except (TypeError, ValueError):
        return 0


def _profile_level(info_json):
    """Best-effort IIIF Image API compliance level (0/1/2), or None."""
    prof = info_json.get('profile')
    entries = prof if isinstance(prof, list) else [prof]
    for e in entries:
        s = e if isinstance(e, str) else (e.get('@id', '') if isinstance(e, dict) else '')
        if isinstance(s, str):
            for lvl in ('level2', 'level1', 'level0'):
                if lvl in s:
                    return int(lvl[-1])
    return None
