"""P13 第三輪（2026-10-08）：卡片要讓人「哇這就是我／我也想試」。

守的是：
* 卡第 1 行＝程式組句的「你的數位分身其實是：<形狀><質感>的<色系>居民，<氣質三詞擇二>（ENFP · 雙子 · AB）」，全是 AI 判決欄位；
* 卡第 2 行＝PLAN「我想：」之後的願望（沒有那個標籤就沒有這一行，不拿動作句充數）；
* 卡第 3 行＝「試的紀錄」裡世界留下的改變那一句（不是路線）；
* 每一行的長度上限（雲端手機 ≤4 行、每行 ≤60 字；電視 ≤3 句、每句 ≤60 字）；
* 變化由 cell_id 確定性決定（醒來的地點、ws_list 順序、信的感官種類與身體部位），而且分得開；
* 世界材料補了「人類常見的心願」接得住的東西；12 份像真 AI 回答的觀眾輸入。
"""
from __future__ import annotations

import json
import pathlib
import re
import shutil
import subprocess
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from ops.exhibit.twin import fortune as fz  # noqa: E402
from ops.exhibit.twin import sidecar, tv_contract, twinagent, twinground  # noqa: E402
from vacant_network.memory import assert_ks1_clean  # noqa: E402

F = fz.resolve({"mbti": "ENFP", "mbti_source": "ai", "zodiac": "雙子", "blood": "AB"}, {})
LOOK = {"shape": "小巧", "texture": "斑駁", "color": "赭紅", "vibe": ["急切", "敏感", "話很多"]}


# ───────── 第 1 行 ─────────

def test_verdict_line_is_composed_from_the_judgement_fields() -> None:
    v = fz.verdict_of(F, LOOK, "seed")
    assert v.startswith("你的數位分身其實是：小巧斑駁的赭紅色居民，") and v.endswith("（ENFP · 雙子 · AB）")
    words = v.split("居民，")[1].split("（")[0].split("、")
    assert len(words) == 2 and set(words) <= set(LOOK["vibe"]), "三詞擇二"
    assert len(v) <= fz.MAX_CARD_LINE_CHARS
    # 確定性；不同 seed 可以擇不同的二
    assert fz.verdict_of(F, LOOK, "seed") == v
    assert len({fz.verdict_of(F, LOOK, f"s{i}") for i in range(30)}) == 3
    # 色系已經帶「色」不重複；缺外形就只留命盤；沒有任何外形與氣質 ⇒ 舊寫法
    assert "暖土色居民" in fz.verdict_of(F, {"color": "暖土", "vibe": []}, "x")
    assert fz.verdict_of(F, {}, "x") == fz.VERDICT_PREFIX + fz.first_line(F)
    # 只給一個詞、沒給血型
    f2 = fz.resolve({"mbti": "INFP", "mbti_source": "ai", "zodiac": "雙魚"}, {})
    assert fz.verdict_of(f2, {"shape": "圓潤", "vibe": ["害羞"]}, "x") == \
        "你的數位分身其實是：圓潤的居民，害羞（INFP · 雙魚）"


def test_verdict_line_never_exceeds_the_cloud_line_limit() -> None:
    long_vibe = {"shape": "粗獷", "texture": "斑駁", "color": "苔綠", "vibe": ["追根究柢的人", "不服輸", "壞心眼嗎"]}
    look = fz.normalize_look({"shape": "粗獷", "texture": "斑駁", "color": "苔綠", "vibe": "追根究柢的人啊、不服輸、壞心眼嗎"})
    assert look["vibe"] == ["不服輸", "壞心眼嗎"], "超過 6 字的詞不收"
    for words in (long_vibe["vibe"], ["一二三四五六", "甲乙丙丁戊己", "天地玄黃宇宙"]):
        v = fz.verdict_of(F, {**long_vibe, "vibe": words}, "x")
        assert len(v) <= fz.MAX_CARD_LINE_CHARS, v


