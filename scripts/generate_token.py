#!/usr/bin/env python3
"""
Generate JWT tokens for testing the X-Customer-ID routing.

Usage:
    python generate_token.py customer1
    python generate_token.py customer2 --name "Acme Corp"
"""
import argparse
import base64
import hashlib
import hmac
import json
import time


def generate_jwt(customer_id: str, customer_name: str = None, secret: str = 'your-jwt-secret-change-me') -> str:
    """Generate a JWT token with customer information."""
    
    # Header
    header = {
        'alg': 'HS256',
        'typ': 'JWT'
    }
    
    # Payload
    payload = {
        'customer_id': customer_id,
        'customer_name': customer_name or customer_id,
        'sub': customer_id,
        'iat': int(time.time()),
        'exp': int(time.time()) + 3600,  # 1 hour expiry
        'iss': 'x-customer-id-demo'
    }
    
    # Encode header and payload
    header_b64 = base64.urlsafe_b64encode(json.dumps(header).encode()).rstrip(b'=').decode()
    payload_b64 = base64.urlsafe_b64encode(json.dumps(payload).encode()).rstrip(b'=').decode()
    
    # Create signature
    message = f"{header_b64}.{payload_b64}".encode()
    signature = base64.urlsafe_b64encode(
        hmac.new(secret.encode(), message, hashlib.sha256).digest()
    ).rstrip(b'=').decode()
    
    return f"{header_b64}.{payload_b64}.{signature}"


def main():
    parser = argparse.ArgumentParser(description='Generate JWT tokens for testing')
    parser.add_argument('customer_id', help='Customer ID to include in token')
    parser.add_argument('--name', '-n', help='Customer name (optional)')
    parser.add_argument('--secret', '-s', default='your-jwt-secret-change-me', help='JWT secret')
    
    args = parser.parse_args()
    
    token = generate_jwt(args.customer_id, args.name, args.secret)
    
    print(f"\n{'='*60}")
    print(f"Generated JWT Token for: {args.customer_id}")
    print(f"{'='*60}\n")
    print(f"Token:\n{token}\n")
    print(f"{'='*60}")
    print(f"\nTest with curl:")
    print(f"{'='*60}\n")
    print(f'curl -H "Authorization: Bearer {token}" \\')
    print(f'     https://YOUR_API_ENDPOINT/test\n')
    
    # Decode and show payload
    payload_b64 = token.split('.')[1]
    payload_b64 += '=' * (4 - len(payload_b64) % 4)
    payload = json.loads(base64.urlsafe_b64decode(payload_b64))
    
    print(f"{'='*60}")
    print(f"Token Payload:")
    print(f"{'='*60}")
    print(json.dumps(payload, indent=2))


if __name__ == '__main__':
    main()
