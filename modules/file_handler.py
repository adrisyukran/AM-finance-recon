"""
File Handler Module
Handles file upload, parsing, and data extraction operations
"""

import os
import pandas as pd
from werkzeug.utils import secure_filename
from typing import Dict, List, Tuple, Optional
import numpy as np


class FileHandler:
    """Handle file operations for finance reconciliation"""

    def __init__(self, config):
        """
        Initialize FileHandler with configuration

        Args:
            config: Application configuration object
        """
        self.config = config
        self.upload_folder = config.UPLOAD_FOLDER
        self.allowed_extensions = config.ALLOWED_EXTENSIONS

    def allowed_file(self, filename: str) -> bool:
        """
        Check if file extension is allowed

        Args:
            filename: Name of the file to check

        Returns:
            bool: True if file extension is allowed, False otherwise
        """
        return (
            "." in filename
            and filename.rsplit(".", 1)[1].lower() in self.allowed_extensions
        )

    def save_uploaded_file(self, file) -> Tuple[bool, str, str]:
        """
        Save uploaded file to upload folder

        Args:
            file: FileStorage object from Flask request

        Returns:
            Tuple of (success, message, file_path)
        """
        if not file or file.filename == "":
            return False, "No file selected", ""

        if not self.allowed_file(file.filename):
            return (
                False,
                f"File type not allowed. Allowed types: {', '.join(self.allowed_extensions)}",
                "",
            )

        # Secure the filename
        filename = secure_filename(file.filename)

        # Create unique filename to avoid conflicts
        base_name, ext = os.path.splitext(filename)
        counter = 1
        final_filename = filename

        while os.path.exists(os.path.join(self.upload_folder, final_filename)):
            final_filename = f"{base_name}_{counter}{ext}"
            counter += 1

        file_path = os.path.join(self.upload_folder, final_filename)

        try:
            file.save(file_path)
            return True, "File uploaded successfully", file_path
        except Exception as e:
            return False, f"Error saving file: {str(e)}", ""

    def read_file(self, file_path: str) -> Tuple[bool, str, Optional[pd.DataFrame]]:
        """
        Read CSV or Excel file into pandas DataFrame

        Args:
            file_path: Path to the file to read

        Returns:
            Tuple of (success, message, dataframe)
        """
        if not os.path.exists(file_path):
            return False, "File not found", None

        try:
            file_extension = os.path.splitext(file_path)[1].lower()

            if file_extension == ".csv":
                df = pd.read_csv(file_path)
            elif file_extension in [".xlsx", ".xls"]:
                df = pd.read_excel(file_path, engine="openpyxl")
            else:
                return False, "Unsupported file format", None

            if df.empty:
                return False, "File is empty", None

            return True, f"File loaded successfully ({len(df)} rows)", df

        except Exception as e:
            return False, f"Error reading file: {str(e)}", None

    def analyze_columns(self, df: pd.DataFrame) -> Dict:
        """
        Analyze DataFrame columns to identify potential amount and description columns

        Args:
            df: pandas DataFrame to analyze

        Returns:
            Dictionary containing column analysis results
        """
        analysis = {
            "all_columns": df.columns.tolist(),
            "numeric_columns": [],
            "text_columns": [],
            "suggested_amount_column": None,
            "suggested_description_column": None,
        }

        for col in df.columns:
            # Check for numeric columns
            if pd.api.types.is_numeric_dtype(df[col]):
                analysis["numeric_columns"].append(col)

                # Suggest as amount column if it has positive and negative values
                if not analysis["suggested_amount_column"]:
                    if df[col].min() < 0 and df[col].max() > 0:
                        analysis["suggested_amount_column"] = col
            else:
                # Check for text columns
                analysis["text_columns"].append(col)

                # Suggest as description column (longest text on average)
                if not analysis["suggested_description_column"]:
                    avg_length = df[col].astype(str).str.len().mean()
                    if (
                        avg_length > 10
                    ):  # Arbitrary threshold for meaningful descriptions
                        analysis["suggested_description_column"] = col

        # If no amount column suggested, use first numeric column
        if not analysis["suggested_amount_column"] and analysis["numeric_columns"]:
            analysis["suggested_amount_column"] = analysis["numeric_columns"][0]

        # If no description column suggested, use first text column
        if not analysis["suggested_description_column"] and analysis["text_columns"]:
            analysis["suggested_description_column"] = analysis["text_columns"][0]

        return analysis

    def process_transactions(
        self, df: pd.DataFrame, amount_column: str, description_column: str
    ) -> Tuple[bool, str, Optional[pd.DataFrame]]:
        """
        Process DataFrame to identify expenses and revenues

        Args:
            df: pandas DataFrame with transaction data
            amount_column: Name of column containing amounts
            description_column: Name of column containing descriptions

        Returns:
            Tuple of (success, message, processed_dataframe)
        """
        try:
            # Validate columns exist
            if amount_column not in df.columns:
                return False, f"Amount column '{amount_column}' not found", None

            if description_column not in df.columns:
                return (
                    False,
                    f"Description column '{description_column}' not found",
                    None,
                )

            # Create a copy to avoid modifying original
            processed_df = df.copy()

            # Add index column to track original row numbers
            processed_df["original_index"] = processed_df.index

            # Extract amount and description
            processed_df["amount"] = pd.to_numeric(
                processed_df[amount_column], errors="coerce"
            )
            processed_df["description"] = (
                processed_df[description_column].astype(str).str.strip()
            )

            # Remove rows with invalid amounts
            processed_df = processed_df.dropna(subset=["amount"])

            # Identify transaction type
            processed_df["transaction_type"] = processed_df["amount"].apply(
                lambda x: "expense" if x < 0 else "revenue" if x > 0 else "zero"
            )

            # Remove zero amount transactions
            processed_df = processed_df[processed_df["transaction_type"] != "zero"]

            # Add absolute amount column for easier calculations
            processed_df["abs_amount"] = processed_df["amount"].abs()

            # Add status columns for tracking
            processed_df["match_status"] = "unmatched"
            processed_df["match_group_id"] = None
            processed_df["match_confidence"] = None

            # Count transactions
            expense_count = len(
                processed_df[processed_df["transaction_type"] == "expense"]
            )
            revenue_count = len(
                processed_df[processed_df["transaction_type"] == "revenue"]
            )

            message = f"Processed {len(processed_df)} transactions ({expense_count} expenses, {revenue_count} revenues)"

            return True, message, processed_df

        except Exception as e:
            return False, f"Error processing transactions: {str(e)}", None

    def get_summary_statistics(self, df: pd.DataFrame) -> Dict:
        """
        Get summary statistics for processed transactions

        Args:
            df: Processed DataFrame with transactions

        Returns:
            Dictionary containing summary statistics
        """
        try:
            expenses = df[df["transaction_type"] == "expense"]
            revenues = df[df["transaction_type"] == "revenue"]

            summary = {
                "total_transactions": len(df),
                "expense_count": len(expenses),
                "revenue_count": len(revenues),
                "total_expense_amount": abs(expenses["amount"].sum()),
                "total_revenue_amount": revenues["amount"].sum(),
                "net_balance": df["amount"].sum(),
                "matched_count": len(df[df["match_status"] == "matched"]),
                "unmatched_count": len(df[df["match_status"] == "unmatched"]),
            }

            return summary

        except Exception as e:
            return {"error": str(e)}

    def export_to_csv(self, df: pd.DataFrame, output_path: str) -> Tuple[bool, str]:
        """
        Export DataFrame to CSV file

        Args:
            df: DataFrame to export
            output_path: Path where file should be saved

        Returns:
            Tuple of (success, message)
        """
        try:
            df.to_csv(output_path, index=False)
            return True, f"File exported successfully to {output_path}"
        except Exception as e:
            return False, f"Error exporting to CSV: {str(e)}"

    def export_to_excel(
        self, df: pd.DataFrame, output_path: str, highlight_matched: bool = False
    ) -> Tuple[bool, str]:
        """
        Export DataFrame to Excel file with optional highlighting

        Args:
            df: DataFrame to export
            output_path: Path where file should be saved
            highlight_matched: Whether to highlight matched rows

        Returns:
            Tuple of (success, message)
        """
        try:
            if highlight_matched:
                # Export with formatting
                with pd.ExcelWriter(output_path, engine="openpyxl") as writer:
                    df.to_excel(writer, index=False, sheet_name="Reconciliation")

                    # Get workbook and worksheet
                    workbook = writer.book
                    worksheet = writer.sheets["Reconciliation"]

                    # Apply highlighting
                    from openpyxl.styles import PatternFill

                    yellow_fill = PatternFill(
                        start_color=self.config.DEFAULT_HIGHLIGHT_COLOR,
                        end_color=self.config.DEFAULT_HIGHLIGHT_COLOR,
                        fill_type="solid",
                    )

                    # Highlight matched rows (skip header)
                    for idx, row in df.iterrows():
                        if row.get("match_status") == "matched":
                            excel_row = (
                                idx + 2
                            )  # +2 because Excel is 1-indexed and has header
                            for cell in worksheet[excel_row]:
                                cell.fill = yellow_fill

            else:
                # Simple export without formatting
                df.to_excel(output_path, index=False)

            return True, f"File exported successfully to {output_path}"

        except Exception as e:
            return False, f"Error exporting to Excel: {str(e)}"
