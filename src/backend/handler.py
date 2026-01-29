"""
Backend Lambda - Simulates your upstream service.
Demonstrates that X-Customer-ID header is received from API Gateway.
"""
import json
from typing import Any


def lambda_handler(event: dict, context: Any) -> dict:
    """
    Backend handler that receives the X-Customer-ID header
    set by API Gateway from the authorizer context.
    
    In a real scenario, this would be your Private Link endpoint
    forwarding to Kubernetes ingress.
    """
    print(f"Event: {json.dumps(event)}")
    
    # Extract headers (API Gateway v2 format)
    headers = event.get('headers', {})
    
    # Get the X-Customer-ID header set by API Gateway
    customer_id = headers.get('x-customer-id', 'unknown')
    customer_name = headers.get('x-customer-name', 'unknown')
    
    # Get request details
    request_context = event.get('requestContext', {})
    http_info = request_context.get('http', {})
    
    path = http_info.get('path', '/')
    method = http_info.get('method', 'GET')
    source_ip = http_info.get('sourceIp', 'unknown')
    
    # Build response showing the routing information
    response_body = {
        'message': 'Request successfully routed!',
        'routing': {
            'customerId': customer_id,
            'customerName': customer_name,
            'targetNamespace': f'cust-{customer_id}',  # Simulated K8s namespace
            'targetService': f'{customer_id}-service.cust-{customer_id}.svc.cluster.local'
        },
        'request': {
            'path': path,
            'method': method,
            'sourceIp': source_ip
        },
        'headers': {
            'x-customer-id': customer_id,
            'x-customer-name': customer_name,
            'host': headers.get('host', 'unknown'),
            'user-agent': headers.get('user-agent', 'unknown')
        },
        'info': 'In production, this request would be forwarded to your K8s ingress '
                'which routes based on the X-Customer-ID header to the correct namespace.'
    }
    
    return {
        'statusCode': 200,
        'headers': {
            'Content-Type': 'application/json',
            'X-Customer-ID': customer_id,  # Echo back for verification
            'X-Routed-To': f'cust-{customer_id}'
        },
        'body': json.dumps(response_body, indent=2)
    }
