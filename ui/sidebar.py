import streamlit as st

AI_MODE_OFF = "off"
AI_MODE_LOCAL = "local"
AI_MODE_CLOUD = "cloud"


def init_sidebar_state() -> None:
    # AI mode
    st.session_state.setdefault("ai_mode", AI_MODE_OFF)

    # Local (Ollama)
    st.session_state.setdefault("ollama_base_url", "http://localhost:11434")
    st.session_state.setdefault("ollama_model", "llama3.1:8b")

    # Cloud (OpenAI)
    st.session_state.setdefault("cloud_provider", "openai")
    st.session_state.setdefault("openai_model", "gpt-4.1-mini")
    st.session_state.setdefault("openai_api_key", "")


def render_sidebar() -> None:
    init_sidebar_state()

    with st.sidebar:
        st.subheader("AI")

        modes = [AI_MODE_OFF, AI_MODE_LOCAL, AI_MODE_CLOUD]
        st.selectbox(
            "AI mode",
            modes,
            index=modes.index(st.session_state["ai_mode"]),
            key="ai_mode",
            help="Off uses deterministic parsing only. Local uses Ollama. Cloud uses a hosted provider.",
        )

        if st.session_state["ai_mode"] == AI_MODE_LOCAL:
            st.caption("Local LLM via Ollama (works with SSH tunnel too).")
            st.text_input(
                "Ollama URL",
                value=st.session_state["ollama_base_url"],
                key="ollama_base_url",
                help="Example: http://localhost:11434",
            )
            st.text_input(
                "Model",
                value=st.session_state["ollama_model"],
                key="ollama_model",
                help="Example: llama3.1:8b",
            )

        if st.session_state["ai_mode"] == AI_MODE_CLOUD:
            st.warning("Cloud AI sends JD and resume text to the provider and may incur charges.")
            st.selectbox("Provider", ["openai"], key="cloud_provider")
            st.text_input("Model", value=st.session_state["openai_model"], key="openai_model")
            st.text_input(
                "API Key",
                value=st.session_state["openai_api_key"],
                key="openai_api_key",
                type="password",
            )
