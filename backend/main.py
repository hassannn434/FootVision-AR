
from fastapi import FastAPI, HTTPException, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from ultralytics import YOLO
from collections import defaultdict, Counter
from typing import Optional
import cv2
import numpy as np
import csv
import io
import os
import tempfile
import threading
import time

# ============================================================
# FOOTVISION AR - MATCH INTELLIGENCE BACKEND
# ============================================================

app = FastAPI(
    title="FootVision AR API",
    description="Football detection, tracking, team classification, player profiles and match analytics",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://reliable-phoenix-72cd39.netlify.app",
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:8501",
        "http://127.0.0.1:8501"
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ============================================================
# PLAYER PROFILES
# ============================================================

players = [
    {
        "id": 1,
        "name": "Alex Morgan",
        "team": "Blue FC",
        "jersey_number": 10,
        "position": "Forward",
        "goals": 2,
        "assists": 1,
        "passes": 38,
        "shots": 5,
        "speed_kmh": 29.4
    },
    {
        "id": 2,
        "name": "James Wilson",
        "team": "Blue FC",
        "jersey_number": 7,
        "position": "Midfielder",
        "goals": 1,
        "assists": 2,
        "passes": 52,
        "shots": 3,
        "speed_kmh": 27.8
    },
    {
        "id": 3,
        "name": "Daniel Smith",
        "team": "White FC",
        "jersey_number": 9,
        "position": "Forward",
        "goals": 1,
        "assists": 0,
        "passes": 25,
        "shots": 4,
        "speed_kmh": 31.2
    }
]

# ============================================================
# GLOBAL STATE
# ============================================================

model = None

model_lock = threading.Lock()
video_lock = threading.Lock()
analytics_lock = threading.Lock()

manual_team_overrides = {}
track_player_assignments = {}

previous_centroids = None


def new_analytics():
    return {
        "frames_processed": 0,
        "total_detections": 0,
        "detections_by_track": defaultdict(int),
        "team_counts": defaultdict(int),
        "confidence_sum": 0.0,
        "confidence_count": 0,
        "positions": defaultdict(list),
        "events": [],
        "video_info": {},
        "last_updated": None
    }


analytics = new_analytics()


def reset_analytics_data():
    global analytics
    with analytics_lock:
        analytics = new_analytics()


# ============================================================
# REQUEST MODELS
# ============================================================

class TeamOverrideRequest(BaseModel):
    track_id: int
    team: str


class PlayerAssignmentRequest(BaseModel):
    track_id: int
    player_id: Optional[int] = None


class PlayerUpdateRequest(BaseModel):
    name: str
    team: str
    jersey_number: int
    position: str
    goals: int = 0
    assists: int = 0
    passes: int = 0
    shots: int = 0
    speed_kmh: float = 0.0


# ============================================================
# YOLO MODEL
# ============================================================

def get_model():
    global model

    with model_lock:
        if model is None:
            print("Loading YOLOv8 model...")

            model_path = os.path.join(
                os.path.dirname(os.path.abspath(__file__)),
                "yolov8n.pt"
            )

            model = YOLO(model_path)

            print("YOLOv8 loaded successfully.")

    return model


# ============================================================
# JERSEY COLOUR EXTRACTION
# ============================================================

def extract_jersey_features(frame, x1, y1, x2, y2):

    height, width = frame.shape[:2]

    x1 = max(0, int(x1))
    y1 = max(0, int(y1))
    x2 = min(width, int(x2))
    y2 = min(height, int(y2))

    if x2 <= x1 or y2 <= y1:
        return None, "#808080"

    person = frame[y1:y2, x1:x2]

    if person.size == 0:
        return None, "#808080"

    h, w = person.shape[:2]

    upper_body = person[
        int(h * 0.15):int(h * 0.60),
        int(w * 0.20):int(w * 0.80)
    ]

    if upper_body.size == 0:
        return None, "#808080"

    hsv = cv2.cvtColor(
        upper_body,
        cv2.COLOR_BGR2HSV
    )

    valid_mask = (
        (hsv[:, :, 2] > 35) &
        (hsv[:, :, 2] < 250)
    )

    valid_pixels = hsv[valid_mask]

    if len(valid_pixels) < 10:
        return None, "#808080"

    median_hsv = np.median(
        valid_pixels,
        axis=0
    )

    feature = np.array([
        float(median_hsv[0]) * 2,
        float(median_hsv[1]),
        float(median_hsv[2])
    ], dtype=np.float32)

    representative_hsv = np.uint8([[median_hsv]])

    representative_bgr = cv2.cvtColor(
        representative_hsv,
        cv2.COLOR_HSV2BGR
    )[0][0]

    rgb = representative_bgr[::-1]

    jersey_color = "#{:02X}{:02X}{:02X}".format(
        int(rgb[0]),
        int(rgb[1]),
        int(rgb[2])
    )

    return feature, jersey_color


# ============================================================
# AUTOMATIC TEAM CLASSIFICATION
# ============================================================

def classify_teams(detections):

    global previous_centroids

    usable = [
        item for item in detections
        if item["feature"] is not None
    ]

    if len(usable) < 2:
        for item in detections:
            item["auto_team"] = "Unclassified"
        return

    features = np.array(
        [item["feature"] for item in usable],
        dtype=np.float32
    )

    criteria = (
        cv2.TERM_CRITERIA_EPS +
        cv2.TERM_CRITERIA_MAX_ITER,
        30,
        0.5
    )

    try:
        _, labels, centers = cv2.kmeans(
            features,
            2,
            None,
            criteria,
            5,
            cv2.KMEANS_PP_CENTERS
        )

    except cv2.error:
        for item in detections:
            item["auto_team"] = "Unclassified"
        return

    if previous_centroids is not None:

        direct = (
            np.linalg.norm(
                centers[0] - previous_centroids[0]
            ) +
            np.linalg.norm(
                centers[1] - previous_centroids[1]
            )
        )

        swapped = (
            np.linalg.norm(
                centers[0] - previous_centroids[1]
            ) +
            np.linalg.norm(
                centers[1] - previous_centroids[0]
            )
        )

        if swapped < direct:
            centers = centers[[1, 0]]
            labels = 1 - labels

    previous_centroids = centers.copy()

    if np.linalg.norm(
        centers[0] - centers[1]
    ) < 20:

        for item in detections:
            item["auto_team"] = "Unclassified"

        return

    for index, item in enumerate(usable):

        item["auto_team"] = (
            "Team A"
            if int(labels[index][0]) == 0
            else "Team B"
        )

    for item in detections:
        if item["feature"] is None:
            item["auto_team"] = "Unclassified"


# ============================================================
# DETECTION AND TRACKING PIPELINE
# ============================================================

def detect_frame_internal(frame, persist=True):

    detector = get_model()

    results = detector.track(
        source=frame,
        persist=persist,
        tracker="bytetrack.yaml",
        classes=[0],
        conf=0.35,
        verbose=False
    )

    result = results[0]

    detections = []

    if result.boxes is not None:

        boxes = result.boxes

        coordinates = boxes.xyxy.cpu().numpy()
        confidences = boxes.conf.cpu().numpy()

        track_ids = (
            boxes.id.int().cpu().tolist()
            if boxes.id is not None
            else None
        )

        for index, (box, confidence) in enumerate(
            zip(coordinates, confidences)
        ):

            x1, y1, x2, y2 = box.tolist()

            feature, jersey_color = extract_jersey_features(
                frame,
                x1,
                y1,
                x2,
                y2
            )

            track_id = (
                int(track_ids[index])
                if track_ids is not None
                else None
            )

            detections.append({

                "x1": round(float(x1), 2),
                "y1": round(float(y1), 2),
                "x2": round(float(x2), 2),
                "y2": round(float(y2), 2),

                "confidence": round(float(confidence), 3),

                "track_id": track_id,

                "class_name": "Person",

                "jersey_color": jersey_color,

                "feature": feature,

                "auto_team": "Unclassified"
            })

    classify_teams(detections)

    response_detections = []

    team_counts = {
        "Team A": 0,
        "Team B": 0,
        "Unclassified": 0
    }

    for item in detections:

        track_id = item["track_id"]

        manual_team = (
            manual_team_overrides.get(track_id)
            if track_id is not None
            else None
        )

        final_team = manual_team or item["auto_team"]

        if final_team not in team_counts:
            final_team = "Unclassified"

        team_counts[final_team] += 1

        player_id = (
            track_player_assignments.get(track_id)
            if track_id is not None
            else None
        )

        assigned_player = next(
            (
                p for p in players
                if p["id"] == player_id
            ),
            None
        )

        response_detections.append({

            "x1": item["x1"],
            "y1": item["y1"],
            "x2": item["x2"],
            "y2": item["y2"],

            "confidence": item["confidence"],

            "track_id": track_id,

            "class_name": item["class_name"],

            "jersey_color": item["jersey_color"],

            "auto_team": item["auto_team"],

            "team": final_team,

            "manual_override": manual_team is not None,

            "player_id": player_id,

            "player": assigned_player
        })

    return {

        "success": True,

        "count": len(response_detections),

        "team_a_count": team_counts["Team A"],

        "team_b_count": team_counts["Team B"],

        "unclassified_count": team_counts["Unclassified"],

        "width": int(frame.shape[1]),

        "height": int(frame.shape[0]),

        "detections": response_detections

    }


# ============================================================
# ANALYTICS RECORDING
# ============================================================

def record_frame_analytics(
    result,
    frame_number=None,
    timestamp_sec=None
):

    with analytics_lock:

        analytics["frames_processed"] += 1

        analytics["total_detections"] += result["count"]

        analytics["last_updated"] = time.time()

        for detection in result["detections"]:

            track_id = detection.get("track_id")

            team = detection.get(
                "team",
                "Unclassified"
            )

            confidence = float(
                detection.get("confidence", 0)
            )

            analytics["team_counts"][team] += 1

            analytics["confidence_sum"] += confidence

            analytics["confidence_count"] += 1

            if track_id is not None:

                key = str(track_id)

                analytics["detections_by_track"][key] += 1

                center_x = (
                    detection["x1"] +
                    detection["x2"]
                ) / 2

                center_y = (
                    detection["y1"] +
                    detection["y2"]
                ) / 2

                analytics["positions"][key].append({

                    "x": round(center_x, 2),

                    "y": round(center_y, 2),

                    "frame": frame_number,

                    "timestamp": timestamp_sec,

                    "team": team

                })

        analytics["events"].append({

            "frame": frame_number,

            "timestamp": timestamp_sec,

            "count": result["count"],

            "team_a": result["team_a_count"],

            "team_b": result["team_b_count"],

            "unclassified": result["unclassified_count"]

        })


# ============================================================
# ROOT AND HEALTH
# ============================================================

@app.get("/")
def home():

    return {
        "message": "Welcome to FootVision AR",
        "status": "running",
        "version": app.version
    }


@app.get("/api/health")
def health():

    return {

        "status": "healthy",

        "application": "FootVision AR",

        "ai_model": "YOLOv8",

        "tracking": "ByteTrack",

        "classification": "Jersey colour clustering",

        "player_profiles": "Manual profile assignment",

        "analytics": "Enabled",

        "video_processing": "Enabled",

        "heatmap": "Enabled",

        "reports": "Enabled"

    }


# ============================================================
# PLAYER PROFILE APIs
# ============================================================

@app.get("/api/players")
def get_players():

    return players


@app.get("/api/players/{player_id}")
def get_player(player_id: int):

    player = next(
        (p for p in players if p["id"] == player_id),
        None
    )

    if player is None:
        raise HTTPException(404, "Player not found.")

    return player


@app.put("/api/players/{player_id}")
def update_player(
    player_id: int,
    request: PlayerUpdateRequest
):

    player = next(
        (p for p in players if p["id"] == player_id),
        None
    )

    if player is None:
        raise HTTPException(404, "Player not found.")

    player.update(request.model_dump())

    return {
        "success": True,
        "player": player,
        "message": "Player information updated."
    }


# ============================================================
# PLAYER ASSIGNMENT
# ============================================================

@app.post("/api/player-assign")
def assign_player(request: PlayerAssignmentRequest):

    if request.player_id is None:

        track_player_assignments.pop(
            request.track_id,
            None
        )

        return {
            "success": True,
            "track_id": request.track_id,
            "player": None,
            "message": "Player profile unassigned."
        }

    player = next(
        (
            p for p in players
            if p["id"] == request.player_id
        ),
        None
    )

    if player is None:
        raise HTTPException(404, "Player profile not found.")

    for old_track_id, old_player_id in list(
        track_player_assignments.items()
    ):

        if old_player_id == request.player_id:

            del track_player_assignments[old_track_id]

    track_player_assignments[
        request.track_id
    ] = request.player_id

    return {

        "success": True,

        "track_id": request.track_id,

        "player_id": player["id"],

        "player": player,

        "message": "Player profile assigned successfully."

    }


@app.get("/api/track-assignments")
def get_track_assignments():

    return {
        str(track_id): player_id
        for track_id, player_id
        in track_player_assignments.items()
    }


# ============================================================
# TEAM OVERRIDE
# ============================================================

@app.post("/api/team-override")
def update_team_override(request: TeamOverrideRequest):

    if request.team not in [
        "Team A",
        "Team B",
        "Auto"
    ]:

        raise HTTPException(
            400,
            "Invalid team selection."
        )

    if request.team == "Auto":

        manual_team_overrides.pop(
            request.track_id,
            None
        )

    else:

        manual_team_overrides[
            request.track_id
        ] = request.team

    return {

        "success": True,

        "track_id": request.track_id,

        "team": request.team

    }


# ============================================================
# IMAGE FRAME DETECTION
# ============================================================

@app.post("/api/detect-frame")
async def detect_frame(file: UploadFile = File(...)):

    if (
        not file.content_type
        or not file.content_type.startswith("image/")
    ):

        raise HTTPException(
            400,
            "Please upload a valid image frame."
        )

    image_bytes = await file.read()

    if not image_bytes:

        raise HTTPException(
            400,
            "Uploaded image is empty."
        )

    image_array = np.frombuffer(
        image_bytes,
        np.uint8
    )

    frame = cv2.imdecode(
        image_array,
        cv2.IMREAD_COLOR
    )

    if frame is None:

        raise HTTPException(
            400,
            "Could not decode image."
        )

    try:

        result = detect_frame_internal(
            frame,
            persist=True
        )

        record_frame_analytics(result)

        return result

    except Exception as error:

        raise HTTPException(
            500,
            detail=f"Detection failed: {str(error)}"
        )


# ============================================================
# VIDEO UPLOAD AND PROCESSING
# ============================================================

@app.post("/api/detect-video")
async def detect_video(
    file: UploadFile = File(...),
    frame_interval: int = 5,
    max_frames: int = 600
):

    global previous_centroids

    if not file.filename:
        raise HTTPException(400, "Video filename is missing.")

    allowed_extensions = (
        ".mp4",
        ".avi",
        ".mov",
        ".mkv",
        ".mpeg",
        ".mpg"
    )

    if not file.filename.lower().endswith(
        allowed_extensions
    ):

        raise HTTPException(
            400,
            "Upload MP4, AVI, MOV, MKV or MPEG video."
        )

    if not 1 <= frame_interval <= 60:
        raise HTTPException(
            400,
            "frame_interval must be between 1 and 60."
        )

    if not 1 <= max_frames <= 5000:
        raise HTTPException(
            400,
            "max_frames must be between 1 and 5000."
        )

    video_bytes = await file.read()

    if not video_bytes:
        raise HTTPException(400, "Uploaded video is empty.")

    suffix = os.path.splitext(
        file.filename
    )[1] or ".mp4"

    temp_path = None
    cap = None

    try:

        with tempfile.NamedTemporaryFile(
            delete=False,
            suffix=suffix
        ) as temp:

            temp.write(video_bytes)
            temp_path = temp.name

        cap = cv2.VideoCapture(temp_path)

        if not cap.isOpened():

            raise HTTPException(
                400,
                "Could not open uploaded video."
            )

        fps = cap.get(cv2.CAP_PROP_FPS) or 25.0

        total_frames = int(
            cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0
        )

        width = int(
            cap.get(cv2.CAP_PROP_FRAME_WIDTH) or 0
        )

        height = int(
            cap.get(cv2.CAP_PROP_FRAME_HEIGHT) or 0
        )

        with video_lock:

            previous_centroids = None

            reset_analytics_data()

            get_model().predictor = None

            processed = 0

            frame_number = 0

            track_summary = {}

            team_totals = defaultdict(int)

            while processed < max_frames:

                ok, frame = cap.read()

                if not ok:
                    break

                current_frame = frame_number

                frame_number += 1

                if current_frame % frame_interval != 0:
                    continue

                timestamp_sec = (
                    current_frame / fps
                    if fps > 0
                    else None
                )

                result = detect_frame_internal(
                    frame,
                    persist=True
                )

                record_frame_analytics(
                    result,
                    current_frame,
                    timestamp_sec
                )

                processed += 1

                for detection in result["detections"]:

                    team_totals[
                        detection["team"]
                    ] += 1

                    track_id = detection.get("track_id")

                    if track_id is not None:

                        track_summary[str(track_id)] = {

                            "track_id": track_id,

                            "team": detection["team"],

                            "jersey_color": detection["jersey_color"],

                            "last_confidence": detection["confidence"],

                            "player": detection.get("player")

                        }

            cap.release()
            cap = None

            if processed == 0:

                raise HTTPException(
                    400,
                    "No video frames could be processed."
                )

            video_info = {

                "filename": file.filename,

                "fps": round(float(fps), 2),

                "total_frames": total_frames,

                "processed_frames": processed,

                "width": width,

                "height": height,

                "duration_seconds": (
                    round(total_frames / fps, 2)
                    if fps > 0
                    else None
                ),

                "frame_interval": frame_interval

            }

            with analytics_lock:
                analytics["video_info"] = video_info

            return {

                "success": True,

                "message": "Video processing completed.",

                "video": video_info,

                "frames_processed": processed,

                "total_detections": analytics["total_detections"],

                "unique_tracks": len(track_summary),

                "team_counts": dict(team_totals),

                "players_tracked": list(
                    track_summary.values()
                ),

                "analytics": build_analytics_summary()

            }

    except HTTPException:
        raise

    except Exception as error:

        raise HTTPException(
            500,
            detail=f"Video processing failed: {str(error)}"
        )

    finally:

        if cap is not None:
            cap.release()

        if temp_path and os.path.exists(temp_path):
            os.remove(temp_path)


# ============================================================
# ANALYTICS SUMMARY
# ============================================================

def build_analytics_summary():

    with analytics_lock:

        frames = analytics["frames_processed"]

        total = analytics["total_detections"]

        confidence_count = analytics["confidence_count"]

        avg_conf = (
            analytics["confidence_sum"] / confidence_count
            if confidence_count
            else 0
        )

        most_seen = sorted(
            analytics["detections_by_track"].items(),
            key=lambda item: item[1],
            reverse=True
        )

        return {

            "frames_processed": frames,

            "total_detections": total,

            "unique_players": len(
                analytics["detections_by_track"]
            ),

            "average_detections_per_frame": (
                round(total / frames, 2)
                if frames
                else 0
            ),

            "average_confidence": round(
                avg_conf,
                3
            ),

            "team_counts": dict(
                analytics["team_counts"]
            ),

            "video_info": dict(
                analytics["video_info"]
            ),

            "most_detected_tracks": [

                {
                    "track_id": int(track_id),
                    "detections": count
                }

                for track_id, count in most_seen[:20]

            ],

            "last_updated": analytics["last_updated"]

        }


@app.get("/api/analytics/summary")
def analytics_summary():

    return build_analytics_summary()


# ============================================================
# PLAYER ANALYTICS
# ============================================================

@app.get("/api/analytics/players")
def analytics_players():

    with analytics_lock:

        output = []

        for track_id, count in analytics[
            "detections_by_track"
        ].items():

            positions = analytics[
                "positions"
            ].get(track_id, [])

            teams = [
                p["team"]
                for p in positions
                if p.get("team")
            ]

            team = (
                Counter(teams).most_common(1)[0][0]
                if teams
                else "Unclassified"
            )

            assigned_id = track_player_assignments.get(
                int(track_id)
            )

            assigned_player = next(
                (
                    p for p in players
                    if p["id"] == assigned_id
                ),
                None
            )

            output.append({

                "track_id": int(track_id),

                "detections": count,

                "team": team,

                "player_id": assigned_id,

                "player": assigned_player,

                "positions_recorded": len(positions)

            })

    return sorted(
        output,
        key=lambda item: item["detections"],
        reverse=True
    )


# ============================================================
# TEAM COMPARISON ANALYTICS
# ============================================================

@app.get("/api/analytics/teams")
def analytics_teams():

    with analytics_lock:

        counts = dict(
            analytics["team_counts"]
        )

    return {

        "teams": [

            {
                "team": team,
                "detections": counts.get(team, 0)
            }

            for team in [
                "Team A",
                "Team B",
                "Unclassified"
            ]

        ],

        "team_a_count": counts.get("Team A", 0),

        "team_b_count": counts.get("Team B", 0),

        "unclassified_count": counts.get(
            "Unclassified",
            0
        )

    }


# ============================================================
# MOVEMENT HEATMAP DATA
# ============================================================

@app.get("/api/analytics/heatmap")
def analytics_heatmap():

    with analytics_lock:

        positions = {
            track_id: list(points)
            for track_id, points
            in analytics["positions"].items()
        }

    all_points = []

    tracks = []

    for track_id, points in positions.items():

        for point in points:

            all_points.append({

                "track_id": int(track_id),

                **point

            })

        tracks.append({

            "track_id": int(track_id),

            "points": points

        })

    return {

        "success": True,

        "point_count": len(all_points),

        "tracks": tracks,

        "points": all_points

    }


# ============================================================
# HEATMAP IMAGE
# ============================================================

@app.get("/api/analytics/heatmap/image")
def analytics_heatmap_image():

    with analytics_lock:

        positions = [

            point

            for points in analytics["positions"].values()

            for point in points

        ]

        video_info = dict(
            analytics["video_info"]
        )

    width = video_info.get("width") or 1920
    height = video_info.get("height") or 1080

    canvas_width = 1000
    canvas_height = 600

    heat = np.zeros(
        (canvas_height, canvas_width),
        dtype=np.float32
    )

    for point in positions:

        x = int(
            point["x"] * canvas_width / max(1, width)
        )

        y = int(
            point["y"] * canvas_height / max(1, height)
        )

        x = max(0, min(canvas_width - 1, x))
        y = max(0, min(canvas_height - 1, y))

        cv2.circle(
            heat,
            (x, y),
            24,
            1.0,
            -1
        )

    if heat.max() > 0:
        heat = heat / heat.max()

    heat_uint8 = np.uint8(
        heat * 255
    )

    colored = cv2.applyColorMap(
        heat_uint8,
        cv2.COLORMAP_JET
    )

    success, encoded = cv2.imencode(
        ".png",
        colored
    )

    if not success:
        raise HTTPException(
            500,
            "Could not generate heatmap image."
        )

    return StreamingResponse(
        io.BytesIO(encoded.tobytes()),
        media_type="image/png",
        headers={
            "Content-Disposition":
            'inline; filename="footvision_heatmap.png"'
        }
    )


# ============================================================
# MOVEMENT DETAILS
# ============================================================

@app.get("/api/analytics/movement")
def analytics_movement():

    with analytics_lock:

        output = []

        for track_id, points in analytics[
            "positions"
        ].items():

            total_distance = 0.0

            for index in range(1, len(points)):

                previous = points[index - 1]
                current = points[index]

                dx = current["x"] - previous["x"]
                dy = current["y"] - previous["y"]

                total_distance += float(
                    np.sqrt(dx * dx + dy * dy)
                )

            output.append({

                "track_id": int(track_id),

                "team": (
                    points[-1]["team"]
                    if points
                    else "Unclassified"
                ),

                "positions_recorded": len(points),

                "movement_distance_pixels": round(
                    total_distance,
                    2
                ),

                "first_position": (
                    points[0]
                    if points
                    else None
                ),

                "last_position": (
                    points[-1]
                    if points
                    else None
                )

            })

    return sorted(
        output,
        key=lambda item: item[
            "movement_distance_pixels"
        ],
        reverse=True
    )


# ============================================================
# MATCH EVENTS
# ============================================================

@app.get("/api/analytics/events")
def analytics_events():

    with analytics_lock:

        return {
            "events": list(
                analytics["events"]
            )
        }


# ============================================================
# ANALYTICS RESET
# ============================================================

@app.post("/api/analytics/reset")
def reset_analytics():

    reset_analytics_data()

    return {

        "success": True,

        "message": "Match analytics have been reset."

    }


# ============================================================
# CSV MATCH REPORT
# ============================================================

@app.get("/api/analytics/report")
def download_analytics_report():

    summary = build_analytics_summary()

    player_rows = analytics_players()

    team_data = analytics_teams()

    output = io.StringIO()

    writer = csv.writer(output)

    writer.writerow([
        "FOOTVISION AR - MATCH ANALYTICS REPORT"
    ])

    writer.writerow([
        "Generated At",
        time.strftime("%Y-%m-%d %H:%M:%S")
    ])

    writer.writerow([])

    writer.writerow(["MATCH SUMMARY"])

    writer.writerow([
        "Frames Processed",
        summary["frames_processed"]
    ])

    writer.writerow([
        "Total Detections",
        summary["total_detections"]
    ])

    writer.writerow([
        "Unique Tracks",
        summary["unique_players"]
    ])

    writer.writerow([
        "Average Confidence",
        summary["average_confidence"]
    ])

    writer.writerow([])

    writer.writerow([
        "TEAM ANALYTICS"
    ])

    writer.writerow([
        "Team",
        "Detection Count"
    ])

    for team in team_data["teams"]:

        writer.writerow([
            team["team"],
            team["detections"]
        ])

    writer.writerow([])

    writer.writerow([
        "PLAYER TRACKING ANALYTICS"
    ])

    writer.writerow([
        "TRACK ID",
        "TEAM",
        "DETECTIONS",
        "ASSIGNED PLAYER",
        "POSITIONS RECORDED"
    ])

    for row in player_rows:

        assigned = row.get("player") or {}

        writer.writerow([

            row["track_id"],

            row["team"],

            row["detections"],

            assigned.get(
                "name",
                "Not assigned"
            ),

            row["positions_recorded"]

        ])

    writer.writerow([])

    writer.writerow([
        "VIDEO INFORMATION"
    ])

    for key, value in summary.get(
        "video_info",
        {}
    ).items():

        writer.writerow([
            key,
            value
        ])

    output.seek(0)

    return StreamingResponse(

        iter([output.getvalue()]),

        media_type="text/csv",

        headers={

            "Content-Disposition":
            'attachment; filename="footvision_match_analytics.csv"'

        }

    )


# ============================================================
# END OF FOOTVISION AR BACKEND
# ============================================================
