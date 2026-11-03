
import React, { useEffect, useRef, useState, useCallback } from "react";
import "./CameraPanel.css";

const API_URL = "https://significance-quantum-completion-ide.trycloudflare.com";
export default function CameraPanel() {
  const videoRef = useRef(null);
  const canvasRef = useRef(null);
  const streamRef = useRef(null);
  const processingRef = useRef(false);
  const cameraStartTimeRef = useRef(null);

  const [stream, setStream] = useState(null);
  const [videoUrl, setVideoUrl] = useState("");
  const [fileName, setFileName] = useState("");
  const [status, setStatus] = useState("No video source selected");
  const [error, setError] = useState("");
  const [aiActive, setAiActive] = useState(false);

  const [detections, setDetections] = useState([]);
  const [playerProfiles, setPlayerProfiles] = useState([]);

  const [teamCounts, setTeamCounts] = useState({
    teamA: 0,
    teamB: 0,
    unknown: 0
  });

  const [manualAssignments, setManualAssignments] = useState({});
  const [updatingTrack, setUpdatingTrack] = useState(null);
  const [assigningTrack, setAssigningTrack] = useState(null);
  const [selectedPlayer, setSelectedPlayer] = useState(null);

  // Advanced analytics state
  const [analytics, setAnalytics] = useState([]);
  const [teamAnalytics, setTeamAnalytics] = useState(null);
  const [matchSummary, setMatchSummary] = useState(null);
  const [heatmapData, setHeatmapData] = useState([]);
  const [showHeatmap, setShowHeatmap] = useState(false);
  const [loadingAnalytics, setLoadingAnalytics] = useState(false);

  // ---------------------------------------------------------
  // LOAD PLAYER PROFILES
  // ---------------------------------------------------------

  useEffect(() => {
    fetch(`${API_URL}/api/players`)
      .then(response => {
        if (!response.ok) {
          throw new Error("Could not load player profiles.");
        }
        return response.json();
      })
      .then(data => setPlayerProfiles(data))
      .catch(err => setError(err.message));

    return () => {
      if (streamRef.current) {
        streamRef.current.getTracks().forEach(track => track.stop());
      }
    };
  }, []);

  useEffect(() => {
    if (videoRef.current) {
      videoRef.current.srcObject = stream;
    }
  }, [stream]);

  useEffect(() => {
    return () => {
      if (videoUrl) {
        URL.revokeObjectURL(videoUrl);
      }
    };
  }, [videoUrl]);

  // ---------------------------------------------------------
  // API HELPER
  // ---------------------------------------------------------

  const apiRequest = async (endpoint, options = {}) => {
    const response = await fetch(`${API_URL}${endpoint}`, options);

    if (!response.ok) {
      const details = await response.json().catch(() => ({}));
      throw new Error(details.detail || `Request failed: ${response.status}`);
    }

    return response.json();
  };

  // ---------------------------------------------------------
  // RESET MATCH ANALYSIS
  // ---------------------------------------------------------

  const clearOverlay = () => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    const context = canvas.getContext("2d");

    if (context) {
      context.clearRect(0, 0, canvas.width, canvas.height);
    }
  };

  const stopCamera = () => {
    if (streamRef.current) {
      streamRef.current.getTracks().forEach(track => track.stop());
      streamRef.current = null;
    }

    setStream(null);
  };

  const resetAnalysis = async () => {
    setDetections([]);
    setTeamCounts({
      teamA: 0,
      teamB: 0,
      unknown: 0
    });

    setManualAssignments({});
    setSelectedPlayer(null);

    setAnalytics([]);
    setTeamAnalytics(null);
    setMatchSummary(null);
    setHeatmapData([]);

    setAiActive(false);
    setShowHeatmap(false);

    processingRef.current = false;
    cameraStartTimeRef.current = null;

    clearOverlay();

    try {
      await apiRequest("/api/analytics/reset", {
        method: "POST"
      });
    } catch (err) {
      console.error("Analytics reset failed:", err);
    }
  };

  // ---------------------------------------------------------
  // START WEBCAM
  // ---------------------------------------------------------

  const startCamera = async () => {
    setError("");
    setStatus("Starting webcam...");

    stopCamera();

    setVideoUrl("");
    setFileName("");

    await resetAnalysis();

    try {
      const cameraStream = await navigator.mediaDevices.getUserMedia({
        video: {
          width: { ideal: 1280 },
          height: { ideal: 720 }
        },
        audio: false
      });

      streamRef.current = cameraStream;
      cameraStartTimeRef.current = performance.now() / 1000;

      setStream(cameraStream);
      setStatus("Live webcam active");

    } catch (err) {
      setError(
        "Unable to access camera. Please allow camera permission."
      );

      setStatus("Camera unavailable");
    }
  };

  // ---------------------------------------------------------
  // UPLOAD FOOTBALL VIDEO
  // ---------------------------------------------------------

  const handleVideoUpload = async event => {
    const file = event.target.files?.[0];

    if (!file) return;

    if (!file.type.startsWith("video/")) {
      setError("Please select a valid video file.");
      event.target.value = "";
      return;
    }

    stopCamera();

    await resetAnalysis();

    setError("");

    setVideoUrl(URL.createObjectURL(file));
    setFileName(file.name);
    setStatus("Uploaded video ready");

    event.target.value = "";
  };

  // ---------------------------------------------------------
  // CLEAR VIDEO
  // ---------------------------------------------------------

  const clearVideo = async () => {
    stopCamera();

    setVideoUrl("");
    setFileName("");

    setStatus("No video source selected");
    setError("");

    await resetAnalysis();
  };

  // ---------------------------------------------------------
  // TEAM COLOURS
  // ---------------------------------------------------------

  const getTeamColour = team => {
    if (team === "Team A") return "#4d9dff";
    if (team === "Team B") return "#f5c451";
    return "#aeb8c5";
  };

  // ---------------------------------------------------------
  // DRAW DETECTION BOXES
  // ---------------------------------------------------------

  const drawDetections = useCallback((items, width, height) => {
    const canvas = canvasRef.current;

    if (!canvas) return;

    canvas.width = width;
    canvas.height = height;

    const context = canvas.getContext("2d");

    context.clearRect(0, 0, width, height);

    items.forEach(item => {
      const colour = getTeamColour(item.team);

      const boxWidth = item.x2 - item.x1;
      const boxHeight = item.y2 - item.y1;

      context.strokeStyle = colour;
      context.lineWidth = Math.max(2, width / 500);

      context.strokeRect(
        item.x1,
        item.y1,
        boxWidth,
        boxHeight
      );

      const playerLabel = item.player
        ? `#${item.player.jersey_number} ${item.player.name}`
        : item.track_id != null
          ? `ID ${item.track_id}`
          : "Person";

      const label = `${playerLabel} | ${item.team}`;

      const fontSize = Math.max(13, width / 75);

      context.font = `bold ${fontSize}px Arial`;

      const textWidth = context.measureText(label).width;
      const labelHeight = fontSize + 10;
      const labelY = Math.max(0, item.y1 - labelHeight);

      context.fillStyle = colour;

      context.fillRect(
        item.x1,
        labelY,
        textWidth + 12,
        labelHeight
      );

      context.fillStyle = "#07120e";

      context.fillText(
        label,
        item.x1 + 6,
        labelY + fontSize
      );

      context.font = `${Math.max(11, fontSize - 2)}px Arial`;

      context.fillText(
        `${Math.round(item.confidence * 100)}%`,
        item.x1 + 5,
        item.y2 + fontSize
      );
    });
  }, []);

  // ---------------------------------------------------------
  // DRAW PLAYER HEATMAP
  // ---------------------------------------------------------

  const drawHeatmap = useCallback((items, width, height) => {
    const canvas = canvasRef.current;

    if (!canvas) return;

    canvas.width = width;
    canvas.height = height;

    const context = canvas.getContext("2d");

    context.clearRect(0, 0, width, height);

    items.forEach(player => {
      const positions = player.positions || [];

      if (positions.length < 2) return;

      const colour = getTeamColour(player.team);

      context.beginPath();
      context.strokeStyle = colour;
      context.lineWidth = Math.max(3, width / 300);
      context.globalAlpha = 0.55;

      positions.forEach((point, index) => {
        const x = point.normalized_x * width;
        const y = point.normalized_y * height;

        if (index === 0) {
          context.moveTo(x, y);
        } else {
          context.lineTo(x, y);
        }
      });

      context.stroke();
      context.globalAlpha = 1;

      const last = positions[positions.length - 1];

      context.beginPath();
      context.fillStyle = colour;
      context.arc(
        last.normalized_x * width,
        last.normalized_y * height,
        Math.max(5, width / 150),
        0,
        Math.PI * 2
      );

      context.fill();
    });
  }, []);

  // ---------------------------------------------------------
  // REFRESH ANALYTICS
  // ---------------------------------------------------------

  const refreshAnalytics = useCallback(async () => {
    setLoadingAnalytics(true);

    try {
      const [
        playerData,
        teamData,
        summaryData,
        heatmap
      ] = await Promise.all([
        apiRequest("/api/analytics/players"),
        apiRequest("/api/analytics/teams"),
        apiRequest("/api/analytics/summary"),
        apiRequest("/api/analytics/heatmap")
      ]);

      setAnalytics(playerData.players || []);
      setTeamAnalytics(teamData.teams || null);
      setMatchSummary(summaryData);
      setHeatmapData(heatmap.players || []);

    } catch (err) {
      console.error("Analytics update failed:", err);
    } finally {
      setLoadingAnalytics(false);
    }
  }, []);

  // ---------------------------------------------------------
  // CHANGE TEAM CLASSIFICATION
  // ---------------------------------------------------------

  const changeTeam = async (trackId, selectedTeam) => {
    if (trackId == null) {
      setError("This person has no tracking ID yet. Try again.");
      return;
    }

    setUpdatingTrack(trackId);
    setError("");

    try {
      await apiRequest("/api/team-override", {
        method: "POST",
        headers: {
          "Content-Type": "application/json"
        },
        body: JSON.stringify({
          track_id: trackId,
          team: selectedTeam
        })
      });

      setManualAssignments(previous => {
        const updated = { ...previous };

        if (selectedTeam === "Auto") {
          delete updated[trackId];
        } else {
          updated[trackId] = selectedTeam;
        }

        return updated;
      });

      setDetections(previous =>
        previous.map(item => {
          if (item.track_id !== trackId) return item;

          return {
            ...item,
            team: selectedTeam === "Auto"
              ? item.auto_team
              : selectedTeam,
            manual_override: selectedTeam !== "Auto"
          };
        })
      );

      await refreshAnalytics();

    } catch (err) {
      setError(`Team update failed: ${err.message}`);
    } finally {
      setUpdatingTrack(null);
    }
  };

  // ---------------------------------------------------------
  // ASSIGN PLAYER PROFILE
  // ---------------------------------------------------------

  const assignPlayerProfile = async (trackId, value) => {
    setAssigningTrack(trackId);
    setError("");

    try {
      const data = await apiRequest("/api/player-assign", {
        method: "POST",
        headers: {
          "Content-Type": "application/json"
        },
        body: JSON.stringify({
          track_id: trackId,
          player_id: value === "" ? null : Number(value)
        })
      });

      setDetections(previous =>
        previous.map(item => {
          if (item.track_id !== trackId) return item;

          return {
            ...item,
            player: data.player || null,
            player_id: data.player?.id ?? null
          };
        })
      );

      await refreshAnalytics();

    } catch (err) {
      setError(`Profile assignment failed: ${err.message}`);
    } finally {
      setAssigningTrack(null);
    }
  };

  // ---------------------------------------------------------
  // PROCESS WEBCAM AND UPLOADED VIDEO
  // ---------------------------------------------------------

  useEffect(() => {
    let animationId;
    let lastProcessTime = 0;
    let stopped = false;

    const processFrame = async timestamp => {
      animationId = requestAnimationFrame(processFrame);

      const video = videoRef.current;

      if (
        stopped ||
        !video ||
        video.readyState < 2 ||
        video.videoWidth === 0 ||
        video.paused ||
        processingRef.current ||
        timestamp - lastProcessTime < 300
      ) {
        return;
      }

      lastProcessTime = timestamp;
      processingRef.current = true;

      try {
        const captureCanvas = document.createElement("canvas");

        captureCanvas.width = video.videoWidth;
        captureCanvas.height = video.videoHeight;

        const captureContext = captureCanvas.getContext("2d");

        captureContext.drawImage(
          video,
          0,
          0,
          captureCanvas.width,
          captureCanvas.height
        );

        const blob = await new Promise(resolve => {
          captureCanvas.toBlob(
            resolve,
            "image/jpeg",
            0.8
          );
        });

        if (!blob || stopped) return;

        const formData = new FormData();

        formData.append("file", blob, "frame.jpg");

        // Use video playback time for uploaded footage.
        // Use elapsed camera time for live webcam.
        let frameTime;

        if (videoUrl) {
          frameTime = video.currentTime;
        } else {
          if (cameraStartTimeRef.current === null) {
            cameraStartTimeRef.current = performance.now() / 1000;
          }

          frameTime =
            performance.now() / 1000 -
            cameraStartTimeRef.current;
        }

        formData.append("video_time", String(frameTime));

        const response = await fetch(
          `${API_URL}/api/detect-frame`,
          {
            method: "POST",
            body: formData
          }
        );

        if (!response.ok) {
          const details = await response.json().catch(() => ({}));

          throw new Error(
            details.detail || "AI detection failed."
          );
        }

        const data = await response.json();

        if (!stopped) {
          setDetections(data.detections || []);

          setTeamCounts({
            teamA: data.team_a_count || 0,
            teamB: data.team_b_count || 0,
            unknown: data.unclassified_count || 0
          });

          if (showHeatmap) {
            const heatmap = await apiRequest(
              "/api/analytics/heatmap"
            );

            if (!stopped) {
              setHeatmapData(heatmap.players || []);

              drawHeatmap(
                heatmap.players || [],
                data.width,
                data.height
              );
            }
          } else {
            drawDetections(
              data.detections || [],
              data.width,
              data.height
            );
          }

          // Update dashboard analytics periodically.
          await refreshAnalytics();

          setAiActive(true);
          setStatus("AI detection running");
          setError("");
        }

      } catch (err) {
        if (!stopped) {
          setError(`AI processing error: ${err.message}`);
          setAiActive(false);
        }
      } finally {
        processingRef.current = false;
      }
    };

    if (stream || videoUrl) {
      animationId = requestAnimationFrame(processFrame);
    }

    return () => {
      stopped = true;
      cancelAnimationFrame(animationId);
      processingRef.current = false;
    };
  }, [
    stream,
    videoUrl,
    showHeatmap,
    drawDetections,
    drawHeatmap,
    refreshAnalytics
  ]);

  // ---------------------------------------------------------
  // HEATMAP TOGGLE
  // ---------------------------------------------------------

  const toggleHeatmap = async () => {
    const nextValue = !showHeatmap;

    setShowHeatmap(nextValue);

    if (!nextValue) {
      const video = videoRef.current;

      if (video && video.videoWidth > 0) {
        drawDetections(
          detections,
          video.videoWidth,
          video.videoHeight
        );
      }
    }
  };

  // ---------------------------------------------------------
  // DOWNLOAD MATCH REPORT
  // ---------------------------------------------------------

  const downloadReport = async () => {
    try {
      const response = await fetch(
        `${API_URL}/api/analytics/report`
      );

      if (!response.ok) {
        throw new Error("Could not download match report.");
      }

      const blob = await response.blob();

      const downloadUrl = URL.createObjectURL(blob);

      const link = document.createElement("a");

      link.href = downloadUrl;
      link.download = "footvision_match_report.csv";

      document.body.appendChild(link);
      link.click();
      link.remove();

      URL.revokeObjectURL(downloadUrl);

    } catch (err) {
      setError(err.message);
    }
  };

  // ---------------------------------------------------------
  // CURRENTLY VISIBLE PLAYERS
  // ---------------------------------------------------------

  const visiblePlayers = detections.filter(
    (item, index, array) =>
      item.track_id != null &&
      array.findIndex(
        other => other.track_id === item.track_id
      ) === index
  );

  // ---------------------------------------------------------
  // FORMAT NUMBERS
  // ---------------------------------------------------------

  const formatNumber = value => {
    return Number(value || 0).toFixed(1);
  };

  // ---------------------------------------------------------
  // USER INTERFACE
  // ---------------------------------------------------------

  return (
    <section className="camera-panel">

      <div className="camera-heading">
        <div>
          <span className="camera-label">
            AI VIDEO ANALYSIS
          </span>

          <h2>Live Camera & Match Footage</h2>

          <p>
            AI player detection, tracking, movement analytics
            and team performance analysis.
          </p>
        </div>

        <span className="camera-status">
          <span className="status-dot"></span>
          {status}
        </span>
      </div>

      {/* VIDEO CONTROLS */}

      <div className="camera-controls">

        <button
          className="camera-button primary"
          onClick={startCamera}
        >
          Start Webcam
        </button>

        <label className="camera-button secondary">
          Upload Football Video

          <input
            type="file"
            accept="video/*"
            onChange={handleVideoUpload}
            hidden
          />
        </label>

        <button
          className="camera-button secondary"
          onClick={clearVideo}
        >
          Clear
        </button>

      </div>

      {error && (
        <p className="camera-error">
          {error}
        </p>
      )}

      {/* VIDEO PLAYER */}

      <div className="video-container">

        <video
          ref={videoRef}
          src={videoUrl || undefined}
          autoPlay={Boolean(stream)}
          muted
          controls={Boolean(videoUrl)}
          playsInline
        />

        <canvas
          ref={canvasRef}
          className="detection-canvas"
        />

        {!stream && !videoUrl && (
          <div className="video-placeholder">
            <div className="camera-placeholder-icon">
              ◎
            </div>

            <h3>No video source selected</h3>

            <p>
              Start your webcam or upload a match recording.
            </p>
          </div>
        )}

      </div>

      {fileName && (
        <p className="uploaded-file">
          Selected video: <strong>{fileName}</strong>
        </p>
      )}

      {/* AI STATUS */}

      <div className="detection-notice">
        <span>AI PROCESSING</span>

        <p>
          {aiActive
            ? "YOLOv8 detection, ByteTrack tracking and team classification are active."
            : "Select a webcam or video and play it to start AI detection."}
        </p>
      </div>

      {/* TEAM COUNTS */}

      <div className="detection-stats">

        <div>
          <span>TEAM A</span>
          <strong>{teamCounts.teamA}</strong>
        </div>

        <div>
          <span>TEAM B</span>
          <strong>{teamCounts.teamB}</strong>
        </div>

        <div>
          <span>UNCLASSIFIED</span>
          <strong>{teamCounts.unknown}</strong>
        </div>

      </div>

      {/* MATCH ANALYTICS */}

      <div className="team-management">

        <div className="team-management-heading">
          <div>
            <span className="camera-label">
              MATCH INTELLIGENCE
            </span>

            <h3>Match Analytics Dashboard</h3>

            <p>
              Live statistics calculated from detected player movement.
            </p>
          </div>

          <button
            className="camera-button secondary"
            onClick={refreshAnalytics}
            disabled={loadingAnalytics}
          >
            {loadingAnalytics ? "Refreshing..." : "Refresh"}
          </button>
        </div>

        <div className="profile-stat-grid">

          <div>
            <span>TRACKED PLAYERS</span>
            <strong>
              {matchSummary?.total_unique_tracks ?? 0}
            </strong>
          </div>

          <div>
            <span>PROCESSED FRAMES</span>
            <strong>
              {matchSummary?.total_processed_frames ?? 0}
            </strong>
          </div>

          <div>
            <span>TOTAL DETECTIONS</span>
            <strong>
              {matchSummary?.total_detections ?? 0}
            </strong>
          </div>

          <div>
            <span>TEAM A TRACKS</span>
            <strong>
              {matchSummary?.team_a_players ?? 0}
            </strong>
          </div>

          <div>
            <span>TEAM B TRACKS</span>
            <strong>
              {matchSummary?.team_b_players ?? 0}
            </strong>
          </div>

          <div>
            <span>TOTAL MOVEMENT</span>
            <strong>
              {formatNumber(matchSummary?.total_distance_px)} px
            </strong>
          </div>

        </div>

        <div className="detection-notice">
          <span>MOVEMENT MEASUREMENT</span>
          <p>
            Distance and speed are estimated in video pixels.
            They are not calibrated real-world distances or km/h.
          </p>
        </div>

      </div>

      {/* TEAM COMPARISON */}

      <div className="team-management">

        <div className="team-management-heading">
          <div>
            <span className="camera-label">
              TEAM PERFORMANCE
            </span>

            <h3>Team Comparison</h3>
          </div>
        </div>

        <div className="profile-stat-grid">

          {["Team A", "Team B"].map(team => {
            const stats = teamAnalytics?.[team];

            return (
              <div key={team}>
                <span>{team.toUpperCase()}</span>

                <strong>
                  {stats?.players ?? 0} players
                </strong>

                <p>
                  Distance: {formatNumber(stats?.total_distance_px)} px
                </p>

                <p>
                  Avg movement: {formatNumber(stats?.average_speed_px_s)} px/s
                </p>
              </div>
            );
          })}

        </div>

      </div>

      {/* HEATMAP CONTROLS */}

      <div className="team-management">

        <div className="team-management-heading">
          <div>
            <span className="camera-label">
              PLAYER MOVEMENT VISUALIZATION
            </span>

            <h3>Movement Heatmap</h3>

            <p>
              View player movement paths over the video.
            </p>
          </div>

          <button
            className="camera-button secondary"
            onClick={toggleHeatmap}
          >
            {showHeatmap ? "Hide Heatmap" : "Show Heatmap"}
          </button>
        </div>

        <p className="team-empty">
          {showHeatmap
            ? "Movement trails are displayed using the current video frame."
            : "Activate the heatmap to display player movement trails."}
        </p>

      </div>

      {/* PLAYER MANAGEMENT */}

      <div className="team-management">

        <div className="team-management-heading">
          <div>
            <span className="camera-label">
              PLAYER MANAGEMENT
            </span>

            <h3>Detected Players & Profiles</h3>

            <p>
              Assign player profiles and correct team classifications.
            </p>
          </div>
        </div>

        {visiblePlayers.length === 0 ? (
          <p className="team-empty">
            No tracked players yet. Play a football video to display players.
          </p>
        ) : (
          <div className="team-player-list">

            {visiblePlayers.map(item => (
              <div
                className="team-player-row"
                key={item.track_id}
              >

                <div className="team-player-info">

                  <span
                    className="jersey-colour-swatch"
                    style={{
                      backgroundColor: item.jersey_color || "#808080"
                    }}
                  />

                  <div>
                    <strong>
                      {item.player
                        ? `#${item.player.jersey_number} ${item.player.name}`
                        : `Player ID ${item.track_id}`}
                    </strong>

                    <span>
                      {item.player
                        ? `${item.player.position} · ${item.player.team}`
                        : `Automatic: ${item.auto_team}`}

                      {item.manual_override
                        ? " · Manually corrected"
                        : ""}
                    </span>

                    {item.player && (
                      <button
                        className="profile-details-button"
                        onClick={() => setSelectedPlayer(item.player)}
                      >
                        View player statistics
                      </button>
                    )}

                    {item.movement && (
                      <span>
                        Movement: {formatNumber(item.movement.distance_px)} px
                        {" · "}
                        Speed: {formatNumber(item.movement.instant_speed_px_s)} px/s
                      </span>
                    )}
                  </div>

                </div>

                <select
                  value={item.player_id ?? ""}
                  disabled={assigningTrack === item.track_id}
                  onChange={event =>
                    assignPlayerProfile(
                      item.track_id,
                      event.target.value
                    )
                  }
                  aria-label={`Assign profile to player ${item.track_id}`}
                >
                  <option value="">
                    No profile assigned
                  </option>

                  {playerProfiles.map(player => (
                    <option
                      key={player.id}
                      value={player.id}
                    >
                      #{player.jersey_number} — {player.name}
                    </option>
                  ))}
                </select>

                <select
                  value={manualAssignments[item.track_id] || "Auto"}
                  disabled={updatingTrack === item.track_id}
                  onChange={event =>
                    changeTeam(
                      item.track_id,
                      event.target.value
                    )
                  }
                  aria-label={`Assign team for player ${item.track_id}`}
                >
                  <option value="Auto">Automatic team</option>
                  <option value="Team A">Team A</option>
                  <option value="Team B">Team B</option>
                </select>

              </div>
            ))}

          </div>
        )}

      </div>

      {/* PLAYER PERFORMANCE TABLE */}

      <div className="team-management">

        <div className="team-management-heading">
          <div>
            <span className="camera-label">
              PERFORMANCE ANALYTICS
            </span>

            <h3>Player Movement Statistics</h3>

            <p>
              Statistics accumulated for each tracking ID.
            </p>
          </div>
        </div>

        {analytics.length === 0 ? (
          <p className="team-empty">
            Player analytics will appear after video processing starts.
          </p>
        ) : (
          <div style={{ overflowX: "auto" }}>
            <table style={{
              width: "100%",
              borderCollapse: "collapse",
              textAlign: "left"
            }}>
              <thead>
                <tr>
                  <th>Player</th>
                  <th>Team</th>
                  <th>Distance (px)</th>
                  <th>Average (px/s)</th>
                  <th>Maximum (px/s)</th>
                  <th>Samples</th>
                </tr>
              </thead>

              <tbody>
                {analytics.map(player => (
                  <tr key={player.track_id}>
                    <td>
                      {player.player_name}
                    </td>

                    <td>
                      {player.team}
                    </td>

                    <td>
                      {formatNumber(player.distance_px)}
                    </td>

                    <td>
                      {formatNumber(player.average_speed_px_s)}
                    </td>

                    <td>
                      {formatNumber(player.max_speed_px_s)}
                    </td>

                    <td>
                      {player.observations}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

      </div>

      {/* REPORT DOWNLOAD */}

      <div className="camera-controls">

        <button
          className="camera-button primary"
          onClick={downloadReport}
        >
          Download Match Report (CSV)
        </button>

        <button
          className="camera-button secondary"
          onClick={refreshAnalytics}
        >
          Update Analytics
        </button>

      </div>

      {/* PLAYER PROFILE MODAL */}

      {selectedPlayer && (
        <div className="player-profile-modal">

          <div className="player-profile-card">

            <button
              className="profile-close"
              onClick={() => setSelectedPlayer(null)}
            >
              ×
            </button>

            <span className="camera-label">
              PLAYER PROFILE · DEMO DATA
            </span>

            <h3>
              #{selectedPlayer.jersey_number} {selectedPlayer.name}
            </h3>

            <p>
              {selectedPlayer.position} · {selectedPlayer.team}
            </p>

            <div className="profile-stat-grid">

              <div>
                <span>GOALS</span>
                <strong>{selectedPlayer.goals}</strong>
              </div>

              <div>
                <span>ASSISTS</span>
                <strong>{selectedPlayer.assists}</strong>
              </div>

              <div>
                <span>PASSES</span>
                <strong>{selectedPlayer.passes}</strong>
              </div>

              <div>
                <span>SHOTS</span>
                <strong>{selectedPlayer.shots}</strong>
              </div>

              <div>
                <span>SPEED</span>
                <strong>{selectedPlayer.speed_kmh} km/h</strong>
              </div>

            </div>

            <small>
              These are sample roster statistics, not measurements calculated from the video.
            </small>

          </div>

        </div>
      )}

    </section>
  );
}
