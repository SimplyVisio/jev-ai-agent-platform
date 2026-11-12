from jev_ai.security import hash_api_key


def test_hash_api_key_matches_sha256() -> None:
    assert hash_api_key("abc") == "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad"


def test_hash_api_key_is_deterministic() -> None:
    assert hash_api_key("secret") == hash_api_key("secret")
