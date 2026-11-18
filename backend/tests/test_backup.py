"""Copia de la BD (docker-review #06): consistente con WAL, un solo archivo, retención de las N más recientes."""
import sqlite3
from datetime import UTC, datetime

from app.backup import backup_db, next_run, prune


def _wal_db(path):
    con = sqlite3.connect(path)
    con.execute("PRAGMA journal_mode=WAL")
    con.execute("CREATE TABLE t (id INTEGER PRIMARY KEY, v TEXT)")
    con.executemany("INSERT INTO t (v) VALUES (?)", [(f"fila {i}",) for i in range(50)])
    con.commit()
    return con  # abierta: las filas siguen en el -wal sin checkpoint


def test_backup_is_consistent_with_open_wal(tmp_path):
    src = tmp_path / "app.db"
    con = _wal_db(src)
    try:
        out = backup_db(src, tmp_path / "backups", datetime(2026, 11, 17, tzinfo=UTC))
    finally:
        con.close()
    assert out.name == "app-2026-11-17.db"
    copy = sqlite3.connect(out)
    assert copy.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
    assert copy.execute("PRAGMA journal_mode").fetchone()[0] == "delete"
    assert copy.execute("SELECT count(*) FROM t").fetchone()[0] == 50
    copy.close()
    assert sorted(p.name for p in (tmp_path / "backups").iterdir()) == ["app-2026-11-17.db"]


def test_backup_same_day_replaces(tmp_path):
    src = tmp_path / "app.db"
    _wal_db(src).close()
    day = datetime(2026, 11, 17, tzinfo=UTC)
    backup_db(src, tmp_path / "b", day)
    backup_db(src, tmp_path / "b", day)
    assert [p.name for p in (tmp_path / "b").iterdir()] == ["app-2026-11-17.db"]


def test_prune_keeps_newest(tmp_path):
    for day in range(1, 11):
        (tmp_path / f"app-2026-11-{day:02d}.db").write_bytes(b"x")
    (tmp_path / "app.db.bak-manual").write_bytes(b"x")  # copias manuales: nunca se tocan
    (tmp_path / "app-latest.db").write_bytes(b"x")
    removed = prune(tmp_path, 7)
    assert [p.name for p in removed] == ["app-2026-11-01.db", "app-2026-11-02.db", "app-2026-11-03.db"]
    left = sorted(p.name for p in tmp_path.iterdir())
    assert left == ["app-2026-11-04.db", "app-2026-11-05.db", "app-2026-11-06.db", "app-2026-11-07.db",
                    "app-2026-11-08.db", "app-2026-11-09.db", "app-2026-11-10.db", "app-latest.db",
                    "app.db.bak-manual"]
    assert prune(tmp_path, 7) == []


def test_next_run():
    assert next_run(datetime(2026, 11, 17, 2, 59, tzinfo=UTC), 3) == datetime(2026, 11, 17, 3, tzinfo=UTC)
    assert next_run(datetime(2026, 11, 17, 3, 0, tzinfo=UTC), 3) == datetime(2026, 11, 18, 3, tzinfo=UTC)
