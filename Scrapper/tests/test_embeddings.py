"""Test local embedding generation on Biology syllabus."""
import sys, time
sys.path.insert(0, r"C:\Qcaa_AI\Scrapper")
from scraper import extract_pdf_text, chunk_text, generate_embeddings

# Extract text
text = extract_pdf_text(r"C:\Qcaa_AI\Scrapper\qcaa_data\biology\syllabus.pdf")
print(f"Text length: {len(text)} chars\n")

# Chunk
chunks = chunk_text(text, "Biology", "biology_syllabus_2025")
print(f"Chunks: {len(chunks)}\n")

# Show ALL chunks summary
print(f"{'#':>3}  {'Section':20s} {'Type':18s} {'Words':>5}  First 70 chars")
print("-" * 120)
for i, c in enumerate(chunks):
    preview = c['text'][:70].replace('\n', ' ')
    print(f"{i:3d}  {c['section']:20s} {c['type']:18s} {c['metadata']['word_count']:5d}  {preview}…")

# Stats
word_counts = [c['metadata']['word_count'] for c in chunks]
print(f"\n--- Stats ---")
print(f"Total chunks: {len(chunks)}")
print(f"Min words:    {min(word_counts)}")
print(f"Max words:    {max(word_counts)}")
print(f"Avg words:    {sum(word_counts) / len(word_counts):.0f}")
types = {}
for c in chunks:
    types[c['type']] = types.get(c['type'], 0) + 1
print(f"Types:        {types}")

# Generate embeddings
t0 = time.time()
embeddings = generate_embeddings(chunks)
elapsed = time.time() - t0
print(f"\nEmbeddings: {len(embeddings)} vectors")
print(f"Dimension: {len(embeddings[0])}")
print(f"Time: {elapsed:.1f}s")
print(f"Sample vector (first 5): {embeddings[0][:5]}")
