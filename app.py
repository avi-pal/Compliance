"""
Email Compliance System - Streamlit Frontend
Aesthetic UI for compliance email monitoring
"""

import streamlit as st
import requests
import pandas as pd
import json
from datetime import datetime

# ── Page Configuration ──────────────────────────────────────────────────────

st.set_page_config(
    page_title="Email Compliance System",
    page_icon="📧",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ── Custom CSS for Aesthetic UI ─────────────────────────────────────────────

st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');
    
    * {
        font-family: 'Inter', sans-serif;
    }
    
    .main {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        padding: 2rem;
    }
    
    .stTabs [data-baseweb="tab-list"] {
        gap: 8px;
        background: rgba(255, 255, 255, 0.1);
        border-radius: 16px;
        padding: 8px;
        backdrop-filter: blur(10px);
    }
    
    .stTabs [data-baseweb="tab"] {
        height: 50px;
        border-radius: 12px;
        padding: 0 24px;
        font-weight: 500;
        color: #4a5568;
        background: transparent;
        border: none;
        transition: all 0.3s ease;
    }
    
    .stTabs [aria-selected="true"] {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%) !important;
        color: white !important;
        box-shadow: 0 4px 15px rgba(102, 126, 234, 0.4);
    }
    
    .upload-card {
        background: white;
        border-radius: 20px;
        padding: 2rem;
        box-shadow: 0 10px 40px rgba(0, 0, 0, 0.1);
        border: 1px solid rgba(255, 255, 255, 0.2);
    }
    
    .email-card {
        background: white;
        border-radius: 16px;
        padding: 1.5rem;
        margin-bottom: 1rem;
        box-shadow: 0 4px 20px rgba(0, 0, 0, 0.08);
        border-left: 4px solid #667eea;
        transition: transform 0.2s ease, box-shadow 0.2s ease;
    }
    
    .email-card:hover {
        transform: translateY(-2px);
        box-shadow: 0 8px 30px rgba(0, 0, 0, 0.12);
    }
    
    .email-card.critical {
        border-left-color: #e53e3e;
    }
    
    .email-card.high {
        border-left-color: #dd6b20;
    }
    
    .email-card.medium {
        border-left-color: #d69e2e;
    }
    
    .email-card.low {
        border-left-color: #38a169;
    }
    
    .priority-badge {
        display: inline-block;
        padding: 4px 12px;
        border-radius: 20px;
        font-size: 0.75rem;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 0.5px;
    }
    
    .badge-critical {
        background: #fed7d7;
        color: #c53030;
    }
    
    .badge-high {
        background: #feebc8;
        color: #c05621;
    }
    
    .badge-medium {
        background: #fefcbf;
        color: #b7791f;
    }
    
    .badge-low {
        background: #c6f6d5;
        color: #276749;
    }
    
    .metric-card {
        background: white;
        border-radius: 16px;
        padding: 1.5rem;
        text-align: center;
        box-shadow: 0 4px 20px rgba(0, 0, 0, 0.08);
    }
    
    .stButton>button {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        color: white;
        border: none;
        border-radius: 12px;
        padding: 0.75rem 2rem;
        font-weight: 600;
        transition: all 0.3s ease;
    }
    
    .stButton>button:hover {
        transform: translateY(-2px);
        box-shadow: 0 8px 25px rgba(102, 126, 234, 0.4);
    }
    
    .stTextInput>div>div>input, .stNumberInput>div>div>input {
        border-radius: 12px;
        border: 2px solid #e2e8f0;
        padding: 0.75rem 1rem;
    }
    
    .stTextInput>div>div>input:focus, .stNumberInput>div>div>input:focus {
        border-color: #667eea;
        box-shadow: 0 0 0 3px rgba(102, 126, 234, 0.1);
    }
    
    .success-message {
        background: linear-gradient(135deg, #c6f6d5 0%, #9ae6b4 100%);
        border-radius: 16px;
        padding: 1.5rem;
        text-align: center;
        color: #22543d;
    }
    
    .info-box {
        background: linear-gradient(135deg, #bee3f8 0%, #90cdf4 100%);
        border-radius: 16px;
        padding: 1rem 1.5rem;
        color: #2a4365;
        margin-bottom: 1rem;
    }
    
    .stDataFrame {
        border-radius: 16px;
        overflow: hidden;
    }
    
    h1 {
        color: #2d3748;
        font-weight: 700;
        margin-bottom: 0.5rem;
    }
    
    h2 {
        color: #4a5568;
        font-weight: 600;
        margin-bottom: 1.5rem;
    }
    
    h3 {
        color: #2d3748;
        font-weight: 600;
        margin-bottom: 1rem;
    }
    
    .stExpander {
        border-radius: 12px;
        border: 1px solid #e2e8f0;
    }
</style>
""", unsafe_allow_html=True)

# ── API Configuration ───────────────────────────────────────────────────────

API_BASE_URL = "http://localhost:8000"

def api_get(endpoint, params=None):
    try:
        response = requests.get(f"{API_BASE_URL}{endpoint}", params=params, timeout=30)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        st.error(f"API Error: {str(e)}")
        return None

def api_post(endpoint, data=None, files=None):
    try:
        if files:
            response = requests.post(f"{API_BASE_URL}{endpoint}", files=files, timeout=30)
        else:
            response = requests.post(f"{API_BASE_URL}{endpoint}", json=data, timeout=30)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        st.error(f"API Error: {str(e)}")
        return None

def api_put(endpoint, data):
    try:
        response = requests.put(f"{API_BASE_URL}{endpoint}", json=data, timeout=30)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        st.error(f"API Error: {str(e)}")
        return None

def api_delete(endpoint):
    try:
        response = requests.delete(f"{API_BASE_URL}{endpoint}", timeout=30)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        st.error(f"API Error: {str(e)}")
        return None

# ── Header ────────────────────────────────────────────────────────────────────

st.markdown("<h1 style='text-align: center;'>📧 Email Compliance System</h1>", unsafe_allow_html=True)
st.markdown("<p style='text-align: center; color: #718096; font-size: 1.1rem;'>AI-Powered Compliance Monitoring System</p>", unsafe_allow_html=True)
st.markdown("<br>", unsafe_allow_html=True)

# ── Main Tabs ─────────────────────────────────────────────────────────────────

tab1, tab2, tab3, tab4 = st.tabs([
    "📤 Upload CSV", 
    "⚖️ Priority Matrix", 
    "🚨 Non-Compliant Emails", 
    "👤 Human Approval"
])

# ── Tab 1: Upload CSV ─────────────────────────────────────────────────────────

with tab1:
    st.markdown("<h2>Upload Email CSV for Analysis</h2>", unsafe_allow_html=True)
    
    col1, col2 = st.columns([2, 1])
    
    with col1:
        st.markdown("""
        <div class='info-box'>
            <strong>📋 CSV Format Required:</strong><br>
            Columns: <code>email_id</code>, <code>subject</code>, <code>sender</code>, <code>recipient</code>, <code>body</code>, <code>metadata</code> (optional)
        </div>
        """, unsafe_allow_html=True)
        
        uploaded_file = st.file_uploader(
            "Choose a CSV file",
            type=['csv'],
            help="Upload a CSV file containing emails to be analyzed"
        )
        
        if uploaded_file is not None:
            try:
                df = pd.read_csv(uploaded_file)
                st.success(f"✅ File loaded: {len(df)} emails found")
                
                with st.expander("Preview Data"):
                    st.dataframe(df.head(10), use_container_width=True)
                
                if st.button("🚀 Start Analysis", type="primary", use_container_width=True):
                    with st.spinner("Uploading and processing..."):
                        # Reset file pointer
                        uploaded_file.seek(0)
                        files = {"file": (uploaded_file.name, uploaded_file, "text/csv")}
                        response = api_post("/analyze/csv", files=files)
                        
                        if response and response.get("status") == "ok":
                            st.markdown(f"""
                            <div class='success-message'>
                                <h3>✅ Upload Successful!</h3>
                                <p>{response.get('message', 'Emails are being processed in the background.')}</p>
                                <p><strong>Filename:</strong> {response.get('filename', uploaded_file.name)}</p>
                                <br>
                                <p>⏱️ <strong>Next Steps:</strong></p>
                                <p>Check the <strong>🚨 Non-Compliant Emails</strong> and <strong>👤 Human Approval</strong> tabs after a few minutes to see the results.</p>
                            </div>
                            """, unsafe_allow_html=True)
                        else:
                            st.error("Failed to upload file. Please try again.")
            except Exception as e:
                st.error(f"Error reading CSV: {str(e)}")
    
    with col2:
        st.markdown("""
        <div class='upload-card'>
            <h3>📊 Processing Flow</h3>
            <ol style='line-height: 2;'>
                <li>Upload CSV file</li>
                <li>System validates format</li>
                <li>Emails processed in background</li>
                <li>Compliant emails discarded</li>
                <li>Non-compliant stored by priority</li>
                <li>View results in other tabs</li>
            </ol>
        </div>
        
        <div class='upload-card' style='margin-top: 1rem;'>
            <h3>🎯 Storage Rules</h3>
            <p><span class='priority-badge badge-low'>Compliant</span> Discarded</p>
            <p><span class='priority-badge badge-medium'>Priority &lt; 5</span> Human Approval</p>
            <p><span class='priority-badge badge-critical'>Priority ≥ 5</span> Non-Compliant</p>
        </div>
        """, unsafe_allow_html=True)

# ── Tab 2: Priority Matrix ────────────────────────────────────────────────────

with tab2:
    st.markdown("<h2>⚖️ Priority Matrix Configuration</h2>", unsafe_allow_html=True)
    
    # Fetch current matrix
    matrix_data = api_get("/matrix")
    
    if matrix_data:
        col1, col2 = st.columns([1, 1])
        
        with col1:
            st.markdown("<h3>Current Weights</h3>", unsafe_allow_html=True)
            st.markdown("<p style='color: #718096;'>Adjust violation category weights. Higher values = higher priority.</p>", unsafe_allow_html=True)
            
            updated_weights = {}
            
            for category, weight in matrix_data.items():
                updated_weights[category] = st.number_input(
                    f"{category}",
                    min_value=0.0,
                    max_value=10.0,
                    value=float(weight),
                    step=0.5,
                    help=f"Current weight: {weight}"
                )
            
            if st.button("💾 Save Changes", type="primary", use_container_width=True):
                response = api_put("/matrix", {"weights": updated_weights})
                if response:
                    st.success("✅ Priority matrix updated successfully!")
                    st.balloons()
                    st.rerun()
        
        with col2:
            st.markdown("<h3>📊 Weight Distribution</h3>", unsafe_allow_html=True)
            
            chart_data = pd.DataFrame({
                'Category': list(matrix_data.keys()),
                'Weight': list(matrix_data.values())
            })
            
            st.bar_chart(chart_data.set_index('Category'), use_container_width=True)
            
            st.markdown("""
            <div class='upload-card'>
                <h4>📖 Priority Thresholds</h4>
                <table style='width: 100%; border-collapse: collapse;'>
                    <tr style='border-bottom: 1px solid #e2e8f0;'>
                        <td style='padding: 8px;'><span class='priority-badge badge-critical'>CRITICAL</span></td>
                        <td style='padding: 8px; text-align: right;'>≥ 8.0</td>
                    </tr>
                    <tr style='border-bottom: 1px solid #e2e8f0;'>
                        <td style='padding: 8px;'><span class='priority-badge badge-high'>HIGH</span></td>
                        <td style='padding: 8px; text-align: right;'>≥ 5.0</td>
                    </tr>
                    <tr style='border-bottom: 1px solid #e2e8f0;'>
                        <td style='padding: 8px;'><span class='priority-badge badge-medium'>MEDIUM</span></td>
                        <td style='padding: 8px; text-align: right;'>≥ 2.0</td>
                    </tr>
                    <tr>
                        <td style='padding: 8px;'><span class='priority-badge badge-low'>LOW</span></td>
                        <td style='padding: 8px; text-align: right;'>&lt; 2.0</td>
                    </tr>
                </table>
            </div>
            """, unsafe_allow_html=True)

# ── Tab 3: Non-Compliant Emails ───────────────────────────────────────────────

with tab3:
    st.markdown("<h2>🚨 Non-Compliant Emails</h2>", unsafe_allow_html=True)
    st.markdown("<p style='color: #718096;'>High-priority violations (Priority Score ≥ 5.0) that require immediate attention.</p>", unsafe_allow_html=True)
    
    limit = st.slider("Number of emails to display", 10, 500, 100, 10)
    
    if st.button("🔄 Refresh Data", type="secondary"):
        st.rerun()
    
    emails_data = api_get("/emails/non-compliant", params={"limit": limit})
    
    if emails_data:
        count = emails_data.get("count", 0)
        emails = emails_data.get("emails", [])
        
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Total Non-Compliant", count)
        with col2:
            st.metric("Priority Threshold", "≥ 5.0")
        with col3:
            st.metric("Status", "Action Required")
        
        st.markdown("<br>", unsafe_allow_html=True)
        
        if not emails:
            st.info("📭 No non-compliant emails found. Check back later or upload new data.")
        else:
            for email in emails:
                metadata = email.get("metadata", {})
                priority_level = metadata.get("priority_level", "LOW")
                priority_score = metadata.get("priority_score", 0)
                
                priority_class = priority_level.lower()
                badge_class = f"badge-{priority_class}"
                
                email_id = email.get("id") or metadata.get("email_id", "unknown")

                # Two column layout: email card on left, buttons on right
                left_col, right_col = st.columns([4, 1])

                with left_col:
                    with st.container():
                        st.markdown(f"""
                        <div class='email-card {priority_class}'>
                            <div style='display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px;'>
                                <span class='priority-badge {badge_class}'>{priority_level}</span>
                                <span style='color: #718096; font-size: 0.9rem;'>Score: {priority_score:.2f}</span>
                            </div>
                            <h4>{metadata.get('subject', 'No Subject')}</h4>
                            <p style='color: #718096; margin: 8px 0;'>
                                <strong>From:</strong> {metadata.get('sender', 'Unknown')} |
                                <strong>To:</strong> {metadata.get('recipient', 'Unknown')}
                            </p>
                            <p style='color: #4a5568; margin: 12px 0;'><strong>Summary:</strong> {metadata.get('summary', 'No summary available')}</p>
                            <p style='color: #e53e3e; margin: 12px 0;'><strong>Recommended Action:</strong> {metadata.get('recommended_action', 'No action specified')}</p>
                        </div>
                        """, unsafe_allow_html=True)

                        with st.expander("View Full Email Content"):
                            st.text(email.get("document", "No content"))

                            if metadata.get("classifications"):
                                st.markdown("**Classifications:**")
                                try:
                                    classifications = json.loads(metadata["classifications"])
                                    for cls in classifications:
                                        st.markdown(f"- **{cls.get('category', 'Unknown')}** (Confidence: {cls.get('confidence', 0):.2f})")
                                        if cls.get('evidence'):
                                            st.caption(f"  Evidence: {cls['evidence']}")
                                except:
                                    st.text(metadata["classifications"])

                with right_col:
                    st.markdown("<br>", unsafe_allow_html=True)
                    if st.button("✅ Discard\n(Action Taken)", key=f"discard_non_compliant_{email_id}", type="secondary", use_container_width=True):
                        with st.spinner("Deleting..."):
                            response = api_delete(f"/emails/non-compliant/{email_id}")
                            if response and response.get("status") == "ok":
                                st.success("✅ Discarded!")
                                st.rerun()
                            else:
                                st.error("Failed to discard.")
    else:
        st.error("Failed to fetch non-compliant emails. Is the API running?")

# ── Tab 4: Human Approval ────────────────────────────────────────────────────

with tab4:
    st.markdown("<h2>👤 Emails Requiring Human Approval</h2>", unsafe_allow_html=True)
    st.markdown("<p style='color: #718096;'>Lower-priority violations (Priority Score < 5.0) that need manual review.</p>", unsafe_allow_html=True)
    
    limit = st.slider("Number of emails to display", 10, 500, 100, 10, key="human_approval_limit")
    
    if st.button("🔄 Refresh Data", type="secondary", key="human_approval_refresh"):
        st.rerun()
    
    emails_data = api_get("/emails/human-approval", params={"limit": limit})
    
    if emails_data:
        count = emails_data.get("count", 0)
        emails = emails_data.get("emails", [])
        
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Pending Review", count)
        with col2:
            st.metric("Priority Threshold", "< 5.0")
        with col3:
            st.metric("Status", "Review Required")
        
        st.markdown("<br>", unsafe_allow_html=True)
        
        if not emails:
            st.info("📭 No emails pending human approval. Check back later or upload new data.")
        else:
            for email in emails:
                metadata = email.get("metadata", {})
                priority_level = metadata.get("priority_level", "LOW")
                priority_score = metadata.get("priority_score", 0)
                
                priority_class = priority_level.lower()
                badge_class = f"badge-{priority_class}"
                
                email_id = email.get("id") or metadata.get("email_id", "unknown")

                # Two column layout: email card on left, buttons on right
                left_col, right_col = st.columns([4, 1])

                with left_col:
                    with st.container():
                        st.markdown(f"""
                        <div class='email-card {priority_class}'>
                            <div style='display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px;'>
                                <span class='priority-badge {badge_class}'>{priority_level}</span>
                                <span style='color: #718096; font-size: 0.9rem;'>Score: {priority_score:.2f}</span>
                            </div>
                            <h4>{metadata.get('subject', 'No Subject')}</h4>
                            <p style='color: #718096; margin: 8px 0;'>
                                <strong>From:</strong> {metadata.get('sender', 'Unknown')} |
                                <strong>To:</strong> {metadata.get('recipient', 'Unknown')}
                            </p>
                            <p style='color: #4a5568; margin: 12px 0;'><strong>Summary:</strong> {metadata.get('summary', 'No summary available')}</p>
                            <p style='color: #d69e2e; margin: 12px 0;'><strong>Recommended Action:</strong> {metadata.get('recommended_action', 'No action specified')}</p>
                        </div>
                        """, unsafe_allow_html=True)

                        with st.expander("View Full Email Content"):
                            st.text(email.get("document", "No content"))

                            if metadata.get("classifications"):
                                st.markdown("**Classifications:**")
                                try:
                                    classifications = json.loads(metadata["classifications"])
                                    for cls in classifications:
                                        st.markdown(f"- **{cls.get('category', 'Unknown')}** (Confidence: {cls.get('confidence', 0):.2f})")
                                        if cls.get('evidence'):
                                            st.caption(f"  Evidence: {cls['evidence']}")
                                except:
                                    st.text(metadata["classifications"])

                with right_col:
                    st.markdown("<br>", unsafe_allow_html=True)

                    # Mark as Non-Compliant button
                    if st.button("🚨 Mark as\nNon-Compliant", key=f"move_non_compliant_{email_id}", type="primary", use_container_width=True):
                        with st.spinner("Moving..."):
                            response = api_post(f"/emails/human-approval/{email_id}/move-to-non-compliant")
                            if response and response.get("status") == "ok":
                                st.success("✅ Moved!")
                                st.rerun()
                            else:
                                st.error("Failed to move.")

                    st.markdown("<br>", unsafe_allow_html=True)

                    # Discard as Compliant button
                    if st.button("✅ Discard\n(Compliant)", key=f"discard_human_{email_id}", type="secondary", use_container_width=True):
                        with st.spinner("Deleting..."):
                            response = api_delete(f"/emails/human-approval/{email_id}")
                            if response and response.get("status") == "ok":
                                st.success("✅ Discarded!")
                                st.rerun()
                            else:
                                st.error("Failed to discard.")
    else:
        st.error("Failed to fetch human approval emails. Is the API running?")

# ── Footer ────────────────────────────────────────────────────────────────────

st.markdown("<br><br>", unsafe_allow_html=True)
st.markdown("""
<div style='text-align: center; color: #a0aec0; padding: 2rem; border-top: 1px solid #e2e8f0;'>
    <p>Email Compliance System v1.0.0 | Powered by LangGraph & Azure OpenAI</p>
    <p style='font-size: 0.85rem;'>© 2024 Compliance Team. All rights reserved.</p>
</div>
""", unsafe_allow_html=True)
