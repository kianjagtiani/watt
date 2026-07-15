from assistant.db import connect
from assistant.store import users


def test_add_get_allow_remove():
    conn = connect(":memory:")
    assert not users.is_allowed(conn, "15550001111")
    users.add_user(conn, "15550001111", name="Kian", is_admin=True)
    u = users.get_user(conn, "15550001111")
    assert u["name"] == "Kian" and u["is_admin"] == 1
    assert u["timezone"] == "America/Los_Angeles"
    assert users.is_allowed(conn, "15550001111")
    assert users.remove_user(conn, "15550001111")
    assert not users.is_allowed(conn, "15550001111")
    assert not users.remove_user(conn, "15550001111")


def test_mark_refused_once():
    conn = connect(":memory:")
    assert users.mark_refused(conn, "19998887777") is True
    assert users.mark_refused(conn, "19998887777") is False


def test_readd_admin_does_not_demote():
    conn = connect(":memory:")
    users.add_user(conn, "15550001111", name="Kian", is_admin=True)
    users.add_user(conn, "15550001111")
    u = users.get_user(conn, "15550001111")
    assert u["is_admin"] == 1
    assert u["name"] == "Kian"
