"""
Simple question-answer knowledge base for the AI chatbot.

Questions and answers are stored in ai_agent/data/qa_pairs.json so you can feed
your own data without changing Python code.
"""

import json
import re
from hashlib import sha1
from difflib import SequenceMatcher
from pathlib import Path
from typing import Dict, List, Optional


QA_FILE = Path(__file__).resolve().parents[1] / "data" / "qa_pairs.json"
MIN_MATCH_SCORE = 0.62


def normalize_text(text: str) -> str:
    text = (text or "").lower()
    text = re.sub(r"[^a-z0-9\s]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _pair_id(question: str) -> str:
    normalized = normalize_text(question)
    return sha1(normalized.encode("utf-8")).hexdigest()[:12]


def load_qa_pairs() -> List[Dict[str, str]]:
    if not QA_FILE.exists():
        return []

    try:
        with QA_FILE.open("r", encoding="utf-8") as file:
            data = json.load(file)
    except (json.JSONDecodeError, OSError):
        return []

    if not isinstance(data, list):
        return []

    return [
        {
            "id": str(item.get("id") or _pair_id(item.get("question", ""))),
            "question": str(item.get("question", "")).strip(),
            "answer": str(item.get("answer", "")).strip(),
        }
        for item in data
        if isinstance(item, dict) and item.get("question") and item.get("answer")
    ]


def save_qa_pair(question: str, answer: str) -> Dict[str, str]:
    question = (question or "").strip()
    answer = (answer or "").strip()
    if not question or not answer:
        raise ValueError("Both question and answer are required.")

    pairs = load_qa_pairs()
    normalized_question = normalize_text(question)

    for pair in pairs:
        if normalize_text(pair["question"]) == normalized_question:
            pair["id"] = pair.get("id") or _pair_id(question)
            pair["question"] = question
            pair["answer"] = answer
            break
    else:
        pairs.append({"id": _pair_id(question), "question": question, "answer": answer})

    QA_FILE.parent.mkdir(parents=True, exist_ok=True)
    with QA_FILE.open("w", encoding="utf-8") as file:
        json.dump(pairs, file, indent=2)

    return {"id": _pair_id(question), "question": question, "answer": answer}


def delete_qa_pair(pair_id: str) -> bool:
    pair_id = str(pair_id or "").strip()
    if not pair_id:
        return False

    pairs = load_qa_pairs()
    remaining = [pair for pair in pairs if str(pair.get("id")) != pair_id]
    if len(remaining) == len(pairs):
        return False

    with QA_FILE.open("w", encoding="utf-8") as file:
        json.dump(remaining, file, indent=2)

    return True


def find_answer(user_question: str) -> Optional[Dict[str, object]]:
    query = normalize_text(user_question)
    if not query:
        return None

    best_pair = None
    best_score = 0.0

    for pair in load_qa_pairs():
        stored_question = normalize_text(pair["question"])
        if not stored_question:
            continue

        if query == stored_question:
            return {
                "answer": pair["answer"],
                "matched_question": pair["question"],
                "match_score": 1.0,
            }

        score = SequenceMatcher(None, query, stored_question).ratio()
        query_words = set(query.split())
        stored_words = set(stored_question.split())
        if query_words and stored_words:
            overlap_score = len(query_words & stored_words) / len(query_words | stored_words)
            score = max(score, overlap_score)

        if score > best_score:
            best_pair = pair
            best_score = score

    if best_pair and best_score >= MIN_MATCH_SCORE:
        return {
            "answer": best_pair["answer"],
            "matched_question": best_pair["question"],
            "match_score": round(best_score, 2),
        }

    return None
