"""
Entrypoint for the Hugging Face Space. The Gradio SDK runs this file
directly and manages host/port binding itself via environment variables
it sets before launch, so no manual server_name/server_port wiring is
needed here - unlike the Render deploy this used to target.
"""

from app.ui import demo

if __name__ == "__main__":
    demo.launch()
