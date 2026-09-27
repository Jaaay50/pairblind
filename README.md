# pairblind

Behavioral comparison for OpenAI-compatible endpoints. A habit match is not proof of which model is behind the URL. A habit miss is not proof that someone swapped it.

Short open choices ("pick a number", "pick a mahjong tile") only describe a distribution. A sigmoid of that distance is a display scale, not an identity probability. This repo keeps those probes as a secondary signal and adds checks a habit-only mimic fails.

## What is better

- Blind items with a known answer: integer sum, exact JSON keys, and a nonce that must be echoed alone. Two endpoints are paired on the same nonce and compared with an exact McNemar test.
- Habit probes stay, but the report prints mode share, sample size, and JS divergence. It does not print an identity percent.
- No bundled "official fingerprint" that pretends to be a blind validation. You record your own reference from an endpoint you trust, and you date it.
- Standard library only. Key comes from an env var or a file and is not written to the JSONL. User-Agent is the default Python client, not a spoofed Codex or Claude CLI string.
- Local only. Nothing is uploaded.

## Limits

Temperature, a system prompt injected by the relay, quantization, and a model update all move habit distributions. Blind items catch a dumb substitute and a broken relay. They do not authenticate a vendor. A relay can still answer `1847293 + 9055117` correctly with a cheaper model. Read a pass as "this endpoint can do this item", not as "this endpoint is GPT".

## Run

```bash
python3 -m unittest discover -s tests -v
export PAIRBLIND_API_KEY=...   # or --key-file
python3 -m pairblind.cli collect \
  --base-url https://example.invalid/v1 \
  --model your-alias \
  --out .runs/left.jsonl \
  --repeats 20 \
  --nonce 0123456789abcdef
python3 -m pairblind.cli score .runs/left.jsonl --reference .runs/trusted.jsonl
python3 -m pairblind.cli compare .runs/left.jsonl .runs/right.jsonl
```

Use the same `--nonce` on both endpoints so the blind items pair.

## License

MIT.
