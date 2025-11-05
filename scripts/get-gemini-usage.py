#!/usr/bin/env python3
"""
Get actual Gemini API usage from Google Cloud Monitoring.

This script queries the Cloud Monitoring API for real Vertex AI usage metrics.
"""

from google.cloud import monitoring_v3
from datetime import datetime, timedelta, timezone
import sys

def get_gemini_usage(project_id="copycat-429012", hours=24):
    """
    Get Gemini API usage from Cloud Monitoring.

    Returns:
        dict with request_count, error_count, and other metrics
    """
    try:
        client = monitoring_v3.MetricServiceClient()
        project_name = f"projects/{project_id}"

        # Time range: last N hours
        now = datetime.now(timezone.utc)
        start_time = now - timedelta(hours=hours)

        interval = monitoring_v3.TimeInterval({
            "end_time": {"seconds": int(now.timestamp())},
            "start_time": {"seconds": int(start_time.timestamp())},
        })

        print(f"📊 Querying Vertex AI metrics for {project_id}")
        print(f"   Time range: {start_time.strftime('%Y-%m-%d %H:%M')} to {now.strftime('%Y-%m-%d %H:%M')} UTC\n")

        # Available Vertex AI metrics:
        metrics_to_check = [
            "aiplatform.googleapis.com/prediction/online/response_count",
            "aiplatform.googleapis.com/prediction/online/prediction_latencies",
            "aiplatform.googleapis.com/quota/generate_content_requests/usage",
            "aiplatform.googleapis.com/quota/generate_content_requests/limit",
        ]

        results = {}

        for metric_type in metrics_to_check:
            try:
                print(f"Checking: {metric_type}")

                request = monitoring_v3.ListTimeSeriesRequest(
                    name=project_name,
                    filter=f'metric.type="{metric_type}"',
                    interval=interval,
                    view=monitoring_v3.ListTimeSeriesRequest.TimeSeriesView.FULL,
                )

                time_series = client.list_time_series(request=request)

                total_value = 0
                count = 0

                for ts in time_series:
                    print(f"  Found time series: {ts.metric.labels}")
                    for point in ts.points:
                        if hasattr(point.value, 'int64_value'):
                            total_value += point.value.int64_value
                        elif hasattr(point.value, 'double_value'):
                            total_value += point.value.double_value
                        count += 1

                if count > 0:
                    results[metric_type] = {
                        'total': total_value,
                        'data_points': count
                    }
                    print(f"  ✅ Total: {total_value} ({count} data points)\n")
                else:
                    print(f"  ⚠️  No data found\n")

            except Exception as e:
                print(f"  ❌ Error: {e}\n")
                continue

        if not results:
            print("⚠️  No metrics found. This could mean:")
            print("   1. No Gemini API calls made in the last 24 hours")
            print("   2. Metrics not yet available (can take 1-5 minutes)")
            print("   3. API not enabled or permissions missing")
            return None

        print("\n" + "="*60)
        print("📈 SUMMARY")
        print("="*60)
        for metric, data in results.items():
            metric_name = metric.split('/')[-1]
            print(f"{metric_name}: {data['total']} (from {data['data_points']} samples)")

        return results

    except Exception as e:
        print(f"❌ Error querying Cloud Monitoring: {e}")
        import traceback
        traceback.print_exc()
        return None


if __name__ == "__main__":
    project_id = sys.argv[1] if len(sys.argv) > 1 else "copycat-429012"
    hours = int(sys.argv[2]) if len(sys.argv) > 2 else 24

    get_gemini_usage(project_id, hours)
