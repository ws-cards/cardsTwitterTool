import pytest

from crawler.post_source import (
    collect_posts,
    create_import_source,
    filter_by_keywords,
)


@pytest.mark.asyncio
async def test_json_import(sample_json):
    source = create_import_source(sample_json)
    posts = await collect_posts(source)
    assert len(posts) == 2
    assert posts[0].author_handle == "alice"
    assert posts[0].source_id == "1"
    assert "ABC/S123-001" in posts[0].text


@pytest.mark.asyncio
async def test_csv_import(sample_csv):
    source = create_import_source(sample_csv)
    posts = await collect_posts(source)
    assert len(posts) == 1
    assert posts[0].author_handle == "carol"
    assert posts[0].image_urls == ["https://example.com/c.jpg"]


@pytest.mark.asyncio
async def test_missing_file(tmp_path):
    source = create_import_source(tmp_path / "nope.json")
    with pytest.raises(FileNotFoundError):
        await source.initialize()


def test_unsupported_format(tmp_path):
    path = tmp_path / "x.txt"
    path.write_text("nope", encoding="utf-8")
    with pytest.raises(ValueError):
        create_import_source(path)


@pytest.mark.asyncio
async def test_keyword_filter(sample_json):
    posts = await collect_posts(create_import_source(sample_json))
    matched = filter_by_keywords(posts, ["weiss"], match_mode="any", case_sensitive=False)
    assert len(matched) == 1
    assert matched[0].source_id == "1"
