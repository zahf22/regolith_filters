import sys
import os
import json
import zipfile
from typing import List, Dict, NamedTuple
from enum import Enum

from reticulator import *

def unzip_file(file, input_path, output_path):
    print("Current working directory:", os.getcwd())
    zip_path = os.path.join(input_path, file)
    print(f"Attempting to unzip: {zip_path}")
    print(f"Output directory: {output_path}")

    # Ensure the output directory exists
    os.makedirs(output_path, exist_ok=True)

    with zipfile.ZipFile(zip_path, 'r') as zip_ref:
        for member in zip_ref.infolist():
            member_path = os.path.join(output_path, member.filename)

            # Check if file already exists
            if os.path.exists(member_path):
                print(f"File '{member.filename}' already exists. Skipping extraction.")
                continue

            # Ensure the directory exists
            os.makedirs(os.path.dirname(member_path), exist_ok=True)

            # Extract the file
            try:
                with zip_ref.open(member) as source, open(member_path, 'wb') as target:
                    target.write(source.read())
                print(f"Extracted '{member.filename}'.")
            except Exception as e:
                print(f"Error extracting '{member.filename}': {e}")

        print(f"Finished processing zip archive: {zip_path}")
        
def get_jsonpath(data, path, default=None):
    keys = [k for k in path.strip('/').split('/') if k]
    current = data
    for key in keys:
        if isinstance(current, dict):
            current = current.get(key, default)
        elif isinstance(current, list):
            try:
                index = int(key)
                current = current[index]
            except (ValueError, IndexError):
                return default
        else:
            return default
        if current is None:
            return default
    return current

class NameJsonPath(NamedTuple):
    path: str
    should_pop: bool = False
    add_affixes: bool = False

def format_name(name):
    parts = name.split(":")
    if len(parts) == 2:
        return parts[1].replace("_", " ").title()
    else:
        return name.replace("_", " ").title()

def get_json_value(asset, path, should_pop):
    try:
        if should_pop:
            return asset.pop_jsonpath(path)
        else:
            return get_jsonpath(asset.data, path)
    except Exception as e:
        return None

def assign_translation_value(path, value, translation_dict, key_list):
    for key in key_list:
        if key in path:
            translation_dict[key] = value

def process_asset(asset, jsonpaths_list, key_list):
    translation_data = {}
    for jsonpaths in jsonpaths_list:
        for jp in jsonpaths:
            value = get_json_value(asset, jp.path, jp.should_pop)
            if value is not None:
                assign_translation_value(jp.path, value, translation_data, key_list)
    return translation_data

def gather_translations(
    assets: List[JsonFileResource],
    settings: dict,
    jsonpaths_list: List[List[NameJsonPath]],
    ignored_namespaces: List[str],
    key_list: List[str],
) -> Dict[str, Dict[str, str]]:
    all_translations: Dict[str, Dict[str, str]] = {}
    auto_name = settings.get('auto_name', False)

    for asset in assets:
        try:
            identifier = asset.identifier
        except AssetNotFoundError:
            continue

        namespace = identifier.split(':')[0] if ':' in identifier else ''
        if namespace in ignored_namespaces:
            continue

        short_id = identifier.split(':')[1]
        if short_id not in all_translations:
            all_translations[short_id] = {}

        translation_info = process_asset(asset, jsonpaths_list, key_list)
        all_translations[short_id].update(translation_info)

    return all_translations

def save_translation_file(base_path, subfolder, filename, content):
    dir_path = os.path.join(base_path, "scripts", subfolder)
    os.makedirs(dir_path, exist_ok=True)
    file_path = os.path.join(dir_path, filename)
    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(content + "\n")

def filter_entries_with_props(translations):
    return {k: v for k, v in translations.items() if v}

def generate_js_object_str(translations_filtered, var_name):
    lines = []
    lines.append(f"export const {var_name} = {{")
    for idx, (name, props) in enumerate(translations_filtered.items()):
        lines.append(f"  {name}: {{")
        prop_items = list(props.items())

        for p_idx, (prop_key, prop_value) in enumerate(prop_items):
            if prop_key in ['recipe', 'pattern']:
                val_str = json.dumps(prop_value)
                lines.append(f"    {prop_key}: {val_str}" + ("," if p_idx < len(prop_items) - 1 else ""))
            else:
                if isinstance(prop_value, dict):
                    val_str = json.dumps(prop_value)
                    lines.append(f"    {prop_key}: {val_str}" + ("," if p_idx < len(prop_items) - 1 else ""))
                elif isinstance(prop_value, list):
                    val_str = json.dumps(prop_value)
                    lines.append(f"    {prop_key}: {val_str}" + ("," if p_idx < len(prop_items) - 1 else ""))
                else:
                    val_str = str(prop_value).replace('"', '\\"')
                    lines.append(f"    {prop_key}: \"{val_str}\"" + ("," if p_idx < len(prop_items) - 1 else ""))
        comma = "," if idx < len(translations_filtered) - 1 else ""
        lines.append(f"  }}{comma}")
    lines.append("};")
    return "\n".join(lines)

def map_pattern_grid(patterns):
    slot_mapping = {}
    slot_number = 1
    
    for row in patterns:
        for ch in row:
            key = f"slot_{slot_number}"
            if ch.strip():
                slot_mapping[key] = ch
            else:
                slot_mapping[key] = None
            slot_number += 1
            
    return slot_mapping

