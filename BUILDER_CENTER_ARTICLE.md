# Pass Customer Identity from JWT to Backend Services Using HTTP API Gateway

## Overview

Enterprise applications often need to pass customer identity information from an authenticated request to backend services. While the JWT token contains this information, backend services shouldn't need to parse and validate JWTs themselves - they should receive the customer identity as a simple header.

This article shows you how to use Amazon API Gateway HTTP APIs with a Lambda authorizer to extract customer information from JWT tokens and pass it as a custom header (`X-Customer-ID`) to your backend services. This enables clean separation between authentication at the API Gateway layer and identity consumption at the backend.

## Problem Statement

Consider a typical enterprise architecture where:

1. **Clients authenticate with JWT tokens** - containing customer/user identity claims
2. **Backend services need customer context** - to apply business logic, logging, or audit trails
3. **Backend shouldn't parse JWTs** - separation of concerns means the backend trusts the API Gateway to handle authentication

The challenge: HTTP API Gateway doesn't automatically extract JWT claims and forward them as headers. You need a mechanism to:
- Extract the `customer_id` (or similar claim) from the JWT
- Pass it to the backend as a header the service can easily consume

## Architecture

![Architecture Diagram](generated-diagrams/x-customer-id-architecture-eks.png)

The request flow:

1. Client sends a request with a JWT token in the Authorization header
2. API Gateway invokes the Lambda authorizer
3. Lambda authorizer validates the JWT and extracts the `customer_id` claim
4. Lambda returns the customer ID in the authorizer context
5. API Gateway adds `X-Customer-ID` header using the authorizer context
6. Request reaches your backend service with the customer identity header attached
7. Backend uses the header for business logic, logging, or downstream calls

## Prerequisites

Before you begin, ensure you have:

- An AWS account with permissions to create API Gateway, Lambda, and IAM resources
- AWS CLI v2 installed and configured
- AWS SAM CLI installed
- Python 3.11 or later

## Implementation

### Step 1: Create the Lambda Authorizer

The Lambda authorizer validates the JWT token and extracts customer information. Create `src/authorizer/handler.py`:

```python
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
    try:
        # Extract token from Authorization header
        auth_header = event.get('headers', {}).get('authorization', '')
        
        if not auth_header:
            return {'isAuthorized': False}
        
        # Remove 'Bearer ' prefix
        token = auth_header.replace('Bearer ', '').replace('bearer ', '')
        
        if not token:
            return {'isAuthorized': False}
        
        # Decode and validate JWT
        payload = decode_jwt(token)
        
        if not payload:
            return {'isAuthorized': False}
        
        # Extract customer information from token
        customer_id = payload.get('customer_id') or payload.get('tenant_id') or payload.get('sub')
        customer_name = payload.get('customer_name') or payload.get('name') or customer_id
        
        if not customer_id:
            return {'isAuthorized': False}
        
        # Return authorized response with customer context
        # These values will be available as $context.authorizer.customerId
        return {
            'isAuthorized': True,
            'context': {
                'customerId': customer_id,
                'customerName': customer_name
            }
        }
        
    except Exception as e:
        print(f"Authorization error: {str(e)}")
        return {'isAuthorized': False}


def decode_jwt(token: str) -> dict | None:
    """
    Decode and validate a JWT token.
    
    Note: This is a simplified implementation for demonstration.
    In production, use PyJWT with proper signature verification
    and consider using Amazon Cognito or another identity provider.
    """
    try:
        parts = token.split('.')
        if len(parts) != 3:
            return None
        
        header_b64, payload_b64, signature_b64 = parts
        
        # Decode payload
        payload_b64 += '=' * (4 - len(payload_b64) % 4)
        payload_json = base64.urlsafe_b64decode(payload_b64)
        payload = json.loads(payload_json)
        
        # Verify signature
        jwt_secret = os.environ.get('JWT_SECRET')
        message = f"{header_b64}.{payload_b64}".encode()
        expected_signature = base64.urlsafe_b64encode(
            hmac.new(jwt_secret.encode(), message, hashlib.sha256).digest()
        ).rstrip(b'=').decode()
        
        if not hmac.compare_digest(signature_b64, expected_signature):
            return None
        
        return payload
        
    except Exception as e:
        print(f"JWT decode error: {str(e)}")
        return None
```

### Step 2: Create the SAM Template

The SAM template defines the HTTP API Gateway with the Lambda authorizer and header mapping. Create `template.yaml`:

