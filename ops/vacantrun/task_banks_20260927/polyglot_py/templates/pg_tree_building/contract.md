# Contract

Write your solution to `tree_building.py` in the root of this workspace. The file does not exist
yet; create it. Start from this skeleton and keep these names, because the tests import them:

```python
class Record:
    def __init__(self, record_id, parent_id):
        self.record_id = record_id
        self.parent_id = parent_id


class Node:
    def __init__(self, node_id):
        self.node_id = node_id
        self.children = []


def BuildTree(records):
    root = None
    records.sort(key=lambda x: x.record_id)
    ordered_id = [i.record_id for i in records]
    if records:
        if ordered_id[-1] != len(ordered_id) - 1:
            raise ValueError('broken tree')
        if ordered_id[0] != 0:
            raise ValueError('invalid')
    trees = []
    parent = {}
    for i in range(len(ordered_id)):
        for j in records:
            if ordered_id[i] == j.record_id:
                if j.record_id == 0:
                    if j.parent_id != 0:
                        raise ValueError('error!')
                if j.record_id < j.parent_id:
                    raise ValueError('something went wrong!')
                if j.record_id == j.parent_id:
                    if j.record_id != 0:
                        raise ValueError('error!')
                trees.append(Node(ordered_id[i]))
    for i in range(len(ordered_id)):
        for j in trees:
            if i == j.node_id:
                parent = j
        for j in records:
            if j.parent_id == i:
                for k in trees:
                    if k.node_id == 0:
                        continue
                    if j.record_id == k.node_id:
                        child = k
                        parent.children.append(child)
    if len(trees) > 0:
        root = trees[0]
    return root
```

- Put all of your code in `tree_building.py`. Only use the Python standard library; do not
  install packages.
- Don't change the names of existing functions or classes, as they may be referenced from
  other code like unit tests.
- The tests for this task are in `tree_building_test.py`. The tests are correct; don't change them. Run them
  with:

      python3 -m pytest -q tree_building_test.py

  or, without pytest:

      python3 -m unittest tree_building_test.py
