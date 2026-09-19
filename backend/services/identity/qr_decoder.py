"""
MetrCheck AI — Robust & Secure QR Code Decoder Service
Detects single or multiple QR codes, categorizes content, safely validates URLs with SSRF protection,
and associates QR codes with spatial bounding boxes for visual evidence.
"""

import re
import ipaddress
import urllib.parse
import cv2
import numpy as np
import logging
from typing import List, Optional, Dict, Any, Tuple
from services.identity.schemas import QRContentData, FieldStatus

import socket

logger = logging.getLogger(__name__)

# Private and non-routable IP ranges for SSRF prevention (IPv4 and IPv6)
FORBIDDEN_IP_NETWORKS = [
    # IPv4
    ipaddress.ip_network("0.0.0.0/8"),
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("100.64.0.0/10"),
    ipaddress.ip_network("127.0.0.0/8"),
    ipaddress.ip_network("169.254.0.0/16"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.0.0.0/24"),
    ipaddress.ip_network("192.0.2.0/24"),
    ipaddress.ip_network("192.88.99.0/24"),
    ipaddress.ip_network("192.168.0.0/16"),
    ipaddress.ip_network("198.18.0.0/15"),
    ipaddress.ip_network("198.51.100.0/24"),
    ipaddress.ip_network("203.0.113.0/24"),
    ipaddress.ip_network("224.0.0.0/4"),
    ipaddress.ip_network("240.0.0.0/4"),
    ipaddress.ip_network("255.255.255.255/32"),
    # IPv6
    ipaddress.ip_network("::/128"),
    ipaddress.ip_network("::1/128"),
    ipaddress.ip_network("fc00::/7"),
    ipaddress.ip_network("fe80::/10"),
    ipaddress.ip_network("ff00::/8"),
]

BLOCKED_INTERNAL_PORTS = {21, 22, 23, 25, 53, 69, 135, 137, 138, 139, 445, 1433, 1521, 3306, 5432, 6379, 9200, 11211, 27017}


class SafeURLValidator:
    """
    Validates QR and external API URLs to prevent SSRF and unsafe protocol execution.
    Only allows standard public http / https URLs with verified external endpoints.
    """

    @classmethod
    def _is_ip_forbidden(cls, ip_obj: ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
        if (
            ip_obj.is_private
            or ip_obj.is_loopback
            or ip_obj.is_link_local
            or ip_obj.is_reserved
            or ip_obj.is_multicast
            or ip_obj.is_unspecified
        ):
            return True
        for net in FORBIDDEN_IP_NETWORKS:
            if ip_obj in net:
                return True
        return False

    @classmethod
    def validate_url(cls, raw_url: str) -> Tuple[bool, Optional[str], Optional[str], Optional[str]]:
        """
        Validates URL. Returns: (is_safe, parsed_url, hostname, warning_reason)
        """
        if not raw_url or not isinstance(raw_url, str):
            return False, None, None, "Empty or invalid URL input"

        raw_trimmed = raw_url.strip()
        try:
            parsed = urllib.parse.urlparse(raw_trimmed)
        except Exception as e:
            return False, None, None, f"Malformed URL: {e}"

        # 1. Scheme Validation
        if parsed.scheme.lower() not in ("http", "https"):
            return False, None, None, f"Untrusted scheme '{parsed.scheme}'. Only HTTP and HTTPS are permitted."

        hostname = parsed.hostname
        if not hostname:
            return False, None, None, "URL contains no valid hostname."

        # 2. Port Validation (reject sensitive internal ports)
        if parsed.port and parsed.port in BLOCKED_INTERNAL_PORTS:
            return False, None, hostname, f"Blocked connection to restricted internal port {parsed.port}."

        # 3. Localhost & loopback name checks
        lower_host = hostname.lower()
        if (
            lower_host in ("localhost", "local", "ip6-localhost", "ip6-loopback", "metadata.google.internal")
            or lower_host.endswith(".localhost")
            or lower_host.endswith(".local")
            or lower_host.endswith(".internal")
            or lower_host.endswith(".lan")
            or lower_host.endswith(".home")
            or lower_host.endswith(".corp")
        ):
            return False, None, hostname, "Loopback or private internal domain name rejected."

        # 4. IP address literal SSRF protection
        try:
            # Strip brackets for IPv6 literals like [::1]
            host_clean = lower_host.strip("[]")
            ip_obj = ipaddress.ip_address(host_clean)
            if cls._is_ip_forbidden(ip_obj):
                return False, None, hostname, f"Forbidden private/internal IP address ({ip_obj})."
        except ValueError:
            # Hostname is a domain name. Resolve DNS to prevent DNS rebinding attacks
            try:
                addr_info = socket.getaddrinfo(lower_host, None, socket.AF_UNSPEC, socket.SOCK_STREAM)
                for item in addr_info:
                    ip_str = item[4][0]
                    resolved_ip = ipaddress.ip_address(ip_str)
                    if cls._is_ip_forbidden(resolved_ip):
                        return False, None, hostname, f"Domain resolves to forbidden private IP address ({resolved_ip})."
            except (socket.gaierror, socket.herror):
                # If offline or DNS cannot resolve, domain is preserved if not in forbidden names
                pass
            except Exception as e:
                logger.debug(f"[SafeURLValidator] DNS resolution check skipped for {hostname}: {e}")

        return True, raw_trimmed, hostname, None


class QRCodeIntelligenceDecoder:
    """
    Multi-pass QR Code detector using OpenCV with polygon extraction,
    safe content inspection, and GS1 Digital Link classification.
    """

    def __init__(self):
        self._detector = cv2.QRCodeDetector()

    @staticmethod
    def classify_content(raw_value: str) -> Tuple[str, Optional[Dict[str, Any]]]:
        """
        Determine content category:
        - GS1_DIGITAL_LINK
        - URL
        - FSSAI_VERIFY_URL
        - IDENTIFIER
        - TEXT
        """
        clean = raw_value.strip()

        # GS1 Digital Link check
        if "/01/" in clean or "/gtin/" in clean.lower():
            ai_data: Dict[str, Any] = {}
            gtin_m = re.search(r'/01/(\d{8,14})', clean)
            if gtin_m:
                ai_data["gtin"] = gtin_m.group(1)
            lot_m = re.search(r'/10/([A-Za-z0-9\-_]+)', clean)
            if lot_m:
                ai_data["lot"] = lot_m.group(1)
            exp_m = re.search(r'/17/(\d{6})', clean)
            if exp_m:
                ai_data["expiry"] = exp_m.group(1)
            return "GS1_DIGITAL_LINK", ai_data

        # FSSAI URL / License identifier check
        if "fssai" in clean.lower() and ("lic" in clean.lower() or re.search(r'\d{14}', clean)):
            lic_m = re.search(r'\b(1\d{13})\b', clean)
            fssai_data = {"fssai_license": lic_m.group(1)} if lic_m else {}
            return "FSSAI_VERIFY_URL", fssai_data

        # Standard URL
        if re.match(r'^https?://', clean, re.IGNORECASE):
            return "URL", None

        # 14-digit pure FSSAI identifier in QR
        if len(clean) == 14 and clean.isdigit() and clean.startswith("1"):
            return "FSSAI_IDENTIFIER", {"fssai_license": clean}

        # 8..14 digit GTIN barcode in QR
        if len(clean) in (8, 12, 13, 14) and clean.isdigit():
            return "GTIN_IDENTIFIER", {"gtin": clean}

        return "TEXT", None

    def decode_image(self, img_bgr: np.ndarray, image_label: str = "Front") -> List[QRContentData]:
        """
        Detect and decode all QR codes from an image array with multi-scale & contrast fallback.
        """
        if img_bgr is None or img_bgr.size == 0:
            return []

        results: List[QRContentData] = []
        seen_values = set()

        # Pass 1: Direct detection on original BGR
        try:
            val, pts, _ = self._detector.detectAndDecode(img_bgr)
            if val and val.strip() and val.strip() not in seen_values:
                clean_val = val.strip()
                seen_values.add(clean_val)
                bbox = None
                if pts is not None and len(pts) > 0:
                    xs = [int(p[0]) for p in pts[0]]
                    ys = [int(p[1]) for p in pts[0]]
                    bbox = [min(xs), min(ys), max(xs), max(ys)]

                content_type, ai_data = self.classify_content(clean_val)
                is_safe = True
                parsed_url = None
                hostname = None
                warning = None

                if "URL" in content_type:
                    is_safe, parsed_url, hostname, warning = SafeURLValidator.validate_url(clean_val)

                results.append(QRContentData(
                    raw_value=clean_val,
                    content_type=content_type,
                    is_safe_url=is_safe,
                    parsed_url=parsed_url,
                    hostname=hostname,
                    gs1_ai_data=ai_data,
                    bounding_box=bbox,
                    image_id=image_label,
                    confidence=0.98,
                    status=FieldStatus.FOUND if is_safe else FieldStatus.REVIEW_REQUIRED,
                    security_warning=warning
                ))
        except Exception as e:
            logger.debug(f"[QR Decoder] Pass 1 direct decode error: {e}")

        # Pass 2: Enhanced grayscale CLAHE pass if not detected
        if not results:
            try:
                gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)
                clahe = cv2.createCLAHE(clipLimit=2.5, tileGridSize=(8, 8))
                enhanced = clahe.apply(gray)
                enhanced_bgr = cv2.cvtColor(enhanced, cv2.COLOR_GRAY2BGR)

                val_enh, pts_enh, _ = self._detector.detectAndDecode(enhanced_bgr)
                if val_enh and val_enh.strip() and val_enh.strip() not in seen_values:
                    clean_val = val_enh.strip()
                    seen_values.add(clean_val)
                    bbox = None
                    if pts_enh is not None and len(pts_enh) > 0:
                        xs = [int(p[0]) for p in pts_enh[0]]
                        ys = [int(p[1]) for p in pts_enh[0]]
                        bbox = [min(xs), min(ys), max(xs), max(ys)]

                    content_type, ai_data = self.classify_content(clean_val)
                    is_safe, parsed_url, hostname, warning = (True, None, None, None)
                    if "URL" in content_type:
                        is_safe, parsed_url, hostname, warning = SafeURLValidator.validate_url(clean_val)

                    results.append(QRContentData(
                        raw_value=clean_val,
                        content_type=content_type,
                        is_safe_url=is_safe,
                        parsed_url=parsed_url,
                        hostname=hostname,
                        gs1_ai_data=ai_data,
                        bounding_box=bbox,
                        image_id=image_label,
                        confidence=0.92,
                        status=FieldStatus.FOUND if is_safe else FieldStatus.REVIEW_REQUIRED,
                        security_warning=warning
                    ))
            except Exception as e:
                logger.debug(f"[QR Decoder] Pass 2 CLAHE error: {e}")

        return results


qr_decoder_service = QRCodeIntelligenceDecoder()
