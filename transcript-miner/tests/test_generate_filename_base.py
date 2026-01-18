from common.utils import generate_filename_base


def test_generate_filename_base_preserves_date_and_video_id_and_sanitizes_channel() -> (
    None
):
    # Non-word characters (incl. whitespace and punctuation) become underscores,
    # then underscores are collapsed and stripped.
    assert (
        generate_filename_base(
            published_date_str="2025-01-02",
            channel_name="My Channel!",
            video_id="VIDEO123",
        )
        == "2025-01-02_My_Channel_VIDEO123"
    )


def test_generate_filename_base_replaces_slash_and_backslash() -> None:
    assert (
        generate_filename_base(
            published_date_str="2025-01-02",
            channel_name=r"A/B\\C",
            video_id="VID",
        )
        == "2025-01-02_A_B_C_VID"
    )


def test_generate_filename_base_collapses_existing_underscores() -> None:
    # The implementation collapses runs of underscores even if they already
    # exist in the input.
    assert (
        generate_filename_base(
            published_date_str="2025-01-02",
            channel_name="A__B",
            video_id="VID",
        )
        == "2025-01-02_A_B_VID"
    )


def test_generate_filename_base_strips_leading_and_trailing_underscores() -> None:
    assert (
        generate_filename_base(
            published_date_str="2025-01-02",
            channel_name="  A  ",
            video_id="VID",
        )
        == "2025-01-02_A_VID"
    )


def test_generate_filename_base_can_yield_empty_sanitized_channel() -> None:
    # If the channel name contains only characters that map to underscores,
    # collapsing + strip("_") can yield an empty string.
    assert (
        generate_filename_base(
            published_date_str="2025-01-02",
            channel_name="!!!",
            video_id="VID",
        )
        == "2025-01-02__VID"
    )


def test_generate_filename_base_allows_unicode_word_chars() -> None:
    # Python regex \w matches unicode word characters by default.
    assert (
        generate_filename_base(
            published_date_str="2025-01-02",
            channel_name="München",
            video_id="VID",
        )
        == "2025-01-02_München_VID"
    )


def test_generate_filename_base_is_deterministic() -> None:
    args = {
        "published_date_str": "2025-01-02",
        "channel_name": "A/B C!!!",
        "video_id": "VID",
    }
    assert generate_filename_base(**args) == generate_filename_base(**args)


def test_generate_filename_base_handles_very_long_channel_names() -> None:
    channel_name = ("A" * 300) + " " + ("B" * 300)
    expected_sanitized = ("A" * 300) + "_" + ("B" * 300)

    assert (
        generate_filename_base(
            published_date_str="2025-01-02",
            channel_name=channel_name,
            video_id="VID",
        )
        == f"2025-01-02_{expected_sanitized}_VID"
    )


def test_generate_filename_base_treats_tabs_and_newlines_as_separators() -> None:
    assert (
        generate_filename_base(
            published_date_str="2025-01-02",
            channel_name="A\tB\nC",
            video_id="VID",
        )
        == "2025-01-02_A_B_C_VID"
    )


def test_generate_filename_base_preserves_hyphens() -> None:
    # Implementation allows hyphens via the character class [^\w\-].
    assert (
        generate_filename_base(
            published_date_str="2025-01-02",
            channel_name="A-B",
            video_id="VID",
        )
        == "2025-01-02_A-B_VID"
    )


def test_generate_filename_base_replaces_emoji_with_underscore() -> None:
    assert (
        generate_filename_base(
            published_date_str="2025-01-02",
            channel_name="A😀B",
            video_id="VID",
        )
        == "2025-01-02_A_B_VID"
    )


def test_generate_filename_base_drops_combining_marks_via_sanitizing() -> None:
    # Combining marks (e.g. U+0301) are not matched by \w, so they become underscores,
    # which may be stripped at the ends.
    assert (
        generate_filename_base(
            published_date_str="2025-01-02",
            channel_name="Cafe\u0301",
            video_id="VID",
        )
        == "2025-01-02_Cafe_VID"
    )
