import httpx
import json
import time  # ADD THIS

BASE = "http://localhost:8000"
TICKER = "AAPL"

questions = [
    ("What were Apple total revenues in fiscal 2025?", None),
    ("How much did Apple services revenue grow year over year?", None),
    ("What is Apple gross margin?", "10-K"),
    ("What are Apple main risks in China?", "10-K"),
    ("What regulatory risks does Apple face?", "10-K"),
    ("How does Apple manage supply chain risks?", "10-K"),
    ("What has recent news said about Apple stock?", "news"),
    ("What are analysts saying about Apple?", "news"),
    ("How did Apple perform in the most recent quarter?", "10-Q"),
    ("What was Apple revenue in Q2 2026?", "10-Q"),
    ("What did Apple say about AI investments?", None),
    ("How is Apple doing in the services business?", None),
    ("What is Apple cricket sponsorship strategy?", None),
    ("Who is Apple CFO?", None),
    ("How has Apple revenue changed over the last 3 years?", "10-K"),
]

print("=== RAG Quality Test ===\n")
results = []

for i, (question, doc_type) in enumerate(questions, 1):
    body = {"question": question}
    if doc_type:
        body["doc_type"] = doc_type

    try:
        r = httpx.post(
            f"{BASE}/companies/{TICKER}/ask",
            json=body,
            timeout=45    # INCREASE to 45 seconds
        )
        data = r.json()
        answer = data.get("answer", "ERROR")
        sources = data.get("sources", [])
        top_similarity = sources[0]["similarity"] if sources else 0

        if "cannot find" in answer.lower():
            grade = "❓ NO ANSWER"
        elif top_similarity > 0.6:
            grade = "✅ GOOD"
        elif top_similarity > 0.45:
            grade = "⚠️  OKAY"
        else:
            grade = "❌ WEAK"

    except Exception as e:
        grade = "❌ ERROR"
        answer = str(e)
        top_similarity = 0
        sources = []

    results.append({
        "question": question,
        "grade": grade,
        "top_similarity": top_similarity,
        "answer_preview": answer[:150],
    })

    print(f"Q{i}: {question}")
    print(f"     Filter: {doc_type or 'all'}")
    print(f"     Grade: {grade} (similarity: {top_similarity})")
    print(f"     Answer: {answer[:150]}")
    print()

    # ADD THIS: wait 3 seconds between questions to avoid rate limits
    time.sleep(3)

# Summary
good = sum(1 for r in results if "✅" in r["grade"])
okay = sum(1 for r in results if "⚠️" in r["grade"])
weak = sum(1 for r in results if "❌" in r["grade"])
no_answer = sum(1 for r in results if "❓" in r["grade"])

print("=== Summary ===")
print(f"✅ Good:      {good}/15")
print(f"⚠️  Okay:      {okay}/15")
print(f"❌ Weak:      {weak}/15")
print(f"❓ No answer: {no_answer}/15")
print(f"\nOverall score: {good + okay}/15 acceptable answers")