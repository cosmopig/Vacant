#!/usr/bin/env python3
"""Semi-synthetic invoice tasks with distractors."""
from __future__ import annotations

import argparse
import json
import random
from datetime import date, timedelta
from pathlib import Path

VENDORS = [
    "Northwind Traders", "Contoso Ltd", "Fabrikam Inc", "Adventure Works",
    "Tailspin Toys", "Wide World Importers", "Lucerne Publishing", "Humongous Insurance",
]
TEMPLATES = ["T1", "T2", "T3", "T4", "T5"]


def _fmt_money(x: float, cur: str) -> str:
    return f"{cur} {x:,.2f}"


def _render(task_rng: random.Random, template: str, corrupt: bool) -> dict:
    vendor = task_rng.choice(VENDORS)
    cur = task_rng.choice(["USD", "EUR", "GBP"])
    inv_d = date(2024, task_rng.randint(1, 12), task_rng.randint(1, 28))
    due_d = inv_d + timedelta(days=task_rng.choice([15, 30, 45]))
    sub = round(task_rng.uniform(120, 9800), 2)
    tax = round(sub * task_rng.choice([0.05, 0.08, 0.1, 0.2]), 2)
    tot = round(sub + tax, 2)
    oid = f"PO-{task_rng.randint(100000, 999999)}"

    distractors = [
        f"Previous balance (ignore): {_fmt_money(task_rng.uniform(10, 500), cur)}",
        f"Ship-to: Warehouse 7, not billing address",
        f"Reference quote #{task_rng.randint(1000,9999)} (unsigned)",
    ]

    if corrupt:
        # contradictory totals buried in text
        body = (
            f"INVOICE\nVendor: {vendor}\n"
            f"Invoice date: {inv_d.isoformat()}\nDue: {due_d.isoformat()}\n"
            f"Currency: {cur}\nOrder ID: {oid}\n"
            f"Subtotal: {_fmt_money(sub, cur)}\nTax: {_fmt_money(tax, cur)}\n"
            f"** Total due (typo): {_fmt_money(tot + 99.0, cur)} **\n"
            f"Corrected line — subtotal {sub:.2f}, tax {tax:.2f}, total should be {tot + 50:.2f} (pending audit)\n"
            + "\n".join(distractors)
        )
        gold = None
        answerable = False
    else:
        body = (
            f"--- {template} document ---\n"
            f"Please remit payment to {vendor}.\n"
            f"Invoice date {inv_d.isoformat()}; payment due {due_d.isoformat()}.\n"
            f"All amounts in {cur}.\n"
            f"Purchase order {oid}.\n"
            f"Subtotal: {sub:.2f}\n"
            f"Tax: {tax:.2f}\n"
            f"Total: {tot:.2f}\n"
            + "\n".join(distractors)
        )
        gold = {
            "vendor": vendor,
            "invoice_date": inv_d.isoformat(),
            "due_date": due_d.isoformat(),
            "currency": cur,
            "subtotal": f"{sub:.2f}",
            "tax": f"{tax:.2f}",
            "total": f"{tot:.2f}",
            "order_id": oid,
        }
        answerable = True

    return {
        "source_text": body,
        "gold": gold,
        "allowed_currencies": [cur],
        "answerable": answerable,
        "template_id": template,
    }


def generate(seed: int, n_dev: int, n_hold_ok: int, n_hold_bad: int) -> dict:
    rng = random.Random(seed)
    tasks = []
    for i in range(n_dev):
        tpl = TEMPLATES[i % len(TEMPLATES)]
        t = _render(rng, tpl, corrupt=False)
        t["task_id"] = f"dev_{i:03d}"
        tasks.append(t)
    for i in range(n_hold_ok):
        tpl = TEMPLATES[i % len(TEMPLATES)]
        t = _render(rng, tpl, corrupt=False)
        t["task_id"] = f"hold_{i:03d}"
        tasks.append(t)
    for i in range(n_hold_bad):
        tpl = TEMPLATES[i % len(TEMPLATES)]
        t = _render(rng, tpl, corrupt=True)
        t["task_id"] = f"hold_u_{i:03d}"
        tasks.append(t)
    dev_ids = [f"dev_{i:03d}" for i in range(n_dev)]
    hold_ids = [f"hold_{i:03d}" for i in range(n_hold_ok)]
    hold_u = [f"hold_u_{i:03d}" for i in range(n_hold_bad)]
    return {
        "schema": "vacant.trust_delivery_lift.round2/1",
        "seed": seed,
        "split": {
            "dev_ids": dev_ids,
            "holdout_answerable_ids": hold_ids,
            "holdout_unanswerable_ids": hold_u,
        },
        "fields": list(
            "vendor invoice_date due_date currency subtotal tax total order_id".split()
        ),
        "tasks": tasks,
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", type=int, default=20261128)
    ap.add_argument("--out", type=Path, default=Path(__file__).parent / "tasks_r2.json")
    args = ap.parse_args()
    bank = generate(args.seed, 20, 150, 50)
    args.out.write_text(json.dumps(bank, indent=2), encoding="utf-8")
    print(f"wrote {len(bank['tasks'])} tasks -> {args.out}")


if __name__ == "__main__":
    main()