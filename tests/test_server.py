from fastapi.testclient import TestClient
from src.server import app

def test_api_endpoints():
    with TestClient(app) as client:
        # 1. Test healthz
        resp = client.get("/healthz")
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"

        # 2. Test /ask on role-blocked question
        q_blocked = {
            "id": "test-blocked",
            "question": "Under SEBI Mutual Funds Regulations, what is the independent director minimum?",
            "role": "public",
            "as_of": "2026-01-01"
        }
        res = client.post("/ask", json=q_blocked)
        assert res.status_code == 200
        data = res.json()
        assert data["status"] == "not_permitted"
        assert len(data["citations"]) == 0

        # 3. Test /ask on out-of-corpus question
        q_ooc = {
            "id": "test-ooc",
            "question": "What is the net owned fund requirement for NBFC?",
            "role": "legal",
            "as_of": "2026-01-01"
        }
        res_ooc = client.post("/ask", json=q_ooc)
        assert res_ooc.status_code == 200
        data_ooc = res_ooc.json()
        assert data_ooc["status"] == "not_in_corpus"
        assert len(data_ooc["citations"]) == 0

        print("ALL FASTAPI SERVICE TESTS PASSED!")

if __name__ == "__main__":
    test_api_endpoints()
