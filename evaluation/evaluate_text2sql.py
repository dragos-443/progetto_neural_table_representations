import json
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_DIR = Path(__file__).resolve().parent
for path in (PROJECT_ROOT, SCRIPT_DIR):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from config import MODEL, get_text2sql_evaluation_dir, get_text2sql_results_dir
from metrics import (
    cell_precision,
    cell_recall,
    tuple_cardinality,
    tuple_constraint,
    tuple_order,
)


TEXT2SQL_PATH = get_text2sql_results_dir(MODEL) / "text2sql_results.json"
OUTPUT_PATH = get_text2sql_evaluation_dir(MODEL) / "text2sql_evaluation.json"


def exact_match(pred_rows, gold_rows):
    pred_norm = sorted([
        tuple(str(cell).strip().lower() for cell in row)
        for row in pred_rows
    ])

    gold_norm = sorted([
        tuple(str(cell).strip().lower() for cell in row)
        for row in gold_rows
    ])

    return pred_norm == gold_norm


def main():
    with open(TEXT2SQL_PATH, "r", encoding="utf-8") as f:
        text2sql_data = json.load(f)

    results = []

    for item in text2sql_data:
        example_id = item["id"]
        db_id = item["db_id"]
        question = item["question"]

        gold_result = item["gold_result"]
        pred_result = item["predicted_result"]

        gold_rows = gold_result["rows"] if gold_result["success"] else []
        pred_rows = pred_result["rows"] if pred_result["success"] else []

        precision = cell_precision(pred_rows, gold_rows)
        recall = cell_recall(pred_rows, gold_rows)
        cardinality_error = tuple_cardinality(pred_rows, gold_rows)
        order_score = tuple_order(pred_rows, gold_rows)
        constraint_score = tuple_constraint(pred_rows, gold_rows)
        match = exact_match(pred_rows, gold_rows)

        result_item = {
            "id": example_id,
            "db_id": db_id,
            "question": question,
            "gold_sql": item["gold_sql"],
            "predicted_sql": item["predicted_sql"],
            "gold_rows": gold_rows,
            "pred_rows": pred_rows,
            "cell_precision": precision,
            "cell_recall": recall,
            "tuple_cardinality_error": cardinality_error,
            "tuple_order": order_score,
            "tuple_constraint": constraint_score,
            "exact_match": match,
            "execution_success": pred_result["success"],
            "execution_error": pred_result["error"],
        }

        results.append(result_item)

        print("=" * 80)
        print(f"Esempio {example_id}")
        print(f"DB: {db_id}")
        print(question)
        print("Gold SQL:", item["gold_sql"])
        print("Pred SQL:", item["predicted_sql"])
        print("Gold:", gold_rows)
        print("Pred:", pred_rows)

        if not pred_result["success"]:
            print("Errore SQL:", pred_result["error"])

        print(f"Cell Precision: {precision:.2f}")
        print(f"Cell Recall: {recall:.2f}")
        print(f"Tuple Cardinality Error: {cardinality_error}")
        print(f"Tuple Order: {order_score}")
        print(f"Tuple Constraint: {constraint_score}")
        print("Exact match:", "✅" if match else "❌")

    avg_precision = sum(r["cell_precision"] for r in results) / len(results)
    avg_recall = sum(r["cell_recall"] for r in results) / len(results)
    avg_cardinality = sum(r["tuple_cardinality_error"] for r in results) / len(results)
    avg_tuple_order = sum(r["tuple_order"] for r in results) / len(results)
    avg_tuple_constraint = sum(r["tuple_constraint"] for r in results) / len(results)
    exact_accuracy = sum(1 for r in results if r["exact_match"]) / len(results)
    execution_success_rate = sum(1 for r in results if r["execution_success"]) / len(results)

    summary = {
        "num_examples": len(results),
        "avg_cell_precision": avg_precision,
        "avg_cell_recall": avg_recall,
        "avg_tuple_cardinality_error": avg_cardinality,
        "avg_tuple_order": avg_tuple_order,
        "avg_tuple_constraint": avg_tuple_constraint,
        "exact_match_accuracy": exact_accuracy,
        "execution_success_rate": execution_success_rate,
    }

    output = {
        "summary": summary,
        "results": results,
    }

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)

    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)

    print("\n" + "=" * 80)
    print("TEXT2SQL SUMMARY")
    print(f"Avg Cell Precision: {avg_precision:.2f}")
    print(f"Avg Cell Recall: {avg_recall:.2f}")
    print(f"Avg Tuple Cardinality Error: {avg_cardinality:.2f}")
    print(f"Avg Tuple Order: {avg_tuple_order:.2f}")
    print(f"Avg Tuple Constraint: {avg_tuple_constraint:.2f}")
    print(f"Exact Match Accuracy: {exact_accuracy:.2f}")
    print(f"Execution Success Rate: {execution_success_rate:.2f}")
    print("\nSalvato in:", OUTPUT_PATH)


if __name__ == "__main__":
    main()


