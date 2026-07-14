"""Quick sanity: EvalPlusMBPPLoader must expose a .load() stub."""
from vacant.codebench import EvalPlusMBPPLoader


def test_evalplus_loader_has_load_method():
    """Verification command 2: hasattr(l, 'load') must return True."""
    l = EvalPlusMBPPLoader("/nonexistent")
    assert hasattr(l, "load"), "EvalPlusMBPPLoader must expose a load() stub"


def test_evalplus_loader_load_raises_not_implemented():
    """The .load() stub should also raise NotImplementedError (honest stub)."""
    l = EvalPlusMBPPLoader("/nonexistent")
    try:
        l.load()
        assert False, "load() should have raised NotImplementedError"
    except NotImplementedError:
        pass  # expected