```yaml
AWSTemplateFormatVersion: '2010-09-09'
Transform: AWS::Serverless-2016-10-31
Description: HTTP API Gateway with X-Customer-ID header passthrough

Parameters:
  Environment:
    Type: String
    Default: dev
  JwtSecret:
    Type: String
    NoEcho: true

Globals:
  Function:
    Architectures:
      - arm64

Resources:
  # Lambda Authorizer
  AuthorizerFunction:
    Type: AWS::Serverless::Function
    Properties:
      FunctionName: !Sub ${AWS::StackName}-authorizer
      CodeUri: src/authorizer/
      Handler: handler.lambda_handler
      Runtime: python3.13
      Timeout: 30
      MemorySize: 256
      Environment:
        Variables:
          JWT_SECRET: !Ref JwtSecret

  AuthorizerFunctionPermission:
    Type: AWS::Lambda::Permission
    Properties:
      FunctionName: !Ref AuthorizerFunction
      Action: lambda:InvokeFunction
      Principal: apigateway.amazonaws.com
      SourceArn: !Sub arn:aws:execute-api:${AWS::Region}:${AWS::AccountId}:${HttpApi}/*

  # HTTP API Gateway
  HttpApi:
    Type: AWS::ApiGatewayV2::Api
    Properties:
      Name: !Sub ${AWS::StackName}-api
      ProtocolType: HTTP

  # Lambda Authorizer Configuration
  HttpApiAuthorizer:
    Type: AWS::ApiGatewayV2::Authorizer
    Properties:
      ApiId: !Ref HttpApi
      AuthorizerType: REQUEST
      AuthorizerUri: !Sub arn:aws:apigateway:${AWS::Region}:lambda:path/2015-03-31/functions/${AuthorizerFunction.Arn}/invocations
      AuthorizerPayloadFormatVersion: "2.0"
      EnableSimpleResponses: true
      IdentitySource:
        - $request.header.Authorization
      Name: JwtAuthorizer

  # Integration with Backend
  HttpApiIntegration:
    Type: AWS::ApiGatewayV2::Integration
    Properties:
      ApiId: !Ref HttpApi
      IntegrationType: HTTP_PROXY
      IntegrationUri: !Ref BackendEndpoint
      IntegrationMethod: ANY
      ConnectionType: VPC_LINK
      ConnectionId: !Ref VpcLink
      # Map authorizer context to X-Customer-ID header
      RequestParameters:
        append:header.X-Customer-ID: $context.authorizer.customerId
        append:header.X-Customer-Name: $context.authorizer.customerName

  # Route
  HttpApiRoute:
    Type: AWS::ApiGatewayV2::Route
    Properties:
      ApiId: !Ref HttpApi
      RouteKey: $default
      AuthorizationType: CUSTOM
      AuthorizerId: !Ref HttpApiAuthorizer
      Target: !Sub integrations/${HttpApiIntegration}

  # Stage
  HttpApiStage:
    Type: AWS::ApiGatewayV2::Stage
    Properties:
      ApiId: !Ref HttpApi
      StageName: !Ref Environment
      AutoDeploy: true

Outputs:
  ApiEndpoint:
    Value: !Sub https://${HttpApi}.execute-api.${AWS::Region}.amazonaws.com/${Environment}
```

### Step 3: Configure Header Mapping

The key configuration is the `RequestParameters` in the integration:

```yaml
RequestParameters:
  append:header.X-Customer-ID: $context.authorizer.customerId
  append:header.X-Customer-Name: $context.authorizer.customerName
```

This tells API Gateway to:
1. Take the `customerId` value from the authorizer context (`$context.authorizer.customerId`)
2. Add it as the `X-Customer-ID` header to the request sent to your backend

### Step 4: Consume the Header in Your Backend

Your backend service receives the `X-Customer-ID` header and can use it directly:

```python
# Example: Flask backend
from flask import Flask, request

app = Flask(__name__)

@app.route('/api/orders')
def get_orders():
    customer_id = request.headers.get('X-Customer-ID')
    customer_name = request.headers.get('X-Customer-Name')
    
    # Use customer_id for business logic
    orders = fetch_orders_for_customer(customer_id)
    
    # Include in audit logs
    app.logger.info(f"Orders requested by customer: {customer_id}")
    
    return {'customer': customer_id, 'orders': orders}
```

