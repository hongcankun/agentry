# Trae CLI Sandbox

Set up an isolated Trae CLI run that loads the artifact under test and produces output for the evaluation, with no live external side effects.

Each case runs its repetitions independently, so every repetition gets its own sandbox. `mode: "sandbox"` in the case is the signal; prepare pre-creates an empty `sandbox/` anchor under the case directory, and the executor creates `<case-dir>/sandbox/<repetition>/bin` and `<case-dir>/sandbox/<repetition>/sinks` for each repetition. Below, `$CASE` is the case directory, `$REP` the repetition, `$SBX="$CASE/sandbox/$REP"`, and `$TARGET_MODEL` the case `target`'s model.

## Isolate config and home

Run `traecli` with a per-repetition home so it never reads the maintainer's real config, skills, agents, commands, or rules:

```bash
export SBX="$CASE/sandbox/$REP"
export SANDBOX_HOME="$SBX/home"
mkdir -p "$SANDBOX_HOME/.trae" "$SBX/bin" "$SBX/sinks"
HOME="$SANDBOX_HOME" traecli ...
```

Install or expose only this case's artifact version, copied from the case's `artifact/` bundle, under `$SANDBOX_HOME/.trae`:

- skill → `$SANDBOX_HOME/.trae/skills/<skill>/`
- subagent → `$SANDBOX_HOME/.trae/agents/<agent>.md`
- command → `$SANDBOX_HOME/.trae/commands/<command>.md`
- rule → `$SANDBOX_HOME/.trae/rules/<category>/<rule>.md`

Copy from the case bundle, do not symlink back to the working tree, so the sandbox reflects exactly the side under test.

## Route external commands to run-local mocks

Prepend this repetition's sandbox bin to `PATH` so fake executables shadow real ones, and pin the target model so this side runs as the case's target rather than the tool default:

```bash
PATH="$SBX/bin:$PATH" HOME="$SANDBOX_HOME" traecli exec -m "$TARGET_MODEL" "/<command> ..."
```

Stage the case's `tool-mocks/` into `$SBX/bin/` and make them executable. Bake the sink path in as you copy each mock — substitute `$SBX/sinks` for the mock's `__SINK__` placeholder (the shared convention) — so the producer's environment carries no evaluation-revealing variable; mocks must write only under `$SBX/sinks/` and return fixture-backed responses. Provide mocks for any network- or tracker-facing binary a scenario could invoke (for example the platform CLI it would call to post comments).

The substitution itself is whatever reliably replaces the token for your mock files; the `sed` loop below is illustrative (it assumes text mocks and a sink path free of its `#` delimiter — choose a delimiter or method that suits the actual path):

```bash
for src in "$CASE"/tool-mocks/*; do
  dest="$SBX/bin/$(basename "$src")"
  sed "s#__SINK__#$SBX/sinks#g" "$src" >"$dest"
  chmod +x "$dest"
done
```

Then stage a **catch-all capture shim** for any network- or tracker-facing command the producer might invoke that the scenario did not pre-mock, so an un-anticipated call is captured inertly instead of reaching a real remote — no fabricated success. Install one shim and symlink the binary names a scenario could plausibly reach (the platform CLIs, `curl`, `git`, and so on), skipping names an author mock already staged:

```bash
cat >"$SBX/bin/_capture" <<EOF
#!/bin/sh
printf '%s\n' "\$(basename "\$0") \$*" >>"$SBX/sinks/uncaptured.log"
echo "sandbox: '\$(basename "\$0")' is not available in this environment" >&2
exit 1
EOF
chmod +x "$SBX/bin/_capture"
for name in curl wget git gh glab codebase; do
  [ -e "$SBX/bin/$name" ] || ln -s _capture "$SBX/bin/$name"
done
```

The shim exits non-zero with an inert message: a command whose specific response the behavior depends on must have a real `tool-mocks/` entry, and its absence should surface as an under-specified (`needs-review`) result, not a fake pass.

## Deny real side effects

Run with no production credentials in the sandbox environment and no configured real remote. A confirmation turn authorizes only the sandboxed action. Treat any real remote call, credential use, or write outside `$SBX` as a failed or `needs-review` run.

## Produce and capture

Drive the producer's composed task — the blinded prompt built from the case, which activates the installed artifact — non-interactively, pinning the target model, and capture stdout/stderr as the transcript. Run the producer's task here, not `/evaluate-authoring` (that is the orchestrator command that launched this run; re-invoking it inside the sandbox would recurse):

```bash
PATH="$SBX/bin:$PATH" HOME="$SANDBOX_HOME" \
  traecli exec -m "$TARGET_MODEL" "<composed producer task>" \
  >"$SBX/transcript.txt" 2>&1
```

Collect the transcript, final output, per-turn output for multi-turn scenarios, and every write under `$SBX/sinks/`. Write result records in the shared result schema so the project runner collects them identically to rendered simulation.

Judging happens **after and outside** the sandbox: the rubric evaluator reads the captured output plus the checks and returns a verdict, so it needs no sandbox home, no artifact install, and no mocks. Do not re-activate the artifact to judge.

## Clean up

Remove `$SBX` after capture. Because each repetition has its own sandbox, no state carries over between repetitions, sides, or targets, and independent cases can run in parallel.
