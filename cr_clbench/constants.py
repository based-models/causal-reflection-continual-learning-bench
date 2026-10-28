"""Model, price, and context-budget constants for the GLM runs."""

API_BASE = "https://api.basedmodels.com/v1"
PUBLIC_MODEL_ID = "glm-5.3-flash:causal-reflection"
LITELLM_MODEL = f"openai/{PUBLIC_MODEL_ID}"
LEADERBOARD_NAME = "ICL + GLM 5.3 Flash"
TASK_NAME = "codebase_adaptation"
DATABASE_TASK = "database_exploration"
SALES_TASK = "sales_prediction"
COHORT_TASK = "cohort_studies"
POKER_TASK = "exploitable_poker"
SPECTRUM_TASK = "blind_spectrum_monitoring"
SUPPORTED_TASKS = (
    TASK_NAME,
    DATABASE_TASK,
    SALES_TASK,
    COHORT_TASK,
    POKER_TASK,
    SPECTRUM_TASK,
)
WORKLOAD = "coding"
QUERY_WORKLOAD = "query"
FORECAST_WORKLOAD = "forecast"
COHORT_WORKLOAD = "cohort"
STRATEGY_WORKLOAD = "strategy"
REGISTRY_WORKLOAD = "registry"

# Fireworks lists GLM 5.3 Flash at 1,048,576 context tokens and 131,072 output tokens.
# https://fireworks.ai/models/fireworks/glm-5p3-flash
CONTEXT_WINDOW_TOKENS = 1_048_576
MAX_OUTPUT_TOKENS = 131_072
# Room for the API's causal prefix and readout tail on top of the prompt.
CAUSAL_WRAPPER_TOKENS = 4_096
# ICL treats max_tokens as the prompt budget. Leave the output cap and the
# wrapper outside that budget so a full transcript still fits the window.
CONTEXT_BUDGET_TOKENS = (
    CONTEXT_WINDOW_TOKENS - MAX_OUTPUT_TOKENS - CAUSAL_WRAPPER_TOKENS
)

# Per million tokens: input $0.15, cached input $0.03, output $0.50.
INPUT_USD_PER_MILLION = 0.15
CACHED_INPUT_USD_PER_MILLION = 0.03
OUTPUT_USD_PER_MILLION = 0.50

# The coding encoder classifies the first 2,000 characters of a plain-text user message.
OBSERVATION_HEAD_CHARS = 2_000
