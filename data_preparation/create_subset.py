import json
import os
import re
from pathlib import Path

INPUT_PATH = Path("spider/dev.json")                # file di input (Spider)
OUTPUT_PATH = Path("data/mini_spider_subset.json")  # file di output (subset)

TARGET_DBS = {"concert_singer", "pets_1"}           # database che vogliamo usare

# prende i primi 5 esempi per ogni database selezionato, funzione usata inizialmente sostituita da select_interesting_examples
def select_first_examples(data):
    # lista che conterrà il sottoinsieme selezionato
    subset = []

    # massimo numero di esempi per ogni database 
    max_per_db = 10

    # numero totale di esempi da selezionare
    TOTAL_EXAMPLES = 20

    # contatore totale degli esempi selezionati
    total_selected = 0

    # contatore per tracciare quanti esempi sono stati presi per ciascun DB
    counts = {db: 0 for db in TARGET_DBS}

    # insieme delle query gia' viste dopo normalizzazione
    seen_queries = set()

    # scorre tutti gli esempi del dataset
    for ex in data:
        db = ex["db_id"]

        # se il database è tra quelli scelti e non abbiamo ancora raggiunto il limite
        if db in TARGET_DBS and counts[db] < max_per_db:
            normalized_query = normalize_query(ex["query"])

            # salta query SQL duplicate o scritte con spazi diversi
            if normalized_query in seen_queries:
                continue

            # aggiunge l'esempio al sottoinsieme mantenendo solo i campi utili
            subset.append({
                "db_id": db,
                "question": ex["question"],
                "query": ex["query"]
            })
            seen_queries.add(normalized_query)

            # aggiorna il contatore per quel database
            counts[db] += 1
            total_selected += 1  # aggiorna totale


        # interrompe quando si raggiungono 10 esempi totali
        if total_selected >= TOTAL_EXAMPLES:
            break

    return subset
SQL_COMPLEXITY_PATTERNS = [
    r"\bJOIN\b",
    r"\bGROUP\s+BY\b",
    r"\bORDER\s+BY\b",
    r"\bWHERE\b",
    r"\bCOUNT\s*\(",
    r"\bAVG\s*\(",
    r"\bMAX\s*\(",
    r"\bMIN\s*\(",
    r"\bLIMIT\b",
]

###     VADO A SELEZIONARE ESEMPI PIU' INTERESANTI      ###
def normalize_query(query):
    # normalizza la query per riconoscere duplicati scritti con spazi diversi
    return " ".join(query.lower().split())


def sql_complexity_score(query):
    # assegna un punteggio in base alle operazioni SQL piu' informative
    return sum(
        1
        for pattern in SQL_COMPLEXITY_PATTERNS
        if re.search(pattern, query, re.IGNORECASE)
    )


def format_example(ex):
    # mantiene solo i campi necessari per il benchmark
    return {
        "db_id": ex["db_id"],
        "question": ex["question"],
        "query": ex["query"]
    }


def select_interesting_examples(data):
    # seleziona query piu' varie e informative, evitando duplicati SQL
    max_per_db = 10
    seen_queries = set()
    candidates = {db: [] for db in TARGET_DBS}

    for index, ex in enumerate(data):
        db = ex["db_id"]

        if db not in TARGET_DBS:
            continue

        normalized_query = normalize_query(ex["query"])
        if normalized_query in seen_queries:
            continue

        seen_queries.add(normalized_query)
        candidates[db].append({
            "index": index,
            "score": sql_complexity_score(ex["query"]),
            "example": format_example(ex)
        })

    subset = []
    for db in TARGET_DBS:
        db_examples = sorted(
            candidates[db],
            key=lambda item: (-item["score"], item["index"])
        )
        subset.extend(item["example"] for item in db_examples[:max_per_db])

    return subset


def main():
    # apre il file JSON di input e carica i dati
    with open(INPUT_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)

    #subset = select_first_examples(data)
    subset = select_interesting_examples(data)

    print(f"Esempi selezionati: {len(subset)}")

    # crea cartella data se non esiste
    os.makedirs("data", exist_ok=True)

    # salva il sottoinsieme in un file JSON, OUTPUT_PATH = "data/mini_spider_subset.json" 
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(subset, f, indent=2, ensure_ascii=False)

    print("Salvato in:", OUTPUT_PATH)

    # stampa una preview delle domande selezionate
    for i, ex in enumerate(subset, 1):
        print(f"\n{i}. [{ex['db_id']}] {ex['question']}")

if __name__ == "__main__":
    main()
