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


def test_v5_table_same_value_other_column():
    a = "| entity | active | backup | ts |\n|---|---|---|---|\n| Coral | v3.14.4 | v3.14.4 | 10:00 |\n| Reef | v2.1.0 | v2.0.9 | 10:00 |\n"
    b = a.replace("| Coral | v3.14.4 | v3.14.4 | 10:00 |", "| Coral | v4.4.4 | v3.14.4 | 10:07 |").replace("| Reef | v2.1.0 | v2.0.9 | 10:00 |", "| Reef | v2.1.0 | v2.0.9 | 10:07 |")
    assert S.value_status(a, b, "v3.14.4") == "unchanged"          # 舊做法：最像的一行還有這個值
    assert S.value_status(a, b, "v3.14.4", by_field=True) == "changed"
    c = a.replace("10:00", "10:09")
    assert S.value_status(a, c, "v3.14.4", by_field=True) == "unchanged"


def test_v5_csv_reordered_rows_and_xml():
    a = "code,entity,price,checked\nP1,Kestrel,204.00 USD,10:00\nP2,Sable,99.00 USD,10:00\n"
    b = "code,entity,price,checked\nP2,Sable,99.00 USD,10:05\nP1,Kestrel,204.00 USD,10:05\n"
    assert S.value_status(a, b, "204.00 USD", by_field=True) == "unchanged"
    assert S.value_status(a, b.replace("204.00", "210.00"), "204.00 USD", by_field=True) == "changed"
    x = "<?xml version='1.0'?><d><item><name>A</name><cap>55 seats</cap><max>55 seats</max></item></d>"
    y = x.replace("<cap>55 seats</cap>", "<cap>91 seats</cap>")
    assert S.value_status(x, y, "55 seats", by_field=True) == "changed"
    assert S.value_status(x, x, "55 seats", by_field=True) == "unchanged"


def test_v5_html_table():
    a = "<html><body><p>Updated 10:00</p><table><tr><th>Name</th><th>Speed</th><th>Max</th></tr><tr><td>Kestrel</td><td>27 knots</td><td>27 knots</td></tr></table></body></html>"
    b = a.replace("<td>27 knots</td><td>27 knots</td>", "<td>31 knots</td><td>27 knots</td>").replace("10:00", "10:05")
    assert S.value_status(a, b, "27 knots", by_field=True) == "changed"
    assert S.value_status(a, a.replace("10:00", "10:05"), "27 knots", by_field=True) == "unchanged"


def test_guard_label_change_on_handed_line_is_not_rewritten_into_sibling(tmp_path):
    """撤回的 v5 修法（只准改值）不再做；但標籤被改的交辦行也不能拿兄弟行來頂替。"""
    before = "# R\n- Summit Gear 44 — crate capacity: 39 units\n- Summit Gear 44 — stock on hand: 12 units\n"
    (tmp_path / "report.md").write_text("# R\n- Summit Gear 44 — stock on hand: 63 units\n- Summit Gear 44 — stock on hand: 12 units\n")
    S.guard(tmp_path, "report.md", [2], before, record=False)
    out = (tmp_path / "report.md").read_text().splitlines()
    assert out[2] == "- Summit Gear 44 — stock on hand: 12 units"


def test_guard_entity_with_digits_does_not_overwrite_sibling_lines(tmp_path):
    """獨立稽核 11-25：_line_key 取「第一個數字之前」，Hauler H220 的所有行撞成同一個鍵，交辦的行被兄弟行蓋掉。"""
    before = ("# R\n- Hauler H220 — pallet capacity: 30 pallets\n- Hauler H220 — on-time arrival rate: 84.8%\n"
              "- Hauler H220 — base lane tariff: 871.75 USD\n")
    agent = before.replace("on-time arrival rate: 84.8%", "on-time arrival rate: 78%")
    (tmp_path / "report.md").write_text(agent)
    r = S.guard(tmp_path, "report.md", [3], before, record=False)
    out = (tmp_path / "report.md").read_text().splitlines()
    assert out[2] == "- Hauler H220 — on-time arrival rate: 78%"
    assert out[1] == "- Hauler H220 — pallet capacity: 30 pallets" and out[3].endswith("871.75 USD")
    assert r["restored_lines"] == []


def test_guard_still_restores_out_of_scope_edit_on_digit_entity(tmp_path):
    before = "# R\n- Hauler H220 — pallet capacity: 30 pallets\n- Hauler H220 — on-time arrival rate: 84.8%\n"
    agent = before.replace("30 pallets", "99 pallets").replace("84.8%", "78%")
    (tmp_path / "report.md").write_text(agent)
    r = S.guard(tmp_path, "report.md", [3], before, record=False)
    out = (tmp_path / "report.md").read_text().splitlines()
    assert out[1].endswith("30 pallets") and out[2].endswith("78%") and r["restored_lines"] == [2]
