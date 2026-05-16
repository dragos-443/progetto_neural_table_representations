import json
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_DIR = Path(__file__).resolve().parent
for path in (PROJECT_ROOT, SCRIPT_DIR):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from config import MODEL, get_tableqa_evaluation_dir, get_tableqa_results_dir
from metrics import (
    cell_precision,
    cell_recall,
    tuple_cardinality,
    tuple_constraint,
    tuple_order,
)


GROUND_TRUTH_PATH = Path("data/ground_truth_results.json")
SERIALIZATION_STRATEGIES = ["row_wise", "natural_language", "special_tokens"]
PROMPTING_MODES = ["few_shot", "zero_shot"]
TABLEQA_RESULTS_DIR = get_tableqa_results_dir(MODEL)
TABLEQA_EVALUATION_DIR = get_tableqa_evaluation_dir(MODEL)


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


def evaluate_strategy(gold_data, strategy, mode):
    """
    Valuta una strategia di serializzazione e una modalità di prompting.
    Ritorna il dizionario con i risultati, oppure None se il file non esiste.
    """
    tableqa_path = TABLEQA_RESULTS_DIR / f"tableqa_results_{strategy}_{mode}.json"
    
    # Controlla se il file esiste
    if not tableqa_path.exists():
        print(f"⚠️  File non trovato: {tableqa_path}")
        return None
    
    # Carica i risultati della strategia
    with open(tableqa_path, "r", encoding="utf-8") as f:
        tableqa_data = json.load(f)
    
    results = []
    
    # Valuta ogni esempio
    for gold_item, pred_item in zip(gold_data, tableqa_data):
        example_id = gold_item["id"]
        db_id = gold_item["db_id"]
        question = gold_item["question"]
        
        gold_result = gold_item["gold_result"]
        pred_result = pred_item["predicted_result"]
        
        gold_rows = gold_result["rows"] if gold_result["success"] else []
        pred_rows = pred_result["rows"] if pred_result["success"] else []
        
        precision = cell_precision(pred_rows, gold_rows)
        recall = cell_recall(pred_rows, gold_rows)
        cardinality_error = tuple_cardinality(pred_rows, gold_rows)
        order_score = tuple_order(pred_rows, gold_rows)
        constraint_score = tuple_constraint(pred_rows, gold_rows)
        match = exact_match(pred_rows, gold_rows)
        
        item = {
            "id": example_id,
            "db_id": db_id,
            "question": question,
            "serialization_strategy": strategy,
            "prompting_mode": mode,
            "gold_rows": gold_rows,
            "pred_rows": pred_rows,
            "cell_precision": precision,
            "cell_recall": recall,
            "tuple_cardinality_error": cardinality_error,
            "tuple_order": order_score,
            "tuple_constraint": constraint_score,
            "exact_match": match,
        }
        
        results.append(item)
        
        # Stampa il risultato per questo esempio
        print("=" * 80)
        print(f"Strategia: {strategy} - Modalità: {mode}")
        print(f"Esempio {example_id}")
        print(f"DB: {db_id}")
        print(question)
        print("Gold:", gold_rows)
        print("Pred:", pred_rows)
        print(f"Cell Precision: {precision:.2f}")
        print(f"Cell Recall: {recall:.2f}")
        print(f"Tuple Cardinality Error: {cardinality_error}")
        print(f"Tuple Order: {order_score}")
        print(f"Tuple Constraint: {constraint_score}")
        print("Exact match:", "✅" if match else "❌")
    
    # Calcola le medie
    avg_precision = sum(r["cell_precision"] for r in results) / len(results)
    avg_recall = sum(r["cell_recall"] for r in results) / len(results)
    avg_cardinality = sum(r["tuple_cardinality_error"] for r in results) / len(results)
    avg_tuple_order = sum(r["tuple_order"] for r in results) / len(results)
    avg_tuple_constraint = sum(r["tuple_constraint"] for r in results) / len(results)
    exact_accuracy = sum(1 for r in results if r["exact_match"]) / len(results)
    
    summary = {
        "serialization_strategy": strategy,
        "prompting_mode": mode,
        "num_examples": len(results),
        "avg_cell_precision": avg_precision,
        "avg_cell_recall": avg_recall,
        "avg_tuple_cardinality_error": avg_cardinality,
        "avg_tuple_order": avg_tuple_order,
        "avg_tuple_constraint": avg_tuple_constraint,
        "exact_match_accuracy": exact_accuracy,
    }
    
    output = {
        "summary": summary,
        "results": results,
    }
    
    # Salva i risultati per questa strategia
    output_path = TABLEQA_EVALUATION_DIR / f"tableqa_evaluation_{strategy}_{mode}.json"
    TABLEQA_EVALUATION_DIR.mkdir(parents=True, exist_ok=True)
    
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)
    
    print("\n" + "=" * 80)
    print(f"TABLE QA EVALUATION - {strategy.upper()} - {mode.upper()}")
    print(f"Num Examples: {len(results)}")
    print(f"Avg Cell Precision: {avg_precision:.2f}")
    print(f"Avg Cell Recall: {avg_recall:.2f}")
    print(f"Avg Tuple Cardinality Error: {avg_cardinality:.2f}")
    print(f"Avg Tuple Order: {avg_tuple_order:.2f}")
    print(f"Avg Tuple Constraint: {avg_tuple_constraint:.2f}")
    print(f"Exact Match Accuracy: {exact_accuracy:.2f}")
    print(f"Salvato in: {output_path}\n")
    
    return summary


