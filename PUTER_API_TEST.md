# Puter API Test Results
**Date:** 2026-04-13 | **Tester:** Claude Opus 4.6 + hackkejr

## Budget
- **25,000,000 units/month = $0.25/month**
- **Reset: รายเดือน (อัตโนมัติ)**
- 1 unit = $0.00000001

## Models ที่ใช้ได้ / ใช้ไม่ได้

| Model | Status |
|-------|--------|
| openai/gpt-5-nano | OK |
| openai/gpt-5.4 | OK |
| google/gemini-2.5-flash | OK |
| deepseek/deepseek-v3.2 | OK |
| mistralai/devstral-2512 | OK |
| anthropic/claude-* | FAIL (500) |
| meta-llama/* | FAIL (502) |

## ราคาจริง (ทดสอบ 2026-04-13)

### ต่อ 1 ล้าน tokens

| Model | Input/1M | Output/1M |
|-------|---------|----------|
| gemini-2.5-flash | $0.30 | $0.08 |
| gpt-5-nano | $0.05 | $0.40 |
| deepseek-v3.2 | - | $4.13 |
| devstral-2512 | - | $4.41 |
| gpt-5.4 | $2.50 | $15.00 |

### ต่อ 1 request (~500 tokens output)

| Model | Cost/request | Max requests/month |
|-------|-------------|-------------------|
| gemini-2.5-flash | 4,760 units | ~5,252 |
| gpt-5-nano | 20,100 units | ~1,243 |
| deepseek-v3.2 | 206,472 units | ~121 |
| devstral-2512 | 220,560 units | ~113 |
| gpt-5.4 | ~750,000 units | ~15 |

## Coding Quality Test

**Prompt:** "Write a Python function that reads CSV, removes duplicates, writes to new file"

| Model | Code Quality | Tool Calling | Speed |
|-------|-------------|-------------|-------|
| gemini-2.5-flash | ดี (docstring, error handling, สมบูรณ์) | OK | เร็ว |
| gpt-5-nano | ได้ (2000 tokens) | OK | เร็ว |
| deepseek-v3.2 | ดีมาก | OK | ปานกลาง |
| devstral-2512 | ดีมาก (coding-focused) | OK | ปานกลาง |
| gpt-5.4 | ดีมาก | OK | ช้า |

## ข้อจำกัด

- **Temperature:** ห้ามส่ง (gpt-5-nano รับแค่ default=1)
- **Rate limit:** ไม่พบ (5 requests ติดกันผ่านหมด ~1.7s/req)
- **Max tokens:** ขอได้ถึง 32000 แต่ output จริงขึ้นกับ model (~4700 max)
- **Long context:** 6000+ input tokens ใช้ได้ปกติ
- **Streaming:** ใช้ได้ (OpenAI SSE format)
- **Auth:** Token ไม่มี exp (ไม่หมดอายุ จนกว่า logout/revoke)

## แนะนำ

1. **Default: `gemini-2.5-flash`** — ถูกสุด คุณภาพดี ใช้ได้ 5,000+ ครั้ง/เดือน
2. **งาน coding ยาก: `deepseek-v3.2`** — ฉลาดกว่า แต่ใช้ได้แค่ ~120 ครั้ง/เดือน
3. **อย่าใช้ `gpt-5.4`** — แพงมาก ได้แค่ ~15 ครั้ง/เดือน

## API Endpoint

```
POST https://api.puter.com/puterai/openai/v1/chat/completions
Authorization: Bearer <puter_token>
Content-Type: application/json
```

## Settings (ToonCode)

```json
{
  "api_provider": "puter",
  "puter_token": "YOUR_TOKEN",
  "default_model": "google/gemini-2.5-flash",
  "auto_approve": true
}
```

## Metering API

```
GET https://api.puter.com/metering/usage
Authorization: Bearer <puter_token>
```
