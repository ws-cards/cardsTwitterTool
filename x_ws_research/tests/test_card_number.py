from vision.card_number import extract_card_numbers, normalize_card_number, numbers_equal


def test_normalize_standard():
    assert normalize_card_number("abc/s123-1") == "ABC/S123-001"
    assert normalize_card_number("BD/W54-076") == "BD/W54-076"


def test_normalize_loose_separators():
    assert normalize_card_number("abc_s123－001") == "ABC/S123-001"


def test_extract_from_text():
    text = "今日構築 ABC/S123-001 與 BD/W54-076SP"
    nums = extract_card_numbers(text)
    assert "ABC/S123-001" in nums
    assert any(n.startswith("BD/W54-076") for n in nums)


def test_numbers_equal():
    assert numbers_equal("abc/s1-1", "ABC/S1-001")
    assert not numbers_equal("ABC/S1-001", "ABC/S1-002")


def test_empty():
    assert normalize_card_number("") is None
    assert normalize_card_number(None) is None
    assert extract_card_numbers("") == []
