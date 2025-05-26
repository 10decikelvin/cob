import os
import json
import random
import re
import time
import uuid
from datetime import datetime, timezone
import requests
from dotenv import load_dotenv
import concurrent.futures

# Load configuration from config.py
import config

# Load environment variables from .env file
load_dotenv()
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")

# --- Helper Functions ---
def generate_hex_color():
    """Generates a random 6-digit hex color string (without #)."""
    return f"{random.randint(0, 0xFFFFFF):06x}".upper()

def parse_llm_response(response_text, tags):
    """
    Parses LLM response to extract content from specified XML-like tags.
    Args:
        response_text (str): The raw response string from the LLM.
        tags (list of str): A list of tag names to extract (e.g., ['obfuscated_text', 'instructions_list']).
    Returns:
        dict: A dictionary where keys are tag names and values are the extracted content.
              Returns None for a tag if not found or if content is empty.
    """
    parsed_data = {}
    for tag in tags:
        match = re.search(f"<{tag}>(.*?)</{tag}>", response_text, re.DOTALL | re.IGNORECASE)
        if match and match.group(1).strip():
            parsed_data[tag] = match.group(1).strip()
        else:
            parsed_data[tag] = None
    return parsed_data

def call_openrouter(model_name, system_prompt, user_prompt):
    """
    Calls the OpenRouter API with the given model and prompts.
    Returns:
        str: The content of the LLM's response, or None if an error occurs.
    """
    if not OPENROUTER_API_KEY:
        print("Error: OPENROUTER_API_KEY not found. Please set it in your .env file.")
        return None

    try:
        response = requests.post(
            url="https://openrouter.ai/api/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {OPENROUTER_API_KEY}",
                "Content-Type": "application/json"
            },
            json={
                "model": model_name,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ]
            }
        )
        response.raise_for_status()  # Raise an exception for HTTP errors
        data = response.json()
        return data['choices'][0]['message']['content']
    except requests.exceptions.RequestException as e:
        print(f"Error calling OpenRouter API for model {model_name}: {e}")
        if response is not None:
            print(f"Response status: {response.status_code}")
            print(f"Response text: {response.text}")
        return None
    except (KeyError, IndexError) as e:
        print(f"Error parsing OpenRouter response for model {model_name}: {e}")
        print(f"Response data: {data if 'data' in locals() else 'N/A'}")
        return None

# --- LLM System Prompts ---
BASE_SYSTEM_PROMPT = """
You are participating in an LLM benchmarking game.
The game involves obfuscating and deobfuscating a hex color (a 6-digit string like 'FF00AA').

Overall Rules:
1. LLM1 receives a plaintext hex color. LLM1 outputs an obfuscated string and an 'instructions_list'.
2. LLM2 (same base model as LLM1) receives LLM1's output and tries to deobfuscate the color.
3. LLM3 (different base model) acts as an attacker. LLM3 gets the obfuscated string AND the FULL 'instructions_list' from LLM1.
4. LLM3 has only ONE attempt to guess the color using this information.

Before providing your main response in the specified XML-like tags, you are encouraged to use <think>...</think> tags to outline your thought process. These <think> tags will be ignored by the parser but help you structure your response and may improve your reasoning.

Your responses MUST strictly follow the specified XML-like tag format for the final output. Do not include any other text, explanations, or formatting outside the designated output tags (e.g., <obfuscated_text>, <instructions_list>, <deobfuscated_color>).
"""

LLM1_SYSTEM_PROMPT = BASE_SYSTEM_PROMPT + """
You are LLM1 (Obfuscator).
Your task is to obfuscate the given hex color.
The input color will be provided in a <color_to_obfuscate> tag.
You must output an obfuscated string AND a separate 'instructions_list'.
Your goal is to make it possible for LLM2 (your ally, same base model) to deobfuscate using your output.
LLM3 (opponent, different base model) will receive your FULL instructions_list for its single attempt.
Remember to use <think>...</think> tags for your thought process before the final output tags.
Format your entire response strictly as: <obfuscated_text>YOUR_OBFUSCATED_STRING</obfuscated_text><instructions_list>YOUR_INSTRUCTIONS</instructions_list>
"""

LLM2_SYSTEM_PROMPT = BASE_SYSTEM_PROMPT + """
You are LLM2 (Deobfuscator - Ally). You are allied with LLM1 (same base model).
You will receive an <obfuscated_text> and an <instructions_list>.
Your task is to deobfuscate the original hex color.
Remember to use <think>...</think> tags for your thought process before the final output tags.
Format your entire response strictly as: <deobfuscated_color>RRGGBB</deobfuscated_color>
The color should be a 6-digit hex string without '#'.
"""

