"""Derive the preregistered v3 candidate patch; never execute handback code."""
import argparse
import json
import os
from pathlib import Path
import re
import shlex
import stat
import subprocess
import tempfile


ARTIFACT_DIRS = {'.git', '.venv', '.envs', 'venv', 'build', 'dist', '__pycache__',
                 '.pytest_cache', '.mypy_cache', '.ruff_cache', '.cache', '.tox', '.nox', '.eggs'}
ARTIFACT_SUFFIXES = {'.pyc', '.pyo', '.so', '.pyd', '.dll', '.dylib', '.o', '.a'}


def _artifact(name):
    return name in ARTIFACT_DIRS or name.endswith(('.egg-info', '.dist-info'))


def _files(root, excluded):
    found = {}
    for directory, dirs, names in os.walk(root, followlinks=False):
        dirs[:] = [name for name in dirs if not _artifact(name)]
        links = [name for name in dirs if (Path(directory) / name).is_symlink()]
        for name in [*names, *links]:
            path = Path(directory) / name
            relative = path.relative_to(root).as_posix()
            if relative in excluded or _artifact(name) or path.suffix in ARTIFACT_SUFFIXES:
                continue
            mode = path.lstat().st_mode
            if stat.S_ISLNK(mode):
                found[relative] = (0o120000, os.fsencode(os.readlink(path)))
            elif stat.S_ISREG(mode):
                found[relative] = (0o100755 if mode & 0o111 else 0o100644, path.read_bytes())
            else:
                raise ValueError('unsupported handback file: ' + relative)
    return found


def _substitution(expression):
    if len(expression) < 4 or expression[0] != 's':
        raise ValueError('unsupported setup substitution')
    delimiter, fields, current, index = expression[1], [], [], 2
    while index < len(expression) and len(fields) < 2:
        char = expression[index]
        if char == '\\' and index + 1 < len(expression):
            following = expression[index+1]
            current.extend([following] if following == delimiter else ['\\', following])
            index += 2
            continue
        if char == delimiter:
            fields.append(''.join(current))
            current = []
        else:
            current.append(char)
        index += 1
    flags = expression[index:]
    if len(fields) != 2 or flags not in ('', 'g'):
        raise ValueError('unsupported setup substitution flags')
    pattern, replacement = fields
    if '[[:' in pattern:
        raise ValueError('unsupported setup character class')
    converted, index = [], 0
    while index < len(pattern):
        char = pattern[index]
        if char == '\\' and index + 1 < len(pattern):
            following = pattern[index+1]
            converted.append(following if following in '()+?|{}' else '\\' + following)
            index += 2
        else:
            converted.append('\\' + char if char in '()+?|{}' else char)
            index += 1
    regex = re.compile(''.join(converted))
    def replace(match):
        result, index = [], 0
        while index < len(replacement):
            char = replacement[index]
            if char == '\\' and index + 1 < len(replacement):
                following = replacement[index+1]
                result.append(match.group(int(following)) if following.isdigit() else following)
                index += 2
            else:
                result.append(match.group(0) if char == '&' else char)
                index += 1
        return ''.join(result)
    return lambda text: '\n'.join(regex.sub(replace, line, count=0 if flags == 'g' else 1)
                                  for line in text.split('\n'))


def normalize_setup(files, commands):
    normalized = dict(files)
    for command in commands:
        if not command.startswith('sed '):
            continue
        tokens = shlex.split(command)
        if len(tokens) != 4 or tokens[:2] != ['sed', '-i']:
            raise ValueError('unsupported tracked setup edit: ' + command)
        name = tokens[3]
        if Path(name).is_absolute() or '..' in Path(name).parts or name not in normalized:
            raise ValueError('setup target absent from base: ' + name)
        mode, data = normalized[name]
        if mode == 0o120000:
            raise ValueError('setup target is a symlink: ' + name)
        normalized[name] = (mode, _substitution(tokens[2])(data.decode('utf-8')).encode('utf-8'))
    return normalized


