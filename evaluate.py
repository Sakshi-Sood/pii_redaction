"""
Evaluation module for PII Redaction Pipeline.
Provides evaluate() function returning pandas DataFrames, summary metrics,
and detailed diagnostic records for Streamlit and CLI use.
"""

import json
import os
import pandas as pd
from typing import Dict, Any, Tuple, List
from redactor import detect_pii, extract_prospectus_denylist
from docx import Document

def compute_overlap_stats(span_a: Tuple[int, int], span_b: Tuple[int, int]) -> Tuple[float, float, int]:
    """
    Compute Intersection over Union (IoU), relative overlap, and intersection length.
    Returns: (iou, relative_overlap_min, inter_len)
    """
    start_a, end_a = span_a
    start_b, end_b = span_b
    
    inter_start = max(start_a, start_b)
    inter_end = min(end_a, end_b)
    inter_len = max(0, inter_end - inter_start)
    
    if inter_len == 0:
        return 0.0, 0.0, 0
        
    len_a = end_a - start_a
    len_b = end_b - start_b
    union_len = len_a + len_b - inter_len
    
    iou = inter_len / union_len if union_len > 0 else 0.0
    rel_min = inter_len / min(len_a, len_b) if min(len_a, len_b) > 0 else 0.0
    
    return iou, rel_min, inter_len