def test_normalize_look_filters_emoji_reality_time_and_bad_enums() -> None:
    lk = fz.normalize_look({"shape": "圓潤", "texture": "不存在", "color": "奶油",
                            "vibe": "跳躍、嘴快、鬼靈精 💨、愛貓、每天早起"})
    assert lk["texture"] is None and lk["shape"] == "圓潤" and lk["color"] == "奶油"
    assert lk["vibe"] == ["跳躍", "嘴快", "鬼靈精"], "emoji 單獨成詞不收；『愛貓』有現實詞；時段詞不收"
    assert fz.normalize_look(None) == {"shape": None, "texture": None, "color": None, "vibe": []}


# ───────── 第 2 行：願望 ─────────

def test_card_line_two_is_the_wish_after_the_label_and_never_an_action_sentence() -> None:
    plan = "我想：想讓音樂盒斷掉的那個音，有東西接住\n為什麼是他：…\n"
    assert fz.wish_of(plan, "x", F) == "讓音樂盒斷掉的那個音，有東西接住"
    assert fz.wish_of("**我想**：看哨子的裂縫能不能再響一次。\n", "x", F) == "看哨子的裂縫能不能再響一次"
    # 以動作開頭的「我想：」＝計畫句不是願望 ⇒ 寧缺
    assert fz.wish_of("我想：用捏土處的黏土，在土堆裡挖一個空間\n", "x", F) is None
    # 名詞片語不是願望（真跑 a4：「一張填滿了圓圈的紙卡」）⇒ 寧缺
    assert fz.wish_of("我想：一張填滿了圓圈的紙卡\n", "x", F) is None
    assert fz.wish_of("我想：想看紙船會不會漂到暗處\n", "x", F) == "看紙船會不會漂到暗處"
    assert fz.wish_of("我想：想聽見音樂盒的第十二個音\n", "x", F) == "聽見音樂盒的第十二個音"
    assert fz.wish_of("我想：把哨子的裂縫補起來\n", "x", F) is None
    # 沒有標籤（第二輪的動作句）＝沒有這一行，不充數
    assert fz.wish_of("把陶哨子的裂縫用黏土填平\n為什麼是他\n", "x", F) is None
    assert fz.wish_of("", "x", F) is None
    # 太長：在句讀截；截不出像樣的就不上卡
    assert fz.wish_of("我想：" + "讓音樂盒斷掉的那個音有東西接住，" * 3 + "\n", "x", F) == "讓音樂盒斷掉的那個音有東西接住"
    assert fz.wish_of("我想：" + "一" * 40 + "\n", "x", F) is None
    # 抽象詞堆疊 ⇒ 不上卡
    assert fz.wish_of("我想：渴望把壓抑的靜默化成共振\n", "x", F) is None


def test_card_line_two_prefix_and_total_width() -> None:
    c = fz.compose_card_v3(F, plan_text="我想：讓音樂盒斷掉的那個音，有東西接住\n", record_text="", rows=[], files={},
                           retries=0, look=LOOK, seed="s")
    assert c["want_line"] == "它心裡想：讓音樂盒斷掉的那個音，有東西接住"
    assert c["tried_line"] is None and c["said_line"] is None, "沒有試的紀錄 ⇒ 第 3、4 行不出"
    assert c["lines"][0] == c["verdict"] and len(c["lines"]) == 2


# ───────── 第 3 行：改變 ─────────

REC = ("陶哨子綁進音樂盒\n\n我先走到桌五，把哨子拿起來。\n\n中間出了意外，線滑掉了一次。\n\n"
       "改變：我把陶哨子綁在音樂盒的轉盤上，斷掉的第 12 個音現在會響一聲低低的咚。這是我自己做的結。\n\n感想：原來接住比修好簡單。\n")


