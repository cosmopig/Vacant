# Twin-2K-500 as the test-phase ground truth

The self-filled C01–C16 / H01–H24 answers are not used in this test phase. Ground truth is the public dataset Twin-2K-500 (Toubia, Gui, Peng, Merlau, Li, and Chen, 2025; [arXiv:2505.17479](https://arxiv.org/abs/2505.17479); Hugging Face `LLM-Digital-Twin/Twin-2K-500`, config `wave_split`, CC BY 4.0, ungated).

- Calibration for RAW, SUMMARY, and STRUCTURED is that person's wave 1–3 answers, after dropping any item whose id or text also appears in wave 4.
- Holdout items are wave 4 questions with exactly two options. Labels stay in `labels.jsonl` and are not put in the profile.
- `persona_summary` is ignored. The published summary was built with wave 4 answers.
- RAW retrieves the top 8 calibration items. The full wave 1–3 text is about 95k characters, which does not fit a 32k-token context.
- STRUCTURED is length-matched to SUMMARY: whole rules are dropped from the end until the text is not longer than the summary.
- Other arms: leave-one-out population majority (no model call), demographics-only, and no profile.
- Test-retest is the per-person agreement between the earlier answer and the wave 4 answer on repeated binary items. Accuracy divided by that rate is reported separately. A rate of 0 does not become a number.

Preliminary reference, not a result of this checkout: a rough pilot on 294 people was about 83% test-retest and about 56% majority. The converter recomputes both on the participants actually sampled.

Nothing from the dataset is committed. The cache defaults to `~/.cache/vacant/twin2k500`.

```bash
python3 -m vacant_network.personal twin2k-prepare \
  --participants 20 --seed 20261109 \
  --cache ~/.cache/vacant/twin2k500 \
  --out "$HOME/vacant-twin2k-20"

VACANT_PERSONAL_API_KEY=ollama \
python3 -m vacant_network.personal twin2k-run \
  --config ops/personal_pilot/config.example.json \
  --prepared "$HOME/vacant-twin2k-20" \
  --backend openai \
  --out "$HOME/vacant-twin2k-20/run"
```

`twin2k-run --backend fixture` does not call the endpoint. The example config points at `http://127.0.0.1:11434/v1`, model `qwen3-coder:30b`, `pricing: local`.

Resume after a dropped tunnel. Completed cells stay. A `usage_unknown` row is not sent again.

```bash
python3 -m vacant_network.personal twin2k-run \
  --config ops/personal_pilot/config.kaggle.example.json \
  --prepared "$HOME/vacant-twin2k-20" \
  --backend openai \
  --out "$HOME/vacant-twin2k-20/run" \
  --resume
```

Kaggle notes (`zstd` before the Ollama installer, servers started with `start_new_session=True`, no `terminate` in the keep-alive cell): [docs/KAGGLE_OLLAMA.md](../../../docs/KAGGLE_OLLAMA.md).
