# ============================================================================
# ModelServe — Streamlit Testing UI
# ============================================================================
# Minimal UI for testing the fraud detection API.
# Run with: streamlit run app/ui.py
# ============================================================================

import streamlit as st
import requests
from typing import Optional

# Page config
st.set_page_config(
    page_title="ModelServe Testing UI",
    page_icon="🔍",
    layout="centered",
)

# ─────────────────────────────────────────────────────────────
#  Configuration
# ─────────────────────────────────────────────────────────────

st.sidebar.header("Configuration")
API_BASE = st.sidebar.text_input(
    "API Base URL",
    value="http://localhost:8000",
    help="The base URL of the running FastAPI server"
)

# ─────────────────────────────────────────────────────────────
#  Helper Functions
# ─────────────────────────────────────────────────────────────

def check_api_available() -> bool:
    """Check if API is available."""
    try:
        response = requests.get(f"{API_BASE}/health", timeout=5)
        return response.status_code == 200
    except requests.exceptions.RequestException:
        return False


def get_health() -> Optional[dict]:
    """Get health status."""
    try:
        response = requests.get(f"{API_BASE}/health", timeout=10)
        if response.status_code == 200:
            return response.json()
        return None
    except requests.exceptions.RequestException:
        return None


def post_predict(entity_id: int) -> Optional[dict]:
    """Make prediction via POST."""
    try:
        response = requests.post(
            f"{API_BASE}/predict",
            json={"entity_id": entity_id},
            timeout=10
        )
        if response.status_code == 200:
            return response.json()
        return {"error": response.json().get("detail", "Unknown error")}
    except requests.exceptions.RequestException as e:
        return {"error": str(e)}


def get_predict(entity_id: int, explain: bool = False) -> Optional[dict]:
    """Make prediction via GET."""
    try:
        url = f"{API_BASE}/predict/{entity_id}"
        params = {"explain": explain} if explain else {}
        response = requests.get(url, params=params, timeout=10)
        if response.status_code == 200:
            return response.json()
        return {"error": response.json().get("detail", "Unknown error")}
    except requests.exceptions.RequestException as e:
        return {"error": str(e)}


# ─────────────────────────────────────────────────────────────
#  Main UI
# ─────────────────────────────────────────────────────────────

st.title("🔍 ModelServe Testing UI")
st.markdown("Test the fraud detection API endpoints easily.")

# Check API availability
if not check_api_available():
    st.error("❌ API is not available. Make sure the FastAPI server is running.")
    st.info(f"Start the server with: uvicorn app.main:app --reload --host 0.0.0.0 --port 8000")
    st.markdown("---")
    st.markdown("*Then refresh this page.*")
    st.stop()

st.success("✅ API is connected")

# Create tabs for different functionalities
tab1, tab2, tab3 = st.tabs(["🏥 Health", "📊 Predict", "📈 Metrics"])

# ─────────────────────────────────────────────────────────────
#  Tab 1: Health Check
# ─────────────────────────────────────────────────────────────

with tab1:
    st.header("Health Check")

    if st.button("Check Health", type="primary"):
        with st.spinner("Checking..."):
            health = get_health()

        if health:
            col1, col2 = st.columns(2)
            with col1:
                st.metric("Status", health.get("status", "unknown"))
            with col2:
                st.metric("Model Version", health.get("model_version", "N/A"))
        else:
            st.error("Failed to get health status")

# ─────────────────────────────────────────────────────────────
#  Tab 2: Predict
# ─────────────────────────────────────────────────────────────

with tab2:
    st.header("Make Prediction")

    method = st.radio("Method", ["POST", "GET"], horizontal=True)
    entity_id = st.number_input(
        "Entity ID (cc_num)",
        min_value=1,
        value=1234567890,
        step=1,
        help="Credit card number for feature lookup"
    )

    explain = False
    if method == "GET":
        explain = st.checkbox("Include feature values", help="Include feature values in response")

    if st.button("Predict", type="primary"):
        with st.spinner("Making prediction..."):
            if method == "POST":
                result = post_predict(entity_id)
            else:
                result = get_predict(entity_id, explain)

        if result:
            if "error" in result:
                st.error(f"Error: {result['error']}")
            else:
                st.subheader("Prediction Result")

                # Display results in columns
                col1, col2, col3 = st.columns(3)
                with col1:
                    pred_label = "⚠️ Fraud" if result.get("prediction") == 1 else "✅ Legitimate"
                    st.metric("Prediction", pred_label)
                with col2:
                    prob = result.get("probability", 0)
                    st.metric("Probability", f"{prob:.4f}")
                with col3:
                    st.metric("Model Version", result.get("model_version", "N/A"))

                st.caption(f"Timestamp: {result.get('timestamp', 'N/A')}")

                # Show features if available and requested
                if explain and result.get("features"):
                    st.subheader("Feature Values")
                    features = result["features"]
                    # Display as a simple table
                    feature_data = [{"Feature": k, "Value": v} for k, v in features.items()]
                    st.table(feature_data)

# ─────────────────────────────────────────────────────────────
#  Tab 3: Metrics
# ─────────────────────────────────────────────────────────────

with tab3:
    st.header("Prometheus Metrics")

    st.info("Fetch and view Prometheus metrics from the API.")

    if st.button("Fetch Metrics", type="primary"):
        with st.spinner("Fetching metrics..."):
            try:
                response = requests.get(f"{API_BASE}/metrics", timeout=10)
                if response.status_code == 200:
                    metrics_text = response.text

                    # Display metrics in a code block
                    st.subheader("Raw Metrics")
                    st.code(metrics_text, language="text")

                    # Try to parse and display key metrics
                    st.subheader("Key Metrics Summary")

                    key_metrics = {}
                    for line in metrics_text.split("\n"):
                        if line.startswith("#") or not line.strip():
                            continue
                        if "modelserve" in line or "prediction" in line or "feast" in line:
                            parts = line.split()
                            if len(parts) >= 2:
                                key_metrics[parts[0]] = parts[1]

                    if key_metrics:
                        cols = st.columns(min(3, len(key_metrics)))
                        for i, (name, value) in enumerate(key_metrics.items()):
                            with cols[i % 3]:
                                st.metric(name.split("{")[0], value)
                    else:
                        st.info("No custom metrics found (only standard Prometheus metrics)")
                else:
                    st.error(f"Failed to fetch metrics: {response.status_code}")
            except requests.exceptions.RequestException as e:
                st.error(f"Error fetching metrics: {e}")

# ─────────────────────────────────────────────────────────────
#  Footer
# ─────────────────────────────────────────────────────────────

st.markdown("---")
st.caption("ModelServe - MLOps Capstone Project | Fraud Detection API Testing UI")