def evaluate(
    ground_truth_path: str = "ground_truth.json",
    prospectus_path: str = "input/Red Herring Prospectus.docx",
    iou_threshold: float = 0.3,
    rel_overlap_threshold: float = 0.5
) -> Dict[str, Any]:
    """
    Run evaluation against ground truth JSON dataset.
    Uses strict/relative overlap matching that prevents small sub-spans
    from stealing match slots from adjacent entities.
    """
    prospectus_denylist = None
    if os.path.exists(prospectus_path):
        try:
            doc = Document(prospectus_path)
            prospectus_denylist = extract_prospectus_denylist(doc)
        except Exception:
            pass

    with open(ground_truth_path, "r", encoding="utf-8") as f:
        samples = json.load(f)

    entity_types = ["PERSON", "EMAIL", "PHONE", "ADDRESS", "ORG", "DOB", "IP", "SSN", "CREDIT_CARD"]
    metrics = {etype: {"tp": 0, "fp": 0, "fn": 0, "support": 0} for etype in entity_types}
    
    false_positives = []
    false_negatives = []
    type_confusions = []
    perfect_samples = 0

    for sample in samples:
        sample_id = sample.get("id", "unknown")
        text = sample["text"]
        gt_spans = sample.get("spans", [])
        
        pred_spans = detect_pii(text, denylist=prospectus_denylist)
        
        # Track support
        for g in gt_spans:
            if g["type"] in metrics:
                metrics[g["type"]]["support"] += 1

        # Generate candidate match pairs with quality scores
        candidate_pairs = []
        for g_idx, g in enumerate(gt_spans):
            g_bounds = (g["start"], g["end"])
            for p_idx, p in enumerate(pred_spans):
                p_bounds = (p[0], p[1])
                iou, rel_min, inter_len = compute_overlap_stats(g_bounds, p_bounds)
                
                # Match condition: significant IoU OR significant relative overlap (>50% of smaller span)
                # with minimum intersection of at least 5 chars or full span length
                min_len = min(g_bounds[1] - g_bounds[0], p_bounds[1] - p_bounds[0])
                if iou >= iou_threshold or (rel_min >= rel_overlap_threshold and inter_len >= min(min_len, 5)):
                    same_type = (p[2] == g["type"])
                    candidate_pairs.append({
                        "g_idx": g_idx,
                        "p_idx": p_idx,
                        "iou": iou,
                        "same_type": same_type,
                        "inter_len": inter_len,
                        "g": g,
                        "p": p
                    })

        # Match prioritization:
        # 1. Same entity type match first (True before False)
        # 2. Highest IoU score
        # 3. Highest intersection length
        candidate_pairs.sort(key=lambda x: (x["same_type"], x["iou"], x["inter_len"]), reverse=True)

        matched_gt = set()
        matched_pred = set()
        sample_has_error = False

        # Phase 1: Match True Positives (same type)
        for pair in candidate_pairs:
            g_idx, p_idx = pair["g_idx"], pair["p_idx"]
            if pair["same_type"] and g_idx not in matched_gt and p_idx not in matched_pred:
                matched_gt.add(g_idx)
                matched_pred.add(p_idx)
                metrics[pair["g"]["type"]]["tp"] += 1

        # Phase 2: Detect genuine Type Confusions among remaining overlapping pairs
        for pair in candidate_pairs:
            g_idx, p_idx = pair["g_idx"], pair["p_idx"]
            if not pair["same_type"] and g_idx not in matched_gt and p_idx not in matched_pred:
                # Require higher IoU (>=0.4) for declaring a type confusion to avoid small sub-word collisions
                if pair["iou"] >= 0.4:
                    matched_gt.add(g_idx)
                    matched_pred.add(p_idx)
                    metrics[pair["p"][2]]["fp"] += 1
                    metrics[pair["g"]["type"]]["fn"] += 1
                    sample_has_error = True
                    type_confusions.append({
                        "sample_id": sample_id,
                        "expected_type": pair["g"]["type"],
                        "predicted_type": pair["p"][2],
                        "expected_text": pair["g"]["value"],
                        "predicted_text": pair["p"][3],
                        "context": text
                    })

        # Phase 3: Record unmatched predictions as False Positives
        for p_idx, p in enumerate(pred_spans):
            if p_idx not in matched_pred:
                sample_has_error = True
                p_type = p[2]
                if p_type in metrics:
                    metrics[p_type]["fp"] += 1
                false_positives.append({
                    "sample_id": sample_id,
                    "entity_type": p_type,
                    "text": p[3],
                    "span": f"[{p[0]}:{p[1]}]",
                    "context": text
                })

        # Phase 4: Record unmatched ground truths as False Negatives
        for g_idx, g in enumerate(gt_spans):
            if g_idx not in matched_gt:
                sample_has_error = True
                g_type = g["type"]
                if g_type in metrics:
                    metrics[g_type]["fn"] += 1
                false_negatives.append({
                    "sample_id": sample_id,
                    "entity_type": g_type,
                    "text": g["value"],
                    "span": f"[{g['start']}:{g['end']}]",
                    "context": text
                })

        if not sample_has_error:
            perfect_samples += 1

    rows = []
    total_tp = 0
    total_fp = 0
    total_fn = 0
    total_support = 0
    f1_list = []
    
    for etype in entity_types:
        d = metrics[etype]
        tp, fp, fn, support = d["tp"], d["fp"], d["fn"], d["support"]
        if support == 0 and fp == 0:
            continue
        prec = tp / (tp + fp) if (tp + fp) > 0 else 0.0
        rec = tp / (tp + fn) if (tp + fn) > 0 else 0.0
        f1 = (2 * prec * rec) / (prec + rec) if (prec + rec) > 0 else 0.0
        
        total_tp += tp
        total_fp += fp
        total_fn += fn
        total_support += support
        f1_list.append(f1)
        
        rows.append({
            "Entity Type": etype,
            "Precision": round(prec * 100, 2),
            "Recall": round(rec * 100, 2),
            "F1-Score": round(f1 * 100, 2),
            "Support": support,
            "TP": tp,
            "FP": fp,
            "FN": fn
        })

    df_metrics = pd.DataFrame(rows)
    
    micro_p = total_tp / (total_tp + total_fp) if (total_tp + total_fp) > 0 else 0.0
    micro_r = total_tp / (total_tp + total_fn) if (total_tp + total_fn) > 0 else 0.0
    micro_f1 = (2 * micro_p * micro_r) / (micro_p + micro_r) if (micro_p + micro_r) > 0 else 0.0
    macro_f1 = sum(f1_list) / len(f1_list) if f1_list else 0.0
    
    # Meaningful span-level accuracy metrics:
    # 1. Span Jaccard Accuracy (Threat Score): TP / (TP + FP + FN)
    span_jaccard_accuracy = total_tp / (total_tp + total_fp + total_fn) if (total_tp + total_fp + total_fn) > 0 else 0.0
    # 2. Sample Perfect Redaction Rate: % of blocks with 0 FP and 0 FN
    perfect_sample_rate = (perfect_samples / len(samples) * 100) if samples else 0.0

    return {
        "df_metrics": df_metrics,
        "micro_p": round(micro_p * 100, 2),
        "micro_r": round(micro_r * 100, 2),
        "micro_f1": round(micro_f1 * 100, 2),
        "macro_f1": round(macro_f1 * 100, 2),
        "span_jaccard_accuracy": round(span_jaccard_accuracy * 100, 2),
        "perfect_sample_rate": round(perfect_sample_rate, 2),
        "perfect_samples_count": perfect_samples,
        "total_samples": len(samples),
        "total_support": total_support,
        "total_tp": total_tp,
        "total_fp": total_fp,
        "total_fn": total_fn,
        "false_positives": false_positives,
        "false_negatives": false_negatives,
        "type_confusions": type_confusions
    }
