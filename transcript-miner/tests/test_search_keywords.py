from transcript_miner.transcript_downloader import search_keywords


def test_search_keywords_returns_empty_for_empty_inputs() -> None:
    assert search_keywords(transcript="", keywords=["x"]) == ([], [])
    assert search_keywords(transcript="something", keywords=[]) == ([], [])


def test_search_keywords_is_case_insensitive_and_whole_word() -> None:
    found_keywords, found_lines = search_keywords(
        transcript="Inflation is rising.",
        keywords=["inflation"],
    )

    assert found_keywords == ["inflation"]
    assert found_lines == ["Inflation is rising."]


def test_search_keywords_does_not_match_substrings() -> None:
    found_keywords, found_lines = search_keywords(
        transcript="concatenate\ncopycat\n",
        keywords=["cat"],
    )

    assert found_keywords == []
    assert found_lines == []


def test_search_keywords_collects_all_matching_lines_and_strips_whitespace() -> None:
    found_keywords, found_lines = search_keywords(
        transcript="  Inflation now\nno match here\nDEFLATION? inflation.\n",
        keywords=["inflation"],
    )

    assert found_keywords == ["inflation"]
    assert found_lines == [
        "Inflation now",
        "DEFLATION? inflation.",
    ]


def test_search_keywords_found_lines_can_contain_duplicates_across_keywords() -> None:
    # Implementation detail: `found_lines` is collected per keyword and is not de-duplicated.
    found_keywords, found_lines = search_keywords(
        transcript="Alpha beta\nbeta ALPHA\n",
        keywords=["alpha", "beta"],
    )

    assert found_keywords == ["alpha", "beta"]
    assert found_lines == [
        "Alpha beta",
        "beta ALPHA",
        "Alpha beta",
        "beta ALPHA",
    ]
