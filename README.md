# FOOTVISION AR

AI-powered football intelligence and augmented-reality web application starter.

This ZIP contains the **Milestone 1 full-stack foundation** from the setup guide:
- React + Vite frontend
- FastAPI backend
- Sample player-statistics API
- React-to-FastAPI integration
- CORS configuration
- Setup instructions

> Important: YOLO detection, ByteTrack tracking, jersey OCR, PostgreSQL persistence and true camera-anchored AR are planned next milestones. They are not implemented in this starter ZIP. The sample player statistics are demo data, not live match data.

## Requirements

- Python 3.11+
- Node.js LTS
- VS Code (recommended)

## Project structure

```text
footvision-ar/
├── backend/
│   ├── main.py
│   ├── requirements.txt
│   └── .env.example
├── frontend/
│   ├── index.html
│   ├── package.json
│   ├── vite.config.js
│   └── src/
│       ├── App.jsx
│       ├── index.css
│       └── main.jsx
└── README.md
```

## 1. Start the backend

Open a terminal in the project root:

### Windows PowerShell

```powershell
cd backend
py -3.11 -m venv venv
.\venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
uvicorn main:app --reload
```

If PowerShell blocks activation, use Command Prompt instead:

```bat
cd backend
py -3.11 -m venv venv
venv\Scripts\activate.bat
pip install -r requirements.txt
uvicorn main:app --reload
```

### macOS / Linux

```bash
cd backend
python3 -m venv venv
source venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
uvicorn main:app --reload
```

Backend URLs:
- API health: http://127.0.0.1:8000/
- API documentation: http://127.0.0.1:8000/docs
- Players: http://127.0.0.1:8000/api/players

Keep this terminal running.

## 2. Start the frontend

Open a **second terminal** in the project root:

```bash
cd frontend
npm install
npm run dev
```

Open the local URL printed by Vite, normally:
http://localhost:5173

Keep this terminal running too.

## 3. Test the API

Visit http://127.0.0.1:8000/docs and try:
- `GET /`
- `GET /api/players`
- `GET /api/players/{player_id}`

The React dashboard fetches player data from the FastAPI endpoint.

## Troubleshooting

- **`python` not found:** install Python and enable “Add Python to PATH”, then reopen the terminal.
- **`npm` not found:** install Node.js LTS, then reopen the terminal.
- **PowerShell activation error:** use Command Prompt commands shown above, or configure your local PowerShell execution policy.
- **Frontend cannot reach API:** make sure FastAPI is running on port 8000 and frontend on port 5173.
- **CORS error:** check that the frontend origin is `http://localhost:5173`. If Vite uses another port, update `allow_origins` in `backend/main.py`.
- **Port already in use:** stop the other process or run the service on a different port and update the frontend API URL/CORS settings.

## Planned next milestones

1. Camera capture and video overlay in the browser.
2. Video upload and AI inference endpoint.
3. YOLO player detection and ByteTrack tracking.
4. Jersey-number OCR and player-to-roster matching.
5. Persistent PostgreSQL data and match/statistics APIs.
6. Three.js AR-style overlays and field mapping.
7. Testing, deployment and internship documentation.

## Demo-data disclaimer

Names and statistics in `backend/main.py` are fictional sample records used to verify API integration. Do not present them as actual player statistics.