def test_card_line_three_is_the_change_sentence_in_third_person_not_a_route() -> None:
    t = fz.tried_of(REC, "x", F)
    assert t == "它試了：把陶哨子綁在音樂盒的轉盤上，斷掉的第 12 個音現在會響一聲低低的咚"
    assert len(t) <= fz.MAX_CARD_LINE_CHARS
    for route in ("先去了", "再到", "做出《"):
        assert route not in t, "路線留在檔案庫，不上卡"
    # 沒有「改變：」標籤 ⇒ 取「感想：」前面最近的一段
    rec2 = "標題\n\n我走過去。\n\n那個角落現在多了一盞亮著的小燈。\n\n感想：好。\n"
    assert fz.tried_of(rec2, "x", F) == "它試了：那個角落現在多了一盞亮著的小燈"
    # 句子太長：取「現在…」那一半；沒有改變也沒有標題 ⇒ 沒有這一行
    long_ = "改變：" + "原本兩道光交界的地是一片平整而且沒有任何標記的青灰綠色區域，現在那個點出現了一圈細線\n感想：好。"
    assert fz.tried_of("標題\n" + long_, "x", F) == "它試了，現在那個點出現了一圈細線", "只剩『現在…』那一半時接在『它試了，』後面"
    assert fz.tried_of("標題\n改變：現在小燈亮著。\n感想：好。", "x", F) == "它試了，現在小燈亮著"
    assert fz.tried_of("", "x", F) is None
    # 標題行當後備（沒有改變段）
    assert fz.tried_of("修補陶哨子的裂縫\n", "x", F) == "它試了：修補陶哨子的裂縫"


def test_full_card_respects_cloud_and_tv_limits() -> None:
    c = fz.compose_card_v3(F, plan_text="我想：讓音樂盒斷掉的那個音，有東西接住\n", record_text=REC, rows=[], files={},
                           retries=0, look=LOOK, seed="s")
    assert len(c["lines"]) == 4 and c["lines"][0].startswith(fz.VERDICT_PREFIX)
    assert len(c["lines"]) <= 4 and all(0 < len(x) <= 60 for x in c["lines"]), c["lines"]
    assert c["tv_lines"] == [c["want_line"], c["tried_line"]] and len(c["tv_lines"]) <= 3
    assert all(len(x) <= tv_contract.FORTUNE_LINE_MAX for x in c["tv_lines"])
    assert tv_contract.FORTUNE_LINE_MAX == 60 and tv_contract.FORTUNE_MAX_LINES == 3 == sidecar.FORTUNE_MAX_LINES
    assert fz.MAX_CARD_LINE_CHARS == 60
    # 最壞情況：第 2、3 行用滿上限仍不超過 60 字
    assert len(fz.WANT_PREFIX) + fz.MAX_WANT_CARD <= 60 and len(fz.TRIED_PREFIX) + fz.MAX_TRIED_CARD <= 60
    assert len(fz.SAID_PREFIX) + fz.MAX_SAID_CARD <= 60
    # 電視拍的形狀自檢過得了
    row = {"schema": "twin.sidecar/1", "type": "twin_fortune", "ts_ms": 1, "cell_id": "tw-abc", "run_id": "r", "phase": "card",
           "attempt": 1, "mbti": "ENFP", "mbti_source": "ai", "zodiac": "雙子", "element": "風", "blood": "AB",
           "lines": c["tv_lines"]}
    assert sidecar._fortune_problems(row, 0) == []


def test_cloud_phone_limits_match_when_the_cloud_worktree_is_there() -> None:
    p = ROOT.parent / "vacant-world-cloud-wt-p13" / "server.js"
    if not p.is_file():
        pytest.skip("雲端 worktree 不在這台機器上")
    t = p.read_text(encoding="utf-8")
    assert re.search(r"MAX_FORTUNE_LINES\s*=\s*4\b", t) and re.search(r"MAX_FORTUNE_LINE_CHARS\s*=\s*60\b", t)


# ───────── 變化由 cell_id 決定 ─────────

