from __future__ import annotations

import json
import statistics
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Optional

try:
    import psutil
except ImportError:  # optional dependency
    psutil = None


def _percentile(values: list[float], q: float) -> float:
    if not values:
        return float("nan")
    if len(values) == 1:
        return values[0]
    x = sorted(values)
    pos = (len(x) - 1) * q
    lo = int(pos)
    hi = min(lo + 1, len(x) - 1)
    frac = pos - lo
    return x[lo] * (1.0 - frac) + x[hi] * frac


def _rss_mb() -> Optional[float]:
    if psutil is None:
        return None
    return psutil.Process().memory_info().rss / (1024.0 * 1024.0)


@dataclass
class PerfFrame:
    frame_id: int
    stages_ms: Dict[str, float] = field(default_factory=dict)
    total_ms: Optional[float] = None
    rss_mb: Optional[float] = None

    def to_dict(self) -> dict:
        result = {"frame_id": self.frame_id, **self.stages_ms}
        result["total_ms"] = self.total_ms
        result["fps"] = None if not self.total_ms or self.total_ms <= 0 else 1000.0 / self.total_ms
        result["rss_mb"] = self.rss_mb
        return result


class StageTimer:
    def __init__(self, recorder: "PerfRecorder", stage: str):
        self.recorder = recorder
        self.stage = stage
        self._t0_ns: Optional[int] = None

    def __enter__(self) -> "StageTimer":
        self._t0_ns = time.perf_counter_ns()
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        if self._t0_ns is None:
            return
        self.recorder.add_stage(self.stage, (time.perf_counter_ns() - self._t0_ns) / 1e6)


class PerfRecorder:
    """Backend-agnostic per-frame profiler and NADIR real-time gate."""

    def __init__(self) -> None:
        self.frames: list[PerfFrame] = []
        self._active: Optional[PerfFrame] = None
        self._frame_t0_ns: Optional[int] = None

    def begin_frame(self, frame_id: int) -> None:
        if self._active is not None:
            raise RuntimeError("A frame is already active")
        self._active = PerfFrame(frame_id=frame_id)
        self._frame_t0_ns = time.perf_counter_ns()

    def stage(self, name: str) -> StageTimer:
        if self._active is None:
            raise RuntimeError("begin_frame() must be called before stage()")
        return StageTimer(self, name)

    def add_stage(self, name: str, elapsed_ms: float) -> None:
        if self._active is None:
            raise RuntimeError("No active frame")
        self._active.stages_ms[f"{name}_ms"] = float(elapsed_ms)

    def end_frame(self) -> PerfFrame:
        if self._active is None or self._frame_t0_ns is None:
            raise RuntimeError("No active frame")
        self._active.total_ms = (time.perf_counter_ns() - self._frame_t0_ns) / 1e6
        self._active.rss_mb = _rss_mb()
        frame = self._active
        self.frames.append(frame)
        self._active = None
        self._frame_t0_ns = None
        return frame

    def summary(self, warmup: int = 0) -> dict:
        frames = self.frames[warmup:]
        totals = [f.total_ms for f in frames if f.total_ms is not None]
        if not totals:
            return {"frames": 0}
        mean_ms = statistics.fmean(totals)
        rss = [f.rss_mb for f in frames if f.rss_mb is not None]
        return {
            "frames": len(totals),
            "latency_mean_ms": mean_ms,
            "latency_p50_ms": _percentile(totals, 0.50),
            "latency_p95_ms": _percentile(totals, 0.95),
            "fps_from_mean_latency": 1000.0 / mean_ms,
            "peak_rss_mb": max(rss) if rss else None,
        }

    def realtime_gate(self, *, min_fps: float = 15.0, max_p95_ms: float = 80.0, warmup: int = 0) -> dict:
        s = self.summary(warmup=warmup)
        if s.get("frames", 0) == 0:
            return {"pass": False, "reason": "no measured frames", **s}
        fps_ok = s["fps_from_mean_latency"] >= min_fps
        p95_ok = s["latency_p95_ms"] <= max_p95_ms
        return {
            "pass": bool(fps_ok and p95_ok),
            "fps_ok": bool(fps_ok),
            "p95_ok": bool(p95_ok),
            "min_fps": min_fps,
            "max_p95_ms": max_p95_ms,
            **s,
        }

    def write_jsonl(self, path: str | Path) -> None:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8") as f:
            for frame in self.frames:
                f.write(json.dumps(frame.to_dict(), sort_keys=True) + "\n")
