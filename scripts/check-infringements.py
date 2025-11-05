#!/usr/bin/env python3
"""Check analyzed videos and their infringement status."""

import os
from google.cloud import firestore

# Use emulator
os.environ['FIRESTORE_EMULATOR_HOST'] = 'localhost:8200'

db = firestore.Client(project='copycat-dev', database='(default)')

print("=== Checking Analyzed Videos ===\n")

# Get all videos with status = analyzed
analyzed_videos = db.collection('videos').where('status', '==', 'analyzed').stream()

count = 0
infringement_count = 0

for video_doc in analyzed_videos:
    count += 1
    video = video_doc.to_dict()

    video_id = video.get('video_id', 'unknown')
    title = video.get('title', 'No title')[:60]

    print(f"\n[{count}] Video: {video_id}")
    print(f"    Title: {title}")
    print(f"    Status: {video.get('status')}")

    vision_analysis = video.get('vision_analysis')
    print(f"    vision_analysis type: {type(vision_analysis)}")

    if vision_analysis:
        print(f"    vision_analysis keys: {vision_analysis.keys() if isinstance(vision_analysis, dict) else 'N/A'}")

        # Check different possible structures
        if isinstance(vision_analysis, dict):
            # Check direct structure
            contains_infringement = vision_analysis.get('contains_infringement')
            confidence = vision_analysis.get('confidence_score') or vision_analysis.get('confidence')

            # Check nested structure
            full_analysis = vision_analysis.get('full_analysis')
            if full_analysis and isinstance(full_analysis, dict):
                print(f"    full_analysis keys: {full_analysis.keys()}")
                contains_infringement = full_analysis.get('contains_infringement')
                confidence = full_analysis.get('confidence_score') or full_analysis.get('confidence')

            print(f"    contains_infringement: {contains_infringement}")
            print(f"    confidence: {confidence}")

            if contains_infringement:
                infringement_count += 1
                print(f"    ⚠️  INFRINGEMENT DETECTED")
        else:
            print(f"    vision_analysis is not a dict: {vision_analysis}")

print(f"\n=== Summary ===")
print(f"Total analyzed videos: {count}")
print(f"Infringements found: {infringement_count}")
print(f"Detection rate: {(infringement_count/count*100):.1f}%" if count > 0 else "N/A")
