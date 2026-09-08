from src.span_extractor import find_best_verbatim_span, norm

def test_span_extractor():
    passage = "Under Regulation 16(a), an investment adviser must obtain age, income details, and risk appetite. Failure to comply leads to penalties."

    # Test 1: Direct match
    q1 = "Under Regulation 16(a), an investment adviser must obtain age"
    res1 = find_best_verbatim_span(passage, q1)
    assert norm(res1) in norm(passage), f"Failed test 1: {res1}"

    # Test 2: Added trailing period
    q2 = "an investment adviser must obtain age, income details, and risk appetite."
    res2 = find_best_verbatim_span(passage, q2)
    assert norm(res2) in norm(passage), f"Failed test 2: {res2}"

    # Test 3: Approximate quote with extra words
    q3 = "The adviser should obtain age, income details and risk appetite"
    res3 = find_best_verbatim_span(passage, q3)
    assert norm(res3) in norm(passage), f"Failed test 3: {res3}"

    print("ALL SPAN EXTRACTOR TESTS PASSED!")

if __name__ == "__main__":
    test_span_extractor()
