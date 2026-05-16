import json
import sqlite3
from pathlib import Path


SUBSET_PATH = Path("data/mini_spider_subset.json")
OUTPUT_PATH = Path("data/ground_truth_results.json")
SPIDER_DB_DIR = Path("spider/database")


# eseguo una query SQL su un database di Spider
def execute_sql(db_id: str, sql: str):

    # costruisco il percorso del database
    db_path = SPIDER_DB_DIR / db_id / f"{db_id}.sqlite"

    # controllo che il database esista
    if not db_path.exists():
        return {
            "success": False,
            "columns": [],
            "rows": [],
            "error": f"Database not found: {db_path}",
        }


    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # eseguo la query SQL
        cursor.execute(sql)

        # recupero righe e nomi delle colonne
        rows = cursor.fetchall()
        columns = [desc[0] for desc in cursor.description] if cursor.description else []

        conn.close()

        # restituisco il risultato corretto della query
        return {
            "success": True,
            "columns": columns,
            "rows": rows,
            "error": None,
        }

    except Exception as e:

        # gestisco eventuali errori SQL
        return {
            "success": False,
            "columns": [],
            "rows": [],
            "error": str(e),
        }


def main():
    # carico gli esempi del subset
    with open(SUBSET_PATH, "r", encoding="utf-8") as f:
        examples = json.load(f)

    # lista che conterrà i risultati ground truth
    results = []

    # eseguo la query gold per ogni esempio
    for i, ex in enumerate(examples, start=1):
        db_id = ex["db_id"]
        question = ex["question"]
        gold_sql = ex["query"]

        # eseguo la query SQL corretta
        result = execute_sql(db_id, gold_sql)

        # salvo domanda, SQL e risultato ottenuto
        output_item = {
            "id": i,
            "db_id": db_id,
            "question": question,
            "gold_sql": gold_sql,
            "gold_result": result,
        }

        results.append(output_item)

        # stampo una preview del risultato
        print("=" * 80)
        print(f"Esempio {i}")
        print(f"DB: {db_id}")
        print(f"Domanda: {question}")
        print(f"SQL gold: {gold_sql}")

        if result["success"]:
            print("Colonne:", result["columns"])
            print("Righe:", result["rows"])
        else:
            print("Errore:", result["error"])

    # creo la cartella di output se non esiste
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)

    # salvo i risultati ground truth nel file JSON
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)

    print("\nSalvato in:", OUTPUT_PATH)


if __name__ == "__main__":
    main()

