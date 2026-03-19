import pytest
from tts_utilities.util import as_list

def test_as_list_with_list():
    """Should return the same list object."""
    input_val = [1, 2, 3]
    result = as_list(input_val)
    assert result == [1, 2, 3]
    assert result is input_val  # Verify it doesn't create a unnecessary copy

def test_as_list_with_string():
    """Strings should be wrapped in a list, not exploded into characters."""
    assert as_list("hello") == ["hello"]

def test_as_list_with_dict():
    """Dictionaries should be wrapped in a list, not converted to a list of keys."""
    input_val = {"key": "value"}
    assert as_list(input_val) == [{"key": "value"}]

def test_as_list_with_tuple():
    """Other iterables like tuples should be converted to lists."""
    assert as_list((1, 2)) == [1, 2]

def test_as_list_with_set():
    """Sets should be converted to lists."""
    result = as_list({1, 2})
    assert len(result) == 2
    assert 1 in result and 2 in result

def test_as_list_with_integer():
    """Non-iterable types should be wrapped in a list."""
    assert as_list(123) == [123]

def test_as_list_with_none():
    """NoneType should be wrapped in a list."""
    assert as_list(None) == [None]

def test_as_list_with_generator():
    """Generators should be exhausted into a list."""
    gen = (i for i in range(3))
    assert as_list(gen) == [0, 1, 2]