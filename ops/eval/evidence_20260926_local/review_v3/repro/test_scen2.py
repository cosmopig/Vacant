import json, pathlib, sys
sys.path.insert(0, "/home/user/Vacant")
sys.path.insert(0, "/home/user/Vacant/tests")
from test_zero_budget import Pi, proj, _install  # noqa
from vacant_network.trace.recorder import Recorder


def test_subdir_relative_output(proj):
    (proj / ".git").mkdir()
    sub = proj / "sub"
    sub.mkdir()
    (sub / "in.csv").write_text("a\n1\n")
    a = Pi(sub)
    a.ask("Read in.csv and write the total to out.txt.")
    a.bash("cat in.csv", "a\n1\n")
    a.bash("echo 1 > out.txt", "", write={"sub/out.txt": "1\n"}) if False else None
    (sub / "out.txt").write_text("1\n")
    a.n += 1
    inp = {"command": "echo 1 > out.txt"}
    a.ev("pre_tool", tool="bash", call_id="w", input=inp)
    a.ev("post_tool", tool="bash", call_id="w", input=inp, output="")
    d = a.turn(13)
    print("NUDGE:", d)
    a.ev("session_end", reason="quit", turn=15, budget=15)
    print((Recorder(proj).dir / "delivery.md").read_text())
