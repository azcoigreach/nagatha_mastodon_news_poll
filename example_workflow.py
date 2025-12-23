"""Example usage script for Mastodon Poll Provider."""
import httpx
import json
import time


BASE_URL = "http://localhost:9000"
CORE_URL = "http://localhost:8000/api/v1"


def print_section(title: str):
    """Print a section header."""
    print(f"\n{'=' * 60}")
    print(f"  {title}")
    print(f"{'=' * 60}\n")


def main():
    """Demonstrate the full workflow."""
    
    print_section("1. Check Provider Health")
    
    response = httpx.get(f"{BASE_URL}/health")
    print(f"Status: {response.status_code}")
    print(json.dumps(response.json(), indent=2))
    
    
    print_section("2. View Current Settings")
    
    response = httpx.get(f"{BASE_URL}/settings")
    print(json.dumps(response.json(), indent=2))
    
    
    print_section("3. Run News Cycle")
    
    response = httpx.post(
        f"{BASE_URL}/run-cycle",
        json={
            "hashtags": ["#uspol"],
            "post_limit": 50
        }
    )
    print(f"Status: {response.status_code}")
    result = response.json()
    print(json.dumps(result, indent=2))
    
    if result.get("success"):
        task_id = result.get("task_id")
        print(f"\n⏳ Task queued: {task_id}")
        print("Waiting for task to complete (this may take a minute)...")
        
        # Wait for task completion
        for i in range(30):
            time.sleep(2)
            # Check task status via Nagatha Core
            try:
                status_response = httpx.get(f"{CORE_URL}/tasks/{task_id}")
                if status_response.status_code == 200:
                    task_status = status_response.json()
                    if task_status.get("status") in ["SUCCESS", "FAILURE"]:
                        print(f"\n✅ Task completed with status: {task_status.get('status')}")
                        break
                    print(f"   [{i*2}s] Status: {task_status.get('status')}")
            except:
                pass
    
    
    print_section("4. View Pending Polls")
    
    response = httpx.get(f"{BASE_URL}/polls", params={"status_filter": "pending"})
    polls_data = response.json()
    print(f"Found {polls_data.get('count', 0)} pending polls")
    
    if polls_data.get("count", 0) > 0:
        poll = polls_data["polls"][0]
        poll_id = poll["id"]
        print(f"\nFirst poll ({poll_id}):")
        print(f"  Question: {poll['poll_data']['question']}")
        print(f"  Options: {[opt['text'] for opt in poll['poll_data']['options']]}")
        
        
        print_section("5. Moderate Poll (Approve)")
        
        response = httpx.post(
            f"{BASE_URL}/polls/{poll_id}/moderate",
            json={
                "approved": True,
                "moderator_notes": "Looks good for posting!"
            }
        )
        print(f"Status: {response.status_code}")
        print(json.dumps(response.json(), indent=2))
        
        
        print_section("6. Statistics")
        
        response = httpx.get(f"{BASE_URL}/stats")
        print(json.dumps(response.json(), indent=2))
        
        
        print("\n" + "=" * 60)
        print("  Workflow Complete!")
        print("=" * 60)
        print(f"\n📝 To post the approved poll to Mastodon:")
        print(f'   curl -X POST {BASE_URL}/post-poll \\')
        print(f'     -H "Content-Type: application/json" \\')
        print(f'     -d \'{{"poll_id": "{poll_id}"}}\'')
        print()
    else:
        print("\n⚠️  No polls generated. Check:")
        print("   - Mastodon credentials are correct")
        print("   - Posts exist for the specified hashtags")
        print("   - OpenAI API key is valid")
        print("\nView logs: docker-compose logs -f worker")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"\n❌ Error: {e}")
        print("\nMake sure the service is running:")
        print("   docker-compose up -d")
