"""
Finance Reconciliation Automation - Main Flask Application
"""

import os
import json
from flask import (
    Flask,
    render_template,
    request,
    jsonify,
    session,
    send_file,
    redirect,
    url_for,
)
from werkzeug.utils import secure_filename
import pandas as pd
from datetime import datetime
import uuid

from config import Config
from modules import FileHandler, EntityMatcher, BalanceCalculator, Exporter

# Initialize Flask app
app = Flask(__name__)
app.config.from_object(Config)
Config.init_app(app)

# Initialize modules
file_handler = FileHandler(app.config)
entity_matcher = EntityMatcher(app.config)
balance_calculator = BalanceCalculator(app.config)
exporter = Exporter(app.config)


# ==================== UTILITY FUNCTIONS ====================


def get_session_id():
    """Get or create session ID"""
    if "session_id" not in session:
        session["session_id"] = str(uuid.uuid4())
    return session["session_id"]


def get_session_data(key, default=None):
    """Get data from session"""
    session_id = get_session_id()
    session_key = f"{session_id}_{key}"
    return session.get(session_key, default)


def set_session_data(key, value):
    """Set data in session"""
    session_id = get_session_id()
    session_key = f"{session_id}_{key}"
    session[session_key] = value


def clear_session_data():
    """Clear all session data"""
    session_id = session.get("session_id")
    if session_id:
        keys_to_remove = [key for key in session.keys() if key.startswith(session_id)]
        for key in keys_to_remove:
            session.pop(key, None)


# ==================== ROUTES ====================


@app.route("/")
def index():
    """Main upload page"""
    clear_session_data()
    return render_template("index.html")


@app.route("/upload", methods=["POST"])
def upload_file():
    """Handle file upload"""
    try:
        if "file" not in request.files:
            return jsonify({"success": False, "message": "No file uploaded"}), 400

        file = request.files["file"]

        # Save file
        success, message, file_path = file_handler.save_uploaded_file(file)

        if not success:
            return jsonify({"success": False, "message": message}), 400

        # Read file
        success, message, df = file_handler.read_file(file_path)

        if not success:
            return jsonify({"success": False, "message": message}), 400

        # Analyze columns
        analysis = file_handler.analyze_columns(df)

        # Store data in session
        set_session_data("file_path", file_path)
        set_session_data("file_name", file.filename)
        set_session_data("df_json", df.to_json(orient="split"))
        set_session_data("analysis", analysis)

        return jsonify(
            {
                "success": True,
                "message": message,
                "columns": analysis["all_columns"],
                "suggested_amount": analysis["suggested_amount_column"],
                "suggested_description": analysis["suggested_description_column"],
            }
        )

    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500


@app.route("/select_columns", methods=["POST"])
def select_columns():
    """Process column selection and start matching"""
    try:
        data = request.get_json()
        amount_column = data.get("amount_column")
        description_column = data.get("description_column")

        if not amount_column or not description_column:
            return (
                jsonify({"success": False, "message": "Please select both columns"}),
                400,
            )

        # Get DataFrame from session
        df_json = get_session_data("df_json")
        if not df_json:
            return (
                jsonify(
                    {
                        "success": False,
                        "message": "No data found. Please upload file again",
                    }
                ),
                400,
            )

        df = pd.read_json(df_json, orient="split")

        # Process transactions
        success, message, processed_df = file_handler.process_transactions(
            df, amount_column, description_column
        )

        if not success:
            return jsonify({"success": False, "message": message}), 400

        # Store processed data
        set_session_data("processed_df_json", processed_df.to_json(orient="split"))
        set_session_data("amount_column", amount_column)
        set_session_data("description_column", description_column)

        return jsonify({"success": True, "message": message})

    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500


@app.route("/auto_match", methods=["POST"])
def auto_match():
    """Perform automatic matching"""
    try:
        # Get processed DataFrame
        processed_df_json = get_session_data("processed_df_json")
        if not processed_df_json:
            return (
                jsonify({"success": False, "message": "No processed data found"}),
                400,
            )

        processed_df = pd.read_json(processed_df_json, orient="split")

        # Perform auto matching
        matches, unmatched_expenses, unmatched_revenues = entity_matcher.auto_match_all(
            processed_df
        )

        # Validate matches
        valid_matches, invalid_matches = balance_calculator.validate_all_matches(
            matches
        )

        # Update DataFrame with match information
        updated_df = balance_calculator.assign_match_groups(processed_df, valid_matches)

        # Generate review items for unmatched transactions
        review_items = entity_matcher.generate_review_items(
            unmatched_revenues, unmatched_expenses
        )

        # Calculate statistics
        summary = file_handler.get_summary_statistics(updated_df)
        balance_stats = balance_calculator.calculate_total_balance(valid_matches)

        # Store results in session
        set_session_data("matches", json.dumps(valid_matches, default=str))
        set_session_data("review_items", json.dumps(review_items, default=str))
        set_session_data("updated_df_json", updated_df.to_json(orient="split"))
        set_session_data(
            "unmatched_expenses_json", unmatched_expenses.to_json(orient="split")
        )
        set_session_data(
            "unmatched_revenues_json", unmatched_revenues.to_json(orient="split")
        )

        return jsonify(
            {
                "success": True,
                "matched_count": len(valid_matches),
                "review_count": len(review_items),
                "summary": summary,
                "balance_stats": balance_stats,
            }
        )

    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500