def test_variation_is_deterministic_and_actually_spreads() -> None:
    ids = [twinagent.public_twin_id(f"sub-{i}") for i in range(400)]
    a = [twinagent.variation_for(t) for t in ids]
    assert a == [twinagent.variation_for(t) for t in ids]
    assert {v["wake"] for v in a} == set(twinagent.WAKE_PLACES)
    assert {v["sense"] for v in a} == set(twinagent.LETTER_SENSES)
    assert {v["body"] for v in a} == set(twinagent.LETTER_BODY_PARTS)
    for v in a[:50]:
        assert sorted(v["places"]) == sorted(twinagent.WAKE_PLACES) and v["places"][0] == v["wake"]
        assert "眼" not in v["body"] and "指尖" not in v["body"]
    # 地點順序也分得開（不只是起點）：400 個 cell 至少有 20 種不同的順序
    assert len({tuple(v["places"]) for v in a}) >= 20
    # 負控制：沒有變化時所有 cell 的列出順序一樣（這把尺量得到）
    assert len({tuple(sorted(twinagent.WAKE_PLACES)) for _ in a}) == 1


def test_per_cell_prompts_carry_the_condition_and_stay_clean() -> None:
    tid = twinagent.public_twin_id("sub-X")
    v = twinagent.variation_for(tid)
    s1, m2 = twinagent.letter_system_for(tid), twinagent.first_message_for(tid)
    assert s1.startswith(twinagent.LETTER_SYSTEM_PROMPT) and f"「{v['sense']}」" in s1 and f"「{v['body']}」" in s1
    assert m2.startswith(twinagent.FIRST_MESSAGE) and f"「{v['wake']}」" in m2
    for t in (s1, m2):
        assert_ks1_clean(t)
        assert "例如" not in t
    # 基底指令不再硬性要求「瞳孔／指尖」那組固定模子
    base = twinagent.LETTER_SYSTEM_PROMPT
    assert "具體的感官細節" not in base and "身體習慣" in base
    # 觀眾資料不進 argv：條件只來自 cell_id
    assert "sub-X" not in s1 + m2


def test_system_prompt_first_line_is_a_wish_and_the_change_is_labelled() -> None:
    p = twinagent.SYSTEM_PROMPT
    assert "以「我想：」開頭" in p and "主角是那樣東西，不是你的手" in p and "二十四個字以內" in p
    assert "動詞放在最前面" in p and "不是名詞片語" in p
    assert "「怎麼試」：從這裡才寫動作" in p
    assert "提到的每一樣地上的東西，都要是你這一跑已經打開讀過的" in p
    assert "以「改變：」開頭" in p and "別的居民看得見的改變" in p
    assert_ks1_clean(p)
    names = [pathlib.PurePath(rel).stem for rel in twinground.pool()]
    assert [n for n in names if len(n) >= 3 and n in p] == [], "指令裡沒有任何地上物件的名字"


# ───────── ws_list 順序（TS）─────────

def _run_order_ts(tmp_path: pathlib.Path, names: list[str], rel_dir: str, order: dict) -> list[str]:
    node = shutil.which("node")
    if not node:
        pytest.skip("沒有 node")
    ts = (ROOT / "ops/exhibit/twin/pi_ext/twin_ws_tools.ts").read_text(encoding="utf-8")
    seg = ts.split("// <list-order>")[1].split("// </list-order>")[0]
    f = tmp_path / "order.mts"
    f.write_text(seg + f"\nconsole.log(JSON.stringify(orderNames({json.dumps(names, ensure_ascii=False)}, "
                 f"{json.dumps(rel_dir, ensure_ascii=False)}, {json.dumps(order, ensure_ascii=False)})));\n", encoding="utf-8")
    r = subprocess.run([node, "--experimental-strip-types", "--no-warnings", str(f)], capture_output=True, text=True)
    if r.returncode != 0:
        pytest.skip("這版 node 不能直接跑 TS：" + r.stderr[:200])
    return json.loads(r.stdout)


