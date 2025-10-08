"""
Entity Matcher Module
Handles entity matching algorithms for reconciliation
"""

import re
from typing import Dict, List, Tuple, Optional, Set
import pandas as pd
from fuzzywuzzy import fuzz, process
from collections import defaultdict
import itertools


class EntityMatcher:
    """Advanced entity matching for finance reconciliation"""

    def __init__(self, config):
        """
        Initialize EntityMatcher with configuration

        Args:
            config: Application configuration object
        """
        self.config = config
        self.stopwords = set(config.STOPWORDS)
        self.fuzzy_threshold = config.FUZZY_MATCH_THRESHOLD
        self.high_confidence_threshold = config.HIGH_CONFIDENCE_THRESHOLD
        self.keyword_min_length = config.KEYWORD_MIN_LENGTH

    def extract_keywords(self, text: str) -> Set[str]:
        """
        Extract meaningful keywords from text

        Args:
            text: Text string to extract keywords from

        Returns:
            Set of extracted keywords
        """
        if pd.isna(text) or not isinstance(text, str):
            return set()

        # Convert to lowercase
        text = text.lower()

        # Remove special characters but keep spaces
        text = re.sub(r"[^\w\s]", " ", text)

        # Split into words
        words = text.split()

        # Filter out stopwords and short words
        keywords = {
            word
            for word in words
            if word not in self.stopwords and len(word) >= self.keyword_min_length
        }

        return keywords

    def extract_company_names(self, text: str) -> List[str]:
        """
        Extract potential company/vendor names from text

        Args:
            text: Text string to extract company names from

        Returns:
            List of potential company names
        """
        if pd.isna(text) or not isinstance(text, str):
            return []

        # Pattern for capitalized words (potential company names)
        pattern = r"\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\b"
        matches = re.findall(pattern, text)

        return matches

    def extract_amounts(self, text: str) -> List[float]:
        """
        Extract numeric amounts from text

        Args:
            text: Text string to extract amounts from

        Returns:
            List of extracted amounts
        """
        if pd.isna(text) or not isinstance(text, str):
            return []

        # Pattern for numbers with optional decimals and separators
        pattern = r"\d+(?:,\d{3})*(?:\.\d{2})?"
        matches = re.findall(pattern, text)

        amounts = []
        for match in matches:
            try:
                # Remove commas and convert to float
                amount = float(match.replace(",", ""))
                amounts.append(amount)
            except ValueError:
                continue

        return amounts

    def calculate_similarity(self, text1: str, text2: str) -> float:
        """
        Calculate similarity score between two text strings

        Args:
            text1: First text string
            text2: Second text string

        Returns:
            Similarity score between 0 and 1
        """
        if pd.isna(text1) or pd.isna(text2):
            return 0.0

        # Use token sort ratio for better matching with word order variations
        score = fuzz.token_sort_ratio(str(text1), str(text2))

        # Convert to 0-1 scale
        return score / 100.0

    def exact_match(
        self, expenses: pd.DataFrame, revenues: pd.DataFrame
    ) -> Tuple[List[Dict], pd.DataFrame, pd.DataFrame]:
        """
        Perform exact matching between expenses and revenues

        Args:
            expenses: DataFrame of expense transactions
            revenues: DataFrame of revenue transactions

        Returns:
            Tuple of (matches, remaining_expenses, remaining_revenues)
        """
        matches = []
        matched_expense_ids = set()
        matched_revenue_ids = set()

        for _, revenue in revenues.iterrows():
            revenue_amount = revenue["abs_amount"]
            revenue_desc = str(revenue["description"]).lower().strip()

            # Look for exact amount and description match
            for _, expense in expenses.iterrows():
                if expense["original_index"] in matched_expense_ids:
                    continue

                expense_amount = expense["abs_amount"]
                expense_desc = str(expense["description"]).lower().strip()

                # Check for exact match
                if (
                    abs(expense_amount - revenue_amount) < self.config.BALANCE_TOLERANCE
                    and expense_desc == revenue_desc
                ):
                    matches.append(
                        {
                            "match_type": "exact",
                            "confidence": 1.0,
                            "revenue": revenue.to_dict(),
                            "expenses": [expense.to_dict()],
                            "balance": revenue_amount - expense_amount,
                        }
                    )
                    matched_expense_ids.add(expense["original_index"])
                    matched_revenue_ids.add(revenue["original_index"])
                    break

        # Remove matched transactions
        remaining_expenses = expenses[
            ~expenses["original_index"].isin(matched_expense_ids)
        ]
        remaining_revenues = revenues[
            ~revenues["original_index"].isin(matched_revenue_ids)
        ]

        return matches, remaining_expenses, remaining_revenues

    def keyword_match(
        self, expenses: pd.DataFrame, revenues: pd.DataFrame, min_keywords: int = 2
    ) -> Tuple[List[Dict], pd.DataFrame, pd.DataFrame]:
        """
        Match transactions based on shared keywords

        Args:
            expenses: DataFrame of expense transactions
            revenues: DataFrame of revenue transactions
            min_keywords: Minimum number of shared keywords for a match

        Returns:
            Tuple of (matches, remaining_expenses, remaining_revenues)
        """
        matches = []
        matched_expense_ids = set()
        matched_revenue_ids = set()

        for _, revenue in revenues.iterrows():
            revenue_keywords = self.extract_keywords(revenue["description"])

            if len(revenue_keywords) < min_keywords:
                continue

            potential_expenses = []

            for _, expense in expenses.iterrows():
                if expense["original_index"] in matched_expense_ids:
                    continue

                expense_keywords = self.extract_keywords(expense["description"])
                shared_keywords = revenue_keywords.intersection(expense_keywords)

                if len(shared_keywords) >= min_keywords:
                    keyword_score = len(shared_keywords) / max(
                        len(revenue_keywords), len(expense_keywords)
                    )
                    potential_expenses.append(
                        {
                            "expense": expense,
                            "shared_keywords": shared_keywords,
                            "keyword_score": keyword_score,
                        }
                    )

            # Try to find expense combinations that match the revenue amount
            if potential_expenses:
                best_match = self._find_best_expense_combination(
                    revenue, potential_expenses
                )

                if best_match:
                    matches.append(best_match)
                    for exp in best_match["expenses"]:
                        matched_expense_ids.add(exp["original_index"])
                    matched_revenue_ids.add(revenue["original_index"])

        # Remove matched transactions
        remaining_expenses = expenses[
            ~expenses["original_index"].isin(matched_expense_ids)
        ]
        remaining_revenues = revenues[
            ~revenues["original_index"].isin(matched_revenue_ids)
        ]

        return matches, remaining_expenses, remaining_revenues

    def fuzzy_match(
        self, expenses: pd.DataFrame, revenues: pd.DataFrame
    ) -> Tuple[List[Dict], pd.DataFrame, pd.DataFrame]:
        """
        Perform fuzzy matching between expenses and revenues

        Args:
            expenses: DataFrame of expense transactions
            revenues: DataFrame of revenue transactions

        Returns:
            Tuple of (matches, remaining_expenses, remaining_revenues)
        """
        matches = []
        matched_expense_ids = set()
        matched_revenue_ids = set()

        for _, revenue in revenues.iterrows():
            revenue_desc = str(revenue["description"])
            potential_expenses = []

            for _, expense in expenses.iterrows():
                if expense["original_index"] in matched_expense_ids:
                    continue

                expense_desc = str(expense["description"])
                similarity = self.calculate_similarity(revenue_desc, expense_desc)

                if similarity >= self.fuzzy_threshold:
                    potential_expenses.append(
                        {
                            "expense": expense,
                            "similarity": similarity,
                            "keyword_score": similarity,
                        }
                    )

            # Try to find expense combinations that match the revenue amount
            if potential_expenses:
                best_match = self._find_best_expense_combination(
                    revenue, potential_expenses
                )

                if best_match:
                    matches.append(best_match)
                    for exp in best_match["expenses"]:
                        matched_expense_ids.add(exp["original_index"])
                    matched_revenue_ids.add(revenue["original_index"])

        # Remove matched transactions
        remaining_expenses = expenses[
            ~expenses["original_index"].isin(matched_expense_ids)
        ]
        remaining_revenues = revenues[
            ~revenues["original_index"].isin(matched_revenue_ids)
        ]

        return matches, remaining_expenses, remaining_revenues

    def _find_best_expense_combination(
        self, revenue: pd.Series, potential_expenses: List[Dict]
    ) -> Optional[Dict]:
        """
        Find the best combination of expenses that match a revenue amount

        Args:
            revenue: Revenue transaction series
            potential_expenses: List of potential expense matches with scores

        Returns:
            Dictionary containing match information or None
        """
        revenue_amount = revenue["abs_amount"]
        tolerance = self.config.BALANCE_TOLERANCE

        # Sort by score (descending)
        potential_expenses.sort(key=lambda x: x.get("keyword_score", 0), reverse=True)

        # Try single expense match first
        for pot_exp in potential_expenses:
            expense = pot_exp["expense"]
            if abs(expense["abs_amount"] - revenue_amount) < tolerance:
                confidence = pot_exp.get("keyword_score", 0.5)
                return {
                    "match_type": "fuzzy_single",
                    "confidence": confidence,
                    "revenue": revenue.to_dict(),
                    "expenses": [expense.to_dict()],
                    "balance": revenue_amount - expense["abs_amount"],
                }

        # Try combinations of 2-5 expenses
        for combo_size in range(2, min(6, len(potential_expenses) + 1)):
            for combo in itertools.combinations(potential_expenses[:10], combo_size):
                total_expense = sum(pe["expense"]["abs_amount"] for pe in combo)

                if abs(total_expense - revenue_amount) < tolerance:
                    # Calculate average confidence
                    avg_confidence = sum(
                        pe.get("keyword_score", 0) for pe in combo
                    ) / len(combo)

                    return {
                        "match_type": f"fuzzy_multiple_{combo_size}",
                        "confidence": avg_confidence,
                        "revenue": revenue.to_dict(),
                        "expenses": [pe["expense"].to_dict() for pe in combo],
                        "balance": revenue_amount - total_expense,
                    }

        return None

    def find_potential_matches(
        self, revenue: pd.Series, expenses: pd.DataFrame, top_n: int = 5
    ) -> List[Dict]:
        """
        Find potential expense matches for a revenue transaction (for manual review)

        Args:
            revenue: Revenue transaction series
            expenses: DataFrame of unmatched expense transactions
            top_n: Number of top matches to return

        Returns:
            List of potential matches with scores
        """
        revenue_desc = str(revenue["description"])
        revenue_amount = revenue["abs_amount"]
        revenue_keywords = self.extract_keywords(revenue_desc)

        potential_matches = []

        for _, expense in expenses.iterrows():
            expense_desc = str(expense["description"])
            expense_keywords = self.extract_keywords(expense_desc)

            # Calculate various similarity scores
            fuzzy_score = self.calculate_similarity(revenue_desc, expense_desc)

            # Keyword overlap score
            if revenue_keywords and expense_keywords:
                shared_keywords = revenue_keywords.intersection(expense_keywords)
                keyword_score = len(shared_keywords) / max(
                    len(revenue_keywords), len(expense_keywords)
                )
            else:
                keyword_score = 0.0

            # Amount similarity (closer amounts = higher score)
            amount_diff = abs(expense["abs_amount"] - revenue_amount)
            amount_score = (
                max(0, 1 - (amount_diff / revenue_amount)) if revenue_amount > 0 else 0
            )

            # Combined score
            combined_score = (
                (fuzzy_score * 0.4) + (keyword_score * 0.4) + (amount_score * 0.2)
            )

            potential_matches.append(
                {
                    "expense": expense.to_dict(),
                    "fuzzy_score": fuzzy_score,
                    "keyword_score": keyword_score,
                    "amount_score": amount_score,
                    "combined_score": combined_score,
                    "shared_keywords": list(
                        revenue_keywords.intersection(expense_keywords)
                    ),
                }
            )

        # Sort by combined score
        potential_matches.sort(key=lambda x: x["combined_score"], reverse=True)

        return potential_matches[:top_n]

    def auto_match_all(
        self, df: pd.DataFrame
    ) -> Tuple[List[Dict], pd.DataFrame, pd.DataFrame]:
        """
        Run all matching algorithms in sequence

        Args:
            df: DataFrame with all transactions

        Returns:
            Tuple of (all_matches, unmatched_expenses, unmatched_revenues)
        """
        # Split into expenses and revenues
        expenses = df[df["transaction_type"] == "expense"].copy()
        revenues = df[df["transaction_type"] == "revenue"].copy()

        all_matches = []

        # Level 1: Exact matching
        exact_matches, expenses, revenues = self.exact_match(expenses, revenues)
        all_matches.extend(exact_matches)

        # Level 2: Keyword matching
        keyword_matches, expenses, revenues = self.keyword_match(expenses, revenues)
        all_matches.extend(keyword_matches)

        # Level 3: Fuzzy matching
        fuzzy_matches, expenses, revenues = self.fuzzy_match(expenses, revenues)
        all_matches.extend(fuzzy_matches)

        return all_matches, expenses, revenues

    def generate_review_items(
        self, unmatched_revenues: pd.DataFrame, unmatched_expenses: pd.DataFrame
    ) -> List[Dict]:
        """
        Generate review items for manual matching

        Args:
            unmatched_revenues: DataFrame of unmatched revenue transactions
            unmatched_expenses: DataFrame of unmatched expense transactions

        Returns:
            List of review items with potential matches
        """
        review_items = []

        for _, revenue in unmatched_revenues.iterrows():
            potential_matches = self.find_potential_matches(revenue, unmatched_expenses)

            review_items.append(
                {
                    "revenue": revenue.to_dict(),
                    "potential_expenses": potential_matches,
                    "status": "pending_review",
                }
            )

        return review_items
