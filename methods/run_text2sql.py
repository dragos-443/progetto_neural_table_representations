import json
import os
import sqlite3
import sys
from pathlib import Path
from openai import OpenAI
from dotenv import load_dotenv


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from config import MODEL, get_text2sql_results_dir


SUBSET_PATH = Path("data/mini_spider_subset.json")
SCHEMA_PATH = Path("data/db_schemas.json")
OUTPUT_PATH = get_text2sql_results_dir(MODEL) / "text2sql_results.json"
SPIDER_DB_DIR = Path("spider/database")

# carico le variabili dal file .env
load_dotenv()

# inizializzo il client OpenAI usando la API key
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# costruisco il prompt da inviare all'LLM
def build_prompt(schema_text, question):
    return f"""
You are a Text-to-SQL system.

Given the database schema and the natural language question,
generate a valid SQLite SQL query.

Return ONLY the SQL query. Do not add explanations.

DATABASE SCHEMA:
{schema_text}

QUESTION:
{question}
""".strip()

# invio il prompt al modello LLM
def call_llm(prompt):
    response = client.chat.completions.create(
        model=MODEL,
        #temperature=0, # per output più deterministici, funziona con gpt-4o-mini ma non con gpt-5.5 (che è più creativo)
        messages=[
            {"role": "user", "content": prompt}
        ],
    )

    # estraggo la query SQL generata dal modello
    sql = response.choices[0].message.content.strip()

    # rimuovo eventuali blocchi markdown ```sql
    sql = sql.replace("```sql", "").replace("```", "").strip()

    return sql

# eseguo una query SQL sul database SQLite
def execute_sql(db_id, sql):

    # costruisco il percorso del database
    db_path = SPIDER_DB_DIR / db_id / f"{db_id}.sqlite"

    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute(sql)

        rows = cursor.fetchall()
        columns = [desc[0] for desc in cursor.description] if cursor.description else []

        conn.close()

        # restituisco il risultato della query
        return {
            "success": True,
            "columns": columns,
            "rows": rows,
            "error": None,
        }

    except Exception as e:
        return {
            "success": False,
            "columns": [],
            "rows": [],
            "error": str(e),
        }


def normalize(rows):
    return sorted([tuple(str(cell).strip().lower() for cell in row) for row in rows])


# confronto tra risultato gold e risultato predetto
def compare_results(res1, res2):
    if not res1["success"] or not res2["success"]:
        return False

    return normalize(res1["rows"]) == normalize(res2["rows"])


def main():
    with open(SUBSET_PATH, "r", encoding="utf-8") as f:
        examples = json.load(f)

    with open(SCHEMA_PATH, "r", encoding="utf-8") as f:
        schemas = json.load(f)

    results = []

    for i, ex in enumerate(examples, start=1):
        db_id = ex["db_id"]
        question = ex["question"]
        gold_sql = ex["query"]

        schema_text = schemas[db_id]["prompt_text"]
        prompt = build_prompt(schema_text, question)

        predicted_sql = call_llm(prompt)

        gold_result = execute_sql(db_id, gold_sql)
        predicted_result = execute_sql(db_id, predicted_sql)

        match = compare_results(gold_result, predicted_result)

        print("=" * 80)
        print(f"Esempio {i}")
        print(f"DB: {db_id}")

        print("\nDomanda:")
        print(question)

        print("\nSQL gold:")
        print(gold_sql)

        print("\nSQL generata:")
        print(predicted_sql)

        print("\nOutput gold:")
        print(gold_result["rows"])

        print("\nOutput predetto:")
        print(predicted_result["rows"])

        if not predicted_result["success"]:
            print("\nErrore SQL:")
            print(predicted_result["error"])

        print("\nMatch output:", "✅" if match else "❌")

        results.append({
            "id": i,
            "db_id": db_id,
            "question": question,
            "gold_sql": gold_sql,
            "predicted_sql": predicted_sql,
            "gold_result": gold_result,
            "predicted_result": predicted_result,
            "match": match,
        })

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)

    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)

    print("\nRisultati salvati in:", OUTPUT_PATH)


    total = len(results)
    correct = sum(1 for r in results if r["match"])

    print("\n" + "=" * 80)
    print(f"Accuracy: {correct}/{total} = {correct/total:.2f}")


if __name__ == "__main__":
    main()