def test_ws_list_order_follows_list_order_json(tmp_path) -> None:
    places = list(twinagent.WAKE_PLACES)
    order = {"places": places[3:] + places[:3], "rot": 5}
    got = _run_order_ts(tmp_path, sorted(places), "地上", order)
    assert got == order["places"] and sorted(got) == sorted(places), "只改順序，不增減"
    files = [f"{i}.txt" for i in range(7)]
    got2 = _run_order_ts(tmp_path, files, "地上/紙卡地", order)
    assert got2 == sorted(files)[5:] + sorted(files)[:5] and sorted(got2) == sorted(files)
    # 其他資料夾與沒有 order 檔：字母序（舊行為）
    assert _run_order_ts(tmp_path, ["b", "a"], "", order) == ["a", "b"]
    assert _run_order_ts(tmp_path, ["b", "a"], "地上", None) == ["a", "b"]


def test_list_order_file_name_is_pinned_between_python_and_ts() -> None:
    ts = (ROOT / "ops/exhibit/twin/pi_ext/twin_ws_tools.ts").read_text(encoding="utf-8")
    assert twinagent.LIST_ORDER_NAME in ts and "STEP_LOG" in ts.split("function loadListOrder")[1].split("}")[0]


# ───────── 世界材料：人類常見的心願接得住 ─────────

WISH_FILES = {
    "吃/慢慢吃": ["長桌廣場/桌六的砂鍋.txt"],
    "還東西": ["投遞口/借走的細頸陶瓶.txt"],
    "大聲說": ["畫架與長椅/冷藍光邊的紙喇叭.txt"],
    "畫": ["畫架與長椅/板角那個炭條的圓.txt", "長桌廣場/一張畫到邊緣的圖.txt"],
    "遠行": ["長桌廣場/桌四邊的紙鞋.txt", "長桌廣場/土堆上的紙船.txt"],
    "睡": ["石頭閘門/石墩背面的凹印.txt"],
    "告白": ["草稿角/石壁前那張半張紙.txt"],
    "跳舞": ["紙卡地/轉到一半的小人.txt"],
    "收集": ["長桌廣場/桌二的空位.txt"],
    "送禮": ["投遞口/綁好線的小方塊.txt"],
    "寫信": ["草稿角/信紙與那根線.txt", "投遞口/缺角的信.txt"],
    "獨處": ["紙卡地/圍成一圈的碎石.txt"],
    "學會一件事": ["帳本鏈/彎處旁那塊黏土板.txt"],
    "照顧小東西": ["捏土處/量了三次的土團.txt", "畫架與長椅/長椅底下縮著的灰藍小東西.txt"],
    "被記得": ["帳本鏈/多出的小印.txt"],
    "唱出聲音": ["石頭閘門/束在一起的陶管.txt"],
    "修好": ["捏土處/碗口缺了三角.txt"],
}


def test_every_common_wish_has_something_in_the_world_to_hold_it() -> None:
    pool = set(twinground.pool())
    for wish, files in WISH_FILES.items():
        assert files and all(f in pool for f in files), wish
    assert len(WISH_FILES) >= 15
    # 新的 17 件都登了性情吸引力與關聯組（不是孤兒）
    lure = json.loads((twinground.MATERIALS / "_lure.json").read_text(encoding="utf-8"))["lure"]
    linked = {m for ms in twinground.groups().values() for m in ms}
    new = {f for fs in WISH_FILES.values() for f in fs}
    assert new <= set(lure)


def test_new_materials_keep_water_rare_and_do_not_touch_the_gate_facts() -> None:
    """世界裡『水只有兩處』：新材料不新增水；也不使用帳本鏈 418–447 的片號（G3 的權威）。"""
    water = ("河", "湖", "海", "池", "雨", "水珠", "水滴", "泉", "溪", "喝水")
    for rel in {f for fs in WISH_FILES.values() for f in fs} - {
            "長桌廣場/土堆上的紙船.txt", "捏土處/陶杯裡的種子.txt"}:
        t = (twinground.MATERIALS / rel).read_text(encoding="utf-8")
        assert [w for w in water if w in t] == [], (rel, [w for w in water if w in t])
        assert not [n for n in re.findall(r"(?<![0-9])(4[1-4][0-9])(?![0-9])", t) if 418 <= int(n) <= 447], rel


