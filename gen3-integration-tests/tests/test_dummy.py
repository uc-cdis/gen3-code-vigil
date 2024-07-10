import pytest


class TestDummy:
    def test_dummy_pass(self):
        assert 1 == 1

    def test_dummy_fail(self):
        assert 1 == 2

    @pytest.mark.skip
    def test_dummy_skip(self):
        assert 1 == 1
