from schemas.models import KeywordConfig, PostRecord
from services.keyword_filter import filter_posts, keyword_matches, parse_keyword_list


def _post(text: str, source_id: str = "1") -> PostRecord:
    return PostRecord(source_id=source_id, author_handle="u", text=text)


def test_parse_keywords():
    assert parse_keyword_list("Weiss, デッキ， card") == ["Weiss", "デッキ", "card"]


def test_or_match():
    assert keyword_matches("Hello Weiss world", ["ws", "weiss"], match_mode="any")
    assert not keyword_matches("nothing here", ["weiss", "deck"], match_mode="any")


def test_and_match():
    text = "Weiss Schwarz deck list"
    assert keyword_matches(text, ["weiss", "deck"], match_mode="all")
    assert not keyword_matches(text, ["weiss", "missing"], match_mode="all")


def test_case_sensitive():
    assert keyword_matches("Weiss", ["weiss"], case_sensitive=False)
    assert not keyword_matches("Weiss", ["weiss"], case_sensitive=True)


def test_whitespace_normalization_preserves_original():
    original = "Weiss   Schwarz\n\ndeck"
    post = _post(original)
    matched = filter_posts(
        [post],
        KeywordConfig(
            keywords=["weiss schwarz deck"],
            match_mode="any",
            case_sensitive=False,
            normalize_whitespace=True,
        ),
    )
    assert len(matched) == 1
    assert matched[0].text == original  # original untouched


def test_empty_keywords_pass_all():
    posts = [_post("a"), _post("b", "2")]
    assert len(filter_posts(posts, keywords=[])) == 2
