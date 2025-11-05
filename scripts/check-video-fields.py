#!/usr/bin/env python3
"""Check what fields analyzed videos have."""

from google.cloud import firestore

# Connect to Firestore emulator
db = firestore.Client(project='copycat-local', database='(default)')

# Get one analyzed video
doc = db.collection('videos').where('status', '==', 'analyzed').limit(1).get()[0]
data = doc.to_dict()

print(f"Video {doc.id} fields:")
for key in sorted(data.keys()):
    if key in ['analysis', 'vision_analysis', 'status', 'analyzed_at', 'last_analyzed_at']:
        print(f"  {key}: {type(data[key]).__name__}")
        if isinstance(data[key], dict):
            print(f"    Keys: {list(data[key].keys())[:5]}")
