# Max Images Processing Guide

The image analysis service now supports limiting the number of images processed in a batch run using the `max_images` parameter.

## Usage Examples

### Browser / GET Requests

```
http://localhost:8002/run?max_images=3
```

Process up to **3 images** from the default input folder.

```
http://localhost:8002/run?max_images=5&overwrite=true
```

Process up to **5 images**, re-processing any that already exist in MongoDB.

```
http://localhost:8002/run
```

Process **all images** (no limit).

### PowerShell / REST API

**Process 3 images:**
```powershell
$body = @{
    max_images = 3
} | ConvertTo-Json

Invoke-RestMethod -Uri "http://localhost:8002/run" `
    -Method POST `
    -ContentType "application/json" `
    -Body $body
```

**Process 5 images with custom folder:**
```powershell
$body = @{
    input_folder = "C:\path\to\images"
    max_images = 5
    overwrite = $false
} | ConvertTo-Json

Invoke-RestMethod -Uri "http://localhost:8002/run" `
    -Method POST `
    -ContentType "application/json" `
    -Body $body
```

**Process all images (no limit):**
```powershell
Invoke-RestMethod -Uri "http://localhost:8002/run" `
    -Method POST `
    -ContentType "application/json" `
    -Body "{}"
```

## Parameter Details

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `input_folder` | string | (configured default) | Path to folder containing images to process |
| `max_images` | integer | 0 | Maximum number of images to process. `0` = no limit |
| `overwrite` | boolean | false | If `true`, re-processes images that already exist in MongoDB |

## Response

All requests return a `RunResponse` containing:

```json
{
  "status": "ok",
  "total_images": 3,
  "ocr_detections": 3,
  "sentiment_inferences": 3,
  "face_detections": 2,
  "ocr_failures": 0,
  "emotion_failures": 0,
  "elapsed_seconds": 12.5
}
```

## Notes

- Images are processed in the order they're discovered in the folder
- The `max_images` limit is applied **after** filename validation (only valid images are counted)
- Results are always stored in MongoDB, regardless of the `max_images` setting
- If `overwrite=false` and an image was already processed, it is skipped (and still counts toward the limit)
