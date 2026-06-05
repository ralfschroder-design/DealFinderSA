from dealfinder.phone import extract_phone, normalize_phone


def test_normalize_local_format():
    assert normalize_phone("082 123 4567") == "0821234567"


def test_normalize_plus_27():
    assert normalize_phone("+27 82 123 4567") == "0821234567"


def test_normalize_rejects_too_short():
    assert normalize_phone("123") is None


def test_extract_from_description():
    assert extract_phone("Please call me on 082-123-4567 after 5pm") == "0821234567"


def test_extract_plus27_in_text():
    assert extract_phone("WhatsApp +27821234567 for viewing") == "0821234567"


def test_extract_none_when_absent():
    assert extract_phone("No number here, email only") is None


def test_extract_handles_empty():
    assert extract_phone(None) is None
    assert extract_phone("") is None
