from collections.abc import Callable, Mapping
from html import escape

import streamlit as st
from httpx import HTTPError
from ollama import ResponseError
from pydantic import ValidationError
from streamlit.delta_generator import DeltaGenerator

from llm_startup_arena.config import AppConfig
from llm_startup_arena.domain import Company, GameState, RoundSnapshot
from llm_startup_arena.engine import (
    CompanyRanker,
    CompanyScore,
    GameFactory,
    GameResult,
    RoundResolver,
)
from llm_startup_arena.llm import CompanyDecision, DecisionCoordinator, RoundDecisionRecord
from llm_startup_arena.llm.ollama_provider import OllamaProvider

from .session import GameSession

COMPANY_COLORS = {
    "nova": ("#A78BFA", "#6D28D9"),
    "orbit": ("#5EEAD4", "#0F766E"),
    "pixel": ("#FCD34D", "#B45309"),
    "apex": ("#FDA4AF", "#BE123C"),
}


def inject_styles() -> None:
    st.markdown(
        """
        <style>
        .stApp { background: #f4f7fb; color: #1e293b; }
        .block-container {
            max-width: 1480px; padding-top: 4rem; padding-bottom: 2rem;
        }
        .arena-header {
            padding: 1rem 1.35rem; margin-bottom: .65rem;
            border: 1px solid #dce3ef; border-radius: 18px;
            background:
                radial-gradient(circle at 85% 20%, rgba(167, 139, 250, .22), transparent 28%),
                linear-gradient(135deg, #ffffff 0%, #f3f0ff 100%);
            box-shadow: 0 8px 28px rgba(71, 85, 105, .08);
        }
        .arena-kicker { color: #64748b; font-size: .7rem; letter-spacing: .14em; }
        .arena-title { color: #172033; font-size: 1.65rem; font-weight: 760; margin: .1rem 0; }
        .arena-subtitle { color: #64748b; font-size: .84rem; margin: 0; }
        .company-card {
            min-height: 200px; padding: .85rem 1rem; border-radius: 18px 18px 0 0;
            border: 1px solid #dce3ef; background: #ffffff;
            box-shadow: 0 12px 28px rgba(71, 85, 105, .09);
        }
        .company-accent { height: 4px; border-radius: 10px; margin-bottom: .8rem; }
        .company-topline { display: flex; justify-content: space-between; gap: .5rem; }
        .company-name { color: #172033; font-size: 1.08rem; font-weight: 700; }
        .live-rank { font-size: .68rem; font-weight: 700; letter-spacing: .06em; }
        .model-name { color: #718096; font-size: .72rem; margin: .1rem 0 .8rem; }
        .cash { color: #172033; font-size: 1.45rem; font-weight: 750; }
        .cash-label { color: #8491a7; font-size: .62rem; letter-spacing: .09em; }
        .valuation { color: #64748b; font-size: .68rem; margin-top: .15rem; }
        .card-divider { border-top: 1px solid #e5eaf2; margin: .8rem 0; }
        .metric-grid { display: grid; grid-template-columns: repeat(4, 1fr); gap: .35rem; }
        .metric-value { color: #334155; font-size: .92rem; font-weight: 650; }
        .metric-label { color: #8491a7; font-size: .6rem; }
        .status-pill {
            display: inline-block; padding: .22rem .55rem; margin-top: .8rem;
            border-radius: 999px; font-size: .62rem; font-weight: 650;
        }
        .round-note { color: #64748b; font-size: .74rem; margin-top: .35rem; }
        .model-progress { color: #475569; font-size: .74rem; margin-top: .35rem; }
        .decision-box {
            height: 205px; margin-top: 0; padding: .8rem .9rem;
            border: 1px solid #dce3ef; border-top: 0;
            border-radius: 0 0 18px 18px; background: #f9fbfe;
            overflow-y: auto; box-sizing: border-box;
        }
        .decision-label { color: #8491a7; font-size: .68rem; letter-spacing: .08em; }
        .decision-strategy { color: #334155; font-size: .88rem; margin: .3rem 0 .65rem; }
        .decision-budget { color: #64748b; font-size: .75rem; line-height: 1.45; }
        .ranking-header {
            margin: 0 0 1rem; padding: 1.25rem 1.5rem; text-align: center;
            border: 1px solid #ddd6fe; border-radius: 18px;
            background: linear-gradient(135deg, #ffffff 0%, #f3f0ff 100%);
        }
        .ranking-title { color: #172033; font-size: 1.5rem; font-weight: 750; }
        .ranking-winner { color: #7c3aed; font-size: 1rem; margin-top: .3rem; }
        .ranking-card {
            min-height: 230px; padding: 1rem; border: 1px solid #dce3ef;
            border-radius: 16px; background: #ffffff;
        }
        .ranking-position { color: #7c3aed; font-size: 1.4rem; font-weight: 750; }
        .ranking-company { color: #172033; font-size: 1.05rem; font-weight: 700; }
        .ranking-model { color: #8491a7; font-size: .72rem; margin-bottom: .8rem; }
        .ranking-total { color: #334155; font-size: 1.25rem; font-weight: 700; }
        .ranking-breakdown { color: #64748b; font-size: .72rem; line-height: 1.6; }
        .decision-empty {
            display: flex; height: 100%; align-items: center; justify-content: center;
            color: #94a3b8; font-size: .74rem; text-align: center;
        }
        div[data-testid="stTabs"] { margin-top: 1rem; }
        div[data-testid="stTabs"] button { color: #64748b; font-size: .78rem; }
        div[data-testid="stTabs"] button[aria-selected="true"] { color: #6d28d9; }
        div[data-baseweb="tab-highlight"] { background-color: #8b5cf6; }
        div[data-testid="stButton"] button[kind="primary"] {
            border-color: #7c3aed; background: #7c3aed; color: #ffffff;
        }
        div[data-testid="stButton"] button[kind="secondary"] {
            border-color: #cbd5e1; background: #ffffff; color: #334155;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def render_company_card(
    company: Company,
    score: CompanyScore,
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
            <div class="company-topline">
                <div class="company-name">{escape(company.name)}</div>
                <div class="live-rank" style="color:{highlight}">#{score.position} LIVE</div>
            </div>
            <div class="model-name">{escape(company.model)}</div>
            <div class="cash">${company.cash:,.0f}</div>
            <div class="cash-label">AVAILABLE CASH</div>
            <div class="valuation">Valuation ${score.total_value:,.0f}</div>
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


def render_decision_placeholder(slot: DeltaGenerator, next_round: int) -> None:
    slot.markdown(
        f"""
        <div class="decision-box">
            <div class="decision-empty">Awaiting decision for round {next_round}</div>
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
    scores = {score.company_id: score for score in CompanyRanker().rank(session.state).rankings}
    columns = st.columns(config.game.company_count, gap="medium")
    for column, company in zip(columns, session.state.companies, strict=True):
        accent, highlight = COMPANY_COLORS[company.id]
        with column:
            render_company_card(
                company,
                scores[company.id],
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
            else:
                render_decision_placeholder(slot, session.state.round_number + 1)
    return decision_slots


def render_talent_pool(state: GameState) -> None:
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
    st.dataframe(
        employee_roster_rows(state),
        hide_index=True,
        use_container_width=True,
    )


def history_chart_rows(
    snapshots: list[RoundSnapshot],
    metric: str,
) -> list[dict[str, int]]:
    """Convert stored snapshots into Streamlit chart rows."""
    return [
        {
            "Round": snapshot.round_number,
            **{
                company.company_name: int(getattr(company, metric))
                for company in snapshot.companies
            },
        }
        for snapshot in snapshots
    ]


def render_game_history(snapshots: list[RoundSnapshot]) -> None:
    chart_specs = (
        ("Cash", "cash"),
        ("Product", "product_score"),
        ("Reputation", "reputation"),
        ("Clients", "client_count"),
        ("Employees", "employee_count"),
    )
    tabs = st.tabs([label for label, _ in chart_specs])
    for tab, (label, metric) in zip(tabs, chart_specs, strict=True):
        with tab:
            rows = history_chart_rows(snapshots, metric)
            company_names = (
                [company.company_name for company in snapshots[0].companies] if snapshots else []
            )
            st.line_chart(
                rows,
                x="Round",
                y=company_names,
                x_label="Round",
                y_label=label,
                height=300,
            )


def company_overview_rows(state: GameState) -> list[dict[str, str | int]]:
    scores = {score.company_id: score for score in CompanyRanker().rank(state).rankings}
    return [
        {
            "Rank": scores[company.id].position,
            "Company": company.name,
            "Model": company.model,
            "Valuation": f"${scores[company.id].total_value:,}",
            "Cash": f"${company.cash:,}",
            "Product": company.product_score,
            "Reputation": company.reputation,
            "Clients": len(company.client_ids),
            "Employees": len(company.employees),
        }
        for company in sorted(state.companies, key=lambda item: scores[item.id].position)
    ]


def render_dashboard_tabs(session: GameSession) -> None:
    overview_tab, teams_tab, talent_tab, history_tab = st.tabs(
        ["Overview", "Teams", "Talent", "History"]
    )
    with overview_tab:
        st.dataframe(
            company_overview_rows(session.state),
            hide_index=True,
            use_container_width=True,
        )
    with teams_tab:
        render_employee_rosters(session.state)
    with talent_tab:
        render_talent_pool(session.state)
    with history_tab:
        render_game_history(session.snapshot_history)


def render_final_ranking(result: GameResult) -> None:
    winner = result.winner
    st.markdown(
        f"""
        <div class="ranking-header">
            <div class="ranking-title">Final company ranking</div>
            <div class="ranking-winner">Winner: {escape(winner.company_name)} · ${winner.total_value:,.0f}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    columns = st.columns(len(result.rankings), gap="medium")
    for column, score in zip(columns, result.rankings, strict=True):
        with column:
            st.markdown(
                f"""
                <div class="ranking-card">
                    <div class="ranking-position">#{score.position}</div>
                    <div class="ranking-company">{escape(score.company_name)}</div>
                    <div class="ranking-model">{escape(score.model)}</div>
                    <div class="ranking-total">${score.total_value:,.0f}</div>
                    <div class="ranking-breakdown">
                        Cash: ${score.cash_value:,.0f}<br>
                        Product: ${score.product_value:,.0f}<br>
                        Reputation: ${score.reputation_value:,.0f}<br>
                        Clients: ${score.client_value:,.0f}<br>
                        Team: ${score.employee_value:,.0f}
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
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

    if session.is_finished:
        render_final_ranking(CompanyRanker().rank(state))

    controls = st.container()
    decision_slots = render_company_grid(session, config)
    with controls:
        render_round_controls(session, coordinator, resolver, config, decision_slots)
    render_dashboard_tabs(session)


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
