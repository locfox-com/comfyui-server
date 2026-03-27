# API Documentation

The ComfyUI AI Image Server provides a REST API for submitting image processing jobs and retrieving results.

## Base URL

```
http://localhost:80
```

## Authentication

Currently, the API does not require authentication. In production, implement API key or OAuth authentication.

---

## Health Check

### GET /health

Check API health status.

**Response:**
```json
{
  "status": "healthy",
  "version": "1.0.0"
}
```

---

## Jobs API

### Create Face Swap Job

### POST /api/v1/jobs/face-swap

Swap faces between two images.

**Request Body:**
```json
{
  "source_image_url": "https://example.com/source.jpg",
  "target_image_url": "https://example.com/target.jpg",
  "source_face_index": 0,
  "target_face_index": 0,
  "webhook_url": "https://example.com/webhook",
  "metadata": {
    "user_id": "user123"
  }
}
```

**Parameters:**
- `source_image_url` (string, required): URL of source image (face to extract)
- `target_image_url` (string, required): URL of target image (face to replace)
- `source_face_index` (integer, optional): Face index in source image (default: 0)
- `target_face_index` (integer, optional): Face index in target image (default: 0)
- `webhook_url` (string, optional): URL to receive job completion notification
- `metadata` (object, optional): Custom metadata for the job

**Response (202 Accepted):**
```json
{
  "job_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "pending",
  "operation": "face_swap",
  "created_at": "2024-01-15T10:30:00Z"
}
```

**Error Response (422):**
```json
{
  "detail": [
    {
      "loc": ["body", "source_image_url"],
      "msg": "field required",
      "type": "value_error.missing"
    }
  ]
}
```

---

### Create Upscale Job

### POST /api/v1/jobs/upscale

Upscale an image to higher resolution.

**Request Body:**
```json
{
  "image_url": "https://example.com/image.jpg",
  "scale_factor": 2,
  "model": "RealESRGAN_x4plus.pth",
  "webhook_url": "https://example.com/webhook",
  "metadata": {
    "user_id": "user123"
  }
}
```

**Parameters:**
- `image_url` (string, required): URL of image to upscale
- `scale_factor` (integer, optional): Scale factor 2 or 4 (default: 2)
- `model` (string, optional): Upscale model name (default: "RealESRGAN_x4plus.pth")
- `webhook_url` (string, optional): URL for completion notification
- `metadata` (object, optional): Custom metadata

**Response (202 Accepted):**
```json
{
  "job_id": "660e8400-e29b-41d4-a716-446655440001",
  "status": "pending",
  "operation": "upscale",
  "created_at": "2024-01-15T10:30:00Z"
}
```

---

### Create Remove Background Job

### POST /api/v1/jobs/remove-background

Remove background from an image.

**Request Body:**
```json
{
  "image_url": "https://example.com/image.jpg",
  "model": "RMBG-1.4.pth",
  "webhook_url": "https://example.com/webhook",
  "metadata": {
    "user_id": "user123"
  }
}
```

**Parameters:**
- `image_url` (string, required): URL of image to process
- `model` (string, optional): Background removal model (default: "RMBG-1.4.pth")
- `webhook_url` (string, optional): URL for completion notification
- `metadata` (object, optional): Custom metadata

**Response (202 Accepted):**
```json
{
  "job_id": "770e8400-e29b-41d4-a716-446655440002",
  "status": "pending",
  "operation": "remove_background",
  "created_at": "2024-01-15T10:30:00Z"
}
```

---

## Job Status API

### Get Job Status

### GET /api/v1/jobs/{job_id}

Get the status of a specific job.

**Path Parameters:**
- `job_id` (string, required): Job UUID

**Response (200 OK):**
```json
{
  "job_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "completed",
  "operation": "face_swap",
  "progress": 100,
  "input_data": {
    "source_image_url": "https://example.com/source.jpg",
    "target_image_url": "https://example.com/target.jpg"
  },
  "output_url": "https://r2.dev/output/result_550e8400.jpg",
  "error": null,
  "created_at": "2024-01-15T10:30:00Z",
  "started_at": "2024-01-15T10:30:05Z",
  "completed_at": "2024-01-15T10:31:15Z"
}
```

**Status Values:**
- `pending`: Job queued, waiting to be processed
- `processing`: Job is currently being processed
- `completed`: Job completed successfully
- `failed`: Job failed with an error

**Error Response (404 Not Found):**
```json
{
  "detail": "Job not found"
}
```

---

### List Jobs

### GET /api/v1/jobs

List all jobs with optional filtering.

**Query Parameters:**
- `status` (string, optional): Filter by status (`pending`, `processing`, `completed`, `failed`)
- `operation` (string, optional): Filter by operation type (`face_swap`, `upscale`, `remove_background`)
- `limit` (integer, optional): Maximum number of results (default: 50, max: 100)
- `offset` (integer, optional): Number of results to skip (default: 0)

**Example:**
```
GET /api/v1/jobs?status=completed&operation=face_swap&limit=10
```

**Response (200 OK):**
```json
{
  "total": 150,
  "jobs": [
    {
      "job_id": "550e8400-e29b-41d4-a716-446655440000",
      "status": "completed",
      "operation": "face_swap",
      "created_at": "2024-01-15T10:30:00Z",
      "completed_at": "2024-01-15T10:31:15Z"
    }
  ]
}
```

---

### Cancel Job

