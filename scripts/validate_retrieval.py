from backend.services.rag_service import rag_service

queries = [
    "What are common symptoms of dehydration?",
    "What should someone do for a mild fever?",
    "What are warning signs associated with chest pain?",
    "What symptoms may indicate an allergic reaction?",
    "What are common signs of respiratory infection?"
]

print("=== RETRIEVAL QUALITY VALIDATION ===")
for i, q in enumerate(queries, 1):
    results = rag_service.query(q, top_k=2)
    print(f"\n--- QUERY {i}: \"{q}\" ---")
    print(f"Matches returned: {len(results)}")
    if results:
        top = results[0]
        meta = top["metadata"]
        print(f"Top Title: {meta.get('title')}")
        print(f"Source: {meta.get('source')}")
        print(f"Score: {top.get('score')}")
        snippet = top['text'][:140].replace('\n', ' ')
        print(f"Snippet: {snippet}...")
    else:
        print("Result: No documents passed relevance threshold (Out of scope or unindexed topic).")
