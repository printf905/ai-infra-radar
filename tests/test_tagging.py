from radar.config import AppConfig, TopicConfig
from radar.db import connect, fetch_all, init_db, upsert_paper
from radar.models import Paper
from radar.tagging import tag_database, tags_for_paper, tags_for_text


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


def test_speculative_decoding_paper_gets_llm_inference_tag() -> None:
    tags = tags_for_paper(
        "Speculative Decoding for Faster LLM Serving",
        "We improve generation throughput.",
        {"llm_inference": ["speculative decoding", "serving"]},
    )

    assert tags == {"llm_inference": 0.95}


def test_agent_paper_gets_agents_tag() -> None:
    tags = tags_for_paper(
        "Tool Use for Autonomous Agents",
        "Planning systems can call external tools.",
        {"agents": ["agent", "agents", "tool use", "planning"]},
    )

    assert tags == {"agents": 0.95}


def test_unrelated_paper_gets_no_tag() -> None:
    tags = tags_for_paper(
        "A Survey of Sorting Algorithms",
        "We compare merge sort and quicksort.",
        {"llm_inference": ["speculative decoding"], "agents": ["tool use"]},
    )

    assert tags == {}


def test_duplicate_tags_are_not_inserted_twice() -> None:
    conn = connect(":memory:")
    init_db(conn)
    paper_id = upsert_paper(
        conn,
        Paper(
            arxiv_id="2401.1",
            title="Speculative Decoding for LLM Inference",
            abstract="Speculative decoding improves inference throughput.",
            url="https://arxiv.org/abs/2401.1",
        ),
    )
    config = AppConfig(
        topics={
            "llm_inference": TopicConfig(
                keywords=["speculative decoding", "inference"],
                weight=1.0,
            )
        }
    )

    assert tag_database(conn, config) == 1
    assert tag_database(conn, config) == 1

    rows = fetch_all(conn, "SELECT paper_id, tag, confidence FROM paper_tags")

    assert len(rows) == 1
    assert rows[0]["paper_id"] == paper_id
    assert rows[0]["tag"] == "llm_inference"
    assert rows[0]["confidence"] == 0.95
