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
    excluded_keys = {"min_activation_range", "max_activation_range", "attack_type"}
    config_lines = []
    
    config_key = None
    for key, value in attack.items():
        if key in excluded_keys:
            continue
        
        if key == "id":
            # ID is treated as the key for this block, written in uppercase
            config_key = value.upper()
            continue

        if key == "damage_range" and isinstance(value, list):
            # Ensure damage is represented as a proper array in the output
            config_value = f"[{', '.join(map(str, value))}]"
        elif isinstance(value, (int, float)):
            # Handle numeric values, including multiplication for durations
            config_value = int(value * 20) if key in {"cast_duration", "tip_duration", "attack_time"} else value
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
    return f"""    [identifier('{attack_id}'), {entity_name}{to_camel_case(attack_id)}]"""

def to_camel_case(snake_str):
    """Convert snake_case to CamelCase."""
    components = snake_str.split('_')
    return ''.join(x.title() for x in components)

def generate_function_template(entity_name, attack_id, template_type):
    """Generate function template for an attack based on the template type."""
    templates = {
        "basic": f"""
export async function {to_camel_case(entity_name)}{to_camel_case(attack_id)}(entity) {{
    const config = {to_camel_case(entity_name).upper()}_CONFIG.{attack_id.upper()};
    const damage = utils.randomInt(...config.DAMAGE_RANGE);
    utils.delayExecute(config.CAST_DURATION, () => {{
        utils.executeIfValid(entity, () => {{
        utils.resetAndReadyAbility(entity);
        }});
    }});
    utils.resetFamilyAttack(entity, ['{entity_name}']);
    utils.executeIfValid(entity, () => {{
      entity.setProperty(utils.identifier('animations'), config.ANIMATION);
    }});
    utils.facePlayer(entity, 1);
    utils.delayExecute(config.ATTACK_TIME, () => {{
        utils.executeIfValid(entity, () => {{
            utils.getTargets(entity, {{
                position: utils.getPosForward(entity, 2),
                radius: config.RADIUS,
                callback: (victim) => {{
                    victim.applyDamage(damage, {{ cause: EntityDamageCause.entityAttack, damagingEntity: entity }})
                    utils.normalizedKnockBack(entity.location, victim, 0.3, 2.6, 'default');
                }}
            }})
        }});
    }});
}}
""",
        "courotine": f"""
export async function {to_camel_case(entity_name)}{to_camel_case(attack_id)}(entity) {{
    const config = {to_camel_case(entity_name).upper()}_CONFIG.{attack_id.upper()};
    utils.tipPlayer(entity, config.TIP_DURATION, config.TIP_MESSAGE);
    utils.facePlayer(entity, 1);

    utils.resetFamilyAttack(entity, ['{entity_name}']);

    let active = function* () {{
        utils.facePlayer(entity, 1);
        yield 5;
        utils.executeIfValid(entity, () => {{
            entity.setProperty(utils.identifier('animations'), config.ANIMATION);
        }});
        utils.facePlayer(entity, (0.56 * 20));
        yield (0.56 * 20);
        utils.applyImpulse(entity, 1.3, 8.2, -6);
        utils.getTargets(entity, {{
            position: utils.getPosForward(entity, 2),
            radius: (config.RADIUS + 3),
            target: "multiple",
            callback: (victim) => {{
                utils.normalizedKnockBack(entity.location, victim, 0.2, 1.7, 'default');
            }}
        }})
        utils.addEffect(entity, 'slow_falling', 3, 1);
        yield 20;
        while (!entity.isOnGround) {{
            utils.applyImpulse(entity, 0.5, -0.4, -0.1);
            utils.addEffect(entity, 'slow_falling', 1, 1);
            utils.facePlayer(entity, 1);
            yield 5; // Pause for 5 tick before re-checking
        }};

        yield (2.96 * 20);
    }}.bind(this);

    startCoroutineForBoss(active, () => {{
        if (!entity.isValid()) return;
        entity.addTag(utils.identifier('{attack_id}'));
        const setCoolDown = Date.now() + 100 * config.CAST_DURATION + config.COOLDOWN;
        utils.setAbilityCooldown(entity.id, '{attack_id}', setCoolDown);
        utils.resetAndReadyAbility(entity);
    }}, entity.id);
}}
"""
    }

    return templates.get(template_type, "Invalid template type!")


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
    switch_cases = ",\n".join([generate_switch_case(entity_name_camel, attack["id"]) for attack in mob["attacks"]])
    handlers_content = f"""// Handlers for {entity_name_camel} Attacks
import {{ {", ".join([entity_name_camel + to_camel_case(attack["id"]) for attack in mob["attacks"]])} }} from './functions';
import {{ identifier }} from '../../utils';

const attackHandlers = new Map([
{switch_cases}
]);

function handle{entity_name_camel}Attack(entity, attackId) {{
    if (entity.typeId !== identifier('{entity_name}')) return;

    const attackHandler = attackHandlers.get(attackId);
    if (attackHandler) attackHandler(entity);
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
    function_templates = "\n".join(
        generate_function_template(entity_name, attack["id"], attack.get("attack_type", "basic")) 
        for attack in mob["attacks"]
    )
    functions_content = f"""// Function Definitions for {entity_name_camel} Attacks
import {{ EntityDamageCause }} from "@minecraft/server";
import * as utils from '../../utils/index';
import {{ startCoroutineForBoss }} from "../../eventManager/CoroutineClass";
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