LLM3_SYSTEM_PROMPT = BASE_SYSTEM_PROMPT + """
You are LLM3 (Attacker - Opponent).
Your task is to deobfuscate a hex color. You have only ONE attempt.
You will receive an <obfuscated_text> AND the FULL <instructions_list> from LLM1.
Use both to try and determine the original hex color.
Remember to use <think>...</think> tags for your thought process before the final output tags.
Format your entire response strictly as: <deobfuscated_color>RRGGBB</deobfuscated_color>
The color should be a 6-digit hex string without '#'.
"""

# --- Game Logic ---
def run_llm1_obfuscation(model_name, color_to_obfuscate):
    print(f"  LLM1 ({model_name}) obfuscating {color_to_obfuscate}...")
    user_prompt = f"<color_to_obfuscate>{color_to_obfuscate}</color_to_obfuscate>"
    response_text = call_openrouter(model_name, LLM1_SYSTEM_PROMPT, user_prompt)
    
    print(f"    LLM1 ({model_name}) raw response: {response_text}") # Log raw response
    
    if not response_text:
        return None, None, {"prompt": user_prompt, "response": None, "parsed_obfuscated_text": None, "parsed_instructions": None}

    parsed = parse_llm_response(response_text, ['obfuscated_text', 'instructions_list'])
    obfuscated_text = parsed.get('obfuscated_text')
    instructions = parsed.get('instructions_list')
    
    conversation_log = {
        "prompt": user_prompt, 
        "response": response_text, # Raw response is already in the log
        "parsed_obfuscated_text": obfuscated_text,
        "parsed_instructions": instructions
    }
    
    if not obfuscated_text or not instructions:
        print(f"  LLM1 ({model_name}) failed to provide valid obfuscation/instructions (check raw response above).")
        # response_text already printed
        return None, None, conversation_log
        
    print(f"    Parsed Obfuscated: {obfuscated_text[:50]}...")
    print(f"    Parsed Instructions: {instructions[:50]}...")
    return obfuscated_text, instructions, conversation_log

def run_llm2_deobfuscation(model_name, obfuscated_text, instructions, original_color):
    print(f"  LLM2 ({model_name}) deobfuscating...")
    user_prompt = f"<obfuscated_text>{obfuscated_text}</obfuscated_text><instructions_list>{instructions}</instructions_list>"
    response_text = call_openrouter(model_name, LLM2_SYSTEM_PROMPT, user_prompt)

    print(f"    LLM2 ({model_name}) raw response: {response_text}") # Log raw response
    
    parsed_color = None
    is_correct = False

    if response_text:
        parsed = parse_llm_response(response_text, ['deobfuscated_color'])
        parsed_color = parsed.get('deobfuscated_color')
        if parsed_color and re.match(r"^[0-9A-Fa-f]{6}$", parsed_color):
            is_correct = (parsed_color.upper() == original_color.upper())
            print(f"    Parsed Deobfuscated: {parsed_color} (Correct: {is_correct})")
        else:
            print(f"    LLM2 ({model_name}) provided invalid color format: {parsed_color} (check raw response above).")
            # response_text already printed
            parsed_color = None # Ensure it's None if format is bad
    else:
        print(f"  LLM2 ({model_name}) failed to respond (check raw response above).")

    conversation_log = {
        "prompt": user_prompt,
        "response": response_text, # Raw response is already in the log
        "parsed_deobfuscated_color": parsed_color,
        "is_correct_deobfuscation": is_correct
    }
    return parsed_color, is_correct, conversation_log

def run_llm3_attack(attacker_model_name, obfuscated_text, full_instructions, plaintext_color):
    print(f"  LLM3 ({attacker_model_name}) attacking. Target: {plaintext_color}")
    # LLM3 gets only one attempt with full instructions.
    attempt_num = 1
    succeeded_on_attempt = None # Will be 1 if successful, None otherwise
    
    print(f"    Attempt {attempt_num}/{config.LLM3_MAX_ATTEMPTS} with full instructions...")
    
    # LLM3 always gets full instructions now.
    user_prompt = f"<obfuscated_text>{obfuscated_text}</obfuscated_text><instructions_list>{full_instructions}</instructions_list>"
    percentage_provided = 1.0 # Always 100%

    response_text = call_openrouter(attacker_model_name, LLM3_SYSTEM_PROMPT, user_prompt)
    print(f"      LLM3 ({attacker_model_name}) attempt {attempt_num} raw response: {response_text}")

    guessed_color = None
    is_correct = False

    if response_text:
        parsed = parse_llm_response(response_text, ['deobfuscated_color'])
        guessed_color = parsed.get('deobfuscated_color')
        if guessed_color and re.match(r"^[0-9A-Fa-f]{6}$", guessed_color):
            is_correct = (guessed_color.upper() == plaintext_color.upper())
            print(f"      Parsed Guessed: {guessed_color} (Correct: {is_correct})")
        else:
            print(f"      LLM3 ({attacker_model_name}) provided invalid color format: {guessed_color} (check raw response above).")
            guessed_color = None 
    else:
        print(f"      LLM3 ({attacker_model_name}) failed to respond on attempt {attempt_num} (check raw response above).")

    attempts_log = [{ # Log for the single attempt
        "attempt_number": attempt_num,
        "instructions_provided_percentage": percentage_provided,
        "prompt": user_prompt,
        "response": response_text,
        "guessed_color": guessed_color,
        "is_correct": is_correct
    }]

    if is_correct:
        succeeded_on_attempt = attempt_num # This will be 1

    return succeeded_on_attempt, attempts_log

