# C5 native-platform audit

Requested base: `claude/vacant-verification-redesign-jv7eou`.
Review branch created from `41f450f7f53e36737e56c3de00a8ab9b467e6a91`.

The reviewed `vacant_network/trace/evidence.py` has git blob
`f6f833967c1cfc7a1dccee2e2e4f5f6b05055449`.

The C5 archives contain 920 paired tasks (1,840 runs). The current zero-config
path is a trace-evidence reviewer, not the executable acceptance/resampling
mechanism evaluated as CONFORM in the paper. A concrete measurement bug is also
present: the C5 native agent runs `sh run_tests.sh`, but the current
`RUNNERS` pattern does not classify that direct wrapper as a test runner.
Consequently, the stop hook repeatedly tells the agent that no test/build ran
even when the recorded runner output contains named passing checks and a zero
failure summary.

This review branch is separate from the requested working branch. Changes here
are review candidates until package tests and a native-agent smoke test pass.
Model-quality improvement requires a new controlled experiment; local regression
tests cannot establish it.
