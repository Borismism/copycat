"""Check discovery service Firestore configuration."""

from google.cloud import firestore

# Connect to the copycat database
client = firestore.Client(project="irdeto-copycat-internal-dev", database="copycat")

# Check ip_configs collection
print("=== IP Configs Collection ===")
configs = list(client.collection("ip_configs").stream())
print(f"Found {len(configs)} configs\n")

if not configs:
    print("❌ No configs found! The ip_configs collection is empty.")
    print("\nThe discovery service needs configs with 'search_keywords' to work.")
else:
    for doc in configs:
        data = doc.to_dict()
        print(f"Config ID: {doc.id}")
        print(f"  Name: {data.get('name', 'N/A')}")
        print(f"  Deleted: {data.get('deleted', False)}")
        print(f"  Has search_keywords: {bool(data.get('search_keywords'))}")

        search_keywords = data.get('search_keywords', [])
        if search_keywords:
            print(f"  Search keywords ({len(search_keywords)}): {search_keywords[:5]}...")
        else:
            print(f"  ⚠️  No search_keywords field!")
        print()

# Summary
print("\n=== Summary ===")
active_configs = [c for c in configs if not c.to_dict().get('deleted', False)]
configs_with_keywords = [
    c for c in active_configs
    if c.to_dict().get('search_keywords')
]
total_keywords = sum(
    len(c.to_dict().get('search_keywords', []))
    for c in configs_with_keywords
)

print(f"Total configs: {len(configs)}")
print(f"Active configs: {len(active_configs)}")
print(f"Configs with search_keywords: {len(configs_with_keywords)}")
print(f"Total search keywords: {total_keywords}")

if total_keywords == 0:
    print("\n❌ NO KEYWORDS CONFIGURED!")
    print("The discovery service will not discover anything without keywords.")
    print("\nTo fix: Add 'search_keywords' array to your ip_configs documents.")