@app.route("/matching")
def matching_page():
    """Display matching page"""
    return render_template("matching.html")


@app.route("/get_matches")
def get_matches():
    """Get matched items for display"""
    try:
        matches_json = get_session_data("matches", "[]")
        matches = json.loads(matches_json)

        return jsonify({"success": True, "matches": matches})

    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500


@app.route("/review")
def review_page():
    """Display review page for manual matching"""
    return render_template("review.html")


@app.route("/get_review_items")
def get_review_items():
    """Get items that need manual review"""
    try:
        review_items_json = get_session_data("review_items", "[]")
        review_items = json.loads(review_items_json)

        return jsonify({"success": True, "review_items": review_items})

    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500


@app.route("/confirm_match", methods=["POST"])
def confirm_match():
    """Confirm a manual match"""
    try:
        data = request.get_json()
        revenue_index = data.get("revenue_index")
        expense_indices = data.get("expense_indices", [])

        if not revenue_index or not expense_indices:
            return (
                jsonify({"success": False, "message": "Invalid match data"}),
                400,
            )

        # Get current data
        updated_df_json = get_session_data("updated_df_json")
        matches_json = get_session_data("matches", "[]")
        unmatched_expenses_json = get_session_data("unmatched_expenses_json")
        unmatched_revenues_json = get_session_data("unmatched_revenues_json")

        updated_df = pd.read_json(updated_df_json, orient="split")
        matches = json.loads(matches_json)
        unmatched_expenses = pd.read_json(unmatched_expenses_json, orient="split")
        unmatched_revenues = pd.read_json(unmatched_revenues_json, orient="split")

        # Find revenue and expenses
        revenue = unmatched_revenues[
            unmatched_revenues["original_index"] == revenue_index
        ].iloc[0]
        selected_expenses = unmatched_expenses[
            unmatched_expenses["original_index"].isin(expense_indices)
        ]

        # Create new match
        new_match = {
            "match_type": "manual",
            "confidence": 1.0,
            "revenue": revenue.to_dict(),
            "expenses": [exp.to_dict() for _, exp in selected_expenses.iterrows()],
            "balance": revenue["amount"]
            + sum(exp["amount"] for _, exp in selected_expenses.iterrows()),
        }

        # Validate match
        is_valid, message = balance_calculator.validate_match(new_match)

        if not is_valid:
            return (
                jsonify(
                    {
                        "success": False,
                        "message": f"Invalid match: {message}",
                    }
                ),
                400,
            )

        # Add to matches
        matches.append(new_match)

        # Update DataFrame
        updated_df = balance_calculator.assign_match_groups(updated_df, matches)

        # Remove from unmatched
        unmatched_expenses = unmatched_expenses[
            ~unmatched_expenses["original_index"].isin(expense_indices)
        ]
        unmatched_revenues = unmatched_revenues[
            unmatched_revenues["original_index"] != revenue_index
        ]

        # Regenerate review items
        review_items = entity_matcher.generate_review_items(
            unmatched_revenues, unmatched_expenses
        )

        # Update session
        set_session_data("matches", json.dumps(matches, default=str))
        set_session_data("updated_df_json", updated_df.to_json(orient="split"))
        set_session_data(
            "unmatched_expenses_json", unmatched_expenses.to_json(orient="split")
        )
        set_session_data(
            "unmatched_revenues_json", unmatched_revenues.to_json(orient="split")
        )
        set_session_data("review_items", json.dumps(review_items, default=str))

        return jsonify(
            {
                "success": True,
                "message": "Match confirmed successfully",
                "remaining_reviews": len(review_items),
            }
        )

    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500


@app.route("/export_options")
def export_options_page():
    """Display export options page"""
    # Get summary data
    updated_df_json = get_session_data("updated_df_json")
    matches_json = get_session_data("matches", "[]")

    if not updated_df_json:
        return redirect(url_for("index"))

    updated_df = pd.read_json(updated_df_json, orient="split")
    matches = json.loads(matches_json)

    summary = file_handler.get_summary_statistics(updated_df)

    return render_template("export_options.html", summary=summary)


