#!/usr/bin/env python3
"""Check analyzed videos in Firestore."""

from google.cloud import firestore

# Connect to Firestore emulator
db = firestore.Client(project='copycat-local', database='(default)')

# Query videos by status
statuses = ['analyzed', 'failed', 'processing', 'pending']
for status in statuses:
    docs = list(db.collection('videos').where('status', '==', status).limit(10).stream())
    print(f"\n{status.upper()}: {len(docs)} videos (showing first 10)")
    for doc in docs[:3]:
        data = doc.to_dict()
        print(f"  - {doc.id}: {data.get('title', 'N/A')[:50]}")

# Check total
all_videos = list(db.collection('videos').limit(10).stream())
print(f"\nTOTAL: {len(all_videos)} videos (sample)")
