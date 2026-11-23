import pytest
from shipping import shipping_cost

def test_negative():
    with pytest.raises(ValueError):
        shipping_cost(-1)
