#!/usr/bin/env python3
from pathlib import Path

# Stopwords FR + custom
STOPWORDS_FR = {
    "alors","au","aucuns","aussi","autre","avant","avec","avoir","bon",
    "car","ce","cela","ces","ceux","chaque","ci","comme","comment","dans",
    "des","du","dedans","dehors","depuis","devrait","doit","donc","dos",
    "début","elle","elles","en","encore","essai","est","et","eu","fait",
    "faites","fois","font","hors","ici","il","ils","je","juste","la","le",
    "les","leur","là","ma","maintenant","mais","mes","mine","moins","mon",
    "même","ni","nommés","notre","nous","nouveaux","ou","où","par",
    "parce","parole","pas","personnes","peut","peu","pièce","plupart",
    "pour","pourquoi","quand","que","quel","quelle","quelles","quels",
    "qui","sa","sans","ses","seulement","si","sien","son","sont","sous",
    "soyez","sujet","sur","ta","tandis","tellement","tels","tes","ton",
    "tous","tout","trop","très","tu","valeur","voie","voient","vont",
    "votre","vous","vu","ça","étaient","état","étions","été","être",
    "moi","toi","lui","ex","non","re","ve","m","r","e","d","un","deux",
    "v","t","h"
}

# Stopwords EN
STOPWORDS_EN = {
    "a","about","above","after","again","against","all","am","an","and",
    "any","are","aren't","as","at","be","because","been","before","being",
    "below","between","both","but","by","can't","cannot","could","couldn't",
    "did","didn't","do","does","doesn't","doing","don't","down","during",
    "each","few","for","from","further","had","hadn't","has","hasn't","have",
    "haven't","having","he","he'd","he'll","he's","her","here","here's",
    "hers","herself","him","himself","his","how","how's","i","i'd","i'll",
    "i'm","i've","if","in","into","is","isn't","it","it's","its","itself",
    "let's","me","more","most","mustn't","my","myself","no","nor","not","of",
    "off","on","once","only","or","other","ought","our","ours","ourselves",
    "out","over","own","same","shan't","she","she'd","she'll","she's",
    "should","shouldn't","so","some","such","than","that","that's","the",
    "their","theirs","them","themselves","then","there","there's","these",
    "they","they'd","they'll","they're","they've","this","those","through",
    "to","too","under","until","up","very","was","wasn't","we","we'd","we'll",
    "we're","we've","were","weren't","what","what's","when","when's","where",
    "where's","which","while","who","who's","whom","why","why's","with",
    "won't","would","wouldn't","you","you'd","you'll","you're","you've",
    "your","yours","yourself","yourselves"
}

ALL_STOPWORDS = STOPWORDS_FR.union(STOPWORDS_EN)

def clean_file(file_path: Path, output_dir: Path):
    output_file = output_dir / file_path.name
    with open(file_path, "r", encoding="utf-8") as f_in, open(output_file, "w", encoding="utf-8") as f_out:
        for line in f_in:
            if ":" not in line:
                continue
            word, count = line.strip().split(":", 1)
            word_clean = word.strip().lower()
            count = count.strip()
            # Supprimer si stopword ou longueur <= 2
            if word_clean not in ALL_STOPWORDS and len(word_clean) > 2:
                f_out.write(f"{word}:{count}\n")  # garde le mot tel quel (majuscules incluses)
    print(f"{file_path.name} nettoyé → {output_file}")

def main():
    data_dir = Path("data_word_frequency")
    output_dir = Path("data_word_frequency_clean")
    output_dir.mkdir(exist_ok=True)

    txt_files = list(data_dir.glob("*.txt"))
    if not txt_files:
        print("⚠ Aucun fichier trouvé dans data_word_frequency")
        return

    for file_path in txt_files:
        clean_file(file_path, output_dir)

    print("✅ Nettoyage terminé (stopwords + mots <=2 lettres supprimés).")

if __name__ == "__main__":
    main()
