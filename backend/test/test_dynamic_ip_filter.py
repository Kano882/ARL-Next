"""
test_dynamic_ip_filter.py
=========================
Unit tests for Scheme 4: Adaptive Dynamic IP / P2P-CDN Edge Node Filter.
Ensures:
  1. Standard hyphenated dynamic IP subdomains are detected and dropped when self-resolving.
  2. Prefixed (node-, ip-, edge-) dynamic IP subdomains are detected and dropped.
  3. Underscore-separated dynamic IP subdomains are detected and dropped.
  4. RFC 1918 Private/Reserved IPs are 100% EXEMPTED (Never dropped).
  5. Versioned subdomains / non-self-resolving regular business domains are 100% PRESERVED (0 False Positive).
"""
import pytest
import sys
from pathlib import Path

# Add backend to path
BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.utils.domain import (
    extract_dynamic_ip_from_domain,
    is_private_or_reserved_ip,
    is_dynamic_ip_edge_domain
)


class TestDynamicIPExtraction:
    def test_standard_hyphen(self):
        assert extract_dynamic_ip_from_domain("117-187-206-224.volcsiriusbd.com") == "117.187.206.224"
        assert extract_dynamic_ip_from_domain("36-158-45-44.volcsiriusbd.com") == "36.158.45.44"

    def test_prefixed_variants(self):
        assert extract_dynamic_ip_from_domain("node-117-187-206-224.cdn.com") == "117.187.206.224"
        assert extract_dynamic_ip_from_domain("ip-117-187-206-224.cdn.com") == "117.187.206.224"
        assert extract_dynamic_ip_from_domain("edge-117-187-206-224.cdn.com") == "117.187.206.224"
        assert extract_dynamic_ip_from_domain("pcdn-117-187-206-224.cdn.com") == "117.187.206.224"

    def test_underscore_variant(self):
        assert extract_dynamic_ip_from_domain("117_187_206_224.cdn.com") == "117.187.206.224"

    def test_invalid_ranges(self):
        # 999 is invalid IPv4 octet
        assert extract_dynamic_ip_from_domain("999-187-206-224.example.com") is None

    def test_regular_domains(self):
        assert extract_dynamic_ip_from_domain("icp.volcsiriusbd.com") is None
        assert extract_dynamic_ip_from_domain("api.feishu.cn") is None
        assert extract_dynamic_ip_from_domain("login.douyin.com") is None


class TestPrivateIPExemption:
    def test_rfc1918_private(self):
        assert is_private_or_reserved_ip("10.10.1.5") is True
        assert is_private_or_reserved_ip("192.168.1.1") is True
        assert is_private_or_reserved_ip("172.16.0.1") is True
        assert is_private_or_reserved_ip("127.0.0.1") is True

    def test_public_ips(self):
        assert is_private_or_reserved_ip("117.187.206.224") is False
        assert is_private_or_reserved_ip("36.158.45.44") is False
        assert is_private_or_reserved_ip("180.184.50.159") is False


class TestSelfResolvingFilter:
    def test_edge_cdn_matching_dropped(self):
        # Self-resolving public IP -> Must be dropped (True)
        assert is_dynamic_ip_edge_domain("117-187-206-224.volcsiriusbd.com", ["117.187.206.224"]) is True
        assert is_dynamic_ip_edge_domain("node-117-187-206-224.cdn.com", ["117.187.206.224"]) is True
        assert is_dynamic_ip_edge_domain("117_187_206_224.cdn.com", ["117.187.206.224"]) is True

    def test_rfc1918_private_exempted(self):
        # Even if matching internal IP -> Must NOT be dropped (False)
        assert is_dynamic_ip_edge_domain("10-10-1-5.corp.internal", ["10.10.1.5"]) is False
        assert is_dynamic_ip_edge_domain("192-168-1-100.company.local", ["192.168.1.100"]) is False

    def test_version_subdomain_zero_false_positive(self):
        # Regular business with version in name -> Non-self-resolving -> Must NOT be dropped (False)
        assert is_dynamic_ip_edge_domain("api-v1-0-0-1.company.com", ["203.0.113.88"]) is False
        assert is_dynamic_ip_edge_domain("service-1-2-3-4.corp.com", ["180.184.50.159"]) is False

    def test_regular_business_subdomains(self):
        assert is_dynamic_ip_edge_domain("icp.volcsiriusbd.com", ["180.184.50.159"]) is False
        assert is_dynamic_ip_edge_domain("feishu.cn", ["110.242.68.4"]) is False
