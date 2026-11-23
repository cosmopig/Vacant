"""Harden operator setup commands without changing the selected test environments."""
import shlex


QHULL_URL = 'https://codeload.github.com/qhull/qhull/tar.gz/refs/tags/2020.2'
QHULL_SHA256 = '59356b229b768e6e2b09a701448bfa222c37b797a84f87f864f97462d8dbc7c5'
QHULL_VERIFY = ('import hashlib,pathlib,sys; '
                'actual=hashlib.sha256(pathlib.Path(sys.argv[1]).read_bytes()).hexdigest(); '
                'sys.exit(0 if actual == sys.argv[2] else "Qhull sha256 mismatch")')
QHULL_CHECK = ('python -I -c ' + shlex.quote(QHULL_VERIFY) +
               ' "$QHULL_TAR" "$QHULL_SHA256" || exit 1')


def secure_downloads(commands):
    hardened = []
    for command in commands:
        if command.startswith('QHULL_URL='):
            hardened.extend([f'QHULL_URL="{QHULL_URL}"', f'QHULL_SHA256="{QHULL_SHA256}"'])
        elif command.startswith('QHULL_SHA256='):
            continue
        elif command == 'wget -O "$QHULL_TAR" "$QHULL_URL"':
            hardened.append('curl --fail --location --proto "=https" --tlsv1.2 '
                            '--output "$QHULL_TAR" "$QHULL_URL" || exit 1')
        elif command.startswith('tar ') and '"$QHULL_TAR"' in command:
            if not hardened or hardened[-1] != QHULL_CHECK:
                hardened.append(QHULL_CHECK)
            hardened.append(command)
        else:
            hardened.append(command)
    return hardened


def temporary_requirements(commands):
    safe, index = [], 0
    while index < len(commands):
        command = commands[index]
        if '$HOME/requirements.txt' not in command:
            safe.append(command)
            index += 1
            continue
        group = commands[index:index+3]
        if (len(group) != 3 or not command.startswith('cat <<')
                or '$HOME/requirements.txt' not in group[1] or group[2] != 'rm $HOME/requirements.txt'):
            raise ValueError('unsupported requirements-file recipe')
        safe.append('\n'.join(['(', 'set -e', 'VACANT_REQUIREMENTS=$(mktemp)',
            'trap \'rm -f -- "$VACANT_REQUIREMENTS"\' EXIT',
            *[line.replace('$HOME/requirements.txt', '"$VACANT_REQUIREMENTS"') for line in group[:2]], ')']))
        index += 3
    return safe
