#!/usr/bin/env python3
"""Initialize local development data in Firestore emulator."""

import os
from google.cloud import firestore
from datetime import datetime, timezone

def main():
    """Initialize Firestore with local dev data."""

    # Connect to Firestore emulator
    project_id = os.environ.get('GCP_PROJECT_ID', 'copycat-local')
    db = firestore.Client(project='copycat-local', database='(default)')

    print("🚀 Initializing local development data...")

    # 1. Create admin user
    print("\n👤 Creating admin user...")
    admin_user = {
        'email': 'admin@localhost',
        'role': 'admin',
        'notes': 'Local development admin user',
        'assigned_by': 'system',
        'assigned_at': datetime.now(timezone.utc),
        'created_at': datetime.now(timezone.utc),
        'updated_at': datetime.now(timezone.utc)
    }
    db.collection('user_roles').document('admin@localhost').set(admin_user)
    print(f"   ✅ Created {admin_user['email']} with role: {admin_user['role']}")

    # 2. Create Justice League IP config
    print("\n🦸 Creating Justice League IP config...")
    ip_config = {
        'id': 'justice-league-test',
        'name': 'Justice League (Test)',
        'description': 'DC Comics Justice League superhero team',
        'owner': 'Warner Bros. Discovery / DC Comics',
        'characters': [
            {
                'name': 'Superman',
                'visual_description': 'Blue suit with red cape, S symbol on chest, red boots',
                'key_features': ['red cape', 'S symbol', 'blue suit', 'flying pose']
            },
            {
                'name': 'Batman',
                'visual_description': 'Dark knight in cape and cowl with pointed ears, bat symbol',
                'key_features': ['bat symbol', 'black cape', 'pointed ears', 'utility belt']
            },
            {
                'name': 'Wonder Woman',
                'visual_description': 'Warrior princess with golden lasso, tiara, armor',
                'key_features': ['golden lasso', 'tiara', 'armor', 'bracelets']
            }
        ],
        'search_keywords': [
            'Superman AI generated',
            'Batman Sora video',
            'Justice League AI',
            'Superman Runway ML',
            'Batman Kling AI'
        ],
        'tier': 1,  # Tier 1 = daily searches
        'active': True,
        'priority': 'high',
        'created_at': datetime.now(timezone.utc),
        'updated_at': datetime.now(timezone.utc)
    }
    db.collection('ip_configs').document('justice-league-test').set(ip_config)
    print(f"   ✅ Created IP config: {ip_config['name']}")
    print(f"      Characters: {len(ip_config['characters'])}")
    print(f"      Keywords: {len(ip_config['search_keywords'])}")
    print(f"      Tier: {ip_config['tier']} (daily)")

    # 3. Initialize system stats
    print("\n📊 Initializing system stats...")
    system_stats = {
        'total_videos': 0,
        'total_channels': 0,
        'total_infringements': 0,
        'updated_at': datetime.now(timezone.utc)
    }
    db.collection('system_stats').document('global').set(system_stats)
    print("   ✅ System stats initialized")

    print("\n✅ Local development data initialized successfully!")
    print("\n🔑 Use this header for API calls:")
    print("   X-Dev-User: admin@localhost")

if __name__ == '__main__':
    main()
