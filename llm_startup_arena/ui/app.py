from html import escape

import streamlit as st
from httpx import HTTPError
from ollama import ResponseError
from pydantic import ValidationError

from llm_startup_arena.config import AppConfig
from llm_startup_arena.domain import Company, GameState
from llm_startup_arena.engine import GameFactory
from llm_startup_arena.llm.ollama_provider import OllamaProvider

from .session import GameSession

COMPANY_COLORS = {
    "nova": ("#7C5CFC", "#A78BFA"),
    "orbit": ("#00B8A9", "#2DD4BF"),
    "pixel": ("#F59E0B", "#FBBF24"),
    "apex": ("#EF476F", "#FB7185"),
}


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


def inject_styles() -> None:
    st.markdown(
        """
        <style>
        .stApp { background: #0b1020; }
        .block-container { max-width: 1400px; padding-top: 2.5rem; }
        .arena-header {
            padding: 1.5rem 1.75rem; margin-bottom: 1.5rem;
            border: 1px solid #25304a; border-radius: 18px;
            background: linear-gradient(135deg, #151d35 0%, #10162a 100%);
        }
        .arena-kicker { color: #9ca8c7; font-size: .82rem; letter-spacing: .12em; }
        .arena-title { color: #f8fafc; font-size: 2.15rem; font-weight: 750; margin: .2rem 0; }
        .arena-subtitle { color: #9ca8c7; margin: 0; }
        .company-card {
            min-height: 310px; padding: 1.35rem; border-radius: 18px;
            border: 1px solid #29334d; background: #131a2d;
            box-shadow: 0 12px 32px rgba(0, 0, 0, .2);
        }
        .company-accent { height: 5px; border-radius: 10px; margin-bottom: 1.2rem; }
        .company-name { color: #f8fafc; font-size: 1.25rem; font-weight: 700; }
        .model-name { color: #8f9ab7; font-size: .82rem; margin: .25rem 0 1.25rem; }
        .cash { color: #f8fafc; font-size: 1.75rem; font-weight: 750; }
        .cash-label { color: #7f8aa6; font-size: .72rem; letter-spacing: .09em; }
        .card-divider { border-top: 1px solid #29334d; margin: 1.15rem 0; }
        .metric-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: .6rem; }
        .metric-value { color: #e8ecf7; font-size: 1.08rem; font-weight: 650; }
        .metric-label { color: #7f8aa6; font-size: .7rem; }
        .status-pill {
            display: inline-block; padding: .3rem .65rem; margin-top: 1.25rem;
            border-radius: 999px; font-size: .72rem; font-weight: 650;
        }
        .round-note { color: #7f8aa6; font-size: .82rem; margin-top: .5rem; }
        </style>
        """,
        unsafe_allow_html=True,
    )


def render_company_card(
    company: Company,
    accent: str,
    highlight: str,
    *,
    is_finished: bool,
) -> None:
    status = "FINISHED" if is_finished else "READY"
    st.markdown(
        f"""
        <div class="company-card">
            <div class="company-accent" style="background:{accent}"></div>
            <div class="company-name">{escape(company.name)}</div>
            <div class="model-name">{escape(company.model)}</div>
            <div class="cash">${company.cash:,.0f}</div>
            <div class="cash-label">AVAILABLE CASH</div>
            <div class="card-divider"></div>
            <div class="metric-grid">
                <div><div class="metric-value">{len(company.employees)}</div><div class="metric-label">EMPLOYEES</div></div>
                <div><div class="metric-value">{len(company.client_ids)}</div><div class="metric-label">CLIENTS</div></div>
                <div><div class="metric-value">{company.product_score}</div><div class="metric-label">PRODUCT</div></div>
            </div>
            <div class="status-pill" style="color:{highlight}; background:{accent}22">{status}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def round_label(state: GameState, total_rounds: int) -> str:
    if state.round_number >= total_rounds:
        return f"GAME COMPLETE · {total_rounds} ROUNDS"
    if state.round_number == 0:
        return f"READY FOR ROUND 1 OF {total_rounds}"
    return f"ROUND {state.round_number} COMPLETE · NEXT: {state.round_number + 1} OF {total_rounds}"


def render_round_controls(session: GameSession, config: AppConfig) -> None:
    progress_column, next_column, reset_column = st.columns([5, 1.4, 1.2])
    with progress_column:
        st.progress(session.state.round_number / config.game.total_rounds)
        st.markdown(
            '<div class="round-note">Round progression only; LLM decisions arrive in stage 3.</div>',
            unsafe_allow_html=True,
        )
    with next_column:
        if st.button(
            "Run next round",
            type="primary",
            disabled=session.is_finished,
            use_container_width=True,
        ):
            session.advance_round()
            st.rerun()
    with reset_column:
        if st.button("New game", use_container_width=True):
            session.new_game()
            st.rerun()


def render_arena(session: GameSession, config: AppConfig) -> None:
    state = session.state
    st.markdown(
        f"""
        <div class="arena-header">
            <div class="arena-kicker">{round_label(state, config.game.total_rounds)}</div>
            <div class="arena-title">Startup Arena</div>
            <p class="arena-subtitle">Four local models begin with equal resources. Strategy decides what happens next.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    render_round_controls(session, config)
    columns = st.columns(config.game.company_count, gap="medium")
    for column, company in zip(columns, state.companies, strict=True):
        accent, highlight = COMPANY_COLORS[company.id]
        with column:
            render_company_card(
                company,
                accent,
                highlight,
                is_finished=session.is_finished,
            )


def render_connection_test(config: AppConfig) -> None:
    st.subheader("Ollama connection test")
    selected_model = st.selectbox("Model", config.models)
    if not st.button("Generate test decision", type="primary"):
        return

    provider = OllamaProvider(base_url=config.ollama_base_url)
    state = build_demo_state(selected_model, starting_cash=config.game.starting_cash)
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
    inject_styles()
    factory = GameFactory(config.game, config.models)
    session = GameSession(st.session_state, factory, config.game.total_rounds)
    render_arena(session, config)

    with st.expander("Developer tools"):
        render_connection_test(config)