def main():
    # Load settings
    try:
        settings = json.loads(sys.argv[1])
    except IndexError:
        #print("Warning: No settings provided. Using default settings.")
        settings = {}

    ignored_namespaces = settings.get("ignored_namespaces", ['minecraft'])

    project = Project("./BP", "./RP")
    behavior_pack = project.behavior_pack
    resource_pack = project.resource_pack

    # --- Generate NameJsonPath objects dynamically based on key_list ---

    key_list = settings.get("key_list", [])

    # For entities
    entity_jsonpaths = []
    for key in key_list:
        path = f"minecraft:entity/description/{key}"
        entity_jsonpaths.append(NameJsonPath(path, True, False))
    entity_jsonpaths_list = [entity_jsonpaths]

    # For blocks
    block_jsonpaths = []
    for key in key_list:
        path = f"minecraft:block/description/{key}"
        block_jsonpaths.append(NameJsonPath(path, True, False))
    block_jsonpaths_list = [block_jsonpaths]

    # For recipes
    recipe_jsonpaths = []
    for key in key_list:
        path = f"minecraft:recipe_shaped/{key}"
        recipe_jsonpaths.append(NameJsonPath(path, False, False))
    recipe_jsonpaths_list = [recipe_jsonpaths]

    # For items
    item_jsonpaths = []
    for key in key_list:
        path = f"minecraft:item/description/{key}"
        item_jsonpaths.append(NameJsonPath(path, True, False))
    item_jsonpaths_list = [item_jsonpaths]

    # Gather entity translations
    entity_translations = gather_translations(
        behavior_pack.entities,
        settings.get("entity", {}),
        entity_jsonpaths_list,
        ignored_namespaces,
        key_list
    )

    # Gather block translations
    block_translations = gather_translations(
        behavior_pack.blocks,
        settings.get("blocks", {}),
        block_jsonpaths_list,
        ignored_namespaces,
        key_list
    )

    # Gather recipe translations
    recipe_translations = gather_translations(
        behavior_pack.recipes,
        settings.get("recipes", {}),
        recipe_jsonpaths_list,
        ignored_namespaces,
        key_list
    )

    # Gather item translations
    item_translations = gather_translations(
        behavior_pack.items,
        settings.get("items", {}),
        item_jsonpaths_list,
        ignored_namespaces,
        key_list
    )

    # Filter entries
    recipe_translations_filtered = filter_entries_with_props(recipe_translations)
    entity_translations_filtered = filter_entries_with_props(entity_translations)
    block_translations_filtered = filter_entries_with_props(block_translations)
    item_translations_filtered = filter_entries_with_props(item_translations)

    # --- Build recipe_lookup from recipe assets ---
    recipe_lookup = {}
    for recipe_asset in behavior_pack.recipes:
        recipe_id = recipe_asset.identifier  # e.g., 'minecraft:some_recipe'
        recipe_data = recipe_asset.data
        if isinstance(recipe_data, dict) and 'key' in recipe_data:
            recipe_lookup[recipe_id] = recipe_data['key']

    def associate_recipe_with_translations(recipe_translations_filtered, filtered_translations_dict, name_key='name'):
        for item_name, item_data in filtered_translations_dict.items():
            recipe_id = item_data.get('recipe')
            if not recipe_id:
                continue  # No recipe property; skip
            if recipe_id not in recipe_translations_filtered:
                print(f"{item_name}: recipe ID '{recipe_id}' not in recipeTranslations")
                continue
            recipe_data = recipe_translations_filtered[recipe_id]
            key_value = recipe_data.get('key', None)
            pattern = recipe_data.get('pattern', None)
            print(f"Before assignment: {filtered_translations_dict[item_name]}")

            # Parse key if JSON string
            if isinstance(key_value, str):
                try:
                    recipe_obj = json.loads(key_value)
                except json.JSONDecodeError:
                    print(f"Failed to parse JSON for recipe ID '{recipe_id}'")
                    recipe_obj = key_value
            else:
                recipe_obj = key_value

            # Assign recipe object and pattern
            filtered_translations_dict[item_name]['recipe'] = recipe_obj
            filtered_translations_dict[item_name]['pattern'] = map_pattern_grid(pattern)

            print(f"After assignment: {filtered_translations_dict[item_name]}")

    # Apply for blocks
    associate_recipe_with_translations(
        recipe_translations_filtered, block_translations_filtered, 'block'
    )

    # Apply for items
    associate_recipe_with_translations(
        recipe_translations_filtered, item_translations_filtered, 'item'
    )

    # Apply for entities
    associate_recipe_with_translations(
        recipe_translations_filtered, entity_translations_filtered, 'entity'
    )

    # Generate JS strings
    entity_object_str = generate_js_object_str(entity_translations_filtered, "blockTranslations")
    block_object_str = generate_js_object_str(block_translations_filtered, "blockTranslations")
    item_object_str = generate_js_object_str(item_translations_filtered, "itemTranslations")

    # Save files
    short_path = settings.get('short_path', '')
    base_path = '../../packs'

    save_translation_file(base_path, short_path, "entity_translations.js", entity_object_str)
    save_translation_file(base_path, short_path, "block_translations.js", block_object_str)
    save_translation_file(base_path, short_path, "item_translations.js", item_object_str)
    file = 'guidebook.zip'
    output_path = os.path.join(base_path, 'scripts', '5fs', 'apt')
    unzip_file(file, '../cache/filters/guidebook', output_path)

    # Save project
    project.save()

if __name__ == "__main__":
    main() 