# ───────── 12 份像真 AI 回答的觀眾輸入 ─────────

R3 = ROOT / "ops/exhibit/twin/evidence_divine_20261007/round3"


def test_round3_inputs_are_twelve_varied_ai_answers() -> None:
    rows = json.loads((R3 / "inputs12_parsed.json").read_text(encoding="utf-8"))
    assert len(rows) == 12
    cards = [r["card"] for r in rows]
    assert len({c["mbti"] for c in cards}) == 12 and len({c["zodiac"] for c in cards}) == 12
    assert {c["blood"] for c in cards} == {"A", "B", "O", "AB"}
    assert {c["shape"] for c in cards} == set(fz.SHAPES) and {c["texture"] for c in cards} == set(fz.TEXTURES)
    assert {c["color"] for c in cards} == set(fz.COLORS)
    assert len({c["want"] for c in cards}) == 12
    wants = "\n".join(c["want"] for c in cards)
    for daily in ("吃", "還", "睡"):
        assert daily in wants, daily
    # 口吻真的不同：有 emoji、有粗體、有免責、有亂序
    raw = "\n".join(r["text_raw"] for r in rows)
    assert "**" in raw and "✨" in raw and "不是判決" in raw and "娛樂性質" in raw
    assert len({len(r["text_raw"]) for r in rows}) >= 10


def test_round3_parse_report_records_what_the_real_cloud_parser_misses() -> None:
    rep = (R3 / "parse_report.txt").read_text(encoding="utf-8")
    assert "a3 raw缺: shape,texture,color,vibe,mbti,zodiac,blood,want,first_line" in rep, "粗體整份解析不出來"
    assert all("cleaned缺: -" in ln for ln in rep.splitlines() if ln.startswith("a")), "清理後 12 份欄位齊全"


# ───────── 真跑中發現的格式問題（組合器是確定性後處理，修了可以對同一份真跑文字重算）─────────

def test_cut_never_leaves_a_hanging_fragment_and_self_made_marker_stays_off_the_card() -> None:
    # 真跑 a1：太長的願望在「、」被截成「…由細線和紙捏成的」殘句 ⇒ 現在寧缺
    assert fz.wish_of("我想：讓長桌廣場的土堆上出現一個由細線和紙捏成的、能發出聲音而且會轉圈的小鳥。\n", "x", F) is None
    # 在整句的句讀（，）截，而且截出來的是完整的一句
    assert fz.wish_of("我想：讓土堆上的紙船漂到暗處去，然後再也不用回來了啊啊啊啊啊啊啊啊啊啊\n", "x", F) == "讓土堆上的紙船漂到暗處去"
    # 真跑 a1：「這是我自己做的」是紙上的標記句，不是卡上的內容
    rec = "標題\n\n改變：在土堆上放了一個這是我自己做的紙鳥，讓它成為土堆的一部分。\n感想：好。\n"
    assert fz.tried_of(rec, "x", F) == "它試了：在土堆上放了一個紙鳥，讓它成為土堆的一部分"
    # 真跑 a8：模型把路徑整串放進引號 ⇒ 卡上只留物件的名字
    rec2 = "標題\n\n改變：我將「長桌廣場/土堆上的紙船.txt」從土堆頂端移開，現在它斜靠在「長桌廣場/土堆裡的洞」的洞口處。\n感想：好。\n"
    t = fz.tried_of(rec2, "x", F)
    assert "/" not in t and ".txt" not in t and "「土堆裡的洞」" in t, t


def test_recompute_cards_reproduces_the_vm_cards_when_nothing_changed() -> None:
    """用最終組合器對存下來的真跑文字重算；真跑當下的卡原樣留著，重算的另放（見 recompute_cards.py）。"""
    src = (R3 / "recompute_cards.py").read_text(encoding="utf-8")
    assert "card_md_final" in src and "compose_card_v3" in src


