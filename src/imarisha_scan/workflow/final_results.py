from __future__ import annotations

import re
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class FinalExtractionOutput:
    csv_path: Path
    db_path: Path
    row_count: int


class FinalResultsWorkflow:
    """Simple upload -> extract -> CSV -> SQLite workflow for review/export."""

    def __init__(self) -> None:
        self._deps_loaded = False

    def _load_dependencies(self) -> None:
        if self._deps_loaded:
            return
        global cv2, fitz, np, pd, pytesseract
        try:
            import cv2  # type: ignore
            import fitz  # type: ignore
            import numpy as np  # type: ignore
            import pandas as pd  # type: ignore
            import pytesseract  # type: ignore
        except ModuleNotFoundError as exc:
            raise RuntimeError(
                "Missing extraction dependency. Install with: "
                "pip install pymupdf opencv-python-headless pandas pytesseract pillow numpy"
            ) from exc

        self._deps_loaded = True

    def run(self, source_pdf: Path, output_csv: Path, output_db: Path, student_id_mode: str = "auto") -> FinalExtractionOutput:
        self._load_dependencies()

        if source_pdf.suffix.lower() != ".pdf":
            raise ValueError("Only PDF extraction is supported in the simplified workflow.")

        rows = self._extract_pdf_rows(source_pdf, student_id_mode=student_id_mode)
        df = pd.DataFrame(rows)

        if not df.empty:
            sort_cols = [
                c
                for c in ["student_id", "page", "section", "question_id", "item_number", "answer"]
                if c in df.columns
            ]
            if sort_cols:
                df = df.sort_values(sort_cols, na_position="last").reset_index(drop=True)

        output_csv.parent.mkdir(parents=True, exist_ok=True)
        output_db.parent.mkdir(parents=True, exist_ok=True)
        df.to_csv(output_csv, index=False)
        self._write_dataframe_to_db(df, output_db)

        return FinalExtractionOutput(csv_path=output_csv, db_path=output_db, row_count=len(df.index))

    def _write_dataframe_to_db(self, dataframe: Any, db_path: Path) -> None:
        conn = sqlite3.connect(db_path)
        try:
            dataframe.to_sql("final_results", conn, if_exists="replace", index=False)
        finally:
            conn.close()

    def _extract_pdf_rows(self, pdf_path: Path, student_id_mode: str) -> list[dict[str, Any]]:
        doc = fitz.open(pdf_path)
        all_rows: list[dict[str, Any]] = []
        try:
            for page_idx in range(len(doc)):
                page = doc[page_idx]
                img_bgr = self._render_page_to_bgr(page)
                page_number = page_idx + 1

                qr_raw = self._decode_qr_robust(img_bgr)
                if not qr_raw:
                    all_rows.append(self._missing_qr_row(page_number))
                    continue

                qr_parsed = self._parse_qr_data(qr_raw)
                qr_student_id = qr_parsed.get("studentid")
                qr_type = (qr_parsed.get("type") or "").upper() or None

                exam_id = None
                test_id = None
                if qr_type == "EXAM":
                    exam_id = qr_parsed.get("examid") or qr_parsed.get("assessmentid")
                elif qr_type == "TEST":
                    test_id = qr_parsed.get("testid") or qr_parsed.get("assessmentid")

                printed_id = self._extract_student_id_printed_text(page)
                handwritten_id, _ = self._extract_student_id_handwritten_ocr(img_bgr)
                id_info = self._resolve_student_id(qr_student_id, printed_id, handwritten_id, student_id_mode)

                base = {
                    "page": page_number,
                    "student_id": id_info["student_id"],
                    "student_id_all": id_info["student_id_all"],
                    "student_id_qr": id_info["student_id_qr"],
                    "student_id_text": id_info["student_id_text"],
                    "student_id_handwritten": id_info["student_id_handwritten"],
                    "student_id_source": id_info["student_id_source"],
                    "id_conflict": id_info["id_conflict"],
                    "sheet_type": qr_type,
                    "exam_id": exam_id if qr_type == "EXAM" else None,
                    "test_id": test_id if qr_type == "TEST" else None,
                    "qr_raw": qr_raw,
                }

                sections = self._detect_section_blocks(page)
                for section in sections:
                    option_centers = self._find_option_centers(page, section)
                    section_rows = self._extract_rows_for_section(page, section)

                    if section["section_type"] == "OPEN_ENDED":
                        for row in section_rows:
                            self._append_output_row(all_rows, base, row, [], True, {})
                        continue

                    for row in section_rows:
                        answers, row_review, scores = self._extract_row_answers(page, img_bgr, section, row, option_centers)
                        review_flag = row_review or id_info["needs_review"] or (row["question_id"] is None)
                        self._append_output_row(all_rows, base, row, answers, review_flag, scores)
        finally:
            doc.close()

        return all_rows

    @staticmethod
    def _missing_qr_row(page_number: int) -> dict[str, Any]:
        return {
            "page": page_number,
            "student_id": None,
            "student_id_all": None,
            "student_id_qr": None,
            "student_id_text": None,
            "student_id_handwritten": None,
            "student_id_source": "missing",
            "id_conflict": False,
            "sheet_type": None,
            "exam_id": None,
            "test_id": None,
            "section": None,
            "question_id": None,
            "item_number": None,
            "answer": None,
            "matching_pair": None,
            "manual_marking": False,
            "needs_review": True,
            "score_debug": None,
            "qr_raw": None,
        }

    @staticmethod
    def _parse_qr_data(data: str | None) -> dict[str, str | None]:
        parsed: dict[str, str | None] = {
            "type": None,
            "studentid": None,
            "examid": None,
            "testid": None,
            "assessmentid": None,
        }
        if not data:
            return parsed

        for part in data.split(";"):
            if "=" in part:
                k, v = part.split("=", 1)
                parsed[k.strip().lower()] = v.strip()
        return parsed

    def _decode_qr_robust(self, img_bgr: Any) -> str | None:
        detector = cv2.QRCodeDetector()
        attempts = []

        gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)
        attempts.append(gray)

        clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8, 8))
        attempts.append(clahe.apply(gray))

        attempts.append(cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 11, 2))
        _, otsu = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        attempts.append(otsu)

        sharpen_kernel = np.array([[0, -1, 0], [-1, 5, -1], [0, -1, 0]], dtype=np.float32)
        attempts.append(cv2.filter2D(gray, -1, sharpen_kernel))
        attempts.append(cv2.resize(gray, None, fx=2.5, fy=2.5, interpolation=cv2.INTER_CUBIC))

        h, w = gray.shape
        qr_crop = gray[int(0.10 * h) : int(0.38 * h), int(0.72 * w) : int(0.98 * w)]
        attempts.append(cv2.resize(qr_crop, None, fx=3.0, fy=3.0, interpolation=cv2.INTER_CUBIC))

        for attempt in attempts:
            data, _, _ = detector.detectAndDecode(attempt)
            if data:
                return data
        return None

    def _render_page_to_bgr(self, page: Any, zoom: float = 3.5) -> Any:
        pix = page.get_pixmap(matrix=fitz.Matrix(zoom, zoom), alpha=False)
        img = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width, pix.n)
        if pix.n == 4:
            img = cv2.cvtColor(img, cv2.COLOR_RGBA2BGR)
        elif pix.n == 3:
            img = cv2.cvtColor(img, cv2.COLOR_RGB2BGR)
        return img

    @staticmethod
    def _extract_student_id_printed_text(page: Any) -> str | None:
        text = page.get_text("text", sort=True)
        match = re.search(r"Student ID:\s*(\d+)", text, flags=re.IGNORECASE)
        return match.group(1) if match else None

    def _extract_student_id_handwritten_ocr(self, img_bgr: Any) -> tuple[str | None, bool]:
        h, w = img_bgr.shape[:2]
        roi = img_bgr[int(0.16 * h) : int(0.30 * h), int(0.02 * w) : int(0.48 * w)]
        gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
        gray = cv2.GaussianBlur(gray, (3, 3), 0)

        variants = [gray]
        _, th1 = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        variants.extend(
            [
                th1,
                cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 21, 11),
                cv2.bitwise_not(th1),
            ]
        )

        best_digits: str | None = None
        best_conf = -1.0

        for variant in variants:
            data = pytesseract.image_to_data(
                variant,
                config="--psm 6 -c tessedit_char_whitelist=0123456789[]:",
                output_type=pytesseract.Output.DICT,
            )

            tokens: list[str] = []
            confs: list[float] = []
            for txt, conf_str in zip(data["text"], data["conf"]):
                txt = (txt or "").strip()
                try:
                    conf_val = float(conf_str)
                except ValueError:
                    conf_val = -1.0

                if txt:
                    tokens.append(txt)
                    confs.append(conf_val)

            joined = " ".join(tokens)
            digit_groups = re.findall(r"\d+", joined)
            if not digit_groups:
                continue

            candidate = max(digit_groups, key=len)
            avg_conf = float(np.mean([c for c in confs if c >= 0])) if confs else -1.0
            if len(candidate) >= 1 and avg_conf > best_conf:
                best_digits = candidate
                best_conf = avg_conf

        if best_digits:
            return best_digits, best_conf < 45

        return None, True

    @staticmethod
    def _resolve_student_id(qr_id: str | None, printed_id: str | None, handwritten_id: str | None, mode: str) -> dict[str, Any]:
        if mode == "qr":
            return {
                "student_id": qr_id,
                "student_id_all": qr_id if qr_id else None,
                "student_id_qr": qr_id,
                "student_id_text": None,
                "student_id_handwritten": None,
                "student_id_source": "qr",
                "id_conflict": False,
                "needs_review": qr_id is None,
            }

        if mode == "text":
            detected = [x for x in [printed_id, handwritten_id] if x]
            conflict = len(set(detected)) > 1
            chosen = printed_id or handwritten_id
            return {
                "student_id": chosen,
                "student_id_all": ",".join(detected) if detected else None,
                "student_id_qr": qr_id,
                "student_id_text": printed_id,
                "student_id_handwritten": handwritten_id,
                "student_id_source": "text",
                "id_conflict": conflict,
                "needs_review": True,
            }

        detected = [x for x in [qr_id, printed_id, handwritten_id] if x]
        conflict = len(set(detected)) > 1

        if qr_id:
            chosen, source = qr_id, "qr"
        elif printed_id:
            chosen, source = printed_id, "text_printed"
        elif handwritten_id:
            chosen, source = handwritten_id, "text_handwritten"
        else:
            chosen, source = None, "missing"

        return {
            "student_id": chosen,
            "student_id_all": ",".join(dict.fromkeys(detected)) if detected else None,
            "student_id_qr": qr_id,
            "student_id_text": printed_id,
            "student_id_handwritten": handwritten_id,
            "student_id_source": source,
            "id_conflict": conflict,
            "needs_review": chosen is None or conflict or source.startswith("text"),
        }

    @staticmethod
    def _detect_section_blocks(page: Any) -> list[dict[str, Any]]:
        heading_specs = [
            ("MC", "MULTIPLE CHOICE"),
            ("TF", "TRUE / FALSE"),
            ("MATCH", "MATCHING"),
            ("OPEN_ENDED", "OPEN ENDED"),
        ]
        found = []
        for section_type, phrase in heading_specs:
            for rect in page.search_for(phrase, quads=False):
                found.append((section_type, rect))
        found.sort(key=lambda x: x[1].y0)

        if not found:
            return []

        blocks = []
        page_bottom = page.rect.y1
        for idx, (section_type, rect) in enumerate(found):
            y0 = rect.y1 + 6
            y1 = (found[idx + 1][1].y0 - 6) if idx + 1 < len(found) else (page_bottom - 10)
            if y1 > y0 + 10:
                blocks.append({"section_type": section_type, "y0": y0, "y1": y1})
        return blocks

    @staticmethod
    def _find_option_centers(page: Any, section: dict[str, Any]) -> dict[str, float]:
        words = page.get_text("words", sort=True)
        top_zone_y1 = section["y0"] + 80
        labels = {"MC": ["A", "B", "C", "D"], "TF": ["T", "F"], "MATCH": ["A", "B", "C", "D"]}.get(
            section["section_type"], []
        )

        centers: dict[str, float] = {}
        for x0, y0, x1, y1, text, *_ in words:
            if y0 < section["y0"] or y1 > top_zone_y1:
                continue
            clean = text.strip().upper()
            if clean in labels and clean not in centers:
                centers[clean] = (x0 + x1) / 2.0
        return centers

    def _extract_rows_for_section(self, page: Any, section: dict[str, Any]) -> list[dict[str, Any]]:
        words = page.get_text("words", sort=True)
        section_words = [w for w in words if w[1] >= section["y0"] and w[3] <= section["y1"]]
        lines = self._group_words_into_lines(section_words)
        rows: list[dict[str, Any]] = []

        for line in lines:
            texts = [w[4].strip() for w in line if w[4].strip()]
            if not texts:
                continue

            joined = " ".join(texts).upper()
            if "ID A B C D" in joined or "ID T F" in joined or "QID ITEM A B C D" in joined or "QUESTION STUDENT ANSWER" in joined:
                continue

            xs, ys0, xs1, ys1 = [w[0] for w in line], [w[1] for w in line], [w[2] for w in line], [w[3] for w in line]
            bbox = (min(xs), min(ys0), max(xs1), max(ys1))
            y_center = (bbox[1] + bbox[3]) / 2.0

            if section["section_type"] in {"MC", "TF", "OPEN_ENDED"}:
                qids = [t for t in texts if re.fullmatch(r"\d{5,6}", t)]
                if qids:
                    rows.append({"section_type": section["section_type"], "question_id": qids[0], "item_number": None, "y_center": y_center, "row_bbox": bbox})
            elif section["section_type"] == "MATCH":
                qids = [t for t in texts if re.fullmatch(r"\d{5,6}", t)]
                items = [t for t in texts if re.fullmatch(r"[1-4]", t)]
                if qids and items:
                    rows.append({"section_type": section["section_type"], "question_id": qids[0], "item_number": int(items[0]), "y_center": y_center, "row_bbox": bbox})

        return rows

    @staticmethod
    def _group_words_into_lines(words: list[Any], y_tolerance: float = 4.0) -> list[list[Any]]:
        lines: list[list[Any]] = []
        for word in sorted(words, key=lambda w: (w[1], w[0])):
            if not lines:
                lines.append([word])
                continue
            current_y = float(np.mean([w[1] for w in lines[-1]]))
            if abs(word[1] - current_y) <= y_tolerance:
                lines[-1].append(word)
            else:
                lines.append([word])
        return lines

    def _extract_row_answers(
        self,
        page: Any,
        img_bgr: Any,
        section: dict[str, Any],
        row: dict[str, Any],
        option_centers: dict[str, float],
    ) -> tuple[list[str], bool, dict[str, float]]:
        gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)
        sx = img_bgr.shape[1] / page.rect.width
        sy = img_bgr.shape[0] / page.rect.height

        if section["section_type"] == "MC":
            ordered_labels, output_map = ["A", "B", "C", "D"], {"A": "A", "B": "B", "C": "C", "D": "D"}
        elif section["section_type"] == "TF":
            ordered_labels, output_map = ["T", "F"], {"T": "True", "F": "False"}
        elif section["section_type"] == "MATCH":
            ordered_labels, output_map = ["A", "B", "C", "D"], {"A": "A", "B": "B", "C": "C", "D": "D"}
        else:
            return [], True, {}

        row_h_page = max(10.0, row["row_bbox"][3] - row["row_bbox"][1])
        radius = max(10, int((row_h_page * sy) * 0.38))
        cy = int(row["y_center"] * sy)

        scores: dict[str, float] = {}
        for label in ordered_labels:
            if label not in option_centers:
                scores[label] = 0.0
                continue
            cx = int(option_centers[label] * sx)
            scores[label] = self._sample_bubble_score(gray, cx, cy, radius)

        score_values = list(scores.values())
        if not score_values:
            return [], True, scores

        mean_score = float(np.mean(score_values))
        max_score = float(np.max(score_values))
        min_score = float(np.min(score_values))

        filled_labels = [label for label in ordered_labels if scores[label] >= mean_score + 10.0]
        needs_review = False

        if not filled_labels:
            best_label = max(scores, key=scores.get)
            sorted_vals = sorted(score_values, reverse=True)
            if len(sorted_vals) >= 2 and (sorted_vals[0] - sorted_vals[1]) >= 12:
                filled_labels = [best_label]
            else:
                needs_review = True

        if (max_score - min_score) < 4.0:
            needs_review = True
        if section["section_type"] in {"TF", "MATCH"} and len(filled_labels) != 1:
            needs_review = True

        answers = [output_map[label] for label in filled_labels if label in output_map]
        return answers, needs_review, scores

    @staticmethod
    def _sample_bubble_score(gray: Any, cx: int, cy: int, radius: int) -> float:
        x0, y0 = max(0, cx - radius), max(0, cy - radius)
        x1, y1 = min(gray.shape[1], cx + radius), min(gray.shape[0], cy + radius)
        if x1 <= x0 or y1 <= y0:
            return 0.0

        roi = gray[y0:y1, x0:x1]
        if roi.size == 0:
            return 0.0

        yy, xx = np.ogrid[: roi.shape[0], : roi.shape[1]]
        rr = min(roi.shape[0], roi.shape[1]) / 2.2
        cy0, cx0 = roi.shape[0] / 2.0, roi.shape[1] / 2.0
        mask = (xx - cx0) ** 2 + (yy - cy0) ** 2 <= rr**2

        pixels = roi[mask]
        if pixels.size == 0:
            pixels = roi.flatten()
        return 255.0 - float(np.mean(pixels))

    @staticmethod
    def _append_output_row(
        output_rows: list[dict[str, Any]],
        base: dict[str, Any],
        row: dict[str, Any],
        answers: list[str],
        needs_review: bool,
        scores: dict[str, float],
    ) -> None:
        if row["section_type"] == "OPEN_ENDED":
            output_rows.append({**base, "section": "OPEN_ENDED", "question_id": row["question_id"], "item_number": None, "answer": None, "matching_pair": None, "manual_marking": True, "needs_review": True, "score_debug": None})
            return

        if not answers:
            output_rows.append({**base, "section": row["section_type"], "question_id": row["question_id"], "item_number": row["item_number"], "answer": None, "matching_pair": None, "manual_marking": False, "needs_review": True, "score_debug": str(scores)})
            return

        for answer in answers:
            pair = None
            if row["section_type"] == "MATCH" and row["item_number"] in {1, 2, 3, 4}:
                left_label = {1: "A", 2: "B", 3: "C", 4: "D"}[row["item_number"]]
                pair = f"{left_label}={answer}"
            output_rows.append({**base, "section": row["section_type"], "question_id": row["question_id"], "item_number": row["item_number"], "answer": answer, "matching_pair": pair, "manual_marking": False, "needs_review": bool(needs_review), "score_debug": str(scores)})