def run_single_round(obfuscator_model, deobfuscator_model, attacker_model, color, round_num_for_log): # Added round_num_for_log
    print(f" Starting Round {round_num_for_log}: Obfuscator/Deobfuscator: {obfuscator_model}, Attacker: {attacker_model}")
    # This function's data structure will be returned and then assigned to the correct round in main
    # It no longer needs to know its own round number internally for the dict key
    current_round_data = {
        "round_number": round_num_for_log, # Store the round number for clarity in data.json
        "obfuscator_model": obfuscator_model,
        "deobfuscator_model": deobfuscator_model,
        "attacker_model": attacker_model,
        "obfuscated_text": None,
        "instructions_list": None,
        "llm1_conversation": {},
        "llm2_conversation": {},
        "llm3_attempts": [], # Will contain one attempt
        "attacker_succeeded_on_attempt": None # Will be 1 or None
    }

    obfuscated_text, instructions, llm1_log = run_llm1_obfuscation(obfuscator_model, color)
    current_round_data["llm1_conversation"] = llm1_log
    if not obfuscated_text or not instructions:
        print(f"  LLM1 failed in Round {round_num_for_log}. Cannot proceed with LLM2/LLM3 for this round.")
        return current_round_data

    current_round_data["obfuscated_text"] = obfuscated_text
    current_round_data["instructions_list"] = instructions

    # LLM2 (Ally Deobfuscation)
    _, _, llm2_log = run_llm2_deobfuscation(deobfuscator_model, obfuscated_text, instructions, color)
    current_round_data["llm2_conversation"] = llm2_log
    if not llm2_log.get("is_correct_deobfuscation"):
        print(f"  Warning: LLM2 ({deobfuscator_model}) failed to deobfuscate in Round {round_num_for_log}.")

    # LLM3 (Attacker Deobfuscation) - single attempt with full instructions
    succeeded_attempt, llm3_log = run_llm3_attack(attacker_model, obfuscated_text, instructions, color)
    current_round_data["llm3_attempts"] = llm3_log
    current_round_data["attacker_succeeded_on_attempt"] = succeeded_attempt
    
    return current_round_data

def determine_battle_outcome(r1_succeeded, r2_succeeded, model_A_name, model_B_name):
    """
    Determines the winner of the battle based on single LLM3 attempts.
    - r1_succeeded: True if Model B (as LLM3 in Round 1) succeeded.
    - r2_succeeded: True if Model A (as LLM3 in Round 2) succeeded.
    """
    outcome = "tie" 

    # Model A was LLM3 in Round 2. Model B was LLM3 in Round 1.
    # A wins if its LLM3 (r2) succeeded AND B's LLM3 (r1) failed.
    # B wins if its LLM3 (r1) succeeded AND A's LLM3 (r2) failed.
    # Otherwise, it's a tie (both succeeded or both failed).

    if r2_succeeded and not r1_succeeded:
        outcome = f"{model_A_name}_wins"
    elif r1_succeeded and not r2_succeeded:
        outcome = f"{model_B_name}_wins"
    
    print(f"Outcome check: Model B (as LLM3 in R1) succeeded: {r1_succeeded}, Model A (as LLM3 in R2) succeeded: {r2_succeeded}. Result: {outcome}")
    return outcome

# --- Data Persistence ---
def load_data(filepath=config.DATA_FILE_PATH):
    if os.path.exists(filepath):
        try:
            with open(filepath, 'r') as f:
                return json.load(f)
        except json.JSONDecodeError:
            print(f"Warning: Could not decode JSON from {filepath}. Starting with empty data.")
            return []
    return []

def save_data(data, filepath=config.DATA_FILE_PATH):
    try:
        with open(filepath, 'w') as f:
            json.dump(data, f, indent=2)
    except IOError as e:
        print(f"Error saving data to {filepath}: {e}")

