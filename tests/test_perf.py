import time

from nadir.perf import PerfRecorder


def test_perf_recorder_contract():
    p = PerfRecorder()
    p.begin_frame(0)
    with p.stage("geometry"):
        time.sleep(0.001)
    frame = p.end_frame()
    d = frame.to_dict()
    assert d["frame_id"] == 0
    assert d["geometry_ms"] > 0.0
    assert d["total_ms"] >= d["geometry_ms"]
    s = p.summary()
    assert s["frames"] == 1
    assert s["latency_p95_ms"] > 0.0
