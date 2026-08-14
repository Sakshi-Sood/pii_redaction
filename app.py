import os
import tempfile
import streamlit as st
from docx import Document
from redactor import process_document

# Page configuration
st.set_page_config(
    page_title="PII Redaction System",
    page_icon="🛡️",
    layout="centered"
)

# Header
st.title("🛡️ PII Redaction System")
st.write("Upload a Word document (`.docx`) to automatically detect and redact sensitive Personally Identifiable Information (PII) including names, emails, phone numbers, addresses, and organizations.")

st.divider()

# Upload section
default_doc_path = "input/Red Herring Prospectus.docx"
uploaded_file = st.file_uploader("Choose a `.docx` file", type=["docx"])
use_sample = st.checkbox("Or use the default sample (`Red Herring Prospectus.docx`)", value=(uploaded_file is None and os.path.exists(default_doc_path)))

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
    st.info(f"📄 Loaded: **{input_filename}** ({len(doc_bytes) / 1024:.1f} KB)")
    
    if st.button("🚀 Redact Document", type="primary", use_container_width=True):
        with st.spinner("Detecting PII and generating redacted document..."):
            # Write uploaded bytes to a temp input file
            with tempfile.NamedTemporaryFile(suffix=".docx", delete=False) as tmp_in:
                tmp_in.write(doc_bytes)
                tmp_in_path = tmp_in.name
                
            with tempfile.NamedTemporaryFile(suffix=".docx", delete=False) as tmp_out:
                tmp_out_path = tmp_out.name

            try:
                # Run redaction pipeline
                process_document(tmp_in_path, tmp_out_path)
                
                with open(tmp_out_path, "rb") as f:
                    redacted_bytes = f.read()
                    
                st.success("✅ Document redacted successfully!")
                
                # Download button
                output_name = f"redacted_{input_filename}"
                st.download_button(
                    label=f"📥 Download {output_name}",
                    data=redacted_bytes,
                    file_name=output_name,
                    mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                    type="primary",
                    use_container_width=True
                )
            except Exception as e:
                st.error(f"Error during redaction: {e}")
            finally:
                # Clean up temporary files
                for p in [tmp_in_path, tmp_out_path]:
                    if os.path.exists(p):
                        try:
                            os.remove(p)
                        except Exception:
                            pass
else:
    st.info("👆 Please upload a `.docx` file or select the sample document above to get started.")

st.divider()
st.caption("🔒 **Security & Privacy**: All processing runs locally in memory. Legal identity of the filing subject is preserved.")
