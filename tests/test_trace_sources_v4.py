"""v4：受影響看值（雜訊不觸發、值改了會觸發、陣列重排不誤判）與網路出口紀錄進鏈。"""
import json

from vacant_network.trace import sources as S


def j(o):
    return json.dumps(o)


def test_json_noise_does_not_trigger_value_change_does():
    a = {"generated_at": "2026-11-25T10:00:00Z", "items": [{"entity": "Kestrel 200", "stock": "38 units", "id": "ab12"},
                                                          {"entity": "Kestrel 200X", "stock": "41 units", "id": "cd34"}]}
    b = json.loads(j(a)); b["generated_at"] = "2026-11-25T10:05:00Z"; b["items"][0]["id"] = "zz99"
    assert S.value_status(j(a), j(b), "38 units") == "unchanged"
    c = json.loads(j(b)); c["items"][0]["stock"] = "45 units"
    assert S.value_status(j(a), j(c), "38 units") == "changed"


def test_json_reordered_array_follows_the_item():
    a = {"items": [{"entity": "A 1", "v": "10 kg"}, {"entity": "B 2", "v": "20 kg"}]}
    b = {"items": [{"entity": "B 2", "v": "20 kg"}, {"entity": "A 1", "v": "10 kg"}]}
    assert S.value_status(j(a), j(b), "10 kg") == "unchanged"
    b["items"][1]["v"] = "11 kg"
    assert S.value_status(j(a), j(b), "10 kg") == "changed"


def test_csv_row_noise_and_change():
    a = "code,entity,price,checked\nP1,Kestrel 200,204.00 USD,2026-11-25T10:00Z\nP2,Sable Hose 36,204.00 USD,2026-11-25T10:00Z\n"
    b = a.replace("10:00Z", "10:07Z")
    assert S.value_status(a, b, "204.00 USD") == "unchanged"
    c = b.replace("P1,Kestrel 200,204.00 USD", "P1,Kestrel 200,219.50 USD")
    assert S.value_status(a, c, "204.00 USD") == "changed"


def test_text_line_and_not_a_source():
    a = "Report generated 10:00:01 (views 1001)\nThe northern route is 32 km long.\n"
    b = "Report generated 10:03:44 (views 1002)\nThe northern route is 32 km long.\n"
    assert S.value_status(a, b, "32 km") == "unchanged"
    assert S.value_status(a, b.replace("32 km", "35 km"), "32 km") == "changed"
    assert S.value_status(a, b, "99 km") is None
