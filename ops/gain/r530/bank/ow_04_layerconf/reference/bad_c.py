"""Known-bad C: the skeleton. Every name exists, almost nothing happens."""
class Config(object):
    def __init__(self, values):
        self._values = values

    def get(self, key):
        return self._values[key]

    def source(self, key):
        return "default"

    def as_dict(self):
        return dict(self._values)


def load(defaults, file_text, env):
    return Config(dict(defaults))
