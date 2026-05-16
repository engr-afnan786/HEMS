# HEMS Pakistan — Convex Optimization Dashboard v3.0

This project is a Home Energy Management System (HEMS) for Pakistan (NEPRA IESCO Feb 2026 / Budget 2024-25). It uses Convex Optimization (SOCP) with a fallback mechanism to minimize daily energy costs considering load, solar PV generation, and Time-of-Use (TOU) tariffs.

## Features

- **Convex Optimization**: Uses CVXPY and ECOS/SCS to optimize battery scheduling and load management.
- **Robustness**: SOCP (Second-Order Cone Programming) model with a fallback mechanism.
- **Dashboard**: Web-based interactive dashboard built with Flask and Plotly.
- **Hardware Integration**: Optional MQTT hardware control support using Paho-MQTT.

## Installation

1. Clone the repository:
   ```bash
   git clone <your-github-repo-url>
   cd HEMS_Production
   ```

2. Create a virtual environment and activate it:
   ```bash
   python -m venv .venv312
   
   # On Windows
   .\.venv312\Scripts\activate
   
   # On Linux/macOS
   source .venv312/bin/activate
   ```

3. Install the dependencies:
   ```bash
   pip install -r requirements.txt
   ```

4. Set up your environment variables:
   Copy `.env.example` to `.env` and fill in the required parameters.

## Usage

Run the web application:
```bash
python run.py
```
Open your browser and navigate to `http://localhost:5000` to access the dashboard.

## Tech Stack
- **Backend**: Python, Flask, Pandas
- **Optimization**: CVXPY, NumPy, SciPy
- **Visualization**: Plotly, Matplotlib
- **IoT/Hardware**: Paho-MQTT

## License
MIT License