@app.route("/export", methods=["POST"])
def export_file():
    """Export reconciled file"""
    try:
        data = request.get_json()
        export_type = data.get("export_type")  # 'new' or 'update'
        file_format = data.get("file_format", "xlsx")

        # Get data from session
        updated_df_json = get_session_data("updated_df_json")
        matches_json = get_session_data("matches", "[]")
        file_path = get_session_data("file_path")
        file_name = get_session_data("file_name")

        if not updated_df_json or not file_path:
            return (
                jsonify({"success": False, "message": "No data to export"}),
                400,
            )

        updated_df = pd.read_json(updated_df_json, orient="split")
        matches = json.loads(matches_json)

        # Generate output filename
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        base_name = os.path.splitext(file_name)[0]

        if export_type == "new":
            # Create new grouped file
            output_filename = (
                f"{base_name}_reconciled_grouped_{timestamp}.{file_format}"
            )
            output_path = os.path.join(app.config["UPLOAD_FOLDER"], output_filename)

            success, message = exporter.create_new_reconciled_file(
                updated_df, matches, output_path, file_format
            )

        elif export_type == "update":
            # Update existing file
            status_columns = data.get("status_columns", ["Reconciliation Status"])
            status_text = data.get("status_text", "RECONCILED")
            highlight = data.get("highlight", False)

            options = {
                "status_columns": status_columns,
                "status_text": status_text,
                "highlight": highlight,
            }

            success, message, output_path = exporter.update_existing_file(
                file_path, updated_df, matches, options
            )

        else:
            return (
                jsonify({"success": False, "message": "Invalid export type"}),
                400,
            )

        if success:
            # Store output path for download
            set_session_data("output_file", output_path)
            return jsonify(
                {
                    "success": True,
                    "message": message,
                    "download_url": url_for("download_file"),
                }
            )
        else:
            return jsonify({"success": False, "message": message}), 500

    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500


@app.route("/export_report", methods=["POST"])
def export_report():
    """Export detailed reconciliation report"""
    try:
        updated_df_json = get_session_data("updated_df_json")
        matches_json = get_session_data("matches", "[]")
        file_name = get_session_data("file_name")

        if not updated_df_json:
            return (
                jsonify({"success": False, "message": "No data to export"}),
                400,
            )

        updated_df = pd.read_json(updated_df_json, orient="split")
        matches = json.loads(matches_json)

        # Generate report filename
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        base_name = os.path.splitext(file_name)[0]
        report_filename = f"{base_name}_report_{timestamp}.xlsx"
        report_path = os.path.join(app.config["UPLOAD_FOLDER"], report_filename)

        success, message = exporter.generate_reconciliation_report(
            updated_df, matches, report_path
        )

        if success:
            set_session_data("output_file", report_path)
            return jsonify(
                {
                    "success": True,
                    "message": message,
                    "download_url": url_for("download_file"),
                }
            )
        else:
            return jsonify({"success": False, "message": message}), 500

    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500


@app.route("/download")
def download_file():
    """Download exported file"""
    try:
        output_file = get_session_data("output_file")

        if not output_file or not os.path.exists(output_file):
            return "File not found", 404

        return send_file(
            output_file,
            as_attachment=True,
            download_name=os.path.basename(output_file),
        )

    except Exception as e:
        return str(e), 500


@app.route("/get_summary")
def get_summary():
    """Get reconciliation summary"""
    try:
        updated_df_json = get_session_data("updated_df_json")
        matches_json = get_session_data("matches", "[]")

        if not updated_df_json:
            return (
                jsonify({"success": False, "message": "No data available"}),
                400,
            )

        updated_df = pd.read_json(updated_df_json, orient="split")
        matches = json.loads(matches_json)

        summary = file_handler.get_summary_statistics(updated_df)
        balance_stats = balance_calculator.calculate_total_balance(matches)

        return jsonify(
            {
                "success": True,
                "summary": summary,
                "balance_stats": balance_stats,
            }
        )

    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500


@app.route("/reset")
def reset():
    """Reset session and start over"""
    clear_session_data()
    return redirect(url_for("index"))


# ==================== ERROR HANDLERS ====================


@app.errorhandler(404)
def not_found(error):
    """Handle 404 errors"""
    return render_template("error.html", error="Page not found"), 404


@app.errorhandler(500)
def internal_error(error):
    """Handle 500 errors"""
    return render_template("error.html", error="Internal server error"), 500


# ==================== MAIN ====================

if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)
