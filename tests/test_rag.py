from app.rag import retrieve_relevant_chunks


def test_retrieves_most_relevant_chunk_first():
    chunks = [
        "The tenant must pay rent by the 1st of every month.",
        "Landlord must give 24 hours notice before entering the unit.",
        "This paragraph is about grocery shopping and has nothing to do with leases.",
    ]
    results = retrieve_relevant_chunks("when is rent due", chunks, top_k=2)
    assert results[0].startswith("The tenant must pay rent")


def test_excludes_chunks_with_zero_overlap():
    chunks = ["Completely unrelated text about cooking pasta."]
    results = retrieve_relevant_chunks("security deposit refund timeline", chunks)
    assert results == []


def test_empty_chunk_list_returns_empty():
    assert retrieve_relevant_chunks("any question", []) == []


def test_respects_top_k_limit():
    chunks = [f"rent clause number {i} about rent payments" for i in range(10)]
    results = retrieve_relevant_chunks("rent payments", chunks, top_k=3)
    assert len(results) == 3
