from forkbl.crypto import encrypt_field


def test_encrypt_field_shape():
    value = encrypt_field("password", "01234567-0123-0123-0123-012345678901")
    assert value.startswith("__RIS_ENC{") and value.endswith("}")
    ciphertext, iv, digest = value[len("__RIS_ENC{") : -1].split("@")
    assert len(ciphertext) == 32
    assert len(iv) == 32
    assert len(digest) == 64
