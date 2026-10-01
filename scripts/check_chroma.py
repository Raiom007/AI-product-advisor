import random

import chromadb

c = chromadb.PersistentClient('data/chroma')
coll = c.get_collection('reviews')
all_ids = coll.get(include=[])['ids']
sampled_ids = random.sample(all_ids, min(5, len(all_ids)))

res = coll.get(ids=sampled_ids, include=['documents'])
for rid, doc in zip(res['ids'], res['documents']):
    print(f"{rid}: {doc[:60]}")
