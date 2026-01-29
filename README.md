# X-Customer-ID Header Routing with HTTP API Gateway

This example demonstrates how to dynamically set the `X-Customer-ID` header in HTTP API Gateway based on JWT token claims, enabling customer-based routing in downstream services (like Kubernetes ingress).

## Architecture

![X-Customer-ID Header Routing Architecture](generated-diagrams/x-customer-id-architecture-eks.png)

## Prerequisites

- AWS CLI configured with appropriate credentials
- AWS SAM CLI installed
- Python 3.11+

## Project Structure

```
x-customer-id-routing/
├── template.yaml              # SAM/CloudFormation template
├── src/
│   ├── authorizer/
│   │   ├── handler.py         # Lambda authorizer (extracts customer from JWT)
│   │   └── requirements.txt
│   └── backend/
│       ├── handler.py         # Backend Lambda (shows routing info)
│       └── requirements.txt
├── scripts/
│   ├── generate_token.py      # Generate test JWT tokens
│   └── test_api.sh            # Test the deployed API
└── README.md
```

## Deployment

### 1. Build the SAM application

```bash
cd x-customer-id-routing
sam build
```

### 2. Deploy to AWS

```bash
sam deploy --guided
```

Follow the prompts:
- Stack Name: `x-customer-id-routing`
- AWS Region: `us-east-1` (or your preferred region)
- Parameter Environment: `dev`
- Parameter JwtSecret: (enter a secret or use default for testing)
- Confirm changes before deploy: `Y`
- Allow SAM CLI IAM role creation: `Y`

### 3. Note the outputs

After deployment, note the `ApiEndpoint` output URL.

## Testing

### Generate a test token

```bash
python3 scripts/generate_token.py customer1 --name "Acme Corp"
```

Output:
```
============================================================
Generated JWT Token for: customer1
============================================================

Token:
eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...

============================================================
Test with curl:
============================================================

curl -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..." \
     https://YOUR_API_ENDPOINT/test
```

### Test the API

```bash
# Using the test script
chmod +x scripts/test_api.sh
./scripts/test_api.sh x-customer-id-routing

# Or manually with curl
API_ENDPOINT="https://xxxxx.execute-api.us-east-1.amazonaws.com/dev"
TOKEN=$(python3 scripts/generate_token.py customer1 | grep -A1 "Token:" | tail -1)

curl -H "Authorization: Bearer $TOKEN" "$API_ENDPOINT/test"
```

### Expected Response

```json
{
  "message": "Request successfully routed!",
  "routing": {
    "customerId": "customer1",
    "customerName": "Acme Corp",
    "targetNamespace": "cust-customer1",
    "targetService": "customer1-service.cust-customer1.svc.cluster.local"
  },
  "request": {
    "path": "/test",
    "method": "GET",
    "sourceIp": "x.x.x.x"
  },
  "headers": {
    "x-customer-id": "customer1",
    "x-customer-name": "Acme Corp"
  }
}
```

## How It Works

### 1. Lambda Authorizer

The authorizer extracts `customer_id` from the JWT token and returns it in the context:

```python
return {
    'isAuthorized': True,
    'context': {
        'customerId': customer_id,      # Available as $context.authorizer.customerId
        'customerName': customer_name
    }
}
```

### 2. API Gateway Header Mapping

The CloudFormation template maps authorizer context to headers:

```yaml
RequestParameters:
  append:header.X-Customer-ID: $context.authorizer.customerId
  append:header.X-Customer-Name: $context.authorizer.customerName
```

### 3. Backend Receives Header

The backend (or your K8s ingress) receives the `X-Customer-ID` header and can route accordingly.

## Integrating with Kubernetes Ingress

Replace the backend Lambda with a VPC Link to your Private Link endpoint. Your K8s ingress can then route based on the header:

### NGINX Ingress Example

```yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: customer-routing
  annotations:
    nginx.ingress.kubernetes.io/canary: "true"
    nginx.ingress.kubernetes.io/canary-by-header: "X-Customer-ID"
    nginx.ingress.kubernetes.io/canary-by-header-value: "customer1"
spec:
  rules:
  - http:
      paths:
      - path: /
        pathType: Prefix
        backend:
          service:
            name: customer1-service
            port:
              number: 80
```

### Dynamic Routing with NGINX ConfigMap

```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: nginx-config
data:
  nginx.conf: |
    map $http_x_customer_id $backend {
      customer1 "customer1-service.cust1.svc.cluster.local";
      customer2 "customer2-service.cust2.svc.cluster.local";
      default   "default-service.default.svc.cluster.local";
    }
    
    server {
      location / {
        proxy_pass http://$backend;
      }
    }
```

## Security Considerations

1. **Strip incoming X-Customer-ID headers** - API Gateway should overwrite any client-provided X-Customer-ID header
2. **Validate JWT properly** - Use PyJWT with proper signature verification in production
3. **Use HTTPS** - Always use HTTPS for token transmission
4. **Short token expiry** - Use short-lived tokens with refresh mechanism

## Cleanup

```bash
sam delete --stack-name x-customer-id-routing
```

## Customization

### Using a different JWT claim

Modify `src/authorizer/handler.py`:

```python
customer_id = payload.get('tenant_id')  # or 'org_id', 'account_id', etc.
```

### Adding more context headers

Update `template.yaml`:

```yaml
RequestParameters:
  append:header.X-Customer-ID: $context.authorizer.customerId
  append:header.X-Tenant-Tier: $context.authorizer.tenantTier
  append:header.X-Region: $context.authorizer.region
```

## Troubleshooting

### "Unauthorized" response
- Check that the JWT secret matches between token generation and Lambda environment
- Verify the Authorization header format: `Bearer <token>`

### Header not appearing
- Check CloudWatch logs for the authorizer Lambda
- Verify the authorizer is returning the context correctly
- Check API Gateway access logs for `$context.authorizer.customerId`

### Integration timeout
- Increase Lambda timeout in template.yaml
- Check VPC configuration if using Private Link

---

## Disclaimer

This project is provided as an example implementation only. Neither the author nor their employer is liable for any issues arising from its use. No technical support is provided or guaranteed. 

This example demonstrates a specific use case of AWS features. Any feature requests or bug reports related to AWS services should be submitted through the appropriate AWS support channels.

Use at your own risk.
