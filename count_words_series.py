#!/usr/bin/env python3
import os
import re
import argparse
from pathlib import Path
from collections import Counter

def get_available_series(data_dir: Path):
    if not data_dir.exists():
        return []
    return sorted([item.name for item in data_dir.iterdir() if item.is_dir()])

def extract_text_from_srt(content: str) -> str:
    lines = content.split('\n')
    text_lines = []
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        if not line or line.isdigit() or '-->' in line:
            i += 1
            continue
        text_lines.append(line)
        i += 1
    return ' '.join(text_lines)

def extract_text_from_sub(content: str) -> str:
    lines = content.split('\n')
    text_lines = []
    for line in lines:
        line = line.strip()
        if not line or re.match(r'^\d{2}:\d{2}:\d{2}', line) or line.isdigit():
            continue
        text_lines.append(line)
    return ' '.join(text_lines)

def clean_text(text: str) -> str:
    text = re.sub(r'<[^>]+>', '', text)
    text = text.replace('\u2019', "'").replace('\u2018', "'")
    text = text.replace('\u2013', ' ').replace('\u2014', ' ').replace('\u2212', ' ')
    return text

def count_words_in_file(file_path: Path) -> Counter:
    try:
        with open(file_path, 'r', encoding='cp1252', errors='ignore') as f:
            content = f.read()
    except UnicodeDecodeError:
        try:
            with open(file_path, 'r', encoding='latin-1', errors='ignore') as f:
                content = f.read()
        except:
            return Counter()
    except:
        return Counter()
    
    if file_path.suffix.lower() == '.srt':
        text = extract_text_from_srt(content)
    elif file_path.suffix.lower() == '.sub':
        text = extract_text_from_sub(content)
    else:
        return Counter()
    
    text = clean_text(text).lower()
    tokens = re.findall(r"\w+(?:['-]\w+)*", text, flags=re.UNICODE)
    return Counter(tokens)

def count_words_in_series(series_dir: Path) -> Counter:
    subtitle_files = list(series_dir.glob('*.srt')) + list(series_dir.glob('*.sub'))
    total_counter = Counter()
    for file_path in subtitle_files:
        total_counter.update(count_words_in_file(file_path))
    return total_counter

def save_word_count(counter: Counter, output_file: Path):
    with open(output_file, 'w', encoding='utf-8') as f:
        for word, count in counter.most_common():
            f.write(f"{word}:{count}\n")

def main():
    parser = argparse.ArgumentParser(description="Compter les mots dans les fichiers SRT/SUB de chaque série")
    parser.add_argument('--data-dir', type=str, required=True, help="Dossier contenant les séries (chaque sous-dossier = une série)")
    args = parser.parse_args()
    
    data_dir = Path(args.data_dir)
    if not data_dir.exists():
        print(f"❌ Dossier introuvable : {data_dir}")
        return

    word_freq_dir = data_dir.parent / "data_word_frequency"
    word_freq_dir.mkdir(exist_ok=True)
    
    series_list = get_available_series(data_dir)
    if not series_list:
        print("❌ Aucun sous-dossier trouvé dans le dossier principal.")
        return
    
    for series_name in series_list:
        series_dir = data_dir / series_name
        word_counter = count_words_in_series(series_dir)
        if word_counter:
            output_file = word_freq_dir / f"{series_name}.txt"
            save_word_count(word_counter, output_file)
            print(f"✅ {series_name}: {sum(word_counter.values())} mots traités")
        else:
            print(f"⚠️ {series_name}: aucun fichier SRT/SUB trouvé ou vide")

if __name__ == "__main__":
    main()
