from dealfinder.cli import cmd_init_db


def test_init_db_prints_all_migrations(capsys):
    cmd_init_db(None)
    out = capsys.readouterr().out
    assert "001_core.sql" in out
    assert "002_clustering.sql" in out
    assert "create table if not exists listings" in out
    assert "create table if not exists price_history" in out
