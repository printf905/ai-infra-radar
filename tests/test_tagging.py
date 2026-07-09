from radar.tagging import tags_for_text


def test_tags_for_text_matches_words_and_phrases() -> None:
    keywords = {
        "inference": ["serving", "latency"],
        "agents": ["tool use"],
        "training": ["train"],
    }

    tags = tags_for_text("Low latency model serving with tool use", keywords)

    assert tags == ["agents", "inference"]


def test_tags_for_text_uses_word_boundaries() -> None:
    tags = tags_for_text("The trainer failed", {"training": ["train"]})

    assert tags == []
