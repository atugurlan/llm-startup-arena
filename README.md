# LLM Startup Arena

Four local LLMs compete to build the most valuable startup over ten rounds.

The project is intentionally local-first and uses Ollama for model inference.

## Requirements

- [uv](https://docs.astral.sh/uv/)
- [Ollama](https://ollama.com/)
- The four local models:

```powershell
ollama pull qwen3:8b
ollama pull llama3.1:8b
ollama pull gemma3:12b
ollama pull mistral-nemo:12b
```

## Project structure

```text
llm_startup_arena/
|-- domain/         # Companies, employees, clients, events, and game state
|-- engine/         # Arena orchestration and deterministic round resolution
|-- llm/            # Provider contract, prompts, and Ollama integration
|-- persistence/    # JSON match storage
|-- ui/             # Streamlit interface
`-- config.py       # Global game configuration
```

The LLMs choose actions. The deterministic engine calculates all consequences.

## Employee roles

Employees are deterministic game entities, not additional LLM agents. Each employee has
a role, skill level, salary, morale, loyalty, and experience. These values will be used by
the game engine when it resolves company decisions.

| Role | Responsibility | Planned gameplay effect |
|---|---|---|
| `ENGINEER` | Builds and improves the technology | Makes product investment more effective |
| `PRODUCT` | Chooses what the company should build | Improves product direction and client satisfaction |
| `MARKETING` | Creates awareness and demand | Increases reputation and client attraction |
| `SALES` | Converts interested clients into contracts | Improves the chance of winning clients |
| `OPERATIONS` | Keeps the company efficient and organized | Reduces operating costs and supports employee morale |

The current starting team contains two engineers and one employee each in product,
marketing, and sales. Operations is available as a role but is not part of the initial
five-person team. Role bonuses are planned mechanics and are not implemented yet.

## Run locally

```powershell
uv sync
uv run streamlit run app.py
```

Open `http://localhost:8501` after Streamlit starts. `uv run` keeps the project
environment synchronized with `pyproject.toml` and `uv.lock`.

The initial screen includes a live Ollama connection test for each configured model.

Run the checks with:

```powershell
uv run pytest
uv run ruff check .
```

## Architecture

```mermaid
classDiagram
    direction LR

    class StreamlitApp {
        +run()
        +display_companies()
        +display_round()
        +display_leaderboard()
    }

    class Arena {
        +GameState state
        +GameConfig config
        +run_round()
        +run_game()
        +is_finished bool
    }

    class GameFactory {
        +create() GameState
        -create_companies()
        -create_employees()
        -create_clients()
    }

    class RoundResolver {
        +resolve_investments()
        +resolve_recruitment()
        +resolve_clients()
        +resolve_sabotage()
        +process_payroll()
    }

    class GameConfig {
        +total_rounds = 10
        +company_count = 4
        +starting_cash
        +starting_employees = 5
        +total_clients = 20
    }

    class GameState {
        +round_number
        +market_event
        +companies
        +clients
    }

    class Company {
        +id
        +name
        +model
        +cash
        +product_score
        +reputation
        +employees
        +client_ids
    }

    class Employee {
        +id
        +name
        +role
        +skill
        +salary
        +morale
        +loyalty
        +experience
    }

    class Client {
        +id
        +name
        +segment
        +revenue_per_round
        +satisfaction
        +contract_rounds_remaining
        +company_id
    }

    class MarketEvent {
        +id
        +name
        +description
        +modifiers
    }

    class LLMProvider {
        <<interface>>
        +generate_decision(model, company_id, state)
    }

    class OllamaProvider {
        +base_url
        +generate_decision(model, company_id, state)
    }

    class CompanyDecision {
        +strategy
        +budget
        +target_client_ids
        +target_employee_ids
        +partnership_offer
        +sabotage_action
    }

    class BudgetAllocation {
        +product
        +marketing
        +training
        +recruitment
        +retention
        +sabotage
    }

    class MatchRepository {
        +save_match()
        +load_match()
        +list_matches()
    }

    StreamlitApp --> Arena : controls
    StreamlitApp --> GameFactory : creates initial state
    StreamlitApp --> MatchRepository : loads history

    Arena *-- GameConfig
    Arena *-- GameState
    Arena --> LLMProvider : requests decisions
    Arena --> RoundResolver : resolves round
    Arena --> MatchRepository : saves results

    GameFactory --> GameConfig : reads rules
    GameFactory --> GameState : creates

    GameState *-- Company
    GameState *-- Client
    GameState o-- MarketEvent

    Company *-- Employee
    Company --> Client : owns contracts

    LLMProvider <|.. OllamaProvider
    LLMProvider --> CompanyDecision
    CompanyDecision *-- BudgetAllocation

    RoundResolver --> GameState : updates
    RoundResolver --> CompanyDecision : processes
```
