<!-- provenance: vq-el4.4 (2026-11-07)。e014 原始任務無 request.md（factoid 提問）。
     來源：dabstep-11-pi-A-r1 events.jsonl 的第一則 user message（使用者原文；非 hidden/、非 scorer.py）。
     原始文字 sha256 前 16 位：09d547031ef70635 -->
You are an expert data analyst and you will answer factoid questions by referencing files in the data directory: `/app/data/`
Don't forget to reference any documentation in the data dir before answering a question.

Here is the question you need to answer: What is the highest transaction amount (in EUR) recorded?

Here are the guidelines you MUST follow when answering the question above: Answer must be the exact number. If a question does not have a relevant or applicable answer for the task, please respond with 'Not Applicable'.

Before answering the question, reference any documentation in the data dir and leverage its information in your reasoning / planning.

When you have computed the final answer, write ONLY the final answer to `/app/answer.txt` (e.g. if the answer is 42, the file should contain just `42`).
