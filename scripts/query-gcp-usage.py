#!/usr/bin/env python3
"""Query actual Gemini API usage from Google Cloud Monitoring."""

import requests
import subprocess
from datetime import datetime, timedelta, timezone

def get_gemini_usage_from_gcp(project_id="copycat-429012", hours=24):
    """
    Get actual Gemini API usage from Cloud Monitoring.

    Returns dict with:
    - total_requests: Number of API calls
    - total_errors: Number of failed calls
    - response_codes: Breakdown by status code
    """
    # Get auth token
    token = subprocess.check_output(['gcloud', 'auth', 'print-access-token']).decode().strip()

    # Time range
    end_time = datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')
    start_time = (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat().replace('+00:00', 'Z')

    url = f'https://monitoring.googleapis.com/v3/projects/{project_id}/timeSeries'
    params = {
        'filter': 'metric.type="aiplatform.googleapis.com/prediction/online/response_count"',
        'interval.startTime': start_time,
        'interval.endTime': end_time
    }

    headers = {
        'Authorization': f'Bearer {token}',
        'Content-Type': 'application/json'
    }

    print(f"📊 Querying Cloud Monitoring for {project_id}")
    print(f"   Time range: last {hours} hours\n")

    response = requests.get(url, params=params, headers=headers)

    if response.status_code != 200:
        print(f"❌ Error {response.status_code}: {response.text}")
        return None

    data = response.json()
    time_series = data.get('timeSeries', [])

    print(f"✅ Found {len(time_series)} time series\n")

    # Aggregate metrics
    total_requests = 0
    by_response_code = {}

    for ts in time_series:
        response_code = ts.get('metric', {}).get('labels', {}).get('response_code', 'unknown')

        # Sum all points
        points_total = 0
        for point in ts.get('points', []):
            value = int(point.get('value', {}).get('int64Value', 0))
            points_total += value

        total_requests += points_total
        by_response_code[response_code] = by_response_code.get(response_code, 0) + points_total

        print(f"  Response code {response_code}: {points_total} requests")

    total_errors = sum(count for code, count in by_response_code.items() if code != '200')

    print(f"\n" + "="*60)
    print(f"📈 SUMMARY")
    print(f"="*60)
    print(f"Total requests: {total_requests}")
    print(f"Successful (200): {by_response_code.get('200', 0)}")
    print(f"Errors: {total_errors}")
    print(f"="*60)

    return {
        'total_requests': total_requests,
        'successful_requests': by_response_code.get('200', 0),
        'total_errors': total_errors,
        'by_response_code': by_response_code,
    }


if __name__ == "__main__":
    import sys
    project_id = sys.argv[1] if len(sys.argv) > 1 else "copycat-429012"
    hours = int(sys.argv[2]) if len(sys.argv) > 2 else 24

    get_gemini_usage_from_gcp(project_id, hours)