# --- Main Execution ---
def main():
    if not OPENROUTER_API_KEY:
        print("Critical: OPENROUTER_API_KEY is not set. Exiting.")
        return

    if len(config.LLM_MODELS) < 2:
        print("Critical: At least two models must be defined in config.LLM_MODELS. Exiting.")
        return

    all_battle_data = load_data()
    print(f"Loaded {len(all_battle_data)} previous battle records.")

    battle_count = 0
    # Max workers for ThreadPoolExecutor - can be tuned. 
    # Setting to 2 as we run two rounds in parallel.
    MAX_WORKERS = 2 

    try:
        with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
            while True:
                battle_count += 1
                print(f"\n--- Starting Battle #{len(all_battle_data) + 1} ---")
                
                model_A_name, model_B_name = random.sample(config.LLM_MODELS, 2)
                print(f"Model A: {model_A_name}, Model B: {model_B_name}")

                plaintext_color = generate_hex_color()
                print(f"Plaintext Color: {plaintext_color}")

                battle_id = f"{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}_{str(uuid.uuid4())[:8]}"
                current_battle = {
                    "battle_id": battle_id,
                    "timestamp_start": datetime.now(timezone.utc).isoformat(),
                    "model_A_info": {"name": model_A_name},
                    "model_B_info": {"name": model_B_name},
                    "plaintext_color": plaintext_color,
                    "rounds": [None, None], # Pre-allocate for round data
                    "battle_outcome": None,
                    "timestamp_end": None
                }

                # Prepare submissions for ThreadPoolExecutor
                # Round 1: Model A is LLM1/LLM2, Model B is LLM3
                future_round1 = executor.submit(
                    run_single_round,
                    obfuscator_model=model_A_name,
                    deobfuscator_model=model_A_name,
                    attacker_model=model_B_name,
                    color=plaintext_color,
                    round_num_for_log=1
                )
                current_battle["model_A_info"]["role_in_round1"] = "LLM1_LLM2"
                current_battle["model_B_info"]["role_in_round1"] = "LLM3"

                # Round 2: Model B is LLM1/LLM2, Model A is LLM3
                future_round2 = executor.submit(
                    run_single_round,
                    obfuscator_model=model_B_name,
                    deobfuscator_model=model_B_name,
                    attacker_model=model_A_name,
                    color=plaintext_color,
                    round_num_for_log=2
                )
                current_battle["model_A_info"]["role_in_round2"] = "LLM3"
                current_battle["model_B_info"]["role_in_round2"] = "LLM1_LLM2"

                # Get results
                # This will block until each round completes.
                # The rounds themselves run their LLM calls sequentially internally.
                # The benefit here is that network latency for Round 1 and Round 2 calls can overlap.
                print("Waiting for rounds to complete...")
                round1_data = future_round1.result()
                round2_data = future_round2.result()
                
                # Ensure round_number is correctly set if not done by run_single_round (it is now)
                # round1_data["round_number"] = 1 
                # round2_data["round_number"] = 2
                current_battle["rounds"][0] = round1_data
                current_battle["rounds"][1] = round2_data
                
                # Determine outcome based on success (True/False)
                # succeeded_on_attempt will be 1 if successful, None otherwise.
                r1_succeeded = round1_data.get("attacker_succeeded_on_attempt") is not None
                r2_succeeded = round2_data.get("attacker_succeeded_on_attempt") is not None
                
                battle_outcome = determine_battle_outcome(
                    r1_succeeded, # Model B as LLM3 in R1
                    r2_succeeded, # Model A as LLM3 in R2
                    model_A_name, 
                    model_B_name
                )
                current_battle["battle_outcome"] = battle_outcome
                current_battle["timestamp_end"] = datetime.now(timezone.utc).isoformat()
                
                print(f"\nBattle Outcome: {battle_outcome}")

                all_battle_data.append(current_battle)
                save_data(all_battle_data)
                print(f"Battle data saved. Total battles recorded: {len(all_battle_data)}")

                if not config.RUN_CONTINUOUSLY and battle_count >= getattr(config, "NUM_BATTLES_TO_RUN", 1):
                    print(f"Reached target number of battles ({getattr(config, 'NUM_BATTLES_TO_RUN', 1)}). Exiting.")
                    break
                
                print("Pausing before next battle...")
                time.sleep(5) # Pause before starting a new battle

    except KeyboardInterrupt:
        print("\nProcess interrupted by user. Saving final data...")
        save_data(all_battle_data) # Ensure data is saved on exit
        print("Data saved. Exiting.")
    except Exception as e:
        print(f"An unexpected error occurred: {e}")
        import traceback
        traceback.print_exc()
        print("Attempting to save data before exiting due to error...")
        save_data(all_battle_data)
        print("Data saved. Exiting.")


if __name__ == "__main__":
    main()
