import os
import tempfile
import streamlit as st
from docx import Document
from redactor import process_document

# Page configuration
st.set_page_config(
    page_title="PII Redaction System",
    layout="centered",
    initial_sidebar_state="collapsed"
)

# Minimalist Custom Styling
st.markdown("""
<style>
    /* Global Typography & Background */
    html, body, [class*="css"] {
        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
        color: #1e293b;
    }
    
    /* Main container max width & padding */
    .block-container {
        max-width: 760px;
        padding-top: 2.5rem;
        padding-bottom: 3rem;
    }
    
    /* Headings */
    h1 {
        font-size: 1.85rem;
        font-weight: 600;
        letter-spacing: -0.02em;
        color: #0f172a;
        margin-bottom: 0.35rem;
    }
    
    /* Subtitle text */
    .subtitle {
        font-size: 0.95rem;
        color: #64748b;
        line-height: 1.5;
        margin-bottom: 1.5rem;
    }
    
    /* Card containers */
    .custom-card {
        background-color: #ffffff;
        border: 1px solid #e2e8f0;
        border-radius: 8px;
        padding: 1.25rem 1.5rem;
        margin-bottom: 1.25rem;
    }
    
    /* Button refinement */
    .stButton > button {
        border-radius: 6px;
        font-weight: 500;
        font-size: 0.9rem;
        padding: 0.5rem 1.25rem;
        border: 1px solid transparent;
        transition: all 0.15s ease-in-out;
    }
    
    .stDownloadButton > button {
        border-radius: 6px;
        font-weight: 500;
        font-size: 0.9rem;
        padding: 0.5rem 1.25rem;
    }
    
    /* File uploader container */
    [data-testid="stFileUploader"] {
        border: 1px dashed #cbd5e1;
        border-radius: 6px;
        padding: 0.5rem;
        background: #f8fafc;
    }
    
    /* Divider */
    hr {
        border: 0;
        height: 1px;
        background: #e2e8f0;
        margin: 1.5rem 0;
    }
    
    /* Footer text */
    .footer-text {
        font-size: 0.8rem;
        color: #94a3b8;
        text-align: center;
        margin-top: 2rem;
    }
</style>
""", unsafe_allow_html=True)

# App Header
st.title("PII Redaction System")
st.markdown('<p class="subtitle">Securely identify and pseudonymize Personally Identifiable Information in Word (.docx) documents with full formatting preservation.</p>', unsafe_allow_html=True)

# Upload Card
default_doc_path = "input/Red Herring Prospectus.docx"
uploaded_file = st.file_uploader("Upload Word Document (.docx)", type=["docx"], label_visibility="collapsed")
use_sample = st.checkbox("Use sample document (Red Herring Prospectus.docx)", value=(uploaded_file is None and os.path.exists(default_doc_path)))

doc_bytes = None
input_filename = "document.docx"

if uploaded_file is not None:
    doc_bytes = uploaded_file.read()
    input_filename = uploaded_file.name
elif use_sample and os.path.exists(default_doc_path):
    with open(default_doc_path, "rb") as f:
        doc_bytes = f.read()
    input_filename = "Red_Herring_Prospectus.docx"

if doc_bytes is not None:
    file_size_kb = len(doc_bytes) / 1024
    st.markdown(f"**Loaded File:** `{input_filename}` &nbsp;|&nbsp; Size: `{file_size_kb:.1f} KB`")
    
    col_act1, col_act2 = st.columns([1, 1])
    
    with col_act1:
        start_redaction = st.button("Process & Redact", type="primary", use_container_width=True)

    if start_redaction:
        with st.spinner("Processing document and redacting entities..."):
            with tempfile.NamedTemporaryFile(suffix=".docx", delete=False) as tmp_in:
                tmp_in.write(doc_bytes)
                tmp_in_path = tmp_in.name
                
            with tempfile.NamedTemporaryFile(suffix=".docx", delete=False) as tmp_out:
                tmp_out_path = tmp_out.name

            try:
                process_document(tmp_in_path, tmp_out_path)
                
                with open(tmp_out_path, "rb") as f:
                    redacted_bytes = f.read()
                    
                st.success("Document redaction complete.")
                
                output_name = f"redacted_{input_filename}"
                st.download_button(
                    label=f"Download {output_name}",
                    data=redacted_bytes,
                    file_name=output_name,
                    mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                    type="secondary",
                    use_container_width=True
                )
            except Exception as e:
                st.error(f"Processing error: {e}")
            finally:
                for p in [tmp_in_path, tmp_out_path]:
                    if os.path.exists(p):
                        try:
                            os.remove(p)
                        except Exception:
                            pass
else:
    st.info("Select or upload a .docx file above to proceed.")

st.markdown('<div class="footer-text">Local execution. Issuer corporate identities are preserved.</div>', unsafe_allow_html=True)
