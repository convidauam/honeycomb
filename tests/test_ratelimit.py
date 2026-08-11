import pytest

from honeycomb.security import ratelimit


def test_sliding_window_limiter_allows_up_to_the_per_key_limit():
    limiter = ratelimit.SlidingWindowLimiter(window_seconds=600, max_per_key=2, max_global=100)
    limiter.check_and_record('alice')
    limiter.check_and_record('alice')
    with pytest.raises(ratelimit.RateLimitError) as excinfo:
        limiter.check_and_record('alice')
    assert excinfo.value.scope == 'key'


def test_sliding_window_limiter_per_key_limit_does_not_affect_other_keys():
    limiter = ratelimit.SlidingWindowLimiter(window_seconds=600, max_per_key=1, max_global=100)
    limiter.check_and_record('alice')
    limiter.check_and_record('bob')


def test_sliding_window_limiter_enforces_global_limit_across_keys():
    limiter = ratelimit.SlidingWindowLimiter(window_seconds=600, max_per_key=100, max_global=2)
    limiter.check_and_record('alice')
    limiter.check_and_record('bob')
    with pytest.raises(ratelimit.RateLimitError) as excinfo:
        limiter.check_and_record('carol')
    assert excinfo.value.scope == 'global'


def test_sliding_window_limiter_with_none_limits_never_blocks():
    limiter = ratelimit.SlidingWindowLimiter(window_seconds=600, max_per_key=None, max_global=None)
    for _ in range(50):
        limiter.check_and_record('alice')


def test_positive_int_setting_falls_back_to_default_when_blank():
    assert ratelimit.positive_int_setting({}, 'x', 42) == 42
    assert ratelimit.positive_int_setting({'x': ''}, 'x', 42) == 42


def test_positive_int_setting_falls_back_to_default_when_not_a_number():
    assert ratelimit.positive_int_setting({'x': 'garbage'}, 'x', 42) == 42


def test_positive_int_setting_falls_back_to_default_when_not_positive():
    assert ratelimit.positive_int_setting({'x': '0'}, 'x', 42) == 42
    assert ratelimit.positive_int_setting({'x': '-5'}, 'x', 42) == 42


def test_positive_int_setting_reads_explicit_value():
    assert ratelimit.positive_int_setting({'x': '120'}, 'x', 42) == 120


def test_limit_setting_or_none_is_none_when_blank_or_absent():
    assert ratelimit.limit_setting_or_none({}, 'x') is None
    assert ratelimit.limit_setting_or_none({'x': ''}, 'x') is None


def test_limit_setting_or_none_is_none_when_zero_or_negative():
    assert ratelimit.limit_setting_or_none({'x': '0'}, 'x') is None
    assert ratelimit.limit_setting_or_none({'x': '-1'}, 'x') is None


def test_limit_setting_or_none_is_none_when_garbage():
    assert ratelimit.limit_setting_or_none({'x': 'garbage'}, 'x') is None


def test_limit_setting_or_none_reads_explicit_value():
    assert ratelimit.limit_setting_or_none({'x': '5'}, 'x') == 5
