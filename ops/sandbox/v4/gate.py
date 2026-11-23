"""Export a bank-independent v4 suite; no workspaces or agent sessions are built."""
import json
from pathlib import Path
import shutil

from ops.sandbox.v3 import p2p_runner, patch


WRAPPER = '''from pathlib import Path
import runpy
import json
import os

def main():
    workspace = Path.cwd()
    root = next(p for p in workspace.parents if (p / "gates" / INSTANCE / "selection.json").is_file())
    suite = root / "gates" / INSTANCE
    os.environ.update(json.loads((suite / "selection.json").read_text()).get("runner_environment", {}))
    runpy.run_path(str(suite / "gate_runtime.py"))["check"](workspace, suite, root / INSTANCE)
'''


def write_suite(root, instance, config):
    if Path(instance).name != instance or instance in ('', '.', '..'):
        raise ValueError('invalid instance ID')
    interpreter = Path(config['interpreter'])
    if interpreter.is_absolute() or '..' in interpreter.parts:
        raise ValueError('interpreter must be kit-relative')
    if not config['selectors'] or config['timeout_s'] < 120:
        raise ValueError('frozen P2P selectors and per-instance timeout required')
    suite = Path(root) / 'gates' / instance
    suite.mkdir(parents=True, exist_ok=True)
    for source, name in ((Path(__file__).with_name('gate_runtime.py'), 'gate_runtime.py'),
                         (Path(__file__).with_name('node_runner.py'), 'node_runner.py'),
                         (Path(p2p_runner.__file__), 'p2p_runner.py'),
                         (Path(patch.__file__), 'setup_normalization.py')):
        shutil.copyfile(source, suite / name)
    public = {name: config[name] for name in ('django', 'selectors', 'interpreter', 'timeout_s')}
    public['setup_commands'] = [command for command in config['environment']['commands'] if command.startswith('sed ')]
    public['base_rebuild_commands'] = config.get('base_rebuild_commands', [])
    public['generated_compiled_sources'] = config.get('generated_compiled_sources', {})
    public['nodeid_paths'] = config.get('nodeid_paths', {})
    public['runner_environment'] = config.get('runner_environment', {})
    (suite / 'selection.json').write_text(json.dumps(public, indent=2) + '\n')
    (suite / 'test_gate.py').write_text(WRAPPER.replace('INSTANCE', repr(instance)))
    return suite
