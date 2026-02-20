from app.services.capture_batch import parse_batch_capture_text


def test_parse_batch_capture_text_with_delimiter_blocks() -> None:
    text = "first entry\n---\nsecond entry\n---\nthird entry"
    items = parse_batch_capture_text(text)
    assert items == ["first entry", "second entry", "third entry"]


def test_parse_batch_capture_text_with_blank_line_blocks() -> None:
    text = "first entry\n\nsecond entry\n\nthird entry"
    items = parse_batch_capture_text(text)
    assert items == ["first entry", "second entry", "third entry"]


def test_parse_batch_capture_text_falls_back_to_lines() -> None:
    text = "first entry\nsecond entry\nthird entry"
    items = parse_batch_capture_text(text)
    assert items == ["first entry", "second entry", "third entry"]
