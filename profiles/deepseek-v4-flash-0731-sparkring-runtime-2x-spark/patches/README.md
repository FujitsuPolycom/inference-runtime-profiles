# Patches applied over the runtime image

Three files in the runtime image need changes before this profile serves
correctly. Each patch below is small and targets one defect. Apply them to
copies on the host, then bind-mount the copies over the image's originals —
the image itself is never modified.

Paths in the patch headers are relative to the package root, so apply with
`patch -p1` from the directory holding the `quack/` package, or with `-p0`
against a single copied file.

## `quack-copy_utils-thrcopy-annotation.patch`, `quack-layout_utils-thrmma-annotation.patch`

**Defect.** The image pairs `quack_kernels` 0.5.0 with a `cutlass` build that
exports `ThrCopy` and `ThrMma` from `cutlass.cute`, while six type annotations
in `quack` resolve them through `cutlass.cute.core`. Evaluating those
annotations raises `module cutlass.cute.core has no attribute ThrMma` during
model execution.

**Change.** `cute.core.ThrCopy` becomes `cute.ThrCopy` and `cute.core.ThrMma`
becomes `cute.ThrMma`, in four annotations in `copy_utils.py` and two in
`layout_utils.py`. Annotations only; no behavior changes.

**Applies to** `quack_kernels` 0.5.0, pinned in
`runtime/exl3-r7/requirements-quack.txt` in `FujitsuPolycom/sparkring` and
installed at `/opt/venv/lib/python3.12/site-packages/quack/` in the image.

Upstream copyright is retained in both files: `copy_utils.py` is
QuACK team, `layout_utils.py` is Wentao Guo, Ted Zadouri and Tri Dao.

## `lmcache-mp-heartbeat-guard.patch`

**Defect.** `LMCacheMPSchedulerAdapter._ensure_heartbeat_started` guards on
`self._heartbeats is not None`, but `self._heartbeats` is a dict initialised to
`{}`. An empty dict is not `None`, so the guard returns on the first call and
the thread-creation loop below it is unreachable. The scheduler-side heartbeat
thread never starts, `is_healthy` stays `True` for every server, and the
scheduler never enters degraded mode when a cache server goes away.

**Observed consequence** on the reference deployment: cache servers reap a
healthy engine after roughly 150 seconds of idle time, because the engine never
answers the heartbeat that would keep it registered.

**Change.** Both guards test the dict's truth value instead of its identity, so
an empty dict starts the threads and a populated one skips them.

**Applies to** LMCache 0.5.2 and to the `release/v0.5.2-glm52-dcp-base` branch
of `local-inference-lab/LMCache`, at
`lmcache/integration/vllm/vllm_multi_process_adapter.py`. Apply it before
building the wheel that `leg3pair-inner.sh` installs at container start.

**Verification.** With the patch, the scheduler process logs
`Started PeriodicThread: lmcache-heartbeat` at startup, and a store followed by
more than ten minutes of idle time produces no reap lines in either cache
server's log.
