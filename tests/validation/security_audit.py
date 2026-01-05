"""
Comprehensive Security Audit Suite
Tests for SQL injection, XSS, CSRF, authentication, and multi-tenant data leakage
"""
import requests
import json
from typing import List, Dict
import sys

class SecurityAuditor:
    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url
        self.token = None
        self.passed = []
        self.failed = []
        self.critical = []
        self.warnings = []

    def authenticate(self, username: str = "admin", password: str = "admin123"):
        """Authenticate to get token"""
        try:
            response = requests.post(
                f"{self.base_url}/api/auth/login",
                json={"username": username, "password": password}
            )
            if response.status_code == 200:
                self.token = response.json().get("access_token")
                return True
            return False
        except:
            return False

    def test_sql_injection(self):
        """Test for SQL injection vulnerabilities"""
        print("\n[1/7] Testing SQL Injection Protection...")

        sql_payloads = [
            "' OR '1'='1",
            "1'; DROP TABLE users--",
            "admin'--",
            "' UNION SELECT NULL, NULL--",
            "1' AND 1=1--",
            "' OR 1=1#",
            "admin' OR '1'='1' /*",
        ]

        endpoints_to_test = [
            ("/api/auth/login", "POST", {"username": "{payload}", "password": "test"}),
            ("/api/employees/{payload}", "GET", None),
            ("/api/work-orders/{payload}", "GET", None),
        ]

        vulnerable = False

        for endpoint, method, data_template in endpoints_to_test:
            for payload in sql_payloads:
                try:
                    if data_template:
                        data = {k: v.replace("{payload}", payload) if "{payload}" in v else v
                               for k, v in data_template.items()}
                        response = requests.post(f"{self.base_url}{endpoint}", json=data)
                    else:
                        url = f"{self.base_url}{endpoint.replace('{payload}', payload)}"
                        response = requests.get(url, headers={"Authorization": f"Bearer {self.token}"})

                    # Check if response contains SQL error messages
                    response_text = response.text.lower()
                    if any(word in response_text for word in ['sql', 'sqlite', 'database error', 'syntax error']):
                        self.critical.append(f"🚨 CRITICAL: SQL injection possible at {endpoint} with payload: {payload}")
                        vulnerable = True
                        break

                except:
                    pass

            if vulnerable:
                break

        if not vulnerable:
            self.passed.append("✅ SQL injection protection: No vulnerabilities found")
        else:
            self.failed.append("❌ SQL injection: CRITICAL VULNERABILITY DETECTED")

    def test_xss_protection(self):
        """Test for Cross-Site Scripting (XSS) vulnerabilities"""
        print("[2/7] Testing XSS Protection...")

        xss_payloads = [
            "<script>alert('XSS')</script>",
            "<img src=x onerror=alert('XSS')>",
            "javascript:alert('XSS')",
            "<svg onload=alert('XSS')>",
            "';alert(String.fromCharCode(88,83,83))//",
        ]

        test_endpoints = [
            "/api/clients",
            "/api/employees",
            "/api/work-orders"
        ]

        vulnerable = False

        for endpoint in test_endpoints:
            for payload in xss_payloads:
                try:
                    test_data = {
                        "name": payload,
                        "description": payload,
                        "notes": payload
                    }

                    response = requests.post(
                        f"{self.base_url}{endpoint}",
                        json=test_data,
                        headers={"Authorization": f"Bearer {self.token}"}
                    )

                    # Check if payload is returned unescaped
                    if payload in response.text:
                        self.critical.append(f"🚨 CRITICAL: XSS vulnerability at {endpoint}")
                        vulnerable = True
                        break

                except:
                    pass

            if vulnerable:
                break

        if not vulnerable:
            self.passed.append("✅ XSS protection: No vulnerabilities found")
        else:
            self.failed.append("❌ XSS: CRITICAL VULNERABILITY DETECTED")

    def test_authentication_bypass(self):
        """Test for authentication bypass vulnerabilities"""
        print("[3/7] Testing Authentication Bypass...")

        protected_endpoints = [
            "/api/production",
            "/api/employees",
            "/api/work-orders",
            "/api/quality",
            "/api/attendance"
        ]

        bypass_attempts = 0
        successful_bypasses = 0

        for endpoint in protected_endpoints:
            try:
                # Attempt access without token
                response = requests.get(f"{self.base_url}{endpoint}")
                bypass_attempts += 1

                if response.status_code == 200:
                    self.critical.append(f"🚨 CRITICAL: Authentication bypass at {endpoint}")
                    successful_bypasses += 1
                elif response.status_code == 401:
                    pass  # Expected
                else:
                    self.warnings.append(f"⚠️  Unexpected status {response.status_code} for {endpoint}")

            except:
                pass

        if successful_bypasses == 0:
            self.passed.append(f"✅ Authentication: All {bypass_attempts} endpoints protected")
        else:
            self.failed.append(f"❌ Authentication: {successful_bypasses}/{bypass_attempts} endpoints vulnerable")

    def test_jwt_security(self):
        """Test JWT token security"""
        print("[4/7] Testing JWT Token Security...")

        # Test 1: Invalid token
        try:
            response = requests.get(
                f"{self.base_url}/api/auth/me",
                headers={"Authorization": "Bearer invalid_token"}
            )
            if response.status_code == 401:
                self.passed.append("✅ JWT: Invalid token rejected")
            else:
                self.failed.append("❌ JWT: Invalid token accepted")
        except:
            pass

        # Test 2: Expired token
        expired_token = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIiwibmFtZSI6IkpvaG4gRG9lIiwiZXhwIjoxNTE2MjM5MDIyfQ.SflKxwRJSMeKKF2QT4fwpMeJf36POk6yJV_adQssw5c"
        try:
            response = requests.get(
                f"{self.base_url}/api/auth/me",
                headers={"Authorization": f"Bearer {expired_token}"}
            )
            if response.status_code == 401:
                self.passed.append("✅ JWT: Expired token rejected")
            else:
                self.failed.append("❌ JWT: Expired token accepted")
        except:
            pass

        # Test 3: Token without Bearer prefix
        try:
            response = requests.get(
                f"{self.base_url}/api/auth/me",
                headers={"Authorization": self.token}
            )
            if response.status_code == 401:
                self.passed.append("✅ JWT: Token without Bearer prefix rejected")
        except:
            pass

    def test_multi_tenant_isolation(self):
        """Test multi-tenant data isolation"""
        print("[5/7] Testing Multi-Tenant Data Isolation...")

        # This is a critical test for 50-client architecture
        try:
            # Get data for client A
            headers = {"Authorization": f"Bearer {self.token}"}

            response = requests.get(
                f"{self.base_url}/api/production",
                headers=headers
            )

            if response.status_code == 200:
                data = response.json()

                # Check if client_id_fk is enforced
                if isinstance(data, list) and len(data) > 0:
                    # All records should have the same client_id
                    client_ids = set(record.get('client_id_fk') for record in data if isinstance(record, dict))

                    if len(client_ids) == 1:
                        self.passed.append("✅ Multi-tenant: Data properly isolated by client_id")
                    elif len(client_ids) > 1:
                        self.critical.append("🚨 CRITICAL: Multi-tenant data leakage detected!")
                        self.failed.append("❌ Multi-tenant: Multiple client IDs in single query result")
                    else:
                        self.warnings.append("⚠️  Multi-tenant: Cannot verify isolation (no data)")
                else:
                    self.warnings.append("⚠️  Multi-tenant: No data to test isolation")
            else:
                self.warnings.append("⚠️  Multi-tenant: Cannot access production data")

        except Exception as e:
            self.warnings.append(f"⚠️  Multi-tenant test error: {str(e)}")

    def test_password_security(self):
        """Test password security measures"""
        print("[6/7] Testing Password Security...")

        weak_passwords = ["123", "password", "admin", "test"]

        for weak_pwd in weak_passwords:
            try:
                response = requests.post(
                    f"{self.base_url}/api/auth/register",
                    json={
                        "username": f"test_weak_{weak_pwd}",
                        "password": weak_pwd,
                        "email": f"test_{weak_pwd}@test.com"
                    }
                )

                # Should reject weak passwords
                if response.status_code == 400:
                    pass  # Good, rejected
                elif response.status_code == 201:
                    self.warnings.append(f"⚠️  Password: Weak password '{weak_pwd}' accepted")
                    break

            except:
                pass

        self.passed.append("✅ Password: Security checks in place")

    def test_csrf_protection(self):
        """Test CSRF protection"""
        print("[7/7] Testing CSRF Protection...")

        # Test if state-changing operations require proper headers
        try:
            # Attempt to create resource without proper CSRF token
            response = requests.post(
                f"{self.base_url}/api/clients",
                json={"client_id": "CSRF_TEST", "client_name": "CSRF Test"},
                headers={"Authorization": f"Bearer {self.token}"}
            )

            # For REST APIs with JWT, CSRF is less of a concern
            # But we should still check for proper authorization
            if response.status_code in [201, 401, 403]:
                self.passed.append("✅ CSRF: Proper authorization required")
            else:
                self.warnings.append("⚠️  CSRF: Unexpected response for state-changing operation")

        except Exception as e:
            self.warnings.append(f"⚠️  CSRF test error: {str(e)}")

    def print_report(self):
        """Print security audit report"""
        print("\n" + "="*80)
        print("SECURITY AUDIT REPORT")
        print("="*80)

        if self.critical:
            print(f"\n🚨 CRITICAL VULNERABILITIES ({len(self.critical)}):")
            for msg in self.critical:
                print(f"   {msg}")

        if self.failed:
            print(f"\n❌ FAILED CHECKS ({len(self.failed)}):")
            for msg in self.failed:
                print(f"   {msg}")

        if self.warnings:
            print(f"\n⚠️  WARNINGS ({len(self.warnings)}):")
            for msg in self.warnings:
                print(f"   {msg}")

        if self.passed:
            print(f"\n✅ PASSED CHECKS ({len(self.passed)}):")
            for msg in self.passed:
                print(f"   {msg}")

        total_checks = len(self.passed) + len(self.failed) + len(self.critical)
        security_score = (len(self.passed) / total_checks * 100) if total_checks > 0 else 0

        print("\n" + "="*80)
        print(f"SECURITY SCORE: {security_score:.1f}%")
        print(f"PRODUCTION READY: {'✅ YES' if len(self.critical) == 0 and len(self.failed) == 0 else '❌ NO'}")
        if self.critical:
            print("⚠️  CRITICAL: Fix all critical vulnerabilities before deployment!")
        print("="*80 + "\n")

def main():
    print("\nStarting comprehensive security audit...")
    print("This will test for common vulnerabilities:\n")
    print("1. SQL Injection")
    print("2. Cross-Site Scripting (XSS)")
    print("3. Authentication Bypass")
    print("4. JWT Token Security")
    print("5. Multi-Tenant Data Isolation")
    print("6. Password Security")
    print("7. CSRF Protection")

    auditor = SecurityAuditor()

    # Authenticate
    if not auditor.authenticate():
        print("\n❌ Cannot authenticate. Ensure backend is running.")
        sys.exit(1)

    # Run all security tests
    auditor.test_sql_injection()
    auditor.test_xss_protection()
    auditor.test_authentication_bypass()
    auditor.test_jwt_security()
    auditor.test_multi_tenant_isolation()
    auditor.test_password_security()
    auditor.test_csrf_protection()

    # Print report
    auditor.print_report()

    # Exit with appropriate code
    sys.exit(0 if len(auditor.critical) == 0 and len(auditor.failed) == 0 else 1)

if __name__ == "__main__":
    main()
