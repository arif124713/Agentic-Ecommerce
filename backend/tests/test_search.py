"""Regression test for the search precision fix documented in done.MD §11: MySQL FULLTEXT
`WITH PARSER ngram` in NATURAL LANGUAGE / BOOLEAN mode was empirically found to match 50-80% of
an unrelated catalogue on short queries (shared n-grams like "ee"/"en" are common to huge swaths
of English text). Search was rewritten to precise token-AND `LIKE` matching, broadening to
token-OR only when the strict match returns nothing. This test pins that behaviour down so it
can't silently regress back to the broken approach."""

from tests.conftest import make_product_with_variant


async def _seed_catalogue(db_session):
    await make_product_with_variant(db_session, title="Vintage Blue Denim Jacket", price="2000.00")
    await make_product_with_variant(db_session, title="Classic Blue Cotton Shirt", price="800.00")
    await make_product_with_variant(db_session, title="Red Leather Boots", price="3000.00")


async def _search(client, q: str):
    resp = await client.get("/api/v1/products", params={"q": q, "per_page": 50})
    assert resp.status_code == 200, resp.text
    return resp.json()


async def test_single_token_matches_only_the_containing_title(client, db_session):
    await _seed_catalogue(db_session)
    body = await _search(client, "denim")
    titles = [p["title"] for p in body["data"]]
    assert titles == ["Vintage Blue Denim Jacket"]
    assert body["meta"]["search_fallback"] is False


async def test_multi_token_requires_all_tokens_present(client, db_session):
    await _seed_catalogue(db_session)
    body = await _search(client, "blue shirt")
    titles = [p["title"] for p in body["data"]]
    assert titles == ["Classic Blue Cotton Shirt"]  # "Denim Jacket" has "blue" but not "shirt"
    assert body["meta"]["search_fallback"] is False


async def test_nonsense_query_returns_zero_with_fallback_flag(client, db_session):
    await _seed_catalogue(db_session)
    body = await _search(client, "zzznonexistentqueryxyz")
    assert body["data"] == []
    assert body["meta"]["total"] == 0
    assert body["meta"]["search_fallback"] is True


async def test_zero_result_and_query_broadens_to_or_match(client, db_session):
    """"blue boots" matches no single product on both words, so the precise AND search comes up
    empty — the fallback should broaden to "any word matches" rather than dead-ending, surfacing
    every product that mentions "blue" OR "boots"."""
    await _seed_catalogue(db_session)
    body = await _search(client, "blue boots")
    titles = {p["title"] for p in body["data"]}
    assert titles == {"Vintage Blue Denim Jacket", "Classic Blue Cotton Shirt", "Red Leather Boots"}
    assert body["meta"]["search_fallback"] is True


async def test_search_is_case_insensitive(client, db_session):
    await _seed_catalogue(db_session)
    body = await _search(client, "DENIM")
    assert [p["title"] for p in body["data"]] == ["Vintage Blue Denim Jacket"]
