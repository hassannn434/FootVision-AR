
import streamlit as st
import requests
import pandas as pd
from PIL import Image, ImageDraw, ImageFont
from io import BytesIO

# --------------------------------------------------
# CONFIGURATION
# --------------------------------------------------

st.set_page_config(
    page_title="FootVision AR | Match Intelligence",
    page_icon="⚽",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Local development uses localhost.
# Streamlit Cloud reads the public URL from Secrets.
try:
    API_URL = st.secrets["API_URL"].rstrip("/")
except Exception:
    API_URL = "http://127.0.0.1:8000"
# --------------------------------------------------
# CUSTOM DESIGN
# --------------------------------------------------

st.markdown("""
<style>
.stApp {
    background-color: #0b1020;
    color: #f5f7fa;
}
[data-testid="stSidebar"] {
    background-color: #111827;
}
.metric-card {
    background: #172033;
    border: 1px solid #28364d;
    border-radius: 12px;
    padding: 18px;
    margin-bottom: 10px;
}
.metric-label {
    color: #9caec5;
    font-size: 14px;
}
.metric-value {
    font-size: 28px;
    font-weight: 700;
    color: white;
}
h1, h2, h3 {
    color: #ffffff;
}
div.stButton > button {
    border-radius: 8px;
    font-weight: 600;
}
</style>
""", unsafe_allow_html=True)

# --------------------------------------------------
# API HELPERS
# --------------------------------------------------

def api_get(endpoint):
    try:
        response = requests.get(
            f"{API_URL}{endpoint}",
            timeout=30
        )
        response.raise_for_status()
        return response.json()
    except requests.RequestException as error:
        st.error(f"API connection error: {error}")
        return None


def api_post(endpoint, data=None, files=None):
    try:
        response = requests.post(
            f"{API_URL}{endpoint}",
            json=data,
            files=files,
            timeout=180
        )
        response.raise_for_status()
        return response.json()
    except requests.RequestException as error:
        st.error(f"API request failed: {error}")

        if getattr(error, "response", None) is not None:
            st.error(error.response.text)

        return None


def api_put(endpoint, data):
    try:
        response = requests.put(
            f"{API_URL}{endpoint}",
            json=data,
            timeout=30
        )
        response.raise_for_status()
        return response.json()
    except requests.RequestException as error:
        st.error(f"Update failed: {error}")
        return None


# --------------------------------------------------
# SESSION STATE
# --------------------------------------------------

if "detection_result" not in st.session_state:
    st.session_state.detection_result = None

if "source_image" not in st.session_state:
    st.session_state.source_image = None

if "image_name" not in st.session_state:
    st.session_state.image_name = None


# --------------------------------------------------
# HEADER
# --------------------------------------------------

st.markdown("# ⚽ FOOTVISION AR")
st.markdown("### MATCH INTELLIGENCE")
st.caption(
    "AI-powered football player detection, tracking "
    "and team classification"
)

st.divider()

# --------------------------------------------------
# SIDEBAR
# --------------------------------------------------

st.sidebar.title("⚽ FootVision AR")
st.sidebar.caption("Match Intelligence Platform")

page = st.sidebar.radio(
    "NAVIGATION",
    [
        "Dashboard",
        "Player Profiles",
        "AI Detection",
        "Team Management"
    ]
)

st.sidebar.divider()

if st.sidebar.button("Check Backend Connection", use_container_width=True):
    health = api_get("/api/health")
    if health:
        st.sidebar.success("Backend connected!")

# --------------------------------------------------
# BACKEND STATUS
# --------------------------------------------------

health = api_get("/api/health")

if health:
    st.sidebar.success("● Backend Online")
else:
    st.sidebar.error("● Backend Offline")
    st.error(
        "Start your FastAPI backend before using the dashboard. "
        "Open another PowerShell window and run the backend command "
        "shown below."
    )
    st.code(
        r'cd "C:\Users\reina chaturvedi\OneDrive\Desktop\footvision-ar\backend"'
        "\n"
        r'.\venv\Scripts\python.exe -m uvicorn main:app --host 127.0.0.1 --port 8000'
    )
    st.stop()

players = api_get("/api/players")

if players is None:
    st.stop()

# --------------------------------------------------
# DASHBOARD
# --------------------------------------------------

if page == "Dashboard":

    st.subheader("Player Overview")
    st.write("Current player profiles and match information.")

    total_players = len(players)
    total_goals = sum(p.get("goals", 0) for p in players)
    total_assists = sum(p.get("assists", 0) for p in players)
    total_passes = sum(p.get("passes", 0) for p in players)

    c1, c2, c3, c4 = st.columns(4)

    with c1:
        st.metric("Total Players", total_players)

    with c2:
        st.metric("Total Goals", total_goals)

    with c3:
        st.metric("Total Assists", total_assists)

    with c4:
        st.metric("Total Passes", total_passes)

    st.divider()
    st.subheader("Player Cards")

    if players:
        columns = st.columns(3)

        for index, player in enumerate(players):
            with columns[index % 3]:
                st.markdown(
                    f"""
                    <div class="metric-card">
                        <div class="metric-label">
                            {player.get('team', 'Unknown Team')}
                        </div>
                        <h3>{player.get('name', 'Unknown')}</h3>
                        <div class="metric-label">
                            Jersey #{player.get('jersey_number', '-')}
                            · {player.get('position', '-')}
                        </div>
                        <hr>
                        <b>Goals:</b> {player.get('goals', 0)}<br>
                        <b>Assists:</b> {player.get('assists', 0)}<br>
                        <b>Passes:</b> {player.get('passes', 0)}<br>
                        <b>Shots:</b> {player.get('shots', 0)}<br>
                        <b>Speed:</b> {player.get('speed_kmh', 0)} km/h
                    </div>
                    """,
                    unsafe_allow_html=True
                )

    st.divider()
    st.subheader("Team Distribution")

    team_counts = {}
    for player in players:
        team = player.get("team", "Unknown")
        team_counts[team] = team_counts.get(team, 0) + 1

    if team_counts:
        st.bar_chart(
            pd.DataFrame(
                list(team_counts.items()),
                columns=["Team", "Players"]
            ).set_index("Team")
        )


# --------------------------------------------------
# PLAYER PROFILES
# --------------------------------------------------

elif page == "Player Profiles":

    st.subheader("Player Profile Management")

    player_options = {
        f"{p['name']} (ID: {p['id']})": p
        for p in players
    }

    selected_name = st.selectbox(
        "Select Player",
        list(player_options.keys())
    )

    player = player_options[selected_name]

    st.divider()
    st.subheader("Edit Player Information")

    with st.form("player_edit_form"):

        name = st.text_input("Player Name", player["name"])
        team = st.text_input("Team", player["team"])

        jersey = st.number_input(
            "Jersey Number",
            min_value=0,
            max_value=99,
            value=int(player["jersey_number"])
        )

        position = st.selectbox(
            "Position",
            ["Forward", "Midfielder", "Defender", "Goalkeeper"],
            index=(
                ["Forward", "Midfielder", "Defender", "Goalkeeper"]
                .index(player["position"])
                if player["position"] in
                ["Forward", "Midfielder", "Defender", "Goalkeeper"]
                else 0
            )
        )

        c1, c2 = st.columns(2)

        with c1:
            goals = st.number_input(
                "Goals",
                min_value=0,
                value=int(player.get("goals", 0))
            )

            assists = st.number_input(
                "Assists",
                min_value=0,
                value=int(player.get("assists", 0))
            )

            passes = st.number_input(
                "Passes",
                min_value=0,
                value=int(player.get("passes", 0))
            )

        with c2:
            shots = st.number_input(
                "Shots",
                min_value=0,
                value=int(player.get("shots", 0))
            )

            speed = st.number_input(
                "Speed (km/h)",
                min_value=0.0,
                max_value=60.0,
                value=float(player.get("speed_kmh", 0.0))
            )

        submitted = st.form_submit_button(
            "Save Player Changes",
            use_container_width=True
        )

        if submitted:

            payload = {
                "name": name,
                "team": team,
                "jersey_number": int(jersey),
                "position": position,
                "goals": int(goals),
                "assists": int(assists),
                "passes": int(passes),
                "shots": int(shots),
                "speed_kmh": float(speed)
            }

            result = api_put(
                f"/api/players/{player['id']}",
                payload
            )

            if result:
                st.success("Player profile updated!")
                st.rerun()


# --------------------------------------------------
# AI DETECTION
# --------------------------------------------------

elif page == "AI Detection":

    st.subheader("AI Player Detection")
    st.write(
        "Upload a football image or capture a frame using your camera. "
        "YOLOv8 detects players and the backend classifies jersey colours."
    )

    uploaded_file = st.file_uploader(
        "Upload Football Image",
        type=["jpg", "jpeg", "png"]
    )

    camera_file = st.camera_input("Or capture an image")

    selected_file = camera_file if camera_file is not None else uploaded_file

    if selected_file is not None:

        image_bytes = selected_file.getvalue()

        st.session_state.source_image = image_bytes
        st.session_state.image_name = getattr(
            selected_file, "name", "camera_capture.jpg"
        )

        st.image(
            Image.open(BytesIO(image_bytes)),
            caption="Selected Image",
            use_container_width=True
        )

        if st.button("Run AI Detection", type="primary", use_container_width=True):

            with st.spinner("Running YOLOv8 and ByteTrack..."):

                filename = getattr(
                    selected_file,
                    "name",
                    "camera_capture.jpg"
                )

                mime_type = getattr(
                    selected_file,
                    "type",
                    "image/jpeg"
                ) or "image/jpeg"

                files = {
                    "file": (
                        filename,
                        image_bytes,
                        mime_type
                    )
                }

                result = api_post(
                    "/api/detect-frame",
                    files=files
                )

                if result:
                    st.session_state.detection_result = result
                    st.success("Detection completed!")

    # Display saved detection result

    result = st.session_state.detection_result

    if result and st.session_state.source_image:

        st.divider()
        st.subheader("Detection Results")

        c1, c2, c3, c4 = st.columns(4)

        c1.metric("Players Detected", result.get("count", 0))
        c2.metric("Team A", result.get("team_a_count", 0))
        c3.metric("Team B", result.get("team_b_count", 0))
        c4.metric(
            "Unclassified",
            result.get("unclassified_count", 0)
        )

        original = Image.open(
            BytesIO(st.session_state.source_image)
        ).convert("RGB")

        annotated = original.copy()
        draw = ImageDraw.Draw(annotated)

        try:
            font = ImageFont.truetype("arial.ttf", 16)
        except OSError:
            font = ImageFont.load_default()

        for detection in result.get("detections", []):

            x1 = int(detection["x1"])
            y1 = int(detection["y1"])
            x2 = int(detection["x2"])
            y2 = int(detection["y2"])

            team = detection.get("team", "Unclassified")
            track_id = detection.get("track_id")
            player = detection.get("player")

            if team == "Team A":
                color = "#2196F3"
            elif team == "Team B":
                color = "#FF9800"
            else:
                color = "#AAAAAA"

            draw.rectangle(
                [x1, y1, x2, y2],
                outline=color,
                width=4
            )

            label = f"{team} | ID: {track_id}"

            if player:
                label += f" | {player['name']}"

            draw.text(
                (x1, max(0, y1 - 22)),
                label,
                fill=color,
                font=font
            )

        left, right = st.columns(2)

        with left:
            st.image(
                original,
                caption="Original Image",
                use_container_width=True
            )

        with right:
            st.image(
                annotated,
                caption="AI Detection Output",
                use_container_width=True
            )

        st.divider()
        st.subheader("Detected Player Details")

        detections = result.get("detections", [])

        if detections:

            display_data = []

            for d in detections:
                assigned = d.get("player") or {}

                display_data.append({
                    "Track ID": d.get("track_id"),
                    "Team": d.get("team"),
                    "Auto Team": d.get("auto_team"),
                    "Player": assigned.get("name", "Not Assigned"),
                    "Jersey Colour": d.get("jersey_color"),
                    "Confidence": d.get("confidence"),
                    "Manual Override": d.get("manual_override")
                })

            st.dataframe(
                pd.DataFrame(display_data),
                use_container_width=True,
                hide_index=True
            )

        else:
            st.info("No players were detected in this image.")


# --------------------------------------------------
# TEAM MANAGEMENT
# --------------------------------------------------

elif page == "Team Management":

    st.subheader("Team and Player Assignment")

    result = st.session_state.detection_result

    if not result:
        st.info(
            "First go to AI Detection and run detection on a football image."
        )

    else:

        detections = result.get("detections", [])

        track_ids = [
            d["track_id"]
            for d in detections
            if d.get("track_id") is not None
        ]

        if not track_ids:
            st.warning(
                "No tracking IDs were returned. "
                "Try an image with clearly visible players."
            )

        else:

            selected_track = st.selectbox(
                "Select Tracking ID",
                track_ids
            )

            selected_detection = next(
                d for d in detections
                if d.get("track_id") == selected_track
            )

            st.write(
                f"Current team: **{selected_detection.get('team')}**"
            )

            st.write(
                f"Current player: **{(selected_detection.get('player') or {}).get('name', 'Not assigned')}**"
            )

            st.divider()
            st.subheader("Correct Team Classification")

            team_choice = st.selectbox(
                "Choose Team",
                ["Auto", "Team A", "Team B"]
            )

            if st.button("Update Team", use_container_width=True):

                response = api_post(
                    "/api/team-override",
                    data={
                        "track_id": int(selected_track),
                        "team": team_choice
                    }
                )

                if response:
                    st.success("Team classification updated.")
                    st.info(
                        "Run detection again to see the updated team in the results."
                    )

            st.divider()
            st.subheader("Assign Player Profile")

            player_choices = {
                f"{p['name']} (ID: {p['id']})": p["id"]
                for p in players
            }

            assignment_options = {
                "Unassign Player": None,
                **player_choices
            }

            selected_player = st.selectbox(
                "Select Player Profile",
                list(assignment_options.keys())
            )

            if st.button("Assign Player", use_container_width=True):

                response = api_post(
                    "/api/player-assign",
                    data={
                        "track_id": int(selected_track),
                        "player_id": assignment_options[selected_player]
                    }
                )

                if response:
                    st.success(response.get("message", "Assignment updated."))
                    st.info(
                        "Run detection again to refresh the displayed assignment."
                    )

st.divider()

st.caption(
    "FootVision AR | Match Intelligence | "
    "YOLOv8 + ByteTrack + Jersey Colour Classification"
)
