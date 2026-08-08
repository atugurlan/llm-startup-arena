from collections.abc import Callable, Mapping
from html import escape

import streamlit as st
from httpx import HTTPError
from ollama import ResponseError
from pydantic import ValidationError
from streamlit.delta_generator import DeltaGenerator

from llm_startup_arena.config import AppConfig
from llm_startup_arena.domain import Company, GameState
from llm_startup_arena.engine import GameFactory, RoundResolver
from llm_startup_arena.llm import CompanyDecision, DecisionCoordinator, RoundDecisionRecord
from llm_startup_arena.llm.ollama_provider import OllamaProvider

from .session import GameSession

COMPANY_COLORS = {
    "nova": ("#7C5CFC", "#A78BFA"),
    "orbit": ("#00B8A9", "#2DD4BF"),
    "pixel": ("#F59E0B", "#FBBF24"),
    "apex": ("#EF476F", "#FB7185"),
}


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
        .metric-grid { display: grid; grid-template-columns: repeat(4, 1fr); gap: .6rem; }
        .metric-value { color: #e8ecf7; font-size: 1.08rem; font-weight: 650; }
        .metric-label { color: #7f8aa6; font-size: .7rem; }
        .status-pill {
            display: inline-block; padding: .3rem .65rem; margin-top: 1.25rem;
            border-radius: 999px; font-size: .72rem; font-weight: 650;
        }
        .round-note { color: #7f8aa6; font-size: .82rem; margin-top: .5rem; }
        .model-progress { color: #aeb8d4; font-size: .82rem; margin-top: .5rem; }
        .decision-box {
            height: 310px; margin-top: .75rem; padding: .85rem 1rem;
            border: 1px solid #29334d; border-radius: 14px; background: #101627;
            overflow-y: auto; box-sizing: border-box;
        }
        .decision-label { color: #7f8aa6; font-size: .68rem; letter-spacing: .08em; }
        .decision-strategy { color: #e8ecf7; font-size: .88rem; margin: .3rem 0 .65rem; }
        .decision-budget { color: #9ca8c7; font-size: .75rem; line-height: 1.45; }
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
                <div><div class="metric-value">{company.reputation}</div><div class="metric-label">REPUTATION</div></div>
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


def run_next_round(
    session: GameSession,
    coordinator: DecisionCoordinator,
    resolver: RoundResolver,
    on_decision: Callable[[str, CompanyDecision], None] | None = None,
    on_error: Callable[[str, str], None] | None = None,
    on_model_start: Callable[[str], None] | None = None,
) -> RoundDecisionRecord:
    """Collect and store decisions before advancing the session round."""
    record = coordinator.collect(
        session.state,
        on_decision=on_decision,
        on_error=on_error,
        on_model_start=on_model_start,
    )
    if not record.decisions:
        raise ValueError("All four models failed. The round was not advanced.")
    session.resolve_round(record, resolver)
    return record


def render_round_controls(
    session: GameSession,
    coordinator: DecisionCoordinator,
    resolver: RoundResolver,
    config: AppConfig,
    decision_slots: dict[str, DeltaGenerator],
) -> None:
    progress_column, next_column, reset_column = st.columns([5, 1.4, 1.2])
    with progress_column:
        st.progress(session.state.round_number / config.game.total_rounds)
        progress_message = st.empty()
        progress_message.markdown(
            '<div class="round-note">Each round requests one decision from every local model.</div>',
            unsafe_allow_html=True,
        )
    with next_column:
        if st.button(
            "Run next round",
            type="primary",
            disabled=session.is_finished,
            use_container_width=True,
        ):
            companies = {company.id: company for company in session.state.companies}
            for slot in decision_slots.values():
                slot.empty()

            def show_decision(company_id: str, decision: CompanyDecision) -> None:
                render_decision(decision_slots[company_id], decision, companies=companies)
                progress_message.markdown(
                    f'<div class="model-progress">{escape(companies[company_id].name)} decided.</div>',
                    unsafe_allow_html=True,
                )

            def show_error(company_id: str, message: str) -> None:
                render_decision_error(decision_slots[company_id], message)
                progress_message.markdown(
                    f'<div class="model-progress">{escape(companies[company_id].name)} was rejected. Continuing...</div>',
                    unsafe_allow_html=True,
                )

            def show_model_start(company_id: str) -> None:
                progress_message.markdown(
                    f'<div class="model-progress">Waiting for {escape(companies[company_id].name)}...</div>',
                    unsafe_allow_html=True,
                )

            try:
                run_next_round(
                    session,
                    coordinator,
                    resolver,
                    on_decision=show_decision,
                    on_error=show_error,
                    on_model_start=show_model_start,
                )
                progress_message.markdown(
                    '<div class="model-progress">All four decisions collected.</div>',
                    unsafe_allow_html=True,
                )
            except (HTTPError, ResponseError, ValidationError, ValueError) as error:
                progress_message.markdown(
                    '<div class="model-progress">Round failed.</div>',
                    unsafe_allow_html=True,
                )
                st.error(f"Round failed: {error}")
                return
            st.rerun()
    with reset_column:
        if st.button("New game", use_container_width=True):
            session.new_game()
            st.rerun()


def render_decision(
    slot: DeltaGenerator,
    decision: CompanyDecision,
    events: list[str] | None = None,
    companies: Mapping[str, Company] | None = None,
) -> None:
    allocations = {
        category: amount for category, amount in decision.budget.model_dump().items() if amount > 0
    }
    budget_text = " · ".join(
        f"{escape(category.title())}: ${amount:,.0f}" for category, amount in allocations.items()
    )
    targets = []
    if decision.target_candidate_ids:
        targets.append(f"Candidates: {', '.join(decision.target_candidate_ids)}")
    if decision.target_employee_ids:
        targets.append(f"Employees: {', '.join(decision.target_employee_ids)}")
    if decision.target_client_ids:
        targets.append(f"Clients: {', '.join(decision.target_client_ids)}")
    if decision.sabotage_action is not None:
        targets.append(f"Sabotage: {decision.sabotage_action.value}")
    if decision.target_company_id is not None:
        target_company = (companies or {}).get(decision.target_company_id)
        target_name = target_company.name if target_company else decision.target_company_id
        targets.append(f"Target: {target_name}")
    target_text = " · ".join(escape(target) for target in targets)
    event_text = "<br>".join(f"• {escape(event)}" for event in events or [])
    outcome = (
        f'<div class="decision-budget" style="margin-top:.55rem">{event_text}</div>'
        if event_text
        else ""
    )
    slot.markdown(
        f"""
        <div class="decision-box">
            <div class="decision-label">LATEST DECISION</div>
            <div class="decision-strategy">{escape(decision.strategy)}</div>
            <div class="decision-budget">{budget_text or "No budget allocated"}</div>
            <div class="decision-budget">{target_text}</div>
            {outcome}
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_decision_error(
    slot: DeltaGenerator,
    message: str,
    events: list[str] | None = None,
) -> None:
    event_text = "<br>".join(f"• {escape(event)}" for event in events or [])
    outcome = (
        f'<div class="decision-budget" style="margin-top:.55rem">{event_text}</div>'
        if event_text
        else ""
    )
    slot.markdown(
        f"""
        <div class="decision-box">
            <div class="decision-label">DECISION REJECTED</div>
            <div class="decision-strategy">{escape(message)}</div>
            <div class="decision-budget">Fallback: Hold · Budget: $0</div>
            {outcome}
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_company_grid(
    session: GameSession,
    config: AppConfig,
) -> dict[str, DeltaGenerator]:
    latest_decisions = session.latest_round.decisions if session.latest_round else {}
    latest_errors = session.latest_round.errors if session.latest_round else {}
    decision_slots = {}
    columns = st.columns(config.game.company_count, gap="medium")
    for column, company in zip(columns, session.state.companies, strict=True):
        accent, highlight = COMPANY_COLORS[company.id]
        with column:
            render_company_card(
                company,
                accent,
                highlight,
                is_finished=session.is_finished,
            )
            slot = st.empty()
            decision_slots[company.id] = slot
            if company.id in latest_decisions:
                render_decision(
                    slot,
                    latest_decisions[company.id],
                    session.state.last_round_events.get(company.id),
                    {company.id: company for company in session.state.companies},
                )
            elif company.id in latest_errors:
                render_decision_error(
                    slot,
                    latest_errors[company.id],
                    session.state.last_round_events.get(company.id),
                )
    return decision_slots


def render_talent_pool(state: GameState) -> None:
    with st.expander(f"Available talent · {len(state.available_candidates)} candidates"):
        st.dataframe(
            [
                {
                    "Candidate": candidate.name,
                    "Role": candidate.role.value.title(),
                    "Personality": candidate.personality.value.title(),
                    "Skill": candidate.skill,
                    "Salary / round": f"${candidate.salary:,}",
                }
                for candidate in state.available_candidates
            ],
            hide_index=True,
            use_container_width=True,
        )


def employee_roster_rows(state: GameState) -> list[dict[str, str | int]]:
    return [
        {
            "Company": company.name,
            "Employee": employee.name,
            "Role": employee.role.value.title(),
            "Personality": employee.personality.value.title(),
            "Skill": employee.skill,
            "Morale": employee.morale,
            "Loyalty": employee.loyalty,
            "Salary / round": f"${employee.salary:,}",
        }
        for company in state.companies
        for employee in company.employees
    ]


def render_employee_rosters(state: GameState) -> None:
    employee_count = sum(len(company.employees) for company in state.companies)
    with st.expander(f"Company teams · {employee_count} employees"):
        st.dataframe(
            employee_roster_rows(state),
            hide_index=True,
            use_container_width=True,
        )


def render_arena(
    session: GameSession,
    coordinator: DecisionCoordinator,
    resolver: RoundResolver,
    config: AppConfig,
) -> None:
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

    render_talent_pool(state)
    render_employee_rosters(state)
    controls = st.container()
    decision_slots = render_company_grid(session, config)
    with controls:
        render_round_controls(session, coordinator, resolver, config, decision_slots)


def run() -> None:
    config = AppConfig.from_env()
    st.set_page_config(page_title="LLM Startup Arena", page_icon="🚀", layout="wide")
    inject_styles()
    factory = GameFactory(config.game, config.models)
    session = GameSession(st.session_state, factory, config.game.total_rounds)
    provider = OllamaProvider(base_url=config.ollama_base_url)
    coordinator = DecisionCoordinator(provider)
    resolver = RoundResolver()
    render_arena(session, coordinator, resolver, config)
