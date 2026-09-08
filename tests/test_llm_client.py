from src.llm import LLMClient

def test_llm():
    client = LLMClient()
    print("Testing model:", client.model)
    resp = client.chat_completion([
        {"role": "system", "content": "You are a concise compliance helper."},
        {"role": "user", "content": "Answer in 3 words: What is 2 + 2?"}
    ])
    print("LLM Response:", resp)
    assert len(resp.strip()) > 0
    print("LLM CLIENT TEST PASSED!")

if __name__ == "__main__":
    test_llm()
