# Configuration for the LLM Obfuscation Benchmark

# List of OpenRouter model identifiers to be used in the benchmark.
# Add or remove model strings as needed.
# Example: "openai/gpt-3.5-turbo", "google/gemini-pro", "mistralai/mistral-7b-instruct"
LLM_MODELS = [
    "openai/o3-mini-high",
    "google/gemini-2.5-pro-preview",     # Replace with desired models
    "anthropic/claude-3.7-sonnet",
    "deepseek/deepseek-chat-v3-0324"
    # "anthropic/claude-3-haiku-20240307" # Example, ensure model is available on OpenRouter
]

# ELO K-Factor: Affects how much ELO ratings change after a battle.
ELO_K_FACTOR = 32

# Starting ELO for new models
ELO_DEFAULT_RATING = 1500

# Backend operation mode
# If True, the script runs continuously, generating new battles.
# If False, it will run for a set number of battles (not yet implemented, defaults to continuous).
RUN_CONTINUOUSLY = True

# Optional: Number of battles to run if RUN_CONTINUOUSLY is False
# NUM_BATTLES_TO_RUN = 10 # This is not used if RUN_CONTINUOUSLY is True

# --- LLM Interaction Parameters ---
# Maximum number of attempts for LLM3 (attacker)
LLM3_MAX_ATTEMPTS = 1

# Percentage of instructions revealed to LLM3 on each subsequent failed attempt.
# This is no longer used as LLM3 gets full instructions on its single attempt.
LLM3_INSTRUCTION_REVEAL_PERCENTAGES = [] # Kept for structural consistency, but not used.

# --- API Configuration ---
# It's recommended to load the API key from .env, but you can set a default here if needed.
# OPENROUTER_API_KEY = "YOUR_FALLBACK_API_KEY_IF_NOT_IN_ENV" # Not recommended for security

# --- Output Configuration ---
DATA_FILE_PATH = "data.json"

if __name__ == '__main__':
    # This is just for quick testing of the config values if you run this file directly.
    print("LLM Models:", LLM_MODELS)
    print("ELO K-Factor:", ELO_K_FACTOR)
    print("Run Continuously:", RUN_CONTINUOUSLY)
    print("LLM3 Max Attempts:", LLM3_MAX_ATTEMPTS)
    print("Instruction Reveal Percentages:", LLM3_INSTRUCTION_REVEAL_PERCENTAGES)
    print("Data File Path:", DATA_FILE_PATH)
