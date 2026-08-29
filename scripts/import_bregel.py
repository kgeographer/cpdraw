"""
One-off import of the whgdraw digitizing data from whg_staging.bregel
into the app's own local database (cpdraw).

Source (whg_staging) is opened read-only and never written to.
All writes happen in a single transaction against the target db,
committed only at the end.

Run from the project root with the venv active:
    python scripts/import_bregel.py
"""
import os
import psycopg
from psycopg.types.json import Json
from dotenv import load_dotenv

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
load_dotenv(os.path.join(BASE_DIR, '.env'))

SRC_DSN = "host=localhost port=5432 dbname=whg_staging"
DST_DSN = (
    f"host={os.environ.get('PGHOST', 'localhost')} "
    f"port={os.environ.get('PGPORT', '5432')} "
    f"dbname={os.environ.get('PGDATABASE', 'cpdraw')} "
    f"user={os.environ.get('PGUSER', '')}"
)

OWNER_USERNAME = 'karlg'

PROJECTS = [
    (3, 'bregel', 'Bregel Atlas of Central Asia'),
]


def ewkt(row_val_srid):
    """row_val_srid: (wkt_text_or_None, srid_or_None) -> EWKT string or None"""
    wkt, srid = row_val_srid
    if wkt is None:
        return None
    return f"SRID={srid};{wkt}"


def main():
    src = psycopg.connect(SRC_DSN)
    src.read_only = True
    dst = psycopg.connect(DST_DSN)

    try:
        with dst.cursor() as dcur:
            dcur.execute("SELECT id FROM auth_user WHERE username = %s", (OWNER_USERNAME,))
            row = dcur.fetchone()
            if not row:
                raise SystemExit(f"user {OWNER_USERNAME!r} not found in target db")
            owner_id = row[0]
            print(f"owner_id = {owner_id}")

            # Projects
            for pid, label, title in PROJECTS:
                dcur.execute(
                    """INSERT INTO projects (id, label, title, owner_id, uri, create_date)
                       VALUES (%s, %s, %s, %s, NULL, now())
                       ON CONFLICT (id) DO NOTHING""",
                    (pid, label, title, owner_id),
                )
            print("projects inserted")

            # Names (no owner/user columns)
            with src.cursor() as scur:
                scur.execute("SELECT id, name, type, maps, flag FROM bregel.names ORDER BY id")
                rows = scur.fetchall()
            params = [
                (r[0], r[1], r[2] or '', r[3] if r[3] is not None else [], r[4])
                for r in rows
            ]
            dcur.executemany(
                "INSERT INTO names (id, name, type, maps, flag) VALUES (%s,%s,%s,%s,%s)",
                params,
            )
            print(f"names inserted: {len(rows)}")

            # Placetypes
            with src.cursor() as scur:
                scur.execute(
                    "SELECT id, aat_id, parent_id, term, term_full, note, fclass "
                    "FROM bregel.placetypes ORDER BY id"
                )
                rows = scur.fetchall()
            dcur.executemany(
                "INSERT INTO placetypes (id, aat_id, parent_id, term, term_full, note, fclass) "
                "VALUES (%s,%s,%s,%s,%s,%s,%s)",
                rows,
            )
            print(f"placetypes inserted: {len(rows)}")

            # Maps (owner remapped to karlg; everything else preserved; only the
            # Bregel project - the Arrowsmith pilot project has no data worth keeping)
            with src.cursor() as scur:
                scur.execute(
                    "SELECT id, title, label, cite_uri, cite_text, project, create_date, "
                    'bounds, maxzoom, minzoom, tiles, year_pub, "when", when_constant '
                    "FROM bregel.maps WHERE project = 3 ORDER BY id"
                )
                rows = scur.fetchall()
            params = [
                (r[0], r[1], r[2], r[3], r[4], r[5], r[6], r[7], r[8], r[9], r[10], r[11],
                 Json(r[12]) if r[12] is not None else None, r[13], owner_id)
                for r in rows
            ]
            dcur.executemany(
                "INSERT INTO maps (id, title, label, cite_uri, cite_text, project, create_date, "
                'bounds, maxzoom, minzoom, tiles, year_pub, "when", when_constant, owner_id) '
                "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                params,
            )
            print(f"maps inserted: {len(rows)}")

            # Features (user remapped to karlg; src_name left NULL, not present in source;
            # geometries carried through as EWKT text to preserve SRID exactly)
            with src.cursor() as scur:
                scur.execute(
                    "SELECT id, title, placetype, jsonb, "
                    "ST_AsText(geom_point), ST_SRID(geom_point), "
                    "ST_AsText(geom_line), ST_SRID(geom_line), "
                    "ST_AsText(geom_poly), ST_SRID(geom_poly), "
                    "map "
                    "FROM bregel.features ORDER BY id"
                )
                rows = scur.fetchall()
            params = [
                (
                    r[0], r[1], r[2],
                    Json(r[3]) if r[3] is not None else None,
                    ewkt((r[4], r[5])), ewkt((r[6], r[7])), ewkt((r[8], r[9])),
                    r[10], owner_id,
                )
                for r in rows
            ]
            dcur.executemany(
                "INSERT INTO features (id, title, placetype, jsonb, "
                "geom_point, geom_line, geom_poly, map, user_id) "
                "VALUES (%s,%s,%s,%s,%s::geometry,%s::geometry,%s::geometry,%s,%s)",
                params,
            )
            print(f"features inserted: {len(rows)}")

            # project_placetype isn't in the bregel dump (no such table there),
            # so the feature-type picker in the draw UI has nothing to show.
            # Backfill project 3 (Bregel) from the placetypes actually used in
            # its imported features; source_label defaults to the placetype's
            # own term since the atlas's original source labels weren't captured.
            dcur.execute(
                """INSERT INTO project_placetype (project_id, aattype_id, source_label)
                   SELECT DISTINCT 3, f.placetype::int, p.term
                   FROM features f
                   JOIN maps m ON m.id = f.map
                   JOIN placetypes p ON p.aat_id = f.placetype::int
                   WHERE m.project = 3
                   ON CONFLICT DO NOTHING"""
            )
            print("project_placetype backfilled for project 3")

            # Resync sequences past the imported ids
            for table in ('projects', 'names', 'placetypes', 'maps', 'features',
                          'project_placetype'):
                dcur.execute(
                    f"SELECT setval(pg_get_serial_sequence('{table}', 'id'), "
                    f"(SELECT COALESCE(MAX(id), 1) FROM {table}))"
                )
            print("sequences resynced")

        dst.commit()
        print("COMMITTED")
    except Exception:
        dst.rollback()
        print("ROLLED BACK due to error")
        raise
    finally:
        src.close()
        dst.close()


if __name__ == '__main__':
    main()
