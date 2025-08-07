import json
import unicodedata

def convert_to_english(name):
    """
    Convert accented characters to their English equivalents.
    """
    # Normalize Unicode characters and convert to ASCII
    # This will convert accented characters to their closest English equivalents
    normalized = unicodedata.normalize('NFKD', name)
    ascii_name = normalized.encode('ASCII', 'ignore').decode('ASCII')
    
    return ascii_name

def convert_json_file(input_file, output_file):
    """
    Read JSON file, convert all player names to English equivalents, and save to new file.
    """
    try:
        # Read the JSON file
        with open(input_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        # Convert names
        changes_made = 0
        for player in data:
            if 'name' in player:
                original_name = player['name']
                english_name = convert_to_english(original_name)
                if original_name != english_name:
                    print(f"Converted: '{original_name}' -> '{english_name}'")
                    player['name'] = english_name
                    changes_made += 1
        
        # Save converted data
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=4, ensure_ascii=False)
        
        print(f"\nConversion complete!")
        print(f"Changes made: {changes_made}")
        print(f"Output saved to: {output_file}")
        
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    # Convert the normalized file to English equivalents
    convert_json_file('players_pl_normalized.json', 'players_pl_english.json')
