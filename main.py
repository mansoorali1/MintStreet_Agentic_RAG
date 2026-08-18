"""
Entrypoint for the container. HF Spaces (Docker SDK) expects the app to
listen on 0.0.0.0:7860, so that's set explicitly rather than relying on
Gradio's defaults. share=True and debug=True from the notebook are gone -
those were Kaggle/Colab conveniences and have no place in a production
container (share=True tries to tunnel through Gradio's own servers, which
you don't want or need once this is actually deployed somewhere).
"""
import os

from app.ui import demo

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 7860))
    demo.launch(server_name="0.0.0.0", server_port=port, show_error=True)
