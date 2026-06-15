from llmwiki import store


def test_sha256_bytes_stable():
    assert store.sha256_bytes(b"abc") == store.sha256_bytes(b"abc")
    assert store.sha256_bytes(b"abc") != store.sha256_bytes(b"abd")


def test_page_round_trip(tmp_path):
    path = tmp_path / "p.md"
    store.write_page(path, {"title": "T", "type": "concept", "sources": ["s1"]}, "Body text")
    page = store.read_page(path)
    assert page is not None
    assert page.metadata["title"] == "T"
    assert page.metadata["sources"] == ["s1"]
    assert page.content.strip() == "Body text"


def test_state_save_load(vault):
    state = store.load_state(vault)
    store.set_source_record(state, "raw/sources/a.md", {"checksum": "x"})
    store.save_state(vault, state)
    reloaded = store.load_state(vault)
    assert store.get_source_record(reloaded, "raw/sources/a.md") == {"checksum": "x"}
