"""
Evaluation script CLI wrapper for PII Redaction Pipeline.
"""

import argparse
from evaluate import evaluate

def main():
    parser = argparse.ArgumentParser(description="Evaluate PII redaction against ground truth annotations.")
    parser.add_argument("--ground-truth", default="ground_truth.json", help="Path to ground truth JSON file")
    parser.add_argument("--prospectus", default="input/Red Herring Prospectus.docx", help="Path to prospectus DOCX")
    parser.add_argument("--iou", type=float, default=0.3, help="IoU threshold for overlap matching")
    parser.add_argument("--show-errors", action="store_true", help="Print detailed list of false positives / negatives")
    
    args = parser.parse_args()
    
    res = evaluate(args.ground_truth, args.prospectus, args.iou)
    
    print("\n" + "=" * 80)
    print("                      PII REDACTION EVALUATION REPORT")
    print("=" * 80 + "\n")
    
    print("### Entity-Level Performance (Overlap Matching)\n")
    print(res["df_metrics"].to_string(index=False))
    
    print("\n" + "-" * 80 + "\n")
    print(f"• Total Ground Truth Spans:   {res['total_support']}")
    print(f"• Micro Precision:            {res['micro_p']:.2f}%  (TP / (TP + FP))")
    print(f"• Micro Recall:               {res['micro_r']:.2f}%  (TP / (TP + FN))")
    print(f"• Micro F1-Score:             {res['micro_f1']:.2f}%  (Harmonic Mean of Precision & Recall)")
    print(f"• Macro F1-Score:             {res['macro_f1']:.2f}%")
    print(f"• Span Jaccard Accuracy:      {res['span_jaccard_accuracy']:.2f}%  (TP / (TP + FP + FN))")
    print(f"• Block Perfect Pass Rate:    {res['perfect_sample_rate']:.2f}%  ({res['perfect_samples_count']}/{res['total_samples']} blocks with 0 FP and 0 FN)")
    print("\n" + "=" * 80 + "\n")
    
    if args.show_errors:
        if res["type_confusions"]:
            print(f"### Type Confusions ({len(res['type_confusions'])})\n")
            for tc in res["type_confusions"]:
                print(f"[{tc['sample_id']}] Expected: {tc['expected_type']} (\"{tc['expected_text']}\") vs Predicted: {tc['predicted_type']} (\"{tc['predicted_text']}\")\n")
        
        if res["false_positives"]:
            print(f"### False Positives ({len(res['false_positives'])})\n")
            for fp in res["false_positives"]:
                print(f"[{fp['sample_id']}] FP ({fp['entity_type']}): \"{fp['text']}\" {fp['span']}\n  Context: {fp['context'][:100]}...\n")
                
        if res["false_negatives"]:
            print(f"### False Negatives ({len(res['false_negatives'])})\n")
            for fn in res["false_negatives"]:
                print(f"[{fn['sample_id']}] FN ({fn['entity_type']}): \"{fn['text']}\" {fn['span']}\n  Context: {fn['context'][:100]}...\n")

if __name__ == "__main__":
    main()
