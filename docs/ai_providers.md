# AI providers

The brief narrative (insights, weather synthesis, verdict) is produced by an AI provider. Four backends (D8):

| Provider | Where the call goes | Notes |
|---|---|---|
| `ha_ai_task` | The user `ai_task.*` entity | Recommended -- the entity owns model + parameters. |
| `anthropic_direct` | api.anthropic.com | Bring your own API key. |
| `openai_direct` | api.openai.com | Bring your own API key. |
| `disabled` | No call | Degraded mode (D9) -- brief still generates, sections without AI content. |

Per D9, an AI failure NEVER breaks the brief: the response is parsed as JSON; if anything goes wrong (network, non-200, invalid JSON after 3 retries), `ai_status` becomes `degraded` and the AI output is empty.

## `ha_ai_task`

Forwards the prompt to any `ai_task.*` HA entity via the `ai_task.generate_data` service. The wrapped entity decides which backend to call.

```yaml
ai:
  provider_type: ha_ai_task
  config:
    entity_id: ai_task.google_ai_task
```

Validation: integration checks that `entity_id` is present in `hass.states.async_entity_ids("ai_task")`.

## `anthropic_direct`

Direct POST to `api.anthropic.com/v1/messages` via HA shared aiohttp client.

```yaml
ai:
  provider_type: anthropic_direct
  config:
    api_key: !secret anthropic_api_key
    model: claude-sonnet-4-7
```

Get an API key at https://console.anthropic.com. Per D22, prefer `secrets.yaml` for cleaner config.

## `openai_direct`

Direct POST to `api.openai.com/v1/chat/completions`.

```yaml
ai:
  provider_type: openai_direct
  config:
    api_key: !secret openai_api_key
    model: gpt-4o-mini
```

Get an API key at https://platform.openai.com.

## Retry policy (D8 + G14)

`generate_with_retry` runs up to 3 attempts with exponential back-off (60s / 120s / 240s) and validates the response parses as JSON. Back-off uses `asyncio.sleep` so the coordinator keeps processing other work.

Total worst case before degraded fallback: 7 minutes. Usually <1 minute when the first attempt succeeds.

## Prompts

Three English templates in `prompts/`: `morning_v1.txt`, `evening_v1.txt`, `weekly_v1.txt`. All include a `{{ language }}` directive so the model replies in the instance language (D20). Override via Options -> Advanced -> Prompt template override.

## Cost expectations

Per brief, the prompt is typically 2-5 KB JSON + 1 KB instructions. The response is 1-2 KB JSON. At Anthropic / OpenAI rates, a brief costs ~$0.001-0.01 depending on the model.

Setting `ai_provider: disabled` runs the brief at zero AI cost.
