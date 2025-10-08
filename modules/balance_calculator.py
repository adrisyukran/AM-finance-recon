"""
Balance Calculator Module
Handles balance computation and validation for reconciliation
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Tuple, Optional, Set
from itertools import combinations


class BalanceCalculator:
    """Calculate and validate balances for finance reconciliation"""

    def __init__(self, config):
        """
        Initialize BalanceCalculator with configuration

        Args:
            config: Application configuration object
        """
        self.config = config
        self.balance_tolerance = config.BALANCE_TOLERANCE

    def calculate_match_balance(self, match: Dict) -> float:
        """
        Calculate the balance for a matched group

        Args:
            match: Dictionary containing revenue and expenses

        Returns:
            Balance amount (should be close to 0 for valid matches)
        """
        revenue = match.get("revenue", {})
        expenses = match.get("expenses", [])

        revenue_amount = revenue.get("amount", 0)
        expense_total = sum(exp.get("amount", 0) for exp in expenses)

        # Balance = revenue + expenses (expenses are negative)
        balance = revenue_amount + expense_total

        return balance

    def is_balanced(self, match: Dict) -> bool:
        """
        Check if a matched group is balanced (sums to zero within tolerance)

        Args:
            match: Dictionary containing revenue and expenses

        Returns:
            True if balanced, False otherwise
        """
        balance = self.calculate_match_balance(match)
        return abs(balance) < self.balance_tolerance

    def validate_match(self, match: Dict) -> Tuple[bool, str]:
        """
        Validate a matched group

        Args:
            match: Dictionary containing revenue and expenses

        Returns:
            Tuple of (is_valid, message)
        """
        revenue = match.get("revenue")
        expenses = match.get("expenses", [])

        # Check if revenue exists
        if not revenue:
            return False, "No revenue transaction in match"

        # Check if expenses exist
        if not expenses:
            return False, "No expense transactions in match"

        # Check if balanced
        if not self.is_balanced(match):
            balance = self.calculate_match_balance(match)
            return False, f"Match not balanced. Balance: {balance:.2f}"

        return True, "Match is valid"

    def find_expense_combinations(
        self, target_amount: float, expenses: List[Dict], max_combo_size: int = 10
    ) -> List[List[Dict]]:
        """
        Find all expense combinations that sum to target amount

        Args:
            target_amount: Target amount to match (positive value)
            expenses: List of expense dictionaries
            max_combo_size: Maximum number of expenses in a combination

        Returns:
            List of expense combinations that match the target
        """
        matching_combinations = []

        # Try combinations of different sizes
        for size in range(1, min(max_combo_size + 1, len(expenses) + 1)):
            for combo in combinations(expenses, size):
                combo_sum = sum(abs(exp.get("amount", 0)) for exp in combo)

                if abs(combo_sum - target_amount) < self.balance_tolerance:
                    matching_combinations.append(list(combo))

        return matching_combinations

    def find_expense_combinations_dp(
        self, target_amount: float, expenses: List[Dict]
    ) -> Optional[List[Dict]]:
        """
        Find expense combination using dynamic programming (subset sum problem)

        Args:
            target_amount: Target amount to match (positive value)
            expenses: List of expense dictionaries

        Returns:
            List of expenses that sum to target, or None if no solution
        """
        # Convert to cents to avoid floating point issues
        target_cents = int(round(target_amount * 100))
        expense_cents = [
            int(round(abs(exp.get("amount", 0)) * 100)) for exp in expenses
        ]

        n = len(expenses)

        # DP table: dp[i][j] = can we make amount j using first i expenses?
        dp = [[False] * (target_cents + 1) for _ in range(n + 1)]

        # Base case: 0 amount is always possible
        for i in range(n + 1):
            dp[i][0] = True

        # Fill DP table
        for i in range(1, n + 1):
            for j in range(target_cents + 1):
                # Don't take current expense
                dp[i][j] = dp[i - 1][j]

                # Take current expense if possible
                if j >= expense_cents[i - 1]:
                    dp[i][j] = dp[i][j] or dp[i - 1][j - expense_cents[i - 1]]

        # Check if solution exists
        if not dp[n][target_cents]:
            return None

        # Backtrack to find the actual combination
        result = []
        i, j = n, target_cents

        while i > 0 and j > 0:
            # If value came from not taking current item, move up
            if dp[i - 1][j]:
                i -= 1
            else:
                # Current item was taken
                result.append(expenses[i - 1])
                j -= expense_cents[i - 1]
                i -= 1

        return result if result else None

    def calculate_total_balance(self, matches: List[Dict]) -> Dict:
        """
        Calculate overall balance statistics for all matches

        Args:
            matches: List of matched groups

        Returns:
            Dictionary containing balance statistics
        """
        stats = {
            "total_matches": len(matches),
            "balanced_matches": 0,
            "unbalanced_matches": 0,
            "total_revenue": 0.0,
            "total_expenses": 0.0,
            "net_balance": 0.0,
            "balance_discrepancies": [],
        }

        for match in matches:
            revenue = match.get("revenue", {})
            expenses = match.get("expenses", [])

            revenue_amount = abs(revenue.get("amount", 0))
            expense_total = sum(abs(exp.get("amount", 0)) for exp in expenses)

            stats["total_revenue"] += revenue_amount
            stats["total_expenses"] += expense_total

            balance = self.calculate_match_balance(match)

            if self.is_balanced(match):
                stats["balanced_matches"] += 1
            else:
                stats["unbalanced_matches"] += 1
                stats["balance_discrepancies"].append(
                    {
                        "match": match,
                        "balance": balance,
                        "revenue_amount": revenue_amount,
                        "expense_total": expense_total,
                    }
                )

        stats["net_balance"] = stats["total_revenue"] - stats["total_expenses"]

        return stats

    def suggest_expense_combination(
        self, revenue_amount: float, available_expenses: List[Dict], top_n: int = 3
    ) -> List[Dict]:
        """
        Suggest best expense combinations for a given revenue amount

        Args:
            revenue_amount: Revenue amount to match (positive)
            available_expenses: List of available expense dictionaries
            top_n: Number of suggestions to return

        Returns:
            List of suggested combinations with scores
        """
        suggestions = []

        # Find exact matches first
        exact_combinations = self.find_expense_combinations(
            revenue_amount, available_expenses, max_combo_size=5
        )

        for combo in exact_combinations[:top_n]:
            combo_sum = sum(abs(exp.get("amount", 0)) for exp in combo)
            suggestions.append(
                {
                    "expenses": combo,
                    "total_amount": combo_sum,
                    "balance": revenue_amount - combo_sum,
                    "match_type": "exact",
                    "score": 1.0,
                }
            )

        # If we don't have enough suggestions, find close matches
        if len(suggestions) < top_n:
            close_matches = self._find_close_combinations(
                revenue_amount, available_expenses, top_n - len(suggestions)
            )
            suggestions.extend(close_matches)

        return suggestions

    def _find_close_combinations(
        self, target_amount: float, expenses: List[Dict], top_n: int
    ) -> List[Dict]:
        """
        Find expense combinations close to target amount

        Args:
            target_amount: Target amount
            expenses: List of expense dictionaries
            top_n: Number of suggestions to return

        Returns:
            List of close matches sorted by proximity
        """
        close_matches = []

        # Try combinations of different sizes (limit to avoid performance issues)
        max_expenses = min(10, len(expenses))

        for size in range(1, min(6, max_expenses + 1)):
            for combo in combinations(expenses[:max_expenses], size):
                combo_sum = sum(abs(exp.get("amount", 0)) for exp in combo)
                difference = abs(combo_sum - target_amount)

                # Only consider if reasonably close (within 10%)
                if difference < target_amount * 0.1:
                    proximity_score = max(0, 1 - (difference / target_amount))

                    close_matches.append(
                        {
                            "expenses": list(combo),
                            "total_amount": combo_sum,
                            "balance": target_amount - combo_sum,
                            "match_type": "approximate",
                            "score": proximity_score,
                            "difference": difference,
                        }
                    )

        # Sort by score (best matches first)
        close_matches.sort(key=lambda x: x["score"], reverse=True)

        return close_matches[:top_n]

    def group_by_match_status(self, df: pd.DataFrame) -> Dict[str, pd.DataFrame]:
        """
        Group transactions by match status

        Args:
            df: DataFrame with transactions

        Returns:
            Dictionary of DataFrames grouped by status
        """
        grouped = {
            "matched": df[df["match_status"] == "matched"],
            "unmatched": df[df["match_status"] == "unmatched"],
            "pending": df[df["match_status"] == "pending_review"],
        }

        return grouped

    def calculate_reconciliation_progress(
        self, total_transactions: int, matched_transactions: int
    ) -> Dict:
        """
        Calculate reconciliation progress statistics

        Args:
            total_transactions: Total number of transactions
            matched_transactions: Number of matched transactions

        Returns:
            Dictionary with progress statistics
        """
        if total_transactions == 0:
            return {
                "progress_percentage": 0.0,
                "total_transactions": 0,
                "matched_transactions": 0,
                "unmatched_transactions": 0,
            }

        progress_percentage = (matched_transactions / total_transactions) * 100

        return {
            "progress_percentage": round(progress_percentage, 2),
            "total_transactions": total_transactions,
            "matched_transactions": matched_transactions,
            "unmatched_transactions": total_transactions - matched_transactions,
        }

    def validate_all_matches(
        self, matches: List[Dict]
    ) -> Tuple[List[Dict], List[Dict]]:
        """
        Validate all matches and separate valid from invalid

        Args:
            matches: List of matched groups

        Returns:
            Tuple of (valid_matches, invalid_matches)
        """
        valid_matches = []
        invalid_matches = []

        for match in matches:
            is_valid, message = self.validate_match(match)

            if is_valid:
                valid_matches.append(match)
            else:
                match["validation_error"] = message
                invalid_matches.append(match)

        return valid_matches, invalid_matches

    def calculate_match_group_id(self, match_index: int) -> str:
        """
        Generate unique match group ID

        Args:
            match_index: Index of the match

        Returns:
            Match group ID string
        """
        return f"MG_{match_index:04d}"

    def assign_match_groups(
        self, df: pd.DataFrame, matches: List[Dict]
    ) -> pd.DataFrame:
        """
        Assign match group IDs to transactions in DataFrame

        Args:
            df: DataFrame with transactions
            matches: List of matched groups

        Returns:
            Updated DataFrame with match group assignments
        """
        df_copy = df.copy()

        for idx, match in enumerate(matches):
            match_group_id = self.calculate_match_group_id(idx)
            confidence = match.get("confidence", 0.0)

            # Update revenue transaction
            revenue = match.get("revenue", {})
            if revenue:
                rev_idx = revenue.get("original_index")
                if rev_idx is not None and rev_idx in df_copy.index:
                    df_copy.at[rev_idx, "match_status"] = "matched"
                    df_copy.at[rev_idx, "match_group_id"] = str(match_group_id)
                    df_copy.at[rev_idx, "match_confidence"] = confidence

            # Update expense transactions
            expenses = match.get("expenses", [])
            for expense in expenses:
                exp_idx = expense.get("original_index")
                if exp_idx is not None and exp_idx in df_copy.index:
                    df_copy.at[exp_idx, "match_status"] = "matched"
                    df_copy.at[exp_idx, "match_group_id"] = match_group_id
                    df_copy.at[exp_idx, "match_confidence"] = confidence

        return df_copy
