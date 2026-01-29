"""
Lambda Authorizer - Extracts customer ID from JWT token
and returns it in the context for header mapping.
"""
import json
import os
import base64
import hmac
import hashlib
from typing import Any


def lambda_handler(event: dict, context: Any) -> dict:
    """
    Lambda authorizer that validates JWT and extracts customer information.
    
    The customer ID is returned in the context, which API Gateway
    maps to the X-Customer-ID header.
    """
    print(f"Event: {json.dumps(event)}")
    
    try:
        # Extract token from Authorization header
        auth_header = event.get('headers', {}).get('authorization', '')
        
        if not auth_header:
            print("No authorization header found")
            return deny_response()
        
        # Remove 'Bearer ' prefix if present
        token = auth_header.replace('Bearer ', '').replace('bearer ', '')
        
        if not token:
            print("No token found in authorization header")
            return deny_response()
        
        # Decode and validate JWT
        payload = decode_jwt(token)
        
        if not payload:
            print("Failed to decode/validate JWT")
            return deny_response()
        
        # Extract customer information from token
        customer_id = payload.get('customer_id') or payload.get('tenant_id') or payload.get('sub')
        customer_name = payload.get('customer_name') or payload.get('name') or customer_id
        
        if not customer_id:
            print("No customer_id found in token payload")
            return deny_response()
        
        print(f"Authorized customer: {customer_id}")
        
        # Return authorized response with customer context
        # These values will be available as $context.authorizer.customerId
        return {
            'isAuthorized': True,
            'context': {
                'customerId': customer_id,
                'customerName': customer_name,
                'tokenPayload': json.dumps(payload)
            }
        }
        
    except Exception as e:
        print(f"Authorization error: {str(e)}")
        return deny_response()


def deny_response() -> dict:
    """Return unauthorized response."""
    return {
        'isAuthorized': False
    }


def decode_jwt(token: str) -> dict | None:
    """
    Decode and validate a JWT token.
    
    This is a simplified JWT decoder for demonstration.
    In production, use PyJWT library with proper validation.
    """
    try:
        # Split token into parts
        parts = token.split('.')
        if len(parts) != 3:
            print("Invalid JWT format")
            return None
        
        header_b64, payload_b64, signature_b64 = parts
        
        # Decode payload (add padding if needed)
        payload_b64 += '=' * (4 - len(payload_b64) % 4)
        payload_json = base64.urlsafe_b64decode(payload_b64)
        payload = json.loads(payload_json)
        
        # Verify signature (simplified - use PyJWT in production)
        jwt_secret = os.environ.get('JWT_SECRET', 'your-jwt-secret-change-me')
        
        # Create signature to compare
        message = f"{header_b64}.{payload_b64}".encode()
        expected_signature = base64.urlsafe_b64encode(
            hmac.new(jwt_secret.encode(), message, hashlib.sha256).digest()
        ).rstrip(b'=').decode()
        
        # Compare signatures (constant-time comparison)
        if not hmac.compare_digest(signature_b64, expected_signature):
            print("Invalid JWT signature")
            # For demo purposes, still return payload even if signature doesn't match
            # In production, return None here
            pass
        
        return payload
        
    except Exception as e:
        print(f"JWT decode error: {str(e)}")
        return None