def derive_patch(base, handback, test_patch='', setup_commands=()):
    base, handback = Path(base), Path(handback)
    if not base.is_dir() or not handback.is_dir():
        raise ValueError('base and handback directories required')
    excluded = {line[6:] for line in test_patch.splitlines() if line.startswith(('--- a/', '+++ b/'))}
    baseline = _files(base, set())
    before = normalize_setup(baseline, setup_commands)
    after = _files(handback, excluded)
    for name, raw in baseline.items():
        if (before[name] != raw and name in after and after[name][0] != 0o120000
                and after[name][1] == raw[1]):
            after[name] = (after[name][0], before[name][1])
    binary = {name for name, (_, data) in [*before.items(), *after.items()] if b'\0' in data}
    before = {name: value for name, value in before.items() if name not in binary and name not in excluded}
    after = {name: value for name, value in after.items() if name not in binary}
    with tempfile.TemporaryDirectory(prefix='sandbox-v3-patch-') as temporary:
        root = Path(temporary)
        repo, blobs = root / 'repo.git', root / 'blobs'
        blobs.mkdir()
        environment = {k: v for k, v in os.environ.items() if not k.startswith('GIT_')}
        environment.update(GIT_CONFIG_GLOBAL=os.devnull, GIT_CONFIG_NOSYSTEM='1')
        subprocess.run(['git', 'init', '--bare', '--quiet', '--template=', str(repo)], check=True, env=environment)
        (repo / 'info').mkdir(exist_ok=True)
        (repo / 'info/exclude').write_bytes(b'')
        new_paths = set(after) - set(baseline)
        if new_paths:
            worktree = root / 'ignore-worktree'
            worktree.mkdir()
            for name in new_paths:
                target = worktree / name
                target.parent.mkdir(parents=True, exist_ok=True)
                target.touch()
            for name, (mode, data) in baseline.items():
                path = Path(name)
                if (path.name != '.gitignore' or mode == 0o120000
                        or any(parent.as_posix() in after for parent in path.parents)):
                    continue
                target = worktree / path
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(data)
            ignored = subprocess.run(['git', '-c', 'core.excludesFile='+os.devnull,
                                      '--git-dir', str(repo), '--work-tree', str(worktree),
                                      'check-ignore', '--no-index', '-z', '--stdin'],
                                     input=b''.join(os.fsencode(name)+b'\0' for name in sorted(new_paths)),
                                     cwd=worktree, env=environment, capture_output=True)
            if ignored.returncode not in (0, 1):
                ignored.check_returncode()
            omitted = {os.fsdecode(name) for name in ignored.stdout.split(b'\0') if name}
            after = {name: value for name, value in after.items() if name not in omitted}
        def git(*args, data=None, index=None):
            env = {**environment, **({'GIT_INDEX_FILE': str(index)} if index else {})}
            return subprocess.run(['git', '--git-dir', str(repo), *args], input=data,
                                  cwd=blobs, env=env, check=True, capture_output=True).stdout
        contents = list(dict.fromkeys(data for _, data in [*before.values(), *after.values()]))
        for index, data in enumerate(contents):
            (blobs / str(index)).write_bytes(data)
        hashes = git('hash-object', '-w', '--no-filters', '--stdin-paths',
                     data=''.join(str(i)+'\n' for i in range(len(contents))).encode()).splitlines()
        objects = dict(zip(contents, hashes))
        def tree(files, name):
            index = root / name
            entries = b''.join(f'{mode:o} '.encode() + objects[data] + b'\t' + os.fsencode(path) + b'\0'
                               for path, (mode, data) in sorted(files.items()))
            git('update-index', '-z', '--index-info', data=entries, index=index)
            return git('write-tree', index=index).decode().strip()
        left, right = tree(before, 'before.index'), tree(after, 'after.index')
        options = ('--no-ext-diff', '--no-textconv', '--no-renames', '--no-color')
        stats = git('diff', *options, '--numstat', '-z', left, right)
        paths = []
        for record in stats.split(b'\0'):
            if record:
                added, removed, name = record.split(b'\t', 2)
                if added != b'-' and removed != b'-':
                    paths.append(':(literal)' + os.fsdecode(name))
        if not paths:
            return b''
        return git('diff', *options, '--full-index', '--src-prefix=a/', '--dst-prefix=b/',
                   '--patch', left, right, '--', *paths)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--base', type=Path, required=True)
    parser.add_argument('--handback', type=Path, required=True)
    parser.add_argument('--dataset-json', type=Path, required=True)
    parser.add_argument('--instance', required=True)
    parser.add_argument('--kit-json', type=Path, default=Path(__file__).with_name('KIT.json'))
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    row = next(row for row in map(json.loads, args.dataset_json.read_text().splitlines())
               if row['instance_id'] == args.instance)
    config = json.loads(args.kit_json.read_text())['branches']['sandbox-v3/'+args.instance]['selection']
    args.out.write_bytes(derive_patch(args.base, args.handback, row['test_patch'], config['environment']['commands']))
    print(json.dumps(dict(patch=str(args.out), bytes=args.out.stat().st_size)))


if __name__ == '__main__':
    main()
