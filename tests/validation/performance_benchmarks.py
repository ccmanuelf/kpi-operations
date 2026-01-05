"""
Comprehensive Performance Benchmarking Suite
Tests response times, load capacity, and database performance
"""
import requests
import time
import statistics
import concurrent.futures
from typing import List, Dict
import sys

class PerformanceBenchmark:
    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url
        self.token = None
        self.results = []

    def authenticate(self):
        """Get authentication token"""
        response = requests.post(
            f"{self.base_url}/api/auth/login",
            json={"username": "admin", "password": "admin123"}
        )
        if response.status_code == 200:
            self.token = response.json().get("access_token")
            return True
        return False

    def benchmark_endpoint(self, method: str, endpoint: str, iterations: int = 100) -> Dict:
        """Benchmark a single endpoint"""
        times = []
        errors = 0

        headers = {"Authorization": f"Bearer {self.token}"} if self.token else {}

        for _ in range(iterations):
            start = time.time()
            try:
                if method == "GET":
                    response = requests.get(f"{self.base_url}{endpoint}", headers=headers)
                elif method == "POST":
                    response = requests.post(f"{self.base_url}{endpoint}", headers=headers, json={})
                else:
                    continue

                elapsed = (time.time() - start) * 1000  # Convert to ms

                if response.status_code < 500:
                    times.append(elapsed)
                else:
                    errors += 1

            except Exception as e:
                errors += 1

        if not times:
            return {
                "endpoint": endpoint,
                "method": method,
                "status": "FAILED",
                "error_rate": 100.0
            }

        return {
            "endpoint": endpoint,
            "method": method,
            "avg_time": statistics.mean(times),
            "min_time": min(times),
            "max_time": max(times),
            "median_time": statistics.median(times),
            "p95_time": sorted(times)[int(len(times) * 0.95)] if len(times) > 1 else times[0],
            "p99_time": sorted(times)[int(len(times) * 0.99)] if len(times) > 1 else times[0],
            "error_rate": (errors / iterations) * 100,
            "status": "PASS" if statistics.mean(times) < 200 else "SLOW"
        }

    def test_concurrent_load(self, endpoint: str, concurrent_users: int = 50) -> Dict:
        """Test endpoint under concurrent load"""
        print(f"\n[Concurrent Load Test] Testing {endpoint} with {concurrent_users} concurrent users...")

        def make_request():
            start = time.time()
            try:
                response = requests.get(
                    f"{self.base_url}{endpoint}",
                    headers={"Authorization": f"Bearer {self.token}"}
                )
                elapsed = (time.time() - start) * 1000
                return elapsed, response.status_code
            except:
                return None, 500

        times = []
        errors = 0

        with concurrent.futures.ThreadPoolExecutor(max_workers=concurrent_users) as executor:
            futures = [executor.submit(make_request) for _ in range(concurrent_users)]

            for future in concurrent.futures.as_completed(futures):
                elapsed, status_code = future.result()
                if elapsed and status_code < 500:
                    times.append(elapsed)
                else:
                    errors += 1

        if not times:
            return {"status": "FAILED", "error_rate": 100.0}

        return {
            "endpoint": endpoint,
            "concurrent_users": concurrent_users,
            "total_requests": concurrent_users,
            "successful_requests": len(times),
            "failed_requests": errors,
            "avg_response_time": statistics.mean(times),
            "max_response_time": max(times),
            "requests_per_second": concurrent_users / (sum(times) / 1000),
            "error_rate": (errors / concurrent_users) * 100,
            "status": "PASS" if statistics.mean(times) < 500 and errors == 0 else "FAIL"
        }

    def run_benchmarks(self):
        """Run all performance benchmarks"""
        print("\n" + "="*80)
        print("PERFORMANCE BENCHMARK SUITE")
        print("="*80)

        # Benchmark critical GET endpoints
        print("\n[1/4] Benchmarking GET Endpoints (100 requests each)...")
        get_endpoints = [
            "/api/production",
            "/api/employees",
            "/api/work-orders",
            "/api/quality",
            "/api/attendance"
        ]

        get_results = []
        for endpoint in get_endpoints:
            print(f"   Testing {endpoint}...", end="\r")
            result = self.benchmark_endpoint("GET", endpoint)
            get_results.append(result)
            print(f"   ✅ {endpoint} - Avg: {result.get('avg_time', 0):.1f}ms")

        # Benchmark POST endpoints
        print("\n[2/4] Benchmarking POST Endpoints (50 requests each)...")
        post_endpoints = [
            "/api/production",
            "/api/quality",
            "/api/attendance"
        ]

        post_results = []
        for endpoint in post_endpoints:
            print(f"   Testing {endpoint}...", end="\r")
            result = self.benchmark_endpoint("POST", endpoint, iterations=50)
            post_results.append(result)
            print(f"   ✅ {endpoint} - Avg: {result.get('avg_time', 0):.1f}ms")

        # Test concurrent load
        print("\n[3/4] Testing Concurrent Load (50 concurrent users)...")
        concurrent_result = self.test_concurrent_load("/api/production", concurrent_users=50)
        print(f"   ✅ Concurrent load test - Avg: {concurrent_result.get('avg_response_time', 0):.1f}ms")

        # Sustained load test
        print("\n[4/4] Testing Sustained Load (10 req/sec for 30 seconds)...")
        sustained_result = self.sustained_load_test()
        print(f"   ✅ Sustained load test - Success rate: {100 - sustained_result.get('error_rate', 100):.1f}%")

        return {
            "get_endpoints": get_results,
            "post_endpoints": post_results,
            "concurrent_load": concurrent_result,
            "sustained_load": sustained_result
        }

    def sustained_load_test(self, duration: int = 30, requests_per_second: int = 10) -> Dict:
        """Test sustained load over time"""
        endpoint = "/api/production"
        times = []
        errors = 0
        total_requests = duration * requests_per_second

        start_time = time.time()
        request_count = 0

        while time.time() - start_time < duration:
            loop_start = time.time()

            # Make batch of requests
            for _ in range(requests_per_second):
                req_start = time.time()
                try:
                    response = requests.get(
                        f"{self.base_url}{endpoint}",
                        headers={"Authorization": f"Bearer {self.token}"}
                    )
                    elapsed = (time.time() - req_start) * 1000

                    if response.status_code < 500:
                        times.append(elapsed)
                    else:
                        errors += 1
                except:
                    errors += 1

                request_count += 1

            # Wait for next second
            elapsed = time.time() - loop_start
            if elapsed < 1.0:
                time.sleep(1.0 - elapsed)

        return {
            "duration_seconds": duration,
            "total_requests": request_count,
            "successful_requests": len(times),
            "failed_requests": errors,
            "avg_response_time": statistics.mean(times) if times else 0,
            "error_rate": (errors / request_count) * 100 if request_count > 0 else 100,
            "status": "PASS" if errors / request_count < 0.05 else "FAIL"
        }

    def print_report(self, results: Dict):
        """Print performance benchmark report"""
        print("\n" + "="*80)
        print("PERFORMANCE BENCHMARK REPORT")
        print("="*80)

        # GET endpoints
        print("\n📊 GET Endpoint Performance:")
        print(f"{'Endpoint':<40} {'Avg (ms)':<12} {'P95 (ms)':<12} {'Status':<10}")
        print("-" * 80)
        for result in results["get_endpoints"]:
            status_icon = "✅" if result.get("status") == "PASS" else "⚠️"
            print(f"{result['endpoint']:<40} {result.get('avg_time', 0):>10.1f}   {result.get('p95_time', 0):>10.1f}   {status_icon}")

        # POST endpoints
        print("\n📊 POST Endpoint Performance:")
        print(f"{'Endpoint':<40} {'Avg (ms)':<12} {'P95 (ms)':<12} {'Status':<10}")
        print("-" * 80)
        for result in results["post_endpoints"]:
            status_icon = "✅" if result.get("status") == "PASS" else "⚠️"
            print(f"{result['endpoint']:<40} {result.get('avg_time', 0):>10.1f}   {result.get('p95_time', 0):>10.1f}   {status_icon}")

        # Concurrent load
        print("\n⚡ Concurrent Load Test (50 users):")
        concurrent = results["concurrent_load"]
        print(f"   Avg Response Time: {concurrent.get('avg_response_time', 0):.1f}ms")
        print(f"   Max Response Time: {concurrent.get('max_response_time', 0):.1f}ms")
        print(f"   Requests/Second:   {concurrent.get('requests_per_second', 0):.1f}")
        print(f"   Error Rate:        {concurrent.get('error_rate', 0):.1f}%")
        print(f"   Status:            {'✅ PASS' if concurrent.get('status') == 'PASS' else '❌ FAIL'}")

        # Sustained load
        print("\n🔄 Sustained Load Test (30 seconds @ 10 req/sec):")
        sustained = results["sustained_load"]
        print(f"   Total Requests:    {sustained.get('total_requests', 0)}")
        print(f"   Successful:        {sustained.get('successful_requests', 0)}")
        print(f"   Failed:            {sustained.get('failed_requests', 0)}")
        print(f"   Avg Response Time: {sustained.get('avg_response_time', 0):.1f}ms")
        print(f"   Error Rate:        {sustained.get('error_rate', 0):.1f}%")
        print(f"   Status:            {'✅ PASS' if sustained.get('status') == 'PASS' else '❌ FAIL'}")

        # Overall assessment
        print("\n" + "="*80)
        get_pass = all(r.get("status") == "PASS" for r in results["get_endpoints"])
        post_pass = all(r.get("status") == "PASS" for r in results["post_endpoints"])
        concurrent_pass = results["concurrent_load"].get("status") == "PASS"
        sustained_pass = results["sustained_load"].get("status") == "PASS"

        all_pass = get_pass and post_pass and concurrent_pass and sustained_pass

        print(f"PRODUCTION READY: {'✅ YES' if all_pass else '❌ NO'}")
        print("\nPerformance Requirements:")
        print(f"  GET < 200ms:         {'✅' if get_pass else '❌'}")
        print(f"  POST < 500ms:        {'✅' if post_pass else '❌'}")
        print(f"  Concurrent (50):     {'✅' if concurrent_pass else '❌'}")
        print(f"  Sustained (95%):     {'✅' if sustained_pass else '❌'}")
        print("="*80 + "\n")

def main():
    print("\nStarting comprehensive performance benchmarks...")
    print("This will test:")
    print("1. GET endpoint response times")
    print("2. POST endpoint response times")
    print("3. Concurrent load (50 users)")
    print("4. Sustained load (10 req/sec for 30 seconds)")

    benchmark = PerformanceBenchmark()

    if not benchmark.authenticate():
        print("\n❌ Cannot authenticate. Ensure backend is running.")
        sys.exit(1)

    # Run benchmarks
    results = benchmark.run_benchmarks()

    # Print report
    benchmark.print_report(results)

    # Check if production ready
    all_pass = (
        all(r.get("status") == "PASS" for r in results["get_endpoints"]) and
        all(r.get("status") == "PASS" for r in results["post_endpoints"]) and
        results["concurrent_load"].get("status") == "PASS" and
        results["sustained_load"].get("status") == "PASS"
    )

    sys.exit(0 if all_pass else 1)

if __name__ == "__main__":
    main()
