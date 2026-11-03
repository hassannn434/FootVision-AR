
import CameraPanel from "./CameraPanel";
import { useEffect, useState } from "react";
import axios from "axios";
import {
  Activity,
  Crosshair,
  Goal,
  Radio,
  RefreshCw,
  ShieldCheck
} from "lucide-react";

const API_URL = import.meta.env.VITE_API_URL || "http://127.0.0.1:8000";

function Stat({ label, value }) {
  return (
    <div className="stat">
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  );
}

export default function App() {
  const [players, setPlayers] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  async function loadPlayers() {
    setLoading(true);
    setError("");

    try {
      const response = await axios.get(`${API_URL}/api/players`);
      setPlayers(response.data);
    } catch {
      setError(
        "Could not connect to the API. Check that the FastAPI backend is running on port 8000."
      );
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    loadPlayers();
  }, []);

  return (
    <main className="app-shell">

      {/* HEADER */}
      <header className="topbar">
        <a className="brand" href="/" aria-label="FootVision home">
          <span className="brand-mark">
            <Crosshair size={22} />
          </span>

          <span>
            FOOTVISION
            <span className="brand-accent"> AR</span>
          </span>
        </a>

        <div className="topbar-right">
          <span className="status-dot" />
          <span>PROTOTYPE MODE</span>
        </div>
      </header>

      {/* HERO SECTION */}
      <section className="hero">
        <div className="eyebrow">
          <Activity size={15} />
          AI-POWERED FOOTBALL INTELLIGENCE
        </div>

        <h1>
          See the game
          <br />
          <span>beyond the field.</span>
        </h1>

        <p className="hero-copy">
          A foundation for real-time player detection, match analytics and
          augmented-reality football experiences.
        </p>

        <div className="hero-actions">
          <a className="primary-button" href="#players">
            <Goal size={17} />
            Explore players
          </a>

          <span className="prototype-note">
            <ShieldCheck size={15} />
            Demo data · Not live match stats
          </span>
        </div>
      </section>

      {/* CAMERA AND VIDEO UPLOAD SECTION */}
      <CameraPanel />

      {/* PLAYER OVERVIEW */}
      <section className="section-heading" id="players">
        <div>
          <div className="eyebrow">MATCH INTELLIGENCE</div>
          <h2>Player overview</h2>
        </div>

        <button
          className="refresh-button"
          onClick={loadPlayers}
          disabled={loading}
        >
          <RefreshCw
            size={15}
            className={loading ? "spin" : ""}
          />
          Refresh
        </button>
      </section>

      {/* LOADING MESSAGE */}
      {loading && (
        <div className="message-panel">
          Loading player data from FootVision API…
        </div>
      )}

      {/* API ERROR */}
      {error && (
        <div className="message-panel error-panel">
          {error}
          <button onClick={loadPlayers}>Try again</button>
        </div>
      )}

      {/* PLAYER DATA */}
      {!loading && !error && (
        <>
          <div className="summary-row">
            <div className="summary-card">
              <span>PLAYERS LOADED</span>
              <strong>
                {players.length.toString().padStart(2, "0")}
              </strong>
            </div>

            <div className="summary-card">
              <span>DATA SOURCE</span>
              <strong>REST API</strong>
            </div>

            <div className="summary-card">
              <span>PROCESSING</span>
              <strong className="demo-status">
                <Radio size={15} />
                DEMO
              </strong>
            </div>
          </div>

          <div className="player-grid">
            {players.map((player) => (
              <article className="player-card" key={player.id}>
                <div className="player-card-top">
                  <div className="jersey">
                    #{String(player.jersey_number).padStart(2, "0")}
                  </div>

                  <span className="position-tag">
                    {player.position}
                  </span>
                </div>

                <div className="player-name">
                  {player.name}
                </div>

                <div className="team-name">
                  {player.team}
                </div>

                <div className="stats-grid">
                  <Stat label="GOALS" value={player.goals} />
                  <Stat label="ASSISTS" value={player.assists} />
                  <Stat label="PASSES" value={player.passes} />
                  <Stat label="SHOTS" value={player.shots} />
                </div>

                <div className="speed-row">
                  <span>TOP SPEED · SAMPLE</span>
                  <strong>
                    {player.speed_kmh}
                    <small> km/h</small>
                  </strong>
                </div>
              </article>
            ))}
          </div>
        </>
      )}

      {/* NEXT DEVELOPMENT MILESTONE */}
      <section className="next-panel">
        <div className="next-icon">
          <Crosshair size={22} />
        </div>

        <div>
          <div className="eyebrow">
            NEXT DEVELOPMENT MILESTONE
          </div>

          <h3>Bring the pitch into view.</h3>

          <p>
            Next: YOLO-based player detection, video frame processing,
            player tracking and AR overlays.
          </p>
        </div>
      </section>

      {/* FOOTER */}
      <footer>
        FOOTVISION AR
        <span> · </span>
        FDE INTERNSHIP PROJECT
        <span> · </span>
        PROTOTYPE v0.2
      </footer>

    </main>
  );
}
