import os
import json
import sys

# Load the JSON file
try:
    with open("data/jsonte/data_files/entities.json", "r") as file:
        data = json.load(file)
except FileNotFoundError:
    print("Error: JSON file not found at 'data/jsonte/data_files/entities.json'.")
    sys.exit(1)
except json.JSONDecodeError as e:
    print(f"Error: Failed to parse JSON file. Details: {e}")
    sys.exit(1)

# Parse configuration from command-line arguments
try:
    config = json.loads(sys.argv[1]) if len(sys.argv) > 1 else {}
except json.JSONDecodeError as e:
    print(f"Error: Failed to parse command-line JSON argument. Details: {e}")
    sys.exit(1)

# Handle short_path in configuration
short_path = config.get("short_path", "")  # Default to an empty string if not provided
if not short_path:
    print("Warning: 'short_path' is not provided in the configuration. Using default path.")

# Base output directory
base_output_dir = os.path.join("BP", "scripts", short_path, "entitySubscriptions") if short_path else os.path.join("BP", "scripts", "entitySubscriptions")
os.makedirs(base_output_dir, exist_ok=True)

print(f"Output directory created (or already exists): {base_output_dir}")


def to_camel_case(s):
    parts = s.split('_')
    return ''.join(word.capitalize() for word in parts)

def generate_attack_config(attack):
    """Generate configuration block for an attack."""
    excluded_keys = {"min_activation_range", "max_activation_range"}
    config_lines = []
    
    config_key = None
    for key, value in attack.items():
        if key in excluded_keys:
            continue
        
        if key == "id":
            # ID is treated as the key for this block, written in uppercase
            config_key = value.upper()
            continue

        if key == "damage" and isinstance(value, list):
            # Ensure damage is represented as a proper array in the output
            config_value = f"[{', '.join(map(str, value))}]"
        elif isinstance(value, (int, float)):
            # Handle numeric values, including multiplication for durations
            config_value = int(value * 20) if key in {"cast_duration", "tip_duration"} else value
        else:
            # Convert other types to strings
            config_value = f'"{value}"'
        
        config_lines.append(f"        {key.upper()}: {config_value}")

    # Check if a config key was set (necessary for valid output)
    if not config_key:
        raise ValueError("Missing 'id' key in attack configuration")

    # Combine the configuration lines
    config_body = ",\n".join(config_lines)
    return f"""    {config_key}: {{
{config_body}
    }}"""


def generate_switch_case(entity_name, attack_id):
    """Generate switch case for an attack."""
    return f"""        case `${{maps.identifier}}:{attack_id}`:
            {entity_name}{to_camel_case(attack_id)}(entity);
            break;"""

def generate_function_template(entity_name, attack_id):
    """Generate function template for an attack."""
    return f"""export async function {entity_name}{to_camel_case(attack_id)}(entity) {{
    const config = {entity_name.upper()}_CONFIG.{attack_id.upper()};
    // Add your attack logic here
}}"""

# Process each entity in the JSON
for mob in data["advance_mob"]:
    entity_name = mob["name"]
    entity_name_camel = to_camel_case(entity_name)
    entity_folder = os.path.join(base_output_dir, to_camel_case(entity_name))
    os.makedirs(entity_folder, exist_ok=True)

    # Generate config.js
    attack_configs = ",\n".join([generate_attack_config(attack) for attack in mob["attacks"]])
    config_content = f"""// Attack Configuration for {entity_name_camel}

export const {to_camel_case(entity_name).upper()}_CONFIG = {{
{attack_configs}
}};
"""
    # For config.js
    config_file_path = os.path.join(entity_folder, "config.js")
    if not os.path.exists(config_file_path):
        with open(config_file_path, "w") as config_file:
            config_file.write(config_content)
    else:
        print(f"File already exists: {config_file_path}")

    # Generate handlers.js
    switch_cases = "\n".join([generate_switch_case(entity_name_camel, attack["id"]) for attack in mob["attacks"]])
    handlers_content = f"""// Handlers for {entity_name_camel} Attacks
import {{ {", ".join([entity_name_camel + to_camel_case(attack["id"]) for attack in mob["attacks"]])} }} from './functions';
import * as maps from '../../eventManager/maps'

function handle{entity_name_camel}Attack(entity, attackId) {{
    switch (attackId) {{
{switch_cases}
        default:
            console.warn(`Unknown attack: ${{attackId}}`);
    }}
}}

export const {to_camel_case(entity_name)} = [
    {{
        eventName: "onDataDrivenEntityTrigger",
        param: ["entity", "eventId"],
        func: handle{entity_name_camel}Attack,
        priority: 2
    }}
];
"""
    handlers_file_path = os.path.join(entity_folder, "handlers.js")
    if not os.path.exists(handlers_file_path):
        with open(handlers_file_path, "w") as handlers_file:
            handlers_file.write(handlers_content)
    else:
        print(f"File already exists: {handlers_file_path}")

    # Generate functions.js
    function_templates = "\n".join([generate_function_template(entity_name_camel, attack["id"]) for attack in mob["attacks"]])
    functions_content = f"""// Function Definitions for {entity_name_camel} Attacks
import {{ EntityDamageCause }} from "@minecraft/server";
import * as utils from '../../utils/index';
import {{ startCoroutineForBoss }} from "../../eventManager/CoroutineClass";
import * as maps from '../../eventManager/maps'
import {{ {to_camel_case(entity_name).upper()}_CONFIG }} from "./config"; \n
{function_templates}
"""
    # For functions.js
    functions_file_path = os.path.join(entity_folder, "functions.js")
    if not os.path.exists(functions_file_path):
        with open(functions_file_path, "w") as functions_file:
            functions_file.write(functions_content)
    else:
        print(f"File already exists: {functions_file_path}")

print(f"Output generated for all entities in: {base_output_dir}")
