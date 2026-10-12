from vacant_network.adapters import hookpolicy as h
for c in ["python3 -c \"import json;print(json.load(open('$HOME/.vacant/adapters/install.json')))\"",
          "python3 -c \"import json;print(json.load(open('/home/u/.vacant/adapters/install.json')))\""]:
    print(h._single_py_c(c), '<-', c)
