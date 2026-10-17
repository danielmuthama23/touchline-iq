"""Optional video layer. Join logic is pure Python and tested; detect_video needs opencv+ultralytics
and has NOT been run in this repo's CI."""
from dataclasses import dataclass, field


@dataclass
class Observation:
    video_t: float
    boxes: list = field(default_factory=list)  # {"cls": str, "conf": float, "xyxy": [..]}
    frame_w: int = 0
    frame_h: int = 0
    model: str = ""


def video_to_match_time(video_t, offset):
    return video_t + offset  # offset = match seconds at video second 0 (set explicitly per clip)


def join_observations(obs, events, offset, window=2.0):
    """Temporal co-occurrence only. A link is NOT proof that a detected person made the event."""
    out = []
    for o in obs:
        mt = video_to_match_time(o.video_t, offset)
        near = [(abs(e.t - mt), e) for e in events if abs(e.t - mt) <= window]
        near.sort(key=lambda p: p[0])
        out.append({"video_t": o.video_t, "match_t": mt, "people": sum(b["cls"] == "person" for b in o.boxes),
                    "ball_seen": any(b["cls"] == "sports ball" for b in o.boxes),
                    "event_ids": [e.id for _, e in near],
                    "link_confidence": round(1 - near[0][0] / window, 2) if near else 0.0})
    return out


def detect_video(path, every_s=1.0, max_s=120, model_name="yolov8n.pt"):
    try:
        import cv2
        from ultralytics import YOLO
    except ImportError as e:
        raise RuntimeError("Vision extras not installed: pip install opencv-python-headless ultralytics") from e
    model, cap, res, i = YOLO(model_name), cv2.VideoCapture(path), [], 0
    fps = cap.get(cv2.CAP_PROP_FPS) or 25
    step = max(1, int(fps * every_s))
    while cap.isOpened():
        ok, frame = cap.read()
        if not ok or i / fps > max_s:
            break
        if i % step == 0:
            r = model(frame, verbose=False)[0]
            boxes = [{"cls": r.names[int(c)], "conf": round(float(p), 2), "xyxy": [round(float(v)) for v in b]}
                     for b, c, p in zip(r.boxes.xyxy, r.boxes.cls, r.boxes.conf)
                     if r.names[int(c)] in ("person", "sports ball")]
            res.append(Observation(i / fps, boxes, frame.shape[1], frame.shape[0], model_name))
        i += 1
    cap.release()
    return res
