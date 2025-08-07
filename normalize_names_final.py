import json
import re

def normalize_name(name):
    """
    Precise normalization of player names by fixing specific UTF-8 encoding issues.
    """
    # Specific encoding fixes - only target problematic patterns
    
    # Replace A(c) with é
    name = name.replace('A(c)', 'é')
    
    # Replace A! with á (but only when it's clearly an encoding issue)
    name = name.replace('A!', 'á')
    
    # Replace A+- with ñ
    name = name.replace('A+-', 'ñ')
    
    # Replace AP with ã
    name = name.replace('AP', 'ã')
    
    # Specific known problematic patterns
    specific_replacements = {
        'APSes': 'ães',  # Bruno Guimarães
        'ãSes': 'ães',   # Fix the remaining issue
        'DAaz': 'Díaz',  # Luis Díaz
        'MartAnez': 'Martínez',  # Emiliano Martínez
        'JimA(c)nez': 'Jiménez',  # Raúl Jiménez
        'DomAnguez': 'Domínguez',  # Nicolás Domínguez
        'LukiA': 'Lukić',  # Saša Lukić
        'EstupiA+-A!n': 'Estupiñán',  # Pervis Estupiñán
        'DurA!n': 'Durán',  # Jáder Durán
        'GarcAa': 'García',  # Andrés García
        'PeriA!iA': 'Perišić',  # Ivan Perišić
        'BayA+-ndA+-r': 'Bayındır',  # Altay Bayındır
        'FA(c)lix': 'Félix',  # João Félix
        'VA(c)liz': 'Véliz',  # Alejo Véliz
        'SA!vio': 'Sávio',  # Sávio
        'GonzA!lez': 'González',  # Nicolás González
        'AlcA!ntara': 'Alcántara',  # Thiago Alcántara
        'SA!nchez': 'Sánchez',  # Davinson Sánchez
        'Valdimarsson': 'Valdimarsson',  # Hákon Rafn Valdimarsson
        'NAoA+-ez': 'Núñez',  # Darwin Núñez
        'NAo': 'Nú',  # Fix NAo pattern
        'NA,r': 'Nør',  # Fix NA,r pattern
        'A(r)': 'î',  # Fix A(r) pattern
        'RaAol': 'Raúl',  # Fix RaAol pattern
        'MuA+-oz': 'Muñoz',  # Daniel Muñoz
        'MagalhAPSes': 'Magalhães',  # Gabriel Magalhães
        'KovaAiA': 'Kovačić',  # Mateo Kovačić
        'RAoben': 'Rúben',  # Rúben Dias
        'LindelAPf': 'Lindelöf',  # Victor Lindelöf
        'DAobravka': 'Dúbravka',  # Martin Dúbravka
        'Palhinha': 'Palhinha',  # João Palhinha
        'RodrAguez': 'Rodríguez',  # Guido Rodríguez
        'CaoimhAn': 'Caoimhín',  # Caoimhín Kelleher
        'VinAcius': 'Vinícius',  # Carlos Vinícius
        'FranASSa': 'França',  # Matheus França
        'BuendAa': 'Buendía',  # Emi Buendía
        'Barco': 'Barco',  # Valentín Barco
        'GrA,nbaek': 'Grønbaek',  # Albert Grønbaek
        'MitroviA': 'Mitrović',  # Aleksandar Mitrović
    }
    
    for pattern, replacement in specific_replacements.items():
        name = name.replace(pattern, replacement)
    
    return name

def normalize_json_file(input_file, output_file):
    """
    Read JSON file, normalize all player names, and save to new file.
    """
    try:
        # Read the JSON file
        with open(input_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        # Normalize names
        changes_made = 0
        for player in data:
            if 'name' in player:
                original_name = player['name']
                normalized_name = normalize_name(original_name)
                if original_name != normalized_name:
                    print(f"Fixed: '{original_name}' -> '{normalized_name}'")
                    player['name'] = normalized_name
                    changes_made += 1
        
        # Save normalized data
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=4, ensure_ascii=False)
        
        print(f"\nNormalization complete!")
        print(f"Changes made: {changes_made}")
        print(f"Output saved to: {output_file}")
        
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    # Normalize the main file
    normalize_json_file('players_pl.json', 'players_pl_normalized.json')
