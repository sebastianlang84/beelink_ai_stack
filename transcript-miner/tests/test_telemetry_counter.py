from __future__ import annotations


def test_counter_add_supports_inc_and_add() -> None:
    from common.telemetry import counter_add

    class IncOnly:
        def __init__(self):
            self.value = 0

        def inc(self, n=1):
            self.value += n

    class AddOnly:
        def __init__(self):
            self.calls = []

        def add(self, amount, attrs=None):
            self.calls.append((amount, attrs))

    m1 = IncOnly()
    counter_add(m1, 3)
    assert m1.value == 3

    m2 = AddOnly()
    counter_add(m2, 2, {"k": "v"})
    assert m2.calls == [(2, {"k": "v"})]