```java
// Example: Spring Boot backend
@RestController
public class OrderController {
    
    @GetMapping("/api/orders")
    public ResponseEntity<OrderResponse> getOrders(
            @RequestHeader("X-Customer-ID") String customerId,
            @RequestHeader("X-Customer-Name") String customerName) {
        
        // Use customerId for business logic
        List<Order> orders = orderService.findByCustomer(customerId);
        
        // Include in audit logs
        log.info("Orders requested by customer: {}", customerId);
        
        return ResponseEntity.ok(new OrderResponse(customerId, orders));
    }
}
```

## Testing the Solution

### Generate a Test Token

```python
#!/usr/bin/env python3
import json
import base64
import hmac
import hashlib
import time

def generate_token(customer_id: str, customer_name: str, secret: str) -> str:
    header = {"alg": "HS256", "typ": "JWT"}
    payload = {
        "customer_id": customer_id,
        "customer_name": customer_name,
        "iat": int(time.time()),
        "exp": int(time.time()) + 3600
    }
    
    header_b64 = base64.urlsafe_b64encode(
        json.dumps(header).encode()
    ).rstrip(b'=').decode()
    
    payload_b64 = base64.urlsafe_b64encode(
        json.dumps(payload).encode()
    ).rstrip(b'=').decode()
    
    message = f"{header_b64}.{payload_b64}".encode()
    signature = base64.urlsafe_b64encode(
        hmac.new(secret.encode(), message, hashlib.sha256).digest()
    ).rstrip(b'=').decode()
    
    return f"{header_b64}.{payload_b64}.{signature}"

if __name__ == "__main__":
    token = generate_token("customer1", "Acme Corp", "your-jwt-secret")
    print(f"Token: {token}")
```

### Test the API

```bash
# Deploy the stack
sam build && sam deploy --guided

# Generate a token
TOKEN=$(python3 generate_token.py)

# Call the API
curl -H "Authorization: Bearer $TOKEN" \
     https://your-api-id.execute-api.us-east-1.amazonaws.com/dev/api/orders
```

## Use Cases

This pattern is useful when your backend needs customer identity for:

- **Audit logging** - Record which customer made each request
- **Business logic** - Apply customer-specific rules or configurations
- **Downstream API calls** - Pass customer context to other internal services
- **Data filtering** - Scope database queries to the customer's data
- **Rate limiting** - Apply per-customer rate limits at the backend

## Security Considerations

1. **Strip incoming X-Customer-ID headers** - Malicious clients could send their own header. Use a WAF rule or Lambda@Edge to strip any incoming X-Customer-ID headers before they reach API Gateway.

2. **Use proper JWT validation** - The example uses simplified JWT validation. In production, use PyJWT with proper signature verification, or use Amazon Cognito as your identity provider.

3. **Secure the JWT secret** - Store the JWT secret in AWS Secrets Manager.

4. **Use HTTPS only** - Ensure all communication uses HTTPS.

## Why X-Customer-ID Instead of Host Header?

You might wonder why we use a custom header. HTTP API Gateway cannot dynamically modify the Host header - it's set automatically based on the integration endpoint. Custom headers like `X-Customer-ID` provide a clean way to pass identity information that your backend can easily consume.

| Header | Can API Gateway Set It? | Notes |
|--------|------------------------|-------|
| `Host` | ❌ No | Set automatically based on integration endpoint |
| `X-Customer-ID` | ✅ Yes | Custom headers can be set from authorizer context |

## Cleanup

```bash
sam delete --stack-name x-customer-id-routing
```

## Conclusion

This pattern provides clean separation of concerns:

- **API Gateway** handles JWT validation and extracts customer identity
- **Backend services** receive customer identity as a simple header
- **No JWT parsing in backend** - the backend trusts the API Gateway layer

The `X-Customer-ID` header approach keeps your backend code simple while ensuring customer context flows through your entire request chain.

## Source Code

The complete working example is available on GitHub: [https://github.com/sambit19/x-customer-id-routing](https://github.com/sambit19/x-customer-id-routing)

## Related Resources

- [Amazon API Gateway HTTP APIs](https://docs.aws.amazon.com/apigateway/latest/developerguide/http-api.html)
- [Lambda Authorizers for HTTP APIs](https://docs.aws.amazon.com/apigateway/latest/developerguide/http-api-lambda-authorizer.html)
- [VPC Links for HTTP APIs](https://docs.aws.amazon.com/apigateway/latest/developerguide/http-api-vpc-links.html)