def main():
    # Carica i ground truth (una sola volta)
    with open(GROUND_TRUTH_PATH, "r", encoding="utf-8") as f:
        gold_data = json.load(f)
    
    print("\n" + "=" * 80)
    print("TABLEQA MULTI-STRATEGY EVALUATION")
    print("=" * 80)
    print(f"Ground truth caricato da: {GROUND_TRUTH_PATH}")
    print(f"Numero di esempi: {len(gold_data)}\n")
    
    # Valuta ogni strategia e modalità
    strategies_summaries = {}
    
    for strategy in SERIALIZATION_STRATEGIES:
        for mode in PROMPTING_MODES:
            print(f"\n📊 Valutando strategia: {strategy} - modalità: {mode}")
            print("-" * 80)
            summary = evaluate_strategy(gold_data, strategy, mode)
            if summary:
                key = f"{strategy}_{mode}"
                strategies_summaries[key] = summary
    
    # Crea il file di confronto tra strategie e modalità
    comparison_path = TABLEQA_EVALUATION_DIR / "tableqa_evaluation_summary_by_strategy_and_mode.json"
    TABLEQA_EVALUATION_DIR.mkdir(parents=True, exist_ok=True)
    with open(comparison_path, "w", encoding="utf-8") as f:
        json.dump(strategies_summaries, f, indent=2, ensure_ascii=False)
    
    print("\n" + "=" * 80)
    print("CONFRONTO STRATEGIE E MODALITÀ")
    print("=" * 80)
    print(f"{'Strategia':<20} {'Modalità':<12} {'Precisione':<12} {'Recall':<12} {'Cardinality':<14} {'Exact Match':<12}")
    print("-" * 80)
    
    for key, summary in strategies_summaries.items():
        strategy = summary["serialization_strategy"]
        mode = summary["prompting_mode"]
        print(
            f"{strategy:<20} "
            f"{mode:<12} "
            f"{summary['avg_cell_precision']:<12.2f} "
            f"{summary['avg_cell_recall']:<12.2f} "
            f"{summary['avg_tuple_cardinality_error']:<14.2f} "
            f"{summary['exact_match_accuracy']:<12.2f}"
        )
    
    print("=" * 80)
    print(f"Confronto salvato in: {comparison_path}")


if __name__ == "__main__":
    main()

