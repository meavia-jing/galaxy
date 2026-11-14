"""Django project package.

When the native ``mysqlclient`` wheel cannot be installed (no C compiler on
Windows), fall back to the pure-Python ``PyMySQL`` driver and expose it as
``MySQLdb`` so Django's MySQL backend works unchanged.
"""
try:  # pragma: no cover - driver bootstrap
    import MySQLdb  # noqa: F401
except ImportError:  # pragma: no cover
    try:
        import pymysql

        pymysql.install_as_MySQLdb()
    except ImportError:
        # Truly optional: only required when DB_ENGINE=mysql.
        pass
