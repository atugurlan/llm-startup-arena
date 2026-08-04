SYSTEM_PROMPT = """
You are the founder and CEO of one company in a competitive startup simulation.
Choose actions that maximize the company's value after ten rounds while keeping it solvent.
Return only a decision matching the supplied JSON schema. Do not calculate game outcomes;
the deterministic game engine resolves every consequence.
""".strip()


def build_company_prompt(company_id: str, state_json: str) -> str:
    return (
        f"You control company {company_id}.\n"
        "All companies make decisions from the same frozen round snapshot.\n"
        f"Current game state:\n{state_json}"
    )