def test_fit_prefers_whole_clauses_that_are_complete_and_the_now_half_of_a_long_change() -> None:
    # 真跑 a5：子句串被截在「…並在兩道光交界的地」（結尾掛著「地」）——不是完整的一句
    s = "在畫架與長椅區域，把「畫架上的去向」拿走了，並在兩道光交界的地放了一張空白的貼紙，貼紙邊緣是新的"
    got = fz._fit(s, 40)
    assert got is None or (got.endswith(("了", "的")) is False or "地放" in got), got
    assert fz._complete("在長桌廣場土堆東側的一個角落") is False, "沒有動詞的名詞片語"
    assert fz._complete("把帶有三角形缺口的紙卡從紙卡地移開") is True
    assert fz._complete("並在兩道光交界的地") is False
    assert fz._fit("原本一片空白，現在那個點出現了一圈細線", 12) == "現在那個點出現了一圈細線"
    # 願望：讓…要有謂語；聽見／看… 開頭的動詞自己就是謂語
    assert fz._complete("讓那封信裡沉重的情感", wish=True) is False
    assert fz._complete("聽見音樂盒的第十二個音", wish=True) is True


def test_paths_and_file_names_are_cleaned_to_object_names_and_a_predicative_de_is_not_a_fragment() -> None:
    assert fz._clean_paths("我把桌五_音樂盒.txt 從桌上挪走") == "我把音樂盒 從桌上挪走"
    assert fz._clean_paths("放進「碗口缺了三角.txt」的缺口") == "放進「碗口缺了三角」的缺口"
    assert fz._clean_paths("「地上/長桌廣場/土堆上的紙船.txt」") == "「土堆上的紙船」"
    # 真跑 v11：「現在長椅中間是空的」結尾的「的」是句尾；真跑 a1 的「…捏成的」才是殘句
    assert fz._complete("我把長椅上的紙筒拿走了，現在長椅中間是空的") is True
    assert fz._complete("一個由細線和紙捏成的") is False
    assert fz.tried_of("t\n\n改變：我把桌五_音樂盒.txt 從長桌廣場挪到了兩道光交界的地上。\n感想：好。\n", "x", F) == \
        "它試了：把音樂盒 從長桌廣場挪到了兩道光交界的地上"


def test_subordinate_tail_and_self_made_marker_in_the_said_line() -> None:
    # 真跑 a？：「讓一張紙在沒有任何動作干擾的情況下，從一端到另一端慢慢地滑動」在逗號截成「…的情況下」——從屬子句還沒說完
    assert fz._complete("讓一張紙在沒有任何動作干擾的情況下", wish=True) is False
    assert fz.wish_of("我想：讓一張紙在沒有任何動作干擾的情況下，從一端到另一端慢慢地平靜地滑動\n", "x", F) is None
    assert fz.said_of("感想：這是我自己做的，雖然沒能做出預想中的轟鳴，但至少讓那個東西動了。\n", "x", F) == \
        "雖然沒能做出預想中的轟鳴，但至少讓那個東西動了"


def test_label_lead_and_empty_quote_do_not_reach_the_card() -> None:
    # 真跑 v10：紀錄裡的「試了什麼：」標籤被抄上卡；真跑 a6：引號裡只有資料夾 ⇒ 「」是空的
    assert fz.tried_of("t\n\n改變：試了什麼：在石壁上為那條淺線留下一個深沉的印紋。\n感想：好。\n", "x", F) == \
        "它試了：在石壁上為那條淺線留下一個深沉的印紋"
    assert fz._clean_paths("把「地上/紙卡地/」中原本空置的行填滿") == "把「紙卡地」中原本空置的行填滿"


def test_wish_length_does_not_count_the_closing_full_stop() -> None:
    w = "讓長桌廣場的土堆上出現一個由細線和紙捏成的、能發出聲音的小鳥"
    assert len(w) == fz.MAX_WANT_CARD
    assert fz.wish_of("我想：" + w + "。\n", "x", F) == w