### DELETE /api/v1/jobs/{job_id}

Cancel a pending or processing job.

**Path Parameters:**
- `job_id` (string, required): Job UUID

**Response (200 OK):**
```json
{
  "job_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "cancelled",
  "message": "Job cancelled successfully"
}
```

**Error Response (400 Bad Request):**
```json
{
  "detail": "Cannot cancel job that is already completed"
}
```

---

## Webhook Notifications

When a job completes (successfully or with failure), the API sends a POST request to the provided webhook URL.

### Webhook Payload

**Success:**
```json
{
  "job_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "completed",
  "operation": "face_swap",
  "output_url": "https://r2.dev/output/result_550e8400.jpg",
  "metadata": {
    "user_id": "user123"
  },
  "timestamp": "2024-01-15T10:31:15Z"
}
```

**Failure:**
```json
{
  "job_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "failed",
  "operation": "face_swap",
  "error": "Failed to process image: Model not loaded",
  "metadata": {
    "user_id": "user123"
  },
  "timestamp": "2024-01-15T10:31:15Z"
}
```

### Webhook Best Practices

1. **Return 200 OK**: Always respond with `200 OK` to acknowledge receipt
2. **Retry Logic**: The API will retry failed webhook deliveries (up to 3 times)
3. **Idempotency**: Handle duplicate webhook notifications gracefully
4. **Verification**: Verify the job exists before processing the webhook

---

## Error Responses

### Standard Error Format

```json
{
  "detail": "Error message description"
}
```

### HTTP Status Codes

- `200 OK`: Successful request
- `202 Accepted`: Job accepted for processing
- `400 Bad Request`: Invalid request parameters
- `404 Not Found`: Resource not found
- `422 Unprocessable Entity`: Validation error
- `500 Internal Server Error`: Server error
- `503 Service Unavailable`: Service temporarily unavailable

### Common Errors

**Invalid URL:**
```json
{
  "detail": [
    {
      "loc": ["body", "image_url"],
      "msg": "invalid or missing URL scheme",
      "type": "value_error.url.scheme"
    }
  ]
}
```

**Missing Required Field:**
```json
{
  "detail": [
    {
      "loc": ["body", "source_image_url"],
      "msg": "field required",
      "type": "value_error.missing"
    }
  ]
}
```

---

## Rate Limiting

The API implements rate limiting to prevent abuse:

- **API Endpoints**: 10 requests per second per IP
- **WebSocket Connections**: 10 concurrent connections per IP
- **Burst Capacity**: 20 additional requests allowed temporarily

Rate limit headers are included in responses:

```
X-RateLimit-Limit: 10
X-RateLimit-Remaining: 7
X-RateLimit-Reset: 1705300800
```

When rate limited, the API returns `429 Too Many Requests`:

```json
{
  "detail": "Rate limit exceeded. Please try again later."
}
```

---

## WebSocket API

### Connect to Job Updates

### WS /ws/jobs/{job_id}

Receive real-time updates for a specific job.

**Example (JavaScript):**
```javascript
const ws = new WebSocket('ws://localhost/ws/jobs/550e8400-e29b-41d4-a716-446655440000');

ws.onmessage = (event) => {
  const data = JSON.parse(event.data);
  console.log('Job update:', data);
};

ws.onerror = (error) => {
  console.error('WebSocket error:', error);
};
```

**Message Format:**
```json
{
  "job_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "processing",
  "progress": 45,
  "message": "Processing image..."
}
```

---

## SDK Examples

### Python

```python
import requests

# Create face swap job
response = requests.post('http://localhost/api/v1/jobs/face-swap', json={
    'source_image_url': 'https://example.com/source.jpg',
    'target_image_url': 'https://example.com/target.jpg',
    'webhook_url': 'https://example.com/webhook'
})

job = response.json()
job_id = job['job_id']

# Poll for completion
while True:
    status = requests.get(f'http://localhost/api/v1/jobs/{job_id}')
    data = status.json()
    if data['status'] in ['completed', 'failed']:
        break
    time.sleep(2)

print(f"Output URL: {data['output_url']}")
```

### JavaScript/Node.js

```javascript
const axios = require('axios');

// Create upscale job
const response = await axios.post('http://localhost/api/v1/jobs/upscale', {
  image_url: 'https://example.com/image.jpg',
  scale_factor: 4
});

const { job_id } = response.data;

// Poll for completion
while (true) {
  const { data } = await axios.get(`http://localhost/api/v1/jobs/${job_id}`);
  if (data.status === 'completed' || data.status === 'failed') {
    console.log('Output URL:', data.output_url);
    break;
  }
  await new Promise(resolve => setTimeout(resolve, 2000));
}
```

---

## Testing the API

### cURL Examples

```bash
# Health check
curl http://localhost/health

# Create face swap job
curl -X POST http://localhost/api/v1/jobs/face-swap \
  -H "Content-Type: application/json" \
  -d '{
    "source_image_url": "https://example.com/source.jpg",
    "target_image_url": "https://example.com/target.jpg"
  }'

# Get job status
curl http://localhost/api/v1/jobs/{job_id}

# List completed jobs
curl "http://localhost/api/v1/jobs?status=completed&limit=10"
```

---

## Support

For API issues or questions:
- Check the [Deployment Guide](./DEPLOYMENT.md)
- Review logs: `docker compose logs -f api`
- Health check: `curl http://localhost/health`
- GitHub Issues: <repository-url>
