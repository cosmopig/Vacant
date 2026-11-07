<!-- provenance: vq-el4.4 (2026-11-07)。e014 原始任務無 request.md（factoid 提問）。
     來源：dabstep-1273-pi-C-r1 events.jsonl 的第一則 user message（使用者原文；非 hidden/、非 scorer.py）。
     原始文字 sha256 前 16 位：3dc8a6212f4623c5 -->
You are an expert data analyst and you will answer factoid questions by referencing files in the data directory: `/app/data/`
Don't forget to reference any documentation in the data dir before answering a question.

Here is the question you need to answer: For credit transactions, what would be the average fee that the card scheme GlobalCard would charge for a transaction value of 10 EUR?

Here are the guidelines you MUST follow when answering the question above: Answer must be just a number expressed in EUR rounded to 6 decimals. If a question does not have a relevant or applicable answer for the task, please respond with 'Not Applicable'

Before answering the question, reference any documentation in the data dir and leverage its information in your reasoning / planning.

When you have computed the final answer, write ONLY the final answer to `/app/answer.txt` (e.g. if the answer is 42, the file should contain just `42`).
