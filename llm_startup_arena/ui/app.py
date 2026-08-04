import streamlit as st
from httpx import HTTPError
from ollama import ResponseError
from pydantic import ValidationError

from llm_startup_arena.config import AppConfig
from llm_startup_arena.domain import Company, GameState
from llm_startup_arena.llm.ollama_provider import OllamaProvider


def build_demo_state(model: str, *, starting_cash: int = 500_000) -> GameState:
    company = Company(
        id="nova",
        name="Nova",
        model=model,
        cash=starting_cash,
        product_score=20,
        reputation=50,
    )
    return GameState(round_number=1, companies=[company], clients=[])


def render_connection_test(config: AppConfig) -> None:
    st.subheader("Ollama connection test")
    selected_model = st.selectbox("Model", config.models)

    if not st.button("Generate test decision", type="primary"):
        return

    provider = OllamaProvider(base_url=config.ollama_base_url)
    state = build_demo_state(
        selected_model,
        starting_cash=config.game.starting_cash,
    )

    try:
        with st.spinner(f"Waiting for {selected_model}..."):
            decision = provider.generate_decision(
                model=selected_model,
                company_id="nova",
                state=state,
            )
    except (HTTPError, ResponseError, ValidationError, ValueError) as error:
        st.error(f"Ollama call failed: {error}")
        return

    st.success(f"{selected_model} returned a valid company decision.")
    st.json(decision.model_dump())


def run() -> None:
    config = AppConfig.from_env()
    st.set_page_config(page_title="LLM Startup Arena", page_icon="🚀", layout="wide")
    st.title("LLM Startup Arena")
    st.caption("Four local LLMs. Ten rounds. One winning startup.")
    render_connection_test(config)
