import base64
import json
import zlib

from forkbl.payload import decode_access_url


def test_decode_access_url_round_trip():
    payload = {"app": "putty", "un": "user", "hn": "bastion", "pn": "22", "pw": "cHdk"}
    encoded = base64.b64encode(zlib.compress(json.dumps(payload).encode())).decode()
    assert decode_access_url("accessclient://" + encoded) == payload
