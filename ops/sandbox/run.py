"""配對實驗的行程層：隔離工作區、安裝、原始紀錄與獨立評分。"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import random
import re
import shutil
import signal
import subprocess
import sys
import tarfile
import time
import urllib.request

if __package__ in (None, ''):
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from ops.sandbox.score import TASKS, score

REPO = Path(__file__).resolve().parents[2]
UNKNOWN = 'UNKNOWN'


def rows(path):
    if not Path(path).exists():
        return []
    result = []
    for line in Path(path).read_text(errors='replace').splitlines():
        try:
            result.append(json.loads(line))
        except ValueError:
            pass
    return result


def calls(path, tag):
    found = [r for r in rows(path) if r.get('run_tag') == tag]
    usage = [r.get('usage') or {} for r in found]
    return {'model_calls': len(found) if found else UNKNOWN,
            'prompt_tokens': sum(u['prompt_tokens'] for u in usage)
            if usage and all('prompt_tokens' in u for u in usage) else UNKNOWN,
            'completion_tokens': sum(u['completion_tokens'] for u in usage)
            if usage and all('completion_tokens' in u for u in usage) else UNKNOWN,
            'model_errors': sum(bool(r.get('error')) or r.get('status', 200) >= 400 for r in found)}


def disk(path):
    return sum(p.stat().st_size for p in Path(path).rglob('*') if p.is_file() and not p.is_symlink())


def leftovers(ws):
    result = dict(pytest_cache=0, logs=0, other=0)
    for p in ws.rglob('*'):
        if not p.is_file() or p.is_symlink():
            continue
        key = 'pytest_cache' if '.pytest_cache' in p.parts else 'logs' if p.suffix in ('.log', '.jsonl') else 'other'
        result[key] += p.stat().st_size
    return result


def claim_success(text):
    return bool(re.search(r'\b(done|completed|fixed|all tests pass(?:ed)?|\d+ passed)\b', text, re.I))


def contamination_evidence(work):
    markers = (str(TASKS.resolve()), 'ops/sandbox/tasks', '/hidden/', '/solution/', '_hidden')
    evidence = []
    for name in ('events.jsonl', 'stderr.txt', 'diff.patch'):
        path = work / name
        if not path.exists():
            continue
        for number, line in enumerate(path.read_text(errors='replace').splitlines(), 1):
            matched = [marker for marker in markers if marker in line]
            if matched:
                start = min(line.index(marker) for marker in matched)
                evidence.append(dict(source=name, line=number, markers=matched,
                                     excerpt=line[max(0, start-100):start+500]))
    return evidence


def terminate_tree(pid):
    parents = {}
    for entry in Path('/proc').glob('[0-9]*/status'):
        try:
            ppid = next(line.split()[1] for line in entry.read_text().splitlines() if line.startswith('PPid:'))
            parents[int(entry.parent.name)] = int(ppid)
        except (OSError, StopIteration):
            continue
    descendants = {pid}
    while True:
        expanded = descendants | {p for p, parent in parents.items() if parent in descendants}
        if expanded == descendants:
            break
        descendants = expanded
    for child in sorted(descendants - {pid}, reverse=True):
        try:
            os.kill(child, signal.SIGKILL)
        except ProcessLookupError:
            pass
    try:
        os.killpg(pid, signal.SIGKILL)
    except ProcessLookupError:
        pass


def execute(cmd, cwd, env, timeout, stdout, stderr):
    with Path(stdout).open('wb') as out, Path(stderr).open('wb') as err:
        proc = subprocess.Popen(cmd, cwd=cwd, env=env, stdin=subprocess.DEVNULL,
                                stdout=out, stderr=err, start_new_session=True)
        try:
            return proc.wait(timeout=timeout), False
        except subprocess.TimeoutExpired:
            terminate_tree(proc.pid)
            proc.wait()
            return proc.returncode, True
        except BaseException:
            terminate_tree(proc.pid)
            proc.wait()
            raise


def gate_suite(task, dest):
    """vrun 接 check_*/main，不接 pytest；包裝的內容僅有原始可見測試。"""
    dest.mkdir()
    source = (task / 'repo/tests/test_visible.py').read_text()
    code = (
        'import os, pathlib, subprocess, tempfile\n\n'
        'def main():\n'
        '    with tempfile.TemporaryDirectory() as temp:\n'
        '        path = pathlib.Path(temp) / "test_public.py"\n'
        f'        path.write_text({source!r})\n'
        '        driver = "import sys,pytest; sys.path.insert(0,sys.argv.pop(1)); raise SystemExit(pytest.main(sys.argv[1:]))"\n'
        f'        run = subprocess.run([{sys.executable!r}, "-I", "-c", driver, os.getcwd(), str(path), "-q", "-p", "no:cacheprovider", "--noconftest"], capture_output=True, text=True, timeout=10, env={{**os.environ, "PYTEST_DISABLE_PLUGIN_AUTOLOAD": "1"}})\n'
        '        assert run.returncode == 0, run.stdout + run.stderr\n'
    )
    (dest / 'test_visible.py').write_text(code)


def final_messages(path):
    messages = []
    model_error = False
    for event in rows(path):
        message = event.get('message', {})
        if event.get('type') == 'message_end' and message.get('role') == 'assistant':
            if message.get('stopReason') in ('error', 'aborted'):
                model_error = True
            if not any(c.get('type') == 'toolCall' for c in message.get('content', [])):
                text = '\n'.join(c.get('text', '') for c in message.get('content', []) if c.get('type') == 'text')
                if text:
                    messages.append(text)
    return messages[-1] if messages else '', model_error


def cell(args, task_id, sample, arm):
    dest = args.out / 'cells' / f'{task_id}-s{sample}-{arm}'
    if (dest / 'result.json').exists():
        return json.loads((dest / 'result.json').read_text()), True
    dest.mkdir(parents=True, exist_ok=True)
    # A partial cell is preserved; restart in a separate fresh attempt directory.
    work = dest / f'work-{time.time_ns()}'
    work.mkdir()
    ws, home, vh = work / 'ws', work / 'home', work / 'vacant'
    home.mkdir()
    vh.mkdir()
    task = TASKS / task_id
    meta = json.loads((task / 'task.json').read_text())
    tag = f'{args.out.name}-{task_id}-s{sample}-{arm}-{time.time_ns()}'
    tag = hashlib.sha256(tag.encode()).hexdigest()[:24]
    result = dict(task=task_id, sample=sample, arm=arm, run_tag=tag,
                  infra_void=False, infra_reason=None, work_dir=str(work),
                  git_sha=args.runtime_git_sha)
    start = time.monotonic()
    env = {'HOME': str(home), 'VACANT_HOME': str(vh), 'PATH': str(Path(sys.executable).parent) + os.pathsep + os.environ['PATH'],
           'PYTHONPATH': str(REPO), 'PYTHONNOUSERSITE': '1', 'LANG': 'C.UTF-8',
           'TMPDIR': str(work), 'PI_OFFLINE': '1'}
    agent_dir = home / '.pi/agent'
    env['PI_CODING_AGENT_DIR'] = str(agent_dir)
    try:
        shutil.copytree(task / 'repo', ws)
        for command in (['git', 'init', '-q'], ['git', 'add', '-A'],
                        ['git', '-c', 'user.name=Sandbox', '-c', 'user.email=sandbox@localhost',
                         '-c', 'commit.gpgsign=false', 'commit', '-qm', 'fixture']):
            subprocess.run(command, cwd=ws, env=env, check=True, capture_output=True)
        agent_dir.mkdir(parents=True)
        config = json.loads((Path(__file__).parent / 'runtime/models.json.tmpl').read_text().replace('${RUN_TAG}', tag))
        provider = config['providers']['ollama']
        provider['baseUrl'] = args.proxy_base.rstrip('/') + f'/t/{tag}/v1'
        provider['models'][0]['id'] = args.model
        (agent_dir / 'models.json').write_text(json.dumps(config, indent=2))
        if arm == 'C':
            rc, timed = execute([sys.executable, '-m', 'vacant_network.cli', 'install', '--agents', 'pi'],
                                ws, env, 60, work / 'install.stdout', work / 'install.stderr')
            if rc or timed:
                raise RuntimeError('vacant install failed')
        prompt = meta['prompt']
        if args.agent_cmd:
            agent = [v.replace('{prompt}', prompt) for v in json.loads(args.agent_cmd)]
            if not any('{prompt}' in v for v in json.loads(args.agent_cmd)):
                agent.append(prompt)
        else:
            agent = ['pi', '--mode', 'json', '-p', '--no-session', '--offline', '--no-skills',
                     '--no-context-files', '--no-prompt-templates', '--tools', 'read,bash,edit,write,grep,find,ls',
                     '--provider', 'ollama', '--model', args.model, prompt]
        command = agent
        if arm == 'G':
            agent[-1] += '{VACANT_FEEDBACK}'
            gate_suite(task, work / 'suite')
            command = [sys.executable, '-m', 'vacant_network.cli', 'run', '--workspace', str(ws),
                       '--suite', str(work / 'suite'), '--run-dir', str(work / 'gate'),
                       '--sandbox', 'none', '--vacant', '1', '--retry', 'revise', '--max-attempts', '3',
                       '--feedback-into', 'both', '--timeout', str(args.timeout), '--', *agent]
        (work / 'command.json').write_text(json.dumps(command, indent=2))
        rc, timed = execute(command, ws, env, args.timeout, work / 'stdout.jsonl', work / 'stderr.txt')
        shutil.copyfile(work / 'stdout.jsonl', work / 'events.jsonl')
        final, model_error = final_messages(work / 'events.jsonl')
        (work / 'final.txt').write_text(final)
        result.update(exit_code=rc, claim_success=claim_success(final), final_text=final)
        gate = next(iter((work / 'gate').glob('run_*.json')), None) if arm == 'G' else None
        summary = json.loads(gate.read_text()) if gate else {}
        hook_events = rows(vh / 'intake/hooks/events.jsonl')
        feedback = sum(e.get('action') == 'continue' and e.get('kind') == 'stop' for e in hook_events)
        result.update(gate_attempts=summary.get('attempts_used'),
                      gate_requests_seen=summary.get('requests_seen'),
                      vacant_feedback_rounds=summary.get('attempts_used', 1) - 1 if arm == 'G' else feedback,
                      hook_records=len(hook_events), hook_errors=len(rows(vh / 'intake/hooks/errors.jsonl')))
        result.update(calls(args.call_log, tag))
        if timed or model_error or result['model_errors'] or (rc != 0 and not (arm == 'G' and rc == 20)):
            result.update(infra_void=True, infra_reason='timeout' if timed else 'model/process error')
        if arm == 'G' and (summary.get('infra_void') or any(
                a.get('agent_timed_out') or a.get('agent_rc') not in (0, None)
                for a in summary.get('attempts', []))):
            result.update(infra_void=True, infra_reason='gate agent timeout/process error or infra_void')
        result['score'] = score(task, ws)
        if result['score']['error'] and ('timeout' in result['score']['error'] or not result['score']['n_failed']):
            result.update(infra_void=True, infra_reason='scorer: ' + result['score']['error'])
        result['hidden_pass'] = result['score']['hidden_pass'] and not result['infra_void']
        result['visible_pass'] = result['score']['visible_pass'] and not result['infra_void']
        subprocess.run(['git', 'add', '-A'], cwd=ws, env=env, check=True, capture_output=True)
        diff = subprocess.run(['git', 'diff', '--cached', 'HEAD', '--'], cwd=ws, env=env, capture_output=True, text=True)
        (work / 'diff.patch').write_text(diff.stdout)
        with tarfile.open(work / 'workspace.tar.gz', 'w:gz') as archive:
            for root, dirs, files in os.walk(ws, followlinks=False):
                dirs[:] = [d for d in dirs if d != '.git' and not (Path(root) / d).is_symlink()]
                for name in files:
                    p = Path(root) / name
                    if p.is_file() and not p.is_symlink():
                        archive.add(p, arcname=str(p.relative_to(ws)), recursive=False)
        result.update(vacant_home_bytes=disk(vh), trace_bytes=disk(vh / 'trace'), workspace_bytes=leftovers(ws))
    except Exception as exc:
        result.update(infra_void=True, infra_reason=f'{type(exc).__name__}: {exc}', hidden_pass=False, visible_pass=False)
        result.update(calls(args.call_log, tag))
    result['wall_s'] = round(time.monotonic() - start, 3)
    result['contamination_evidence'] = contamination_evidence(work)
    result['contamination'] = bool(result['contamination_evidence'])
    result['false_success'] = bool(result.get('claim_success') and not result['hidden_pass'])
    temp = dest / 'result.tmp'
    temp.write_text(json.dumps(result, indent=2))
    temp.replace(dest / 'result.json')
    with (args.out / 'progress.jsonl').open('a') as stream:
        stream.write(json.dumps(result) + '\n')
    return result, False


def version(command):
    try:
        return subprocess.run(command, capture_output=True, text=True, timeout=10).stdout.strip()
    except (OSError, subprocess.TimeoutExpired):
        return UNKNOWN


def runtime_identity(args):
    import vacant_network
    model_digest = UNKNOWN
    if not args.agent_cmd:
        try:
            with urllib.request.urlopen('http://127.0.0.1:11434/api/tags', timeout=5) as response:
                model_digest = next((m['digest'] for m in json.load(response)['models'] if m['name'] == args.model), UNKNOWN)
        except (OSError, ValueError):
            pass
    return dict(pi=version(['pi', '--version']), ollama=version(['ollama', '--version']),
                model_digest=model_digest, vacant=vacant_network.__version__,
                git_sha=version(['git', '-C', str(REPO), 'rev-parse', 'HEAD']))


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--arms', nargs='+', choices=['A', 'A2', 'C', 'G'], default=['A', 'A2', 'C', 'G'])
    parser.add_argument('--tasks', nargs='+', default=['all'])
    parser.add_argument('--samples', type=int, default=1)
    parser.add_argument('--seed', type=int, default=20261122)
    parser.add_argument('--out', type=Path, default=Path.home() / 'sandbox-runs' / time.strftime('%Y%m%dT%H%M%S'))
    parser.add_argument('--timeout', type=float, default=900)
    parser.add_argument('--model', default='qwen3:8b')
    parser.add_argument('--proxy-base', default='http://127.0.0.1:18081')
    parser.add_argument('--call-log', type=Path, default=Path.home() / 'sandbox-rt/tagged-calls.jsonl')
    parser.add_argument('--agent-cmd', help='TEST ONLY: JSON argv for a scripted agent; results are L-fake')
    args = parser.parse_args(argv)
    args.out = args.out.expanduser().resolve()
    if args.out == REPO or REPO in args.out.parents:
        parser.error('--out must be outside the repository')
    if args.samples < 1 or args.timeout <= 0:
        parser.error('samples and timeout must be positive')
    task_ids = sorted(p.name for p in TASKS.iterdir()) if args.tasks == ['all'] else args.tasks
    if any(t not in {p.name for p in TASKS.iterdir()} for t in task_ids):
        parser.error('unknown task')
    args.out.mkdir(parents=True, exist_ok=True)
    config = {k: str(v) if isinstance(v, Path) else v for k, v in vars(args).items()}
    meta_path = args.out / 'meta.json'
    identity = runtime_identity(args)
    args.runtime_git_sha = identity['git_sha']
    if meta_path.exists():
        previous = json.loads(meta_path.read_text())
        if previous['config'] != config:
            parser.error('resume configuration differs')
        changed = [key for key, value in identity.items() if previous.get(key) != value]
        if changed:
            parser.error('resume runtime differs: ' + ', '.join(changed) + '; use a fresh --out directory')
    else:
        meta_path.write_text(json.dumps(dict(config=config, task_ids=task_ids, python=sys.version, **identity,
            evidence='L-fake' if args.agent_cmd else 'real-agent'), indent=2))
    rng = random.Random(args.seed)
    for task_id in task_ids:
        for sample in range(1, args.samples + 1):
            arms = list(args.arms)
            rng.shuffle(arms)
            for arm in arms:
                result, skipped = cell(args, task_id, sample, arm)
                print(json.dumps({k: result.get(k) for k in ('task', 'sample', 'arm', 'hidden_pass', 'infra_void', 'wall_s')} | {'skipped': skipped}), flush=True)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
